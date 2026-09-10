"""GLOBAL MASTER DIALOGUE LIBRARY — Part 7 (handoff + everyday Naija phrasings; clears 1,000)."""

KB = [
dict(cat="engagement", intent="human_handoff", kw=[
    "talk to a human","speak to a person","real person","agent","customer care","operator","human being",
    "connect me to someone","i want a person","not a bot","talk to staff","front desk","representative",
    "make i talk to person","give me human"],
 en="Of course — you deserve a human, and I'm happy to bring one in. I've alerted our front desk and a team member will be with you shortly; I'll stay right here too if you need anything meanwhile. Thank you for your patience!",
 pcm="Of course o — you deserve human, and I go happy bring one in. I don alert our front desk and team member go meet you sharp sharp; go still dey here too if you need anything meanwhile. Thank you for your patience!",
 cta="I'm handing you over now — someone is on the way."),
dict(cat="greetings", intent="greet_pidgin", kw=[
    "how far o","howfar","wetin dey sup","how you dey","you dey","na you be bot","abeg hello","make we talk",
    "i dey find help","help me abeg","i need help o","assistance please abeg"],
 en="How far! I'm right here for you — tell me what you need and we'll sort it together, nice and easy. Booking, bills, directions, or anything at all?",
 pcm="How far o! I dey right here for you — tell me wetin you need and go sort am together, nice and easy. Booking, bill, direction, or anything at all?",
 cta="Abeg tell me wetin dey your mind."),
dict(cat="bills", intent="bill_too_high", kw=[
    "this bill is too high","too expensive","overpriced","i cant afford","bill too much","this is expensive",
    "reduce the bill","bill is high","costly"],
 en="I hear you, and I'm not going to brush that aside — cost matters, and we have options. Our billing desk can review the bill line-by-line, discuss a payment plan, and confirm any insurance or discount you qualify for.",
 pcm="I hear you, and I no go brush am aside — cost matter, and we get options. Our billing desk fit review the bill line-by-line, discuss payment plan, and confirm any insurance or discount wey you qualify.",
 cta="Ask the billing desk for a review — or open Make a complaint."),
dict(cat="operations", intent="where_is_my_doctor", kw=[
    "where is my doctor","my doctor not around","doctor don go","i cant find my doctor","doctor absent",
    "who is covering my doctor","my doctor no dey"],
 en="I understand the worry when your usual doctor isn't around — your care doesn't stop. A covering clinician with full access to your folder is available, and your doctor is briefed on your case. Ask the front desk who is covering today.",
 pcm="I understand the worry when your normal doctor no dey — your care no go stop. Covering clinician wey get full access to your folder dey available, and your doctor dey briefed on your case. Ask front desk who dey cover today.",
 cta="Ask the front desk who is covering today."),
dict(cat="operations", intent="open_sunday", kw=[
    "open on sunday","sunday hours","are you open sunday","public holiday","open on holiday","sunday clinic"],
 en="Great question — our clinics are closed on Sundays and public holidays, but the emergency unit and admissions run 24/7 every day, and the pharmacy keeps an emergency window. For routine visits, Monday morning is usually calm.",
 pcm="Correct question — our clinic dey close for Sunday and public holiday, but emergency and admission dey run 24/7 every day, and pharmacy keep emergency window. For normal visit, Monday morning dey usually calm.",
 cta="Open Book a visit for a weekday slot."),
dict(cat="selfservice", intent="resend_otp", kw=[
    "resend code","code not coming","no code","i didnt get code","otp not received","send code again",
    "code no reach","i no receive code"],
 en="No stress — codes can occasionally be delayed by the network. I cannot send a new code from this chat. Use Forgot password on the sign-in page, or ask the front desk to help you.",
 pcm="No stress — code fit delay sometimes by network. I no fit send new code from this chat. Use Forgot password for the sign-in page, or ask front desk make dem help you.",
 cta="Use Forgot password on the sign-in page, or ask the desk."),
]
