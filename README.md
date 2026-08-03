# AI Multilingual Document Translation & Intelligence System

Production-ready, high-performance web application designed to automatically process, OCR, detect multi-lingual paragraphs, translate any type of regional or international document (general text, personal letters, business contracts, legal documents, technical reports, literature, idioms, government forms, certificates, invoices) into English, extract structured metadata JSON fields, preserve original visual layouts, and support full-text English searching across regional documents.

---

## 🌟 Key Features

1. **Supported Input Formats**:
   - PDF & Scanned PDF
   - PNG, JPEG, JPG, TIFF
   - Word Documents (DOCX)
   - Plain Text (TXT)
   - ZIP Archives (Batch processing of multiple files simultaneously)

2. **16 Supported Languages (Automatic Detection)**:
   - Hindi, Marathi, Gujarati, Bengali, Punjabi, Tamil, Telugu, Kannada, Malayalam, Urdu, Odia, Assamese, Bhojpuri, Nepali, Sanskrit, English, and Mixed Language paragraphs.

3. **Advanced Image Preprocessing (OpenCV & NumPy)**:
   - Deskewing & Auto-Rotation
   - FastNLM Noise Removal
   - Sharpening Filter
   - Contrast Limited Adaptive Histogram Equalization (CLAHE)
   - Border Cropping

4. **Multilingual OCR & Layout Parsing**:
   - RapidOCR / PaddleOCR integration
   - Paragraph, line, header, footer, table, and bounding box extraction.
   - Confidence scoring per block and document.

5. **LLM-Enhanced Intelligence & Universal Translation**:
   - Integrated with Gemini & Groq APIs (configured via `.env`).
   - Zero-shot Document Metadata JSON extraction.
   - High-accuracy translation of general, literary, technical, legal, and administrative documents without disclaimers or refusals.
   - Summarization and Document Classification.

6. **Web Dashboard**:
   - Drag & drop document upload.
   - Real-time step-by-step progress indicator.
   - Side-by-Side comparison (Original extracted text vs English translation).
   - Full-text English Search across all translated documents.
   - Filter by Language, Category, Department.
   - Export metadata to Excel.
   - Download generated English output in original uploaded format.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables (`.env`)

```env
APP_NAME="AI Multilingual Document Translation & Intelligence System"
DEBUG=True
HOST=0.0.0.0
PORT=8000
GEMINI_API_KEY="your_optional_gemini_key"
GROQ_API_KEY="your_optional_groq_key"
```

### 3. Launch Application

```bash
uvicorn main:app --reload
```

Open your browser at:
- Web Dashboard: `http://localhost:8000`
- Interactive Swagger API Docs: `http://localhost:8000/docs`

---

## 🐳 Docker Deployment

```bash
docker-compose up --build -d
```

---

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

---

## 📑 REST API Documentation

- `POST /api/v1/upload` - Upload document or ZIP archive
- `GET /api/v1/documents` - Search and list documents with filters
- `GET /api/v1/document/{id}` - Retrieve document details and paragraphs
- `GET /api/v1/download/original/{id}` - Download original document
- `GET /api/v1/download/translated/{id}` - Download generated English PDF
- `GET /api/v1/metadata/{id}` - Get extracted JSON metadata
- `DELETE /api/v1/document/{id}` - Delete document
- `GET /api/v1/export/excel` - Export metadata to Excel sheet
- `POST /api/v1/email/{id}` - Email translated document
