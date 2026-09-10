"""GLOBAL MASTER DIALOGUE LIBRARY — Part 1 (core patient journey).

Written to a premium patient-experience standard: warm, confident, empathetic,
contractions, light reassurance, ends with a soft low-friction call-to-action,
and NEVER diagnoses or prescribes. Pidgin alongside English; Yoruba/Hausa/Igbo
on core intents. Keywords are conversation triggers (500+ across the library).
"""

KB = [
# ---------------------------------------------------------------- GREETINGS
dict(cat="greetings", intent="greet", kw=[
    "hello","hi","hey","good morning","morning","good afternoon","afternoon","good evening",
    "evening","how far","how far na","greetings","salut","welcome","good day","how do you do",
    "hello there","hi there","how are you today","greetings to you","nice day"],
 en="Hello, and a very warm welcome! I'm your hospital care assistant, and I'm really glad you're here. Whether you're booking a visit, checking a bill, or just finding your way around, I've got you. How can I make your day easier?",
 pcm="How far! Welcome o. Na me be your hospital care assistant, and I dey here to help you well well. Wetin you dey find today — booking, bill, or direction? Make we do am together.",
 yo="Ẹ nílẹ̀! A dúpẹ́ pé o wá. Èmi ni olùrànlọ́wọ́ aláìsàn rẹ — kí ni mo lè ṣe fún ọ lónìí?",
 ha="Sannu! Barka da zuwa. Ni ne mai taimaka muku a asibiti. Me za mu iya yi muku yau?",
 ig="Nnọọ! Anyị nwere obi ụtọ na ị bịara. Abụ m onye enyemaka gị — kedu ka m ga-esi nyere gị aka taa?",
 cta="Tell me what you need — booking, bills, directions, or anything at all."),
dict(cat="greetings", intent="how_are_you", kw=[
    "how are you","how are you doing","you okay","are you fine","how is it going","hows it going",
    "you dey there","you dey ok","are you there","are you a robot","who are you","what are you"],
 en="I'm doing wonderfully, thank you for asking — that's so kind of you! I'm the hospital's care assistant, here day and night to make things simple for you and your family. What can I help you with right now?",
 pcm="I dey fine o, thank you! You too dey kind to ask. Na me be the hospital care assistant, I dey here morning and night to make things easy for you. Wetin go help you now?",
 cta="Ask me anything — I'm listening."),
dict(cat="greetings", intent="thanks", kw=[
    "thank you","thanks","thank you very much","thanks a lot","i appreciate","appreciate it",
    "you are helpful","very helpful","that helps","great thanks","many thanks","you too much",
    "na so","well done","good job","perfect","awesome"],
 en="You're so welcome — it's genuinely my pleasure to help. Seeing you sorted is exactly why I'm here. Is there anything else I can take off your plate today?",
 pcm="You don welcome o! Na my pleasure to help you. If anything else dey your mind, just talk.",
 cta="If anything else comes to mind, just say the word."),
dict(cat="greetings", intent="goodbye", kw=[
    "bye","goodbye","see you","see you later","later","good night","i have to go","that is all",
    "nothing else","no more questions","take care","farewell","i am leaving"],
 en="Take good care of yourself — it's been a pleasure assisting you. We're always here for you and your family, any day, any time. See you soon!",
 pcm="Take care o! E don sweet to help you. We dey here always for you and your family, any day any time. Bye bye, see you soon!",
 cta="Come back anytime — even just to say hello."),

# ---------------------------------------------------------------- APPOINTMENTS
dict(cat="appointments", intent="book_appointment", kw=[
    "book appointment","book a visit","make appointment","schedule appointment","i want to book",
    "appointment","book now","reserve","get appointment","see a doctor","see doctor","consult",
    "i need a doctor","want to see doctor","fix appointment","arrange visit","come in tomorrow",
    "when can i come","book me","make booking"],
 en="I'd love to get you booked in — it only takes a minute. Open the booking page in this reply, pick the place you need (Fast Track is at the top), and you will get a reference number straight away. If you'd rather talk to a person, say talk to a human.",
 pcm="No wahala. Open the booking page for this reply, pick the place you need (Fast Track dey for top), and you go collect your number immediately. If you prefer make person talk to you, talk talk to a human.",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="appointments", intent="fast_track", kw=[
    "fast track", "fasttrack", "fast-track", "gold lane", "executive lounge",
    "be seen faster", "skip the queue", "premium queue", "priority lane",
    "executive booking", "seen quickly", "quiet lounge"],
 en="Fast Track is our quiet gold lane. You pay a little more and you are seen faster. Open Book Fast Track to pick a day, or Get a number at the hospital and choose Fast Track at the top of the list.",
 pcm="Fast Track na our quiet gold lane. You pay small extra, dem go see you faster. Open Book Fast Track to pick day, or Get a number for hospital and choose Fast Track for top of the list.",
 cta="Open Book Fast Track or Get a number."),
dict(cat="appointments", intent="reschedule", kw=[
    "reschedule","change appointment","move appointment","postpone","shift my visit","new date",
    "change date","can i change","rebook","cancel and rebook","adjust appointment"],
 en="Of course — life happens, and we're happy to move things for you. The quickest way is to cancel and rebook online, or I can pass you to the front desk who'll adjust it in one call. Which date were you hoping for?",
 pcm="E no be problem at all, we go shift am for you. The fast way na to cancel and book again online, or make I pass you give front desk, go change am with one call. Which date you wan?",
 cta="Open Book a visit to pick a fresh slot."),
dict(cat="appointments", intent="cancel_appointment", kw=[
    "cancel appointment","cancel my visit","i cant come","i can't make it","not coming","cancel booking",
    "annul","withdraw appointment","skip my visit"],
 en="No problem at all. You can cancel using your booking reference on the status page, and there's no penalty for letting us know early.",
 pcm="No wahala. Fit cancel with your booking number for the status page, and no penalty if you tell us early.",
 cta="Open Check a booking to cancel."),
dict(cat="appointments", intent="check_appointment", kw=[
    "check appointment","my appointment","appointment status","when is my appointment","confirm booking",
    "do i have appointment","appointment time","what time is my visit","verify booking"],
 en="Happy to check that for you. Put your booking reference and phone number into the status page and it will show everything instantly. If anything looks off, the front desk will sort it.",
 pcm="Put your booking number and phone number for the status page, e go show you everything sharp sharp. If anything no correct, front desk go fix am.",
 cta="Open Check a booking."),

# ---------------------------------------------------------------- BILLS & INSURANCE
dict(cat="bills", intent="bill_explain", kw=[
    "my bill","explain bill","breakdown of bill","why am i charged","understand my bill","bill details",
    "what is this charge","hospital bill","invoice","receipt","charges on my bill"],
 en="I completely understand wanting clarity on your bill — you deserve to know exactly what you're paying for. The billing desk can walk you through every line in plain language. Ask them for an itemised breakdown.",
 pcm="I understand say you wan know wetin you dey pay for — na your right. Billing desk fit explain every line well well. Ask dem for full breakdown.",
 cta="Ask the billing desk for a line-by-line breakdown."),
dict(cat="bills", intent="bill_estimate", kw=[
    "how much","cost","price","how much is","fees","charge for","estimate","how much will","price list",
    "cost of","charges","tariff","rate","billing rates","package price"],
 en="Great question. Costs vary by service, so the honest figure comes from the billing desk before you proceed. I will not guess a price.",
 pcm="Correct question o! Price dey change depending on the service. Billing desk go give you exact figure. I no go guess price.",
 cta="Ask the billing desk for the figure — I will not guess a price."),
dict(cat="bills", intent="bill_payment", kw=[
    "how to pay","pay bill","payment","pay my bill","payment methods","card payment","transfer",
    "pos","pay online","how do i settle","settle bill","make payment",
    "how do i pay","how can i pay","where do i pay","how to make payment","mode of payment",
    "do you take card","do you accept transfer","can i pay with card"],
 en="Paying is quick and flexible — we accept card, bank transfer, and POS at the billing desk, and you'll always get a proper receipt.",
 pcm="Payment easy o — we dey accept card, transfer, and POS for billing desk, and go collect proper receipt.",
 cta="Pay at the billing desk — card, transfer or POS."),
dict(cat="bills", intent="insurance_nhis", kw=[
    "nhis","insurance","health insurance","hmo","my hmo","insurance cover","does insurance","enrolment",
    "nhia","health plan","insurance card","cover me"],
 en="Yes — we work with NHIS and most health maintenance organisations. Bring your enrolment card or ID and the desk will verify it before you're seen. I cannot check a named plan from this chat.",
 pcm="Yes o! We dey work with NHIS and plenty HMO. Carry your card or ID make desk verify am before dem see you. I no fit check one plan from this chat.",
 cta="Bring your card to the desk — I cannot look up a plan here."),
dict(cat="bills", intent="bill_dispute", kw=[
    "wrong charge","overcharged","dispute bill","this is too much","i was charged wrongly","billing mistake",
    "double charge","incorrect bill","complain about bill","refund"],
 en="I'm really sorry if something on your bill looks off — that's not the experience we want for you. Please send it as a complaint so the billing team must answer it, with a reference you can track.",
 pcm="I dey sorry if anything for your bill no correct. Abeg send am as complaint so billing team must answer, with a number you fit track.",
 cta="Open Make a complaint to dispute a bill."),

# ---------------------------------------------------------------- HOURS & LOCATION
dict(cat="hours", intent="hours_clinic", kw=[
    "opening hours","hours","what time do you open","closing time","when do you close","working hours",
    "clinic hours","are you open","open now","open today","open on saturday","weekend hours","operating hours"],
 en="We're open Monday to Friday from 8am to 6pm, and Saturday mornings from 8am to 1pm — and our emergency unit never closes, day or night. If you're planning a visit, mornings are usually the calmest.",
 pcm="We dey open Monday to Friday 8am to 6pm, and Saturday morning 8am to 1pm — and our emergency no dey close at all, day and night. If you dey plan to come, morning usually calm.",
 yo="A ṣí ní 8 àárọ̀ dé 6 irọ̀lẹ́ ní ọjọ́ ìṣẹ́; ẹ̀yà ìjàmbá wa ṣí ní alẹ́ àti ọ̀sán.",
 ha="Muna buɗewa daga 8 na safe zuwa 6 na yamma a ranakun aiki; sashen gaggawa ba ya rufe ko da yaushe.",
 ig="Anyị na-epe site na 8 nke ututu ruo 6 nke mgbede; ngalaba mberede anaghị emechi.",
 cta="Open Book a visit if you want a morning slot."),
dict(cat="hours", intent="hours_emergency", kw=[
    "is emergency open","emergency hours","a and e hours","casualty hours","emergency at night","24 hours",
    "night emergency","emergency open now"],
 en="Yes — Accident & Emergency is open 24 hours, every single day of the year, including holidays. If someone needs urgent help right now, please come straight in or call an ambulance; don't wait for morning.",
 pcm="Yes o! A&E dey open 24 hours, every day, even holiday. If person need urgent help now now, abeg come straight or call ambulance; no wait morning.",
 cta="If it's urgent, go to A&E now — it is open day and night."),
dict(cat="hours", intent="directions", kw=[
    "where is","directions","how do i get","locate","find the hospital","address","where are you located",
    "map","how to reach","which street","landmark","where is your hospital"],
 en="We'd love to welcome you in person. The hospital homepage has our address, and the reception team can guide you the moment you arrive. I cannot text a map from this chat.",
 pcm="Hospital homepage get our address, and reception go guide you the moment you reach. I no fit text map from this chat.",
 cta="Open Hospital home for the address."),

# ---------------------------------------------------------------- FIRST VISIT
dict(cat="first_visit", intent="first_visit_steps", kw=[
    "first time","first visit","i have never been","new patient","first time coming","how does it work",
    "what happens when i come","first appointment","new here","never visited"],
 en="Welcome — first visits can feel like a lot, so here's the simple path: check in at reception with any ID, get your folder opened, then head to the department on your slip. A staff member is always nearby if you feel stuck.",
 pcm="Welcome o! First visit fit feel like plenty: check in for reception with any ID, dem go open your folder, then you go go the department wey dey your slip. Staff dey always near if you confuse.",
 cta="Open Book a visit if you want a slot waiting."),
dict(cat="first_visit", intent="first_visit_bring", kw=[
    "what to bring","what should i bring","bring what","documents needed","do i need id","what do i need",
    "folder","medical records","previous results","carry what"],
 en="Smart to ask! Please bring any ID, your previous results or scans if you have them, and a list of any medicines you currently take. If it's your first time, we'll open a fresh folder for you on the spot. Anything else you'd like me to check?",
 pcm="Correct question! Abeg carry any ID, your old results or scan if you get, and list of medicine wey you dey take. If na first time, go open new folder for you on the spot. Anything else you wan make I check?",
 cta="Open Book a visit when you are ready."),

# ---------------------------------------------------------------- SERVICES
dict(cat="services", intent="services_overview", kw=[
    "services","what services","what do you offer","departments","what can you do","facilities",
    "list of services","do you have","specialist","clinics available","units"],
 en="We offer a full range of care — from outpatient clinics and diagnostics (lab, imaging) to surgery, maternity, paediatrics, and a 24/7 emergency unit. Think of us as your family's one-stop health home. Which area are you curious about?",
 pcm="We get full care o — from OPD and lab/imaging to surgery, maternity, children ward, and emergency wey dey open 24/7. Think of us as your family one-stop health house. Which area you wan know about?",
 cta="Name a department and I will share the written details we have."),

# ---------------------------------------------------------------- COMPLAINTS
dict(cat="complaints", intent="complaint_start", kw=[
    "i want to complain","complaint","make a complaint","i have a complaint","report issue","bad service",
    "not happy","unhappy","mistreat","rude staff","poor service","something went wrong","i was treated badly",
    "was rude","were rude","rude to me","shouted at me","ignored me","nobody attended to me",
    "kept me waiting","no one helped me","treated me badly","very rude","so rude"],
 en="I'm truly sorry your experience fell short — that matters to us. Open Make a complaint, write what happened in your own words, and you will get a reference to track it. I cannot take the complaint here in chat.",
 pcm="I dey sorry well well say your experience no good. Open Make a complaint, write wetin happen, and you go collect number to track am. I no fit take the complaint for this chat.",
 cta="Open Make a complaint."),
dict(cat="complaints", intent="complaint_status", kw=[
    "complaint status","track complaint","my complaint","where is my complaint","complaint update",
    "has my complaint","complaint reference","follow up on complaint"],
 en="Let's get you an update. Put your complaint reference and phone number into the status page and you'll see exactly where it stands. If it's escalated, you'll see that too.",
 pcm="Put your complaint number and phone for the status page, go see exactly where e stand. If e don escalate, go see am too.",
 cta="Open Check a complaint."),

# ---------------------------------------------------------------- EMERGENCY & TRIAGE
dict(cat="emergency", intent="emergency_general", kw=[
    "emergency","accident","urgent","help now","emergency room","a and e","casualty","injury","bleeding",
    "crash","faint","unconscious","severe pain","emergency care"],
 en="Please don't wait — come straight to our Accident & Emergency unit; it's open 24/7 and the team is ready for you right now. If the person can't be moved, call an ambulance immediately.",
 pcm="Abeg no wait o — come straight our A&E; e dey open 24/7 and the team don ready for you now now. If the person no fit move, call ambulance immediately.",
 cta="Go to A&E now."),
dict(cat="emergency", intent="emergency_chest", kw=[
    "chest pain","heart","difficulty breathing","can't breathe","shortness of breath","stroke","numb face",
    "sudden weakness","collapse","heavy chest","crushing chest"],
 en="This sounds like it needs urgent medical attention — please treat it as an emergency. Come to A&E immediately or call an ambulance now; do not drive yourself if you feel unwell. Our team is ready for you. I'm staying with you — are you able to get moving now?",
 pcm="This one na urgent o — abeg treat am as emergency. Come A&E immediately or call ambulance now now; no drive yourself if you no feel fine. Our team don ready. I dey with you — you fit move now?",
 cta="Please go to A&E now — do not wait."),
dict(cat="triage", intent="triage_explain", kw=[
    "triage","what is triage","why am i waiting","waiting long","queue at emergency","sorting patients",
    "who gets seen first","priority"],
 en="Totally understand — waiting is the hardest part, and I appreciate your patience. Triage means the most critical patients are seen first for everyone's safety, which is why waits can vary. Your turn is coming, and I've noted your wait. Can I get you a seat or water meanwhile?",
 pcm="I understand o — waiting na the hardest part, and I appreciate your patience. Triage mean say the ones wey dey critical dem go see first for everybody safety, na why waiting fit change. Your turn dey come, and I don note your wait. Make I find you seat or water meanwhile?",
 cta="If you feel worse while waiting, tell any staff immediately — they'll fast-track you."),

# ---------------------------------------------------------------- ADMISSION & DISCHARGE
dict(cat="admission", intent="admission_process", kw=[
    "admission","admit","being admitted","how does admission","admission process","stay overnight",
    "getting admitted","ward admission"],
 en="We'll make admission as smooth as possible for you. Once your doctor recommends it, the desk handles your folder and ward placement, and we'll explain everything before you settle in. A family member can stay close during the process. Ask the desk what to pack for your ward.",
 pcm="Go make admission smooth for you. Once your doctor recommend am, desk go handle your folder and ward, and dem go explain everything before you settle. Family member fit stay near during the process. Ask the desk wetin to pack.",
 cta="Ask the ward desk what to pack."),
dict(cat="admission", intent="visiting_hours", kw=[
    "visiting hours","visit a patient","when can i visit","visitation","see a patient","ward visiting",
    "can i visit","visitors allowed"],
 en="We love involved families — visiting hours are usually 10am to 7pm daily, with a limit of two visitors at a time so patients rest well. The ICU has shorter, guided windows for safety. Ask the ward desk for the exact window for that ward.",
 pcm="We dey love family wey dey involved o — visiting hours na usually 10am to 7pm every day, with two visitors at a time so patient go fit rest well. ICU get shorter window for safety. Ask the ward desk for the exact window.",
 cta="Ask the ward desk for visiting times."),
dict(cat="discharge", intent="discharge_process", kw=[
    "discharge","going home","leaving hospital","discharge process","when will i be discharged",
    "getting out","released"],
 en="We're as excited as you are to get you home! Discharge happens once your care team confirms you're ready; the desk will settle your bill and hand over your papers and any follow-up dates. Open Book a visit if you want a review date before you leave.",
 pcm="We dey happy like you say you dey go home! Discharge go happen once your care team confirm say you don ready; desk go settle your bill and give you your papers and follow-up dates. Open Book a visit if you wan review date before you comot.",
 cta="Open Book a visit for your review."),
dict(cat="discharge", intent="aftercare", kw=[
    "after discharge","care at home","recovering at home","post discharge","wound care at home",
    "what to do at home","recovery tips","after surgery care"],
 en="Recovering well at home is our shared goal. Follow your discharge sheet closely, take medicines exactly as written, and keep your follow-up date. If anything worries you — fever, swelling, or unusual pain — come back or call us; we'd rather see you early.",
 pcm="Make you recover well for home na our goal. Follow your discharge sheet well, take your medicine exactly as dem write am, and keep your follow-up date. If anything worry you — fever, swelling, or pain wey no normal — come back or call us; we prefer make we see you early.",
 cta="Open Book a visit if you need a review date."),

# ---------------------------------------------------------------- FOLLOW-UP
dict(cat="followup", intent="followup_book", kw=[
    "follow up","follow-up","review appointment","come back for check","post treatment check",
    "book follow up","review date","next visit"],
 en="Keeping your follow-up is one of the best things you can do for your health — well done for staying on top of it. Open Book a visit, pick the department and a day that suits you. Mornings tend to be quieter.",
 pcm="Make you keep your follow-up na one of the best thing you fit do for your health — well done! Open Book a visit, pick the department and the day wey suit you. Morning usually calm.",
 cta="Open Book a visit for your review."),
]
