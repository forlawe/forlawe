"""Lightweight i18n: English + Nigerian languages (Yoruba, Hausa, Igbo).

Design (§34): patient-facing strings live in one table; staff screens stay
English for now. Translations are best-effort — flag them for community
validation before wide rollout. Voice-to-text uses the matching BCP-47 tag
so patients can DICTATE in their language where the device supports it.
"""
from __future__ import annotations

from flask import session

LANGS = {
    "en": {"name": "English", "speech": "en-NG"},
    "yo": {"name": "Yorùbá", "speech": "yo-NG"},
    "ha": {"name": "Hausa", "speech": "ha-NG"},
    "ig": {"name": "Igbo", "speech": "ig-NG"},
}

STRINGS: dict[str, dict[str, str]] = {
    "tagline": {
        "en": "Patient & Visitor Portal",
        "yo": "Àtẹ fún aláìsàn àti àbẹ̀wò",
        "ha": "Ƙofar marasa lafiya da baƙi",
        "ig": "Ọnụ ụzọ ndị ọrịa na ndị ọbịa",
    },
    "privacy": {
        "en": "Please do not include sensitive medical details — only what we need to help you.",
        "yo": "Jọ̀wọ́ má ṣe fi ìsọfúnni ìlera tó ní ìmọ̀lára sílẹ̀ — ohun tí a nílò láti ràn ọ́ lọ́wọ́ nìkan.",
        "ha": "Da fatan kar a saka bayanin lafiya mai mahimmanci — abin da muke bukata don taimaka muku kawai.",
        "ig": "Biko etinyela ozi ahụike nwere mmetụta — naanị ihe anyị chọrọ iji nyere gị aka.",
    },
    # ---- shared patient navigation & help desk ----
    "back": {"en": "Back", "yo": "Padà", "ha": "Koma", "ig": "Laghachi"},
    "help_need": {
        "en": "Need help? Call the hospital help desk",
        "yo": "Ṣe o nílò ìrànlọ́wọ́? Pe tábìlì ìrànlọ́wọ́ ilé-ìwòsàn",
        "ha": "Kana buƙatar taimako? Kira teburin taimako na asibiti",
        "ig": "Ịchọrọ enyemaka? Kpọọ tebụl enyemaka ụlọ ọgwụ",
    },
    "help_hours": {
        "en": "Someone answers during working hours. Emergencies are answered day and night.",
        "yo": "Ẹnìkan yóò dáhùn ní àkókò iṣẹ́. A ń dáhùn pàjáwìrì ní ọ̀sán àti òru.",
        "ha": "Wani zai amsa a lokutan aiki. Ana amsa gaggawa dare da rana.",
        "ig": "Otu onye ga-aza n'oge ọrụ. A na-aza ihe mberede ehihie na abalị.",
    },
    "help_ask_reception": {
        "en": "Please ask at the hospital reception desk for assistance.",
        "yo": "Jọ̀wọ́ bèèrè ní tábìlì ìtẹ́wọ́gbà ilé-ìwòsàn fún ìrànlọ́wọ́.",
        "ha": "Da fatan ka tambaya a teburin liyafar asibiti don taimako.",
        "ig": "Biko jụọ na tebụl nnabata ụlọ ọgwụ maka enyemaka.",
    },
    "help_emergency": {
        "en": "In an emergency go straight to Accident & Emergency — do not wait online.",
        "yo": "Nínú pàjáwìrì lọ tààrà sí Ẹ̀ka Pàjáwìrì — má dúró lórí ayélujára.",
        "ha": "A cikin gaggawa je kai tsaye zuwa Sashen Gaggawa — kar ka jira a yanar gizo.",
        "ig": "N'ihe mberede gaa ozugbo na Ngalaba Mberede — echerela n'ịntanetị.",
    },

    # ---- patient assistant chat ----
    "chat_greeting": {
        "en": "Hello! I'm your care assistant. Ask me about booking, opening hours, bills, "
              "directions, antenatal care — or anything about your visit. How can I help?",
        "yo": "Pẹ̀lẹ́ o! Èmi ni olùrànlọ́wọ́ ìtọ́jú rẹ. Bi mí nípa ìpàdé, àkókò ìṣí, owó, ọ̀nà, "
              "ìtọ́jú aboyún — tàbí ohunkóhun nípa ìbẹ̀wò rẹ. Báwo ni mo ṣe lè ràn ọ́ lọ́wọ́?",
        "ha": "Sannu! Ni ne mataimakin kulawar ku. Ka tambaye ni game da alƙawari, lokutan "
              "buɗewa, kuɗi, hanya, kulawar masu juna biyu — ko komai game da ziyararka. "
              "Ta yaya zan taimaka?",
        "ig": "Ndewo! Abụ m onye enyemaka nlekọta gị. Jụọ m maka ndebe oge, oge emeghe, ụgwọ, "
              "ụzọ, nlekọta ime — ma ọ bụ ihe ọ bụla gbasara nleta gị. Kedu ka m ga-esi nyere gị aka?",
    },
    "chat_placeholder": {
        "en": "Type your question…", "yo": "Kọ ìbéèrè rẹ…",
        "ha": "Rubuta tambayarka…", "ig": "Pịnye ajụjụ gị…",
    },
    "chat_send": {"en": "Send", "yo": "Firánṣẹ́", "ha": "Aika", "ig": "Zipu"},
    "chat_disclosure": {
        "en": "I can help with hospital questions, but I cannot diagnose illness or prescribe "
              "medicine. A human is always one tap away.",
        "yo": "Mo lè ràn ọ́ lọ́wọ́ pẹ̀lú ìbéèrè ilé-ìwòsàn, ṣùgbọ́n n kò lè ṣe àyẹ̀wò àìsàn tàbí "
              "kọ oògùn. Ẹnìyàn wà ní ìfọwọ́kan kan.",
        "ha": "Zan iya taimaka da tambayoyin asibiti, amma ba zan iya gano cuta ko rubuta "
              "magani ba. Mutum yana nan kusa koyaushe.",
        "ig": "Enwere m ike inyere gị aka na ajụjụ ụlọ ọgwụ, mana enweghị m ike ịchọpụta ọrịa "
              "ma ọ bụ dee ọgwụ. Mmadụ nọ nso mgbe niile.",
    },

    # ---- patient hub (home page tiles) ----
    "hub_welcome": {
        "en": "How can we help you today?",
        "yo": "Báwo ni a ṣe lè ràn ọ́ lọ́wọ́ lónìí?",
        "ha": "Ta yaya za mu taimake ka yau?",
        "ig": "Kedu ka anyị ga-esi nyere gị aka taa?",
    },
    "hub_sub": {
        "en": "Choose what you need. No account, no password — everything below is free.",
        "yo": "Yan ohun tí o nílò. Kò sí àkàǹtì, kò sí ọ̀rọ̀ ìpamọ́ — gbogbo rẹ̀ jẹ́ ọ̀fẹ́.",
        "ha": "Zaɓi abin da kake buƙata. Babu asusu, babu kalmar sirri — duk kyauta ne.",
        "ig": "Họrọ ihe ị chọrọ. Enweghị akaụntụ, enweghị paswọọdụ — ọ bụ n'efu.",
    },
    "hub_book": {"en": "Book an Appointment", "yo": "Fi Ìpàdé Pamọ́",
                 "ha": "Yi Alƙawari", "ig": "Debe Nhọpụta"},
    "hub_book_d": {"en": "Choose a day and time to see us", "yo": "Yan ọjọ́ àti àkókò láti rí wa",
                   "ha": "Zaɓi rana da lokacin ganin mu", "ig": "Họrọ ụbọchị na oge ịhụ anyị"},
    "hub_queue": {"en": "Queue For A Service", "yo": "Dúró Ní Ìlà Fún Iṣẹ́",
                  "ha": "Jera Don Sabis", "ig": "Kwụ n'Ahịrị Maka Ọrụ"},
    "hub_queue_d": {"en": "Get your number and track your turn",
                    "yo": "Gba nọ́mbà rẹ kí o sì tọ́jú àkókò rẹ",
                    "ha": "Sami lambarka ka bi lokacinka", "ig": "Nweta nọmba gị soro oge gị"},
    "hub_chat": {"en": "Hospital Assistant", "yo": "Olùrànlọ́wọ́ Ilé-ìwòsàn",
                 "ha": "Mataimakin Asibiti", "ig": "Onye Enyemaka Ụlọ Ọgwụ"},
    "hub_chat_d": {"en": "Ask a question, get an answer now",
                   "yo": "Bi ìbéèrè, gba ìdáhùn báyìí",
                   "ha": "Yi tambaya, sami amsa yanzu", "ig": "Jụọ ajụjụ, nweta azịza ugbu a"},
    "hub_complaint": {"en": "Complaint Of A Service", "yo": "Ẹ̀dùn Nípa Iṣẹ́",
                      "ha": "Ƙorafi Kan Sabis", "ig": "Mkpesa Banyere Ọrụ"},
    "hub_complaint_d": {"en": "Tell management what went wrong",
                        "yo": "Sọ fún àwọn alábòójútó ohun tí kò dára",
                        "ha": "Gaya wa manajoji abin da ya faru",
                        "ig": "Gwa ndị njikwa ihe na-adịghị mma"},
    "hub_feedback": {"en": "Feedback", "yo": "Èsì", "ha": "Ra'ayi", "ig": "Nzaghachi"},
    "hub_feedback_d": {"en": "Rate your visit — it takes 10 seconds",
                       "yo": "Ṣe ìdíwọ̀n ìbẹ̀wò rẹ — ó gba ìṣẹ́jú mẹ́wàá",
                       "ha": "Ƙididdige ziyararka — daƙiƙa 10 kawai",
                       "ig": "Nyochaa nleta gị — ọ na-ewe sekọnd iri"},
    "hub_refer": {"en": "Share With A Friend", "yo": "Pín Pẹ̀lú Ọ̀rẹ́",
                  "ha": "Raba Da Aboki", "ig": "Kesaa Enyi"},
    "hub_refer_d": {"en": "Recommend this hospital to someone you care about",
                    "yo": "Sọ nípa ilé-ìwòsàn yìí fún ẹnì kan tí o nífẹ̀ẹ́",
                    "ha": "Ba da shawarar wannan asibiti ga wanda kake ƙauna",
                    "ig": "Kwado ụlọ ọgwụ a nye onye ị hụrụ n'anya"},
    "hub_emergency": {"en": "In an emergency, go straight to Accident & Emergency — do not wait online.",
                      "yo": "Nínú pàjáwìrì, lọ tààrà sí Ẹ̀ka Pàjáwìrì — má dúró lórí ayélujára.",
                      "ha": "A cikin gaggawa, je kai tsaye zuwa Sashen Gaggawa — kar ka jira a yanar gizo.",
                      "ig": "N'ihe mberede, gaa ozugbo na Ngalaba Mberede — echerela n'ịntanetị."},

    "f_dept": {"en": "Department / Unit concerned", "yo": "Ẹ̀ka/Ẹyọ tí ọ̀rọ̀ náà kan",
               "ha": "Sashen da ƙorafin ya shafa", "ig": "Ngalaba mkpesa a metụtara"},
    "f_cat": {"en": "Complaint category", "yo": "Irú ẹ̀dùn", "ha": "Nau'in ƙorafi", "ig": "Ụdị mkpesa"},
    "f_desc": {"en": "Describe the complaint", "yo": "àlàyé ẹ̀dùn rẹ", "ha": "Bayyana ƙorafinka",
               "ig": "Kọwaa mkpesa gị"},
    "f_phone": {"en": "Phone number", "yo": "Nọ́mbà fóònù", "ha": "Lambar waya", "ig": "Nọmba ekwentị"},
    "f_attach": {"en": "Optional: photo & preferred contact", "yo": "Àṣàyàn: fọ́tò àti ọ̀nà ìkàn sí",
                 "ha": "Na zaɓi: hoto da hanyar tuntuɓa", "ig": "Nhọrọ: foto na ụzọ ịkpọtụrụ"},
    "btn_complaint": {"en": "SUBMIT COMPLAINT", "yo": "FI Ẹ̀DÙN SÍLẸ̀", "ha": "AIKA ƘORAFI", "ig": "ZIPU MKPESA"},
    "speak": {"en": "Speak", "yo": "Sọ", "ha": "Yi magana", "ig": "Kwuo"},
    "received": {"en": "Your complaint has been received.", "yo": "A gbà ẹ̀dùn rẹ.",
                 "ha": "An karɓi ƙorafinka.", "ig": "A natara mkpesa gị."},
    "ref_no": {"en": "Your reference number", "yo": "Nọ́mbà ìtọ́kasí rẹ",
               "ha": "Lambar tambayarka", "ig": "Nọmba ntụaka gị"},
    "check_status": {"en": "Check status", "yo": "Wo ipò rẹ", "ha": "Duba matsayi", "ig": "Lelee ọnọdụ"},
    "book_title": {"en": "Book a Hospital Visit", "yo": "Ṣàkóso ìbẹ̀wò sí ilé ìwòsàn",
                   "ha": "Yi rajistar ziyarar asibiti", "ig": "Debie oge nleta ụlọ ọgwụ"},
    "f_service": {"en": "Service / Department", "yo": "Iṣẹ́/Ẹ̀ka", "ha": "Sabis / Sashe", "ig": "Ọrụ / Ngalaba"},
    "f_date": {"en": "Preferred date", "yo": "Ọjọ́ tí o fẹ́", "ha": "Ranar da kake so", "ig": "Ụbọchị ị chọrọ"},
    "f_time": {"en": "Preferred time", "yo": "Àkókò tí o fẹ́", "ha": "Lokacin da kake so", "ig": "Oge ị chọrọ"},
    "f_name": {"en": "Patient full name", "yo": "Orúkọ aláìsàn ní kíkún",
               "ha": "Cikakken sunan mara lafiya", "ig": "Aha onye ọrịa n'uju"},
    "btn_book": {"en": "BOOK MY VISIT", "yo": "FIPAMỌ́ ÌBẸ̀WÒ MI", "ha": "AJIYACE ZIYARATA", "ig": "DEBIE NLETA M"},
    "fb_title": {"en": "How was your experience?", "yo": "Báwo ni ìrírí rẹ rí?",
                 "ha": "Ta yaya kwarewarka ta kasance?", "ig": "Kedu ka ahụmịhe gị dịrị?"},
    "fb_improve": {"en": "What can we improve?", "yo": "Kí ni a lè mú dára síi?",
                   "ha": "Me za mu iya gyarawa?", "ig": "Gịnị ka anyị nwere ime ka ọ ka mma?"},
    "btn_feedback": {"en": "SEND FEEDBACK", "yo": "FI ÈSÌ RÁNṢẸ́", "ha": "AIKA RA'AYI", "ig": "ZIPU NZAGHACHI"},
    "q_title": {"en": "Join the Queue", "yo": "Darapọ̀ mọ́ ìlà", "ha": "Shiga jerin jira", "ig": "Sonyere n'ahịrị"},
    "btn_queue": {"en": "GET MY QUEUE NUMBER", "yo": "GBA NỌ́MBÀ ÌLÀ MI",
                  "ha": "SAMO LAMBAR JIRA TA", "ig": "NWETA NỌMBA AHỊRỊ M"},
    "thanks_good": {"en": "We're glad you had a good experience!",
                    "yo": "A yọ̀ pé o ní ìrírí dáadáa!",
                    "ha": "Muna farin ciki da kyakkyawar kwarewa!",
                    "ig": "Anyị nwere obi ụtọ na ahụmịhe gị dị mma!"},
    "sorry": {"en": "We're sorry — and we're on it.", "yo": "A dábìnín — a sì ń ṣe nípa rẹ̀.",
              "ha": "Muna ba da haƙuri — muna magance shi.", "ig": "Anyị na-arịọ mgbaghara — anyị na-edozi ya."},
    "book_again": {"en": "BOOK ANOTHER VISIT", "yo": "ṢÀKÓSO ÌBẸ̀WÒ MÌÍ",
                   "ha": "YI WATA ZIYARA", "ig": "DEBIE NLETA ỌZỌ"},
    "refer": {"en": "REFER A FRIEND OR FAMILY MEMBER", "yo": "DARÍ Ọ̀RẸ́ TÀBI ẸBÍ SÍBẸ̀",
              "ha": "KAI ƊAN UWA KO ABOKI", "ig": "KPỌTA ENYI MA Ọ BỤ ONYE EZINỤLỌ"},
    "no_account": {"en": "No account needed", "yo": "Kò sí àkọọ́lẹ̀ tí a nílò",
                   "ha": "Ba a buƙatar asusu", "ig": "Achọghị akaụntụ"},
    "language": {"en": "Language", "yo": "Èdè", "ha": "Harshe", "ig": "Asụsụ"},
    "status_title": {"en": "Check your complaint status", "yo": "Wo ipò ẹ̀dùn rẹ",
                     "ha": "Duba matsayin ƙorafinka", "ig": "Lelee ọnọdụ mkpesa gị"},
    "booking_confirmed": {"en": "Your visit is booked!", "yo": "A ti fipamọ́ ìbẹ̀wò rẹ!",
                          "ha": "An ajiyace ziyararka!", "ig": "Edebiela nleta gị!"},
    "refer_landing_title": {
        "en": "A friend recommended this hospital",
        "yo": "Ọ̀rẹ́ kan dá ilé ìwòsàn yìí lẹ́yìn",
        "ha": "Wani aboki ya ba da shawarar wannan asibiti",
        "ig": "Enyi tụrụ aro ụlọ ọgwụ a",
    },
    "refer_landing_sub": {
        "en": "No account needed. Book a visit in about a minute — we only ask for what the hospital needs to prepare for you.",
        "yo": "Kò sí àkọọ́lẹ̀ tí a nílò. Ṣàkóso ìbẹ̀wò ní ìṣẹ́jú kan.",
        "ha": "Ba a buƙatar asusu. Yi rajistar ziyara cikin minti ɗaya.",
        "ig": "Achọghị akaụntụ. Debie nleta n'otu nkeji.",
    },
    "refer_friend_said": {
        "en": "Someone who was cared for here thought you might need us too.",
        "yo": "Ẹni tí a tọ́jú níbí rò pé ìwọ náà lè nílò wa.",
        "ha": "Wanda aka kula da shi a nan ya yi tunanin za ka iya buƙatar mu.",
        "ig": "Onye e lekọtara ebe a chere na ị nwekwara ike ịchọ anyị.",
    },
    "refer_book_cta": {
        "en": "BOOK A VISIT",
        "yo": "ṢÀKÓSO ÌBẸ̀WÒ",
        "ha": "YI RAJISTAR ZIYARA",
        "ig": "DEBIE NLETA",
    },
    "refer_share_hint": {
        "en": "Your personal share-link",
        "yo": "Ìtọ́kasí rẹ fún pínpín",
        "ha": "Hanyar raba naka",
        "ig": "Njikọ nke gị ịkekọrịta",
    },
    "refer_copy": {"en": "Copy or share this link", "yo": "Dàákọ tàbí pín ìtọ́kasí yìí",
                   "ha": "Kwafa ko raba wannan hanyar", "ig": "Detuo ma ọ bụ kekọrịta njikọ a"},
    "refer_qr_hint": {
        "en": "A friend can scan this with their phone camera.",
        "yo": "Ọ̀rẹ́ lè ṣe àyẹ̀wò kóòdù yìí pẹ̀lú fóònù wọn.",
        "ha": "Aboki zai iya duba wannan da kyamarar wayarsa.",
        "ig": "Enyi nwere ike sọghee nke a na igwefoto ekwentị ha.",
    },
    "refer_no_pressure": {
        "en": "No prizes. No pressure. Just a kind way to point someone toward good care.",
        "yo": "Kò sí ẹ̀bùn, kò sí ìyànjú. Ọ̀nà àánú ni láti tọ́ ẹnìkan sí ìtọ́jú dáadáa.",
        "ha": "Babu kyauta, babu tilastawa. Hanya ce ta nuna wa wani kula mai kyau.",
        "ig": "Enweghị ihe nrite, enweghị nrụgide. Ọ bụ naanị ụzọ ịkọwa ebe ezi nlekọta dị.",
    },
    "refer_welcome": {
        "en": "A friend sent you — welcome",
        "yo": "Ọ̀rẹ́ rán ọ́ — ẹ kú àbọ̀",
        "ha": "Aboki ne ya aiko ka — barka da zuwa",
        "ig": "Enyi zigara gị — nnọọ",
    },
}


def get_lang() -> str:
    lang = session.get("lang", "en")
    return lang if lang in LANGS else "en"


def translate(key: str, lang: str | None = None) -> str:
    lang = lang or get_lang()
    entry = STRINGS.get(key, {})
    return entry.get(lang) or entry.get("en") or key


def speech_tag(lang: str | None = None) -> str:
    return LANGS.get(lang or get_lang(), LANGS["en"])["speech"]
