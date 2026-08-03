import re
import unicodedata
from typing import Dict, Tuple, List, Any

def classify_character(char: str) -> str:
    """
    Classifies a Unicode character into defined categories per Unicode specification.
    """
    if not char:
        return "Unknown"
    
    code = ord(char)
    cat = unicodedata.category(char)

    # Indic scripts (Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam, Sinhala)
    if 0x0900 <= code <= 0x0DFF:
        if cat.startswith("N"):
            return "Numeric"
        return "Alphabetic"
    
    # Check for Emojis
    if (0x1F600 <= code <= 0x1F64F) or (0x1F300 <= code <= 0x1F5FF) or \
       (0x1F680 <= code <= 0x1F6FF) or (0x2600 <= code <= 0x26FF) or \
       (0x2700 <= code <= 0x27BF):
        return "Emoji"
        
    if cat.startswith("L"):
        return "Alphabetic"
    elif cat.startswith("N"):
        return "Numeric"
    elif cat.startswith("Z"):
        return "Whitespace"
    elif cat.startswith("P"):
        return "Punctuation"
    elif cat == "Sm":
        return "Mathematical Symbol"
    elif cat == "Sc":
        return "Currency Symbol"
    elif cat in ("So", "Sk"):
        return "Unicode Symbol"
    elif cat.startswith("C"):
        return "Control Character"
    return "Unicode Symbol"


# Set of rare graphics/bullet symbols that require placeholder protection (standard punctuation is NEVER turned into placeholders)
EXPLICIT_PROTECTED_SYMBOLS = {
    '•', '○', '●', '✓', '✔', '✗', '★', '☆', '☑', '☐', '☒', '│', '─', '┌', '┐', '└', '┘', '├', '┤', '┬', '┴', '┼'
}


def is_protected_symbol(char: str) -> bool:
    """Determines whether a character is a non-text graphic symbol that should be preserved verbatim."""
    if not char:
        return False
    code = ord(char)
    if 0x0900 <= code <= 0x0DFF:
        return False
    if char in EXPLICIT_PROTECTED_SYMBOLS:
        return True
    cat = classify_character(char)
    return cat in ("Unicode Symbol", "Emoji")



def protect_symbols_for_translation(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Scans text for non-text symbols, currency, emails, URLs, file/reference IDs, phone numbers,
    and technical/smart English terms (e.g. "Smart Classroom", "Smart Board", "Students"),
    replacing them with immutable placeholders [[SYM_0]], [[SYM_1]], ...
    Returns (protected_text, symbol_map).
    """
    if not text:
        return text, {}

    symbol_map: Dict[str, str] = {}
    sym_counter = 0

    working_text = text

    # English technical & educational terms that should be preserved as-is in mixed-language text
    ENGLISH_PRESERVE_PATTERNS = [
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Classroom|Board|Lab|System|Portal|Projector|Display|School|Students|Teacher|PDF|DOCX|ZIP|App|Website|Center|Camp|Drive|Kit|Room))s?\b',
        r'\b(?:Smart\s+Classroom|Smart\s+Board|Digital\s+Board|Computer\s+Lab|CCTV|Wi-Fi|STEM|AI|Excel|Word|PDF|DOCX|TXT|ZIP|Online|Portal)\b',
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',  # Email addresses
        r'https?://[^\s]+',                                     # URLs
        r'\b(?:Ref|File|Doc|No|ID|क्र)[\s.:#-]*[A-Za-z0-9/_-]+\b', # Reference/File IDs
        r'\b(?:\+91[\s-]?)?[6-9]\d{9}\b',                      # Phone numbers
    ]

    # Only protect English preserve patterns if the text contains non-Latin (e.g. Devanagari) content
    has_indic = bool(re.search(r'[\u0900-\u0DFF]', text))
    patterns_to_run = ENGLISH_PRESERVE_PATTERNS if has_indic else ENGLISH_PRESERVE_PATTERNS[2:]

    for pat in patterns_to_run:
        matches = list(re.finditer(pat, working_text, flags=re.IGNORECASE))
        for m in reversed(matches):
            token = m.group(0)
            placeholder = f"[[SYM_{sym_counter}]]"
            symbol_map[placeholder] = token
            working_text = working_text[:m.start()] + placeholder + working_text[m.end():]
            sym_counter += 1

    protected_chunks = []
    i = 0
    n = len(working_text)
    
    while i < n:
        char = working_text[i]
        
        # Check if character is a symbol requiring protection
        if is_protected_symbol(char):
            sym_chars = [char]
            i += 1
            while i < n and is_protected_symbol(working_text[i]):
                sym_chars.append(working_text[i])
                i += 1
            
            sym_str = "".join(sym_chars)
            placeholder = f"[[SYM_{sym_counter}]]"
            symbol_map[placeholder] = sym_str
            protected_chunks.append(placeholder)
            sym_counter += 1
        else:
            protected_chunks.append(char)
            i += 1

    protected_text = "".join(protected_chunks)
    return protected_text, symbol_map



def restore_symbols_after_translation(translated_text: str, symbol_map: Dict[str, str]) -> str:
    """
    Restores original symbol strings from [[SYM_X]] placeholders in translated_text,
    handling any spaces or formatting variations inserted by translation models
    (e.g. [[ SYM_0 ]], [[SYM_0 ]], [SYM_0], [SYM 0], SYM_0).
    """
    if not translated_text:
        return translated_text

    result = translated_text
    if symbol_map:
        for placeholder, original_symbol in symbol_map.items():
            # Exact match
            result = result.replace(placeholder, original_symbol)
            
            sym_num = placeholder.strip("[]SYM_")
            # Handle model variations: [[ SYM_0 ]], [SYM_0], [SYM 0], [[SYM 0]], (SYM_0)
            patterns = [
                re.compile(rf'\[\[\s*SYM[_\s]*{sym_num}\s*\]\]', re.IGNORECASE),
                re.compile(rf'\[\s*SYM[_\s]*{sym_num}\s*\]', re.IGNORECASE),
                re.compile(rf'\(\s*SYM[_\s]*{sym_num}\s*\)', re.IGNORECASE),
                re.compile(rf'\bSYM[_\s]*{sym_num}\b', re.IGNORECASE),
            ]
            for pat in patterns:
                result = pat.sub(original_symbol, result)

    # Clean any remaining unrestored placeholders or artifacts
    return clean_unrestored_placeholders(result, symbol_map)


def normalize_indic_digits(text: str) -> str:
    """Converts Indic digits (०-९) to ASCII digits (0-9), standardizes currency symbols (₹ → Rs. ), and removes black boxes."""
    if not text:
        return text
    
    res = text
    # Convert Rupee symbol ₹ or ₹ to Rs.
    res = res.replace('₹', 'Rs. ').replace('₹ ', 'Rs. ')
    
    # Convert Devanagari digits ०-९ to ASCII digits 0-9
    digit_map = {'०': '0', '१': '1', '२': '2', '३': '3', '४': '4', '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'}
    for d_indic, d_ascii in digit_map.items():
        res = res.replace(d_indic, d_ascii)
        
    # Clean up double Rs. Rs.
    res = re.sub(r'\bRs\.\s*Rs\.\b', 'Rs.', res)
    # Strip any black boxes or missing glyph markers
    res = res.replace('■', '').replace('□', '').replace('\ufffd', '')
    return res

def clean_unrestored_placeholders(text: str, symbol_map: Dict[str, str] = None) -> str:
    """
    Final safety pass ensuring zero leftover [[SYM_X]], [SYM_X], or black square (■, □, )
    characters appear in the final translated text.
    """
    if not text:
        return text

    res = text
    # Remove black squares and missing glyph markers
    res = res.replace("■", "").replace("□", "").replace("\ufffd", "")
    res = re.sub(r'\?{3,}', '', res)

    # Remove any un-mapped leftover SYM placeholders (e.g. [[SYM_99]], [SYM_5], etc.)
    res = re.sub(r'\[\[?\s*SYM[_\s]*\d+\s*\]\]?', '', res, flags=re.IGNORECASE)
    res = re.sub(r'\(?\s*SYM[_\s]*\d+\s*\)?', '', res, flags=re.IGNORECASE)

    # Convert ₹ to Rs.
    res = res.replace('₹', 'Rs. ')

    # Collapse multiple spaces
    res = re.sub(r'\s+', ' ', res).strip()
    return res


def normalize_unicode_nfc(text: str) -> str:
    """Normalizes text using NFC while preserving combining characters and zero-width joiners."""
    if not text:
        return text
    return unicodedata.normalize('NFC', text)


def repair_devanagari_ocr_errors(text: str) -> str:
    """Repairs common Devanagari and Indic OCR errors, broken matras, split words, and invalid Unicode sequences."""
    if not text:
        return text

    res = normalize_unicode_nfc(text)

    # 1. Strip black square artifacts & invalid replacement characters
    res = res.replace("■", "").replace("□", "").replace("\ufffd", "").replace("", "")
    res = re.sub(r'[\u25A0-\u25FF]', '', res)  # Remove geometric box shapes

    # 2. Repair common Devanagari OCR misread characters & matra disjunctions
    # e.g. standalone matras after space: "क र ता" -> "करता", standalone nukta
    res = re.sub(r'([\u0905-\u0939])\s+([\u093E-\u094D])', r'\1\2', res)
    # Repair zero-width spaces/joiners inside words
    res = res.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')

    # 3. Devanagari common OCR typo dictionary replacements
    devanagari_typo_fixes = {
        "सा सन": "शासन",
        "शा सन": "शासन",
        "नि र्णय": "निर्णय",
        "नि णीय": "निर्णय",
        "म हा राष्ट्र": "महाराष्ट्र",
        "जिल् हाधिकारी": "जिल्हाधिकारी",
        "तह सीलदार": "तहसीलदार",
        "दि नांक": "दिनांक",
        "प्र क्रि या": "प्रक्रिया",
    }
    for typo, fix in devanagari_typo_fixes.items():
        res = res.replace(typo, fix)

    return res.strip()


def normalize_dates_and_numbers(text: str) -> str:
    """Normalizes dates (e.g. २५/०८/२०२५ -> 25/08/2025), currency, and Indic digits."""
    if not text:
        return text

    # First convert Indic digits
    res = normalize_indic_digits(text)

    # Format slash/dot separated dates: e.g. 25 / 08 / 2025 -> 25/08/2025
    res = re.sub(r'(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{2,4})', r'\1/\2/\3', res)
    
    return res


def merge_lines_into_paragraphs(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges broken line fragments into coherent paragraph blocks using visual layout coordinates.
    
    Lines are grouped if they share the same page, have similar left/right alignment,
    and vertical distance between consecutive lines is less than 1.5x line height.
    """
    if not lines:
        return []

    # Sort lines by page number, top-to-bottom y0, then left-to-right x0
    sorted_lines = sorted(lines, key=lambda l: (l.get("page", 1), l.get("bbox", [0,0,0,0])[1], l.get("bbox", [0,0,0,0])[0]))

    merged_paragraphs = []
    current_para = None

    for line in sorted_lines:
        txt = line.get("text", "").strip()
        if not txt:
            continue

        bbox = line.get("bbox", [0, 0, 100, 20])
        pg = line.get("page", 1)

        if current_para is None:
            current_para = dict(line)
            current_para["bbox"] = list(bbox)
            current_para["text"] = txt
            continue

        prev_pg = current_para.get("page", 1)
        prev_bbox = current_para["bbox"]
        prev_h = max(10.0, prev_bbox[3] - prev_bbox[1])
        y_gap = bbox[1] - prev_bbox[3]

        # Group if same page and vertical gap is less than 1.5 line height
        if pg == prev_pg and -5 <= y_gap <= (1.8 * prev_h):
            current_para["text"] += f" {txt}"
            # Expand bounding box to encompass merged line
            current_para["bbox"] = [
                min(current_para["bbox"][0], bbox[0]),
                min(current_para["bbox"][1], bbox[1]),
                max(current_para["bbox"][2], bbox[2]),
                max(current_para["bbox"][3], bbox[3])
            ]
            current_para["confidence"] = round(min(current_para.get("confidence", 0.9), line.get("confidence", 0.9)), 2)
        else:
            merged_paragraphs.append(current_para)
            current_para = dict(line)
            current_para["bbox"] = list(bbox)
            current_para["text"] = txt

    if current_para:
        merged_paragraphs.append(current_para)

    return merged_paragraphs



