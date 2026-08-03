from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class MetadataSchema(BaseModel):
    state: Optional[str] = "N/A"
    district: Optional[str] = "N/A"
    department: Optional[str] = "N/A"
    doc_number: Optional[str] = "N/A"
    reference_number: Optional[str] = "N/A"
    date: Optional[str] = "N/A"
    issue_date: Optional[str] = "N/A"
    subject: Optional[str] = "N/A"
    authority_name: Optional[str] = "N/A"
    officer_name: Optional[str] = "N/A"
    election_constituency: Optional[str] = "N/A"
    polling_booth: Optional[str] = "N/A"
    village: Optional[str] = "N/A"
    taluka: Optional[str] = "N/A"
    pin_code: Optional[str] = "N/A"
    phone_number: Optional[str] = "N/A"
    email: Optional[str] = "N/A"
    website: Optional[str] = "N/A"
    summary: Optional[str] = ""
    doc_category: Optional[str] = "General Document"

class ExtractedTextParagraph(BaseModel):
    paragraph: int
    page: int
    language: str
    text: str
    translated_text: str
    confidence: float = 0.90

class DocumentDetailResponse(BaseModel):
    id: str
    filename: str
    language: str
    translated_language: str = "English"
    upload_time: str
    processing_time: float
    status: str
    confidence: float
    original_pdf_path: str
    translated_pdf_path: str
    metadata_json: Dict[str, Any]
    paragraphs: Optional[List[ExtractedTextParagraph]] = []

class DocumentListResponse(BaseModel):
    total: int
    documents: List[DocumentDetailResponse]

class MessageResponse(BaseModel):
    message: str
    id: Optional[str] = None

class DocumentUpdateRequest(BaseModel):
    filename: Optional[str] = None

