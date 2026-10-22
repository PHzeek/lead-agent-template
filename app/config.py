"""Central settings, read once from environment variables (.env locally, Vercel env in prod)."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

def _bool(name:str, default:str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes"}

@dataclass(frozen=True)
class Settings:
    open_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-6-luna"))
    price_input_per_m: float = field(default_factory=lambda: float(os.getenv("PRICE_INPUT_PER_M", "0.10")))
    price_output_per_m: float = field(default_factory=lambda: float(os.getenv("PRICE_OUTPUT_PER_M", "0.50")))
    hubspot_service_key: str = field(default_factory=lambda: os.getenv("HUBSPOT_SERVICE_KEY", ""))
    resend_api_key: str = field(default_factory=lambda: os.getenv("RESEND_API_KEY", ""))
    from_email: str = field(default_factory=lambda: os.getenv("FROM_EMAIL", ""))
    sender_name: str = field(default_factory=lambda: os.getenv("SENDER_NAME", "The team"))
    owner_email: str = field(default_factory=lambda: os.getenv("OWNER_EMAIL", ""))
    send_emails: bool = field(default_factory=lambda: _bool("SEND_EMAILS"))
    booking_url: str = field(default_factory=lambda: os.getenv("BOOKING_URL", "https://cal.com/your-handle/discovery-call"))
    audit_checklist_url: str = field(default_factory=lambda: os.getenv("AUDIT_CHECKLIST_URL", ""))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./leads.db"))
    cron_secret: str = field(default_factory=lambda: os.getenv("CRON_SECRET", ""))
    allowed_origins: list[str] = field(
        default_factory=lambda: [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    )
    max_attempts: int = 5

# Values copied from .env.example that must never reach a real customer.
PLACEHOLDER_MARKERS = ("your-handle", "yourdomain.com", "you@", "change-me", "...")


def config_problems(s: Settings) -> list[str]:
    """Settings that would break a live send. Empty list = safe to send real emails.

    Every check here is a bug that passed all tests and still broke the live deploy (see docs/BREAKLOG.md, Oct 19-21).
    """
    if not s.send_emails:
        return []  # dry-run mode: placeholders are fine
    problems = []
    checks = {
        "RESEND_API_KEY": s.resend_api_key,
        "FROM_EMAIL": s.from_email,
        "OWNER_EMAIL": s.owner_email,
        "BOOKING_URL": s.booking_url,
        "CRON_SECRET": s.cron_secret,
    }
    for name, value in checks.items():
        if not value.strip():
            problems.append(f"{name} is empty")
        elif any(m in value for m in PLACEHOLDER_MARKERS):
            problems.append(f"{name} still looks like a placeholder")
    if s.audit_checklist_url and any(m in s.audit_checklist_url for m in PLACEHOLDER_MARKERS):
        problems.append("AUDIT_CHECKLIST_URL still looks like a placeholder (set a real link or delete it)")
    return problems


def get_settings() -> Settings:
    return Settings()
