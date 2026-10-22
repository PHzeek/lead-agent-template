"""Follow-up emails: a fixed, human-written template per tier + one AI-personalized sentence."""
from dataclasses import dataclass
from html import escape
from typing import Protocol
from urllib.parse import urlencode

import httpx

from .config import Settings
from .models import LeadIn, LeadScore

@dataclass
class Email:
    to: str
    subject: str
    text: str



class Sender(Protocol):
    def send(self, email: Email, idempotency_key: str) -> str: ...


def booking_link(base_url:str, lead: LeadIn) -> str:
    """Cal.com prefills the booking form from ?name=&email= query parameters."""
    sep = "&" if "?" in base_url else "?"
    return base_url + sep + urlencode({"name": lead.name, "email": lead.email})

def compose_followup(lead: LeadIn, score: LeadScore, s: Settings) -> Email | None:
    """Returns None when no email should go out (spam)."""
    if score.tier == "spam":
        return None
    first = lead.name.split()[0]
    opener = score.personalization_line or "Thanks for reaching out about AI for your business."
    link = booking_link(s.booking_url, lead)
    checklist = f"\n\nHere's the AI Business Audit checklist I use with clients: {s.audit_checklist_url}" if s.audit_checklist_url else ""

    if score.tier == "hot":
        subject = f"{first}, next step on your AI project"
        body = (f"Hi {first},\n\n{opener}\n\n"
        "Based on what you shared, a short call is the fastest way to map where AI fits and what it would take. "
        f"Pick any time that works here:\n{link}\n\n"
        f"Talk soon,\n{s.sender_name}")

    elif score.tier == "warm":
        subject = f"Thanks {first}, a couple of ideas"
        body = (f"Hi {first},\n\n{opener}{checklist}\n\n"
                f"If it'd help to talk it through, you can grab a time here:\n{link}\n\n"
                f"Best,\n{s.sender_name}")

    else: # cold
        subject = f"Thanks for reaching out, {first}"
        body = (f"Hi {first}, \n\n{opener}{checklist}\n\n"
                "Whenever you have a specific process in mind, just reply to this email.\n\n"
                f"Best,\n{s.sender_name}")
    return Email(to=lead.email, subject=subject, text=body)

def compose_owner_alert(lead: LeadIn, score: LeadScore | None, lead_id: str, reason: str) -> Email:
    lines = [f"Reason: {reason}", f"Lead: {lead.name} <{lead.email}>", f"Company: {lead.company or '-'}",
             f"Budget / timeline: {lead.budget} / {lead.timeline}", f"Message: {lead.message[:600]}"]
    if score:
        lines += [f"Tier: {score.tier} ({score.score})", f"Why: {' | '.join(score.fit_reasons)}"]
    lines.append("Next step: the system could not finish this lead automatically. Contact them yourself today.")
    lines.append(f"Lead ID: {lead_id}")
    return Email(to="", subject=f"[Lead agent] {reason}: {lead.name}", text="\n".join(lines))



class ResendSender:
    def __init__(self, s: Settings, client: httpx.Client | None = None):
        self.s = s
        self.client = client or httpx.Client(
            base_url="https://api.resend.com",
            headers={"Authorization": f"Bearer {s.resend_api_key}"},
        )

    
    def send(self, email: Email, idempotency_key: str) -> str:
        payload = {
            "from": self.s.from_email,
            "to": [email.to],
            "subject": email.subject,
            "text": email.text,
            "html": "<p>" + escape(email.text).replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>",
        }
        if self.s.owner_email and email.to != self.s.owner_email:
            payload["reply_to"] = self.s.owner_email
        # Idempotency-Key stops a retry from sending the same email twice.
        r = self.client.post("/emails", json=payload, headers={"Idempotency-Key": idempotency_key})
        r.raise_for_status()
        return r.json().get("id", "")


class DryRunSender:
        """Default until SEND_EMAILS=true. Records emails instead of sending them."""

        def __init__(self):
            self.sent: list[Email] = []

        def send(self, email: Email, idempotency_key: str) -> str:
            self.sent.append(email)
            print(f"[dry-run email] to={email.to} subject={email.subject!r}")
            return "dry-run"

        



    

        

        