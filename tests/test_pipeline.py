"""Run: pytest -q   (no API keys needed; external services are faked)"""
import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import LeadRepo, make_engine
from app.emailer import DryRunSender, booking_link, compose_followup
from app.models import LeadIn, LeadScore
from app.pipeline import Pipeline
from app.scoring import ScoreResult, normalize


def make_score(tier="hot", score=90, line="Missing after-hours inquiries is a common, fixable leak."):
    return LeadScore(tier=tier, score=score, confidence="high", use_case="lead follow-up",
                     fit_reasons=["Owner", "Budget 15+"], risks=[], missing_info=["CRM used"],
                     personalization_line=line)


class FakeScorer:
    def __init__(self, tier="hot", fail_times=0):
        self.tier, self.fail_times, self.calls = tier, fail_times, 0

    def score(self, lead):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TimeoutError("LLM timeout")
        return ScoreResult(score=make_score(self.tier), model="fake", input_tokens=800,
                           output_tokens=150, latency_ms=1200, cost_usd=0.000155)


class FakeCRM:
    def __init__(self, fail_times=0):
        self.fail_times, self.calls, self.upserts = fail_times, 0, []

    def upsert_contact(self, lead, score, lead_id, tier_override=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ConnectionError("HubSpot 503")
        self.upserts.append((lead.email, tier_override or (score.tier if score else None)))
        return "12345"


SETTINGS = Settings(owner_email="owner@me.example", booking_url="https://cal.com/me/call",
                    database_url="sqlite://", cron_secret="s3cret", max_attempts=3)
LEAD = LeadIn(name="Maria Lopez", email="maria@brightsmiles.example", company="Bright Smiles",
              budget="15k+", timeline="now", message="We miss after-hours inquiries.")


def build(scorer=None, crm=None):
    repo = LeadRepo(make_engine("sqlite://"))
    sender = DryRunSender()
    p = Pipeline(repo, scorer or FakeScorer(), crm or FakeCRM(), sender, SETTINGS)
    return p, repo, sender


def test_hot_lead_happy_path():
    p, repo, sender = build()
    lead_id, _ = repo.insert(LEAD.email, LEAD.model_dump())
    assert p.process(lead_id) == "done"
    row = repo.get(lead_id)
    assert row["tier"] == "hot" and row["hubspot_id"] == "12345" and row["email_status"] == "sent"
    assert [e.to for e in sender.sent] == ["maria@brightsmiles.example", "owner@me.example"] # follow-up + owner alert
    assert "cal.com/me/call?name=Maria+Lopez&email=maria%40brightsmiles.example" in sender.sent[0].text


def test_honeypot_skips_llm_and_email():
    scorer = FakeScorer()
    p, repo, sender = build(scorer=scorer)
    bot = LEAD.model_copy(update={"hp": "http://spam"})
    lead_id, _ = repo.insert(bot.email, bot.model_dump())
    assert p.process(lead_id) == "done"
    assert scorer.calls == 0 and sender.sent == [] and repo.get(lead_id)["tier"] == "spam"


def test_spam_tier_gets_no_email():
    p, repo, sender = build(scorer=FakeScorer(tier="spam"))
    lead_id, _ = repo.insert(LEAD.email, LEAD.model_dump())
    p.process(lead_id)
    assert repo.get(lead_id)["email_status"] == "skipped" and sender.sent == []


def test_retry_resumes_without_rescoring():
    scorer, crm = FakeScorer(), FakeCRM(fail_times=1)
    p, repo, _ = build(scorer=scorer, crm=crm)
    lead_id, _ = repo.insert(LEAD.email, LEAD.model_dump())
    assert p.process(lead_id) == "scored"      # CRM failed, score saved
    assert repo.get(lead_id)["attempts"] == 1
    assert p.retry_pending() == {lead_id: "done"}  # retry picks it up
    assert scorer.calls == 1                       # LLM not called (or paid for) twice


def test_permanent_llm_failure_parks_lead_as_needs_review():
    crm = FakeCRM()
    p, repo, sender = build(scorer=FakeScorer(fail_times=99), crm=crm)
    lead_id, _ = repo.insert(LEAD.email, LEAD.model_dump())
    for _ in range(3):
        p.process(lead_id)
    assert repo.get(lead_id)["status"] ==  "failed"
    assert crm.upserts == [(LEAD.email, "needs_review")]        # still lands in the CRM
    assert sender.sent[-1].to == "owner@me.example"
    assert "Next step" in sender.sent[-1].text                    # and told what to do                 # and a human is told


def test_duplicate_submission_is_ignored():
    _, repo, _ = build()
    a, created_a = repo.insert(LEAD.email, LEAD.model_dump())
    b, created_b = repo.insert(LEAD.email.upper(), LEAD.model_dump())
    assert created_a and not created_b and a == b


def test_normalize_guardrails():
    s = normalize(make_score(tier="warm", score=97, line="See https://evil.example for details"))
    assert s.score == 74 and s.personalization_line == ""


def test_cold_email_has_no_booking_push():
    email = compose_followup(LEAD, make_score(tier="cold", score=30), SETTINGS)
    assert "cal.com" not in email.text


def test_booking_link_encoding():
    assert booking_link("https://cal.com/me/call", LEAD) == \
    "https://cal.com/me/call?name=Maria+Lopez&email=maria%40brightsmiles.example"


def test_api_endpoints(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    from app import main
    p, repo, _ = build()
    main.app.dependency_overrides[main.get_pipeline] = lambda: p
    main.app.dependency_overrides[main.get_settings] = lambda: SETTINGS
    client = TestClient(main.app)
    r = client.post("/leads", json=json.loads(LEAD.model_dump_json()))
    assert r.status_code == 200 and r.json()["status"] == "done"
    assert client.post("/leads", json=json.loads(LEAD.model_dump_json())).json()["duplicate"] is True
    assert client.post("/cron/retry").status_code == 401
    m = client.get("/metrics", headers={"Authorization": "Bearer s3cret"}).json()
    assert m["leads_total"] == 1 and m["under_5_min_pct"] == 100.0 and m["leads_lost"] == 0
    main.app.dependency_overrides.clear()


def test_bad_input_rejected():
    from app import main
    client = TestClient(main.app)
    assert client.post("/leads", json={"name": "", "email": "not-an-email"}).status_code == 422



def test_resend_sender_builds_payload():
    import json, httpx
    from app.config import Settings
    from app.emailer import Email, ResendSender
    seen = {}
    def handler(req):
        seen["body"] = json.loads(req.read())
        return httpx.Response(200, json={"id": "em_1"})
    client = httpx.Client(base_url="https://api.resend.com", transport=httpx.MockTransport(handler))
    s = Settings(from_email="A <a@x.example>", owner_email="o@x.example")
    sid = ResendSender(s, client).send(Email("lead@x.example", "Hi", "Body"), "key-1")
    assert sid == "em_1" and seen["body"]["subject"] == "Hi" and seen["body"]["reply_to"] == "o@x.example"

def test_config_check_blocks_placeholders():
    # The Oct 19-21 go-live bugs: a placeholder key and a placeholder booking link passed every other test.
    from app.config import Settings, config_problems
    s = Settings(send_emails=True, resend_api_key="re_...", from_email="A <hello@yourdomain.com>",
                 owner_email="o@x.example", booking_url="https://cal.com/your-handle/discovery-call",
                 cron_secret="change-me-long-random-string")
    problems = " ".join(config_problems(s))
    for name in ("RESEND_API_KEY", "FROM_EMAIL", "BOOKING_URL", "CRON_SECRET"):
        assert name in problems
    assert "OWNER_EMAIL" not in problems


def test_config_check_passes_real_values_and_dry_run():
    from app.config import Settings, config_problems
    real = Settings(send_emails=True, resend_api_key="re_live_abc123", from_email="A <hello@acme.example>",
                    owner_email="o@acme.example", booking_url="https://calendly.com/acme/30min",
                    cron_secret="9f2c1d7e4b", audit_checklist_url="")
    assert config_problems(real) == []
    assert config_problems(Settings(send_emails=False, booking_url="https://cal.com/your-handle/x")) == []


def test_health_reports_config_without_secrets():
    from app import main
    from app.config import Settings
    main.app.dependency_overrides[main.get_settings] = lambda: Settings(send_emails=True, resend_api_key="re_...")
    body = TestClient(main.app).get("/health").json()
    main.app.dependency_overrides.clear()
    assert body == {"ok": True, "send_emails": True, "config_ok": False}
