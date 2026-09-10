"""MENTAL HEALTH dialogue — DRAFT, held for clinical tone review (F-043).

The audit found Mental Health is the one department with NO chatbot coverage
at all, and recommended that — unlike the template departments — its dialogue
be reviewed by clinical staff for tone BEFORE it ships. A template copy-paste
would be exactly wrong for a topic where a careless phrase can do real harm.

THIS MODULE IS THEREFORE NOT SEEDED. `seed_kb._all_kb()` skips it while
`_REVIEWED` is False, and a test (tests/test_f042_f043_kb_coverage.py) pins
that exclusion. To publish:

  1. Have a clinical staff member (psychiatry nurse / Mental Health lead)
     review every answer below — especially `crisis`, which must promise
     nothing the hospital does not actually provide.
  2. Confirm the Psychiatry Clinic details (location, how booking works)
     with the front desk.
  3. Set `_REVIEWED = True` and deploy. The library sync adds the intents
     exactly like any other department; nothing else to do.

House style applies (warm, specific, never diagnose) plus three extra rules
for this topic: never minimise ("it could be worse" is banned), never
promise confidentiality the app cannot enforce (the CLINICIAN keeps
consultations confidential; the chat itself is not a clinical channel), and
every crisis-adjacent answer points to a human, today.
"""
from __future__ import annotations

_REVIEWED = False          # flip to True only after clinical tone review (F-043)

_CTA_BOOK = "Open Book a visit — the address is on this reply."
_CTA_DESK = "Ask the front desk, or say talk to a human."
_CTA_HELP = "Anything else I can make easier for you?"

KB: list[dict] = []


def _d(rows: list[tuple]) -> None:
    for suffix, triggers, en, pcm, cta in rows:
        KB.append(dict(cat="dept_mental_health", intent=f"mental_health_{suffix}",
                       kw=sorted({k.strip().lower() for k in triggers if k and k.strip()}),
                       en=en, pcm=pcm, cta=cta))


_d([
    ("what", ["what is mental health clinic", "mental health services", "psychiatry clinic",
              "counselling service", "wetin mental health clinic dey do"],
     "Our Mental Health service is the Psychiatry Clinic — a calm, private place where you can "
     "talk with clinicians who are trained to listen without judgement. People come for low mood, "
     "worry that won't settle, sleep, stress, and support for family members too. Asking about it "
     "is a strong first step, not a weakness.",
     "Our Mental Health service na the Psychiatry Clinic — quiet, private place where you fit talk "
     "with clinician wey sabi listen without judging. People dey come for low mood, worry wey no "
     "gree settle, sleep, stress, and support for family member too. To ask na strong first step.",
     _CTA_BOOK),
    ("book", ["book mental health", "book psychiatry", "see a counselor", "book therapy session",
              "book psychiatrist"],
     "You can book a Psychiatry Clinic slot the same way as any other clinic. If talking feels "
     "hard, you can write what's going on in the booking note — the team will meet you where "
     "you are. You can bring someone you trust along.",
     "You fit book Psychiatry Clinic slot the same way like every other clinic. If to talk hard, "
     "you fit write wetin dey happen for the booking note — the team go meet you where you dey. "
     "You fit bring person wey you trust come.",
     _CTA_BOOK),
    ("first_visit", ["first mental health visit", "what happens psychiatry clinic", "will i be forced",
                     "wetin dey happen for psychiatry"],
     "The first visit is a conversation, not an examination — the clinician asks how you've been "
     "feeling and what you want to change, at your pace. Nothing is forced on you, and any "
     "treatment is discussed and agreed with you first. Many people say the hardest part was "
     "walking through the door — you'd already have done that.",
     "The first visit na conversation, no be examination — the clinician go ask how you dey feel "
     "and wetin you wan change, for your own pace. Nothing go force you, and any treatment dem go "
     "discuss am and agree with you first. The hard part na to enter door — you don do am already.",
     _CTA_DESK),
    ("confidentiality", ["is it confidential", "will my employer know", "mental health privacy",
                         "who go know say i dey come"],
     "What you discuss with the clinic's clinicians is confidential within your care team, the "
     "same as any medical consultation — your visit is recorded in your hospital folder, not "
     "announced to anyone. One honest exception: if there is a serious risk to your life or "
     "someone else's, the team must act to keep you safe. Would you like to book a first chat?",
     "Wetin you talk with the clinic clinician na confidential inside your care team, the same way "
     "like every medical consultation — your visit dey your hospital folder, dem no go announce am "
     "give anybody. One honest exception: if your life or another person life dey serious risk, the "
     "team must act to keep you safe. You wan book first chat?",
     _CTA_BOOK),
    ("crisis", ["i want to harm myself", "suicidal", "i can't go on", "life no worth again",
                "hurt myself"],
     "Thank you for telling me — that took courage, and I want you safe. Please don't stay alone "
     "with this: go straight to our Accident & Emergency (open 24/7) or ask someone you trust to "
     "take you now, and tell the first staff member you meet exactly what you told me. The crisis "
     "team will sit with you and make a plan with you, today.",
     "Thank you for tell me — e take courage, and I want you safe. Abeg no stay alone with am: go "
     "straight to our A&E (e dey open 24/7) or make person wey you trust carry you come now, and "
     "tell the first staff wey you see exactly wetin you tell me. The crisis team go stay with you "
     "and plan with you, today.",
     _CTA_DESK),
    ("cost", ["mental health cost", "how much is psychiatry", "counselling fee", "therapy price"],
     "Psychiatry Clinic fees follow the standard consultation rates — I won't guess a figure "
     "here. The billing desk will confirm the amount before your visit, and cost should never be "
     "the reason you don't ask for help; talk to the front desk about your situation.",
     "Psychiatry Clinic fee follow the normal consultation rate — I no go guess figure here. "
     "Billing desk go confirm the amount before your visit, and cost no suppose be the reason you "
     "no ask for help; talk to front desk about your situation.",
     _CTA_DESK),
    ("hours", ["mental health hours", "psychiatry clinic hours", "when is counselling", "psychiatry today"],
     "The Psychiatry Clinic runs on weekdays, and the booking page shows the current slots. If "
     "things are urgent outside those hours — frightening thoughts, or thoughts of harming "
     "yourself — come to Accident & Emergency any hour, day or night.",
     "Psychiatry Clinic dey run weekday, booking page dey show the current slots. If e urgent "
     "outside those hours — frightening thought, or thought to harm yourself — come A&E any hour, "
     "day or night.",
     _CTA_BOOK),
    ("family", ["support for family", "my relative mental health", "how to help someone",
                "my family member dey sick for head"],
     "Supporting someone through a mental health struggle is heavy, and you don't have to carry "
     "it alone. The clinic sees family members too — to advise you, and, with your relative's "
     "consent, to plan their care together. Book a slot and say it's about supporting a family "
     "member.",
     "To support person wey dey struggle with mental health heavy, and you no suppose carry am "
     "alone. The clinic dey see family member too — to advise you, and with your relative consent, "
     "to plan their care together. Book slot come and talk say na to support family member.",
     _CTA_BOOK),
    ("stigma", ["will people think i'm mad", "ashamed to come", "people go think say i dey craze",
                "fear of stigma"],
     "That worry is real, and you're not the first to carry it — most of our patients walk in "
     "looking exactly like everyone else, because they are. Nothing about your visit is displayed "
     "on public screens or shared at the front desk with bystanders. You came for your health; "
     "that's something to respect, not hide.",
     "That worry real, and you no be the first wey carry am — most of our patient dey waka in like "
     "every other person, because na so e be. Nothing about your visit dey show for public screen "
     "or share for front desk with bystanders. You come for your health; na respect deserve am, "
     "no be hide.",
     _CTA_BOOK),
    ("complaint", ["mental health complaint", "psychiatry clinic problem", "counselling complaint",
                   "psychiatry no well"],
     "I'm sorry — trust matters double in this service. You can raise it on the complaint form "
     "in this app (it reaches the complaint desk, not the clinic you're complaining about), or "
     "ask for the nurse in charge at the Psychiatry Clinic. It will be taken seriously.",
     "I dey sorry — trust matter double for this service. You fit raise am for the complaint form "
     "for this app (e go reach complaint desk, no be the clinic wey you dey complain about), or "
     "ask for the nurse in charge for Psychiatry Clinic. Dem go take am serious.",
     _CTA_DESK),
])
