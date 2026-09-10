"""GLOBAL MASTER DIALOGUE LIBRARY — Part 4 (depth: pushes library to ~1,000 triggers).

Same premium voice; concise warm answers + soft CTA; Pidgin throughout; never
diagnoses. Rich trigger lists include English synonyms, Naija/Pidgin phrasings
and common misspellings so real patients are understood.
"""

KB = [
dict(cat="engagement", intent="compliment", kw=[
    "your staff are great","the nurse was kind","well done team","i love your service","excellent service",
    "thank you nurse","your team is good","great experience","you people are good","commend","appreciate staff",
    "the doctor was wonderful","amazing care","five stars","you deserve praise"],
 en="This just made our day — thank you! I'll pass your kind words straight to the team; recognition like yours is what keeps our staff smiling. May I note the name of the person who helped you so they get the credit?",
 pcm="This one don make our day — thank you! Go pass your kind words go meet the team; na this kind thing dey make our staff dey smile. Make I note the name of the person wey help you make e get the credit?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="engagement", intent="language_switch", kw=[
    "speak yoruba","use yoruba","yoruba please","speak pidgin","use pidgin","pidgin please","speak hausa",
    "hausa please","speak igbo","igbo please","talk my language","change language","english please"],
 en="Absolutely — you can switch my language anytime using the language buttons at the top (English, Yorùbá, Hausa, Igbo, Pidgin). Tap your favourite and I'll speak it. Which shall we use now?",
 pcm="No wahala — you fit change my language any time with the buttons for top (English, Yorùbá, Hausa, Igbo, Pidgin). Tap the one wey you like and go talk am. Which one we go use now?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="operations", intent="doctor_schedule", kw=[
    "which days does the doctor","specialist days","doctor timetable","when is the specialist","consultant day",
    "is the doctor in","doctor schedule","which day is clinic","surgeon day","cardiologist day","gynaecologist day"],
 en="Our specialists run clinics on set days, and I can tell you exactly when the one you need is in. Which specialist or department are you looking for? I'll give you their clinic days so you don't waste a trip.",
 pcm="Our specialists dey run clinic for fixed days, and I fit tell you exactly when the one wey you need dey in. Which specialist or department you dey find? Go give you their clinic days so you no go waste trip.",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="operations", intent="wait_time", kw=[
    "how long is the queue","waiting time","how busy is it","is it busy now","how many people waiting",
    "queue length","will i wait long","how long will i wait","crowded today"],
 en="I appreciate you planning ahead. Queues are usually calmest early morning; right now I can check the live queue for your department so you know what to expect. Which department are you heading to?",
 pcm="I like how you dey plan ahead. Queue usually calm for early morning; right now I fit check the live queue for your department so you know wetin to expect. Which department you dey go?",
 cta="Ask the front desk, or say talk to a human."),

# ---- Maternity depth
dict(cat="maternity", intent="labour_signs", kw=[
    "labour signs","labor signs","water broke","contractions","my waters broke","going into labour",
    "labour pain starting","baby coming","in labour"],
 en="This sounds like it may be starting — congratulations, and well done for being alert! Please come to our maternity unit now; don't wait for it to 'settle'. Bring your ANC card and your hospital bag. We're ready for you and baby. Are you able to get moving?",
 pcm="This one fit don start o — congratulations, and well done say you dey alert! Abeg come our maternity unit now; no wait make e 'settle'. Carry your ANC card and your bag. We don ready for you and baby. You fit move?",
 cta="Go to A&E now if it is urgent — or say talk to a human."),
dict(cat="maternity", intent="breastfeeding", kw=[
    "breastfeeding","breast feeding","latching","my milk","exclusive breastfeeding","nursing","milk supply",
    "baby not latching"],
 en="You're doing one of the best things for your baby — well done! Our lactation team can help with latching, supply, and any soreness, in a private and encouraging space. Would you like me to book you a breastfeeding support session?",
 pcm="You dey do one of the best thing for your baby — well done! Our lactation team fit help with latching, milk, and any soreness, for private and encouraging place. You wan make I book breastfeeding support for you?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="maternity", intent="newborn_jaundice", kw=[
    "baby yellow","jaundice","newborn yellow","baby skin yellow","yellow eyes baby",
    "baby is yellow","my baby is yellow","baby turning yellow","is yellow","looks yellow"],
 en="Thank you for checking — a yellow tint in a newborn should always be seen promptly, and the good news is it's very treatable when caught early. Please bring your baby to our neonatal unit today for a quick check. I'll alert the team for you. Can you come now?",
 pcm="Correct to check o — yellow for newborn suppo be see sharp sharp, and the good news be say e dey very treatable if dem catch am early. Abeg carry your baby come our neonatal unit today for quick check. Go alert the team for you. You fit come now?",
 cta="Please bring baby in today — I'm letting the neonatal team know."),
dict(cat="maternity", intent="immunization_child", kw=[
    "baby immunization","child immunization","vaccine schedule","baby vaccines","polio vaccine","measles vaccine",
    "immunization card","baby injection","vaccination days"],
 en="Protecting your baby is one of the greatest gifts — and it's free at our child-welfare clinic. Bring the child's immunization card and we'll keep them right on schedule, with a gentle team and a little treat after. Shall I book the next immunization?",
 pcm="To protect your pikin na one of the greatest gift — and e dey free for our child-welfare clinic. Carry the pikin immunization card and go keep dem for schedule, with gentle team and small treat after. Make I book the next immunization?",
 cta="Open Book a visit — the address is on this reply."),

# ---- Paediatrics depth
dict(cat="paediatrics", intent="child_fever", kw=[
    "child fever","baby fever","my child is hot","high temperature child","feverish baby","child burning"],
 en="I know a fever in your little one is worrying — you're right to act. For a young baby, or any child who is very drowsy, breathing fast, or not feeding, please bring them in now. For an older, alert child, we can see them today at the children's clinic. How old is your child?",
 pcm="I know say pikin fever dey worry — you correct to act. For small baby, or any pikin wey dey very drowsy, dey breathe fast, or no dey feed, abeg carry am come now. For bigger pikin wey dey alert, we fit see dem today for children clinic. How old the pikin be?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="paediatrics", intent="child_diarrhoea", kw=[
    "child diarrhea","child diarrhoea","baby loose stool","child vomiting","puking child","watery stool child",
    "child dey purge"],
 en="You're doing the right thing by seeking help early — the biggest risk with loose stools is dehydration, so keep offering fluids or ORS if you have it. If your child is very drowsy, sunken-eyed, or not drinking, come in now. Otherwise we'll see you today at the children's clinic.",
 pcm="You dey do the correct thing by seeking help early — the biggest risk with loose stool na dehydration, so keep give am fluids or ORS if you get. If the pikin dey very drowsy, eye don sink, or no dey drink, come now. If not, we go see you today for children clinic.",
 cta="Ask the front desk, or say talk to a human."),

# ---- Labs depth
dict(cat="laboratory", intent="hiv_confidential", kw=[
    "hiv test","hiv testing","aids test","hiv confidential","std test"," hiv","know my status"],
 en="Testing is a brave, caring step — and with us it's completely confidential and judgement-free, with counselling before and after. Results are shared only with you, privately. Would you like me to book a confidential testing slot?",
 pcm="To test na brave, caring step — and with us e dey completely confidential and no judgement, with counselling before and after. Results go share only with you, privately. You wan make I book confidential testing slot?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="laboratory", intent="pregnancy_test", kw=[
    "pregnancy test","test for pregnancy","am i pregnant test","urine pregnancy test","home pregnancy","upt test"],
 en="We do quick, private pregnancy tests at the lab — you'll have your result fast and, whatever it is, we'll guide you kindly on your next steps. No judgement, just support. Shall I arrange it for you now?",
 pcm="We dey do quick, private pregnancy test for lab — go collect your result fast, and anything e be, go guide you kindly for your next steps. No judgement, just support. Make I arrange am for you now?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="laboratory", intent="diabetes_hba1c", kw=[
    "hba1c","diabetes test","sugar test","blood sugar","glucose test","diabetic check","sugar level"],
 en="Keeping an eye on your sugar is smart — our lab runs fasting glucose and HbA1c, and our diabetes clinic will walk you through the result with a practical meal plan. Most sugar tests need an overnight fast; water is fine. Shall I book your test and clinic review together?",
 pcm="To dey watch your sugar na smart thing — our lab dey run fasting glucose and HbA1c, and our diabetes clinic go waka you through the result with practical meal plan. Most sugar test need overnight fast; water dey okay. Make I book your test and clinic review together?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="laboratory", intent="bp_check", kw=[
    "check my bp","blood pressure","bp test","hypertension check","pressure check","my pressure"],
 en="Checking your BP regularly is one of the best habits for a long, healthy life — and it takes five minutes, no fasting needed. Our clinic will read it properly and advise you honestly. Shall I book a BP check for you this week?",
 pcm="To dey check your BP regular na one of the best habit for long healthy life — and e dey take five minutes, no need fasting. Our clinic go read am proper and advise you honestly. Make I book BP check for you this week?",
 cta="Ask the front desk, or say talk to a human."),

# ---- Pharmacy depth
dict(cat="pharmacy", intent="drug_side_effect", kw=[
    "side effect","my medicine dey cause","drug reaction","allergic to medicine","rash after drug","medicine wahala",
    "this drug dey pain my stomach"],
 en="I'm glad you flagged this — reactions to medicine should always be reviewed by a professional, and you should not stop or change a prescription on your own. Please speak to our pharmacist or your doctor today; if you have swelling, rash, or breathing difficulty, treat it as urgent and come in now.",
 pcm="I glad say you flag am — reaction to medicine suppo always be review by professional, and you no suppo stop or change prescription by yourself. Abeg talk to our pharmacist or your doctor today; if you get swelling, rash, or breathing wahala, treat am as urgent and come now.",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="pharmacy", intent="repeat_refill", kw=[
    "refill my drugs","repeat prescription","my chronic drugs","renew my medicine","drug refill","collect monthly drugs"],
 en="We make refills painless for our chronic-care patients — bring your old prescription or folder and we'll have your medicines ready, with a quick check-in to make sure you're doing well. Shall I note your refill so it's ready when you arrive?",
 pcm="We dey make refill painless for our chronic-care patients — carry your old prescription or folder and go make your medicine ready, with quick check-in to make sure you dey fine. Make I note your refill make e ready when you reach?",
 cta="Ask the front desk, or say talk to a human."),

# ---- Dental & eye depth
dict(cat="dental", intent="tooth_extraction", kw=[
    "tooth extraction","remove tooth","pull tooth","extract tooth","bad tooth removal","tooth surgery"],
 en="Extractions at our dental unit are quick, gentle, and done with proper numbing — you'll be comfortable throughout, and we'll give you clear after-care so it heals smoothly. Shall I book an assessment so the dentist can plan it safely?",
 pcm="Extraction for our dental unit quick, gentle, and dem go numb am proper — go comfortable throughout, and dem go give you clear after-care make e heal smooth. Make I book assessment make the dentist fit plan am safe?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="ophthalmology", intent="red_eye", kw=[
    "red eye","pink eye","eye red","conjunctivitis","eye discharge","sore eye","itchy eye"],
 en="Red or sore eyes are common and usually very treatable — but they do need a proper look, especially if there's pain, light sensitivity, or any change in vision (then please come urgently). Our eye clinic will sort you kindly. Shall I book you in?",
 pcm="Red or sore eye dey common and usually very treatable — but e need proper look, especially if e get pain, light wahala, or any change for vision (then abeg come urgent). Our eye clinic go sort you kindly. Make I book you?",
 cta="Open Book a visit — the address is on this reply."),

# ---- Chronic care & clinics
dict(cat="chronic", intent="hypertension_clinic", kw=[
    "bp clinic","hypertension clinic","pressure clinic","high bp clinic","bp follow up"],
 en="Our BP clinic is built to keep you thriving, not just surviving — regular checks, honest advice, and medicines that fit your life and budget. Consistency is the secret to protecting your heart and kidneys. Shall I book your next BP clinic visit?",
 pcm="Our BP clinic na to keep you thrive, no be just survive — regular check, honest advice, and medicine wey fit your life and budget. Consistency na the secret to protect your heart and kidney. Make I book your next BP clinic visit?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="chronic", intent="diabetes_clinic", kw=[
    "diabetes clinic","sugar clinic","diabetic clinic","diabetes follow up","diabetic review"],
 en="Living well with diabetes is absolutely possible with the right partner — and that's what our diabetes clinic is. We pair your reviews with diet coaching and foot/eye checks so nothing is missed. Shall I book your next diabetic review?",
 pcm="To live well with diabetes dey very possible with the right partner — and na wetin our diabetes clinic be. We dey pair your review with diet coaching and foot/eye check so nothing go miss. Make I book your next diabetic review?",
 cta="Open Book a visit — the address is on this reply."),

# ---- Admin / medicals
dict(cat="admin", intent="sick_leave", kw=[
    "sick leave","medical certificate","sick note","doctor's note","medical report for work","certificate of illness"],
 en="We'll take care of that — after a clinician reviews you, we issue a proper medical certificate for your employer or school, usually the same day. Bring a valid ID. Shall I book you a review so your certificate is ready promptly?",
 pcm="Go take care of that — after clinician review you, go issue proper medical certificate for your oga or school, usually same day. Carry valid ID. Make I book you review make your certificate ready sharp?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="admin", intent="pre_employment", kw=[
    "pre employment medical","fitness certificate","employment medical","work medical test","job medical","pre-employment"],
 en="Congratulations on the new role! Our pre-employment medical covers the standard panel employers require, with a signed fitness certificate — most people complete it in one visit. Shall I book your medical and tell you exactly what to bring?",
 pcm="Congratulations for the new role o! Our pre-employment medical cover the normal panel wey employers dey require, with signed fitness certificate — most people finish am for one visit. Make I book your medical and tell you exactly wetin to carry?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="admin", intent="travel_medical", kw=[
    "yellow fever card","travel vaccine","yellow card","international travel","travel medical","yellow fever vaccine"],
 en="Safe travels! We provide yellow-fever vaccination and the official card, plus travel-health advice tailored to your destination. Bring your passport details and come in the morning. Shall I book your vaccination slot?",
 pcm="Safe travels o! We dey provide yellow-fever vaccination and the official card, plus travel-health advice for your destination. Carry your passport details and come for morning. Make I book your vaccination slot?",
 cta="Ask the front desk, or say talk to a human."),

# ---- Support & empathy
dict(cat="support", intent="mortuary", kw=[
    "mortuary","mortuary service","deceased","body","bereavement","lost a loved one","corpse","mortuary fees"],
 en="I'm so sorry for your loss — please accept our deepest condolences. Our mortuary team will handle everything with dignity and guide you gently through each step and requirement. Would you like me to connect you with the mortuary desk right now?",
 pcm="I dey sorry well well for your loss — abeg accept our deepest condolences. Our mortuary team go handle everything with dignity and guide you gently through each step. You wan make I connect you with mortuary desk now now?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="support", intent="missing_patient", kw=[
    "i cant find my patient","missing patient","cant find my relative","lost my mother","where is my husband",
    "my person don lost","cant locate my patient"],
 en="I understand how frightening that is — let's find them right now. Please tell me their full name and what they were wearing, and I'll alert the front desk and security to locate them while you stay at the information point. What's their name?",
 pcm="I understand how e dey frighten — make we find dem now now. Abeg tell me their full name and wetin dem wear, and go alert front desk and security to locate dem while you stay for information point. Wetin be their name?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="support", intent="privacy_data", kw=[
    "is my information safe","data privacy","my records private","who sees my info","confidentiality","ndpr","my data safe"],
 en="Your trust is sacred to us. Your records are confidential and protected under the Nigeria Data Protection Act — only your care team sees them, and we never share your information without your consent. You may also request access or corrections anytime. Anything specific you'd like me to clarify?",
 pcm="Your trust dey sacred to us. Your records dey confidential and protected under Nigeria Data Protection Act — only your care team go see dem, and we no dey share your info without your consent. You fit request access or correction any time. Anything specific you wan make I clarify?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="amenities", intent="cafeteria", kw=[
    "cafeteria","canteen","food","where to eat","restaurant","buy food","water","drinking water","snacks"],
 en="You must be hungry — our cafeteria serves fresh, affordable meals and clean drinking water, and it's open through the day. Ask anyone at the reception desk and they'll point you straight to it. Can I help with anything else?",
 pcm="You suppo hungry o — our cafeteria dey serve fresh, affordable meals and clean drinking water, e dey open through the day. Just ask person for reception, dem go show you. Anything else?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="amenities", intent="parking", kw=[
    "parking","car park","where to park","parking space","park my car","parking fee"],
 en="We've got you — there's patient parking right by the main gate, and it's monitored for your peace of mind. Arriving by ambulance or dropping someone? Pull up to the covered drop-off point instead. Can I help with anything else for your arrival?",
 pcm="We get you o — patient parking dey right by the main gate, and dem dey monitor am for your peace. You dey come by ambulance or dey drop person? Pull up to the covered drop-off point instead. Anything else wey go help your arrival?",
 cta="Ask the front desk, or say talk to a human."),
]
