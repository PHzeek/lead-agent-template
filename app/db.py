"""Lead log: every lead is saved BEFORE any processing, so nothing is lost if a step fails."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, Float, Integer, MetaData, String, Table, Text,
                        create_engine, insert, select, update)

from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

metadata = MetaData()

leads = Table(
    "leads",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("dedupe_key", String(64), unique=True, nullable=False),
    Column("email", String(320), nullable=False),
    Column("payload", Text, nullable=False),
    # received -> scored -> synced -> done (or failed)
    Column("status", String(20), nullable=False, default="received"),
    Column("tier", String(20)),
    Column("score", Integer),
    Column("score_json", Text),
    Column("hubspot_id", String(40)),
    Column("email_status", String(20)),
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error", Text),
    Column("model", String(60)),
    Column("input_tokens", Integer),
    Column("output_tokens", Integer),
    Column("cost_usd", Float),
    Column("latency_ms", Integer),
    Column("received_at", DateTime(timezone=True), nullable=False),
    Column("scored_at", DateTime(timezone=True)),
    Column("synced_at", DateTime(timezone=True)),
    Column("emailed_at", DateTime(timezone=True)),

)

def now() -> datetime:
    return datetime.now(timezone.utc)

def make_engine(url: str) -> Engine:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("sqlite"):
        # FastAPI runs requests in worker threads; in-memory SQLite (tests) needs one shared connection.
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)

class LeadRepo:
    def __init__(self, engine: Engine):
        self.engine = engine
        metadata.create_all(engine)

    @staticmethod
    def dedupe_key(email: str, message: str, day: str) -> str:
        raw = f"{email.strip().lower()}|{message.strip().lower()}|{day}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def insert(self, email: str, payload: dict) -> tuple[str, bool]:
        """Returns (lead_id, created. Same email) + message on the same day = duplicate."""
        received = now()
        key = self.dedupe_key(email, payload.get("message", ""), received.date().isoformat())
        with self.engine.begin() as conn:
            existing = conn.execute(select(leads.c.id).where(leads.c.dedupe_key == key)).first()
            if existing:
                return existing.id, False
            lead_id = str(uuid.uuid4())
            conn.execute(insert(leads).values(
                id=lead_id, dedupe_key=key, email=email, payload=json.dumps(payload),
                status="received", attempts=0, received_at=received,
            ))
            return lead_id, True

    def get(self, lead_id: str) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(select(leads).where(leads.c.id == lead_id)).mappings().first()
            return dict(row) if row else None

    def update(self, lead_id: str, **values) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(leads).where(leads.c.id == lead_id).values(**values))

    def pending(self, max_attempts: int, limit: int = 25) -> list[str]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(leads.c.id)
                .where(leads.c.status.in_(["received", "scored", "synced"]))
                .where(leads.c.attempts < max_attempts)
                .order_by(leads.c.received_at)
                .limit(limit)
            ).all()
            return [r.id for r in rows]

    def all(self) -> list[dict]:
        with self.engine.begin() as conn: 
            return [dict(r) for r in conn.execute(select(leads)).mappings().all()]
