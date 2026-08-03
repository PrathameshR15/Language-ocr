import os
import re
import zipfile
from PIL import Image
from config import settings
from backend.utils.logger import logger

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

class FileValidationError(Exception):
    pass

def sanitize_filename(filename: str) -> str:
    """Strip dangerous characters to prevent directory traversal and OS injection while preserving Indic and unicode filenames."""
    clean_name = os.path.basename(filename)
    # Remove path traversal, control chars, and OS-reserved characters: < > : " / \ | ? * \0
    clean_name = re.sub(r'[\x00-\x1f\x7f<>\:"/\\|?\*]', '', clean_name)
    # Collapse multiple consecutive underscores or spaces
    clean_name = re.sub(r'_+', '_', clean_name)
    clean_name = clean_name.strip(' ._')
    if not clean_name or clean_name == '.' or clean_name.count('_') == len(clean_name):
        return "Government_Document"
    return clean_name

def validate_file_size(file_bytes: bytes) -> bool:
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileValidationError(f"File size exceeds limit of {settings.MAX_FILE_SIZE_MB}MB.")
    return True

def validate_file_extension(filename: str) -> str:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ""
    allowed = [e.lower() for e in settings.ALLOWED_EXTENSIONS]
    if ext not in allowed:
        raise FileValidationError(f"Unsupported file extension '.{ext}'. Allowed: {', '.join(allowed)}")
    return ext

def detect_corrupted_file(file_path: str, ext: str) -> bool:
    """Verify that file can be opened by its target parser without corruption errors."""
    try:
        if ext in ['pdf']:
            if fitz:
                doc = fitz.open(file_path)
                if doc.page_count < 1:
                    raise FileValidationError("PDF file contains no pages.")
                doc.close()
        elif ext in ['png', 'jpg', 'jpeg', 'tiff', 'bmp']:
            with Image.open(file_path) as img:
                img.verify()
        elif ext in ['docx']:
            if DocxDocument:
                DocxDocument(file_path)
        elif ext in ['zip']:
            with zipfile.ZipFile(file_path, 'r') as zf:
                bad_file = zf.testzip()
                if bad_file:
                    raise FileValidationError(f"Corrupted zip archive at entry: {bad_file}")
        elif ext in ['txt']:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as tf:
                tf.read(100)
        return True
    except Exception as e:
        logger.error(f"Corruption check failed for {file_path}: {str(e)}")
        raise FileValidationError(f"Corrupted or unreadable file: {str(e)}")
