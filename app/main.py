"""FastAPI entrypoint. Vercel finds the `app` object in app/main.py automatically."""
import os
import statistics
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import Settings, config_problems, get_settings
from .crm import HubSpotCRM
from .db import LeadRepo, make_engine
from .emailer import DryRunSender, ResendSender
from .models import LeadIn
from .pipeline import Pipeline
from .scoring import OpenAIScorer


@lru_cache
def get_pipeline() -> Pipeline:
    s = get_settings()
    problems = config_problems(s)
    if problems:
        # Fail loudly before any customer gets a broken email. The lead form returns 500, so you notice in seconds.
        raise RuntimeError("Refusing to send live emails: " + "; ".join(problems))
    repo = LeadRepo(make_engine(s.database_url))
    sender = ResendSender(s) if s.send_emails else DryRunSender()
    return Pipeline(repo, OpenAIScorer(s), HubSpotCRM(s.hubspot_service_key), sender, s)


def require_secret(authorization: str = Header(default=""), s: Settings = Depends(get_settings)) -> None:
    if not s.cron_secret or authorization != f"Bearer {s.cron_secret}":
        raise HTTPException(status_code=401, detail="unauthorized")


app = FastAPI(title="AI Lead Qualification Agent")
settings = get_settings()
if settings.allowed_origins:
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                       allow_methods=["POST", "GET"], allow_headers=["*"])


@app.get("/health")
def health(s: Settings = Depends(get_settings)) -> dict:
    # "ok" alone only proves the app is up. config_ok shows whether it is safe to send (no secret values exposed).
    return {"ok": True, "send_emails": s.send_emails, "config_ok": not config_problems(s)}


@app.post("/leads")
def create_lead(lead: LeadIn, pipeline: Pipeline = Depends(get_pipeline)) -> dict:
    # 1) Save first. Once this returns, the lead cannot be lost.
    lead_id, created = pipeline.repo.insert(lead.email, lead.model_dump())
    if not created:
        return {"ok": True, "lead_id": lead_id, "duplicate": True}
    # 2) Process now. Any failure is recorded and retried by /cron/retry; the visitor still sees success.
    status = pipeline.process(lead_id)
    return {"ok": True, "lead_id": lead_id, "status": status}


@app.post("/cron/retry", dependencies=[Depends(require_secret)])
def retry(pipeline: Pipeline = Depends(get_pipeline)) -> dict:
    results = pipeline.retry_pending()
    return {"processed": len(results), "results": results}


@app.get("/metrics", dependencies=[Depends(require_secret)])
def metrics(pipeline: Pipeline = Depends(get_pipeline)) -> dict:
    rows = pipeline.repo.all()
    response_s = sorted(
        (r["emailed_at"] - r["received_at"]).total_seconds()
        for r in rows if r["emailed_at"] and r["received_at"]
    )
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]

    def pct(values: list[float], p: float) -> float | None:
        if not values:
            return None
        return round(values[min(len(values) - 1, int(round(p * (len(values) - 1))))], 2)

    tiers: dict[str, int] = {}
    for r in rows:
        tiers[r["tier"] or "unscored"] = tiers.get(r["tier"] or "unscored", 0) + 1
    return {
        "leads_total": len(rows),
        "by_tier": tiers,
        "by_status": {s: sum(1 for r in rows if r["status"] == s) for s in ("received", "scored", "synced", "done", "failed")},
        "first_response_seconds": {"p50": pct(response_s, 0.5), "p95": pct(response_s, 0.95), "n": len(response_s)},
        "under_5_min_pct": round(100 * sum(1 for x in response_s if x <= 300) / len(response_s), 1) if response_s else None,
        "avg_llm_cost_usd": round(statistics.mean(costs), 6) if costs else None,
        "leads_lost": sum(1 for r in rows if r["status"] == "failed" and not r["hubspot_id"]),
    }


# Local development: serve the form at http://localhost:8000/ (on Vercel, public/ is served by the CDN).
_public = Path(__file__).resolve().parent.parent / "public"
if _public.is_dir() and not os.getenv("VERCEL"):
    app.mount("/", StaticFiles(directory=_public, html=True), name="public")



