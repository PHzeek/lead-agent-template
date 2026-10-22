"""Post a test lead to a running app (local or deployed) and time the round trip.
Run: python -m scripts.send_test_lead http://localhost:8000 [hot|warm|cold|spam]
Set TEST_EMAIL=you@yourdomain.com to receive the follow-ups (plus-addressing keeps each test unique)."""
import os
import sys
import time
import uuid

import httpx

LEADS = {
    "hot": {"name": "Dana Reyes", "company": "Acme Publishing", "role": "Owner",
            "company_size": "11-50",
            "budget": "15k+", "timeline": "now",
            "message": "We get 200 web leads a month and reply to most of them a day later. Need AI to qualify and follow fast."},
    "warm": {"name": "Chris Patel", "company": "Northside Fitness", "role": "Marketing manager", "company_size": "11-50",
             "timeline": "3-6 months", "message": "Looking into automating memmber follow-ups next year."},
    "cold": {"name": "Sam Lee", "timeline": "exploring", "message": "What is an AI agent?"},
    "spam": {"name": "Link Builder", "message": "Buy backlinks now, 1000 links for $50 !!!"},
}

if __name__ == "__main__":
    base = sys.argv[1].rstrip("/")
    kind = sys.argv[2] if len(sys.argv) > 2 else "hot"
    lead = {**LEADS[kind], "email": os.getenv("TEST_EMAIL", "you@example.com").replace("@", f"+{kind}-{uuid.uuid4().hex[:6]}@", 1), "source": "website"}
    t = time.perf_counter()
    r = httpx.post(f"{base}/leads", json=lead, timeout=90)
    print(r.status_code, r.json(), f"{time.perf_counter() - t:.1f}s")