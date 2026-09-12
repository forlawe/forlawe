# Answers: the 4 reds, and your 6 upgrade requirements

---

## Part 1 — The 4 red ✗ marks

**Short answer: ignore them. They are old history, and they are already fixed.**

Look at the commit codes next to each red ✗ in your screenshot:

| Red ✗ | Commit | Time |
|---|---|---|
| "Incident notes: produ…" | `27569cb` | 1:39 PM |
| "CRITICAL: stop a slo…" | `938158f` | 1:28 PM |
| "Production hardening…" | `d3bcb32` | 12:55 PM |
| "Production hardening…" | `d3bcb32` | earlier |

**Every one of those is from BEFORE 1:45 PM — before I found the real bug.**

The fix went in at commit `faada97`, after all four of them. Those reds are like old photos of
a patient when they were sick. The patient is well now. Render keeps the full history forever,
so those entries will sit there permanently — that is normal and harmless.

**What matters is right now:**

```json
{"status":"ok", "database":true, "scheduler":true,
 "last_backup":"2026-08-15T15:50:05", "storage":"db"}
```

Your site is healthy. Scroll to the **top** of that Render list — the newest deploy should be
green ✓. That is the one that counts.

> One note: I saw "Rollback" buttons next to those reds. **Do not press Rollback.** That would
> put the broken version back and take your site down again.

---

## Part 2 — Your 6 upgrade requirements: honest status

I checked every one against the actual code. Here is the truth.

### 🔴 Overall: 1 of 6 done. 5 are new work that does not exist yet.

| # | Requirement | Status |
|---|---|---|
| 1 | Role Management (CRUD on roles) | ❌ **Not built** |
| 2 | Unified Roster + Leave | ❌ **Not built** |
| 3 | Department: HOD name + phone | ⚠️ **Half** |
| 4 | User Management + bulk upload | ⚠️ **Half** |
| 5 | Bigger logo | ❌ **Not done** |
| 6 | AM final comment + submit-once | ⚠️ **Half** |

---

### 1. Role Management — ❌ NOT BUILT

Roles are **hardcoded in the program**, not stored in the database:

```python
ROLES = ("SUPER_ADMIN", "MD_CEO", "ADMIN_MANAGER", "HOD")
```

There is no `Role` table and no screen to manage roles. You can *assign* a user one of those
4 fixed roles, but you cannot create a 5th role, rename one, or change what a role is allowed
to do.

**To do this properly** I need to build a real permissions system: a `Role` table, a
`Permission` table, and a screen to tick which permissions each role gets. Every `require_role`
check in the code (there are dozens) then has to be rewired to ask the database instead of a
fixed list. **This is the biggest item on your list.**

### 2. Unified Roster + Leave — ❌ NOT BUILT

Still two completely separate pages: `/roster` (Admin Manager) and `/dept-roster` (departments).

And **nothing about leave exists anywhere** — no annual, casual, sick or study leave. I searched
the whole codebase; the only match was an unrelated chatbot answer about sick notes.

Your template also asks for fields the system does not store: **staff phone number** on the
roster, **number of staff on duty**, and leave status.

### 3. Department: HOD name + phone — ⚠️ HALF DONE

- ✅ HOD name — exists (`hod_user_id` links to a staff member)
- ❌ HOD phone number — **not a field on the department**

The HOD's phone lives on their *user account*, not on the department. If your HOD is someone
who is not a system user, you cannot record their number at all.

### 4. User Management — ⚠️ HALF DONE

Already working: ✅ create (with phone, email, role), ✅ edit, ✅ suspend, ✅ reset password.

Missing:
- ❌ **Department** cannot be assigned to a user — there is no department field on a user account
- ❌ **Approving user accounts** — no approval step exists
- ❌ **Delete** a user — you can only suspend (deactivate)
- ❌ **Bulk upload** — no nominal roll, no departmental list, no unit/section list upload

Bulk upload is the big one here. Right now, entering 200 staff means typing 200 forms by hand.

### 5. Logo size — ❌ NOT DONE

Current sizes: **28px** in the top bar, 56px on portals, 64px on login. These are small.

Easy fix, and I should also warn you: making the box bigger will look *blurry* unless your
uploaded logo file is high resolution. I would add a size check that warns you at upload time.

### 6. AM Reporting — ⚠️ HALF DONE

- ✅ **Submit once only** — already enforced ("You already submitted today's inspection…")
- ✅ **Drafts save automatically** — autosave and an offline sync queue already work
- ✅ **Voice-to-text** — works, but only on the *per-criterion explanation* boxes
- ❌ **A final overall comment box before submitting** — does not exist. The `Inspection` table
  has no field for it.

---

## What I recommend

This is roughly **3–4 solid days** of work. I suggest this order, highest value first:

**Day 1 — quick wins you will feel immediately**
- Bigger logo + resolution warning (30 min)
- Final comment box with voice-to-text on the AM report (2 hrs)
- HOD phone on departments (1 hr)
- Add department to user accounts (2 hrs)

**Day 2 — the one that saves you the most time**
- Bulk user upload (nominal roll / department / unit lists) with a preview-before-import screen,
  reusing the roster import code that already works
- User approval workflow + proper delete

**Day 3–4 — the big structural pieces**
- Unified roster page (merge both, add phone, staff count, shift type)
- Leave management (annual/casual/sick/study) that blocks rostering someone who is on leave
- Real Role & Permission system

**One honest caution on ordering:** the roster and leave work touches the duty reminders and
SLA escalation that are running in production right now. I want to do that last, carefully,
with tests — not rushed alongside everything else.

---

## Before we start: 2 things still outstanding from before

- ⬜ **Revoke the GitHub token** you pasted in chat — github.com/settings/tokens. Anyone who
  reads that message can change your hospital's code.
- ⬜ **UptimeRobot** monitoring on `/api/v1/health` (10 min, free). It also keeps Supabase awake,
  which is what caused today's outage.

---

**Tell me which day-1 items you want first, or say "do them in your order" and I will start at
the top.**
