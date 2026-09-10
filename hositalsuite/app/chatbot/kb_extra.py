"""GLOBAL MASTER DIALOGUE LIBRARY — Part 3 (support services & extras).

Broadens trigger coverage (pushes the library past 500 triggers) and adds
high-frequency support topics a 25-year front-desk expert knows patients ask.
"""

KB = [
dict(cat="pharmacy", intent="pharmacy", kw=[
    "pharmacy","drug store","medicine collection","collect drugs","prescription","refill",
    "pharmacy hours","get my drugs","medication collection","drug pickup","pharmacy queue"],
 en="Our pharmacy team is quick and careful with every prescription. You can collect your medicines at the pharmacy window with your prescription slip, and our pharmacists will happily explain how to take each one. Shall I check the current pharmacy queue for you?",
 pcm="Our pharmacy team quick and careful with every prescription. Fit collect your medicine for pharmacy window with your slip, and the pharmacists go happy explain how to take each one. Make I check the pharmacy queue for you?",
 cta="If a medicine is unclear, ask the pharmacist before you leave — they love helping."),
dict(cat="records", intent="medical_records", kw=[
    "medical records","my folder","health records","get my records","medical report","card","patient folder",
    "retrieve records","copy of results","medical history"],
 en="Your records are safe with us, and you're entitled to access them. The records desk can prepare a copy of your results or a medical report; some requests need a short processing time and valid ID. Would you like me to start the request for you?",
 pcm="Your records dey safe with us, and na your right to see dem. Records desk fit prepare copy of your results or medical report; some request need small time and valid ID. You wan make I start the request for you?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="support", intent="wheelchair_access", kw=[
    "wheelchair","disabled","accessibility","ramp","can't walk","elderly","stretcher","mobility",
    "physically challenged","help to move"],
 en="We've got you covered — wheelchairs and staff assistance are available free at the reception, and our facilities have ramps for easy movement. Just let me know when you're arriving and I'll have someone ready at the door for you.",
 pcm="We get you o — wheelchair and staff assistance dey free for reception, and our place get ramp for easy movement. Just tell me when you dey come and go make person ready for door for you.",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="support", intent="ambulance", kw=[
    "ambulance","call ambulance","need ambulance","ambulance service","pick up patient","transport patient",
    "ambulance number","emergency transport"],
 en="Yes — we operate an ambulance service for emergencies and transfers. If someone is in danger right now, please call immediately rather than chat; every minute matters. For a planned transfer, I can help you book it. Is this an emergency or a planned transfer?",
 pcm="Yes o — we get ambulance service for emergency and transfer. If person dey in danger now now, abeg call immediately, no chat; every minute matter. For planned transfer, I fit help you book am. Na emergency or planned transfer?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="support", intent="wellness_check", kw=[
    "check up","general check up","health screening","wellness","full body check","annual check",
    "medical check up","screening package","executive check"],
 en="A general check-up is one of the best gifts you can give yourself — many conditions are silent until screened. Our wellness package covers vitals, bloods, and a doctor's review, with clear next steps. Shall I book you a check-up this week?",
 pcm="General check-up na one of the best gift you fit give yourself — plenty conditions no dey show till dem screen. Our wellness package cover vitals, blood, and doctor review, with clear next steps. Make I book you check-up this week?",
 cta="Mornings are ideal for fasting tests — want a morning slot?"),
dict(cat="support", intent="blood_donation", kw=[
    "donate blood","blood donation","give blood","blood drive","donor","blood bank"],
 en="Thank you for wanting to give the gift of life — donors like you save families every day. Our blood bank will screen you quickly and treat you to refreshments after. Would you like me to book a donation slot?",
 pcm="Thank you say you wan give the gift of life — donors like you dey save families every day. Our blood bank go screen you quick and give you refreshment after. You wan make I book donation slot?",
 cta="You're a hero — let's get you booked."),
dict(cat="support", intent="second_opinion", kw=[
    "second opinion","another doctor","different doctor","second doctor","other specialist","another opinion"],
 en="Seeking a second opinion is a wise and completely normal step — we encourage it. I can arrange a consultation with another specialist and share your records with them so you don't repeat tests. Which area would you like reviewed?",
 pcm="To look for second opinion na wise and normal step o — we dey encourage am. I fit arrange consultation with another specialist and share your records with dem so you no go repeat tests. Which area you wan make dem review?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="support", intent="mental_wellbeing", kw=[
    "stress","anxiety","depression","counselling","counseling","mental health","feel overwhelmed","sad",
    "talk to someone","emotional support"],
 en="Thank you for trusting me with that — how you feel matters as much as your physical health. Our counsellors offer a private, judgement-free space, and talking truly helps. Would you like me to book a confidential counselling session for you?",
 pcm="Thank you say you trust me with that — how you feel matter just like your body health. Our counsellors dey give private, no-judgement space, and to talk dey really help. You wan make I book confidential counselling for you?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="departments", intent="physiotherapy", kw=[
    "physiotherapy","physio","rehab","rehabilitation","physical therapy","exercise therapy","post stroke rehab",
    "physio appointment"],
 en="Our physiotherapy team helps you regain strength and mobility after injury, surgery, or stroke, with a personalised plan and lots of encouragement. Sessions are by appointment so you're never kept waiting. Shall I book your physio session?",
 pcm="Our physio team dey help you gain strength and movement back after injury, surgery, or stroke, with personal plan and plenty encouragement. Sessions dey by appointment so dem no go keep you waiting. Make I book your physio session?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="departments", intent="nutrition", kw=[
    "nutrition","dietician","diet","meal plan","diabetic diet","food advice","nutritionist","weight management"],
 en="Good nutrition is medicine too! Our dietitians create practical, affordable meal plans that fit your culture and your budget — for diabetes, hypertension, weight, or pregnancy. Would you like a nutrition consultation?",
 pcm="Good nutrition na medicine too o! Our dietitians dey create practical, affordable meal plan wey fit your culture and your budget — for diabetes, BP, weight, or pregnancy. You wan nutrition consultation?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="support", intent="lost_found", kw=[
    "i lost","left my","forgot my","lost property","left something","missing item","my bag","left my phone",
    "lost and found"],
 en="Don't worry — items left behind are kept safely at the front desk and logged. Tell me what you left and roughly where, and I'll have the desk check for you right now. What item are we looking for?",
 pcm="No worry o — things wey people leave dey keep safe for front desk and dem dey log am. Tell me wetin you leave and roughly where, and go make the desk check for you now now. Which item we dey find?",
 cta="Ask the front desk, or say talk to a human."),
]
