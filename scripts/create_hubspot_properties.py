"""Session 6: create the custom contact properties the agent writes to. Safe to re-run.
Run: python -m scripts.create_hubspot_properties"""
import httpx

from app.config import get_settings

GROUP = {"name": "ai_lead_agent", "label": "AI Lead Agent","displayOrder": -1}

PROPERTIES = [
    {"name": "ai_lead_tier", "label": "AI Lead Tier", "type": "enumeration", "fieldType": "select",
     "options": [{"label": t.replace("_", " ").title(), "value": t, "displayOrder":i}
                 for i, t in enumerate(["hot", "warm", "cold", "spam", "needs_review"])]},
   {"name": "ai_lead_score", "label": "AI Lead Score", "type": "number", "fieldType": "number"},
   {"name": "ai_use_case", "label": "AI Use Case", "type": "string", "fieldType": "text"},
   {"name": "ai_lead_summary", "label": "AI Fit Reasons", "type": "string", "fieldType": "textarea"},
   {"name": "ai_missing_info", "label": "AI Missing Info", "type": "string", "fieldType": "textarea"},
   {"name": "ai_lead_id", "label": "AI Lead ID", "type": "string", "fieldType": "text"},
]


def main() -> None:
    s = get_settings()
    client = httpx.Client(base_url="https://api.hubspot.com", timeout=15,
                          headers={"Authorization": f"Bearer {s.hubspot_service_key}"})
    r = client.post("crm/v3/properties/contacts/groups", json=GROUP)
    print("group:", "created" if r.status_code in (200, 201) else f"{r.status_code} {r.text[:120]}")
    for prop in PROPERTIES:
        r = client.post("/crm/v3/properties/contacts", json={**prop, "groupName": GROUP["name"]})
        if r.status_code in (200, 201):
            print(f"{prop['name']}: created")
        elif r.status_code == 409:
            print(f"{prop['name']}: already exists")
        else:
            print(f"{prop['name']}: ERROR {r.status_code} {r.text[:200]}")


if __name__ == "__main__":
    main()