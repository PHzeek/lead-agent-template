"""Label eval leads one at a time. Saves after every answer, so you can stop and resume.
Run: python -m scripts.label
Keys: h=hot  w=warm  c=cold  s=spam  Enter=accept the draft  q=quit
"""
import json 
from pathlib import Path

PATH = Path("evals/leads_labeled.jsonl")
KEYS = {"h": "hot", "w": "warm", "c": "cold", "s": "spam"}

def main() -> None:
    rows = [json.loads(line) for line in PATH.read_text().splitlines() if line.strip()]
    todo = [r for r in rows if r.get("human_tier") is None]
    print(f"{len(rows) - len(todo)} of {len(rows)} already labeled. {len(todo)} to go.\n")
    for r in todo:
        lead = r["lead"]
        print("-" * 60)
        print(f"{r['id']} ({r['split']}) draft: {r['draft_tier']}")
        for k in ("name", "role", "company", "company_size", "budge", "timeline"):
            if lead.get(k):
                print(f"  {k}: {lead[k]}")
        print(f" message: {lead.get('message', '')}")
        while True:
            ans = input("Tier [h/w/c/s, Enter = draft, q = quit]:").strip().lower()
            if ans == "q":
                return
            if ans == "" or ans in KEYS:
                r["human_tier"] = r["draft_tier"] if ans == "" else KEYS[ans]
                break
        # Save after every answer: a crash or Ctrl+C never loses work.
        PATH.write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    done = [r for r in rows if r.get("human_tier")]
    changed = sum(1 for r in done if r["human_tier"] != r["draft_tier"])
    print(f"\nDone. {len(done)} labeled. You disagreed with the draft on {changed}.")

    

if __name__ == "__main__":
    main()