"""Session 4: score 3 sample leads to prove the LLM + structured output works. Run: python -m scripts.smoke_score"""
from app.config import get_settings
from app.models import LeadIn
from app.scoring import OpenAIScorer

SAMPLES = [
    LeadIn(name="Maria Lopez", email="maria@brightsmiles.example", company="Bright Smiles Dental (3 locations)",
           role="Owner", company_size="11-50", budget="15k+", timeline="1-3 months",
           message="Our front desk misses web inquiries after hours and we lose new patients. Want AI to respond and book consults."),
    LeadIn(name="Tom", email="tom@gmail.example", message="just curious what AI can do",timeline="exploring"),
    LeadIn(name="SEO Pro", email="rank@seo-boost.example", message="We can get your site to #1 on Google. Reply for pricing!!!"),
]

if __name__ == "__main__":
    scorer = OpenAIScorer(get_settings())
    for lead in SAMPLES:
        r = scorer.score(lead)
        print(f"\n{lead.name}: {r.score.tier} ({r.score.score}), {r.latency_ms} ms, ${r.cost_usd:.5f}")
        print(r.score.model_dump_json(indent=2))
        