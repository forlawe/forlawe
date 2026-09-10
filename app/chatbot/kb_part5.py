"""GLOBAL MASTER DIALOGUE LIBRARY — Part 5 (Nigerian-priority topics; crosses 1,000 triggers)."""

KB = [
dict(cat="genetics", intent="genotype", kw=[
    "genotype","my genotype","genotype test","as as ss","genotype before marriage","blood genotype",
    "check genotype","genotype for marriage","ss as aa","know my genotype"],
 en="Knowing your genotype is one of the wisest steps before marriage or family planning — and our lab does it quickly and confidentially. No fasting needed. Shall I book a genotype test for you and your partner?",
 pcm="To know your genotype na one of the wisest step before marriage or family planning — and our lab dey do am quick and confidential. No need fasting. Make I book genotype test for you and your partner?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="genetics", intent="sickle_cell", kw=[
    "sickle cell","sickler","sickle cell clinic","ss disease","sickle cell patient","sickle cell support",
    "crisis","sickle cell care"],
 en="We walk closely with our sickle-cell warriors and their families — dedicated clinic days, pain-management that treats you with dignity, and real support for prevention and planning. You are not alone in this. Shall I book your next sickle-cell clinic visit?",
 pcm="We dey waka closely with our sickle-cell warriors and their family — dedicated clinic days, pain management wey treat you with dignity, and real support for prevention and planning. You no dey alone for this. Make I book your next sickle-cell clinic visit?",
 cta="If a crisis starts, don't wait — come straight in; we'll fast-track you."),
dict(cat="screening", intent="breast_screening", kw=[
    "breast cancer screening","breast check","mammogram","breast lump","breast examination","breast cancer test",
    "check my breast"],
 en="You're being wonderfully proactive — early detection saves lives, and a breast check or mammogram at our unit is quick, private, and handled by a gentle team. If you've felt a lump, please come promptly; most lumps are treatable, especially early. Shall I book your screening?",
 pcm="You dey wonderfully proactive o — early detection dey save lives, and breast check or mammogram for our unit quick, private, and gentle team go handle am. If you don feel lump, abeg come sharp; most lump dey treatable, especially early. Make I book your screening?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="screening", intent="cervical_screening", kw=[
    "cervical cancer","pap smear","pap test","cervical screening","hpv test","cervical check"],
 en="A Pap smear is one of the most powerful five minutes in women's health — it catches changes years before they become problems. Our team is female-led, gentle, and completely private. Shall I book your cervical screening?",
 pcm="Pap smear na one of the most powerful five minutes for women health — e dey catch changes years before dem become problems. Our team na female-led, gentle, and completely private. Make I book your cervical screening?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="screening", intent="prostate_screening", kw=[
    "prostate","prostate cancer","psa test","prostate screening","prostate check","men health check"],
 en="Gentlemen, your health matters too — a simple PSA test and review can catch prostate issues early, when they're most treatable. It's quick and confidential. Shall I book your prostate screening this week?",
 pcm="Gentlemen o, your health matter too — simple PSA test and review fit catch prostate wahala early, when e most treatable. E quick and confidential. Make I book your prostate screening this week?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="clinics", intent="malaria_test", kw=[
    "malaria","malaria test","malaria check","i have malaria","malaria treatment","mp test","fever malaria"],
 en="Malaria is common here, but the right first step is a proper test — we don't treat on guesswork. Our lab confirms quickly, and our clinicians will treat you properly if positive. Shall I arrange a malaria test for you today?",
 pcm="Malaria dey common here, but the right first step na proper test — we no dey treat on guesswork. Our lab go confirm quick, and our clinicians go treat you proper if e positive. Make I arrange malaria test for you today?",
 cta="Come in for the test — if you're very weak or vomiting, come straight away."),
dict(cat="clinics", intent="tb_clinic", kw=[
    "tb","tuberculosis","tb test","coughing blood","chronic cough","tb clinic","tb treatment","catarrah cough long"],
 en="A cough lasting more than two weeks deserves a proper check — and TB, when found, is fully curable with the right care. Our TB clinic tests and treats confidentially and at no cost for the standard regimen. Shall I book your TB screening?",
 pcm="Cough wey pass two weeks deserve proper check — and TB, if dem find am, dey fully curable with the right care. Our TB clinic dey test and treat confidential and free for the normal regimen. Make I book your TB screening?",
 cta="Open Book a visit — the address is on this reply."),
# ENT now lives in the full DEPARTMENT library (kb_departments_full.py — F-042)
dict(cat="clinics", intent="skin", kw=[
    "skin","dermatology","rash","eczema","skin infection","acne","skin allergy","itching skin","dermatologist"],
 en="Healthy skin is health, not vanity — our dermatology team treats rashes, eczema, acne and infections with care and without judgement. Shall I book you a skin clinic review?",
 pcm="Healthy skin na health, no be vanity — our dermatology team dey treat rash, eczema, acne and infection with care and without judgement. Make I book you skin clinic review?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="clinics", intent="joint_pain", kw=[
    "joint pain","rheumatism","arthritis","knee pain","back pain","waist pain","body pain","swollen joints"],
 en="Persistent joint or back pain shouldn't steal your joy — our physicians and physio team work together to find the cause and build a practical recovery plan. Shall I book an assessment for you?",
 pcm="Persistent joint or back pain no suppo steal your joy — our physicians and physio team dey work together to find the cause and build practical recovery plan. Make I book assessment for you?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="clinics", intent="fertility", kw=[
    "fertility","infertility","trying to conceive","cant get pregnant","fertility clinic","ivf","conceive help"],
 en="We understand how personal and emotional this journey is — and you deserve a team that treats it with hope, science and zero judgement. Our fertility clinic assesses both partners compassionately and maps a clear path forward. Shall I book a private consultation?",
 pcm="We understand how personal and emotional this journey be — and you deserve team wey go treat am with hope, science and zero judgement. Our fertility clinic go assess both partners compassionately and map clear path. Make I book private consultation?",
 cta="We'll see both partners — tell me a private time that suits you."),
dict(cat="clinics", intent="menstrual_health", kw=[
    "period pain","menstrual","heavy period","irregular period","period problems","painful period","menstruation"],
 en="Your cycle health says a lot about your overall health — painful, heavy or irregular periods are worth checking, and help is very effective. Our gynaecology team is gentle and private. Shall I book you a review?",
 pcm="Your cycle health dey talk a lot about your overall health — painful, heavy or irregular period dey worth checking, and help dey very effective. Our gynaecology team gentle and private. Make I book you review?",
 cta="Ask the front desk, or say talk to a human."),
dict(cat="packages", intent="executive_check", kw=[
    "executive check up","full medical","comprehensive check","health package","annual medical","corporate medical",
    "executive screening","full body check up"],
 en="Treat yourself to total peace of mind — our executive medical covers head-to-toe screening, labs, imaging and a doctor's debrief, usually in one comfortable morning. It's the smartest gift you can give yourself or a parent. Shall I reserve your executive check?",
 pcm="Treat yourself to total peace of mind — our executive medical cover head-to-toe screening, lab, imaging and doctor debrief, usually for one comfortable morning. Na the smartest gift you fit give yourself or your parent. Make I reserve your executive check?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="packages", intent="home_care", kw=[
    "home care","nurse at home","home nursing","home visit","doctor at home","home service","care at home for elderly"],
 en="We bring trusted care to your home — qualified nurses and clinicians for wound care, injections, elderly support and post-surgery recovery, all supervised by our hospital team. Shall I arrange a home-care assessment for your loved one?",
 pcm="We dey carry trusted care come your home — qualified nurses and clinicians for wound care, injection, elderly support and post-surgery recovery, all supervised by our hospital team. Make I arrange home-care assessment for your person?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="packages", intent="telemedicine", kw=[
    "telemedicine","video consult","online doctor","remote consult","teleconsult","video call doctor","consult from home"],
 en="Yes — for follow-ups and non-emergencies you can consult our clinicians by video from wherever you are, saving you traffic and time. We'll send you a secure link and your clinician joins on time. Shall I schedule a video consult?",
 pcm="Yes o — for follow-up and non-emergency you fit consult our clinicians by video from anywhere you be, save you traffic and time. Go send you secure link and your clinician go join on time. Make I schedule video consult?",
 cta="Open Book a visit — the address is on this reply."),
dict(cat="labs", intent="blood_group", kw=[
    "blood group","my blood group","blood type","genotype and blood group","know my blood group","blood group test"],
 en="Knowing your blood group is essential for emergencies and for family planning — our lab confirms it quickly and records it safely in your folder. No fasting needed. Shall I add a blood-group test to your visit?",
 pcm="To know your blood group dey essential for emergency and family planning — our lab go confirm am quick and record am safe for your folder. No need fasting. Make I add blood-group test to your visit?",
 cta="Ask the front desk, or say talk to a human."),
]
