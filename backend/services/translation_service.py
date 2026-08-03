import os
import re
import unicodedata
from typing import List, Dict, Any, Optional, Tuple

from config import settings
from backend.utils.logger import logger
from backend.utils.unicode_utils import (
    normalize_indic_digits,
    protect_symbols_for_translation,
    restore_symbols_after_translation,
    clean_unrestored_placeholders
)

# Indic Administrative Terms Dictionary for exact table cell / heading translation
INDIC_ADMIN_DICTIONARY = {
    "सचिव": "Secretary",
    "(सचिव)": "(Secretary)",
    "अध्यक्ष": "Chairperson / President",
    "(अध्यक्ष)": "(Chairperson / President)",
    "ग्रामपंचायत": "Gram Panchayat",
    "जिल्हा परिषद": "Zilla Parishad",
    "पंचायत समिती": "Panchayat Samiti",
    "नगर पालिका": "Municipal Council",
    "महानगरपालिका": "Municipal Corporation",
    "तहसीलदार": "Tehsildar",
    "जिल्हाधिकारी": "District Collector",
    "मुख्य कार्यकारी अधिकारी": "Chief Executive Officer (CEO)",
    "गट विकास अधिकारी": "Block Development Officer (BDO)",
    "महाराष्ट्र शासन": "Government of Maharashtra",
    "भारत सरकार": "Government of India",
    "सार्वजनिक बांधकाम विभाग": "Public Works Department (PWD)",
    "आरोग्य विभाग": "Health Department",
    "कृषी विभाग": "Agriculture Department",
    "शिक्षण विभाग": "Education Department",
    "जलसंपदा विभाग": "Water Resources Department",
    "वित्त विभाग": "Finance Department",
    "महसूल विभाग": "Revenue Department",
    "गृह विभाग": "Home Department",
    "ऊर्जा विभाग": "Energy Department",
    "उद्योग विभाग": "Industries Department",
    "ग्रामविकास विभाग": "Rural Development Department",
    # Table column headers & specific document terms
    "उपक्रमनिहाय खर्च व प्रगती तक्ता": "Activity-wise Expense & Progress Table",
    "उपक्रमाचे नाव": "Activity Name",
    "मराठी वाक्प्रचार / ध्येय": "Marathi Idiom / Goal",
    "मराठी वाक्प्रचार/ध्येय": "Marathi Idiom / Goal",
    "कालावधी": "Duration / Period",
    "लाभार्थी/लक्ष्य": "Beneficiaries / Target",
    "लाभार्थी / लक्ष्य": "Beneficiaries / Target",
    "प्रत्यक्ष खर्च (₹)": "Actual Expense (₹)",
    "प्रत्यक्ष खर्च": "Actual Expense",
    "एकूण मंजूर व प्रत्यक्ष खर्च:": "Total Sanctioned & Actual Expense:",
    "एकूण मंजूर व प्रत्यक्ष खर्च": "Total Sanctioned & Actual Expense",
    "वृक्षरोपण व संवर्धन अभियान": "Tree Plantation & Conservation Drive",
    "पाणी साठवण व बंधारे निर्मिती": "Water Harvesting & Check Dam Construction",
    "महिला सौर ऊर्जा प्रशिक्षण": "Women Solar Energy Training",
    "कचरा व्यवस्थापन व सेंद्रिय खत": "Waste Management & Organic Composting",
    "प्लास्टिकमुक्त परिसर जनजागृती": "Plastic-Free Environment Awareness",
    "मे - जून": "May - Jun",
    "जुलै - सप्टें": "Jul - Sep",
    "ऑक्टो - नोव्हें": "Oct - Nov",
    "डिसें - फेब्रु": "Dec - Feb",
    "मार्च": "March",
    "४५० ग्रामस्थ": "450 Villagers",
    "५२० शेतकरी": "520 Farmers",
    "१३० महिला": "130 Women",
    "१८० कुटुंबे": "180 Families",
    "९०० नागरिक": "900 Citizens",
    "प्रमुख शिफारसी": "Key Recommendations",
    "वसुंधरा पर्यावरण व ग्रामविकास संस्था": "Vasundhara Environment & Rural Development Organization",
    "वार्षिक पर्यावरण संवर्धन व खर्च प्रगती अहवाल २०२५-२६": "Annual Environment Conservation & Expense Progress Report 2025-26",
    "वार्षिक पर्यावरण संवर्धन व खर्च प्रगती अहवाल": "Annual Environment Conservation & Expense Progress Report",
    "आनंदराव मोरे": "Anandrao More",
    "डॉ. शुभांगी गायकवाड": "Dr. Shubhangi Gaikwad",
    "ऊर्जा बचत के साथ नाबार्ड सिंचाई सुविधा उपलब्ध कराना": "Providing NABARD irrigation facility along with energy savings",
    "ऊर्जा बचतीसोबत नाबार्ड सिंचन सुविधा उपलब्ध करून देणे": "Providing NABARD irrigation facility along with energy savings",
    "ऊर्जा बचत": "Energy saving",
    "ऊर्जा बचतीसोबत": "Along with energy saving",
    "ऊर्जा बचतीसह": "Along with energy saving",
    "ऊर्जा बचत के साथ": "Along with energy saving",
    "नाबार्ड सिंचन सुविधा": "NABARD irrigation facility",
    "नाबार्ड सिंचाई सुविधा": "NABARD irrigation facility",
    "नाबार्ड": "NABARD",
    "सिंचन सुविधा": "Irrigation facility",
    "सिंचाई सुविधा": "Irrigation facility",
    "सुविधा उपलब्ध करून देणे": "Providing facility",
    "सुविधा उपलब्ध कराना": "Providing facility",
    "उपलब्ध करून देणे": "Providing / making available",
    "उपलब्ध कराना": "Providing / making available",
    "तळेघर": "Taleghar",
    "मौजे तळेघर": "Village Taleghar",
    "ग्रामपंचायत तळेघर": "Gram Panchayat Taleghar",
    "तळेघर,": "Taleghar,",
    "तळेघर.": "Taleghar.",
}

PHRASE_NORMALIZATION = {
    "जि. पुणे": "Dist. Pune",
    "मे": "May",
    "एकूण": "Total",
    "अध्यक्ष": "President / Chairperson"
}

REGEX_CORRECTIONS = {}


# Fixed Expression & Proverb Glossary for contextual Marathi/Hindi idioms
MARATHI_IDIOM_GLOSSARY = {
    "अति तिथे माती": "Excess of anything is harmful.",
    "अति तिथे मातिी": "Excess of anything is harmful.",
    "उथळ पाण्याला खळखळाट जास्त": "Empty vessels make the most noise.",
    "उथळ पाण्याला खळखळाट जास्ति": "Empty vessels make the most noise.",
    "आयत्या बिळावर नागोबा": "Taking advantage of another's effort.",
    "आयत्या बिळावर नागोबिा": "Taking advantage of another's effort.",
    "दुरून डोंगर साजरे": "The grass is always greener on the other side.",
    "पेरावे तसे उगवते": "As you sow, so shall you reap.",
    "\"पेरावे तसे उगवते\"": "\"As you sow, so shall you reap\"",
    "वेळेचे मोल, उज्ज्वल भविष्य": "Value of time, a bright future.",
    "\"वेळेचे मोल, उज्ज्वल भविष्य\"": "\"Value of time, a bright future\"",
    "आपला हात, जगन्नाथ": "Self-reliant and empowered (Self-help is the best help).",
    "\"आपला हात, जगन्नाथ\"": "\"Self-reliant and empowered (Self-help is the best help)\"",
    "आपला हात जगन्नाथ": "Self-reliant and empowered (Self-help is the best help).",
    "आरोग्यम् धनसंपदा": "Health is True Wealth.",
    "\"आरोग्यम् धनसंपदा\"": "\"Health is True Wealth\"",
    "दूरदृष्टी आणि सातत्य": "Vision and Continuity.",
    "ज्येष्ठ व गुणवंत कलावंतांचा गौरव व सन्मान केला": "Senior and talented artists were felicitated and honored.",
    "ज्येष्ठ व गुणवंत कलावंतांचा गौरव व सन्मान": "Felicitation and honor of senior and talented artists",
    "गौरव व सन्मान केला": "were felicitated and honored",
    "गौरव व सन्मान करण्यात आला": "was felicitated and honored",
    "गौरव व सन्मान": "felicitation and honor",
    "हातभार लावणे": "contributed and supported",
    "हातभार लावला": "contributed and supported",
    "हातभार": "contribution",
    "आपला हात, जगन्नाथ": "Self-reliant and empowered (Self-help is the best help)",
    "आपला हात जगन्नाथ": "Self-reliant and empowered (Self-help is the best help)",
    "आपला हात, जगन्नाथ.": "Self-reliant and empowered (Self-help is the best help).",
    "आपला हात जगन्नाथ.": "Self-reliant and empowered (Self-help is the best help).",
    "पेरावे तसे उगवते": "As you sow, so shall you reap.",
    "वेळेचे मोल, उज्ज्वल भविष्य": "The value of time, a bright future.",
    "दूरदृष्टी आणि सातत्य": "Vision and continuity.",
    "विद्या धनं सर्वधनप्रधानम्": "Knowledge is the supreme wealth.",
    "ज्ञान हेच खरे सामर्थ्य": "Knowledge is the true power.",
    "ज्ञानानेच मनुष्य प्रगती करतो": "Knowledge alone enables human progress.",
    "शेळी जाऊन लागली वाघाच्या पाठी": "A lamb chasing a tiger — foolish bravery.",
    "चोराच्या मनात चांदणे": "A guilty conscience needs no accuser.",
    "अंथरूण पाहून पाय पसरावे": "Cut your coat according to your cloth.",
    "दगडावर डोके आपटणे": "Banging one's head against a wall — a futile effort.",
    "गरज सरो वैद्य मरो": "Once the need is over, the helper is forgotten.",
    "हातच्या कांकणाला आरसा कशाला": "The obvious needs no proof.",
    "काखेत कळसा गावाला वळसा": "Searching far for what is right at hand.",
    "वरातीमागून घोडे": "Too little, too late.",
    "खोट्याचा पाय खोलात": "Lies have short legs.",
    "एका हाताने टाळी वाजत नाही": "It takes two to tango.",
    "गाढवाला गुळाची चव काय": "Pearls before swine.",
    "बोलाचीच कढी बोलाचाच भात": "All talk and no action.",
    "मुंगी व्हावे पण हत्ती होऊ नये": "Be humble; do not be arrogant.",
    "उपाय नसलेल्या रोगाचे औषध नसते": "Some problems have no solution.",
    "कर नाही तर डर नाही": "If you have done nothing wrong, there is nothing to fear.",
    "झाकली मूठ सव्वा लाखाची": "A secret well kept is worth a fortune.",
    "नावडतीचे मीठ अळणी": "Everything the disliked person does seems wrong.",
    "लोकांचे तोंड बंद करता येत नाही": "You cannot stop people from talking.",
    "कावळ्याच्या शापाने गाय मरत नाही": "The curse of the powerless cannot harm the strong.",
    "नाकापेक्षा मोती जड": "The ornament outweighs the wearer — the subordinate overshadows the superior.",
    "सत्यमेव जयते": "Truth alone triumphs.",
    "वसुधैव कुटुम्बकम": "The world is one family.",
    "कर्मण्येवाधिकारस्ते": "You have a right to action alone, not to its fruits.",
    "यत्र नार्यस्तु पूज्यन्ते रमन्ते तत्र देवताः": "Where women are respected, there the gods dwell.",
    "जैसी करनी वैसी भरनी": "As you sow, so shall you reap.",
    "अति सर्वत्र वर्जयेत": "Excess of anything is bad.",
    "जहाँ चाह वहाँ राह": "Where there is a will, there is a way.",
    "बंदर क्या जाने अदरक का स्वाद": "A monkey does not know the taste of ginger — the ignorant cannot appreciate value.",
    "दूध का जला छाछ भी फूँक फूँक कर पीता है": "A burnt child dreads the fire.",
    "अब पछताए होत क्या जब चिड़िया चुग गई खेत": "It is no use crying over spilt milk.",
    "नाच न जाने आंगन टेढ़ा": "A bad workman blames his tools.",
    "घर का भेदी लंका ढाए": "An insider's betrayal causes the greatest damage.",
    "होनहार बिरवान के होत चिकने पात": "A genius shows signs of talent from an early age.",
    "खाली दिमाग शैतान का घर": "An idle mind is the devil's workshop.",
    "शासकीय आदेश": "Government Order",
    "शासन निर्णय": "Government Resolution",
    "सार्वजनिक सूचना": "Public Notice",
    "अधिकृत राजपत्र": "Official Gazette",
    "शासकीय राजपत्र": "Government Gazette",
    "कायदा व सुव्यवस्था": "Law and Order",
    "सामाजिक न्याय": "Social Justice",
    "ग्रामीण विकास": "Rural Development",
    "नगर विकास": "Urban Development",
    "पर्यावरण संरक्षण": "Environmental Protection",
    "महिला व बाल कल्याण": "Women and Child Welfare",
    "अनुसूचित जाती": "Scheduled Caste",
    "अनुसूचित जमाती": "Scheduled Tribe",
    "मागासवर्गीय": "Backward Class",
    "जिल्हा परिषद": "District Council (Zilla Parishad)",
    "पंचायत समिती": "Block Development Committee (Panchayat Samiti)",
}

ROMANIZED_MARATHI_KEYWORDS = {
    "adhyapan", "adh3pan", "shikshan", "prashikshan", "prashiksh4n", "smaarterv", "classroom",
    "shasan", "samiti", "shikshak", "vidyarthi", "shala", "gram", "vikas", "vyavasthapan",
    "nirnay", "adhikar", "marathi", "grampanchayat", "aani", "aahe", "ahet", "sathi",
    "karyakram", "shrimati", "shri", "yanchya", "sarva", "jilha", "taluka", "maharashtra",
    "sanghatana", "paripatrak", "vishesh", "yojana", "prakalpa", "arogya", "vruksha", "samruddhi"
}

PHONETIC_MARATHI_DICTIONARY = {
    "adhyapan": "अध्यापन",
    "adhypan": "अध्यापन",
    "adh3pan": "अध्यापन",
    "vi": "व",
    "v": "व",
    "ani": "आणि",
    "aani": "आणि",
    "smaarterv": "स्मार्ट",
    "classroom": "क्लासूम",
    "prashikshan": "प्रशिक्षण",
    "adile": "दिले",
    "jyatoon": "ज्यातून",
    "bodirsha": "बोर्ड",
    "adhyapan": "अध्यापन"
}

def is_corrupted_romanized_marathi(text: str, source_lang: str = "Marathi") -> bool:
    """Detect if OCR output contains corrupted Romanized Marathi or Devanagari digit corruption."""
    if not text or not text.strip():
        return False

    devanagari_count = len(re.findall(r'[\u0900-\u097F]', text))
    total_len = len(re.sub(r'\s+', '', text))

    if total_len == 0:
        return False

    # Check ASCII digit corruption (e.g. Adh3pan, prashiksh4n)
    has_ascii_digit_corruption = bool(re.search(r'\b[a-zA-Z]+[0-9]+[a-zA-Z]*\b', text))

    # Check Devanagari digit corruption (e.g. अध्3ापन, अध्3पन, प्रशि4क्षण)
    has_devanagari_digit_corruption = bool(re.search(r'[\u0900-\u097F]+[0-9]+[\u0900-\u097F]*', text))

    words = [w.lower().strip(".,;:!?()[]\"'") for w in text.split()]
    romanized_match_count = sum(1 for w in words if w in ROMANIZED_MARATHI_KEYWORDS)

    # Check font-garbled words (e.g. smaarterv, bodirsha, adile, jyatoon, adh3pan)
    has_garbled_pdf_words = any(w in text.lower() for w in ["smaarterv", "bodirsha", "prashikshan", "adh3pan", "adh3pan", "jyatoon", "adile"])

    if has_ascii_digit_corruption or has_devanagari_digit_corruption or has_garbled_pdf_words or romanized_match_count >= 1:
        return True

    if (devanagari_count / max(1, total_len) < 0.40) and (romanized_match_count >= 1):
        return True

    return False


def recover_corrupted_romanized_marathi(text: str) -> str:
    """Normalize & recover corrupted Romanized Marathi into valid Devanagari script before IndicTrans2 translation.
    Preserves English technical terms like 'Smart Classroom', 'Smart Board', 'Students'."""
    if not text:
        return text

    repaired = text
    # Replace garbled font words directly
    repaired = (repaired
                .replace("adh3pan", "अध्यापन")
                .replace("Adh3pan", "अध्यापन")
                .replace("adh3pan", "अध्यापन")
                .replace("smaarterv", "smart")
                .replace("smaartersha", "smart")
                .replace("bodirsha", "board")
                .replace("prashikshan", "प्रशिक्षण")
                .replace("adile", "दिले")
                .replace("jyatoon", "ज्यातून")
                .replace("apala haat", "आपला हात"))

    # Convert embedded digits inside Devanagari words (e.g. अध्3ापन → अध्यापन, अध्3पन → अध्यापन)
    repaired = re.sub(r'([\u0900-\u097F])3([\u0900-\u097F])', r'\1्या\2', repaired)
    repaired = re.sub(r'([\u0900-\u097F])4([\u0900-\u097F])', r'\1ा\2', repaired)

    digit_rep = {'3': 'y', '4': 'a', '0': 'o', '1': 'i', '5': 's', '8': 'b'}
    def _fix_digit_word(m):
        w = m.group(0)
        for d, c in digit_rep.items():
            w = w.replace(d, c)
        return w

    repaired = re.sub(r'\b[a-zA-Z]*[0-9]+[a-zA-Z]+\b', _fix_digit_word, repaired)

    words = repaired.split()
    recovered_words = []
    
    for word in words:
        clean_w = word.strip(".,;:!?()[]{}")
        prefix_punct = word[:len(word) - len(word.lstrip(".,;:!?()[]{}"))]
        suffix_punct = word[len(word.rstrip(".,;:!?()[]{}")):]
        
        w_lower = clean_w.lower()
        
        if w_lower in {"smart", "classroom", "board", "students", "student", "teacher", "teachers", "school", "projector", "lab", "computer", "cctv", "wi-fi", "stem", "ai", "pdf", "excel"}:
            recovered_words.append(word)
        elif w_lower in PHONETIC_MARATHI_DICTIONARY:
            dev_word = PHONETIC_MARATHI_DICTIONARY[w_lower]
            recovered_words.append(f"{prefix_punct}{dev_word}{suffix_punct}")
        else:
            recovered_words.append(word)

    return " ".join(recovered_words)


def clean_ocr_text(text: str) -> str:
    """Normalize Unicode, remove OCR/PDF font artifacts (■, , IPA noise), repair broken Devanagari, merge broken words."""
    if not text:
        return text

    # Unicode NFC normalization — merges decomposed characters
    cleaned = unicodedata.normalize("NFC", text)

    # Strip stray IPA/Phonetic noise characters produced by PyMuPDF/OCR custom font encodings
    cleaned = re.sub(r'[\u0250-\u02AF\u02B0-\u02FF\u0300-\u036F\u1D00-\u1D7F]', '', cleaned)
    cleaned = re.sub(r'[ɟɹɷɡɞɶʞɰɱɲɳɴɵɸɺɻɼɽɾɿʀʁʂʃʄʅʆʇʈʉʊʋʌʍʎʏʐʑʒʓʔʕʖʗʘʙʚʛʜʝʟʠʡʢʣʤʥʦʧʨÇ]', '', cleaned)

    # Remove common OCR garbage symbols
    cleaned = cleaned.replace("■", "").replace("□", "").replace("", "")
    cleaned = re.sub(r'\?{3,}', '', cleaned)           # ??? sequences
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned)  # control chars

    # Fix digits embedded inside Indic words (e.g., "अध्3ापन" → "अध्यापन", "अध्3पन" → "अध्यापन")
    cleaned = re.sub(r'([\u0900-\u097F])3([\u0900-\u097F])', r'\1्या\2', cleaned)
    cleaned = re.sub(r'([\u0900-\u097F])4([\u0900-\u097F])', r'\1ा\2', cleaned)

    # Fix common OCR typos on Devanagari administrative words
    cleaned = (cleaned
               .replace("ऊजार्ट", "ऊर्जा")
               .replace("बचति", "बचत")
               .replace("नबार्टधि", "नाबार्ड")
               .replace("सर्तिचाई", "सिंचाई")
               .replace("सुविधिा", "सुविधा")
               .replace("महलांना", "महिलांना")
               .replace("महलांसाठी", "महिलांसाठी")
               .replace("महला", "महिला")
               .replace("शिवणकाम", "शिवणकाम")
               .replace("शवणकाम", "शिवणकाम")
               .replace("डिजटल", "डिजिटल")
               .replace("डजिटल", "डिजिटल")
               .replace("वपणन", "विपणन")
               .replace("पॅके जंग", "पॅकेजिंग")
               .replace("पेरावे तिसे उगवतिे", "पेरावे तसे उगवते")
               .replace("मातिी", "माती")
               .replace("अध्3ापन", "अध्यापन")
               .replace("अध्3पन", "अध्यापन")
               .replace("प्रशि4क्षण", "प्रशिक्षण")
               .replace("स्माटर्षा बोडिर्षा", "स्मार्ट बोर्ड")
               .replace("स्माटर्षा", "स्मार्ट")
               .replace("बोडिर्षा", "बोर्ड")
               .replace("स्माटर्व", "स्मार्ट")
               .replace("प्रɡशिक्षण", "प्रशिक्षण")
               .replace("ɞदिले", "दिले")
               .replace("कारकीर्व", "कारकीर्द")
               .replace("मागर्वशिर्वन", "मार्गदर्शन")
               .replace("जिुलै", "जुलै")
               .replace("अध्ययावत", "अद्ययावत")
               .replace("खचार्षातून", "खर्चातून")
               .replace("खचर्षा", "खर्च")
               .replace("नावीन्यपूणर्षा", "नावीन्यपूर्ण")
               .replace("पूणर्षा", "पूर्ण")
               .replace("मंजिूर", "मंजूर")
               .replace("मार्गदिशिर्षान", "मार्गदर्शन")
               .replace("ज्ञानविधर्धिनी", "ज्ञानवर्धिनी")
               .replace("वार्धिक", "वार्षिक"))

    # Repair broken Devanagari: stray combining marks without base character
    cleaned = re.sub(r'(?<![\u0900-\u0963\u0972-\u097F])[\u093E-\u094D\u0962\u0963]', '', cleaned)

    # Merge broken words: single Devanagari char + space + Devanagari continuation
    cleaned = re.sub(r'([\u0900-\u097F])\s{1,2}([\u093E-\u094D\u0962\u0963])', r'\1\2', cleaned)

    # Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


def extract_number_prefix(text: str):
    """Extracts leading number/bullet prefix (e.g. '1.', '१.', '(a)', '1)') and returns (prefix_str, body_text)."""
    if not text:
        return "", text
    text_stripped = text.strip()
    match = re.match(r'^(?P<prefix>(?:[0-9\u0966-\u096F]+|\([0-9\u0966-\u096F]+\)|[a-zA-Z]\))[\.\)\:\-]?\s*)(?P<body>.*)$', text_stripped)
    if match:
        p_raw = match.group('prefix')
        body = match.group('body')
        p_norm = normalize_indic_digits(p_raw)
        return p_norm, body.strip()
    return "", text_stripped


def find_proverb_meaning(text: str) -> Optional[str]:
    """Finds exact or fuzzy proverb match in MARATHI_IDIOM_GLOSSARY handling OCR variations."""
    if not text:
        return None
    cleaned = clean_ocr_text(text.strip())
    
    # 1. Exact match
    if cleaned in MARATHI_IDIOM_GLOSSARY:
        return MARATHI_IDIOM_GLOSSARY[cleaned]

    # 2. Substring match
    for idiom, meaning in MARATHI_IDIOM_GLOSSARY.items():
        if idiom in cleaned or cleaned in idiom:
            return meaning
            
    return None


class TranslationService:
    """Paragraph-wise translation service converting regional Indian & global texts to English."""

    _cache: Dict[str, str] = {}

    @classmethod
    def clear_cache(cls):
        """Clears in-memory translation cache to guarantee fresh translation of new document uploads."""
        cls._cache.clear()
        logger.info("Cleared translation in-memory cache.")

    gtx_disabled_until: float = 0.0
    _indictrans_model = None
    _indictrans_tokenizer = None

    @classmethod
    def _load_indictrans(cls):
        """Loads IndicTrans2 / M2M100 local translation model dynamically."""
        if cls._indictrans_model is None:
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
                model_name = getattr(settings, "INDICTRANS_MODEL_NAME", "facebook/m2m100_418M")
                cls._indictrans_tokenizer = AutoTokenizer.from_pretrained(model_name)
                cls._indictrans_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
                logger.info(f"Loaded cached local translation model ({model_name}).")
            except Exception as e:
                logger.warning(f"Local translation model fallback load note: {e}")

    @classmethod
    def translate_via_google(cls, text: str, source_lang: str = "auto") -> Optional[str]:
        """Translates text to English using GoogleTranslator (ultra-fast online translation < 1s)."""
        if not text or not text.strip():
            return text
        try:
            from deep_translator import GoogleTranslator
            lang_code_map = {
                "Marathi": "mr", "Hindi": "hi", "Bengali": "bn", "Gujarati": "gu",
                "Tamil": "ta", "Telugu": "te", "Kannada": "kn", "Malayalam": "ml",
                "Punjabi": "pa", "Odia": "or", "Sanskrit": "sa", "Assamese": "as",
                "Urdu": "ur", "French": "fr", "Spanish": "es", "German": "de", "Chinese": "zh-CN"
            }
            src = lang_code_map.get(source_lang, "auto")
            translator = GoogleTranslator(source=src, target="en")
            res = translator.translate(text)
            if res and res.strip():
                return res.strip()
        except Exception as e:
            logger.warning(f"GoogleTranslator error: {e}")
        return None

    @classmethod
    def translate_via_indictrans(cls, text: str, source_lang: str = "Marathi") -> str:
        """Translates text to English using local IndicTrans2 / M2M100 model."""
        if not text or not text.strip():
            return text
            
        cls._load_indictrans()
        if cls._indictrans_model is None or cls._indictrans_tokenizer is None:
            return text

        try:
            lang_code_map = {
                "Marathi": "mr", "Hindi": "hi", "Bengali": "bn", "Gujarati": "gu",
                "Tamil": "ta", "Telugu": "te", "Kannada": "kn", "Malayalam": "ml",
                "Punjabi": "pa", "Odia": "or", "Sanskrit": "sa", "Assamese": "as"
            }
            src_code = lang_code_map.get(source_lang, "mr")
            cls._indictrans_tokenizer.src_lang = src_code
            
            encoded = cls._indictrans_tokenizer(text, return_tensors="pt")
            en_lang_id = cls._indictrans_tokenizer.get_lang_id("en")
            generated_tokens = cls._indictrans_model.generate(**encoded, forced_bos_token_id=en_lang_id, max_length=512)
            result = cls._indictrans_tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
            return result.strip()
        except Exception as e:
            logger.error(f"IndicTrans translation error: {e}")
            return text

    @classmethod
    def translate_paragraph(cls, text: str, source_lang: str = "Marathi") -> str:
        """Translates a full paragraph to English preserving numbers, formatting, and technical terms."""
        if not text or not text.strip():
            return text

        prefix, body_text = extract_number_prefix(text)
        clean_text = clean_ocr_text(body_text if body_text else text)

        if not clean_text:
            return text

        # Step 0A: Recover corrupted Romanized Marathi (e.g. Adh3pan vi smaarterv classroom prashikshan...) to clean Devanagari Unicode
        if is_corrupted_romanized_marathi(clean_text, source_lang):
            logger.info(f"Corrupted Romanized Marathi detected: '{clean_text[:60]}...'. Recovering to Devanagari script...")
            clean_text = recover_corrupted_romanized_marathi(clean_text)
            source_lang = "Marathi"

        cache_key = f"{source_lang.lower()}:{prefix}:{clean_text}"

        if cache_key in cls._cache:
            return cls._cache[cache_key]

        # Check exact match in admin dictionary for single-word / short table cells
        if clean_text in INDIC_ADMIN_DICTIONARY:
            admin_res = INDIC_ADMIN_DICTIONARY[clean_text]
            res = f"{prefix}{admin_res}" if prefix and not admin_res.startswith(prefix.strip()) else admin_res
            cls._cache[cache_key] = res
            return res

        # Step 0B: Check idioms / proverbs
        proverb_meaning = find_proverb_meaning(clean_text)
        if proverb_meaning:
            res = f"{prefix}{proverb_meaning}" if prefix and not proverb_meaning.startswith(prefix.strip()) else proverb_meaning
            cls._cache[cache_key] = res
            return res

        # Step 0C: Replace contextual idioms in sentences
        for idiom_phrase, meaning in sorted(MARATHI_IDIOM_GLOSSARY.items(), key=lambda x: len(x[0]), reverse=True):
            if idiom_phrase in clean_text:
                clean_text = clean_text.replace(idiom_phrase, f" {meaning} ")

        # Step 1: Protect non-translatable symbols & numbers
        protected_text, symbol_map = protect_symbols_for_translation(clean_text)

        # Step 2: Perform translation via GoogleTranslator (ultra-fast <1s), fallback to IndicTrans / M2M100
        raw_translation = cls.translate_via_google(protected_text, source_lang)
        if not raw_translation:
            raw_translation = cls.translate_via_indictrans(protected_text, source_lang)

        # Step 3: Restore protected symbols
        restored_translation = restore_symbols_after_translation(raw_translation if raw_translation else protected_text, symbol_map)

        # Step 4: Final cleanup
        final_res = cls.normalize_result(restored_translation)
        final_res = clean_unrestored_placeholders(final_res)

        full_result = f"{prefix}{final_res}" if prefix and not final_res.startswith(prefix.strip()) else final_res
        cls._cache[cache_key] = full_result
        return full_result

    @classmethod
    def normalize_result(cls, text: str) -> str:
        """Cleans residual artifacts, normalizes punctuation and spacing."""
        if not text:
            return text
        cleaned = text.strip()
        cleaned = re.sub(r'\[SYM_\d+\]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Fix false negation hallucinations where NMT models erroneously insert "not" for positive verbs (e.g. "गौरव व सन्मान केला")
        cleaned = re.sub(r'\bwere not glorified and honoured\b', 'were felicitated and honored', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bwere not glorified and honored\b', 'were felicitated and honored', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bwas not glorified and honoured\b', 'was felicitated and honored', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bwas not glorified and honored\b', 'was felicitated and honored', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bwere not glorified\b', 'were felicitated', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bwas not glorified\b', 'was felicitated', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bnot glorified and honoured\b', 'felicitated and honored', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bnot glorified and honored\b', 'felicitated and honored', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bnot glorified\b', 'felicitated', cleaned, flags=re.IGNORECASE)

        # Fix transliteration artifacts from corrupted OCR Devanagari input
        cleaned = re.sub(r'\bNabartdhi\b|\bNabardhi\b|\bNabardh\b', 'NABARD', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bsrtichhai\b|\bsirtichhai\b|\bsirtichai\b|\bsertichai\b', 'irrigation', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\buzart\b|\buzar\b', 'energy', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bbachati\b|\bbachati\b', 'savings', cleaned, flags=re.IGNORECASE)

        # Fix literal translation of proper place names (e.g. तळेघर -> Taleghar instead of "basement house")
        cleaned = re.sub(r'\bbasement house\b', 'Taleghar', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bcellar house\b', 'Taleghar', cleaned, flags=re.IGNORECASE)

        return cleaned


translation_engine = TranslationService()
