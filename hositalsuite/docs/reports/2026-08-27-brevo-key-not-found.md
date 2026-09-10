# The van is on. Brevo refused the key.

**27 Aug 2026.** Live site now says `"mail": "brevo"`. That is progress.

## What I saw (I opened the three pictures)

| Picture | What it shows | What it means |
|---|---|---|
| System Health 08:10 / 08:11 | Green **on — brevo**. Red: `Brevo said 401 Key not found` | The server **has a secret** and **called Brevo**. Brevo said “I do not know this key”. |
| Live `/api/v1/health` | `"mail": "brevo"` | Same. The empty-drawer problem is gone. |
| Brevo 08:06 | SMTP & API → **API keys & MCP**. IP blocking is **off**. | Do **not** tap **Activate for API keys**. That is not today’s problem. |

The software is working. The secret on Render is the wrong kind, too short, or the hidden dots of an old key.

## Do this (do not send me the secret)

1. Open Brevo → **SMTP & API**.
2. Tap the purple tab **API keys & MCP** (not **SMTP**).
3. Tap **Generate API key**. Give it a name like `Hospital Suite`.
4. A popup shows a **long** line starting with `xkeysib-`. Copy **the whole line now**. After you close it, Brevo only shows dots. Dots will not work.
5. Render → **hospital-suite** → **Environment** → **BREVO_API_KEY** → delete the old value → paste the new full line → **Save Changes** → wait for green.
6. System Health → **Send a test letter**.
7. You want a **green** “sent” message, then check Gmail **and Spam**.

Leave **Activate for API keys** alone. That locks the van to a list of computers. Render’s computer is not on that list.

MAIL_FROM can stay `Hospital Suite <hcareproapp@gmail.com>` or just `hcareproapp@gmail.com`. That part is already reaching Brevo.

## What I will not do

I will not use the old GitHub key. 1.7.13 (clearer error words) is on this computer until you send a **new** token.

## Voice reminder

Native recorded phrase bank is still paused until you pick it.
