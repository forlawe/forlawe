# F-008 — Public route tenant audit (all_orgs surfaces)

Public/anonymous requests deliberately run with `all_orgs()` (RLS bypass) so
hospital-choice pages can render before any tenant is known — making every
org_id filter in those views a MANUAL responsibility. This is the targeted
per-view audit the finding asked for. Verdicts were produced by reading each
view's queries (this file documents them; the two load-bearing checks are
pinned by `tests/test_f008_public_tenant_audit.py`).

| Public surface | Tenant mechanism | Verdict |
|---|---|---|
| `/` patient hub | `current_org()` precedence (user → `?h=` → subdomain → single-tenant; refuses ambiguous) | ✅ |
| `/book` + `/book/status` | Dept lists filter `org_id`; submit scopes `org.id`; status = **ref + phone** two-factor (ref embeds the org code and is globally unique) | ✅ |
| `/queue/join` + submit | Submit **re-validates `dept.org_id == org.id` server-side** — a forged department (or any form field) cannot cross tenants; ticket org = resolved org | ✅ pinned by test |
| Queue personal page `/t/<key>` | Lookup by 96-bit `access_key` (global-unique); org derived FROM the record — capability pattern, no URL-trusting | ✅ |
| `/complaint` + status | Lists filter `org_id`; idempotency keys scoped per org; status = ref + phone two-factor (anonymous complaints unreachable by design) | ✅ |
| `/feedback` portal | Lists and submit scoped to resolved org | ✅ |
| `/chat` | `current_org()` resolution; session rows carry that org | ✅ |
| TV `/api/tv/*` (feed, qr-url, volume, brightness) | Org resolved from screen code / user / host; screen queries filter `org_id`; feed now rate-limited (F-028) | ✅ |
| Personal TV + push subscribe + VAPID lookup | Access-key (96-bit) or staff session; no anonymous subscribe (audit F-032) | ✅ |
| USSD intake | `USSD_SHARED_SECRET` + explicit `hospital_code` — "no fallback to first org" is a documented security fix | ✅ |
| WhatsApp webhook | Routes by the receiving business number's Meta identity (F-019); unmapped numbers on multi-hospital servers are logged, never guessed | ✅ |
| Native voice phrase audio `/voice/phrase/<id>` | Served under `all_orgs()` by sequential id | ✅ acceptable — content is the hospital's own recorded voice bank (no patient data), intended for public TV playback |
| Complaint / booking **status** lookups | Query ref+phone WITHOUT an org filter | ✅ correct-by-design — the org code is inside the ref, ref is globally unique, and the phone is the second credential; cross-tenant enumeration requires both |

## Conclusion

No cross-tenant write or read path found. The two org-agnostic lookups
(status-by-ref+phone, public voice audio) are intentional, documented, and
carry no patient-identifying risk beyond the credentials already required.
The one check the whole queue flow leans on (`dept.org_id == org.id` before
any insert) is now regression-tested.

Future re-checks (any new public route): the route must (a) resolve the org
via `current_org()` precedence or a capability token, (b) filter every query
by it, and (c) never trust an org-bearing form field.
