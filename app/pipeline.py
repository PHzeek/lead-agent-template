"""Orchestration. Each step saves its result, so a retry resumes where it failed instead of starting over."""
import json 

from .config import Settings
from .crm import CRM 
from .db import LeadRepo, now
from .emailer import Sender, compose_followup, compose_owner_alert
from .models import LeadIn, LeadScore
from .scoring import Scorer


class Pipeline:
    def __init__(self, repo: LeadRepo, scorer: Scorer, crm: CRM, sender: Sender, settings: Settings):
        self.repo, self.scorer, self.crm, self.sender, self.s = repo, scorer, crm, sender, settings

    def _alert_owner(self, lead: LeadIn, score: LeadScore | None, lead_id: str, reason: str) -> None:
        if not self.s.owner_email:
            return
        alert = compose_owner_alert(lead, score, lead_id, reason)
        alert.to = self.s.owner_email
        try:
            self.sender.send(alert, idempotency_key=f"{lead_id}-alert-{reason}")
        except Exception as e: # an alert failure must never break the pipeline
            print(f"[warn] owber alert failed: {e}")

    def process(self, lead_id: str) -> str:
        row = self.repo.get(lead_id)
        if row is None:
            raise KeyError(lead_id)
        if row["status"] in ("done", "failed"):
            return row["status"]
        lead = LeadIn(**json.loads(row["payload"]))
        score = LeadScore(**json.loads(row["score_json"])) if row["score_json"] else None
        status = row["status"]
        try:
            # Step 1: score
            if status == "received":
                if lead.hp: # honeypot filled = bot. No LLM cost, no email.
                    score = LeadScore(tier="spam", score=0, confidence="high", use_case="bot",
                                      fit_reasons=["Honey field was filled"], risks=[], missing_info=[],
                                      personalization_line="")
                    self.repo.update(lead_id, status="done", tier="spam", score=0, email_status="skipped",
                                     score_json=score.model_dump_json(), scored_at=now())
                    return "done"
                result = self.scorer.score(lead)
                score = result.score
                self.repo.update(lead_id, status="scored", tier=score.tier, score=score.score,
                                 score_json=score.model_dump_json(), model=result.model,
                                 input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                                 cost_usd=result.cost_usd, latency_ms=result.latency_ms, scored_at=now())
                status = "scored"

            # Step 2: CRM
            if status == "scored":
                hubspot_id = self.crm.upsert_contact(lead, score, lead_id)
                self.repo.update(lead_id, status="synced", hubspot_id=hubspot_id, synced_at=now())
                status = "synced"

            # Step 3: follow-up email (+ alert you on hot leads; a human still makes the call)
            if status == "synced":
                email = compose_followup(lead, score, self.s)
                if email is None:
                    self.repo.update(lead_id, status="done", email_status="skipped")
                else:
                    self.sender.send(email, idempotency_key=f"{lead_id}-followup")
                    self.repo.update(lead_id, status="done", email_status="sent", emailed_at=now())
                if score.tier == "hot":
                    self._alert_owner(lead, score, lead_id, "HOT lead")
                status = "done"
            return status

        except Exception as e:
            attempts = (row["attempts"] or 0) + 1
            self.repo.update(lead_id, attempts=attempts, last_error=f"{type(e).__name__}: {e}"[:1000])
            if attempts >= self.s.max_attempts:
                self._give_up(lead, score, lead_id, status)
                return "failed"
            return status

    def _give_up(self, lead: LeadIn, score: LeadScore | None, lead_id: str, status: str) -> None:
        """Zero leads lost: after max retries, still try to land the lead in the CRM and tell a human."""
        self.repo.update(lead_id, status="failed")
        if status == "received":     # scoring never worked, park it as needs_review
            try:
                self.crm.upsert_contact(lead, None, lead_id, tier_override="needs_review")
            except Exception as e:
                print(f"[warn] fallback CRM sync failed: {e}")
        self._alert_owner(lead, score, lead_id, f"FAILED at step '{status}'")

    def retry_pending(self) -> dict:
        results: dict[str, str] = {}
        for lead_id in self.repo.pending(self.s.max_attempts):
            results[lead_id] = self.process(lead_id)
        return results

            


        



