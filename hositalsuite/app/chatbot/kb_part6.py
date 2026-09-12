"""GLOBAL MASTER DIALOGUE LIBRARY — Part 6 (crosses 1,000 triggers)."""

KB = [
dict(cat="clinics", intent="headache", kw=[
    "headache","head ache","migraine","severe headache","constant headache","head pain","head dey pain"],
 en="Sorry you're dealing with that — most headaches are manageable, but a sudden severe one, or one with fever, vomiting or vision changes, should be seen urgently. For a routine headache, our clinic can help you find triggers and relief. Shall I book you in?",
 pcm="Sorry say you dey deal with that — most headache dey manageable, but sudden severe one, or one wey get fever, vomiting or vision change, suppo be see urgent. For normal headache, our clinic fit help you find triggers and relief. Make I book you?",
 cta="Go to A&E now if it is urgent — or say talk to a human."),
dict(cat="clinics", intent="sleep", kw=[
    "cant sleep","insomnia","sleep problem","not sleeping","snoring","sleep apnea","poor sleep","sleepless"],
 en="Good sleep is medicine — and if it's eluding you, we can help, from practical sleep coaching to checking things like snoring or sleep apnoea that are very treatable. Shall I book a consultation to get your nights back?",
 pcm="Good sleep na medicine — and if e dey escape you, we fit help, from practical sleep coaching to checking things like snoring or sleep apnoea wey dey very treatable. Make I book consultation to return your nights?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="wellness", intent="stop_smoking", kw=[
    "stop smoking","quit smoking","smoking cessation","give up cigarette","quit cigarette","stop smoking help"],
 en="Deciding to quit is a huge win for your heart, lungs and family — and you don't have to do it alone. Our team offers practical, judgement-free support and follow-up that dramatically raises your success. Shall I enrol you in our stop-smoking programme?",
 pcm="To decide to quit na big win for your heart, lung and family — and you no need do am alone. Our team dey offer practical, no-judgement support and follow-up wey go raise your success well well. Make I enrol you for our stop-smoking programme?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="wellness", intent="obesity", kw=[
    "weight loss","obesity","overweight","lose weight","weight management","belly fat","reduce weight"],
 en="A healthier weight is absolutely within reach with the right partner — our team combines medical review, realistic nutrition and encouragement, never shame. Small consistent steps win. Shall I book a weight-management consultation?",
 pcm="Healthier weight dey within reach with the right partner — our team combine medical review, realistic nutrition and encouragement, no be shame. Small consistent steps dey win. Make I book weight-management consultation?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="wellness", intent="elderly_care", kw=[
    "elderly","old parent","geriatric","care for old","senior citizen","my mother is old","old father","aged care"],
 en="Caring for our elders is an honour, and we're here to make it lighter — from gentle comprehensive reviews to home-care support and priority seating when they visit. Tell me what your parent needs and I'll arrange it warmly.",
 pcm="To care for our elders na honour, and we dey here to make am light — from gentle comprehensive review to home-care support and priority seating when dem visit. Tell me wetin your parent need and go arrange am warmly.",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="clinics", intent="adolescent_health", kw=[
    "teenager","adolescent","my teen","young person","youth clinic","teen health","puberty","adolescent clinic"],
 en="Our adolescent clinic gives young people a private, respectful space to ask anything and get proper care — no judgement, no lectures, just support. It's how we raise a healthy, confident generation. Shall I book a teen-friendly slot?",
 pcm="Our adolescent clinic dey give young people private, respectful space to ask anything and get proper care — no judgement, no lecture, just support. Na so we dey raise healthy, confident generation. Make I book teen-friendly slot?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="maternity", intent="cs_section", kw=[
    "caesarean","c section","cs delivery","c-section","caesarean section","booked for cs","surgery delivery"],
 en="If a caesarean is your path, please know it's a safe, well-trodden road with us — a skilled theatre team, attentive anaesthesia, and support for you to meet and breastfeed your baby as soon as it's safe. We'll walk you through every step beforehand. Any questions I can answer?",
 pcm="If caesarean na your path, abeg know say e safe and we don do am plenty times here — skilled theatre team, attentive anaesthesia, and support for you to meet and breastfeed your baby as soon as e safe. Go waka you through every step before. Any question wey I fit answer?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="clinics", intent="circumcision", kw=[
    "circumcision","male circumcision","baby circumcision","circumcise","male circumcision programme"],
 en="We perform safe, medical circumcision for babies and adults in a sterile setting with proper pain control — a big safety win over informal settings. Shall I book the procedure and give you the simple prep instructions?",
 pcm="We dey do safe, medical circumcision for baby and adults for sterile setting with proper pain control — big safety win over informal place. Make I book the procedure and give you the simple prep instructions?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="clinics", intent="hernia_piles", kw=[
    "hernia","rupture","piles","haemorrhoids","hernia surgery","piles treatment","swelling in groin","rectal bleeding"],
 en="These are common, treatable, and nothing to be embarrassed about — our surgeons handle hernia and piles routinely with modern, minimally painful techniques and quick recovery. Shall I book a surgical assessment for you?",
 pcm="These dey common, treatable, and nothing to embarrassed about — our surgeons dey handle hernia and piles routinely with modern, minimally painful techniques and quick recovery. Make I book surgical assessment for you?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="clinics", intent="dialysis", kw=[
    "dialysis","kidney failure","renal","kidney clinic","dialysis unit","kidney problem","creatinine high"],
 en="Our renal team supports kidney patients with dignity — from clinic reviews and lab monitoring to dialysis coordination where needed. You'll have a consistent team who knows you. Shall I book a renal clinic review?",
 pcm="Our renal team dey support kidney patients with dignity — from clinic review and lab monitoring to dialysis coordination where e need. Go get consistent team wey know you. Make I book renal clinic review?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="support", intent="chaplaincy", kw=[
    "chaplain","imam","pastor","prayer","spiritual support","chaplaincy","religious support","worship"],
 en="We care for the whole person — body and spirit. Our chaplaincy team (and visiting imams/pastors) are available for patients and families who would like prayer or spiritual support. Shall I let the chaplaincy know you'd like a visit?",
 pcm="We dey care for the whole person — body and spirit. Our chaplaincy team (and visiting imam/pastor) dey available for patients and family wey go like prayer or spiritual support. Make I let chaplaincy know say you go like visit?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="operations", intent="health_talk", kw=[
    "health talk","outreach","community talk","health education","school talk","church health talk","health seminar"],
 en="We love taking health knowledge to the community — our team gives engaging health talks at schools, churches, mosques and workplaces, and runs outreach screenings. Shall I schedule a health talk or outreach for your organisation?",
 pcm="We dey love to carry health knowledge go community — our team dey give engaging health talk for school, church, mosque and workplace, and we dey run outreach screening. Make I schedule health talk or outreach for your organisation?",
 cta="Tell me your group and preferred date — we'll bring the team."),
]
