# Go-live checklist

Every item on this list is a bug that passed all the unit tests and still broke the live deploy. Each one has a row in [BREAKLOG.md](BREAKLOG.md), dated Oct 19–21, 2026. Run the whole list before the first real lead, and again after any change to settings.

| # | Check | How | Pass looks like |
|---|---|---|---|
| 1 | The email domain is verified | In Resend, open Domains. In your DNS provider, set every Resend record to **DNS only** (in Cloudflare, a grey cloud, not orange) | The domain status says Verified |
| 2 | A real email arrives | Send one test lead to an inbox you own | The email is in the inbox, not spam, from your domain |
| 3 | No placeholders in the settings | Open `/health` | `"config_ok": true`. The app refuses to send until it is |
| 4 | Every link works | Click each link in the actual email | The booking page opens with the name and email filled in |
| 5 | The new settings are live | After any change, go to Vercel, then Deployments | A Production deployment marked "just now" shows Ready. Then send one fresh test lead |
| 6 | Every path works | Send 5 leads: hot, warm, cold, spam, and the hot one again (a duplicate) | Hot, warm and cold get one email each. Spam gets none. The duplicate creates no new row. Each lead shows up in your CRM |
| 7 | The numbers are healthy | `curl -s $APP_URL/metrics -H "Authorization: Bearer $CRON_SECRET"` | `failed: 0` and `leads_lost: 0`, and p50 is in seconds, not minutes |
| 8 | Retries really run | GitHub, then Actions, then retry-pending-leads, then Run workflow | A green run, and any stuck lead moves to `done` |

**Keep secrets out of screenshots.** Load them with `read -s CRON_SECRET`, then run `clear` before recording or taking a screenshot.
