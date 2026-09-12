# Hospital Triage + Doctor Consulting Room

> Written for the founder in plain language.  
> **Honest answer first:** this is **not** a working feature yet.  
> Only a *name* exists on the hospital map.

---

## 1. What is already in the system (and what is not)

| What you asked about | In the build today? | What that means |
|---|---|---|
| A room / unit **named** “Triage” | **Yes — as a label only** | Under **Emergency → Accident & Emergency → Triage**. It is like writing the word on a door. Nobody can “work that door” yet. |
| Outpatient / OPD names | **Yes — as labels only** | Internal Medicine has “Outpatient Clinic / General OPD”. Same story: a name, not a flow. |
| **Working hospital triage** (nurse sees the patient first, then sends them on) | **No** | The queue is one stop: *waiting → called → served*. There is no “first the nurse, then the doctor.” |
| **Doctor consulting rooms** (Room 1, Room 2… each doctor calls their own next patient) | **No** | Staff call the next person for a *whole department*, not for a specific room. |
| Diagnosis, prescriptions, patient file / EMR | **No — and we should not add this yet** | The product rule is: this platform runs the *visit*, not the *medicine*. Clinical records wait until paying hospitals ask for them. |

Today’s working visit is:

**Book → arrive / join queue → one call → “served” → rate the visit → share a link.**

That is a good start. It is **not** how a real OPD or A&E desk actually runs.

---

## 2. How a real Nigerian hospital visit usually works

Think of the hospital as a market with two important tables, not one.

```
Gate / Reception          Triage desk              Consulting rooms
   (check in)     →     (nurse looks first)   →    (doctor sees you)
                              │
                              ├── Room 1  Dr. Amina
                              ├── Room 2  Dr. Tunde
                              └── Emergency bay  (if it cannot wait)
```

### Stop 1 — Reception (you already have this)
Patient booked online **or** walked in.  
Staff tap **Check in → queue**. Patient gets a number like `E-014`.  
Name never appears on the public TV. That part is already built and should stay.

### Stop 2 — Triage (missing)
A nurse (not the doctor) sees the person **first**, for about 2–4 minutes.

The nurse is **not** treating the illness. The nurse is answering three simple questions:

1. **Can this person wait?**  
   - Routine — sit and wait your turn  
   - Soon — see a doctor before the long queue  
   - Urgent — do not wait in the ordinary line  
   - Emergency — take to the emergency bay **now**
2. **Which doctor / which room?**  
   Room 1, Room 2, Paediatrics, etc.
3. **One short note for the doctor**  
   “Chest pain since morning.” / “Child has fever.”  
   Not a diagnosis. Just *why they came*.

Then the nurse **sends** the number to that room’s waiting list.

### Stop 3 — Consulting room (missing)
Each doctor sits in **their** room and only sees **their** list.

- Doctor taps **Call next** → the TV / phone says “E-014, Room 2.”
- When finished: **Done** (or **No-show** if they did not come).
- Optional: send the person on to Pharmacy / Lab / Billing later (not required for the first version).

### After the visit (you already have this)
**How was your experience?**  
Low stars → complaint / recovery ticket.  
High stars → book again + refer a friend.

---

## 3. How this blends with what is already built

Nothing already working gets thrown away. We **stretch the queue** from one stop to two.

```
TODAY (one stop)
  Book ──► Check-in ──► WAITING ──► CALLED ──► DONE ──► Feedback ──► Refer

TOMORROW (two stops, same ticket number)
  Book ──► Check-in ──► TRIAGE WAIT ──► nurse sends to a room
                              │
                              ▼
                     ROOM WAIT ──► doctor calls ──► DONE ──► Feedback ──► Refer
```

| Already built | How triage + rooms use it |
|---|---|
| Booking (`/book`, SMS, reference) | Unchanged. Check-in still creates **one** ticket. |
| Queue ticket + private status link | Same number (`E-014`) follows the patient from triage to the room. The status page will say *“Now at triage”* then *“Please go to Room 2.”* |
| Public TV (numbers only, never names) | Still numbers only. It can show *where*: “Now at Triage: E-014” / “Room 2: E-012”. |
| Staff **Call next / Served / No-show** | Same big buttons. Nurse sees the *triage* list. Doctor sees *only their room*. |
| Department roster | Nurse on duty / doctor on duty can later be taken from the roster you already have. |
| Feedback + referrals | Still happen **after** the doctor marks Done. That is the right moment — the visit is finished. |
| Complaints + SLA | If someone waits too long, or is rude at triage, the existing complaint portal still works. |
| Audit trail | Every “sent to Room 2” and every “called in Room 2” is written down. Nobody can quietly jump the queue without a record. |
| Languages (EN / Yorùbá / Hausa / Igbo) | Patient screens stay in the four languages. |
| AI rule (advisory only, never clinical) | The computer must **never** decide who is an emergency. Only the nurse taps Routine / Soon / Urgent / Emergency. |

---

## 4. What each person sees (simple)

### The patient (phone, no account)
1. Gets number `E-014` at check-in (already works).
2. Status page: **“Please go to the Triage desk when your number is called.”**
3. After the nurse: **“Please sit. You will be called for Room 2.”**
4. After the doctor: **“Your visit is finished. How was your experience?”** → existing feedback.

Public TV never shows the name. Same privacy rule as today.

### The triage nurse (staff login)
A page called **Triage desk**:

- Big **CALL NEXT** button  
- Patient number + name (staff only) + department  
- Four large taps: **Routine · Soon · Urgent · Emergency**  
- Then tap the destination: **Room 1 · Room 2 · Emergency bay**  
- Optional one-line note for the doctor  
- Send.

Urgent / Emergency people go **ahead** of Routine in that room’s list.  
This is visible and audited — not a secret favour.

### The doctor (staff login)
A page called **My consulting room**:

- Chooses **Room 2** (or we pin them to a room).  
- Sees only people sent to Room 2.  
- **CALL NEXT** → patient walks in.  
- **DONE** or **NO-SHOW**.  
- That is all. No writing a medical file in this version.

### The MD / Admin Manager
Dashboard already has “in queue now.” We add:

- How many waiting for **triage**
- How many waiting for **each room**
- Average time: arrival → nurse, nurse → doctor
- How often Emergency / Urgent was used (so management can see if the desk is overloaded)

---

## 5. Rules that keep this honest and safe

1. **One ticket, whole visit.** The patient does not collect a new number at every door.
2. **Nurse first, doctor second** — unless that department has no triage desk (then they go straight to a room, same as today).
3. **Rooms belong to a department.** Room 2 is “Internal Medicine / Room 2”, not a floating room.
4. **Emergency can skip the ordinary line.** The skip is logged. Reason is the urgency tap, not a typed essay.
5. **No vitals required in version 1.** Blood pressure machines fail; we must not block the queue because a cuff is missing. A later optional “vitals noted” box can be added.
6. **No diagnosis, no drugs, no lab results in this platform.** That is a patient file (EMR). We are the *front door and the waiting chairs*, not the doctor’s notebook.
7. **The computer never triages.** A human always taps the urgency. This respects the product rule: AI / software stays administrative, never clinical.
8. **Names stay off the public screen.** Same as today.

---

## 6. First version we would actually build (small, useful)

Not a new app. Extra screens on the queue you already have.

1. **Admin:** add / rename / switch off rooms  
   e.g. “Triage desk”, “Consulting Room 1”, “Consulting Room 2”, “Emergency bay”.
2. **Check-in** puts the ticket in **Triage wait** if that department has a triage desk; otherwise straight into the room list (today’s behaviour).
3. **Triage desk** page for nurses (call → send to a room + urgency).
4. **Consulting room** page for doctors (call → done / no-show).
5. Patient status page + public TV show the *stage* and *room*, still numbers-only on the TV.
6. After **Done**, the existing “How was your experience?” link.
7. Dashboard counts for triage wait and room wait.
8. Tests, same as every other module.

**Left for later (on purpose):**
- Paying at the desk  
- Pharmacy / Lab queues  
- Full vital-signs chart  
- Assigning a named doctor to a room from the roster automatically  
- Clinical notes / EMR  

---

## 7. Why this is the right next clinical-flow piece

You already finished the *outside* of the visit (book, complain, rate, refer).  
Triage + rooms finish the *inside* of the visit — the part patients actually stand in line for.

It does **not** replace the pending menu items (AI recovery, satisfaction dashboard, attendance, founder’s guide). It sits on the **queue** you already paid for.

If you say **“build triage + rooms”**, that is what I will build next, in this same simple style.
