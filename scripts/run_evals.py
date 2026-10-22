"""Sessions 11-12 and 16: measure how often the agent agrees with YOUR labels.
Run: python -m scripts.run_evals --split dev            (iterate the prompt on dev only)
     python -m scripts.run_evals --split test           (report this number publicly)
     python -m scripts.run_evals --prompt app/prompts/score_lead_v2.md --split dev"""
import argparse
import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.models import LeadIn
from app.scoring import DEFAULT_PROMPT, OpenAIScorer

TIERS = ["hot", "warm", "cold", "spam"]
DATA = Path("evals/leads_labeled.jsonl")


def load(split: str) -> list[dict]:
    rows = [json.loads(line) for line in DATA.read_text().splitlines() if line.strip()]
    rows = [r for r in rows if split == "all" or r["split"] == split]
    unlabeled = [r["id"] for r in rows if r.get("human_tier") not in TIERS]
    if unlabeled:
        raise SystemExit(f"Label these first (set human_tier): {unlabeled}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    ap.add_argument("--prompt", default=str(DEFAULT_PROMPT))
    args = ap.parse_args()

    rows = load(args.split)
    scorer = OpenAIScorer(get_settings(), prompt_path=Path(args.prompt))
    results, confusion = [], Counter()
    for r in rows:
        out = scorer.score(LeadIn(**r["lead"]))
        pred, gold = out.score.tier, r["human_tier"]
        confusion[(gold, pred)] += 1
        results.append({"id": r["id"], "human": gold, "agent": pred, "score": out.score.score, "latency_ms": out.latency_ms, "cost_usd": out.cost_usd,
                        "reasons": out.score.fit_reasons})
        print(f"{r["id"]:>4}  human={gold:<5} agent={pred:<5} {'OK' if gold == pred else 'MISS'}")

    n = len(results)
    agree = sum(1 for x in results if x["human"] == x["agent"])
    hot_total = sum(1 for x in results if x["human"] == "hot")
    hot_caught = sum(1 for x in results if x["human"] == "hot" and x["agent"] == "hot")
    hot_missed_as_cold = sum(1 for x in results if x["human"] == "hot" and x["agent"] in ("cold", "spam"))
    lat = sorted(x["latency_ms"] for x in results)

    summary = {
        "split": args.split, "prompt": args.prompt, "n": n,
        "agreement_pct": round(100 * agree / n, 1),
        "hot_recall_pct": round(100 * hot_caught / hot_total, 1) if hot_total else None,
        "hot_missed_as_cold_or_spam": hot_missed_as_cold,
        "latency_ms_p50": lat[n // 2], "latency_ms_p95": lat[min(n - 1, int(0.95 * (n -1)))],
        "cost_usd_total": round(sum(x["cost_usd"] for x in results), 5),
        "cost_usd_per_lead": round(statistics.mean(x["cost_usd"] for x in results), 6), 
    }
    print("\nConfusion matrix (rows = your label, columns = agent):")
    print("         " + "".join(f"{t:>7}" for t in TIERS))
    for g in TIERS:
        print(f"{g:>7} " + "".join(f"{confusion[(g, p)]:>7}" for p in TIERS))
    print("\n" + json.dumps(summary, indent=2))

    out_dir = Path("evals/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{args.split}.json"
    path.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(f"Saved {path}")


if __name__ == "__main__":
    main()