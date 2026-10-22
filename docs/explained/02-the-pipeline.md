# Layer 2: The pipeline (status track, honeypot, scoring)

![Animated pipeline with four save points: received, scored, synced, done. Scenario 1: a lead moves through every step and one AI call costs $0.00023. Scenario 2: HubSpot fails and the lead stops at scored with attempts = 1. Scenario 3: the retry resumes from scored, the AI step is skipped and the count stays at 1. Scenario 4: a bot fills the hidden field and the honeypot ends it at $0, tier spam, email skipped.](../visuals/layer2-save-points.gif)

## The idea

Save points. Each finished step updates the lead's status, like a save point in a video game. When something fails, the retry picks up from the last save point, not from the start. The AI step is the one you pay for, so it never runs twice for the same lead.

## Three ideas in this layer

| Idea | Analogy | Where |
|---|---|---|
| Status track | Save points in a game | `if status == "received"` … `if status == "scored"` in `app/pipeline.py` |
| Honeypot | A fake doorbell only burglars ring. Humans never see the hidden field, bots fill in everything | `if lead.hp:` runs before the AI |
| Structured scoring plus guardrails | The AI fills in a fixed form (`LeadScore`), then a supervisor checks it (`normalize`) | `responses.parse(..., text_format=LeadScore)`, then `normalize()` in `app/scoring.py` |

## In my words

> The status tracks the save points in the pipeline. If something fails, the retry begins at the last save point, not from the beginning. The honeypot catches spam and fakes quietly, ends them as done, and costs $0. This keeps the system updated on every lead's status.

## The code

`app/pipeline.py` (simplified):

```python
if status == "received":
    if lead.hp:                                   # bot: no AI, no email
        self.repo.update(lead_id, status="done", tier="spam")
        return "done"
    result = self.scorer.score(lead)              # the only paid step
    self.repo.update(lead_id, status="scored", tier=result.score.tier, ...)
    status = "scored"
if status == "scored":                            # retries start here if the CRM failed
    hubspot_id = self.crm.upsert_contact(lead, score, lead_id)
```

`app/scoring.py` `normalize()`, the supervisor (simplified):

```python
bands = {"hot": (75, 100), "warm": (50, 74), "cold": (15, 49), "spam": (0, 14)}
lo, hi = bands[score.tier]
if "http" in line.lower() or len(line) > 220: line = ""   # no links in our email
score = max(lo, min(hi, score.score))                    # the number must match the tier
```

| The AI returned | What gets saved | Why |
|---|---|---|
| tier `warm`, score `97` | tier `warm`, score `74` | A 97 contradicts "warm", so the number is clamped to the tier's band |
| A personalization line with `https://evil.example` | `""` | A link could reach a real customer's inbox (prompt injection or phishing) |
| 6 fit reasons | 3 | Keeps the CRM note and the email short |

## Why it's built this way

- **Save points** mean you never pay for the same AI call twice, and a CRM outage costs a delay, not a lead.
- **The honeypot** stops junk before it costs money. Validation (Layer 1) only checks the shape of the data. A bot can send perfectly shaped data.
- **The fixed form plus the supervisor** means the AI's answer always fits your rules before anything reaches a customer. The AI's answer is a draft, not the final word.

## What breaks without it

| Missing piece | What goes wrong for the business |
|---|---|
| Save points | Every retry re-scores the lead: you pay again, and you risk duplicate CRM contacts and duplicate emails |
| Honeypot | Bots get scored, synced to the CRM and emailed: wasted spend, a polluted CRM and a damaged sender reputation |
| Guardrails | Contradictory scores and AI-written links reach the CRM and customers' inboxes |

## Try it

```bash
pytest -k "retry_resumes or honeypot or normalize" -v     # expect: 3 passed
```

**Break it:** in `normalize()`, change `max(lo, min(hi, score.score))` to `score.score` and run the tests again. `test_normalize_guardrails` fails, because 97 now gets saved as is. Undo the change afterwards.

## Production takeaway

Make each step of a multi-step job record its progress, so a retry resumes rather than repeats. Put the cheapest filter first (the honeypot) and the most expensive step (the AI) behind it. Treat model output as untrusted input: give it a schema, then check it against your business rules.
