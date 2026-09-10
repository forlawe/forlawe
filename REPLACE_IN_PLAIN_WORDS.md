# 🧱 Like explaining to a 7 year old — do we have everything, and how do we swap it?

Everything in here was **checked by running commands**, not guessed. The number
next to each claim is what the command printed.

---

## Part 1 — Your question: "Do we have ALL the code, or only the patch?"

**We have ALL of it.** Both. Here is the proof:

| Question | Command I ran | Answer |
|---|---|---|
| How many files are in the forlawe GitHub repo? | `git ls-tree -r --name-only origin/arena/01a08cab-forlawe \| wc -l` | **549 files** |
| How many of those are the app? | `... \| grep -c '^hositalsuite/'` | **541 files** |
| How many files were in the zip you gave me? | `unzip -Z1 … \| grep -v '/$' \| wc -l` | **540 files** |
| Anything in the zip that is missing from the repo? | `comm -23 zipfiles tracked` | **nothing** (blank) |
| What is extra in the repo? | `comm -13 zipfiles tracked` | **1 new file**: `app/templates/_auth_footer.html` |

So: **540 of your files + 1 new file I made = 541.** Not one of your files is
missing. The other 8 of the 549 are the two guides, the 4 `deploy/` helper files,
`.gitignore` and the original zip.

### And here is the really good news

I fetched your **live** repo (`github.com/Hcarepro2026/hositalsuite`) and
compared it brick by brick:

```
your live repo's newest commit     : 2ad087c
the commit written inside your zip : 2ad087c3e0b9eb9534ce303f84d04a802855c755
                                     ^ same
last push to your live repo        : 2026-09-06 09:24
```

**Your zip and your live repo are the same version.** Nothing you changed since
the zip is missing here. Then I compared every file:

```
files that differ between your live repo and this workspace:  8
   (7 changed + 1 new — exactly the fix, nothing else)
```

And the patch note fits your live repo perfectly:

```
$ git apply --check deploy/landing_auth_mobile.patch     (run inside your live repo)
Checking patch app/static/css/app.css...
Checking patch app/templates/_auth_footer.html...
... (all 8 checked, no complaints)
PATCH FITS THE LIVE REPO
```

---

## Part 2 — The story (this is the whole idea)

🏠 **Your hospital suite is a big Lego house.** 540 bricks.

📦 **The zip you sent me** was a box with all 540 bricks inside, plus a note
saying "this house is version 2ad087c".

🔧 **This workspace is my workbench.** I built your whole house again here — all
540 bricks — then I did the work you asked for:

* painted 7 bricks a nicer colour (the 7 changed files), and
* added 1 brand new brick (`_auth_footer.html`).

📚 **The forlawe GitHub repo is my shelf.** On the shelf I put the **entire
house** (all 541 bricks) *and* a small note that says "these 8 bricks are the
special ones". The note is `deploy/landing_auth_mobile.patch`.

So you can choose: **carry the whole house**, or **carry just the note and the 8
bricks**. Both work. Carrying the note is faster and safer.

---

## Part 3 — How we swap it (the recommended way, 5 steps)

This is a recipe. Do the steps in order. After each step I tell you what you
should **see** — if you see something different, stop and tell me.

### Step 1 — Get a fresh copy of your house onto your computer

```bash
git clone https://github.com/Hcarepro2026/hositalsuite.git
cd hositalsuite
```

**You should see:** a folder called `hositalsuite` full of files, and the command
ending with no red words.

### Step 2 — Put the note (the patch) into that folder

Copy `deploy/landing_auth_mobile.patch` from this workspace into the
`hositalsuite` folder you just made. Then:

```bash
git apply --check deploy/landing_auth_mobile.patch
```

**You should see:** *nothing at all.* Nothing = the note fits perfectly.
If you see red words, stop — it means your house has bricks I have not seen.
Tell me and I will write a new note.

### Step 3 — Do the swap, and look at it

```bash
git apply deploy/landing_auth_mobile.patch
git status
```

**You should see exactly 8 lines.** This is the real output from running it
against a clone of your live repo:

```
 M app/static/css/app.css
 M app/templates/forgot_password.html
 M app/templates/landing_sales.html
 M app/templates/login.html
 M app/templates/request_access.html
 M app/templates/reset_password.html
 M app/templates/signup_pick.html
?? app/templates/_auth_footer.html
```

`M` means "changed". `??` means "brand new brick". **7 + 1 = 8.** If you see 6
lines or 9 lines, stop.

### Step 4 — Send it up; Render rebuilds your live app by itself

```bash
git add -A
git commit -m "Landing page: mobile menu, staff sign-up links, auth pages link back"
git push origin main
```

**You should see:** `To github.com/Hcarepro2026/hositalsuite` then `main -> main`.
Render notices on its own and builds in about 2–3 minutes.

> ⚠️ **This step is yours to do.** I am logged in here as the
> `arena-ai-coding-agent` bot, and GitHub reports its rights on your repo as
> `push: false, admin: false` — I am not allowed to write to your repo and I
> will not try. Your own helper works too: `bash push.sh <YOUR_TOKEN>`.

### Step 5 — Check it worked (10 seconds)

```bash
bash deploy/03_verify.sh https://hospital-suite.onrender.com
```

**You should see:** `passed: 17    failed: 0`.
Run here against the live app in this workspace, it printed exactly that.

---

## Part 4 — Two other ways, if you prefer

### Way B — you have your own server (a VPS)

Three commands. The first one photographs everything before we touch it, so we
can always go back.

```bash
bash deploy/01_backup_current.sh /var/www/hositalsuite   # take the photo
bash deploy/02_apply_patch.sh   /var/www/hositalsuite   # swap (checks first)
bash deploy/03_verify.sh        https://your-domain     # prove it worked
```

**Undo button, if you ever need it:**

```bash
tar -xzf ~/hospital-suite-backups/<the-folder-it-printed>/code.tar.gz -C /var/www/hositalsuite
sudo systemctl restart hospital-suite
```

### Way C — no git at all, just copying files

Copy these 8 files from `hositalsuite/` in this workspace to the same places on
your server. **The 2nd one is new — it is the one people forget:**

```
app/static/css/app.css
app/templates/_auth_footer.html        ← NEW, do not forget
app/templates/landing_sales.html
app/templates/login.html
app/templates/request_access.html
app/templates/signup_pick.html
app/templates/forgot_password.html
app/templates/reset_password.html
```

Then check you got them all:

```bash
grep -c nav-toggle  app/templates/landing_sales.html   # must be more than 0
grep -c auth-footer app/templates/login.html           # must be 1
ls -l             app/templates/_auth_footer.html      # must exist
```

Or take the **whole house** (all 541 files): copy the entire `hositalsuite/`
folder — but read Part 5 first, because two things must never be copied.

---

## Part 5 — Kid rules 🚫 (the two things we never touch)

1. **`data/`** — the toy box with the real patient records, photos and logos
   inside. Never copy it. The box in this workspace holds **fake toys**: a
   pretend hospital called *Lagos City Teaching Hospital* and the
   `admin / Admin#2026!` login. Fake toys must never go near the real box.
2. **`.env`, `.secret_key`, `vapid_keys.json`** — the keys to the house. Swap the
   keys and everybody gets locked out: every user signed out, WhatsApp/SMS stop,
   phone notifications stop.

Good news: the note in `deploy/` **cannot** touch those — it only knows about the
8 files. And `02_apply_patch.sh` looks before it writes: if something does not
fit, it stops and changes nothing.

---

## Part 6 — What I already checked for you (so you do not have to)

| I checked | How | Result |
|---|---|---|
| Your own test suite, before I changed anything | `pytest -q` | **1044 passed, 8 skipped** |
| Your own test suite, after I changed things | `pytest -q` (17m19s) | **1044 passed, 8 skipped** — nothing broke |
| Tests that look at exactly the files I touched | 9 test files | **74 passed** |
| The note fits your **live** repo | `git apply --check` in a real clone of it | **fits** |
| After the swap, the 8 files match this workspace | `diff -q` on all 8 | **all ok** |
| The pages really work | `bash deploy/03_verify.sh http://127.0.0.1:8077` | **17 passed, 0 failed** |
| Signing in really works | `POST /login` with the secret token | **302 → /change-password** (correct) |

**Not checked — you should look yourself:** how it looks on *your* phone (the
checks prove the right files are served; only your eyes prove it looks right),
and real WhatsApp/SMS sending (this sandbox only pretends to send).

---

## Tiny summary

* ✅ forlawe has **ALL** the code (541 app files = your 540 + 1 new), not just the patch.
* ✅ Your live repo and the zip are the **same version** (2ad087c), so nothing is missing.
* ✅ Only **8 files** differ, and the patch note fits your live repo.
* 👉 You do: clone → `git apply` → look for 8 lines → push → verify. About 5 minutes.
