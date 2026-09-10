"""GLOBAL MASTER DIALOGUE LIBRARY — Part 2 (departments, surgery, ANC, terminology)."""

KB = [
# ---------------------------------------------------------------- ANC / MATERNITY
dict(cat="maternity", intent="anc_book", kw=[
    "anc","antenatal","antenatal booking","book anc","pregnancy care","prenatal","maternity booking",
    "i am pregnant","expecting","first pregnancy","pregnant booking","anc clinic"],
 en="Congratulations — that's wonderful news, and we'd be honoured to walk this journey with you! ANC booking is quick: bring any ID and your previous records if you have them. Our midwives are gentle, thorough, and happy to answer every question. Shall I book your first ANC visit?",
 pcm="Congratulations o! Na wonderful news, and go honour us to waka this journey with you. ANC booking quick: carry any ID and your old records if you get. Our midwives dey gentle, thorough, and dem go happy answer all your questions. Make I book your first ANC visit?",
 yo="Ìgba àlàáfíà! A ó tọ́jú rẹ dáadáa. Mú ID rẹ wá; ṣé kí n gbé ìpàdé ANC sílẹ̀ fún ọ?",
 ha="Murna! Za mu kula ku kyau. Kawo ID ɗinku; za a iya ajiye lokacin ANC na farko?",
 ig="Ekele! Anyị ga-elekọta gị nke ọma. Weta ID gị; ị chọrọ ka m debe gị oge ANC mbụ?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="maternity", intent="anc_expect", kw=[
    "what happens at anc","anc visit","first anc visit","anc check","pregnancy checkup","what to expect at anc",
    "anc tests","pregnancy tests"],
 en="Your ANC visit is friendly and unrushed: we check your blood pressure, weight, and the baby's growth, run routine tests, and give you clear advice for the weeks ahead. You'll leave knowing exactly what to expect next. Is there anything specific you'd like us to look at?",
 pcm="Your ANC visit go friendly and no rush: dem go check your BP, weight, and the baby growth, run normal tests, and give you clear advice for the weeks wey dey come. Go leave knowing exactly wetin dey next. Anything specific wey you wan make dem look?",
 cta="If you're nervous, say so — our midwives are lovely with first-timers."),
dict(cat="maternity", intent="anc_danger", kw=[
    "bleeding in pregnancy","pregnancy bleeding","severe headache pregnancy","swelling pregnancy",
    "reduced movement","baby not moving","pregnancy pain","pregnancy emergency"],
 en="Thank you for telling me — please treat this as urgent. Come to our maternity emergency right away, or call an ambulance if you can't travel safely. Our team is ready for you and baby. Are you able to get moving now? I'll alert the maternity unit.",
 pcm="Thank you for telling me — abeg treat am as urgent. Come our maternity emergency now now, or call ambulance if you no fit travel safe. Our team don ready for you and baby. You fit move now? Go alert maternity unit.",
 cta="Please come in now — I'm letting the team know to expect you."),

# ---------------------------------------------------------------- SURGERY
dict(cat="surgery", intent="surgery_dos", kw=[
    "surgery do's","before surgery","what to do before surgery","surgery preparation","prepare for surgery",
    "pre surgery","before operation","surgery instructions"],
 en="You're in safe hands, and a little preparation makes everything smoother. Do's: fast exactly as instructed, take only the medicines your team approved, bring your records and a list of your medicines, and arrange for someone to take you home. Want me to send you the full checklist?",
 pcm="You dey safe hands o, and small preparation go make everything smooth. Do's: fast exactly as dem talk, take only the medicine wey your team approve, carry your records and list of your medicine, and arrange person to carry you go home. You wan make I send you the full checklist?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="surgery", intent="surgery_donts", kw=[
    "surgery don'ts","what not to do before surgery","avoid before surgery","can i eat before surgery",
    "smoke before surgery","eat before operation","drink before surgery"],
 en="Great to check first — here are the key don'ts: don't eat or drink anything unless your team says otherwise, don't smoke or drink alcohol in the days before, and don't take herbal mixtures or unprescribed medicines. When in doubt, call us before you take anything. Shall I confirm your fasting time?",
 pcm="Correct to check first o — na the key don'ts: no eat or drink anything except your team talk otherwise, no smoke or drink alcohol for the days before, and no take herbal mixture or medicine wey dem no prescribe. If you doubt, call us before you take anything. Make I confirm your fasting time?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="surgery", intent="surgery_after", kw=[
    "after surgery","post surgery care","recovering after operation","wound care","stitches care",
    "after operation","surgery recovery"],
 en="Recovery is a team effort and you're doing your part just by asking. Follow your discharge sheet, keep the wound clean and dry, take medicines exactly as written, and don't lift anything heavy until cleared. If you notice bleeding, swelling, or fever, come back right away. Want a follow-up reminder?",
 pcm="Recovery na team work and you don do your part just by asking. Follow your discharge sheet, keep the wound clean and dry, take your medicine exactly as dem write am, and no carry heavy thing till dem clear you. If you see bleeding, swelling, or fever, come back sharp sharp. You wan follow-up reminder?",
 cta="Ask the front desk, or say talk to a human."),

# ---------------------------------------------------------------- LABORATORY
dict(cat="laboratory", intent="lab_prep", kw=[
    "lab test","fasting for lab","blood test","do i fast","lab preparation","before blood test",
    "glucose test","lipid test","lab before","empty stomach lab"],
 en="Good thinking to check before your test. Many blood tests need 8–12 hours of fasting (water is fine), but not all — it depends on the test. Tell me which test you're doing and I'll give you the exact prep. And don't worry, our lab team is quick and gentle.",
 pcm="Correct to check before your test o. Plenty blood test need 8–12 hours fasting (water dey okay), but no be all — e depend on the test. Tell me which test you dey do, go give you the exact prep. And no worry, our lab team quick and gentle.",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="laboratory", intent="lab_results", kw=[
    "lab results","my results","test results","when will results","collect results","results ready",
    "how to get results","check my results"],
 en="I know that waiting for results can be anxious — we try to turn them around fast. Most routine results are ready within 24–48 hours, and you'll be told exactly when to collect or how to receive them. Would you like me to check the status of yours?",
 pcm="I know say waiting for result fit make person tense — we dey try turn am round fast. Most normal results dey ready within 24–48 hours, and dem go tell you exactly when to collect or how dem go send am. You wan make I check the status of your own?",
 cta="Ask the front desk, or say talk to a human."),

# ---------------------------------------------------------------- DENTAL / EYE
# dental & eye now live in the full DEPARTMENT library (kb_departments_full.py — F-042)

# ---------------------------------------------------------------- ICU / NEONATAL / PAEDS
dict(cat="icu", intent="icu_visiting", kw=[
    "icu","intensive care","visit icu","icu visiting","critical care","see icu patient","icu hours"],
 en="We know how worrying it is when a loved one is in ICU, and we're doing everything for them. For their safety, visiting is in short, guided windows with one or two family members at a time. The nursing lead will give you a clear update at each window. Would you like me to find your family's visiting time?",
 pcm="We know say e dey worry person when person wey you love dey ICU, and we dey do everything for dem. For their safety, visiting na short window with one or two family at a time. The nursing lead go give you clear update each window. You wan make I find your family visiting time?",
 cta="Ask the front desk, or say talk to a human."),
# paediatrics now lives in the full DEPARTMENT library (kb_departments_full.py — F-042)

dict(cat="neonatal", intent="neonatal", kw=[
    "nicu","neonatal","newborn","new baby","premature","baby in nicu","visit newborn"],
 en="Congratulations on your new baby, and we understand the worry when they need extra care. Our neonatal team are specialists in tiny patients, and we keep parents closely involved with guided visits and clear updates. Would you like today's update time for your baby?",
 pcm="Congratulations for your new baby o, and we understand the worry when dem need extra care. Our neonatal team na specialist for small patient, and dem dey keep parents involved with guided visit and clear update. You wan today update time for your baby?",
 cta="Ask the front desk, or say talk to a human."),

# ---------------------------------------------------------------- OPD / CLINIC TYPES
dict(cat="terminology", intent="term_opd", kw=[
    "opd","what is opd","outpatient","sopd","mopd","what is sopd","what is mopd","specialist opd",
    "medical opd","outpatient department"],
 en="Happy to demystify! OPD is our Outpatient Department — you're seen and go home the same day. MOPD is Medical OPD (general physician clinics) and SOPD is Surgical OPD (surgeon clinics). No referral needed to start; we'll route you correctly. Which one do you need?",
 pcm="Make I clear am! OPD na our Outpatient Department — dem go see you and you go go home same day. MOPD na Medical OPD (general doctor clinic) and SOPD na Surgical OPD (surgeon clinic). No need referral to start; go route you correct. Which one you need?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="terminology", intent="term_general", kw=[
    "what does","meaning of","what is","define","terminology","medical term","explain term","what is vitals",
    "what is triage meaning","what is admission","what is referral"],
 en="I love making hospital language simple! A referral is a note sending you to a specialist; vitals are your basic checks (temperature, pulse, BP); triage is how we sort patients by urgency. If any term on your paper confuses you, send it to me and I'll translate it into plain language.",
 pcm="I dey love make hospital language simple! Referral na note wey dey send you to specialist; vitals na your basic checks (temperature, pulse, BP); triage na how we sort patient by urgency. If any term for your paper confuse you, send am to me and go translate am to plain language.",
 cta="Ask the front desk, or say talk to a human."),

# ---------------------------------------------------------------- FAMILY PLANNING
dict(cat="family_planning", intent="family_planning", kw=[
    "family planning","contraception","birth control","fp clinic","plan my family","contraceptive",
    "implant","iud","family planning clinic"],
 en="You're welcome to ask us anything about family planning — it's confidential, judgement-free, and our counsellors help you choose what fits your body and your life. Consultations are private and free of pressure. Would you like me to book a private counselling slot?",
 pcm="You fit ask us anything about family planning — e dey confidential, no judgement, and our counsellors go help you choose wetin fit your body and your life. Consultation dey private and no pressure. You wan make I book private counselling slot?",
 cta="Ask the front desk, or say talk to a human."),

# ---------------------------------------------------------------- EQUIPMENT
dict(cat="equipment", intent="equipment", kw=[
    "mri","ct scan","x ray","x-ray","ultrasound","scan","imaging","ecg","machine","dialysis",
    "do you have mri","equipment"],
 en="Yes — we have modern diagnostics on site including X-ray, ultrasound, CT, ECG, and laboratory services, so you won't be sent running around town. Each test has a simple prep, and I'll tell you exactly what to do before yours. Which test are you asking about?",
 pcm="Yes o — we get modern diagnostics for site like X-ray, ultrasound, CT, ECG, and lab, so dem no go send you dey run around town. Each test get simple prep, and go tell you exactly wetin to do before your own. Which test you dey ask about?",
 cta="Open Book a visit — the address is on this reply."),
]
