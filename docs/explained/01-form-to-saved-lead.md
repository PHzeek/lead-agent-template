# Layer 1: From form submit to saved lead

![Layer 1 flow: validate with LeadIn, save with repo.insert and a dedupe check, then process. Three outcomes: bad data gets a 422 and never touches the database, a double-click returns the same lead_id with duplicate true, and if OpenAI is down the visitor still sees ok while the lead stays received and is retried.](../visuals/layer1-form-to-saved-lead.png)

## The idea

Validate, then save, then think. A lead is checked and written to the database before any AI runs. If the AI, the CRM or email breaks later, the lead is still safe.

**Analogy: a restaurant ticket rail.** The host checks that the order is real. The ticket goes on the rail before the kitchen cooks. If the stove catches fire, the ticket is still there. And "you already ordered that" stops a double order.

## In my words

> Layer 1 accepts the form and checks that the lead has the required valid inputs: a name, a valid email, a budget from the menu. Then the lead is saved before anything else is processed. As part of saving, it's checked to make sure it isn't a duplicate. Processing happens after that. Payment, order and webhook systems like Stripe and Shopify follow the same "store, then process" rule. Losing a lead is unacceptable, and this pattern makes that nearly impossible.

## The code

`app/main.py`:

```python
@app.post("/leads")
def create_lead(lead: LeadIn, pipeline = Depends(get_pipeline)):
    lead_id, created = pipeline.repo.insert(lead.email, lead.model_dump())  # 1) save first
    if not created:
        return {"ok": True, "lead_id": lead_id, "duplicate": True}         # double-click
    status = pipeline.process(lead_id)                                      # 2) then think
    return {"ok": True, "lead_id": lead_id, "status": status}
```

- `lead: LeadIn` means FastAPI checks the request against the `LeadIn` model in `app/models.py` before this function runs. Bad data gets a 422, and the database is never touched.
- `repo.insert` in `app/db.py` builds a dedupe key from the trimmed, lowercased email, the message and the day. If that key already exists, it returns the existing `lead_id` and `created = False`. Otherwise it writes the row with `status = "received"`.
- `pipeline.process` runs Layer 2. On the happy path it returns `"done"`. If something fails, the error is caught, `attempts` and `last_error` are saved, and the lead keeps its last good status for `/cron/retry`.

## What breaks without it

| Missing piece | What goes wrong for the business |
|---|---|
| Saving first | An AI or CRM outage loses the lead, and you never know it existed |
| Dedupe key | Double-clicks become two leads: double AI cost, two emails to the same person, inflated lead counts |
| Validation | Malformed data reaches the database and breaks scoring and the CRM later |

Validation stops malformed data. It doesn't stop fake leads with valid-looking data. That's the honeypot's job, in Layer 2.

## Try it

```bash
pytest -k "duplicate or bad_input" -v      # expect: 2 passed
```

**Break it:** remove `.lower()` from `dedupe_key` in `app/db.py` and run the tests again. `test_duplicate_submission_is_ignored` fails, because `JOE@X.COM` and `joe@x.example` now count as two leads. Undo the change afterwards.

## Production takeaway

Treat every incoming event (a lead, an order, a webhook) as something to write down first and work on second. Make the write idempotent, meaning a repeated submission has no extra effect, so duplicates are harmless.
