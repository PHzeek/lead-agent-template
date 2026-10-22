"""The AI layer: turn a lead into a structured LeadScore using an LLM with structured outputs."""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openai import OpenAI

from .config import Settings
from .models import LeadIn, LeadScore

DEFAULT_PROMPT = Path(__file__).parent / "prompts" / "score_lead_v2.md"



class ScoringError(RuntimeError):
    pass


@dataclass
class ScoreResult:
    score: LeadScore
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float


class Scorer(Protocol):
    def score(self, lead: LeadIn) -> ScoreResult: ...



def render_lead(lead: LeadIn) -> str:
    """Wrap the lead as clearly delimited data (helps resist prompt injection)."""
    data = lead.model_dump(exclude={"hp"})
    return "Classify this lead.\n<lead>\n" + json.dumps(data, indent=2) + "\n</lead>"


def normalize(score: LeadScore) -> LeadScore:
    """Guardrails on model output: clamp score into its tier's  band and trim long text."""
    bands = {"hot": (75, 100), "warm": (50, 74), "cold": (15, 49), "spam": (0, 14)}
    lo, hi = bands[score.tier]
    line = score.personalization_line.strip()
    if "http" in line.lower() or "www." in line.lower() or len(line) > 220 or score.tier == "spam":
        line = ""
    return score.model_copy(
        update={
            "score":max(lo, min(hi, score.score)),
            "fit_reasons": score.fit_reasons[:3],
            "risks": score.risks[:3],
            "missing_info": score.missing_info[:5],
            "personalization_line": line
        }
    )


class OpenAIScorer:
    def __init__(self, settings: Settings, client: OpenAI | None = None, prompt_path: Path = DEFAULT_PROMPT):
        self.settings = settings
        self._client = client
        self.prompt = Path(prompt_path).read_text()

    @property
    def client(self) -> OpenAI:
        # Created on first use, so the app can start ( and reject bad input) even before keys are set.
        if self._client is None:
            self._client = OpenAI(api_key=self.settings.open_api_key, timeout=30, max_retries=2)
        return self._client

    def score(self, lead: LeadIn) -> ScoreResult:
        start = time.perf_counter()
        response = self.client.responses.parse(
            model=self.settings.llm_model,
            input=[
                {"role":"system", "content": self.prompt},
                {"role": "user", "content": render_lead(lead)},
            ],
            text_format=LeadScore,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ScoringError("Model returned no parsed output (refusal or incomplete response)")
        usage = getattr(response, "usage", None)
        in_tok = getattr(usage, "input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        cost = in_tok / 1e6 * self.settings.price_input_per_m + out_tok / 1e6 * self.settings.price_output_per_m
        return ScoreResult(
            score=normalize(parsed),
            model=self.settings.llm_model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=int((time.perf_counter() - start) * 1000),
            cost_usd=round(cost, 6),
        )



