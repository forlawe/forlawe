"""GLOBAL DIALOGUE LIBRARY — per-department patient conversations.

WHY THIS FILE EXISTS
--------------------
An audit against the 31 standard departments found 17 with NO dialogue coverage
at all: a patient asking about Internal Medicine, Surgery, Obstetrics, the
Laboratory, Medical Records, Billing or Environmental Health got the generic
"I don't have an answer for that" reply.

Every department below gets 20 real patient exchanges, written the way patients
actually ask (including Pidgin), with warm, specific, actionable answers.

HOUSE STYLE (do not drift from this)
------------------------------------
* Warm and human. Contractions. Never robotic, never a wall of text.
* SPECIFIC: name the room, the document, the person to ask for.
* Always end with a soft, low-friction next step.
* NEVER diagnose, never prescribe, never quote a clinical threshold.
  Anything clinical becomes "let's get you to someone who can examine you".
* Money answers give ranges/《ask billing》, never invented figures.

Each entry: (intent_suffix, [triggers...], english, pidgin, cta)
The department name is prepended to every trigger set automatically, so
"laboratory opening hours" reaches the Laboratory answer even when the
question is phrased around the department name.
"""
from __future__ import annotations

# --------------------------------------------------------------------------
# Shared closing lines, so every department sounds like the same hospital.
# --------------------------------------------------------------------------
_CTA_BOOK = "Open Book a visit — the address is on this reply."
_CTA_DESK = "Ask the front desk, or say talk to a human."
_CTA_HELP = "Anything else I can make easier for you?"

# --------------------------------------------------------------------------
# DEPT_DIALOGUES: department name -> 20 exchanges
# --------------------------------------------------------------------------
DEPT_DIALOGUES: dict[str, list[tuple]] = {}


def _d(dept: str, rows: list[tuple]) -> None:
    DEPT_DIALOGUES[dept] = rows


# ============================================================ INTERNAL MEDICINE
_d("Internal Medicine", [
    ("what", ["what does internal medicine do", "what is internal medicine", "wetin internal medicine dey do"],
     "Internal Medicine is our adult general-care team — the doctors who look after long-term "
     "conditions and the problems that don't fit neatly in one box. Think blood pressure, "
     "diabetes, chest and breathing concerns, and ongoing follow-up. They're the doctors who "
     "get to know you over time.",
     "Internal Medicine na our adult doctor team — dem dey handle long-term matter like BP, "
     "sugar, chest and breathing wahala, plus follow-up. Na dem dey know you well well over time.",
     _CTA_BOOK),
    ("book", ["book internal medicine", "see a physician", "appointment with internal medicine"],
     "Yes — you can book. Internal Medicine runs clinic on weekday mornings, and "
     "mornings are usually calmest. Bring any old results or medicine packets you have; it helps "
     "the doctor enormously.", "No wahala, You fit book. Internal Medicine dey run clinic weekday "
     "morning, and morning dey calm pass. Carry your old result and medicine pack come — e go help doctor.",
     _CTA_BOOK),
    ("bring", ["what should i bring to internal medicine", "what to bring physician"],
     "Bring four things and you're set: your hospital card or file number, any medicines you're "
     "currently taking (the actual packets are best), any previous test results, and a list of "
     "what's been troubling you. That last one matters more than people expect.",
     "Bring four things: your hospital card or file number, the medicine wey you dey take (carry the "
     "pack itself), any old test result, and list of wetin dey worry you. That last one dey important well well.",
     _CTA_HELP),
    ("bp", ["blood pressure clinic", "hypertension follow up", "bp check"],
     "Our blood-pressure follow-up runs in the Internal Medicine clinic. Please come with your "
     "medicines and, if you check at home, your readings. I can't advise on the numbers themselves "
     "— the doctor will read them properly with you.",
     "Our BP follow-up dey Internal Medicine clinic. Come with your medicine, and if you dey check for "
     "house, bring the readings. I no fit talk about the numbers — na doctor go explain am well for you.",
     _CTA_BOOK),
    ("diabetes", ["diabetes clinic", "sugar level clinic", "diabetic follow up"],
     "Yes, our diabetes follow-up is part of Internal Medicine, and it usually runs alongside a "
     "dietitian review. Bring your medicines and any home readings. Come fasting only if the doctor "
     "told you to last time — otherwise eat normally.",
     "Yes, diabetes follow-up dey inside Internal Medicine, and dietitian dey join. Bring your medicine "
     "and any reading from house. Only fast if doctor talk am last time — if not, chop normal.",
     _CTA_BOOK),
    ("results", ["internal medicine results", "when will my results be ready"],
     "Most routine results come back within a day or two and go straight into your file for the "
     "doctor to review with you. I'd rather the doctor walked you through them than have you read "
     "numbers alone — results need context.",
     "Most normal result dey ready within one or two days, and e dey enter your file make doctor "
     "review am with you. Better make doctor explain am than make you read number alone.",
     _CTA_HELP),
    ("wait", ["how long is the wait internal medicine", "queue time physician"],
     "Mornings move fastest — arrive early and you'll usually be seen sooner. You can also take a "
     "queue number from your phone before you arrive, so you're not standing in line.",
     "Morning dey fast pass — come early, dem go see you quick. You fit even take queue number from "
     "your phone before you reach here, so you no go stand for line.", "Say 'queue' or open Get a number."),
    ("referral", ["do i need a referral internal medicine", "referral to physician"],
     "You don't need a referral to be seen — you're welcome to book directly. If another clinic has "
     "written you a referral note, bring it along; it saves repeating your story.",
     "You no need referral — you fit book direct. But if another clinic write referral note give you, "
     "bring am, e go save you from repeating story.", _CTA_BOOK),
    ("cost", ["how much internal medicine", "consultation fee physician"],
     "Consultation is charged at our standard clinic rate, and tests are billed separately depending "
     "on what the doctor orders. The billing desk will give you exact figures before anything is done "
     "— you'll never be surprised.",
     "Consultation na our normal clinic rate, and test get im own charge depending on wetin doctor order. "
     "Billing desk go give you exact figure before dem start anything — no surprise.", _CTA_DESK),
    ("admitted", ["will i be admitted", "medical ward admission"],
     "Only if the doctor feels you'd be safer staying with us, and they'd discuss it with you first. "
     "Most people are seen and go home the same day.",
     "Only if doctor feel say e safer make you stay, and dem go first talk am with you. Most people dey "
     "see doctor and go house same day.", _CTA_HELP),
    ("ward", ["medical ward visiting", "where is the medical ward"],
     "The medical wards are on the ward corridor — reception will walk you there, and the nurses' "
     "station is right at the entrance. Visiting is in the afternoon and evening slots.",
     "The medical ward dey the ward corridor — reception go show you, and nurse station dey right for "
     "entrance. Visiting na afternoon and evening.", _CTA_DESK),
    ("chronic", ["chronic illness care", "long term condition", "regular check up"],
     "Long-term conditions are exactly what this team does best. We'll set you up on a regular review "
     "schedule so nothing drifts, and the same team follows you each time wherever possible.",
     "Long-term sickness na exactly wetin this team sabi. We go put you for regular review so nothing go "
     "slip, and same team go dey follow you as e possible.", _CTA_BOOK),
    ("medicine_refill", ["refill my medicine", "run out of tablets", "repeat prescription"],
     "Please don't stop your medicine — come and see us before it runs out. Book a short review and "
     "the doctor can renew it. Bring the empty pack so we get the exact same one.",
     "No stop your medicine o — come see us before e finish. Book small review, doctor go renew am. Carry "
     "the empty pack come make we give you the exact same one.", _CTA_BOOK),
    ("second_opinion", ["second opinion", "another doctor's view"],
     "Of course — asking for another view is completely reasonable and nobody will take it personally. "
     "Just tell reception when you book and we'll arrange it.",
     "No problem at all — to ask another doctor opinion na correct thing, nobody go vex. Just tell "
     "reception when you dey book and we go arrange am.", _CTA_BOOK),
    ("elderly", ["care for my elderly parent", "old person clinic"],
     "We see many older patients and we'll take good care of your parent. Bring their medicines and "
     "come with them if you can — a familiar face helps, and you'll remember the questions they forget.",
     "We dey see plenty old people and we go take good care of your papa or mama. Bring dem medicine and "
     "follow dem come if you fit — familiar face dey help, and you go remember question wey dem forget.",
     _CTA_BOOK),
    ("fasting", ["should i fast for internal medicine", "eat before appointment"],
     "Only fast if you've been specifically told to for a particular test. Otherwise please eat normally "
     "— arriving weak and hungry helps nobody, least of all you.",
     "Only fast if dem tell you say na for particular test. If not, chop normal — to come weak and hungry "
     "no dey help anybody, especially you.", _CTA_HELP),
    ("interpreter", ["i don't speak english well", "translator internal medicine"],
     "That's perfectly fine — tell reception which language you're most comfortable in and we'll find "
     "someone on the team who speaks it. You should never have to struggle to explain how you feel.",
     "No wahala at all — tell reception which language you sabi pass and we go find person for the team "
     "wey dey speak am. You no suppose struggle to explain how you dey feel.", _CTA_DESK),
    ("emergency", ["chest pain now", "can't breathe internal medicine"],
     "Please don't wait for a clinic appointment or for me — go straight to Accident & Emergency now, "
     "or ask anyone in uniform to take you. That's the right thing to do, and nobody will mind.",
     "No wait for clinic appointment or for me — waka go Accident & Emergency now now, or tell any person "
     "wey wear uniform make dem carry you go. Na the correct thing, nobody go vex.",
     "🚑 Please go to A&E straight away."),
    ("complaint", ["complain about internal medicine", "unhappy with the doctor"],
     "I'm sorry — that shouldn't have been your experience, and management truly wants to hear it. "
     "You can file it here in under a minute and you'll get a reference number to track what happens next.",
     "Sorry o — your experience no suppose be like that, and management really wan hear am. You fit file "
     "am here for less than one minute, and you go get reference number to track am.",
     "Tap 'Make a Complaint' and open Make a complaint."),
    ("hours", ["internal medicine opening hours", "when is the physician clinic"],
     "Internal Medicine clinic runs on weekday mornings, and the ward team is on duty around the clock "
     "for anyone already admitted. Mornings are the calmest time to come.",
     "Internal Medicine clinic dey run weekday morning, and ward team dey on duty 24 hours for people wey "
     "don admit. Morning na the calmest time to come.", _CTA_BOOK),
])

# ============================================================ SURGERY
_d("Surgery", [
    ("what", ["what does surgery department do", "surgical department", "wetin surgery dey do"],
     "Our Surgery team handles planned operations and surgical emergencies — from hernias and "
     "appendix to wound care and post-operative follow-up. They also run a clinic for anyone who "
     "needs assessing before a decision is made.",
     "Our Surgery team dey handle operation wey dem plan and emergency one — hernia, appendix, wound "
     "care and after-operation follow-up. Dem get clinic too for people wey need check first.", _CTA_BOOK),
    ("book", ["book surgery clinic", "see a surgeon", "surgical appointment"],
     "You can book into the surgical outpatient clinic. Bring any scans or reports you already have "
     "— a surgeon can advise far better with the pictures in front of them.",
     "You fit book for surgical outpatient clinic. Bring any scan or report wey you get — surgeon go "
     "advise you better when e see the picture.", _CTA_BOOK),
    ("prepare", ["how do i prepare for surgery", "before my operation"],
     "The team will give you written instructions specific to your operation, and please follow those "
     "exactly. Generally: arrange someone to bring you home, pack an overnight bag just in case, and "
     "ask every question you have at the pre-op visit — no question is silly.",
     "The team go give you written instruction for your own operation, follow am exactly. Generally: arrange "
     "person wey go carry you go house, pack small bag for night, and ask every question for the pre-op visit "
     "— no question dey foolish.", _CTA_HELP),
    ("fasting", ["do i need to fast before surgery", "can i eat before operation"],
     "Fasting instructions come from your surgical team and they are important for your safety — please "
     "follow exactly what they wrote for you. If you've lost the paper, call us rather than guess.",
     "Fasting instruction dey come from your surgical team and e dey important for your safety — follow "
     "exactly wetin dem write. If you lost the paper, call us, no guess.", _CTA_DESK),
    ("cost", ["how much is surgery", "operation cost", "price of operation"],
     "Cost depends entirely on the procedure, so I won't guess at a figure. The billing desk will give "
     "you a written estimate before anything is scheduled, and they'll walk you through what's included.",
     "The cost depend on the operation, so I no go guess figure. Billing desk go give you written estimate "
     "before dem schedule anything, and dem go explain wetin dey inside.", _CTA_DESK),
    ("how_long", ["how long is the operation", "duration of surgery"],
     "That varies a lot by procedure, and your surgeon will tell you what to expect for yours. They'll "
     "also tell your family roughly when to expect news, which helps everyone waiting.",
     "E dey depend on the operation, and your surgeon go tell you wetin to expect for your own. Dem go tell "
     "your family when to expect news too, e dey help people wey dey wait.", _CTA_HELP),
    ("recovery", ["how long to recover", "after surgery recovery"],
     "Recovery depends on the operation and on you. Your team will give you a realistic timeline and a "
     "follow-up date before you leave. Please keep that follow-up — it's how we catch small problems early.",
     "Recovery dey depend on the operation and on your body. The team go give you realistic timeline and "
     "follow-up date before you comot. Abeg keep that follow-up — na so we dey catch small problem early.",
     _CTA_HELP),
    ("wound", ["wound dressing", "change my dressing", "wound care"],
     "Wound dressing is done in the dressing room. Ask reception if you are not sure where. Come at your scheduled "
     "time if you have one; if the wound looks angry, is smelling, or you're worried, come sooner rather "
     "than later. We'd always rather see you.",
     "Dressing dey the dressing room. Ask reception if you no sure where. Come for your appointment time; but if the wound "
     "don red, dey smell, or you dey worry, come quick quick. We prefer make you come.", _CTA_DESK),
    ("stitches", ["remove stitches", "when do stitches come out"],
     "Your discharge note will say when — it varies by where the wound is. Come to the dressing room on "
     "that date and it's usually a quick visit.",
     "Your discharge note go talk when — e dey depend on where the wound dey. Come dressing room that day, "
     "e no dey take time.", _CTA_DESK),
    ("theatre", ["where is the theatre", "operating theatre location"],
     "Ask reception for the theatre. There is a waiting area for families nearby. "
     "Reception will walk you across if you're not sure.",
     "Ask reception for the theatre. Family waiting area dey there. Reception go waka with you "
     "if you no sure.", _CTA_DESK),
    ("family_wait", ["where can my family wait", "waiting during operation"],
     "There's a family waiting area right by the theatre complex. Please keep one phone reachable — the "
     "team will come out and update you personally as soon as there's news.",
     "Family waiting area dey right near theatre complex. Make one phone dey reachable — the team go come out "
     "give you update as soon as news dey.", _CTA_HELP),
    ("cancel", ["cancel my operation", "postpone surgery"],
     "Life happens — just let us know as early as you can so we can offer the slot to someone else and "
     "give you a new date. Nobody will be annoyed with you.",
     "Life dey happen — just tell us early so we fit give another person the slot and give you new date. "
     "Nobody go vex for you.", _CTA_DESK),
    ("consent", ["what is consent form", "sign for operation"],
     "The consent form is the surgeon explaining exactly what they plan to do, the risks, and the "
     "alternatives — and you agreeing. Please don't sign until you fully understand it. Asking them "
     "to explain again is completely normal.",
     "Consent form na the surgeon explaining wetin dem wan do, the risk, and other option — then you agree. "
     "No sign until you really understand am. To ask dem make dem explain again na normal thing.", _CTA_HELP),
    ("hernia", ["hernia", "swelling in my groin"],
     "That's exactly the sort of thing the surgical clinic assesses — but I can't tell you what it is from "
     "here, and I wouldn't try. Let's get you seen so someone can examine you properly.",
     "Na exactly wetin surgical clinic dey check — but I no fit tell you wetin e be from here, and I no go try. "
     "Make we book you make person examine you well.", _CTA_BOOK),
    ("appendix", ["appendix pain", "appendicitis"],
     "Severe or worsening tummy pain shouldn't wait for a clinic appointment. Please go to Accident & "
     "Emergency now so someone can examine you straight away.",
     "Belle pain wey strong or dey worse no suppose wait for clinic appointment. Abeg go Accident & Emergency "
     "now make person check you sharp sharp.", "🚑 Please go to A&E straight away."),
    ("scan", ["do i need a scan before surgery", "pre op tests"],
     "Usually yes — some blood tests and often a scan, so the team knows exactly what they're working with. "
     "They'll write you a list, and Laboratory and Imaging are both on site.",
     "Usually yes — some blood test and often scan, so the team go know wetin dem dey face. Dem go write you "
     "list, and Laboratory and Imaging both dey here.", _CTA_DESK),
    ("children", ["surgery for my child", "child operation"],
     "Children's surgery is handled with the Paediatrics team alongside the surgeons, and a parent stays "
     "with the child wherever possible. We'll explain everything to you both.",
     "Children operation, Paediatrics team dey join the surgeon do am, and parent dey stay with the pikin as "
     "e possible. We go explain everything give both of una.", _CTA_BOOK),
    ("results", ["biopsy result", "surgery test results"],
     "Some results take longer than others, and your surgeon will go through them with you at your "
     "follow-up. If anything needs faster attention, we'll contact you — you won't be left wondering.",
     "Some result dey take time pass others, and your surgeon go go through am with you for follow-up. If "
     "anything need quick attention, we go call you — you no go dey wonder.", _CTA_HELP),
    ("hours", ["surgery clinic hours", "when is surgical clinic"],
     "The surgical outpatient clinic runs on weekday mornings. Emergency surgical cover is available "
     "around the clock through Accident & Emergency.",
     "Surgical outpatient clinic dey run weekday morning. Emergency surgical cover dey available 24 hours "
     "through Accident & Emergency.", _CTA_BOOK),
    ("complaint", ["complain about surgery", "unhappy with my operation"],
     "I'm truly sorry. Please tell us — surgical concerns are taken very seriously and go straight to "
     "management. You'll get a reference number and a real response.",
     "I sorry well well. Abeg tell us — surgical matter dey serious and e dey go straight to management. You "
     "go get reference number and real response.", "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ OBSTETRICS & GYNAECOLOGY
_d("Obstetrics & Gynaecology", [
    ("what", ["what is obstetrics", "what is gynaecology", "o and g department"],
     "This is our women's health team. Obstetrics looks after you through pregnancy, birth and just "
     "after; Gynaecology handles women's health concerns more generally. Same warm team, same building.",
     "Na our women health team. Obstetrics dey look after you for pregnancy, birth and after; Gynaecology "
     "dey handle women health matter generally. Same team, same building.", _CTA_BOOK),
    ("anc_book", ["book antenatal", "register for anc", "i am pregnant"],
     "Congratulations! Let's get you registered for antenatal care — the earlier you start, the better "
     "we can look after you and your baby. Bring your ID and any previous pregnancy records.",
     "Congratulations o! Make we register you for antenatal care — the earlier you start, the better we fit "
     "look after you and your baby. Bring your ID and any old pregnancy record.", _CTA_BOOK),
    ("anc_visits", ["how often are antenatal visits", "anc schedule"],
     "Visits get more frequent as your pregnancy progresses — spaced out early on, closer together near "
     "the end. Your midwife will give you your personal schedule at booking, and we'll remind you.",
     "Visit dey increase as the pregnancy dey grow — e dey far apart for early, then close together near the "
     "end. Your midwife go give you your own schedule for booking, and we go remind you.", _CTA_BOOK),
    ("anc_bring", ["what to bring to antenatal", "antenatal card"],
     "Bring your antenatal card every single visit — it's your record and the team needs it. Plus your ID, "
     "any medicines you take, and your last scan or test results if you have them.",
     "Bring your antenatal card every visit — na your record and the team need am. Plus your ID, medicine wey "
     "you dey take, and your last scan or test result if you get am.", _CTA_HELP),
    ("delivery_cost", ["how much is delivery", "cost of childbirth", "delivery fee"],
     "Delivery costs vary depending on the type of birth and what's needed on the day, so I won't quote you "
     "a figure I can't stand behind. The billing desk gives written estimates — and it's a very good idea to "
     "ask for one during pregnancy, not on the day.",
     "Delivery cost dey vary depending on the type of birth and wetin dem need that day, so I no go quote "
     "figure wey I no sure of. Billing desk dey give written estimate — better make you collect am during "
     "pregnancy, no be for the day.", _CTA_DESK),
    ("labour_signs", ["am i in labour", "labour pains started", "water broke"],
     "If your waters have broken, the pains are regular and strong, or you're bleeding — come in now, "
     "don't wait for me or for morning. The labour ward is open every hour of every day and someone is "
     "always there.",
     "If your water don break, the pain dey regular and strong, or you dey bleed — come now now, no wait for "
     "me or for morning. Labour ward dey open every hour every day and person dey there always.",
     "🚑 Please come to the labour ward now."),
    ("labour_bag", ["what to pack for delivery", "hospital bag"],
     "Pack for you and for baby: your antenatal card, ID, wrappers and towels, toiletries, baby clothes, "
     "nappies and a shawl. Pack it by week 36 so it's ready — babies rarely check the calendar.",
     "Pack for you and for baby: antenatal card, ID, wrapper and towel, toiletries, baby cloth, nappy and "
     "shawl. Pack am by week 36 make e ready — baby no dey check calendar.", _CTA_HELP),
    ("scan", ["pregnancy scan", "ultrasound in pregnancy"],
     "Scans are done in our Imaging unit and your midwife will tell you when each one is due. Some scans "
     "need a full bladder — the request slip will say, so please read it.",
     "Dem dey do scan for our Imaging unit and your midwife go tell you when each one due. Some scan need "
     "full bladder — the request slip go talk am, abeg read am.", _CTA_BOOK),
    ("birth_partner", ["can my husband be present", "birth partner", "can someone stay with me"],
     "Yes, in most cases you're welcome to have one support person with you, and it helps more than you'd think. "
     "The midwife will explain the arrangements for the day.",
     "Yes, most times you fit get one person wey go support you, and e dey help well well. The midwife go "
     "explain the arrangement for that day.", _CTA_HELP),
    ("caesarean", ["caesarean section", "cs delivery", "will i need cs"],
     "That's a decision your doctor makes with you, based on what's safest for you and your baby on the "
     "day — never something I could predict from here. If it's discussed, they'll explain exactly why.",
     "Na decision wey your doctor go take with you, based on wetin safe pass for you and your baby that day "
     "— no be something wey I fit predict from here. If dem discuss am, dem go explain why.", _CTA_HELP),
    ("postnatal", ["postnatal check", "after delivery care", "6 week check"],
     "We'll see you and baby after the birth to check you're both healing and thriving — it's an important "
     "visit, not just a formality. Your discharge note will have the date.",
     "We go see you and baby after birth to check say una two dey heal well — na important visit, no be just "
     "formality. Your discharge note go get the date.", _CTA_BOOK),
    ("family_planning", ["family planning", "contraception", "birth spacing"],
     "Our family planning service will talk you through all the options confidentially, with no pressure "
     "and no judgement, so you can choose what fits your life.",
     "Our family planning service go explain all the option to you privately, no pressure, no judgement, so "
     "you fit choose wetin fit your life.", _CTA_BOOK),
    ("gynae", ["gynaecology clinic", "women's health problem"],
     "The gynaecology clinic handles women's health concerns of all kinds, and everything you say stays "
     "private. Please don't feel embarrassed — the team has heard it all and they're kind about it.",
     "Gynaecology clinic dey handle all kind women health matter, and everything wey you talk dey private. "
     "No shy — the team don hear everything and dem dey kind about am.", _CTA_BOOK),
    ("bleeding", ["bleeding in pregnancy", "heavy bleeding"],
     "Bleeding in pregnancy always needs to be looked at in person, straight away — please come in now "
     "rather than waiting or searching online. Better to come and be reassured.",
     "Bleeding for pregnancy always need make person check am face to face, sharp sharp — abeg come now "
     "instead of waiting or dey search online. Better make you come make dem tell you say you dey alright.",
     "🚑 Please come in now."),
    ("baby_movement", ["baby not moving", "reduced fetal movement"],
     "Please come in and be checked — today, not tomorrow. You know your baby's pattern better than anyone, "
     "and if something feels different that's reason enough. Nobody will think you're overreacting.",
     "Abeg come make dem check you — today, no be tomorrow. You sabi your baby movement pass anybody, and if "
     "something different, na enough reason. Nobody go think say you dey overreact.",
     "🚑 Please come in and be checked."),
    ("male_doctor", ["can i see a female doctor", "female doctor please"],
     "Just say so at reception and we'll do our best to arrange it. That's a completely reasonable request "
     "and you won't need to explain yourself.",
     "Just talk am for reception and we go try our best to arrange am. Na correct request and you no need "
     "explain yourself.", _CTA_DESK),
    ("hours", ["antenatal clinic hours", "when is anc"],
     "Antenatal clinic runs on set weekday mornings — reception will confirm which day suits your booking "
     "group. But the labour ward never closes, day or night.",
     "Antenatal clinic dey run some weekday morning — reception go confirm which day fit your booking group. "
     "But labour ward no dey close, day or night.", _CTA_BOOK),
    ("breastfeeding", ["breastfeeding help", "trouble feeding baby"],
     "Our midwives and nurses love helping with this, and there's no such thing as a silly "
     "question. Come to the postnatal clinic or ask any midwife — they'd rather help early than late.",
     "Our midwife and nurse dey really like to help with this one, and no question dey foolish. Come postnatal "
     "clinic or ask any midwife — dem prefer to help early than late.", _CTA_DESK),
    ("results", ["pregnancy test results", "anc test results"],
     "Your results go into your antenatal card and the midwife goes through them with you at your next "
     "visit. If anything needs attention sooner, we will contact you.",
     "Your result dey enter your antenatal card and midwife go go through am with you for your next visit. "
     "If anything need attention quick, we go call you.", _CTA_HELP),
    ("complaint", ["complain about maternity", "unhappy with anc"],
     "I'm so sorry — maternity care especially should feel safe and respectful. Please tell us; it goes "
     "straight to management and you'll get a reference number.",
     "I sorry well well — maternity care especially suppose make you feel safe and respected. Abeg tell us; e "
     "dey go straight to management and you go get reference number.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ LABORATORY
_d("Laboratory", [
    ("what", ["what does the laboratory do", "lab department", "wetin lab dey do"],
     "The Laboratory runs the tests your doctor orders — blood, urine, samples of all kinds — and gets "
     "accurate results back to your file. We also run the blood bank.",
     "Laboratory dey run the test wey your doctor order — blood, urine, all kind sample — and dem dey put "
     "accurate result for your file. We dey run blood bank too.", _CTA_DESK),
    ("hours", ["laboratory hours", "when is the lab open", "lab opening time"],
     "The lab collects samples from early morning through the working day, and there's emergency cover "
     "around the clock for urgent tests. Early morning is best if you're fasting.",
     "Lab dey collect sample from early morning through the work day, and emergency cover dey 24 hours for "
     "urgent test. Early morning better if you dey fast.", _CTA_DESK),
    ("fasting", ["do i need to fast for blood test", "fasting blood sugar", "can i eat before lab"],
     "Some tests need fasting and some don't — your request slip will say. If it does, water is fine but "
     "no food. If you're unsure, come early and ask at the lab window rather than guessing.",
     "Some test need fasting, some no need — your request slip go talk am. If e need, water dey okay but no "
     "food. If you no sure, come early ask for lab window instead of guessing.", _CTA_HELP),
    ("how_long", ["when will my lab results be ready", "how long for results"],
     "Most routine tests are back the same day or the next. A few specialised ones take longer, and the "
     "lab will tell you when you hand in your sample so you're not left guessing.",
     "Most normal test dey ready same day or next day. Some special one dey take longer, and lab go tell you "
     "when you submit your sample so you no go dey guess.", _CTA_HELP),
    ("collect", ["collect my results", "where do i pick up results"],
     "Results go into your file for your doctor, and you can collect a copy at the lab window with your "
     "ID and receipt. We'd always rather your doctor explained them to you than have you reading numbers "
     "alone.",
     "Result dey enter your file for your doctor, and you fit collect copy for lab window with your ID and "
     "receipt. We prefer make doctor explain am give you than make you read number alone.", _CTA_DESK),
    ("explain", ["what does my result mean", "explain my lab result", "is my result normal"],
     "I can see why you'd want to know right away — but I really can't interpret results, and I won't "
     "guess with your health. Numbers mean different things for different people. Let's get you in front "
     "of the doctor who ordered it.",
     "I understand say you wan know now now — but I no fit interpret result, and I no go guess with your "
     "health. Number dey mean different thing for different person. Make we put you in front of the doctor "
     "wey order am.", _CTA_BOOK),
    ("cost", ["how much is a blood test", "lab test price"],
     "It depends which tests were ordered — some are inexpensive, others more. The billing desk will price "
     "your specific slip before the sample is taken, so you'll know first.",
     "E depend on which test dem order — some cheap, some cost. Billing desk go price your own slip before dem "
     "take sample, so you go know first.", _CTA_DESK),
    ("blood_sample", ["taking blood", "afraid of needles", "does it hurt"],
     "It's a quick pinch and then it's done — usually under a minute. Tell the phlebotomist if you're "
     "nervous or have fainted before; they'll lay you down and take extra care. It's a very common worry.",
     "Na small pinch then e don finish — usually less than one minute. Tell the person if you dey fear or you "
     "don faint before; dem go make you lie down and take extra care. Plenty people dey fear am.", _CTA_HELP),
    ("urine", ["urine sample", "how to give urine sample"],
     "The lab will give you a clean container and explain it — briefly, midstream is best, and the "
     "container shouldn't touch anything. Ask if you're unsure; they explain it dozens of times a day.",
     "Lab go give you clean container and explain am — for short, midstream na the best, and the container no "
     "suppose touch anything. Ask if you no sure; dem dey explain am plenty times every day.", _CTA_DESK),
    ("blood_bank", ["blood bank", "i need blood", "blood transfusion"],
     "Our blood bank is part of the Laboratory. If a patient needs blood, the clinical team arranges it — "
     "and if you'd like to donate, we'd be very glad to see you.",
     "Our blood bank dey inside Laboratory. If patient need blood, the clinical team go arrange am — and if "
     "you wan donate, we go happy well well to see you.", _CTA_DESK),
    ("donate", ["donate blood", "blood donation"],
     "Thank you — that's a truly generous thing to do, and it saves lives here. Come to the lab, bring "
     "ID, eat properly beforehand and drink water. The whole thing takes well under an hour.",
     "Thank you — na correct generous thing, and e dey save life here. Come lab, bring ID, chop well before "
     "and drink water. The whole thing no go pass one hour.", _CTA_DESK),
    ("repeat", ["why repeat my test", "they took blood twice"],
     "Sometimes a sample clots, the volume is short, or the doctor wants to confirm something before "
     "acting on it. It's frustrating, I know — but it's done to be sure, never to charge you twice.",
     "Sometimes sample dey clot, the quantity no reach, or doctor wan confirm something before e act. E dey "
     "annoy, I know — but na to make sure, no be to charge you twice.", _CTA_HELP),
    ("home", ["home sample collection", "can you come to my house"],
     "Ask at the lab window about home collection — availability varies. For most tests coming in is "
     "quicker, and you'll be seen promptly.",
     "Ask for lab window about home collection — e no dey always available. For most test, to come here dey "
     "faster, and dem go attend to you quick.", _CTA_DESK),
    ("child", ["blood test for my child", "child sample"],
     "We take extra care with children and you can stay with them throughout — please do, it helps enormously. "
     "Tell the staff if your child is very anxious and they'll take it gently.",
     "We dey take extra care with pikin and you fit stay with dem throughout — abeg do, e dey help well well. "
     "Tell the staff if your pikin dey fear well and dem go do am gently.", _CTA_HELP),
    ("lost", ["lost my lab receipt", "lost result slip"],
     "Not a problem — come to the lab window with your ID and your file number and we'll find you in the "
     "system. It happens all the time.",
     "No problem — come lab window with your ID and file number, we go find you for system. E dey happen every "
     "time.", _CTA_DESK),
    ("wrong", ["my result looks wrong", "wrong result"],
     "Please do raise it. Bring it to the lab window and they will check the record, and repeat "
     "the test if there's any doubt. We would much rather double-check than get it wrong.",
     "Abeg raise am — for real. Bring am come lab window make dem check the record, and dem go repeat the test "
     "if doubt dey. We prefer to double-check than to make mistake.", _CTA_DESK),
    ("privacy", ["is my result private", "who can see my results"],
     "Your results are confidential — only the clinical team caring for you and you yourself. We won't "
     "discuss them with anyone else without your permission.",
     "Your result na confidential — na only the clinical team wey dey care for you and you yourself. We no go "
     "discuss am with anybody without your permission.", _CTA_HELP),
    ("hiv", ["hiv test", "confidential test"],
     "That test is completely confidential and comes with counselling before and after — you'll never be "
     "left to handle news alone. Ask at the lab window or any nurse; nobody will make you uncomfortable.",
     "That test na completely confidential and counselling dey before and after — dem no go leave you alone "
     "with news. Ask for lab window or any nurse; nobody go make you feel uncomfortable.", _CTA_DESK),
    ("where", ["where is the laboratory", "find the lab"],
     "The Laboratory is signposted from the main entrance, with sample collection at the front window. "
     "Reception will walk you there if you'd like.",
     "Laboratory get sign from the main entrance, and sample collection dey the front window. Reception go "
     "waka with you if you want.", _CTA_DESK),
    ("complaint", ["complain about the lab", "lab kept me waiting"],
     "I'm sorry the lab kept you waiting — please tell us so management can see it and fix the cause. "
     "You'll get a reference number to follow it up.",
     "Sorry say lab make you wait — abeg tell us make management see am and fix the cause. You go get reference "
     "number to follow am up.", "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ ORTHOPAEDICS
_d("Orthopaedics", [
    ("what", ["what is orthopaedics", "bone department", "orthopedic"],
     "Orthopaedics is our bones, joints and muscles team — fractures, back and knee pain, sports "
     "injuries, and the follow-up care that goes with them.",
     "Orthopaedics na our bone, joint and muscle team — fracture, back and knee pain, sport injury, and "
     "the follow-up wey follow am.", _CTA_BOOK),
    ("book", ["book orthopaedic clinic", "see a bone doctor"],
     "You can book in. If you've had an X-ray anywhere before, bring the film or report — it saves "
     "time and often saves you a repeat scan.",
     "You fit book. If you don do X-ray anywhere before, bring the film or report — e go save time and "
     "sometimes save you from repeating scan.", _CTA_BOOK),
    ("fracture", ["broken bone", "i think i fractured", "suspected fracture"],
     "A suspected break needs looking at today, not next week — please go to Accident & Emergency so "
     "they can X-ray it and set it properly. Waiting can make it harder to fix.",
     "If you suspect say bone break, e need attention today, no be next week — abeg go Accident & Emergency "
     "make dem X-ray am and set am well. To wait fit make am hard to fix.", "🚑 Please go to A&E today."),
    ("plaster", ["plaster of paris", "cast care", "my cast"],
     "Ask reception for the plaster room. Keep the cast dry, don't push anything down "
     "inside it, and come in straight away if your fingers or toes go numb, cold or blue.",
     "Ask reception for the plaster room. Keep the cast dry, no push anything enter inside, and come "
     "sharp sharp if your finger or toe go numb, cold or blue.", _CTA_DESK),
    ("cast_remove", ["remove my cast", "when does the cast come off"],
     "Your clinic note has the date — it depends on the bone and how you're healing. Please don't remove "
     "it yourself at home, however tempting.",
     "Your clinic note get the date — e depend on the bone and how you dey heal. Abeg no remove am yourself "
     "for house, no matter how e dey tempt you.", _CTA_DESK),
    ("back_pain", ["back pain", "waist pain", "my back hurts"],
     "Back pain is one of the commonest things we see, and there's usually plenty that can help. I can't "
     "tell you the cause from here — let's book you in so someone can examine you properly.",
     "Back pain na one of the common things wey we dey see, and plenty thing dey wey fit help. I no fit tell "
     "you the cause from here — make we book you make person examine you well.", _CTA_BOOK),
    ("knee", ["knee pain", "my knee hurts", "joint pain"],
     "Joint pain deserves a proper look rather than guesswork. Book into the orthopaedic clinic and bring "
     "any old scans; the doctor may also refer you to physiotherapy.",
     "Joint pain need proper check, no be guess work. Book orthopaedic clinic and bring any old scan; doctor "
     "fit send you go physiotherapy too.", _CTA_BOOK),
    ("physio", ["do i need physiotherapy", "physio referral"],
     "Often yes — physiotherapy and orthopaedics work hand in hand, and physio does a lot of the real "
     "recovery work. Your doctor will refer you if it'll help.",
     "Often yes — physiotherapy and orthopaedics dey work together, and na physio dey do plenty of the real "
     "recovery work. Your doctor go refer you if e go help.", _CTA_BOOK),
    ("crutches", ["crutches", "walking aid", "wheelchair"],
     "Ask at the orthopaedic clinic — they'll fit you properly and show you how to use it safely. Badly "
     "fitted crutches cause more problems than they solve.",
     "Ask for orthopaedic clinic — dem go fit am well for you and show you how to use am safely. Crutches wey "
     "no fit you dey cause more problem.", _CTA_DESK),
    ("xray", ["do i need an xray", "orthopaedic xray"],
     "Very likely — the doctor will write the request and Imaging is right here on site, so it's usually "
     "the same visit.",
     "E likely — doctor go write the request and Imaging dey here for site, so na usually same visit.", _CTA_DESK),
    ("cost", ["how much orthopaedic", "cost of plaster"],
     "The consultation is our standard rate; X-rays and plaster are billed separately. Billing will give "
     "you exact figures before anything is done.",
     "Consultation na our normal rate; X-ray and plaster get dem own charge. Billing go give you exact figure "
     "before dem do anything.", _CTA_DESK),
    ("surgery", ["will i need surgery orthopaedic", "bone operation"],
     "Only if it's truly the best option for you, and the surgeon will explain exactly why before "
     "anything is decided. Many things heal perfectly well without an operation.",
     "Only if na really the best option for you, and the surgeon go explain why before dem decide anything. "
     "Plenty thing dey heal well without operation.", _CTA_HELP),
    ("recovery", ["how long to heal a fracture", "bone healing time"],
     "It varies by bone and by person — your doctor will give you a realistic timeline for your specific "
     "injury. Following the plan makes a real difference to how well it heals.",
     "E dey depend on the bone and the person — your doctor go give you realistic timeline for your own injury. "
     "To follow the plan dey really change how well e go heal.", _CTA_HELP),
    ("sports", ["sports injury", "injured playing football"],
     "We see a lot of these. Come and have it assessed rather than running it off — early treatment usually "
     "means a faster, fuller recovery.",
     "We dey see plenty of this one. Come make dem assess am instead of managing am — early treatment usually "
     "mean faster and better recovery.", _CTA_BOOK),
    ("elderly_fall", ["my mother fell", "elderly fall", "old person fell down"],
     "Please bring them in to be checked, even if they seem fine — falls in older people can hide a "
     "fracture. Go to Accident & Emergency if there's severe pain or they can't stand.",
     "Abeg bring dem come make dem check, even if dem look alright — fall for old person fit hide fracture. Go "
     "Accident & Emergency if the pain strong or dem no fit stand.", "🚑 A&E if they cannot stand."),
    ("brace", ["back brace", "support belt"],
     "The clinic will advise whether a brace helps your particular problem and fit you properly if so. "
     "Please don't buy one off the market without being assessed first.",
     "The clinic go advise whether brace go help your own problem and dem go fit am well. Abeg no just buy one "
     "for market without make dem check you first.", _CTA_DESK),
    ("hours", ["orthopaedic clinic hours"],
     "The orthopaedic clinic runs on weekday mornings. For fresh injuries, Accident & Emergency is open "
     "around the clock.",
     "Orthopaedic clinic dey run weekday morning. For fresh injury, Accident & Emergency dey open 24 hours.",
     _CTA_BOOK),
    ("follow_up", ["orthopaedic follow up", "review appointment bone"],
     "Please keep your follow-up appointments — that's how we make sure the bone is healing in the right "
     "position. Missing them is how small problems become big ones.",
     "Abeg keep your follow-up appointment — na so we dey make sure say the bone dey heal for correct position. "
     "To miss am na how small problem dey turn big.", _CTA_BOOK),
    ("work", ["can i go back to work", "fitness for work note"],
     "Your doctor will advise based on your job and your recovery, and can write you a note. Ask at your "
     "next appointment.",
     "Your doctor go advise based on your work and your recovery, and dem fit write you note. Ask for your "
     "next appointment.", _CTA_HELP),
    ("complaint", ["complain about orthopaedics"],
     "I'm sorry to hear that. Please file it — it goes straight to management and you'll get a reference "
     "number to track the response.",
     "Sorry to hear that. Abeg file am — e dey go straight to management and you go get reference number to "
     "track the response.", "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ PUBLIC HEALTH
_d("Public Health", [
    ("what", ["what is public health department", "public health unit"],
     "Public Health looks after the health of the whole community — immunisation, health education, "
     "outreach, and disease prevention. Prevention is far cheaper and kinder than treatment.",
     "Public Health dey look after the health of the whole community — immunisation, health education, "
     "outreach, and disease prevention. To prevent cheaper and better pass to treat.", _CTA_DESK),
    ("immunisation", ["immunisation", "vaccination for my baby", "vaccine schedule"],
     "Our immunisation post runs regularly and it's one of the most valuable things you can do for your "
     "child. Bring the child's immunisation card every time — it's their lifelong record.",
     "Our immunisation post dey run regularly and na one of the best thing wey you fit do for your pikin. "
     "Bring the pikin immunisation card every time — na dem record for life.", _CTA_DESK),
    ("missed_vaccine", ["missed immunisation date", "late for vaccine"],
     "Please don't worry and please don't give up — just come, we'll catch your child up. Missing a date "
     "is common and it's fixable.",
     "No worry and no give up — just come, we go catch your pikin up. To miss date na common thing and e dey "
     "fixable.", _CTA_DESK),
    ("card", ["lost immunisation card", "child health card"],
     "Come to the immunisation post with your child; we'll check the register and issue a replacement "
     "where we can.",
     "Come immunisation post with your pikin; we go check the register and issue another one where we fit.",
     _CTA_DESK),
    ("cost", ["is immunisation free", "vaccine cost"],
     "Routine childhood immunisations under the national programme are free. Ask at the post and they'll "
     "tell you clearly which is which.",
     "Routine children immunisation under national programme na free. Ask for the post and dem go tell you "
     "clearly which one be which.", _CTA_DESK),
    ("outbreak", ["disease outbreak", "cholera", "lassa fever"],
     "If you're worried about an outbreak in your area, come and talk to us — and if you have symptoms, "
     "please tell reception as soon as you arrive so you're seen properly and safely.",
     "If you dey worry about outbreak for your area, come talk to us — and if you get symptoms, tell reception "
     "as soon as you enter so dem go attend to you well and safely.", _CTA_DESK),
    ("health_talk", ["health education", "health talk", "community outreach"],
     "We run health talks and community outreach regularly. If your church, mosque, school or association "
     "would like one, come and talk to us — we'd be glad to arrange it.",
     "We dey run health talk and community outreach regularly. If your church, mosque, school or association "
     "want one, come talk to us — we go gladly arrange am.", _CTA_DESK),
    ("malaria", ["malaria prevention", "mosquito net"],
     "Prevention advice, nets and guidance are all things we can help with. If you're feeling unwell right "
     "now, though, please see a clinician rather than self-treating.",
     "Prevention advice, net and guidance na things wey we fit help with. But if you no dey feel well now now, "
     "abeg see clinician instead of treating yourself.", _CTA_BOOK),
    ("screening", ["health screening", "free check up", "screening programme"],
     "We run screening programmes from time to time. Ask at the Public Health desk what's currently "
     "running — some are free.",
     "We dey run screening programme from time to time. Ask for Public Health desk wetin dey run now — some "
     "of dem free.", _CTA_DESK),
    ("antenatal_link", ["public health and pregnancy"],
     "Public Health works closely with our maternity team on antenatal education and immunisation in "
     "pregnancy. Ask either desk and they'll point you the right way.",
     "Public Health dey work closely with our maternity team for antenatal education and immunisation for "
     "pregnancy. Ask any of the desk and dem go show you the way.", _CTA_DESK),
    ("hours", ["public health hours", "when is immunisation"],
     "The immunisation post runs on set days each week — ask at the Public Health desk or reception for "
     "this week's schedule. Come early; it's calmer.",
     "Immunisation post dey run some days every week — ask for Public Health desk or reception for this week "
     "schedule. Come early; e dey calm.", _CTA_DESK),
    ("travel", ["travel vaccination", "yellow card"],
     "Ask at the Public Health desk about travel vaccinations and certificates — availability varies, and "
     "they'll tell you plainly what we can and can't do here.",
     "Ask for Public Health desk about travel vaccination and certificate — e no dey always available, and dem "
     "go tell you straight wetin we fit and no fit do here.", _CTA_DESK),
    ("water", ["clean water advice", "water safety"],
     "Our Public Health and Environmental Health teams both advise on safe water and sanitation. Come and "
     "ask — it's exactly what they're here for.",
     "Our Public Health and Environmental Health team both dey advise on safe water and sanitation. Come ask "
     "— na exactly wetin dem dey here for.", _CTA_DESK),
    ("nutrition_link", ["child nutrition", "malnutrition"],
     "We work with our Nutrition & Dietetics team on this. Please bring the child in to be weighed and "
     "assessed rather than waiting — early help works best.",
     "We dey work with our Nutrition & Dietetics team for this one. Abeg bring the pikin make dem weigh and "
     "assess am instead of waiting — early help dey work pass.", _CTA_BOOK),
    ("family_planning_link", ["public health family planning"],
     "Family planning services are available and completely confidential. Either Public Health or the "
     "O&G clinic can help you.",
     "Family planning service dey available and completely confidential. Public Health or O&G clinic fit help "
     "you.", _CTA_BOOK),
    ("report", ["report a health hazard", "public health complaint"],
     "Please do report it — that's really useful to us. Tell the Public Health desk, or file it through "
     "the complaint form and it'll reach the right people.",
     "Abeg report am — e dey really useful to us. Tell Public Health desk, or file am through complaint form "
     "and e go reach the right people.", _CTA_DESK),
    ("school", ["school health programme", "health talk for school"],
     "Yes, we do school health programmes. Have the school write to us or come and speak to the Public "
     "Health desk and we'll arrange it.",
     "Yes, we dey do school health programme. Make the school write us or come talk to Public Health desk and "
     "we go arrange am.", _CTA_DESK),
    ("hiv_prevention", ["hiv prevention", "confidential advice"],
     "Confidential advice, testing and counselling are all available, and nobody will make you feel "
     "uncomfortable. Ask at the Public Health desk or the Laboratory.",
     "Confidential advice, testing and counselling all dey available, and nobody go make you feel "
     "uncomfortable. Ask for Public Health desk or Laboratory.", _CTA_DESK),
    ("where", ["where is public health"],
     "The Public Health unit is signposted within the hospital — reception will walk you there.",
     "Public Health unit get sign inside the hospital — reception go waka with you.", _CTA_DESK),
    ("complaint", ["complain about public health"],
     "Please tell us — it goes to management with a reference number so you can follow it up.",
     "Abeg tell us — e dey go management with reference number so you fit follow am up.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ HIMS / MEDICAL RECORDS
_d("Health Information Management (HIMS)", [
    ("what", ["what is hims", "medical records department", "records office"],
     "Health Information Management — most people call it Medical Records — keeps your hospital file "
     "safe, accurate and available to the team treating you. If you need your file number or a copy of "
     "your records, this is the desk.",
     "Health Information Management — plenty people dey call am Medical Records — dey keep your hospital file "
     "safe, correct and available to the team wey dey treat you. If you need your file number or copy of your "
     "record, na this desk.", _CTA_DESK),
    ("file_number", ["my file number", "hospital number", "lost my card"],
     "Come to the Records office with any ID and we'll find you in the system — your file doesn't disappear "
     "just because the card did. Bringing an old receipt speeds it up.",
     "Come Records office with any ID and we go find you for system — your file no dey disappear just because "
     "the card lost. If you bring old receipt e go fast am.", _CTA_DESK),
    ("new_card", ["register as new patient", "get a hospital card"],
     "Welcome! Come to the Records desk with a valid ID; they'll register you and issue your hospital card "
     "and file number. It only takes a few minutes.",
     "Welcome! Come Records desk with valid ID; dem go register you and give you hospital card and file number. "
     "E no go take more than few minutes.", _CTA_DESK),
    ("copy_records", ["copy of my medical records", "request my file"],
     "You have every right to a copy of your own records. Put the request in writing at the Records desk "
     "with your ID — there may be a small copying charge, and it takes a few working days.",
     "You get right to collect copy of your own record. Put the request for writing for Records desk with your "
     "ID — small copying charge fit dey, and e dey take few working days.", _CTA_DESK),
    ("for_someone", ["records for my relative", "collect someone else's file"],
     "We can only release records to someone else with the patient's written permission, or where the law "
     "allows it. That rule protects your family's privacy too.",
     "We fit only release record to another person with the patient written permission, or where law allow am. "
     "That rule dey protect your family privacy too.", _CTA_DESK),
    ("privacy", ["who can see my file", "is my record confidential"],
     "Only the clinical team caring for you. Your record is confidential, access is controlled, and every "
     "look at it is logged.",
     "Na only the clinical team wey dey care for you. Your record na confidential, access dey controlled, and "
     "every time person open am, dem dey log am.", _CTA_HELP),
    ("correct", ["wrong details on my file", "correct my record", "wrong name"],
     "Please tell us and we'll correct it — wrong details on a medical file can cause real problems later. "
     "Bring your ID to the Records desk.",
     "Abeg tell us make we correct am — wrong detail for medical file fit cause real problem later. Bring your "
     "ID come Records desk.", _CTA_DESK),
    ("insurance", ["records for insurance", "report for my insurance"],
     "Yes, we can prepare reports for insurance or employers. Apply at the Records desk; it needs a doctor's "
     "input, so allow a few working days.",
     "Yes, we fit prepare report for insurance or employer. Apply for Records desk; e need doctor input, so "
     "allow few working days.", _CTA_DESK),
    ("sick_note", ["sick note", "medical certificate", "excuse duty"],
     "A medical certificate must come from the doctor who saw you — ask during your consultation. Records "
     "can print a copy afterwards if you lose it.",
     "Medical certificate must come from the doctor wey see you — ask am during your consultation. Records fit "
     "print copy after if you lose am.", _CTA_BOOK),
    ("court", ["records for court", "legal report", "police report"],
     "Legal and police requests follow a formal process to protect you. Bring the official request to the "
     "Records desk and they'll guide you through it.",
     "Legal and police request dey follow formal process to protect you. Bring the official request come Records "
     "desk and dem go guide you.", _CTA_DESK),
    ("old_file", ["my old file from years ago", "records from long ago"],
     "We keep records for many years. Give the Records desk your name, date of birth and roughly when you "
     "attended and they'll search for you.",
     "We dey keep record for plenty years. Give Records desk your name, date of birth and roughly when you come "
     "and dem go search for you.", _CTA_DESK),
    ("how_long_kept", ["how long do you keep records", "record retention"],
     "Records are kept for the period the law requires, then personal details are removed. Our privacy "
     "notice explains it in plain language.",
     "Dem dey keep record for the period wey law require, then dem go remove personal detail. Our privacy notice "
     "explain am for simple language.", "Tap 'Privacy' to read our notice."),
    ("delete", ["delete my data", "erase my records"],
     "You can ask, and we'll take it seriously. Some medical records must legally be kept for a period, but "
     "we'll explain exactly what we can and can't remove. Use the 'Your data rights' link on any page.",
     "You fit ask, and we go take am serious. Some medical record law say make we keep am for some period, but "
     "we go explain exactly wetin we fit and no fit remove. Use the 'Your data rights' link for any page.",
     "Tap 'Privacy' to make a data request."),
    ("hours", ["records office hours", "when is records open"],
     "The Records office runs during normal working hours on weekdays. For urgent needs out of hours, the "
     "ward or A&E team can access what's needed clinically.",
     "Records office dey run normal working hours for weekdays. For urgent need after hours, ward or A&E team fit "
     "access wetin dem need clinically.", _CTA_DESK),
    ("where", ["where is records office", "find medical records"],
     "The Records office is near the main reception — reception will point you or walk you there.",
     "Records office dey near main reception — reception go show you or waka with you.", _CTA_DESK),
    ("wait", ["records taking too long", "waiting for my file"],
     "I'm sorry about the wait. Files are sometimes with a clinic. Ask the Records desk to trace it, and if "
     "the wait is unreasonable please do tell us formally.",
     "Sorry for the wait. Sometimes file dey with clinic. Tell Records desk make dem trace am, and if the wait "
     "too much, abeg tell us formally.", _CTA_DESK),
    ("appointment_letter", ["copy of appointment letter", "lost appointment slip"],
     "No problem — Records or reception can reprint it. Bring your ID.",
     "No problem — Records or reception fit print am again. Bring your ID.", _CTA_DESK),
    ("transfer", ["transfer my records to another hospital", "referral letter"],
     "We can prepare a summary or referral letter for another hospital. Ask your doctor to request it, then "
     "collect it from Records.",
     "We fit prepare summary or referral letter for another hospital. Tell your doctor make e request am, then "
     "collect am for Records.", _CTA_DESK),
    ("digital", ["are records computerised", "electronic records"],
     "We keep both, and we're steadily moving more onto the system. Either way your file is available to the "
     "team treating you.",
     "We dey keep both, and we dey steadily move more enter system. Either way your file dey available to the "
     "team wey dey treat you.", _CTA_HELP),
    ("complaint", ["complain about records"],
     "Please tell us — it reaches management with a reference number.",
     "Abeg tell us — e dey reach management with reference number.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ FINANCE & ACCOUNTS
_d("Finance & Accounts", [
    ("what", ["finance department", "accounts office", "billing department"],
     "Finance & Accounts handles billing, payments and receipts. If you have a question about money, "
     "these are the people who can answer it properly — and they'd much rather explain than have you worry.",
     "Finance & Accounts dey handle billing, payment and receipt. If you get question about money, na dem fit "
     "answer am well — and dem prefer to explain than make you dey worry.", _CTA_DESK),
    ("pay", ["how do i pay", "payment methods", "can i pay with card"],
     "You can pay at the cash office by card, bank transfer or POS, and you'll always get a proper receipt. "
     "Please make sure you receive one, every time.",
     "You fit pay for cash office with card, bank transfer or POS, and dem go give you correct receipt always. "
     "Abeg make sure say you collect am every time.", _CTA_DESK),
    ("estimate", ["how much will it cost", "give me an estimate", "price"],
     "Ask the billing desk for a written estimate before treatment — they do this all day and they're happy "
     "to. It's much better to know in advance.",
     "Ask billing desk for written estimate before treatment — dem dey do am every day and dem dey happy to do "
     "am. E better make you know before.", _CTA_DESK),
    ("receipt", ["lost my receipt", "duplicate receipt"],
     "Come to the cash office with your file number and the rough date; they can look up the payment and "
     "reprint it.",
     "Come cash office with your file number and the rough date; dem fit find the payment and print am again.",
     _CTA_DESK),
    ("overcharge", ["i was overcharged", "wrong bill", "billing mistake"],
     "Please raise it — truly, and don't feel awkward about it. Take your receipt to the billing desk "
     "and ask them to review it. If we've made a mistake we'll correct it.",
     "Abeg raise am — for real, no feel shy. Carry your receipt go billing desk make dem review am. If we make "
     "mistake, we go correct am.", _CTA_DESK),
    ("nhis", ["do you accept nhis", "health insurance", "hmo"],
     "Ask the billing desk which schemes we currently accept and what your plan covers — bring your card so "
     "they can check it properly rather than guessing.",
     "Ask billing desk which scheme we dey accept now and wetin your plan cover — bring your card make dem check "
     "am well instead of guessing.", _CTA_DESK),
    ("instalment", ["can i pay in instalments", "payment plan", "i cannot afford"],
     "Please talk to the billing desk before you go without care. Ask about payment arrangements or any "
     "support available — that conversation is much better had early, and nobody will judge you.",
     "Abeg talk to billing desk before you go without treatment. Ask about payment arrangement or any support "
     "wey dey — better make you talk am early, and nobody go judge you.", _CTA_DESK),
    ("deposit", ["do i need a deposit", "advance payment"],
     "Some procedures and admissions need a deposit. Billing will tell you exactly how much and what it "
     "covers before anything starts.",
     "Some procedure and admission need deposit. Billing go tell you exactly how much and wetin e cover before "
     "anything start.", _CTA_DESK),
    ("refund", ["i want a refund", "refund my money"],
     "Refunds go through the accounts office. Bring your receipt and explain what happened; they'll check "
     "the record and process it if it's due.",
     "Refund dey go through accounts office. Bring your receipt and explain wetin happen; dem go check the "
     "record and process am if e due.", _CTA_DESK),
    ("free", ["is treatment free", "free healthcare"],
     "Some services under national programmes are free — immunisation, for instance. Billing will tell you "
     "clearly which is which, with no shuffling.",
     "Some service under national programme dey free — immunisation, for example. Billing go tell you clearly "
     "which one be which, no story.", _CTA_DESK),
    ("hours", ["cash office hours", "when can i pay"],
     "The cash office runs during working hours, and there's a duty arrangement for emergency admissions "
     "outside those hours — nobody is turned away in an emergency.",
     "Cash office dey run during working hours, and duty arrangement dey for emergency admission outside that "
     "time — dem no dey turn person away for emergency.", _CTA_DESK),
    ("bank", ["bank details", "transfer account number"],
     "Please only use the account details the cash office gives you in person or on an official receipt. "
     "Never pay into an account someone sends you by message — we will never ask you to do that.",
     "Abeg only use the account detail wey cash office give you face to face or for official receipt. Never pay "
     "enter account wey person send you for message — we no go ever ask you do that.", _CTA_DESK),
    ("scam", ["someone asked me to pay them", "is this payment genuine"],
     "Thank you for checking — that instinct is right. All payments go through the cash office and come "
     "with an official receipt. If someone asked you to pay them personally, please report it to us today.",
     "Thank you for checking — your instinct correct. All payment dey go through cash office and official "
     "receipt dey follow. If person ask you make you pay dem personally, abeg report am to us today.",
     "Tap 'Make a Complaint' to report it."),
    ("bill_explain", ["explain my bill", "what am i paying for"],
     "You're entitled to a clear breakdown — ask the billing desk to go through each line with you. Never "
     "feel awkward about asking; it's your money.",
     "You get right to clear breakdown — ask billing desk make dem go through each line with you. No feel shy "
     "to ask; na your money.", _CTA_DESK),
    ("discharge_bill", ["settle bill before discharge", "discharge payment"],
     "Bills are normally settled before discharge. If that's difficult, please speak to billing early rather "
     "than on the day — they have more options when there's time.",
     "Dem dey normally settle bill before discharge. If e hard, abeg talk to billing early instead of for the "
     "day — dem get more option when time dey.", _CTA_DESK),
    ("company", ["my employer will pay", "company cover"],
     "Bring the letter or authorisation from your employer to the billing desk before treatment so they can "
     "set it up properly.",
     "Bring the letter or authorisation from your employer come billing desk before treatment make dem set am up "
     "well.", _CTA_DESK),
    ("statement", ["statement of account", "history of my payments"],
     "The accounts office can print a statement of what you've paid. Bring your ID and file number.",
     "Accounts office fit print statement of wetin you don pay. Bring your ID and file number.", _CTA_DESK),
    ("where", ["where is the cash office", "find billing"],
     "The cash office and billing desk are near the main entrance — reception will point you there.",
     "Cash office and billing desk dey near the main entrance — reception go show you.", _CTA_DESK),
    ("emergency_pay", ["no money but it is an emergency"],
     "In a genuine emergency you will be attended to — please come in. Sort the paperwork afterwards with "
     "the billing desk; your life comes first.",
     "For real emergency dem go attend to you — abeg come. Sort the paperwork after with billing desk; your life "
     "come first.", "🚑 Please come in — you will be seen."),
    ("complaint", ["complain about billing"],
     "Please do — billing complaints matter and go straight to management with a reference number.",
     "Abeg do — billing complaint dey matter and e dey go straight to management with reference number.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ ADMINISTRATION & HR
_d("Administration & Human Resources", [
    ("what", ["admin department", "human resources", "hr office"],
     "Administration & HR looks after staffing, official letters, and the running of the hospital. For "
     "anything about your care, reception or the clinic is faster — but for official matters, this is us.",
     "Administration & HR dey handle staff matter, official letter, and how the hospital dey run. For anything "
     "about your treatment, reception or clinic go fast pass — but for official matter, na us.", _CTA_DESK),
    ("job", ["job vacancy", "i want to work here", "apply for a job", "recruitment"],
     "Vacancies are advertised officially — ask at the Admin office or watch our notice board and official "
     "channels. Please never pay anyone for a job here; genuine recruitment never costs you money.",
     "Dem dey advertise vacancy officially — ask for Admin office or check our notice board and official "
     "channel. Abeg never pay person for job here; correct recruitment no dey cost money.", _CTA_DESK),
    ("internship", ["internship", "housemanship", "student placement", "industrial training"],
     "Placements, housemanship and student attachments go through the Admin office. Bring a formal letter "
     "from your school or council.",
     "Placement, housemanship and student attachment dey go through Admin office. Bring formal letter from your "
     "school or council.", _CTA_DESK),
    ("letter", ["official letter", "letter from the hospital", "confirmation letter"],
     "Apply at the Admin office and explain what the letter is for. Bring your ID; most letters take a few "
     "working days.",
     "Apply for Admin office and explain wetin the letter be for. Bring your ID; most letter dey take few "
     "working days.", _CTA_DESK),
    ("staff_complaint", ["complain about a staff member", "staff behaviour"],
     "I'm sorry that happened. You can report it through the complaint form — and you may submit it "
     "anonymously if you'd prefer. It goes to management either way, and it's taken seriously.",
     "Sorry say e happen. You fit report am through complaint form — and you fit send am anonymous if you prefer. "
     "E dey go management either way, and dem dey take am serious.",
     "Tap 'Make a Complaint' — you can stay anonymous."),
    ("visit_management", ["i want to see the md", "meet management", "see the director"],
     "Ask at the Admin office and they'll advise on the process and arrange an appointment where "
     "appropriate. Management do want to hear from patients.",
     "Ask for Admin office and dem go advise you on the process and arrange appointment where e fit. Management "
     "really wan hear from patient.", _CTA_DESK),
    ("partnership", ["partnership", "donate to the hospital", "sponsorship", "ngo"],
     "That's very kind — thank you. Please speak to the Admin office; they handle partnerships, donations "
     "and formal agreements.",
     "Na kind thing — thank you. Abeg talk to Admin office; dem dey handle partnership, donation and formal "
     "agreement.", _CTA_DESK),
    ("hours", ["admin office hours"],
     "The Admin office runs during normal working hours on weekdays.",
     "Admin office dey run normal working hours for weekdays.", _CTA_DESK),
    ("verify_staff", ["is this person a staff member", "verify identity"],
     "Good question to ask. All staff carry official identification — ask to see it, and check with the "
     "Admin office or reception if anything feels wrong. You're never being rude by checking.",
     "Correct question. All staff dey carry official ID — ask make dem show you, and check with Admin office or "
     "reception if anything no correct. You no dey rude by checking.", _CTA_DESK),
    ("records_link", ["hr records", "my employment record"],
     "Employment records are held by HR at the Admin office — that's separate from patient medical records.",
     "HR dey keep employment record for Admin office — e different from patient medical record.", _CTA_DESK),
    ("training", ["staff training", "cpd", "workshop"],
     "Training and development are coordinated through Admin and the Director of Clinical Services & "
     "Training. Ask at the Admin office.",
     "Training and development dey coordinated through Admin and the Director of Clinical Services & Training. "
     "Ask for Admin office.", _CTA_DESK),
    ("suggestion", ["i have a suggestion", "idea to improve the hospital"],
     "We'd really like to hear it — good ideas often come from patients and visitors. Use the feedback "
     "form or drop it at the Admin office.",
     "We really wan hear am — good idea plenty times dey come from patient and visitor. Use the feedback form or "
     "drop am for Admin office.", "Tap 'Feedback' to share it."),
    ("volunteer", ["volunteer", "i want to help"],
     "How kind — thank you. Speak to the Admin office about volunteering opportunities.",
     "You too kind — thank you. Talk to Admin office about volunteer opportunity.", _CTA_DESK),
    ("id_card", ["staff id card", "replace my id"],
     "Staff ID cards — new ones and replacements — are handled by HR at the Admin office. "
     "Bring a passport photograph and your staff details.",
     "Staff ID card — new one and replacement — na HR for Admin office dey handle am. Bring "
     "passport photograph and your staff detail.", _CTA_DESK),
    ("leave", ["apply for leave", "annual leave"],
     "Leave applications go through your head of department and then HR. Ask at the Admin office for the "
     "current form.",
     "Leave application dey go through your head of department then HR. Ask for Admin office for the current "
     "form.", _CTA_DESK),
    ("salary", ["salary query", "payslip"],
     "Salary and payslip queries are handled by HR together with Finance. Start at the Admin office.",
     "Salary and payslip query, na HR with Finance dey handle am. Start from Admin office.", _CTA_DESK),
    ("policy", ["hospital policy", "rules"],
     "Ask the Admin office for the policy you need — they'll either give you a copy or point you to it.",
     "Ask Admin office for the policy wey you need — dem go give you copy or show you where e dey.", _CTA_DESK),
    ("media", ["press enquiry", "journalist", "interview"],
     "Media enquiries go through Public Affairs and the Admin office. Please don't film patients or staff "
     "without permission.",
     "Media enquiry dey go through Public Affairs and Admin office. Abeg no film patient or staff without "
     "permission.", _CTA_DESK),
    ("where", ["where is the admin office"],
     "The Admin office is in the administrative block — reception will direct you.",
     "Admin office dey the administrative block — reception go direct you.", _CTA_DESK),
    ("complaint", ["complain to administration"],
     "Please file it — it reaches management directly and you'll get a reference number to track it.",
     "Abeg file am — e dey reach management direct and you go get reference number to track am.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ ENVIRONMENTAL HEALTH
_d("Environmental Health", [
    ("what", ["environmental health", "sanitation department", "cleaning department"],
     "Environmental Health keeps the hospital clean, safe and hygienic — cleaning services, waste "
     "management and sanitation. Quietly, it's one of the most important teams for your safety here.",
     "Environmental Health dey keep the hospital clean, safe and hygienic — cleaning service, waste management "
     "and sanitation. Quietly, na one of the most important team for your safety here.", _CTA_DESK),
    ("dirty", ["the toilet is dirty", "this area is not clean", "report dirty ward",
               "the ward is dirty", "ward is dirty", "the place is dirty", "it is dirty here",
               "room is dirty", "not clean", "dirty", "needs cleaning", "no one has cleaned"],
     "Thank you for telling us — please do, we truly want to know. Tell any staff member or reception "
     "and the cleaning team will be sent. You can also file it formally if it keeps happening.",
     "Thank you for telling us — abeg do, we really wan know. Tell any staff or reception and dem go send the "
     "cleaning team. You fit file am formally too if e dey happen again and again.",
     "Tap 'Make a Complaint' if it keeps happening."),
    ("toilet", ["where is the toilet", "restroom", "bathroom"],
     "There are toilets on each floor and near the main waiting areas — any staff member will point you to "
     "the nearest one.",
     "Toilet dey every floor and near the main waiting area — any staff go show you the nearest one.", _CTA_DESK),
    ("waste", ["waste disposal", "where do i throw rubbish", "bin"],
     "Please use the bins provided — and note the colour coding, because medical waste is separated for "
     "everyone's safety. If you can't find a bin, any staff member will help.",
     "Abeg use the bin wey dem provide — and notice the colour, because dem dey separate medical waste for "
     "everybody safety. If you no see bin, any staff go help you.", _CTA_DESK),
    ("sharps", ["needle on the floor", "sharps", "found a syringe"],
     "Please don't touch it — tell a staff member immediately and they'll deal with it safely. Thank you "
     "for spotting it.",
     "Abeg no touch am — tell staff sharp sharp and dem go handle am safely. Thank you say you notice am.",
     "🚑 Tell the nearest staff member now."),
    ("water", ["drinking water", "is the water safe"],
     "Ask staff where the drinking water points are. If you're ever unsure about water safety, ask — never "
     "guess.",
     "Ask staff where the drinking water point dey. If you no sure about water safety, ask — no guess.", _CTA_DESK),
    ("pest", ["mosquitoes", "rats", "pest problem"],
     "Please report it to any staff member or the Environmental Health desk — we'd rather know early. "
     "It'll be dealt with.",
     "Abeg report am to any staff or Environmental Health desk — we prefer to know early. Dem go handle am.",
     _CTA_DESK),
    ("smell", ["bad smell", "odour"],
     "Please tell us where — a bad smell usually means something needs attention, and we'd want to find it "
     "quickly.",
     "Abeg tell us where — bad smell usually mean say something need attention, and we go wan find am quick.",
     _CTA_DESK),
    ("smoking", ["can i smoke", "smoking area"],
     "The hospital is a no-smoking environment, for everyone's health — including patients with breathing "
     "problems. Thank you for respecting that.",
     "The hospital na no-smoking place, for everybody health — including patient wey get breathing problem. "
     "Thank you say you respect am.", _CTA_HELP),
    ("infection", ["infection control", "hand washing", "sanitiser"],
     "Hand hygiene points are placed around the hospital, and please do use them — it's the single most "
     "effective thing any of us can do to stop infection spreading.",
     "Hand hygiene point dey around the hospital, and abeg use dem — na the single most effective thing wey any "
     "of us fit do to stop infection from spreading.", _CTA_HELP),
    ("cleaning_schedule", ["how often do you clean", "cleaning schedule"],
     "Patient areas are cleaned on a regular daily schedule, with extra attention where it's needed. If an "
     "area has been missed, please tell us.",
     "Dem dey clean patient area on regular daily schedule, with extra attention where e need am. If dem miss "
     "any area, abeg tell us.", _CTA_DESK),
    ("linen", ["dirty bed sheet", "change my linen"],
     "Tell the ward nurse and the linen will be changed. You should never have to sleep on soiled bedding "
     "— please do speak up.",
     "Tell the ward nurse and dem go change the linen. You no suppose sleep on dirty bedding — abeg talk.",
     _CTA_DESK),
    ("food_hygiene", ["is the food hygienic", "kitchen cleanliness"],
     "Our Catering and Environmental Health teams work together on food hygiene. If something isn't right "
     "with a meal, please report it the same day.",
     "Our Catering and Environmental Health team dey work together on food hygiene. If something no correct with "
     "food, abeg report am same day.", _CTA_DESK),
    ("visitors", ["visitor hygiene", "should i wear a mask"],
     "Follow the signs and what staff ask of you — masks are sometimes required in certain areas. Clean "
     "your hands on the way in and on the way out.",
     "Follow the sign and wetin staff talk — sometimes mask dey required for some area. Clean your hand when "
     "you dey enter and when you dey comot.", _CTA_HELP),
    ("report_anon", ["report cleanliness anonymously"],
     "Yes — you can submit a complaint anonymously; no phone number is stored. It still reaches management.",
     "Yes — you fit submit complaint anonymous; dem no go store any phone number. E still dey reach management.",
     "Tap 'Make a Complaint' and tick anonymous."),
    ("hours", ["environmental health hours"],
     "Cleaning teams work throughout the day, with cover for urgent needs at any hour.",
     "Cleaning team dey work throughout the day, and cover dey for urgent need any time.", _CTA_DESK),
    ("outside", ["hospital grounds dirty", "compound"],
     "The grounds are part of our remit too. Tell us what you saw and where, and we'll get it sorted.",
     "The compound dey under us too. Tell us wetin you see and where, and we go sort am.", _CTA_DESK),
    ("safety", ["broken step", "slippery floor", "safety hazard"],
     "Please report that immediately to any staff member — a slippery floor or broken step can hurt "
     "someone. Thank you for looking out for others.",
     "Abeg report am immediately to any staff — slippery floor or broken step fit injure person. Thank you say "
     "you dey look out for other people.", _CTA_DESK),
    ("where", ["where is environmental health"],
     "Ask at reception and they'll point you to the Environmental Health desk.",
     "Ask for reception and dem go show you Environmental Health desk.", _CTA_DESK),
    ("complaint", ["complain about cleanliness"],
     "Please do — cleanliness complaints are taken seriously and go straight to management.",
     "Abeg do — cleanliness complaint dey serious and e dey go straight to management.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ ICT
_d("ICT", [
    ("what", ["ict department", "it department", "computer department"],
     "ICT keeps the hospital's systems running — including this assistant you're talking to now. For "
     "anything about your care, reception is faster.",
     "ICT dey keep the hospital system dey run — including this assistant wey you dey talk to now. For anything "
     "about your treatment, reception go fast pass.", _CTA_DESK),
    ("website_problem", ["the website is not working", "app not loading", "site is down"],
     "I'm sorry about that. Try refreshing, or switch between wifi and mobile data. If it keeps failing, "
     "please tell reception so ICT can look — and remember you can always just call or walk in.",
     "Sorry about am. Try refresh, or change between wifi and mobile data. If e still dey fail, tell reception "
     "make ICT check am — and remember say you fit just call or waka come.", _CTA_DESK),
    ("booking_failed", ["my booking did not go through", "error when booking"],
     "Let's sort that out. Check whether you got a reference number — if you did, the booking exists. If "
     "not, try again or call the help desk and we'll book you over the phone.",
     "Make we sort am. Check whether you get reference number — if you get am, the booking dey. If no, try again "
     "or call help desk make we book you for phone.", _CTA_BOOK),
    ("no_sms", ["i did not get the sms", "no text message"],
     "Check the number you entered was right, and look in your spam or blocked messages. If it still hasn't "
     "arrived, your reference number works on its own — you don't need the text.",
     "Check say the number wey you enter correct, and look your spam or blocked message. If e still no come, your "
     "reference number dey work by itself — you no need the text.", _CTA_HELP),
    ("data", ["does this use my data", "is it free to use"],
     "The pages are kept deliberately light so they work on a weak signal and use very little data. There's "
     "no charge to use them.",
     "We make the page light on purpose so e go work for weak network and e no dey chop data. No charge to use "
     "am.", _CTA_HELP),
    ("privacy", ["is my information safe online", "data security"],
     "Yes — the connection is encrypted, access is role-controlled, and we never sell your data. Our privacy "
     "notice explains it in plain language.",
     "Yes — the connection dey encrypted, access dey controlled by role, and we no dey sell your data. Our privacy "
     "notice explain am for simple language.", "Tap 'Privacy' to read it."),
    ("password", ["forgot my password", "reset password"],
     "If you're a staff member, use 'Forgot password' on the login page — it sends a code to your phone. "
     "Patients don't need an account at all.",
     "If you be staff, use 'Forgot password' for login page — e go send code to your phone. Patient no need "
     "account at all.", _CTA_HELP),
    ("wifi", ["is there wifi", "guest wifi"],
     "Ask at reception about visitor wifi — availability varies by area. The patient pages are "
     "built to be very light, so they work fine on mobile data too.",
     "Ask for reception about visitor wifi — e no dey everywhere. But the patient page light well "
     "well, so e dey work fine even for mobile data.", _CTA_DESK),
    ("slow", ["the site is slow"],
     "Sorry about that. It's usually the network — try again in a moment. If it's persistently slow, please "
     "tell us so ICT can investigate.",
     "Sorry about am. Na usually network — try again small time. If e dey slow always, abeg tell us make ICT "
     "check am.", _CTA_DESK),
    ("qr", ["qr code not working", "cannot scan the code"],
     "Try holding the phone steadier and a little further back, in better light. If it still won't scan, you "
     "can just type the address in your browser or ask reception.",
     "Try hold the phone steady and small far back, for better light. If e still no scan, you fit just type the "
     "address for your browser or ask reception.", _CTA_HELP),
    ("wrong_info", ["wrong information on the website"],
     "Thank you for spotting that — please tell us exactly what's wrong and we'll get it corrected.",
     "Thank you say you notice am — abeg tell us exactly wetin no correct and we go correct am.", _CTA_DESK),
    ("language", ["change language", "can i use yoruba"],
     "Yes — tap the language buttons at the top of any patient page for English, Yorùbá, Hausa or Igbo.",
     "Yes — tap the language button for top of any patient page for English, Yorùbá, Hausa or Igbo.", _CTA_HELP),
    ("voice", ["the microphone is not working", "voice typing"],
     "Voice typing needs microphone permission and an internet connection. Check your browser allowed the "
     "microphone. You can always type instead — nothing is lost.",
     "Voice typing need microphone permission and internet. Check say your browser allow the microphone. You fit "
     "always type instead — nothing go lost.", _CTA_HELP),
    ("device", ["works on my phone", "which browser"],
     "It's built to work on ordinary phones and older browsers. If something looks broken on yours, please "
     "tell us which phone and browser — that really helps us fix it.",
     "We build am to work for normal phone and old browser. If something look broken for your own, abeg tell us "
     "which phone and browser — e go really help us fix am.", _CTA_DESK),
    ("printer", ["printer not working", "cannot print"],
     "That's an internal ICT matter — please ask a staff member to log it with ICT.",
     "Na internal ICT matter — abeg tell staff make dem log am with ICT.", _CTA_DESK),
    ("system_down", ["the hospital system is down"],
     "If our systems are having trouble, staff switch to paper so your care continues without interruption. "
     "Please be patient with them — nothing about your treatment stops.",
     "If our system get problem, staff dey switch to paper so your treatment go continue without stopping. Abeg "
     "exercise patience with dem — nothing about your treatment go stop.", _CTA_HELP),
    ("phishing", ["suspicious message from the hospital", "is this text real"],
     "Good instinct. We never ask for your password or for payment into a personal account by message. If "
     "something feels off, call the help desk before acting on it.",
     "Correct instinct. We no dey ask for your password or payment enter personal account through message. If "
     "something no correct, call help desk before you do anything.", _CTA_DESK),
    ("suggestion", ["suggest a feature", "the app should have"],
     "We'd love to hear it — this system actually improves from patient suggestions. Use the feedback form.",
     "We go like to hear am — this system dey really improve from patient suggestion. Use the feedback form.",
     "Tap 'Feedback' to tell us."),
    ("where", ["where is ict"],
     "The ICT unit is inside the administrative block — reception will direct you.",
     "ICT unit dey inside administrative block — reception go direct you.", _CTA_DESK),
    ("complaint", ["complain about the system"],
     "Please do — technical complaints help us fix things for everyone.",
     "Abeg do — technical complaint dey help us fix thing for everybody.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ ENGINEERING & MAINTENANCE
_d("Engineering & Maintenance", [
    ("what", ["engineering department", "maintenance department"],
     "Engineering & Maintenance keeps the building, power, water and medical equipment working — "
     "electrical, plumbing and biomedical. When the lights stay on and the equipment works, that's them.",
     "Engineering & Maintenance dey keep the building, light, water and medical equipment dey work — "
     "electrical, plumbing and biomedical. When light dey and equipment dey work, na dem.", _CTA_DESK),
    ("report_fault", ["report a fault", "something is broken", "report a problem"],
     "Please tell any staff member or reception and it'll be logged for the maintenance team. Say exactly "
     "where it is — that gets it fixed faster.",
     "Abeg tell any staff or reception and dem go log am for maintenance team. Talk exactly where e dey — e go "
     "make dem fix am fast.", _CTA_DESK),
    ("power", ["no light", "power outage", "generator"],
     "We have backup power for clinical areas, so care continues. If the lights are out where you are, "
     "please tell a staff member.",
     "We get backup power for clinical area, so treatment dey continue. If light no dey where you dey, abeg tell "
     "staff.", _CTA_DESK),
    ("water", ["no water", "tap not running"],
     "Please report it to reception or any staff member — it'll go straight to the plumbing team.",
     "Abeg report am to reception or any staff — e go go straight to plumbing team.", _CTA_DESK),
    ("ac", ["air conditioning not working", "too hot", "fan not working"],
     "Sorry about the discomfort. Tell the ward staff or reception and maintenance will attend to it.",
     "Sorry for the discomfort. Tell ward staff or reception and maintenance go attend to am.", _CTA_DESK),
    ("lift", ["lift not working", "elevator"],
     "Please tell reception. If you have difficulty with stairs, tell them too and staff will find another "
     "way to get you where you need to be.",
     "Abeg tell reception. If stairs dey hard for you, tell dem too and staff go find another way to carry you "
     "reach where you dey go.", _CTA_DESK),
    ("equipment", ["machine not working", "equipment broken", "scanner down"],
     "Biomedical engineers look after medical equipment and respond urgently to clinical faults. Staff will "
     "tell you if a service is affected and what the alternative is.",
     "Biomedical engineer dey look after medical equipment and dem dey respond urgent to clinical fault. Staff go "
     "tell you if any service affected and wetin be the alternative.", _CTA_DESK),
    ("light", ["bulb not working", "dark corridor"],
     "Please report it — a dark corridor is a safety issue and we'd want to fix it today.",
     "Abeg report am — dark corridor na safety issue and we go wan fix am today.", _CTA_DESK),
    ("door", ["door broken", "lock not working"],
     "Report it to reception and maintenance will attend. If it's a security concern, say so — that raises "
     "the priority.",
     "Report am to reception and maintenance go attend. If na security matter, talk am — e go raise the priority.",
     _CTA_DESK),
    ("noise", ["construction noise", "drilling"],
     "We're sorry — maintenance work is sometimes unavoidable, and we try to schedule it away from rest "
     "periods. Tell the ward staff if it's disturbing a patient who's unwell.",
     "We sorry — maintenance work dey sometimes necessary, and we dey try schedule am away from rest time. Tell "
     "ward staff if e dey disturb patient wey no well.", _CTA_DESK),
    ("oxygen", ["oxygen supply", "oxygen not working"],
     "Oxygen systems are maintained as a top clinical priority. If there's any concern, tell the nurse "
     "immediately — do not wait.",
     "Dem dey maintain oxygen system as top clinical priority. If any concern dey, tell nurse immediately — no "
     "wait.", "🚑 Tell the nurse immediately."),
    ("wheelchair", ["broken wheelchair", "need a wheelchair"],
     "Ask at reception — they'll find you a working one and log the broken one for repair.",
     "Ask for reception — dem go find you one wey dey work and log the broken one for repair.", _CTA_DESK),
    ("bed", ["bed is broken", "bed not adjusting"],
     "Tell the ward nurse; maintenance handle bed repairs and can usually swap it out quickly.",
     "Tell ward nurse; maintenance dey handle bed repair and dem fit change am quick.", _CTA_DESK),
    ("hours", ["maintenance hours"],
     "The maintenance team works through the day with an on-call arrangement for urgent faults at night.",
     "Maintenance team dey work through the day and on-call arrangement dey for urgent fault for night.",
     _CTA_DESK),
    ("vendor", ["i supply equipment", "contractor", "vendor"],
     "Suppliers and contractors should go through the Admin office, not directly to departments.",
     "Supplier and contractor suppose go through Admin office, no be direct to department.", _CTA_DESK),
    ("safety", ["exposed wire", "electrical hazard"],
     "Please don't touch it — tell a staff member immediately. That's urgent and they'll treat it as such.",
     "Abeg no touch am — tell staff immediately. Na urgent and dem go treat am so.", "🚑 Tell staff now."),
    ("generator_noise", ["generator too loud"],
     "Thank you for telling us — please report where you are and we'll see what can be done.",
     "Thank you for telling us — abeg report where you dey and we go see wetin we fit do.", _CTA_DESK),
    ("waste_link", ["drainage", "blocked drain"],
     "Report it to reception; plumbing and Environmental Health will handle it together.",
     "Report am to reception; plumbing and Environmental Health go handle am together.", _CTA_DESK),
    ("where", ["where is the maintenance office"],
     "Ask at reception — they'll direct you or log the issue for you, which is usually quicker.",
     "Ask for reception — dem go direct you or log the issue for you, wey usually faster.", _CTA_DESK),
    ("complaint", ["complain about facilities"],
     "Please do — facility complaints go to management and help us prioritise repairs.",
     "Abeg do — facility complaint dey go management and e dey help us prioritise repair.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ SECURITY
_d("Security", [
    ("what", ["security department", "hospital security"],
     "Our Security team keeps patients, visitors and staff safe, manages the gate and helps with parking "
     "and lost property. If you feel unsafe at any point, find them or any staff member.",
     "Our Security team dey keep patient, visitor and staff safe, dem dey manage gate and dem dey help with "
     "parking and lost property. If you no feel safe any time, find dem or any staff.", _CTA_DESK),
    ("unsafe", ["i feel unsafe", "someone is threatening me", "harassment"],
     "Please find the nearest staff member or security officer right now — don't wait, and don't handle it "
     "alone. Your safety comes first and you will be taken seriously.",
     "Abeg find the nearest staff or security officer now now — no wait, and no handle am alone. Your safety come "
     "first and dem go take you serious.", "🚨 Find the nearest staff member now."),
    ("lost", ["lost property", "i lost my phone", "lost my bag"],
     "Report it to the Security post as soon as you can, with a description and roughly where you were. "
     "Things are handed in more often than people expect.",
     "Report am to Security post quick, with description and roughly where you dey. People dey submit lost item "
     "pass wetin you think.", _CTA_DESK),
    ("found", ["i found something", "hand in lost item"],
     "Thank you — please hand it in at the Security post so we can return it to whoever lost it.",
     "Thank you — abeg submit am for Security post make we fit return am to the owner.", _CTA_DESK),
    ("parking", ["where can i park", "parking"],
     "Parking is at the main compound — the gate officers will direct you. Please keep the ambulance route "
     "clear at all times.",
     "Parking dey the main compound — gate officer go direct you. Abeg keep the ambulance route clear all the "
     "time.", _CTA_DESK),
    ("visiting", ["visiting hours", "can i visit a patient"],
     "Visiting runs in set afternoon and evening slots — check with the ward, as some units differ. Please "
     "keep numbers small so patients can rest.",
     "Visiting dey run for afternoon and evening slot — check with the ward, because some unit different. Abeg "
     "make una no plenty so patient fit rest.", _CTA_DESK),
    ("id", ["do i need id to enter", "visitor pass"],
     "You may be asked for ID at the gate — please carry one. It's there to keep patients safe.",
     "Dem fit ask you for ID for gate — abeg carry one. Na to keep patient safe.", _CTA_DESK),
    ("night", ["visiting at night", "come at night"],
     "Emergencies are attended to at any hour of the night. General visiting is limited after hours so "
     "patients can rest.",
     "Dem dey attend to emergency any time for night. But general visiting dey limited after hours so patient fit "
     "rest.", _CTA_DESK),
    ("ambulance", ["ambulance access", "emergency entrance"],
     "The emergency entrance is kept clear for ambulances at all times. If you're bringing someone in "
     "urgently, drive to that entrance and call for help.",
     "Emergency entrance dey always clear for ambulance. If you dey bring person come urgent, drive go that "
     "entrance and shout for help.", "🚑 Use the emergency entrance."),
    ("theft", ["something was stolen", "report theft"],
     "I'm sorry that happened. Report it to Security immediately and file a complaint as well so management "
     "sees it. Both matter.",
     "Sorry say e happen. Report am to Security immediately and file complaint too make management see am. The "
     "two dey important.", "Tap 'Make a Complaint' as well."),
    ("child", ["lost child", "cannot find my child"],
     "Tell the nearest staff member or Security immediately — right now. They will help you search straight "
     "away.",
     "Tell the nearest staff or Security immediately — now now. Dem go help you search sharp sharp.",
     "🚨 Tell staff immediately."),
    ("photos", ["can i take photos", "filming in the hospital"],
     "Please don't photograph or film patients or staff without permission — other people's privacy matters "
     "as much as yours. Ask the Admin office if you need to.",
     "Abeg no snap or film patient or staff without permission — other people privacy dey important like your own. "
     "Ask Admin office if you need to.", _CTA_DESK),
    ("weapon", ["can i bring", "prohibited items"],
     "Weapons and dangerous items are not permitted anywhere on hospital premises. Security will advise at "
     "the gate.",
     "Weapon and dangerous item no dey allowed anywhere for hospital premises. Security go advise for gate.",
     _CTA_DESK),
    ("gate", ["what time does the gate close"],
     "The gate is manned around the clock for emergencies. Ask the gate officers about routine access times.",
     "Gate get person 24 hours for emergency. Ask the gate officer about normal access time.", _CTA_DESK),
    ("escort", ["can someone walk me to my car", "escort at night"],
     "Yes — just ask Security. They'd far rather walk with you than have you feel uneasy.",
     "Yes — just ask Security. Dem prefer to waka with you than make you dey uncomfortable.", _CTA_DESK),
    ("crowd", ["too many people", "crowd control"],
     "Security manage waiting areas to keep them safe and calm. Please follow their directions — it's for "
     "everyone's benefit.",
     "Security dey manage waiting area make e safe and calm. Abeg follow dem direction — na for everybody good.",
     _CTA_DESK),
    ("staff_conduct", ["security officer was rude"],
     "I'm sorry — that's not the standard expected. Please report it; it goes to management with a reference "
     "number.",
     "Sorry — that no be the standard wey we expect. Abeg report am; e dey go management with reference number.",
     "Tap 'Make a Complaint' and open Make a complaint."),
    ("emergency_number", ["emergency contact", "who do i call"],
     "In an emergency, come straight to Accident & Emergency or call the hospital help desk number shown at "
     "the bottom of this page.",
     "For emergency, come straight to Accident & Emergency or call the hospital help desk number wey dey for "
     "bottom of this page.", "🚑 A&E is open day and night."),
    ("where", ["where is the security post"],
     "The Security post is at the main gate, and it is manned at all hours. If you need help "
     "finding anything or anyone, they are a good first stop.",
     "Security post dey the main gate, and person dey there all hours. If you need help to find "
     "anything or anybody, na good place to start.", _CTA_DESK),
    ("complaint", ["complain about security"],
     "Please file it — security concerns reach management directly, and you'll get a reference "
     "number so you can follow up on what was done.",
     "Abeg file am — security matter dey reach management direct, and you go get reference number "
     "so you fit follow up wetin dem do.", "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ SMALLER SUPPORT UNITS
_d("Internal Audit", [
    ("what", ["internal audit", "audit department"],
     "Internal Audit checks that hospital money and processes are handled correctly. For patients, the "
     "billing desk is usually the right place — but if you suspect something improper, Audit want to know.",
     "Internal Audit dey check say hospital money and process dey handled correctly. For patient, billing desk "
     "na usually the right place — but if you suspect say something no correct, Audit wan know.", _CTA_DESK),
    ("report_fraud", ["report fraud", "someone asked for a bribe", "extortion", "bribe",
                      "report a bribe", "asked me for money", "demanded money", "corruption",
                      "staff collected money", "illegal payment"],
     "Thank you for speaking up — that takes courage and it truly helps the hospital. Report it through "
     "the complaint form; you can do so ANONYMOUSLY, and it reaches management and Audit directly.",
     "Thank you say you talk — e need courage and e dey really help the hospital. Report am through complaint "
     "form; you fit do am ANONYMOUS, and e dey reach management and Audit direct.",
     "Tap 'Make a Complaint' and tick anonymous."),
    ("payment_person", ["staff asked me to pay them directly"],
     "Please don't pay. All payments go through the cash office with an official receipt. Report this today "
     "— anonymously if you prefer.",
     "Abeg no pay. All payment dey go through cash office with official receipt. Report am today — anonymous if "
     "you prefer.", "Tap 'Make a Complaint' and tick anonymous."),
    ("receipt_check", ["is my receipt genuine"],
     "Take it to the cash office or Audit and ask them to verify it. Nobody will mind you checking.",
     "Carry am go cash office or Audit make dem verify am. Nobody go vex say you check.", _CTA_DESK),
    ("where", ["where is internal audit"],
     "The Audit unit is in the administrative block — reception will direct you.",
     "Audit unit dey administrative block — reception go direct you.", _CTA_DESK),
    ("hours", ["audit office hours"],
     "The Audit unit works normal office hours on weekdays. If your concern is urgent or sensitive, "
     "the complaint form reaches them at any hour — and you may stay anonymous.",
     "Audit unit dey work normal office hours for weekdays. If your matter urgent or sensitive, the "
     "complaint form dey reach dem any time — and you fit stay anonymous.", _CTA_DESK),
    ("anonymous", ["can i report anonymously"],
     "Yes, absolutely. Tick 'Submit anonymously' on the complaint form and no phone number is stored at all.",
     "Yes, for sure. Tick 'Submit anonymously' for the complaint form and dem no go store any phone number.",
     "Tap 'Make a Complaint' and tick anonymous."),
    ("protection", ["will they know it was me", "am i protected"],
     "If you submit anonymously we hold no contact details, so nobody can trace it back to you. Reports are "
     "handled by management, not by the department complained about.",
     "If you submit anonymous, we no dey hold any contact detail, so nobody fit trace am back to you. Management "
     "dey handle report, no be the department wey you complain about.", _CTA_HELP),
    ("complaint", ["complain to audit"],
     "Use the complaint form — it reaches management and Audit with a reference number.",
     "Use the complaint form — e dey reach management and Audit with reference number.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

_d("Planning, Research & Statistics", [
    ("what", ["planning department", "research and statistics"],
     "Planning, Research & Statistics turns hospital data into better services — tracking how long people "
     "wait, what patients need most, and where to improve.",
     "Planning, Research & Statistics dey turn hospital data into better service — dem dey track how long people "
     "dey wait, wetin patient need pass, and where to improve.", _CTA_DESK),
    ("research", ["can i do research here", "student research", "data request"],
     "Research requests go through the Admin office and this unit, with a formal letter from your "
     "institution and the necessary approvals.",
     "Research request dey go through Admin office and this unit, with formal letter from your school and the "
     "necessary approval.", _CTA_DESK),
    ("statistics", ["hospital statistics", "how many patients"],
     "Aggregate statistics are available through official request — individual patient data never is.",
     "Aggregate statistics dey available through official request — individual patient data no dey available at "
     "all.", _CTA_DESK),
    ("survey", ["patient survey", "can i give feedback"],
     "Yes please — your feedback directly shapes what we improve. It takes about ten seconds.",
     "Yes abeg — your feedback dey really shape wetin we go improve. E no go take pass ten seconds.",
     "Tap 'Feedback' to rate your visit."),
    ("my_data", ["is my data used for research"],
     "Only in anonymous, aggregated form — never in a way that identifies you. Our privacy notice explains it.",
     "Na only for anonymous, aggregate form — never for way wey go identify you. Our privacy notice explain am.",
     "Tap 'Privacy' to read it."),
    ("where", ["where is planning unit"],
     "The Planning unit is in the administrative block — reception will point you there. For most "
     "patient matters, though, reception or the clinic will help you faster.",
     "Planning unit dey administrative block — reception go show you. But for most patient matter, "
     "reception or clinic go help you faster.", _CTA_DESK),
    ("complaint", ["complain to planning"],
     "Use the complaint form — it reaches management with a reference number, and the data helps "
     "this team see patterns and fix the underlying cause, not just your case.",
     "Use the complaint form — e dey reach management with reference number, and the data dey help "
     "this team see pattern and fix the root cause, no be only your own case.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

_d("Public Affairs", [
    ("what", ["public affairs", "public relations", "enquiries desk"],
     "Public Affairs is the hospital's front door for enquiries, information and community relations. If "
     "you're not sure who to ask, ask them.",
     "Public Affairs na the hospital front door for enquiry, information and community relation. If you no sure "
     "who to ask, ask dem.", _CTA_DESK),
    ("enquiry", ["general enquiry", "i have a question"],
     "Ask away — the enquiries desk is exactly for this, and no question is too small.",
     "Ask am — the enquiry desk na exactly for this, and no question too small.", _CTA_DESK),
    ("media", ["press", "journalist", "media enquiry"],
     "Media enquiries go through Public Affairs. Please don't film patients or staff without permission.",
     "Media enquiry dey go through Public Affairs. Abeg no film patient or staff without permission.", _CTA_DESK),
    ("event", ["hospital event", "open day", "health fair"],
     "Ask Public Affairs what's coming up — we'd be glad to see you there.",
     "Ask Public Affairs wetin dey come — we go happy to see you there.", _CTA_DESK),
    ("thanks", ["i want to thank the staff", "commend a nurse", "praise"],
     "That would make someone's week — thank you. Leave it as feedback with the person's name and "
     "we'll make sure they and their head of department hear it.",
     "That one go really sweet person belle — thank you. Leave am as feedback with the person name and we go make "
     "sure say dem and dem head of department hear am.", "Tap 'Feedback' to send your praise."),
    ("info", ["information about the hospital", "about us"],
     "Public Affairs can tell you about our services, departments and how to access them. Reception has "
     "leaflets too.",
     "Public Affairs fit tell you about our service, department and how to access dem. Reception get leaflet too.",
     _CTA_DESK),
    ("where", ["where is public affairs"],
     "Public Affairs sits near the main reception, and they are always happy to help you find "
     "whoever or whatever you need. If you are unsure who to ask, start there.",
     "Public Affairs dey near the main reception, and dem dey really happy to help you find whoever "
     "or whatever you need. If you no sure who to ask, start from there.", _CTA_DESK),
    ("complaint", ["complain to public affairs"],
     "Please file it through the complaint form so it's tracked properly with a reference number.",
     "Abeg file am through complaint form make dem track am well with reference number.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

_d("Laundry", [
    ("what", ["laundry department", "hospital laundry"],
     "Our Laundry keeps bed linen, theatre and ward textiles clean and safely processed. It matters more "
     "for infection control than most people realise.",
     "Our Laundry dey keep bed linen, theatre and ward cloth clean and safely processed. E dey important for "
     "infection control pass wetin plenty people think.", _CTA_DESK),
    ("dirty_linen", ["dirty bed sheet", "my sheets need changing"],
     "Tell the ward nurse and it'll be changed. You should never have to lie on soiled bedding — please "
     "speak up, nobody will mind.",
     "Tell ward nurse and dem go change am. You no suppose lie down on dirty bedding — abeg talk, nobody go vex.",
     _CTA_DESK),
    ("own_clothes", ["can i bring my own wrapper", "own bedsheet"],
     "Many patients do bring their own wrapper or towel and that's perfectly fine. Please label anything "
     "you'd hate to lose.",
     "Plenty patient dey bring dem own wrapper or towel and e dey okay. Abeg write your name for anything wey you "
     "no wan lose.", _CTA_HELP),
    ("lost_clothes", ["my clothes are missing", "lost laundry"],
     "I'm sorry. Tell the ward nurse and they'll check with Laundry — items do turn up.",
     "Sorry. Tell ward nurse make dem check with Laundry — item dey show up.", _CTA_DESK),
    ("where", ["where is the laundry"],
     "The Laundry is a service unit — ask the ward staff rather than going there yourself.",
     "Laundry na service unit — ask ward staff instead of going there yourself.", _CTA_DESK),
    ("complaint", ["complain about linen"],
     "Please tell us — linen and cleanliness complaints go straight to management.",
     "Abeg tell us — linen and cleanliness complaint dey go straight to management.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

_d("Nursing Services", [
    ("what", ["nursing services", "apex nurse", "head of nursing"],
     "Nursing Services covers all our ward and clinic nursing, led by the Head of Nursing Services. Nurses "
     "are with you more than anyone else during a stay — they're your first port of call.",
     "Nursing Services cover all our ward and clinic nursing, and Head of Nursing Services dey lead am. Nurse dey "
     "with you pass anybody during your stay — na dem be your first place to run go.", _CTA_DESK),
    ("call_nurse", ["how do i call a nurse", "need a nurse"],
     "Use the call bell by the bed, or ask any passing staff member. Never feel you're bothering them — "
     "that's exactly what they're there for.",
     "Use the call bell near the bed, or tell any staff wey dey pass. No feel say you dey disturb dem — na exactly "
     "wetin dem dey there for.", _CTA_DESK),
    ("pain", ["i am in pain", "pain relief"],
     "Please tell the nurse looking after you now — don't wait or endure it quietly. They can assess you and "
     "speak to the doctor. You should not be left in pain.",
     "Abeg tell the nurse wey dey look after you now — no wait or dey endure am quietly. Dem fit assess you and "
     "talk to doctor. You no suppose dey pain.", "🚑 Tell your nurse now."),
    ("shift", ["when do nurses change shift", "night nurse"],
     "Nurses work day and night shifts so there's always someone on the ward, any hour.",
     "Nurse dey work day and night shift so person dey ward always, any hour.", _CTA_HELP),
    ("injection", ["injection", "drip", "iv"],
     "The nurses will explain what they're giving you and why — and you're entitled to ask. Please do ask if "
     "you're unsure; a good nurse welcomes the question.",
     "Nurse go explain wetin dem dey give you and why — and you get right to ask. Abeg ask if you no sure; good "
     "nurse dey welcome question.", _CTA_HELP),
    ("wound_care", ["dressing change", "nurse wound care"],
     "Ward nurses and the dressing room handle this. Tell them if the dressing is wet, smelling or painful.",
     "Ward nurse and dressing room dey handle am. Tell dem if the dressing wet, dey smell or dey pain you.",
     _CTA_DESK),
    ("relative", ["can i stay with my relative", "sleep in the ward"],
     "Ask the ward nurse — arrangements vary by ward and by patient. They'll tell you what's possible.",
     "Ask ward nurse — arrangement dey vary by ward and by patient. Dem go tell you wetin possible.", _CTA_DESK),
    ("feeding", ["feeding my patient", "bring food for patient"],
     "Please check with the nurse first — some patients are on special or restricted diets for medical "
     "reasons, and it matters.",
     "Abeg check with nurse first — some patient dey on special or restricted diet for medical reason, and e dey "
     "important.", _CTA_DESK),
    ("discharge", ["when will i be discharged", "going home"],
     "The doctor decides with the nursing team, and they'll give you notice plus discharge instructions. "
     "Please read those instructions — they matter more than people think.",
     "Doctor go decide with nursing team, and dem go give you notice plus discharge instruction. Abeg read the "
     "instruction — e dey important pass wetin people think.", _CTA_HELP),
    ("praise", ["thank a nurse", "the nurse was wonderful"],
     "Please tell us — nursing is hard work and hearing this lifts a whole ward. Leave feedback "
     "with the nurse's name.",
     "Abeg tell us — nursing na hard work and to hear this dey really lift the whole ward. Leave feedback with the "
     "nurse name.", "Tap 'Feedback' to send your praise."),
    ("complaint", ["complain about a nurse", "nurse was rude"],
     "I'm sorry — that isn't the standard we hold. Please report it; management take nursing conduct "
     "seriously, and you can submit anonymously if you'd rather.",
     "Sorry — that no be the standard wey we hold. Abeg report am; management dey take nursing conduct serious, "
     "and you fit submit anonymous if you prefer.", "Tap 'Make a Complaint' and open Make a complaint."),
    ("ipc", ["infection control", "why must i wash hands"],
     "Our Infection Prevention & Control team sits within Nursing Services. Hand hygiene is the single most "
     "effective thing any of us can do to protect patients here.",
     "Our Infection Prevention & Control team dey inside Nursing Services. Hand hygiene na the single most "
     "effective thing wey any of us fit do to protect patient here.", _CTA_HELP),
    ("hours", ["nursing hours", "are nurses always available"],
     "Yes — nursing cover is around the clock, every day of the year.",
     "Yes — nursing cover dey 24 hours, every day of the year.", _CTA_HELP),
])


# ============================================================ RADIOLOGY / IMAGING
_d("Radiology / Imaging", [
    ("what", ["radiology", "imaging department", "scan department", "x ray department"],
     "Our Imaging unit does X-rays, ultrasound scans and ECG. Your doctor writes the request and "
     "we do the pictures — then the doctor explains what they show.",
     "Our Imaging unit dey do X-ray, ultrasound scan and ECG. Your doctor go write the request and "
     "we go do the picture — then doctor go explain wetin e show.", _CTA_DESK),
    ("book", ["book a scan", "arrange x ray", "when can i do my scan"],
     "Bring your request slip to the Imaging desk and they'll tell you the next available time. "
     "Some scans are done the same day.",
     "Bring your request slip come Imaging desk and dem go tell you the next time wey dey available. "
     "Some scan dey done same day.", _CTA_DESK),
    ("prepare", ["how do i prepare for a scan", "before ultrasound"],
     "It depends on the scan — some need a full bladder, some need you to fast. Your request slip "
     "will say, so please read it, and ask at the desk if it isn't clear.",
     "E depend on the scan — some need full bladder, some need make you fast. Your request slip go talk "
     "am, abeg read am, and ask for the desk if e no clear.", _CTA_DESK),
    ("results", ["scan results", "when will my x ray be ready"],
     "The report goes to your doctor, usually within a day or two for routine scans. Your doctor will "
     "go through it with you — pictures need explaining, not just reading.",
     "The report dey go your doctor, usually within one or two days for normal scan. Your doctor go go "
     "through am with you — picture need explanation, no be just to read am.", _CTA_HELP),
    ("cost", ["how much is an x ray", "scan price", "ultrasound cost"],
     "It varies by the type of scan. The billing desk will price your specific request before it's "
     "done, so you always know first.",
     "E dey vary by the type of scan. Billing desk go price your own request before dem do am, so you go "
     "always know first.", _CTA_DESK),
    ("safe", ["is x ray safe", "radiation", "is scan safe in pregnancy"],
     "These are good questions and the radiographer will answer them properly for your situation. "
     "Always tell them if you are or might be pregnant, before the scan — never after.",
     "Na correct question and the radiographer go answer am well for your own situation. Always tell dem "
     "if you dey pregnant or you fit dey pregnant, before the scan — no be after.", _CTA_HELP),
    ("bring", ["what to bring for a scan"],
     "Bring your request slip, your hospital card, any previous films or reports, and your receipt. "
     "Old films help the radiologist compare.",
     "Bring your request slip, hospital card, any old film or report, and your receipt. Old film dey help "
     "the radiologist compare.", _CTA_HELP),
    ("wait", ["how long does a scan take"],
     "Most X-rays take just a few minutes; an ultrasound takes a bit longer. The desk will tell you "
     "what to expect on the day.",
     "Most X-ray na few minutes; ultrasound dey take small time pass. The desk go tell you wetin to expect "
     "for the day.", _CTA_HELP),
    ("film", ["collect my x ray film", "copy of my scan"],
     "Ask at the Imaging desk with your ID and receipt. Films are usually released with the report.",
     "Ask for Imaging desk with your ID and receipt. Dem dey usually release film with the report.", _CTA_DESK),
    ("hours", ["imaging hours", "when is x ray open"],
     "Imaging runs through the working day, with emergency cover for urgent cases at any hour.",
     "Imaging dey run through the work day, and emergency cover dey for urgent case any time.", _CTA_DESK),
    ("where", ["where is radiology", "find imaging"],
     "The Imaging unit is signposted inside the hospital — reception will walk you there.",
     "Imaging unit get sign inside the hospital — reception go waka with you.", _CTA_DESK),
    ("complaint", ["complain about imaging"],
     "Please tell us — it reaches management with a reference number so it can be followed up properly.",
     "Abeg tell us — e dey reach management with reference number make dem fit follow am up well.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ FAMILY MEDICINE / GOPD
_d("Family Medicine / General Outpatient", [
    ("what", ["family medicine", "general outpatient", "gopd", "general clinic"],
     "The General Outpatient Department — GOPD — is where most visits begin. If you're not sure which "
     "specialist you need, start here and the doctor will treat you or point you the right way.",
     "General Outpatient Department — GOPD — na where most visit dey start. If you no sure which specialist "
     "you need, start from here and doctor go treat you or show you the right way.", _CTA_BOOK),
    ("book", ["book gopd", "see a general doctor"],
     "You can book into GOPD. Mornings are calmest. Bring your hospital card and any medicines you "
     "are taking.",
     "You fit book for GOPD. Morning dey calm pass. Bring your hospital card and any medicine wey you dey "
     "take.", _CTA_BOOK),
    ("walk_in", ["can i just walk in", "without appointment"],
     "Yes, you can walk in — though booking or taking a queue number from your phone first means less "
     "standing around.",
     "Yes, you fit waka come — but if you book or take queue number from your phone first, you no go stand "
     "for line.", "Say 'queue' or open Get a number."),
    ("which_clinic", ["which department should i see", "i don't know who to see"],
     "Then GOPD is exactly the right place — that's what it's for. The doctor will see you and refer you "
     "on if you need a specialist.",
     "Then GOPD na exactly the right place — na wetin e dey for. Doctor go see you and refer you go specialist "
     "if you need am.", _CTA_BOOK),
    ("bring", ["what to bring to gopd"],
     "Your hospital card, any medicines you're taking, previous results if you have them, and a short "
     "note of what's been troubling you.",
     "Your hospital card, any medicine wey you dey take, old result if you get am, and short note of wetin dey "
     "worry you.", _CTA_HELP),
    ("cost", ["gopd consultation fee"],
     "GOPD consultation is charged at our standard clinic rate; tests and medicines are separate. Billing "
     "will confirm before anything is done.",
     "GOPD consultation na our normal clinic rate; test and medicine get dem own charge. Billing go confirm "
     "before dem do anything.", _CTA_DESK),
    ("children", ["can my child be seen at gopd"],
     "Young children are usually best seen by Paediatrics, but come in and we'll direct you to the right "
     "team quickly.",
     "Small pikin better make Paediatrics see dem, but come and we go direct you to the right team quick.",
     _CTA_BOOK),
    ("referral", ["gopd referral to specialist"],
     "If you need a specialist, the GOPD doctor writes the referral and we book you in — you won't have to "
     "start over.",
     "If you need specialist, GOPD doctor go write the referral and we go book you — you no go start again from "
     "scratch.", _CTA_BOOK),
    ("hours", ["gopd hours", "when is general clinic open"],
     "GOPD runs through the working day on weekdays. Accident & Emergency covers everything outside those "
     "hours.",
     "GOPD dey run through the work day for weekdays. Accident & Emergency dey cover everything outside that "
     "time.", _CTA_BOOK),
    ("dressing", ["wound dressing at gopd", "treatment room"],
     "The treatment and dressing rooms are part of GOPD. Come at your appointment time, or sooner if the "
     "wound looks worse.",
     "Treatment and dressing room dey inside GOPD. Come for your appointment time, or come quick if the wound "
     "worse.", _CTA_DESK),
    ("where", ["where is gopd"],
     "GOPD is signposted from the main entrance — reception will point you straight there.",
     "GOPD get sign from the main entrance — reception go show you straight.", _CTA_DESK),
    ("complaint", ["complain about gopd"],
     "Please do — it goes to management with a reference number and someone will look into it.",
     "Abeg do — e dey go management with reference number and person go look into am.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])

# ============================================================ CATERING SERVICES
_d("Catering Services", [
    ("what", ["catering", "hospital kitchen", "patient meals", "food services"],
     "Our Catering team prepares patient meals, including special diets ordered by the dietitian. Good "
     "food is part of getting better, not an extra.",
     "Our Catering team dey prepare patient food, including special diet wey dietitian order. Good food na "
     "part of recovery, no be extra.", _CTA_DESK),
    ("meal_times", ["meal times", "when is food served"],
     "Meals are served at set times through the day. The ward nurse will tell you the exact times on your "
     "ward.",
     "Dem dey serve food for set time through the day. Ward nurse go tell you the exact time for your ward.",
     _CTA_DESK),
    ("bring_food", ["can i bring food for my patient", "outside food"],
     "Please check with the nurse first — some patients are on restricted or special diets for medical "
     "reasons, and the wrong food can really set them back.",
     "Abeg check with nurse first — some patient dey on restricted or special diet for medical reason, and wrong "
     "food fit really set dem back.", _CTA_DESK),
    ("special_diet", ["diabetic meal", "special diet", "no salt diet"],
     "Special diets are arranged with our Nutrition & Dietetics team. Tell the nurse and they'll set it up.",
     "Special diet, na our Nutrition & Dietetics team dey arrange am. Tell nurse and dem go set am up.", _CTA_DESK),
    ("allergy", ["food allergy", "i cannot eat"],
     "Please tell the nurse straight away so it's recorded on your chart. Never assume the kitchen knows — "
     "tell them, every admission.",
     "Abeg tell nurse sharp sharp make dem record am for your chart. No assume say kitchen sabi — tell dem, every "
     "time you admit.", _CTA_DESK),
    ("quality", ["the food was cold", "food complaint", "food not good"],
     "I'm sorry — please tell the ward nurse the same day so it can be put right, and file it formally if "
     "it keeps happening. Meals matter.",
     "Sorry — abeg tell ward nurse same day make dem fix am, and file am formally if e dey happen again. Food dey "
     "important.", "Tap 'Make a Complaint' if it continues."),
    ("visitors_food", ["is there a canteen", "where can i buy food"],
     "Ask at reception about the canteen or nearby options for visitors.",
     "Ask for reception about canteen or place wey dey near for visitor.", _CTA_DESK),
    ("religious", ["halal food", "religious diet"],
     "Please tell the nurse your dietary requirements on admission and we'll do our best to accommodate them.",
     "Abeg tell nurse your food requirement when you admit and we go try our best to arrange am.", _CTA_DESK),
    ("water", ["drinking water for patients"],
     "Ask the ward nurse — drinking water is provided on the wards.",
     "Ask ward nurse — drinking water dey for the ward.", _CTA_DESK),
    ("hours", ["catering hours"],
     "The kitchen works around the meal service through the day. The ward nurse knows the times for your ward.",
     "Kitchen dey work around the meal service through the day. Ward nurse sabi the time for your ward.", _CTA_DESK),
    ("hygiene", ["is the kitchen clean", "food hygiene"],
     "Catering and Environmental Health work together on food hygiene, and it's taken seriously. Report any "
     "concern the same day.",
     "Catering and Environmental Health dey work together on food hygiene, and dem dey take am serious. Report any "
     "concern same day.", _CTA_DESK),
    ("complaint", ["complain about the food"],
     "Please tell us — food complaints reach management with a reference number.",
     "Abeg tell us — food complaint dey reach management with reference number.",
     "Tap 'Make a Complaint' and open Make a complaint."),
])


# --------------------------------------------------------------------------
# Build the KB list the loader expects.
#
# Every trigger is also emitted prefixed with the department name and with a
# few natural variants, so "laboratory opening hours", "hours for the lab" and
# "when is the lab open" all reach the same answer.
# --------------------------------------------------------------------------
# ============================================================ PAEDIATRICS
_d("Paediatrics", [
    ("what", ["what does paediatrics do", "what is paediatrics", "children clinic", "wetin children clinic dey do"],
     "Paediatrics is our children's clinic — the doctors and nurses who look after children from "
     "newborn to their teenage years. They handle everything from fevers and coughs to check-ups, "
     "growth reviews and immunisations, in a space set up to put children at ease.",
     "Paediatrics na our children clinic — the doctor and nurse wey dey look after pikin from newborn "
     "reach teenage years. Dem dey handle fever, cough, check-up, growth check and immunization for "
     "place wey go make pikin calm.",
     _CTA_BOOK),
    ("book", ["book paediatrics", "book children clinic", "see a children doctor", "appointment for my child"],
     "Yes — you can book a children's clinic slot for your child. Weekday mornings are usually "
     "calmest if your child's visit can wait. Bring your child's immunisation card and any old "
     "notes along.",
     "Yes, you fit book children clinic slot for your pikin. Weekday morning dey calm pass if the "
     "visit fit wait. Carry your pikin immunization card and any old note come.",
     _CTA_BOOK),
    ("bring", ["what to bring paediatrics", "paediatrics what to bring", "children clinic documents", "wetin i go bring for children clinic"],
     "Please bring your child's immunisation card, any medicines they are already taking, and a "
     "note of what you've observed at home — when it started, what makes it better or worse. You "
     "know your child best; that story helps the doctor most.",
     "Abeg carry your pikin immunization card, any medicine wey dem dey take already, and wetin you "
     "don notice for house — when e start, wetin dey make am better or worse. Na you know your "
     "pikin pass; that story go help doctor well.",
     _CTA_DESK),
    ("immunisation", ["immunisation", "child immunisation", "vaccination for child", "child vaccination schedule"],
     "Our children's clinic gives routine immunisations and keeps your child's card up to date each "
     "visit. If you've missed any dose, don't worry — come in and the team will review the card and "
     "plan the catch-ups with you.",
     "Our children clinic dey give normal immunization and dem go update your pikin card every visit. "
     "If you miss any dose, no worry — come make the team check the card and plan the catch-up with you.",
     _CTA_BOOK),
    ("fever_child", ["my child has fever", "sick child", "child fever what to do", "my pikin dey hot"],
     "A sick child deserves to be seen — you don't have to guess at home. If your child is small, "
     "unusually drowsy, refusing feeds or you're simply worried, bring them in; out of hours our "
     "Accident & Emergency is open 24/7. Trust your instinct — you're right to check.",
     "Sick pikin suppose see doctor — you no need guess for house. If your pikin small, dey sleep "
     "pass normal, no gree feed, or you just dey worried, bring dem come; our A&E dey open 24/7. "
     "Trust your mind — e good say you check.",
     _CTA_DESK),
    ("newborn", ["newborn check", "new baby checkup", "baby clinic", "newborn jaundice"],
     "Congratulations! Newborns are seen in the children's clinic for routine checks, and our "
     "neonatal team cares for babies who need extra help. If your newborn looks yellow, feeds "
     "poorly or feels unusually hot or cold, come in the same day — little ones are checked quickly.",
     "Congratulations o! Newborn dey come children clinic for normal check, and our neonatal team "
     "dey care for babies wey need extra help. If your newborn yellow, no dey feed well, or dey "
     "hot or cold pass normal, come that same day — small pikin dey check sharp sharp.",
     _CTA_DESK),
    ("growth", ["child growth check", "my child is not gaining weight", "child nutrition advice", "growth monitoring"],
     "Growth reviews are a normal part of children's clinic visits — the team weighs and measures "
     "your child and plots it on the card with you. If you're worried your child isn't gaining "
     "weight or eating well, book a slot and bring any feeding notes; early worries are easiest to sort.",
     "Growth check na normal part of children clinic visit — the team go weigh and measure your "
     "pikin, dem go mark am for card with you. If you worry say your pikin no dey add weight or no "
     "dey chop well, book slot come with feeding note — early worry easy to settle.",
     _CTA_BOOK),
    ("emergency", ["child emergency", "child accident", "my child swallowed something", "child emergency now"],
     "For anything urgent — a fall, a burn, swallowing something, trouble breathing — come straight "
     "to Accident & Emergency; it's open 24/7 and children are seen promptly. If you can, bring what "
     "they swallowed or the medicine packet with you. Don't wait to book online.",
     "For anything urgent — fall, burn, swallow something, breathing wahala — come straight to A&E; "
     "e dey open 24/7 and pikin dey see quick. If you fit, carry wetin dem swallow or the medicine "
     "pack come. No wait to book online.",
     _CTA_DESK),
    ("cost", ["paediatrics cost", "how much is children clinic", "child consultation fee", "children clinic price"],
     "I'd rather not guess at a figure. Children's clinic fees follow the standard consultation "
     "rates — the billing desk or the booking page will give you the current amount before you "
     "commit to anything.",
     "I no go guess figure. Children clinic fee follow the normal consultation rate — billing desk "
     "or the booking page go give you the current amount before you pay anything.",
     _CTA_DESK),
    ("hours", ["paediatrics opening hours", "children clinic hours", "when is children clinic", "children clinic today"],
     "The children's clinic runs on weekdays, and mornings are usually the calmest time. For "
     "evenings, weekends or anything urgent, Accident & Emergency cares for children around the "
     "clock. Today's times are on the booking page.",
     "Children clinic dey run weekday, morning dey calm pass. For evening, weekend or anything "
     "urgent, A&E dey care for pikin 24/7. Today time dey the booking page.",
     _CTA_BOOK),
    ("where", ["where is paediatrics", "where is children clinic", "paediatrics location", "children clinic direction"],
     "I can't point you round the building myself, but reception will walk you straight to the "
     "children's clinic — ask at the front desk or check the booking page for the location. "
     "Staff will guide you and your little one the whole way.",
     "I no fit point you inside building, but reception go direct you go children clinic — ask for "
     "front desk or check the booking page for location. Staff go guide you and your pikin reach there.",
     _CTA_DESK),
    ("adolescent", ["teenager clinic", "adolescent health", "clinic for teenagers", "teen health talk"],
     "Teenagers are welcome too — the children's team cares for patients right into their teenage "
     "years, and they're used to questions young people find awkward. Anything your teen shares is "
     "treated with respect and privacy.",
     "Teenagers dey welcome too — the children team dey care for patient reach teenage years, and "
     "dem use the kind question wey young people find hard to ask. Anything your teen talk na with "
     "respect and privacy.",
     _CTA_BOOK),
    ("complaint", ["paediatrics complaint", "children clinic problem", "complain about children clinic", "children clinic no well"],
     "I'm sorry something went wrong — especially when it involves your child. You can raise it "
     "formally through the complaint form on this app and it will reach the right people, or speak "
     "to the nurse in charge at the children's clinic straight away.",
     "I dey sorry say wetin happen — especially when e concern your pikin. You fit raise am through "
     "the complaint form for this app and e go reach the right people, or talk to the nurse in "
     "charge for children clinic sharp sharp.",
     _CTA_DESK),
    ("results", ["child test results", "paediatrics results", "children lab results", "my pikin result"],
     "Your child's results come back to the children's clinic, and the team will explain them in "
     "plain language and what happens next. Ask at the clinic desk, or bring the child's folder — "
     "results are always explained with you present.",
     "Your pikin result go return to children clinic, and the team go explain am for plain language "
     "and wetin next. Ask for clinic desk, or carry the pikin folder come — na with you dem go "
     "explain am.",
     _CTA_DESK),
])

# ============================================================ DENTAL SERVICES
_d("Dental Services", [
    ("what", ["dental services", "what does dental do", "what is dental services", "about the dental clinic", "wetin dental clinic dey do"],
     "Dental Services looks after your teeth and mouth — check-ups and cleaning, fillings, "
     "extractions, dentures and urgent toothache care. Regular check-ups catch small problems "
     "before they become big, painful ones.",
     "Dental Services dey look after your teeth and mouth — check-up and cleaning, filling, "
     "extraction, denture and urgent toothache care. Regular check-up dey catch small problem "
     "before e turn big painful one.",
     _CTA_BOOK),
    ("book", ["book dental appointment", "dental booking", "see a dentist", "book tooth checkup"],
     "You can book a dental slot right on this app. If it's your first visit, a check-up and "
     "cleaning is a gentle way to start — the dentist will examine, explain and plan anything "
     "else with you first.",
     "You fit book dental slot for this app. If na your first visit, check-up and cleaning na the "
     "gentle way to start — dentist go examine, explain, and plan anything else with you first.",
     _CTA_BOOK),
    ("bring", ["dental what to bring", "what to bring dentist", "dental documents", "wetin i go bring for dentist"],
     "Just yourself and, if you have them, any previous dental records or X-rays — they help the "
     "dentist see your history at a glance. If you're on any regular medicines, bring the list "
     "along too.",
     "Just you, and if you get am, any old dental record or X-ray — e go help dentist see your "
     "history quick. If you dey take any medicine regular, carry the list come too.",
     _CTA_DESK),
    ("toothache", ["bad toothache", "tooth pain relief", "urgent toothache", "my tooth dey pain me"],
     "A bad toothache can stop your whole day — come in and we'll get you comfortable. Dental "
     "urgencies are seen promptly, and if it's after hours, Accident & Emergency can help with "
     "the pain until the dental team sees you.",
     "Bad toothache fit spoil your whole day — come make we comfort you. Dental emergency dey see "
     "quick, and if e pass working hours, A&E fit help with the pain before dental team see you.",
     _CTA_DESK),
    ("extraction", ["tooth removal", "having a tooth out", "dental extraction", "wax go remove my tooth"],
     "If a tooth needs to come out, the dentist will examine it, explain the plan and make sure "
     "the area is fully numbed before anything happens — you'll feel pressure, not pain. Ask as "
     "many questions as you like before you agree to anything.",
     "If tooth suppose comot, dentist go examine am, explain the plan, and make the place num well "
     "before anything — you go feel pressure, no be pain. Ask any question wey you wan ask before "
     "you agree.",
     _CTA_DESK),
    ("cleaning", ["teeth cleaning", "scaling and polishing", "dental cleaning booking", "clean my teeth"],
     "Cleaning (scaling and polishing) is one of the kindest things you can do for your teeth — "
     "it removes the build-up brushing can't, and your mouth feels new afterwards. You can book "
     "it as a stand-alone visit.",
     "Cleaning (scaling and polishing) na one of the best thing wey you fit do for your teeth — e "
     "remove the build-up wey brush no fit remove, and your mouth go fresh after. You fit book am "
     "as e own visit.",
     _CTA_BOOK),
    ("children_dental", ["child dental", "children teeth", "my child tooth", "pickin teeth"],
     "Children are welcome at the dental clinic — early visits build comfortable, confident "
     "patients for life. The team keeps it gentle and friendly, and will show you and your child "
     "how to keep those little teeth clean.",
     "Pikin dey welcome for dental clinic — early visit go make dem grow dey calm and sure of "
     "dentist. The team dey gentle and friendly, and dem go show you and your pikin how to keep "
     "the small teeth clean.",
     _CTA_BOOK),
    ("dentures", ["dentures", "false teeth", "replacement teeth", "denture fitting"],
     "Dentures and other tooth replacements are discussed at the dental clinic — the dentist will "
     "examine, talk through the options that suit you and give you a written estimate before "
     "anything is made. Nothing happens without your say-so.",
     "Denture and other teeth replacement — you go discuss am for dental clinic — dentist go "
     "examine, talk the options wey suit you, and give you written estimate before dem make "
     "anything. Nothing go happen without your approval.",
     _CTA_DESK),
    ("cost", ["dental cost", "how much is dentist", "tooth extraction price", "dental fee"],
     "Dental costs depend on exactly what your teeth need, so I won't guess a figure. You'll get "
     "a written estimate at the billing desk before any treatment is booked — no surprises.",
     "Dental cost depend on wetin your teeth need, so I no go guess figure. You go get written "
     "estimate for billing desk before any treatment — no surprise.",
     _CTA_DESK),
    ("hours", ["dental opening hours", "dental clinic hours", "when is dental open", "dental today"],
     "The dental clinic runs on weekdays; the booking page shows today's slots. For urgent "
     "tooth trouble outside those hours, come through Accident & Emergency and they'll get you "
     "started.",
     "Dental clinic dey run weekday; booking page go show today slots. For urgent tooth wahala "
     "outside those hours, enter through A&E and dem go start your care.",
     _CTA_BOOK),
    ("where", ["where is dental clinic", "dental location", "dental clinic direction", "where dentist dey"],
     "Ask at reception and they'll point you straight to the dental clinic — or check the "
     "booking page, which shows the location with your appointment. You won't have to hunt for it.",
     "Ask for reception and dem go direct you go dental clinic — or check booking page, e dey "
     "show location with your appointment. You no go dey find am up and down.",
     _CTA_DESK),
    ("complaint", ["dental complaint", "complain about dentist", "dental treatment problem", "dental no well"],
     "I'm sorry your dental visit wasn't right. You can log it on the complaint form in this app "
     "— it reaches the dental team's lead and the hospital's complaint desk — or speak to the "
     "dental nurse in charge before you leave.",
     "I dey sorry say your dental visit no go well. You fit log am for the complaint form for "
     "this app — e go reach dental team lead and the hospital complaint desk — or talk to the "
     "dental nurse in charge before you comot.",
     _CTA_DESK),
])

# ==================================================== OPHTHALMOLOGY (EYE CLINIC)
_d("Ophthalmology (Eye Clinic)", [
    ("what", ["what does ophthalmology do", "what is eye clinic", "about eye clinic", "wetin eye clinic dey do"],
     "The Eye Clinic (Ophthalmology) cares for your vision — routine eye checks, glasses "
     "prescriptions, eye infections, injuries and follow-up for long-term eye conditions. "
     "Bringing your old glasses or prescription helps the team compare and track changes.",
     "The Eye Clinic (Ophthalmology) dey care for your sight — normal eye check, glasses, eye "
     "infection, injury and follow-up for long-term eye matter. Carry your old glasses or "
     "prescription come — e go help the team compare.",
     _CTA_BOOK),
    ("book", ["book eye clinic", "eye test booking", "book ophthalmology", "see eye doctor"],
     "You can book an eye clinic slot on this app. If your visit can wait, weekday mornings are "
     "usually calmest — and bring any glasses, prescriptions or eye drops you're already using.",
     "You fit book eye clinic slot for this app. If your visit fit wait, weekday morning dey calm "
     "pass — carry any glasses, prescription or eye drop wey you dey use come.",
     _CTA_BOOK),
    ("bring", ["eye clinic what to bring", "what to bring ophthalmology", "eye documents", "wetin i go bring for eye clinic"],
     "Bring your old glasses or last prescription, any eye drops you use, and your list of "
     "regular medicines — several of them matter to eye care. If someone usually helps you read "
     "or walk, bring them along too; your eyes may be dilated for checking.",
     "Carry your old glasses or last prescription, any eye drop wey you dey use, and the list of "
     "your regular medicine — some of dem matter for eye care. If person dey help you read or "
     "waka, bring dem come too; dem fit widen your eye for check.",
     _CTA_DESK),
    ("red_eye", ["red eye", "eye infection", "stingy eye", "eye discharge"],
     "A red, sticky or painful eye is worth having looked at properly — please don't just buy "
     "drops from a stall. Book into the eye clinic, and if the eye is very painful or your "
     "vision is affected, come in promptly rather than wait.",
     "Red eye wey dey sting or pain you suppose see doctor — abeg no just buy drop for stall. Book "
     "eye clinic, and if the eye dey pain you well or your vision dey affected, come sharp no wait.",
     _CTA_BOOK),
    ("injury", ["eye injury", "something in my eye", "eye accident", "chemical in eye"],
     "For anything in the eye that shouldn't be — a scratch, a foreign body, a splash of "
     "chemical — come straight to Accident & Emergency, day or night. Don't rub it and don't "
     "try to remove anything yourself; let the team look after your sight.",
     "For anything wey enter your eye wey no suppose dey — scratch, foreign thing, chemical splash "
     "— come straight to A&E, day or night. No rub am and no try remove am yourself; make the "
     "team protect your sight.",
     _CTA_DESK),
    ("vision_change", ["sudden vision change", "blurry vision suddenly", "losing sight", "my eye dey dim"],
     "Any sudden change in your vision deserves same-day attention — come in promptly and tell "
     "reception it's your sight. Gradual changes can wait for a booked clinic slot, but sudden "
     "ones should never wait at home.",
     "Any sudden change for your vision deserve same-day attention — come sharp and tell reception "
     "say na your sight. The one wey dey come slow fit wait for booked slot, but sudden one no "
     "suppose wait for house.",
     _CTA_DESK),
    ("glasses", ["glasses", "reading glasses", "prescription glasses", "eye glass"],
     "The clinic's refraction unit tests your vision and, if you need glasses, gives you a "
     "current prescription to fill. Bring your old glasses along — comparing old and new helps "
     "fine-tune the result.",
     "The clinic refraction unit go test your vision and if you need glasses, dem go give you "
     "current prescription wey you go use. Carry your old glasses come — to compare old and new "
     "go make the result better.",
     _CTA_BOOK),
    ("children_eye", ["child eye test", "children vision", "my child eye", "pickin eye"],
     "Children's eyes can be checked gently at the eye clinic — squints, lazy eye and school "
     "vision worries are all routine here. Early checks make treatment easier, so if you or a "
     "teacher has noticed something, book a children's eye slot.",
     "Pikin eye dey check gently for eye clinic — squint, lazy eye and school vision wahala na "
     "normal here. Early check make treatment easy, so if you or their teacher notice something, "
     "book children eye slot.",
     _CTA_BOOK),
    ("cost", ["eye clinic cost", "how much is eye test", "ophthalmology price", "eye clinic fee"],
     "Eye clinic fees depend on the visit type — a routine test differs from treatment — so I "
     "won't guess a figure. The billing desk will confirm the amount for your visit before "
     "anything happens.",
     "Eye clinic fee depend on the visit type — normal test different from treatment — so I no go "
     "guess figure. Billing desk go confirm the amount for your visit before anything.",
     _CTA_DESK),
    ("hours", ["eye clinic hours", "ophthalmology opening hours", "when is eye clinic", "eye clinic today"],
     "The eye clinic runs on weekdays and the booking page shows the current slots. For sudden "
     "eye problems in the evening or at night, Accident & Emergency is open 24/7 and will "
     "protect your sight first.",
     "Eye clinic dey run weekday and booking page go show the current slots. For sudden eye "
     "wahala for evening or night, A&E dey open 24/7 and dem go protect your sight first.",
     _CTA_BOOK),
    ("where", ["where is eye clinic", "ophthalmology location", "eye clinic direction", "where eye doctor dey"],
     "Reception will point you straight to the eye clinic — or the booking page shows the "
     "location with your appointment. If walking across the grounds is hard for you, tell the "
     "front desk; they'll help.",
     "Reception go direct you straight go eye clinic — or booking page dey show location with "
     "your appointment. If to waka far hard for you, tell front desk; dem go help.",
     _CTA_DESK),
    ("complaint", ["eye clinic complaint", "complain about eye clinic", "ophthalmology problem", "eye clinic no well"],
     "I'm sorry your eye visit didn't go well — your sight is too important to leave with a bad "
     "feeling. Raise it on the complaint form in this app, or speak to the nurse in charge at "
     "the clinic before you leave.",
     "I dey sorry say your eye visit no go well — your sight too important to leave with bad "
     "feeling. Raise am for the complaint form for this app, or talk to the nurse in charge for "
     "the clinic before you comot.",
     _CTA_DESK),
])

# ==================================================== ENT (EAR, NOSE & THROAT)
_d("ENT (Ear, Nose & Throat)", [
    ("what", ["what does ent do", "what is ent clinic", "ear nose throat clinic", "wetin ent clinic dey do"],
     "The ENT clinic looks after ears, nose and throat — hearing checks, ear infections, "
     "sinus and tonsil trouble, nosebleeds and voice concerns. The audiology unit does proper "
     "hearing tests, so a hearing worry is well worth bringing here.",
     "The ENT clinic dey look after ear, nose and throat — hearing check, ear infection, sinus "
     "and tonsil wahala, nosebleed and voice matter. The audiology unit dey do correct hearing "
     "test, so hearing worry suppose come here.",
     _CTA_BOOK),
    ("book", ["book ent appointment", "ent booking", "see ent doctor", "book ear clinic"],
     "You can book an ENT slot on this app. Bring any previous hearing tests, scans or "
     "prescriptions — the specialist can decide much faster with them in hand.",
     "You fit book ENT slot for this app. Carry any old hearing test, scan or prescription come — "
     "the specialist go decide quick when dem see am.",
     _CTA_BOOK),
    ("bring", ["ent what to bring", "what to bring ent clinic", "ent documents", "wetin i go bring for ent"],
     "Bring any old hearing tests or scans, the medicines you're using, and — for hearing "
     "questions — the person you usually talk with, if they can come. Two ears and two "
     "perspectives make the assessment easier.",
     "Carry any old hearing test or scan, the medicine wey you dey use, and — for hearing matter — "
     "the person wey you dey usually talk with, if dem fit come. Two ear and two perspective go "
     "make the check easy.",
     _CTA_DESK),
    ("ear_pain", ["ear pain", "earache", "my ear dey pain me", "blocked ear pain"],
     "Earache is miserable — you don't have to endure it. Book into ENT and let the doctor look "
     "inside the ear properly. If the pain is severe, comes with fever, or it's a small child "
     "suffering, come in the same day.",
     "Earache dey pain person well well — you no suppose endure am. Book ENT make doctor look "
     "inside the ear well. If the pain strong, e come with fever, or na small pikin, come that "
     "same day.",
     _CTA_BOOK),
    ("hearing", ["hearing loss", "i can't hear well", "hearing test", "my ear dey block"],
     "A hearing worry deserves a proper hearing test, not a guess — our audiology unit does "
     "exactly that, and the ENT doctor reviews the result with you. Sudden hearing loss should "
     "be seen the same day; gradual changes can take a booked slot.",
     "Hearing wahala deserve correct hearing test, no be guess — our audiology unit dey do am, and "
     "the ENT doctor go review the result with you. Sudden hearing loss suppose see doctor same "
     "day; the slow one fit take booked slot.",
     _CTA_BOOK),
    ("throat", ["sore throat", "strep throat", "tonsils", "my throat dey pain me"],
     "A sore throat that won't settle, or tonsils that keep flaring, is exactly what the ENT "
     "clinic assesses. Come in and let a doctor look properly — you'll get a clear plan rather "
     "than guesses from a pharmacy counter.",
     "Sore throat wey no gree settle, or tonsil wey dey flare every time — na wetin ENT clinic dey "
     "check. Come make doctor look am well — you go get clear plan, no be guess from chemist.",
     _CTA_BOOK),
    ("nosebleed", ["nosebleed", "my nose dey bleed", "nose bleeding often", "bleeding nose"],
     "A one-off nosebleed usually settles with simple first aid, but bleeding that keeps coming "
     "back should be looked at — book into ENT. If a nosebleed won't stop now, come straight to "
     "Accident & Emergency.",
     "One-time nosebleed dey usually settle with simple first aid, but the one wey dey come back "
     "every time suppose see doctor — book ENT. If nosebleed no gree stop now, come straight to A&E.",
     _CTA_DESK),
    ("foreign_object", ["something stuck in ear", "something in nose", "child put bead in ear", "insect in ear"],
     "If something is stuck in an ear or nose — a bead, a button, an insect — please don't poke "
     "or pull it. Come in and the team will remove it safely with the right instruments; "
     "children are handled gently and quickly.",
     "If something stuck for ear or nose — bead, button, insect — abeg no poke am or pull am. Come "
     "make the team remove am safe with the right instrument; pikin go handle am gentle and quick.",
     _CTA_DESK),
    ("sinus", ["sinus problem", "blocked nose always", "catarrh", "sinusitis"],
     "A nose that's always blocked, facial pressure and stubborn catarrh are routine ENT "
     "questions. The doctor will examine and talk through what will actually help, rather than "
     "you cycling through counter medicines on your own.",
     "Nose wey dey block every time, face pressure and stubborn catarrh na normal ENT matter. The "
     "doctor go examine and talk wetin go really help — instead make you dey cycle counter "
     "medicine alone.",
     _CTA_BOOK),
    ("cost", ["ent cost", "how much is ent clinic", "hearing test price", "ent fee"],
     "ENT fees depend on the visit and any tests — I'd rather not guess. The billing desk will "
     "give you the figure for your visit before anything is booked.",
     "ENT fee depend on the visit and any test — I no go guess. Billing desk go give you the "
     "figure for your visit before dem book anything.",
     _CTA_DESK),
    ("hours", ["ent opening hours", "ent clinic hours", "when is ent clinic", "ent today"],
     "The ENT clinic runs on weekdays — the booking page shows today's slots. Urgent ear, nose "
     "or throat problems outside those hours go through Accident & Emergency, open 24/7.",
     "ENT clinic dey run weekday — booking page dey show today slots. Urgent ear, nose or throat "
     "wahala outside those hours dey go through A&E, wey dey open 24/7.",
     _CTA_BOOK),
    ("where", ["where is ent clinic", "ent location", "ent direction", "where ent dey"],
     "Ask at reception and they'll walk you to the ENT clinic, or check the location shown with "
     "your appointment on the booking page. The audiology unit is signposted from the same place.",
     "Ask for reception and dem go walk you go ENT clinic, or check the location wey dey show "
     "with your appointment for booking page. The audiology unit dey signpost from the same place.",
     _CTA_DESK),
    ("complaint", ["ent complaint", "complain about ent", "ent clinic problem", "ent no well"],
     "I'm sorry your ENT visit wasn't right. Please raise it on the complaint form in this app "
     "so it reaches the clinic lead and the hospital complaint desk, or speak to the nurse in "
     "charge before you leave.",
     "I dey sorry say your ENT visit no go well. Abeg raise am for the complaint form for this "
     "app make e reach clinic lead and the hospital complaint desk, or talk to the nurse in "
     "charge before you comot.",
     _CTA_DESK),
])

_SHORT = {
    "Internal Medicine": ["internal medicine", "physician", "medical clinic"],
    "Surgery": ["surgery", "surgical", "surgeon", "operation"],
    "Obstetrics & Gynaecology": ["obstetrics", "gynaecology", "gynecology", "o and g",
                                 "maternity", "antenatal", "anc"],
    "Laboratory": ["laboratory", "lab", "blood test"],
    "Orthopaedics": ["orthopaedics", "orthopedics", "orthopaedic", "bone clinic"],
    "Public Health": ["public health", "immunisation", "immunization", "vaccination"],
    "Health Information Management (HIMS)": ["hims", "medical records", "records office",
                                             "health information"],
    "Finance & Accounts": ["finance", "accounts", "billing", "cash office"],
    "Administration & Human Resources": ["administration", "admin office", "human resources",
                                         "hr"],
    "Environmental Health": ["environmental health", "sanitation", "cleaning"],
    "ICT": ["ict", "it department", "computer"],
    "Engineering & Maintenance": ["engineering", "maintenance"],
    "Security": ["security"],
    "Internal Audit": ["internal audit", "audit"],
    "Planning, Research & Statistics": ["planning", "research", "statistics"],
    "Public Affairs": ["public affairs", "public relations", "enquiries"],
    "Laundry": ["laundry", "linen"],
    "Nursing Services": ["nursing", "nurse", "matron", "apex nurse"],
    "Paediatrics": ["paediatrics", "pediatrics", "children clinic", "child health"],
    "Dental Services": ["dental", "dentist", "tooth"],
    "Ophthalmology (Eye Clinic)": ["ophthalmology", "eye clinic", "eye"],
    "ENT (Ear, Nose & Throat)": ["ent", "ear nose throat", "ent clinic"],
    "Radiology / Imaging": ["radiology", "imaging", "x ray", "xray", "scan", "ultrasound"],
    "Family Medicine / General Outpatient": ["family medicine", "general outpatient", "gopd",
                                             "general clinic", "outpatient"],
    "Catering Services": ["catering", "kitchen", "patient food", "meals"],
}


def _slug(name: str) -> str:
    out = []
    for ch in name.lower():
        out.append(ch if ch.isalnum() else "_")
    return "_".join(x for x in "".join(out).split("_") if x)[:28]


def _build() -> list[dict]:
    rows: list[dict] = []
    for dept, exchanges in DEPT_DIALOGUES.items():
        shorts = _SHORT.get(dept, [dept.lower()])
        for suffix, triggers, en, pcm, cta in exchanges:
            kw = list(triggers)
            # department-qualified variants, so the dept name alone routes correctly
            for s in shorts:
                kw.append(s)
                for t in triggers[:2]:
                    kw.append(f"{s} {t}")
                    kw.append(f"{t} {s}")
            rows.append(dict(
                cat=f"dept_{_slug(dept)}",
                intent=f"{_slug(dept)}_{suffix}",
                kw=sorted({k.strip().lower() for k in kw if k and k.strip()}),
                en=en, pcm=pcm, cta=cta,
            ))
    return rows


KB = _build()
