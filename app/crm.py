"""HubSpot: create or update the contact (by email) with the AI score on custom properties."""
from typing import Protocol

import httpx

from .models import LeadIn, LeadScore

HUBSPOT_BASE = "https://api.hubapi.com"


class CRM(Protocol):
    def upsert_contact(self, lead: LeadIn, score: LeadScore | None, lead_id: str, tier_override: str | None = None) -> str: ...


def contact_properties(lead: LeadIn, score: LeadScore | None, lead_id: str, tier_override: str | None) -> dict:
    first, _, last = lead.name.strip().partition(" ")
    props = {
        "email": lead.email,
        "firstname": first,
        "lastname": last, 
        "company": lead.company,
        "website": lead.website,
        "jobtitle": lead.role,
        "ai_lead_id": lead_id,
        "ai_lead_tier": tier_override or (score.tier if score else "needs_review"),
    }
    if score:
        props.update({
            "ai_lead_score": str(score.score),
            "ai_use_case": score.use_case[:250],
            "ai_lead_summary": " | ".join(score.fit_reasons)[:2000],
            "ai_missing_info": " | ".join(score.missing_info)[:2000],
        })
    # Hubspot rejects empty strings on some properties: drop blanks
    return {k: v for k, v in props.items() if v not in ("", None)}


class HubSpotCRM:
    def __init__(self, service_key: str, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            base_url=HUBSPOT_BASE,
            headers={"Authorization": f"Bearer {service_key}", "Content-Type": "application/json"},
            timeout=15,
        )

    def upsert_contact(self, lead: LeadIn, score: LeadScore | None, lead_id: str, tier_override: str | None = None) -> str:
        body = {"inputs": [{
            "idProperty":"email",
            "id": lead.email,
            "properties": contact_properties(lead, score, lead_id, tier_override),
        }]}
        r = self.client.post("/crm/v3/objects/contacts/batch/upsert", json=body)
        r.raise_for_status()
        return str(r.json()["results"][0]["id"])