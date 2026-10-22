"""Data contracts: what comes in from the form, and what the LLM must return."""
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Tier = Literal["hot", "warm", "cold", "spam"]

class LeadIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: str = Field(default="", max_length=200)
    website: str = Field(default="", max_length=300)
    role: str = Field(default="", max_length=120)
    company_size: Literal["1-10", "11-50", "51-200", "201-1000", "1000+", "unknown"] = "unknown"
    budget: Literal["<1.5k", "1.5k-5k", "5k-15k", "15k+", "unknown"] = "unknown"
    timeline: Literal["now", "1-3 months", "3-6 months", "exploring", "unknown"] = "unknown"
    message: str = Field(default="", max_length=3000)
    source: str = Field(default="website", max_length=60)
    hp: str = Field(default="", max_length=200, description="Honeypot. Humans never fill this in.")

class LeadScore(BaseModel):
    """Structured output schema. The model is forced to return exactly this shape."""

    tier: Tier
    score: int = Field(description="0-100 overall fit and intent")
    confidence: Literal["high", "medium", "low"]
    use_case: str = Field(description="Short label for the problem, e.g. 'lead follow-up automation'")
    fit_reasons: list[str] = Field(description="1-3 evidence-based reasons for the tier")
    risks: list[str] = Field(description="0-3 reasons this might not be a fit")
    missing_info: list[str] = Field(description="Facts we'd need to confirm on a call")
    personalization_line: str = Field(description="One sentence that references what the lead actually wrote")

    