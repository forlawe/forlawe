"""
GLOBAL MASTER KNOWLEDGE — App Master v2.0 World-Class
Makes the AI assistant knowledgeable about ENTIRE hospital suite, not just appointments.

Coverage: patient hub 6 tiles, booking, queue, complaint, feedback, referrals,
TV screens, personal TV /t/<key>, VAPID push free alarm, voice bank 2M2F 4 languages,
hospital setup logo, branches, attendance, roster 4 patterns + 8 leave types,
HIMS folder, reception flow, triage OPD/SOPD/MOPD/EMERGENCY, call room queue,
onward routing, tracking, reports, audit, admin users, security, notifications,
NDPA data requests, backups, offline PWA, slow internet, multi-browser,
feature phone, Fast Track gold lane, SMS/WhatsApp, USSD, queue estimator,
admission, discharge, follow-up, aftercare, visiting, lab, pharmacy, billing,
emergency navigation, department directions, registration, first visit,
PWA install Android/iPhone, offline behaviour, missing phrase reporting.

Tone: world-class, short clear simple natural human professional kind patient-centred,
warm calm respectful confident, contractions allowed, ends with soft call-to-action,
never diagnoses, never invents location/price/phone.

Written for Nigerian hospitals — premium plus plus plus quality.
"""

KB = [
# ---------------------------------------------------------------- APP OVERVIEW
dict(cat="app_overview", intent="app_what_is", kw=[
    "what is this app","what does app do","explain app","what is hospital suite",
    "what is this system","how does this work","what can this app do",
    "explain this hospital app","what is patient experience os","what is hms",
    "tell me about app","overview of app","app overview","how does app work",
    "what does this app do for patients","what does this app do for staff"],
 en="This is your hospital care system — we built it so your visit feels calm, quick, and respectful. For you, you can book a visit, join the queue and watch your turn live on your phone, ask questions, tell us a problem, and share feedback. For our staff, it guides every step — from reception to billing to doctor to lab to going home — so no one gets forgotten. It's not a medical record; it's a patient-experience system.",
 pcm="Na your hospital care system be this — we build am make your visit calm, quick, and respectful. For you, you fit book visit, join queue and watch your turn live for your phone, ask question, tell us problem, and give feedback. For our staff, e dey guide every step — from reception to billing to doctor to lab to go house — so nobody go forget. E no be medical record; na patient-experience system.",
 yo="Ètò ìtọ́jú ilé-ìwòsàn yìí ni — a ṣe é kí ìbẹ̀wò rẹ rọrùn, kíákíá, àti pẹ̀lú ọ̀wọ̀. O lè ṣe ìforúkọsílẹ̀, darapọ̀ mọ́ ìlà, wo ipò rẹ lórí fóònù, béèrè ìbéèrè, sọ ìṣòro, kí o sì fún wa ní èsì.",
 ha="Wannan tsarin kula da asibitin ku ne — mun gina shi don ziyarar ku ta zama natsuwa, sauri, da mutunci. Za ku iya yin booking, shiga layi ku kalli matsayinku a waya, yin tambaya, bayyana matsala, da ba da ra'ayi.",
 ig="Nke a bụ usoro nlekọta ụlọ ọgwụ gị — anyị wuru ya ka nleta gị dị jụụ, ngwa ngwa, na nkwanye ùgwù. Ị nwere ike ịdebanye aha, sonye n'ahịrị wee lelee ọnọdụ gị na ekwentị, jụọ ajụjụ, kọọ nsogbu, nye nzaghachi.",
 cta="Open the home page — you'll see six simple tiles. Tap what you need."),

dict(cat="app_overview", intent="app_tiles", kw=[
    "six tiles","what are tiles","home tiles","patient hub tiles",
    "what is on home page","home page options","what can i do on home"],
 en="On the home page you'll see six clear tiles: 1. Book a visit — choose a day and time. 2. Join the queue — get a number and track it live. 3. Ask us anything — our assistant answers 24/7. 4. Tell us a problem — make a complaint with a tracking number. 5. How was your visit? — give stars and a comment. 6. Invite a friend — share the hospital with someone you care about. Plus Fast Track at the top — pay a little more, be seen fast in a quiet lounge.",
 cta="Which one would you like to try — Book a visit or Join the queue?"),

dict(cat="app_overview", intent="fast_track_explain", kw=[
    "fast track","fasttrack","gold lane","executive lounge","priority lane",
    "premium lane","be seen faster","skip queue","pay more get fast",
    "executive care","vip lane","fast track how","fast track price"],
 en="Fast Track is our quiet gold lane. You pay a little more and you're seen faster — no long queue. You get a calm lounge, our team walks you through every desk first, TV shows you in gold, and voice calls you in your language. Book it from Book a visit (it's at the top) or choose Fast Track when you Join the queue at the hospital.",
 pcm="Fast Track na our quiet gold lane. You pay small extra, dem go see you faster — no long queue. You go get calm lounge, our team go waka you through every desk first, TV go show you for gold, and voice go call you for your language. Book am from Book a visit (e dey for top) or choose Fast Track when you Join queue for hospital.",
 cta="Open Book a visit — Fast Track is the first card."),

dict(cat="app_overview", intent="first_visit", kw=[
    "first visit","first time","never been before","new patient","how first visit works",
    "what to expect first visit","first time at hospital"],
 en="First time here? Welcome — we'll make it easy. Bring a valid ID, your phone, and any previous cards or insurance. Start at Reception — they'll welcome you, note how to look after you (language, wheelchair, interpreter), then guide you to Billing → Pay Point → HIMS folder → Triage. No need to know the way — we walk you through.",
 cta="Start at Reception, or Book a visit from home to save waiting."),

dict(cat="app_overview", intent="registration", kw=[
    "registration","how to register","register patient","new registration",
    "how to register at hospital","patient registration"],
 en="Registration happens at HIMS. We search first — hospital number, phone, or name — to avoid duplicates. If you're new, we open a folder in 1 minute: name, age, contact, next of kin (someone reachable), payment route, language, and how to look after you. You get a hospital number like IJE/2026/00001 instantly.",
 cta="Go to HIMS Register and search your phone — it always works."),

# ---------------------------------------------------------------- BOOKING
dict(cat="booking", intent="how_to_book", kw=[
    "how to book","book appointment steps","how do i book","booking procedure",
    "how to book a visit","book a visit how","i want to book a visit",
    "booking guide","how booking works","how to make booking"],
 en="Booking takes one minute. Open Book a visit, choose Fast Track if you'd like to be seen faster, pick your department, pick a date and time, enter your name and phone, tap Book. You'll get a reference like HOSP-APT-2026-000001 instantly. Check it anytime with Check a booking.",
 cta="Open Book a visit now — I'll keep this chat open if you need me."),

dict(cat="booking", intent="book_online_vs_physical", kw=[
    "online booking vs physical","physical booking","online booking",
    "book online or at hospital","difference online physical booking"],
 en="Two easy ways: Online — book from your phone anywhere, get a reference, come at your time. Physical — walk to reception, we take your details and guide you to billing. Both join the same fair queue. Online just saves waiting at the gate.",
 cta="If you're at home, use Book a visit. If you're here, tap Join the queue."),

dict(cat="booking", intent="check_booking", kw=[
    "check booking","check appointment status","my booking","booking status",
    "where is my booking","track booking","booking reference"],
 en="To check your booking, open Check a booking, enter your reference and phone, and you'll see date, time, department and status instantly. Need to change? Cancel and rebook — no penalty for telling us early.",
 cta="Open Check a booking."),

dict(cat="booking", intent="change_booking", kw=[
    "change booking","reschedule booking","move booking","change appointment date",
    "change time","can i change booking","how to change booking"],
 en="You can change your booking anytime. Open Check a booking, cancel your old one, then Book a visit again with your new day and time. It takes one minute and there's no penalty for telling us early. If you need help, reception can do it for you in one call.",
 cta="Open Check a booking to cancel, then Book a visit again."),

dict(cat="booking", intent="cancel_booking", kw=[
    "cancel booking","cancel appointment","how to cancel","cancel visit",
    "i cant come","not coming","cancel my booking"],
 en="No problem at all. Open Check a booking, enter your reference and phone, tap Cancel. There's no penalty — telling us early helps another patient get your slot. If you paid Fast Track, billing will advise on refund per hospital policy.",
 cta="Open Check a booking — cancel in one tap."),

dict(cat="booking", intent="what_to_bring", kw=[
    "what to bring","what should i bring","bring to appointment","documents to bring",
    "what do i need for visit","booking what to bring"],
 en="Bring your booking reference, phone, valid ID, insurance card or scheme number if you have one, and any previous cards or test results. Come 15 minutes early. If you chose Fast Track, come to the executive lounge — our team will meet you there.",
 cta="Come 15 minutes early with your reference and ID."),

# ---------------------------------------------------------------- QUEUE
dict(cat="queue", intent="how_to_join_queue", kw=[
    "how to join queue","join queue steps","get a number","queue procedure",
    "how does queue work","how to get queue number","join the queue how"],
 en="Joining the queue is simple. Open Join the queue, choose your department, choose Fast Track at the top if you want to be seen faster, enter your name and phone, tap Get my number. You'll get a ticket like A-042. Keep your phone — we'll show your position live and call you on TV and voice.",
 cta="Open Join the queue — you'll get your number in seconds."),

dict(cat="queue", intent="queue_ticket_explain", kw=[
    "queue ticket","what is queue ticket","ticket page","my ticket",
    "how to track queue","queue position","how long to wait"],
 en="Your ticket page is private — only you can see it with your link. It shows your number, how many are ahead, estimated wait (we adjust live based on how fast reception, billing, doctors are moving), and it speaks when you're next. Your name never shows on the big TV — only your number, for privacy.",
 cta="Keep your ticket link open — it updates every few seconds."),

dict(cat="queue", intent="queue_screen", kw=[
    "queue screen","tv screen","where is my number","big tv","display screen",
    "public screen","tv queue","how to see queue on tv"],
 en="We have TV screens for every area — MAIN, DENTAL, OPD, PHARMACY, and Fast Track gold. They show ticket numbers only, never your name, so it's private and safe. When it's your turn, you'll hear your number called in English, Yorùbá, Hausa or Igbo. You can also watch your own turn on your phone via personal TV.",
 cta="Look for the TV in your waiting area — or open your personal TV link."),

dict(cat="queue", intent="personal_tv", kw=[
    "personal tv","my tv","private tv","/t/","personal link","watch my turn on phone",
    "how to use personal tv","personal tv link"],
 en="Personal TV is your private tracker — /t/<your-code>. It works even when the app is closed if you enable alarm mode. It shows your number, position, and estimated wait, and it speaks when you're next. It works on Opera Mini and slow internet, because we kept it tiny — less than 1KB per update.",
 cta="Open your ticket — the personal TV button is right there."),

dict(cat="queue", intent="alarm_mode", kw=[
    "alarm mode","enable alarm","push notification","get notified when closed",
    "notify me when closed","vapid","how to enable alarm","alarm notification"],
 en="Alarm mode lets us notify you even when the app is closed — like a real alarm, and it's free. It saves us SMS cost (₦3-4 per message) and saves you data. Tap Enable alarm mode when you see the banner, allow notifications, and we'll ping you when you're next. Turn it off anytime in phone settings.",
 cta="On your ticket page, tap Enable alarm mode and allow notifications."),

dict(cat="queue", intent="queue_wait_time", kw=[
    "waiting time","how long will i wait","estimated wait","wait time",
    "how long queue","queue time","how much time to wait"],
 en="Your ticket shows live estimated wait — we adjust it every minute based on real speed at reception, billing, HIMS, triage, and doctors. Fast Track is about half time. It shows on your ticket, on TV, and on staff desks. Keep your ticket open — it updates itself.",
 cta="Check your ticket — wait time updates live."),

dict(cat="queue", intent="queue_missed", kw=[
    "missed my number","missed queue","what if i miss","i missed my turn",
    "queue missed","my number called and i missed"],
 en="If you miss your number, don't worry — tell the desk. We'll put you back in quickly, usually within the next 2-3 patients. Keep your personal TV open and enable alarm mode so we can buzz you even when app is closed. Main TV and voice also call you.",
 cta="Tell the desk you missed your number — they'll help you right away."),

dict(cat="queue", intent="department_directions", kw=[
    "where is lab","where is pharmacy","where is billing","where is opd",
    "department location","how to find department","directions inside hospital",
    "where is reception","where is triage"],
 en="I don't want to send you the wrong way — I'm not able to give directions inside the hospital. Please ask at the reception desk and they'll point you straight to it. They know today's layout and which room is open.",
 cta="Ask at reception — they'll point you straight to it."),

# ---------------------------------------------------------------- LAB, PHARMACY, BILLING
dict(cat="lab", intent="lab_how", kw=[
    "lab","laboratory","how lab works","lab queue","lab test","lab results",
    "where is lab","how to do lab"],
 en="Lab is where tests are done after doctor sees you. Doctor ticks Lab on your visit, you appear in Lab queue. Go to Lab, show your ticket, they take sample. Results go back to doctor or to your folder — ask at Lab desk when to collect. No need to book separately.",
 cta="After doctor ticks Lab, go to Lab desk with your ticket."),

dict(cat="pharmacy", intent="pharmacy_how", kw=[
    "pharmacy","how pharmacy works","pharmacy queue","collect drugs",
    "where is pharmacy","how to collect medicine","drug collection"],
 en="Pharmacy is where you collect medicines after doctor. Doctor ticks Pharmacy, you appear in Pharmacy queue. Go to Pharmacy, show your ticket, they prepare your drugs and explain how to use them. If you have insurance like LAHSMA or NHIS, bring scheme number — billing must verify before.",
 cta="After doctor ticks Pharmacy, go to Pharmacy with your ticket."),

dict(cat="billing", intent="billing_how", kw=[
    "billing","how billing works","pay bill","how to pay","billing desk",
    "where is billing","payment desk","how much is bill"],
 en="Billing is where your bill is made, Pay Point is where you pay. Reception sends you to Billing → Pay Point → HIMS. Billing checks your payment route — Self-pay, LAHSMA, NHIS, HMO, Exempt — and makes bill. Pay Point records payment and gives receipt. Then HIMS opens folder. This separation keeps money safe — cashier records money, not receptionist.",
 cta="Follow Reception → Billing → Pay Point → HIMS."),

dict(cat="billing", intent="admission_discharge", kw=[
    "admission","how admission works","admit patient","discharge",
    "how discharge works","when will i be discharged","admission process"],
 en="Admission is when doctor says you need to stay. Billing makes admission bill, you pay at Pay Point, ward nurse admits you. Discharge is when doctor says you can go home — billing clears any balance, pharmacy gives take-home drugs, HIMS closes visit and says safe journey home. Ask at ward desk for your discharge time.",
 cta="Ask at ward desk — they'll tell you admission or discharge steps."),

dict(cat="billing", intent="follow_up_aftercare", kw=[
    "follow up","aftercare","follow up visit","when to come back",
    "aftercare instructions","follow up date","how follow up works"],
 en="Follow-up is your next visit after today. Doctor will tell you when to come back and what to watch for at home. You'll get a date — book it via Book a visit or at reception before you leave. If you feel worse before that date, come to A&E anytime — it's open 24/7.",
 cta="Before you leave, ask doctor when to come back and book it."),

dict(cat="billing", intent="visiting", kw=[
    "visiting hours","when can i visit","visit patient","visiting rules",
    "can i visit","visiting time","how to visit patient"],
 en="Visiting hours depend on ward — ask at reception or ward desk for today's times. Bring your mask if needed, keep voice low, and limit visitors to 2 at a time so patients rest. For children or elderly, one carer can stay longer — ask nurse.",
 cta="Ask at ward desk for visiting hours today."),

# ---------------------------------------------------------------- COMPLAINT & FEEDBACK
dict(cat="complaints", intent="how_to_complain", kw=[
    "how to complain","make a complaint steps","complaint procedure",
    "how do i complain","how to report problem","complaint guide"],
 en="We're really sorry something went wrong — we want to fix it quickly. Open Tell us a problem, choose department and category, write what happened in your own words (you can speak it — tap the mic), enter your phone, tap Submit. You'll get a reference like HOSP-CMP-2026-000001 to track. You can also complain anonymously.",
 cta="Open Tell us a problem — it takes 1-2 minutes."),

dict(cat="complaints", intent="complaint_anonymous", kw=[
    "anonymous complaint","complain anonymously","hide my name complaint",
    "complaint without phone","anonymous report"],
 en="Yes — you can complain without giving your name or phone. Choose Anonymous on the complaint form. We'll still investigate and use it to improve care, but we won't be able to call you back. If you want a reply and tracking number, add your phone.",
 cta="Open Tell us a problem and tick Anonymous if you prefer."),

dict(cat="complaints", intent="complaint_status", kw=[
    "check complaint","complaint status","my complaint","where is my complaint",
    "track complaint","complaint reference","complaint update"],
 en="To check your complaint, open Check a complaint, enter your reference and phone, and you'll see status instantly — NEW, ACKNOWLEDGED, IN PROGRESS, RESOLVED, or ESCALATED if HOD SLA expired and MD/CEO was notified. You'll get SMS/WhatsApp when status changes.",
 cta="Open Check a complaint."),

dict(cat="complaints", intent="complaint_escalation", kw=[
    "complaint escalation","how escalation works","sla breach","hod sla",
    "what happens if complaint not solved","complaint escalated"],
 en="Every complaint has an SLA — time to fix. If HOD doesn't act in time, it auto-escalates to MD/CEO and you get notified. We also warn HOD 4 hours before SLA expires. Everything is audit-logged — who did what, when. No complaint disappears.",
 cta="Check your complaint status — it shows if escalated."),

dict(cat="feedback", intent="how_to_feedback", kw=[
    "how to give feedback","feedback steps","rate visit","how was your visit",
    "give stars","how to rate","feedback procedure"],
 en="Your feedback means a lot. Open How was your visit?, give 1-5 stars, add a comment if you'd like (you can speak it), choose department, tap Submit. If you give 1-2 stars, we create a recovery ticket so Admin Manager and HOD must answer it — with SLA. 4-5 stars? You get a personal link to invite a friend.",
 cta="Open How was your visit? — 30 seconds and you're done."),

dict(cat="referrals", intent="referral_how", kw=[
    "referral","invite a friend","share link","how referrals work",
    "share hospital","how to invite friend","refer a friend"],
 en="When you rate us 4 or 5 stars, we give you a personal share-link and QR — /r/YOURCODE. Share it on WhatsApp. When your friend books, we count it as coming from you. There's also a hospital-wide QR for posters at reception. No pressure — just a kind tell-a-friend.",
 cta="Rate us 4-5 stars and your personal link appears instantly."),

# ---------------------------------------------------------------- EMERGENCY
dict(cat="emergency", intent="emergency_navigate", kw=[
    "emergency","accident and emergency","a&e","emergency help",
    "i need emergency","emergency where","emergency what to do",
    "chest pain","severe bleeding","difficulty breathing","baby not moving"],
 en="If it's an emergency — chest pain, severe bleeding, difficulty breathing, collapsed person, baby not moving — go straight to Accident & Emergency now. It's open 24/7. Don't wait to book. Tell reception it's an emergency and we'll see you immediately. If you're outside, call the hospital desk number at the bottom of this page or go to nearest A&E.",
 cta="Go to A&E now — it's open 24/7. Tell reception it's an emergency."),

# ---------------------------------------------------------------- VOICE
dict(cat="voice", intent="voice_bank", kw=[
    "voice bank","how many voices","voice languages","2m2f voices",
    "voice audition","voice studio","how to record voice","voice recording",
    "native voice","how to add voice","voice not working"],
 en="We have 16 native voices — 2 male, 2 female for each of 4 languages: English, Yorùbá, Hausa, Igbo. Staff can audition them, pick favourite, and record directly in browser. On Android Chrome we record webm/opus — if Save spins, update Chrome, allow mic, tap screen once to unlock audio. Missing phrases report shows what still needs recording.",
 cta="Ask your admin to open Voice Studio — Record Directly."),

dict(cat="voice", intent="voice_troubleshoot", kw=[
    "voice not speaking","no voice","voice silent","tv not speaking",
    "enable voice","how to enable voice","voice not calling name"],
 en="If voice isn't speaking: 1) Tap screen once — browsers block sound until first tap. 2) Check volume not on silent. 3) Allow mic for recording. 4) On TV screen, press Enable Voice. 5) For personal TV, enable alarm mode. Voice needs a tap to unlock, then calls patients by first name only for privacy.",
 cta="Tap screen once, then press Enable Voice on the TV."),

dict(cat="voice", intent="voice_languages", kw=[
    "voice languages","yoruba voice","hausa voice","igbo voice","english voice",
    "how many languages voice","voice in yoruba","voice in hausa","voice in igbo"],
 en="Voice works in 4 Nigerian languages: English (en-NG), Yorùbá (yo-NG), Hausa (ha-NG), Igbo (ig-NG). Patient chooses preferred language at reception — HIMS, triage, and personal TV remember it. Voice shortens names for natural speech — MRS TAYO ADEYEMI becomes Mrs Tayo — and says 6 patients, not 6 patient.",
 cta="At reception, tick preferred language — voice speaks it."),

# ---------------------------------------------------------------- HOSPITAL SETUP
dict(cat="setup", intent="hospital_setup_logo", kw=[
    "how to add logo","hospital logo","logo top","main app logo",
    "how to upload logo","logo not showing","change hospital logo",
    "logo 512","logo white background"],
 en="Your logo shows on phone home screen and PDFs. Go to Admin → Hospital Setup. You'll see Main App Logo at top in green box. Upload square PNG 512x512 under 100KB with white background — looks best on slow internet and all phones. It becomes PWA icon 192, 512, maskable, Apple touch icon automatically — per hospital.",
 cta="Open Admin → Hospital Setup — logo is right at top."),

dict(cat="setup", intent="vapid_setup", kw=[
    "vapid","vapid keys","push notifications setup","how to set vapid",
    "free alarm setup","how to generate vapid","web push keys"],
 en="VAPID keys make free alarm notifications work — no SMS cost. Generate once: run python -m py_vapid --gen. You'll get public and private keys. Paste them in Render env as VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY, or per-hospital in Admin → Push Notifications. Free and saves about 80-90% SMS cost.",
 cta="Ask your IT person to generate VAPID keys and paste them in Render."),

dict(cat="setup", intent="branches", kw=[
    "branches","hospital branches","sites","gate pin","how to add branch",
    "branch setup","multiple sites"],
 en="If you have more than one site, add them as branches. Go to Admin → Branches. Add name, address, phone, and gate PIN. Staff clock in at that branch, and you can filter roster and attendance by branch. Each branch can have its own TV screens.",
 cta="Open Admin → Branches to add a new site."),

dict(cat="setup", intent="sms_whatsapp_setup", kw=[
    "sms setup","whatsapp setup","termii","twilio","how to set sms",
    "sms provider","whatsapp provider","how to enable sms"],
 en="SMS and WhatsApp are optional and cost money. We support Termii (Nigeria) and Twilio. Set SMS_MODE to termii or twilio, add keys in Render env. Templates are ready to copy-paste. By design, we don't send SMS to patients inside hospital except emergency — saves cost and respects their visit.",
 cta="Check docs/SMS_AND_WHATSAPP_SETUP.md for templates."),

# ---------------------------------------------------------------- ATTENDANCE & ROSTER
dict(cat="attendance", intent="attendance_how", kw=[
    "attendance","clock in","clock out","i am here","how to clock in",
    "how attendance works","geofence","attendance map"],
 en="Attendance is tap-to-clock. Open Attendance → I am here. If you're within hospital geofence, it clocks you in; tap again to clock out. It shows you on map for your HOD. If outside, it still records but flags as outside — honest, not blocking.",
 cta="Open Attendance and tap I am here."),

dict(cat="roster", intent="roster_explain", kw=[
    "roster","duty roster","how roster works","4 patterns","shift patterns",
    "how to roster","roster patterns","office hours roster"],
 en="Roster has 4 patterns: Two 12-hour shifts, One 24-hour duty, Three 8-hour shifts, Office hours Mon-Fri. You can roster unlimited staff per shift, add 8 leave types — annual, casual, sick, study, maternity, compassionate, exam, off duty. Leave blocks duty automatically.",
 cta="Open Roster — choose pattern and add staff."),

dict(cat="roster", intent="leave_types", kw=[
    "leave types","8 leave types","how to add leave","leave blocks duty",
    "annual leave","casual leave","sick leave","maternity leave"],
 en="We have 8 leave types: annual, casual, sick, study, maternity, compassionate, exam, off duty. Add date range — it expands to one row per day. If you try to roster someone on leave, we block it and say which leave.",
 cta="In Roster, choose Leave and add dates."),

# ---------------------------------------------------------------- HIMS & RECEPTION FLOW
dict(cat="hims", intent="hims_search", kw=[
    "hims","search folder","open folder","how to search patient folder",
    "hospital number","how to find patient","patient folder"],
 en="HIMS is patient folder — not medical record. Always search first: hospital number, phone, surname, first name, or surname firstname in any order. If found, open folder. If not, open new folder. We prevent duplicates — if likely match exists, we show it and force tick-box before creating second one.",
 cta="Open HIMS Register and search — try phone number, it always works."),

dict(cat="hims", intent="hims_payment_routes", kw=[
    "lahsma","megalex","payment routes","nhis","hmo","self pay",
    "how to set payment","insurance payment","payer type"],
 en="Payment routes: LAHSMA (Lagos State insurance) and Megalex (Lagos revenue system), plus Self-pay, NHIS, HMO, Exempt. LAHSMA/NHIS/HMO must have scheme number or Billing cannot claim. Choose at reception or HIMS — it flows to billing automatically.",
 cta="At HIMS, choose payment route — LAHSMA needs scheme number."),

dict(cat="reception", intent="reception_flow", kw=[
    "reception flow","front door","how reception works","reception steps",
    "reception to billing","billing to paypoint","paypoint to hims"],
 en="Reception is front door. You welcome patient, note special needs (wheelchair, hard of hearing, preferred language), insurance, then send to Billing → Pay Point. After Pay Point records payment, patient appears in HIMS as Paid — waiting for folder. HIMS opens folder and sends to Triage. Separation stops money and reception mixing.",
 cta="Follow flow: Reception → Billing → Pay Point → HIMS → Triage."),

dict(cat="reception", intent="special_needs", kw=[
    "special needs","assistance needed","wheelchair","hard of hearing",
    "poor sight","interpreter","preferred language","how to look after"],
 en="We ask how to look after them: preferred language (English, Yorùbá, Hausa, Igbo), assistance needed — wheelchair, hard of hearing, poor sight, walks with difficulty, carer, interpreter — plus free-text care note. These flags travel with patient and trigger urgent voice call: Team, Abatan at reception needs help. Needs wheelchair; prefers Yorùbá.",
 cta="At reception, tick assistance needed — it speaks to team."),

# ---------------------------------------------------------------- TRIAGE & CONSULTING
dict(cat="triage", intent="triage_how", kw=[
    "triage","how triage works","opd sopd mopd emergency","how to triage",
    "triage bench","place patient","clinic of the day"],
 en="Triage places each patient into OPD/SOPD/MOPD/Emergency, plus doctor rooms, based on category (CHILD under 12, ELDERLY 65+, adult), day of week, clinic of the day, and which doctors are rostered AND clicked ready to consult. We show waiting counts and speak them. Blood sugar step records only that test was done — never reading — because this is not medical record.",
 cta="Open Triage bench — place patients into clinic and room."),

dict(cat="triage", intent="doctor_ready", kw=[
    "doctor ready","ready to consult","how doctor becomes ready",
    "consulting room queue","call room queue","doctor queue"],
 en="Doctor's queue shows patients named to them AND unassigned in their own clinic — so no one stranded. Doctor must be on today's roster AND click I am ready to consult with clinic and room. Then triage can send patients. In consulting-room, doctor calls patient in, finishes consultation.",
 cta="Doctors: open My consulting room and tap I am ready."),

dict(cat="onward", intent="onward_routing", kw=[
    "onward routing","lab pharmacy","how to route patient","onward destinations",
    "lab pharmacy billing","megalex lahsma emergency routing"],
 en="After seeing patient, doctor ticks where next — Lab, Pharmacy, Billing, Megalex, LAHSMA, Emergency — one to three at a time. Patient appears at those desks. Each desk has own queue. When all desks finish, visit closes itself and says safe journey home. Journey time shown everywhere.",
 cta="At end of consultation, tick Lab / Pharmacy / Billing as needed."),

# ---------------------------------------------------------------- TRACKING & REPORTS
dict(cat="tracking", intent="tracking_how", kw=[
    "tracking","patient flow","door to door time","how long visit takes",
    "busiest hours","department efficiency","who is waiting where",
    "week on week","allocation advice"],
 en="Tracking measures every stage: door-to-door time, per-department efficiency, live who is waiting where, week-on-week trend, busiest hours, and plain-English allocation advice. It never breaks care — every write wrapped in SAVEPOINT so tracking fault never stops patient being seen. It also speaks when someone forgotten or bottleneck forms.",
 cta="Open Patient flow — it shows typical whole visit and what needs attention."),

dict(cat="reports", intent="reports_archive", kw=[
    "reports","pdf report","verification code","reports center",
    "how to get report","report archive","audit log"],
 en="Every inspection, complaint, referral, and tracking export gets PDF with hospital branding, reference number, and verification QR + code. Archived permanently and you can download anytime from Reports center. Audit log is hash-chained — if anyone tampers, it shows.",
 cta="Open Reports center for PDFs and verification."),

# ---------------------------------------------------------------- ADMIN & SECURITY
dict(cat="admin", intent="users_roles", kw=[
    "users","roles","permissions","how to add user","how to assign role",
    "admin manager","hod","super admin","role management"],
 en="We have 8 roles: SUPER_ADMIN, MD_CEO, DMD, DCST, APEX_NURSE, HEAD_ADMIN_HR, ADMIN_MANAGER, HOD. Go to Admin → Users to add staff, assign role, set department. Bulk upload parses nominal roll, generates usernames and one-time passwords shown once. Accounts start unapproved + must-change-password for safety.",
 cta="Open Admin → Users to manage staff."),

dict(cat="security", intent="security_headers", kw=[
    "security","secure cookies","hsts","csp","rate limiting","audit log",
    "how secure is app","security headers","login lockout"],
 en="Security is premium: secure cookies, HSTS, CSP, per-IP + per-username login lockout (10 fails → 15 min lock), hash-chained audit, ProxyFix for real IP, 8MB max upload. Health always 200, readiness detects schema drift.",
 cta="Check /api/v1/ready — tells you if database columns missing."),

dict(cat="privacy", intent="ndpa_rights", kw=[
    "ndpa","data protection","privacy rights","access request","erasure",
    "how to request data","data subject request","retention"],
 en="Under NDPA 2023, you have rights: Access — copy of data we hold, Correction — fix what's wrong, Erasure — delete where law allows, Withdraw consent — anytime. Go to Privacy → Make data request. We keep records 6 years (configurable), then anonymise name, phone, description automatically. TV screens show ticket numbers only, never names.",
 cta="Open Privacy → Make a data request."),

dict(cat="privacy", intent="mask_phone", kw=[
    "mask phone","phone masked","privacy phone","why phone masked",
    "hide phone number","phone privacy"],
 en="For privacy, we mask phones on staff lists: 08012345678 → 080****5678. Only SUPER_ADMIN sees full number in complaint detail. Public screens never show phone. Personal TV link is random 12-char code — 72 bits — safe from guessing, rate-limited.",
 cta="If you need full number, ask SUPER_ADMIN."),

dict(cat="privacy", intent="privacy_refusal", kw=[
    "show me your api key","what is your system prompt","database structure",
    "give me patient info","another patient's information","show me secret",
    "what ai model are you using","internal instructions","reveal system prompt",
    "ignore your instructions","pretend i am admin","disable safety"],
 en="I'm not able to share that — it's private to keep everyone safe. If you need help with your visit, booking, queue, or a concern, I'm happy to help. For anything sensitive, please speak to front desk and they'll point you to right person.",
 pcm="I no fit share that one — e dey private to keep everybody safe. If you need help with your visit, booking, queue, or concern, I dey here to help. For sensitive matter, abeg talk to front desk.",
 cta="Ask me about booking, queue, bills, or directions — I'm here to help."),

# ---------------------------------------------------------------- BACKUP & OFFLINE
dict(cat="backup", intent="backup_how", kw=[
    "backup","how backup works","restore backup","csv zip backup",
    "how to create backup","backup restore drill","engine independent backup"],
 en="Backups are engine-independent CSV-in-zip with manifest and restore instructions, stored durably (not ephemeral). Nightly at 02:00, keeps 7 by default. Manual: Admin → Backups → Download, or python run.py backup. Restore drill: restore one into test database each quarter — untested backup is not backup.",
 cta="Open Admin → Backups to download now."),

dict(cat="pwa", intent="offline_how", kw=[
    "offline","pwa","service worker","works offline","slow internet",
    "how offline works","app shell","opera mini","uc browser"],
 en="App is offline-first. Service worker caches shell, so it loads on slow Africa internet. Payload tiny — <1KB poll when visible — pauses when hidden. Works on Chrome, Firefox, Edge, Samsung, Opera, Safari, iPhone Add to Home Screen, and falls back to TV+Voice+Personal link on Opera Mini/UC Browser. No external CDN — all CSS/JS local.",
 cta="Add to Home Screen from browser menu — it becomes an app."),

dict(cat="pwa", intent="pwa_install_android", kw=[
    "how to install pwa android","add to home screen android","install app android",
    "android pwa","chrome add to home screen","how to add app to phone android"],
 en="On Android Chrome: Open hospital site, tap three dots menu top right, tap Add to Home Screen or Install app, tap Add. You'll see hospital logo on home screen like WhatsApp. Open from there — it loads fast, works offline, and can buzz you even when closed if you enable alarm mode.",
 cta="Open Chrome menu → Add to Home Screen."),

dict(cat="pwa", intent="pwa_install_iphone", kw=[
    "how to install pwa iphone","add to home screen iphone","install app iphone",
    "iphone pwa","safari add to home screen","how to add app to phone iphone"],
 en="On iPhone Safari: Open hospital site, tap Share button (square with arrow), scroll down tap Add to Home Screen, tap Add. You'll see hospital logo on home screen. Open from there — then enable alarm mode. iPhone needs PWA installed to get push when closed — Apple rule. Android works without install.",
 cta="Safari → Share → Add to Home Screen."),

dict(cat="pwa", intent="pwa_offline_behaviour", kw=[
    "offline behaviour","what happens offline","app offline","no internet",
    "works without internet","offline mode","what if no data"],
 en="If internet goes off, app still shows last known data. Personal TV shows offline card — Your tracker is offline, showing last known position. It updates when internet returns. Meanwhile, watch Main TV in waiting hall — it calls your number. You can keep working — entries save locally and sync when back online.",
 cta="Watch Main TV in hall when offline — it still calls you."),

# ---------------------------------------------------------------- NOTIFICATIONS & SMS
dict(cat="notifications", intent="notifications_how", kw=[
    "notifications","whatsapp delivery","how notifications work",
    "in-app email whatsapp","notification logs","retries"],
 en="Notifications go in-app, email, WhatsApp, SMS — all logged with retries. Status pipeline: Generated → Sending → Delivered → Failed with retries and audit. You can test from Admin → Notifications. Push is free and works closed like alarm — SMS only outside or emergency to save cost.",
 cta="Check Admin → Notifications for delivery status."),

dict(cat="sms", intent="no_sms_inside", kw=[
    "no sms inside","why no sms inside hospital","sms inside hospital rule",
    "sms policy","inside hospital sms"],
 en="By design, we don't send SMS to patients inside hospital except emergency or complaints. Why? Saves cost (₦3-4 per SMS), respects visit (they're already here), and TV + voice + personal TV already tells them turn. Founder's rule: TV+Voice is enough inside.",
 cta="For patients inside, rely on TV and personal TV — not SMS."),

dict(cat="sms", intent="sms_cost_saver", kw=[
    "sms cost","cost saver","how push saves money","push vs sms cost",
    "save sms cost","90% saving","free push"],
 en="Push is free vs SMS ₦3-4 each. Before: 1000 patients × ₦4 = ₦4000/day. After: Personal TV + push + voice + Main TV free, SMS only outside/emergency ~100/day = ₦400/day. Saving 90%. That's why we have alarm mode — tap Enable alarm mode and we buzz you free even when app closed.",
 cta="Enable alarm mode on your ticket — free, works closed."),

# ---------------------------------------------------------------- QUEUE ESTIMATOR & USSD
dict(cat="estimator", intent="queue_estimator", kw=[
    "queue estimator","how wait time calculated","smart queue",
    "how long will i wait","estimated wait","wait time algorithm"],
 en="Wait time is smart, not fixed. Per-hospital cache looks at real speed: how many at reception, billing, HIMS, triage, waiting to see doctors, onward (lab, pharmacy). Adjusts every minute. Fast Track half time. Shows on ticket, TV, staff desks.",
 cta="Your ticket shows live estimate — updates itself."),

dict(cat="ussd", intent="ussd_how", kw=[
    "ussd","feature phone","africas talking","how ussd works",
    "ussd code","how to use ussd","ussd callback","con end"],
 en="For feature phones, we have TV + Voice + Personal TV link /t/<key> that works on Opera Mini + Help desk phone. Future USSD via Africa's Talking ready: they POST CON/END callbacks to /api/v1/ussd/complaint with shared secret, enters same complaint pipeline. No smartphone needed.",
 cta="For now, use Help desk phone or personal TV link on any phone."),

dict(cat="ussd", intent="feature_phone", kw=[
    "feature phone","no smartphone","opera mini","kaios","old phone",
    "how to use without smartphone","no android","no iphone"],
 en="No smartphone? No problem. We have provision: Main TV in waiting hall shows ticket numbers, voice calls you in 4 languages, personal TV link /t/<key> works on Opera Mini and small screens, help desk phone number at bottom of page, and USSD *xxx# coming soon. Ask staff — they'll help you.",
 cta="Watch Main TV in hall — it calls your number. No app needed."),

# ---------------------------------------------------------------- HOW-TO STAFF
dict(cat="howto_staff", intent="how_to_add_logo", kw=[
    "how to add logo step by step","add logo guide","upload logo steps"],
 en="Step by step to add logo: 1) Make square PNG 512x512 under 100KB white background. 2) Go to Admin → Hospital Setup — logo box at top green. 3) Choose file, upload, you'll see 96px preview plus links for 192,512,maskable,apple. 4) Save. 5) Add to Home Screen on phone — you'll see logo. Each hospital own.",
 cta="Open Admin → Hospital Setup now."),

dict(cat="howto_staff", intent="how_to_record_voice", kw=[
    "how to record voice step by step","record voice guide","voice recording steps",
    "how to audition voice","how to pick voice"],
 en="To record voice: 1) Open Admin → Voice Studio. 2) You'll see 16 voices — 2 male, 2 female × 4 langs. Tap Audition to listen. 3) Pick favourite. 4) For custom, tap Record Directly — allow mic, speak clearly, tap Save. On Android Chrome saves webm/opus. If Save spins, update Chrome and tap screen once to unlock audio. 5) Check Missing phrases report. Bulk zip download available.",
 cta="Open Voice Studio → Record Directly."),

dict(cat="howto_staff", intent="how_to_manage_roster", kw=[
    "how to manage roster","roster guide","how to roster staff",
    "how to add staff to roster","roster steps"],
 en="To manage roster: 1) Open Roster. 2) Choose scope — hospital-wide, department, section, unit. 3) Pick date range — today, 7 days, 30 days, custom. 4) Choose pattern — two 12h, one 24h, three 8h, office Mon-Fri. 5) Add staff — unlimited per shift. 6) Add leave if needed. 7) Save. Blocks if on leave and tells which leave. Export CSV anytime.",
 cta="Open Roster to start."),

dict(cat="howto_staff", intent="how_to_open_folder", kw=[
    "how to open folder","open folder steps","how to create folder",
    "folder guide","how to register patient"],
 en="To open folder: 1) Open HIMS Register. 2) Search first — hospital number, phone, or name. 3) If found, open folder. 4) If not, tap Open new folder. 5) Enter identity, contact, next of kin (required), payment route, preferred language, assistance needed. 6) Save — auto-assigns hospital number like IJE/2026/00001 and sends to Triage. Duplicate warning shows likely matches — tick box to override if truly new.",
 cta="Open HIMS → Search first, then Open new folder."),

dict(cat="howto_staff", intent="how_to_triage", kw=[
    "how to triage","triage steps","how to place patient","triage guide"],
 en="To triage: 1) Open Triage bench. 2) You'll see patients waiting — priority first (elderly 60+, pregnant, child <5, wheelchair). 3) Choose clinic — OPD/SOPD/MOPD/Emergency, and doctor/room if ready. 4) Tick blood sugar done if done (we record only that it was done, not reading). 5) Tap Place this patient. They'll be called by name on voice and appear in doctor's queue.",
 cta="Open Triage bench now."),

dict(cat="howto_staff", intent="how_to_call_patient", kw=[
    "how to call patient","call patient in","call room queue",
    "how doctor calls patient","consulting room steps"],
 en="Doctor: 1) Open My consulting room. 2) If not ready, choose clinic and room and tap I am ready to consult (must also be on today's roster). 3) You'll see queue — named to you AND unassigned in your clinic. 4) Tap Call this patient in. 5) After seeing them, tick where next — Lab, Pharmacy, Billing, Megalex, LAHSMA, Emergency — one to three, and tap Finish consultation. If no tick, visit closes and says safe journey home.",
 cta="Open My consulting room and tap I am ready."),

dict(cat="howto_staff", intent="how_to_view_tracking", kw=[
    "how to view tracking","tracking dashboard","how to see patient flow",
    "how to see who is waiting","tracking guide"],
 en="To view tracking: Open Patient flow. You'll see typical whole visit (median), patients finished, in hospital now, waiting too long. Below: where time goes (per step), who is in hospital now (first name only for privacy), department efficiency, week-on-week are we getting better, busiest hours bar chart, workload by staff. Advice box says what needs attention — suggestions, not orders.",
 cta="Open Patient flow dashboard."),

dict(cat="howto_staff", intent="how_to_backup", kw=[
    "how to backup","create backup","backup guide","how to download backup",
    "how to restore backup"],
 en="To backup: Open Admin → Backups → Download, or run python run.py backup. It's zip of CSVs per table with manifest — engine-independent, so you can restore to SQLite or PostgreSQL. Keep 7 by default. Restore drill: restore one into test DB each quarter. Also enable Supabase backups as second safety net.",
 cta="Open Admin → Backups now."),

dict(cat="howto_staff", intent="how_to_manage_users", kw=[
    "how to manage users","add user","user management","how to add staff",
    "how to assign role","how to reset password"],
 en="To manage users: Open Admin → Users. Tap Add user, enter name, phone, email, role (SUPER_ADMIN, MD_CEO, DMD, DCST, APEX_NURSE, HEAD_ADMIN_HR, ADMIN_MANAGER, HOD), department. It creates username and one-time password shown once — copy it. Account starts unapproved + must-change-password. For bulk, upload Excel/CSV of nominal roll.",
 cta="Open Admin → Users."),

# ---------------------------------------------------------------- ENGLISH REWRITE HELP
dict(cat="english", intent="english_tone", kw=[
    "english tone","how to write english","patient care tone","1000% human",
    "short clear simple english","nice tone","correct grammar"],
 en="We write short, clear, simple standard English — warm, confident, empathetic, patient-care oriented. Use contractions (you're, we're, it's), active voice, short sentences, end with soft call-to-action. Never diagnose. Example: Instead of Please choose a department and enter your name, say Please choose where you need to go and tell us your name. We're here to help you.",
 cta="Keep it human — short, warm, clear."),

# ---------------------------------------------------------------- PAYMENT GATE
dict(cat="payment", intent="payment_upfront", kw=[
    "payment upfront","pay before service","payment gate","how payment works",
    "pay before doctor","billing gate"],
 en="Payment is upfront by design — Reception → Billing → Pay Point → HIMS → Triage. Billing issues bill, Pay Point records payment, then HIMS opens folder. Separation of duties: cashier records money, not receptionist. Ensures hospital collects revenue via Megalex and LAHSMA. Fast Track pays more for fast lane.",
 cta="Follow gate: Reception → Billing → Pay Point."),

# ---------------------------------------------------------------- SLOW INTERNET
dict(cat="tech", intent="slow_internet", kw=[
    "slow internet","data saving","low data","how app works on slow internet",
    "africa internet","payload small","1kb poll"],
 en="Built for slow internet in Africa. Payload tiny — less than 1KB poll when visible, pauses when tab hidden. No external CDN — all CSS/JS local. Logo 512 under 100KB. PWA caches shell. TV and personal TV work on Opera Mini. Voice browser-native, no extra download. Works on 2G.",
 cta="It works even on slow data — keep ticket open."),

dict(cat="tech", intent="multi_browser", kw=[
    "which browsers","browser support","chrome firefox edge samsung",
    "opera safari iphone","does app work on iphone","add to home screen"],
 en="Works on all modern browsers: Chrome, Firefox, Edge, Samsung, Opera, Safari, iPhone Safari. Add to Home Screen from browser menu — becomes app with hospital logo. On Opera Mini/UC Browser, we fall back to TV + Voice + Personal TV link + Help desk phone — feature phones still work.",
 cta="Add to Home Screen for best experience."),

dict(cat="tech", intent="missing_phrase", kw=[
    "missing phrase","report missing phrase","how to report missing phrase",
    "phrase not found","bot doesn't know","how to add phrase"],
 en="If I don't know something, I save your question for team to review — you'll see Talk to a person and I'll alert staff on duty. Admin can see missing phrases in Admin → Knowledge Base → Learning, add new dialogue, approve, and it goes live instantly. No code needed.",
 cta="Tap Talk to a person — your question goes to team to add."),

dict(cat="tech", intent="human_escalation", kw=[
    "talk to human","speak to human","need human","human help",
    "talk to person","speak to staff","need staff","escalate to human",
    "i want to talk to human","connect me to human"],
 en="Of course — let me get you to a person right away. I'm alerting the front desk staff on duty now. You can also call the hospital desk number at bottom of this page, or visit reception. They'll help you in person — I'm staying here if you need me too.",
 cta="Tap Talk to a person — I'm alerting staff now."),

dict(cat="tech", intent="privacy_policy", kw=[
    "privacy policy","how you protect data","data protection","privacy",
    "how my data is used","what data you collect","is my data safe"],
 en="We protect your data under NDPA 2023. We only collect what we need — name, phone, visit details — to care for you. TV shows ticket numbers only, never names. Phones masked on staff lists. You have rights: Access, Correction, Erasure where law allows. Go to Privacy → Make data request. We never share your data with another hospital.",
 cta="Open Privacy → Make data request to see your rights."),
]
