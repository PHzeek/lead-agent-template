# Decisions log
One entry per real decision. These become your Episode 2 and case-study material.

| Date | Decision | Options considered | Why this one | Trade-off accepted |
|---|---|---|---|---|

|Sep 29 | Code-first (FastAPI) instead of n8n |n8n, Zapier, code | Full control of retries, test, evals; shows engineering depth. you can test it, measure accuracy and control the cost per lead| More setup time|
|Sep 29| Save every lead before processing |Process-then-save, queue service | Zero leads lost even if the LLM/CRM is down. the lead goes into the database before the AI runs, so a failure never loses it. |Extrra table to maintain |
|Sep 29 |Structured Outputs for scoring | Free-text + regex, JSON mode | Schema-guaranteed fields, no parsing bugs. the AI has to return valid tier, score and reasons fields, not free text.| Tied to providers that support it |
| Sep 29  | Human-written email templates + 1 AI sentence  | Full AI-written emails  | No hallucinated promises in customer emails. the email is safe and on-brand, and the AI adds one personal line. |Less "magic" personalization |
| Oct 19 | GitHub Actions cron for retries instead of Vercel Cron | Vercel Cron (Hobby plan limits how often it runs), QStash, cron-job.org | Free, and the schedule lives in the repo | GitHub schedules are best-effort: 2 runs in 7.5 h were observed. Move to a dedicated scheduler before client use |
| Oct 21 | Refuse to send when settings look like placeholders | Rely on review, add a checklist only | Every go-live bug was a setting no unit test could see | The app fails loudly (500 on the form) until settings are fixed, which is the point |
