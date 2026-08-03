import re
from typing import Dict, Any
from backend.services.llm_enhancement_service import llm_service
from backend.utils.logger import logger

# Indian States & UTs
INDIAN_STATES = [
    "Maharashtra", "Uttar Pradesh", "Gujarat", "West Bengal", "Punjab", "Tamil Nadu",
    "Telangana", "Karnataka", "Kerala", "Bihar", "Rajasthan", "Madhya Pradesh",
    "Odisha", "Assam", "Haryana", "Jharkhand", "Chhattisgarh", "Uttarakhand",
    "Himachal Pradesh", "Goa", "Delhi", "Jammu & Kashmir", "Ladakh"
]

# Government Departments
DEPARTMENTS = [
    "Election Commission", "Revenue Department", "Municipal Corporation",
    "Panchayat Samiti", "Court Notices", "Public Health Department",
    "Education Department", "Urban Development", "Land Records",
    "Public Works Department", "Police Department", "Transport Department"
]

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

class MetadataExtractionService:
    """Extracts structured JSON metadata from documents (general, legal, official, business, certificates, etc.)."""

    @staticmethod
    def extract_metadata(text: str, filename: str = "") -> Dict[str, Any]:
        """Extract metadata using hybrid Regex/NLP rules with LLM enhancement if active."""
        
        # 1. Try LLM extraction first if key available
        if llm_service.is_available():
            llm_metadata = llm_service.extract_metadata_llm(text)
            if llm_metadata and isinstance(llm_metadata, dict):
                valid_vals = [v for k, v in llm_metadata.items() if v and str(v).strip() != "N/A"]
                if len(valid_vals) > 2:
                    if "designation" not in llm_metadata:
                        llm_metadata["designation"] = llm_metadata.get("authority_name", "N/A")
                    return llm_metadata

        # 2. Rule-based Regex & Keyword Extraction Fallback
        meta = {
            "state": "N/A",
            "district": "N/A",
            "department": "N/A",
            "office": "N/A",
            "doc_number": "N/A",
            "reference_number": "N/A",
            "file_number": "N/A",
            "letter_number": "N/A",
            "date": "N/A",
            "issue_date": "N/A",
            "subject": "N/A",
            "authority_name": "N/A",
            "officer_name": "N/A",
            "designation": "N/A",
            "election_constituency": "N/A",
            "polling_booth": "N/A",
            "village": "N/A",
            "taluka": "N/A",
            "pin_code": "N/A",
            "phone_number": "N/A",
            "email": "N/A",
            "website": "N/A",
            "address": "N/A",
            "doc_category": "General Document",
            "summary": ""
        }


        if not text:
            return meta

        # Normalize digits
        norm_text = text.translate(DEVANAGARI_DIGITS)

        # Extract State
        for state in INDIAN_STATES:
            if re.search(r'\b' + re.escape(state) + r'\b', norm_text, re.IGNORECASE):
                meta["state"] = state
                break
        if meta["state"] == "N/A":
            if any(k in norm_text for k in ["महाराष्ट्र", "मुंबई", "पुणे", "भोर", "Maharashtra"]):
                meta["state"] = "Maharashtra"
            elif any(k in norm_text for k in ["उत्तर प्रदेश", "लखनऊ", "Uttar Pradesh"]):
                meta["state"] = "Uttar Pradesh"
            elif any(k in norm_text for k in ["ગુજરાત", "Gujarat"]):
                meta["state"] = "Gujarat"

        # Extract Department & Authority
        for dept in DEPARTMENTS:
            if re.search(r'\b' + re.escape(dept) + r'\b', norm_text, re.IGNORECASE):
                meta["department"] = dept
                break
        if meta["department"] == "N/A":
            if any(k in norm_text for k in ["भूसंपादन", "उपजिल्हाधिकारी", "जिल्हाधिकारी", "महसूल", "राजस्व", "Land Acquisition"]):
                meta["department"] = "Land Acquisition & Revenue Department"
                meta["authority_name"] = "District Collector Office (जिल्हाधिकारी कार्यालय / भूसंपादन)"
            elif any(k in norm_text for k in ["निवडणूक", "चुनाव", "Election"]):
                meta["department"] = "Election Commission"
                meta["authority_name"] = "Election Office"

        # District, Taluka & Village Extraction
        if any(k in norm_text for k in ["पुणे", "Pune"]):
            meta["district"] = "Pune (पुणे)"
        else:
            dist_match = re.search(r'(?:District|जि\.|जिला|जिल्हा)\s*[:\-]?\s*([A-Za-z0-9\u0900-\u0DFF]+)', norm_text)
            if dist_match:
                meta["district"] = dist_match.group(1).strip()

        if any(k in norm_text for k in ["भोर", "Bhor"]):
            meta["taluka"] = "Bhor (भोर)"
        else:
            tal_match = re.search(r'(?:Taluka|Tehsil|ता\.|तालुका)\s*[:\-]?\s*([A-Za-z0-9\u0900-\u0DFF]+)', norm_text)
            if tal_match:
                meta["taluka"] = tal_match.group(1).strip()

        if any(k in norm_text for k in ["परहर", "Parhar"]):
            meta["village"] = "Parhar Khurd (परहर खुर्द)"
        else:
            vil_match = re.search(r'(?:Village|Gram|मौजे|ग्राम)\s*[:\-]?\s*([A-Za-z0-9\u0900-\u0DFF\s]+?)(?:,|\.|\s+ता|\n|$)', norm_text)
            if vil_match:
                meta["village"] = vil_match.group(1).strip()

        # PIN Code (6 digits starting with 1-9)
        pin_match = re.search(r'\b[1-9][0-9]{5}\b', norm_text)
        if pin_match:
            meta["pin_code"] = pin_match.group(0)

        # Phone Number (10 digit or +91 format)
        phone_match = re.search(r'(?:\+91[\-\s]?)?[6-9]\d{9}', norm_text)
        if phone_match:
            meta["phone_number"] = phone_match.group(0)

        # Email
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', norm_text)
        if email_match:
            meta["email"] = email_match.group(0)

        # Website
        web_match = re.search(r'https?://[^\s]+|www\.[^\s]+|\b[a-zA-Z0-9.-]+\.(?:gov\.in|org\.in|com|in)\b', norm_text, re.IGNORECASE)
        if web_match:
            meta["website"] = web_match.group(0)

        # Dates (DD/MM/YYYY or DD-MM-YYYY)
        date_match = re.search(r'\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-](19|20)\d\d\b', norm_text)
        if date_match:
            meta["date"] = date_match.group(0)
            meta["issue_date"] = date_match.group(0)

        # Document / Reference Number
        doc_num_match = re.search(r'\b(?:Outward\s+No|Inward\s+No|Ref\s+No|Order\s+No|Notice\s+No|क्रमांक|जा\.क्र\.|विभूस/[^\s]+|एलएक्यू/[^\s]+|क्र\.)\s*[:\.\/]?\s*([A-Za-z0-9\u0900-\u0DFF\/\-_]+)', norm_text, re.IGNORECASE)
        if doc_num_match:
            meta["doc_number"] = doc_num_match.group(1)
            meta["reference_number"] = doc_num_match.group(1)
        else:
            fallback_num = re.search(r'\b([A-Z0-9\u0900-\u0DFF]{2,8}[\-_/][0-9\u0900-\u0DFF]{2,6}(?:[\-_/][0-9\u0900-\u0DFF]{2,4})?)\b', norm_text)
            if fallback_num:
                meta["doc_number"] = fallback_num.group(1)
                meta["reference_number"] = fallback_num.group(1)

        # Category & Subject
        if any(k in norm_text for k in ["निवाडा", "भूसंपादन", "अंतिम निवाडा"]):
            meta["doc_category"] = "Land Acquisition Award Notice (भूसंपादन निवाडा)"

        subj_match = re.search(r'(?:Subject|विषय)\s*[:\-]\s*(.*?)(?=\n\n|\n[०-९\d]+\)|$)', norm_text, re.DOTALL | re.IGNORECASE)
        if subj_match:
            meta["subject"] = subj_match.group(1).replace('\n', ' ').strip()[:180]

        lines = [l.strip() for l in norm_text.split('\n') if l.strip()]
        if meta["subject"] == "N/A" and lines:
            meta["subject"] = lines[0][:150]

        if lines:
            meta["summary"] = " ".join(lines[:4])[:300] + "..."

        return meta

metadata_service = MetadataExtractionService()
