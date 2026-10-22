# Metrics sheet (real numbers only)

## Scoring evals
| Run | Date | Prompt | Split | n | Agreement % | Hot recall % | Hot missed as cold/spam | p50 latency | Cost/lead |
|---|---|---|---|---|---|---|---|---|---|
| v1 | 2026-10-07 | score_lead.md | dev | 20 | 100 (3/3 runs) | 100 | 0 | 3.6–3.8 s | $0.00022 |
| v1 | 2026-10-07 | score_lead.md | dev (+10 hard) | 30 | 96.7 | 91.7 | 0 | 3.9 s | $0.000228 |
| v2 | 2026-10-08 | score_lead_v2.md | dev (+10 hard) | 30 | 98.9 (3 runs) | 100 | 0 | 3.6–3.8 s | $0.000235 |
| v1 | 2026-10-12 | score_lead.md | test | 30 | 100 (2 runs) | 100 | 0 | 4.4–4.8 s | $0.00023 |
| final (v2) | 2026-10-12 | score_lead_v2.md | test | 30 | 98.9 (3 runs) | 100 | 0 | 4.4–5.2 s | $0.00023 |

## Labeling (Session 9)
| Date | Leads | Split | Hot | Warm | Cold | Spam | First-pass disagreements | After review |
|---|---|---|---|---|---|---|---|---|
| 2026-10-07 | 50 | dev 20 / test 30 | 16 | 12 | 14 | 8 | 1 (L10 hot -> warm) | 0 (L10 back to hot) |

Dev set: hot 7, warm 4, cold 6, spam 3.
Hard set added 2026-10-07: L51-L60 (dev). Dev is now 30: hot 12, warm 6, cold 8, spam 4. First-pass disagreements: 2 (L52, L56).

Notes:
- Labeled blind (read the lead before the draft), using docs/LABELING.md.
- L10: hesitated because it's a larger manufacturer outside the dental/med spa focus. Guide says hot (reporting problem, $15k+, 1-3 months). Rubric gap for v2: say clearly that strong fits outside the primary focus can still be hot.
- L36: considered warm, kept cold per guide (exploring, under $1.5k, no stated problem).

## Session 11 notes
- v1 scored 20/20 on dev in 3 of 3 runs (194949, 200212, 200932). Stable on clean leads.
- 100% means the dev set is too easy to show improvement, not that the AI is perfect.
- Next: add ~10 hard dev leads (vague, messy, borderline, adversarial) and rerun v1.
- First hard-set run (221925): 28/30. Both misses (L52, L56) were my label overrides. L52 relabeled warm per guide; L56 kept hot as a new rule.
- Rerun after relabel (224912): 29/30. Only miss: L56 (staff at a dental practice). Target for v2.

## Session 12 (Oct 8): prompt v1 vs v2, dev split (30 leads), 3–4 runs each

v2 = v1 + one tie-breaker: "Delegated by the owner" (dental/med spa staff who name a specific problem AND say the owner/doctor asked them = hot).

| Prompt | Runs | Accuracy | Hot recall | Hot buried | p50 | Cost/lead | Misses |
|---|---|---|---|---|---|---|---|
| v1 score_lead.md | 224912, 235731, 225711, 230654 | 29, 29, 29, 29 (96.7%) | 91.7% | 0 | 3.8–4.3 s | $0.00023 | L56 every run |
| v2 score_lead_v2.md | 224315, 224726, 225118 | 30, 30, 29 (98.9%) | 100% | 0 | 3.6–3.8 s | $0.000235 | L25 once (warm → cold) |

**Decision:** v2 wins on hot recall (91.7% → 100%, stable across 3 runs). L60 (staff, no owner request) stayed warm in all v2 runs: no regression from the new rule.

**Watch:** L25 was correct 7/7 under v1 (3 runs on 20 leads, 4 on 30) and 2/3 under v2. Too few runs to call it; recheck on the test split. Note: v1 has 4 dev runs vs v2's 3; the 4th v1 run (235731, Oct 7) was found later, not cherry-picked.

**Caveat:** the rule was written after seeing L56, so dev results are optimistic. The test split (30 untouched leads) is the real verdict and runs next session before v2 becomes the default.

## Session 13 (Oct 12): test split (30 untouched leads)

| Prompt | Runs | Accuracy | Hot recall | Hot buried | p50 | Cost/lead | Misses |
|---|---|---|---|---|---|---|---|
| v1 score_lead.md | 194519, 195740 | 30, 30 (100%) | 100% | 0 | 4.4–4.8 s | $0.00023 | none |
| v2 score_lead_v2.md | 195352, 200056, 200809 | 29, 30, 30 (98.9%) | 100% | 0 | 4.4–5.2 s | $0.00023 | L23 once (warm → cold) |

**Decision:** v2 is the default (`app/scoring.py`, line 14). It fixed L56 on dev (v1 missed it 4/4) and kept 100% hot recall on test. Cost: one warm → cold miss in 3 test runs. A delayed follow-up is cheaper than a buried buyer. pytest 11 passed after the switch.

**Honest limits:** v1 was slightly better on test (60/60 vs 89/90). All 10 hard leads (L51–L60) are in dev, so the test split has no "delegated by the owner" leads: it shows v2 didn't break normal leads, not that the fix generalizes.

**Watch:** both v2 misses go warm → cold (L25 dev, L23 test): 2 in 6 v2 runs vs 0 in v1. Not enough to act on. Next: write ~10 fresh hard leads (including L56-style and borderline warm) as a new held-out set; any fix is v3, tuned on dev only.
## Live end-to-end (Oct 21, 2026, from /metrics on the production deploy)

Test leads only, sent through the live form: hot, warm, cold, spam and a duplicate, plus 2 earlier go-live leads. These are not client results.

| Date | Leads | Under 5 min % | p50 first response (s) | p95 (s) | Avg LLM cost | Leads lost |
|---|---|---|---|---|---|---|
| 2026-10-21 | 7 (hot 4, warm 1, cold 1, spam 1) | 83.3 (5 of 6 emailed) | 6.78 | 4941.54 | $0.000245 | 0 |

- p95 is one lead: the Oct 19 go-live lead that waited for the typo and API-key fixes, then was delivered by the retry job. The other 5 emailed leads were answered within 5 minutes, with a median of 6.78 s.
- Spam: score 3, `email_status = skipped`. Duplicate: no new row and no second email.
- The same hot message, submitted twice under different emails, scored 96 and 97.
- AI cost is about 2.5 cents per 100 leads, LLM only. Hosting, database, CRM and email were on free tiers during testing.
