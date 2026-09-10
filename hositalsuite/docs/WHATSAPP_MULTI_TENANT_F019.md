# WhatsApp on a multi-hospital server (F-019)

Each hospital on a shared deployment can run its own WhatsApp business line.
Inbound messages are routed by **the number that received them**, not by a
fallback guess.

## How routing works

Every Meta webhook event carries the receiving number's identity
(`metadata.phone_number_id` and `display_phone_number`). The webhook matches
that identity against each hospital's settings:

| Setting key                | Value to put there                                    |
|----------------------------|--------------------------------------------------------|
| `whatsapp_phone_number_id` | The Graph API **phone number id** from Meta dashboard  |
| `whatsapp_display_number`  | The number in international form, e.g. `+234 801 222 3344` |

First hospital whose `whatsapp_phone_number_id` (or normalised display
number) matches receives the conversation.

Rules:

- **One hospital on the server?** Nothing to configure — unmatched numbers
  are served by the only hospital, as before.
- **Several hospitals, unmapped number?** The message is logged as an ERROR
  and NOT delivered to any hospital. No guessing, no cross-hospital leak.
  Fix: set that hospital's `whatsapp_phone_number_id` setting.
- Outbound sending still uses the deployment-wide `WHATSAPP_TOKEN` /
  `WHATSAPP_PHONE_NUMBER_ID` env vars; a per-org number requires per-org
  credentials, which is a Meta app configuration step, not a code change.

Covered by `tests/test_f019_whatsapp_number_routing.py`.
