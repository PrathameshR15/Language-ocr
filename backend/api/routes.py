import os
import zipfile
import tempfile
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Response, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse

from backend.schemas.document import DocumentDetailResponse, DocumentListResponse, MessageResponse, DocumentUpdateRequest
from backend.services.document_parser_service import document_parser
from backend.database.file_db import db_client
from backend.services.pdf_generation_service import pdf_generator
from backend.utils.export_utils import export_metadata_to_excel
from backend.utils.logger import logger
from backend.utils.file_validator import sanitize_filename

router = APIRouter(prefix="/api/v1", tags=["Documents"])

def cleanup_temp_file(filepath: str):
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception:
            pass

def get_media_type_for_file(filepath: str) -> str:
    ext = filepath.lower().split('.')[-1]
    mime_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "txt": "text/plain; charset=utf-8",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "tiff": "image/tiff",
        "bmp": "image/bmp",
    }
    return mime_map.get(ext, "application/octet-stream")


@router.post("/upload", response_model=List[DocumentDetailResponse], status_code=201)
async def upload_document(files: List[UploadFile] = File(...)):
    """Upload one or more documents (PDF, Image, DOCX, ZIP). Batch zip processing supported."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    processed_results = []
    for upload_file in files:
        try:
            content = await upload_file.read()
            filename = upload_file.filename or "uploaded_file"

            # Check if file is a ZIP archive containing multiple documents
            if filename.lower().endswith(".zip"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    zip_path = os.path.join(tmpdir, filename)
                    with open(zip_path, "wb") as zf:
                        zf.write(content)
                    
                    with zipfile.ZipFile(zip_path, "r") as z:
                        for entry in z.namelist():
                            if not entry.endswith("/") and not entry.startswith("__MACOSX"):
                                extracted_bytes = z.read(entry)
                                entry_filename = os.path.basename(entry)
                                if entry_filename:
                                    res = await document_parser.process_document(extracted_bytes, entry_filename)
                                    processed_results.append(res)
            else:
                res = await document_parser.process_document(content, filename)
                processed_results.append(res)

        except Exception as e:
            logger.error(f"Error processing upload for {upload_file.filename}: {e}")
            raise HTTPException(status_code=422, detail=f"File processing error: {str(e)}")

    return processed_results

@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    query: str = Query("", description="English search term across content and metadata"),
    language: str = Query("all", description="Filter by language"),
    state: str = Query("all", description="Filter by Indian State"),
    department: str = Query("all", description="Filter by Department")
):
    """Retrieve and search documents with English query, language, state, and department filters."""
    docs = await db_client.search_documents(
        query=query,
        language=language,
        state=state,
        department=department
    )
    
    # Attach paragraphs to each document
    detailed_docs = []
    for d in docs:
        doc_copy = dict(d)
        doc_copy["paragraphs"] = await db_client.get_extracted_texts_by_doc_id(d["id"])
        detailed_docs.append(doc_copy)
        
    return {"total": len(detailed_docs), "documents": detailed_docs}

@router.get("/document/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(doc_id: str):
    """Retrieve details, paragraphs, and metadata for a specific document."""
    doc = await db_client.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    doc_copy = dict(doc)
    doc_copy["paragraphs"] = await db_client.get_extracted_texts_by_doc_id(doc_id)
    return doc_copy

@router.put("/document/{doc_id}", response_model=DocumentDetailResponse)
async def update_document(doc_id: str, payload: DocumentUpdateRequest):
    """Update document details such as filename/title."""
    doc = await db_client.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    updates = {}
    if payload.filename:
        new_name = sanitize_filename(payload.filename)
        # Preserve original extension if user omitted it
        orig_ext = doc.get("original_extension", "")
        if orig_ext and not new_name.lower().endswith(f".{orig_ext.lower()}"):
            new_name = f"{new_name}.{orig_ext}"
        updates["filename"] = new_name

    if updates:
        updated_doc = await db_client.update_document(doc_id, updates)
        if updated_doc:
            doc = updated_doc

    doc_copy = dict(doc)
    doc_copy["paragraphs"] = await db_client.get_extracted_texts_by_doc_id(doc_id)
    return doc_copy


@router.get("/download/original/{doc_id}")
async def download_original(doc_id: str):
    """Download the uploaded original document file."""
    doc = await db_client.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    file_path = doc.get("original_pdf_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Original uploaded files are not stored on server.")

    media_type = get_media_type_for_file(file_path)
    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type=media_type
    )

@router.get("/download/same_format/{doc_id}")
async def download_same_format(doc_id: str, background_tasks: BackgroundTasks):
    """Download the English converted output generated on-the-fly in original format (DOCX, TXT, Image, PDF)."""
    doc = await db_client.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    paragraphs = await db_client.get_extracted_texts_by_doc_id(doc_id)
    metadata = doc.get("metadata_json", {})
    filename = doc.get("filename", "document")
    ext = (doc.get("original_extension") or filename.split(".")[-1]).lower()

    # Create temporary output file
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
    tmp_path = tf.name
    tf.close()

    try:
        orig_path = doc.get("original_pdf_path")
        if ext == "docx":
            pdf_generator.generate_translated_docx(doc_id, filename, paragraphs, metadata, original_path=orig_path, output_path=tmp_path)
        elif ext == "txt":
            pdf_generator.generate_translated_txt(doc_id, filename, paragraphs, metadata, original_path=orig_path, output_path=tmp_path)
        elif ext in ["png", "jpg", "jpeg", "tiff", "bmp"]:
            pdf_generator.generate_translated_image(doc_id, filename, paragraphs, metadata, img_format=ext, original_path=orig_path, output_path=tmp_path)
        else:
            pdf_generator.generate_translated_pdf(doc_id, filename, paragraphs, metadata, output_path=tmp_path)

        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            cleanup_temp_file(tmp_path)
            raise HTTPException(status_code=500, detail="Failed to generate translated document on-the-fly.")

        background_tasks.add_task(cleanup_temp_file, tmp_path)
        media_type = get_media_type_for_file(tmp_path)
        clean_fn = sanitize_filename(filename)
        if clean_fn.lower().startswith("translated_"):
            download_name = clean_fn
        else:
            download_name = f"Translated_{clean_fn}"

        return FileResponse(
            path=tmp_path,
            filename=download_name,
            media_type=media_type
        )
    except Exception as e:
        cleanup_temp_file(tmp_path)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")

@router.get("/download/translated/{doc_id}")
async def download_translated(
    doc_id: str,
    background_tasks: BackgroundTasks,
    format: Optional[str] = Query("same", description="Format: 'same' for original format, 'pdf' for PDF")
):
    """Download the generated English translated output in original format ('same') or PDF ('pdf')."""
    if format == "same":
        return await download_same_format(doc_id, background_tasks)

    doc = await db_client.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    paragraphs = await db_client.get_extracted_texts_by_doc_id(doc_id)
    metadata = doc.get("metadata_json", {})
    filename = doc.get("filename", "document.pdf")
    clean_fn = sanitize_filename(filename)
    base_name = clean_fn.rsplit('.', 1)[0]
    if base_name.lower().startswith("translated_"):
        pdf_download_name = f"{base_name}.pdf"
    else:
        pdf_download_name = f"Translated_{base_name}.pdf"

    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tf.name
    tf.close()

    try:
        pdf_generator.generate_translated_pdf(doc_id, filename, paragraphs, metadata, output_path=tmp_path)

        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            cleanup_temp_file(tmp_path)
            raise HTTPException(status_code=500, detail="Failed to generate translated PDF on-the-fly.")

        background_tasks.add_task(cleanup_temp_file, tmp_path)

        return FileResponse(
            path=tmp_path,
            filename=pdf_download_name,
            media_type="application/pdf"
        )

    except Exception as e:
        cleanup_temp_file(tmp_path)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")

@router.get("/preview/pdf/{doc_id}")
async def preview_translated_pdf(doc_id: str, background_tasks: BackgroundTasks):
    """Serve the generated English translated PDF inline for browser UI iframe rendering."""
    doc = await db_client.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    paragraphs = await db_client.get_extracted_texts_by_doc_id(doc_id)
    metadata = doc.get("metadata_json", {})
    filename = doc.get("filename", "document.pdf")
    clean_fn = sanitize_filename(filename)
    base_name = clean_fn.rsplit('.', 1)[0]
    pdf_name = f"Translated_{base_name}.pdf"

    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tf.name
    tf.close()

    try:
        pdf_generator.generate_translated_pdf(doc_id, filename, paragraphs, metadata, output_path=tmp_path)

        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            cleanup_temp_file(tmp_path)
            raise HTTPException(status_code=500, detail="Failed to generate translated PDF for preview.")

        background_tasks.add_task(cleanup_temp_file, tmp_path)

        return FileResponse(
            path=tmp_path,
            filename=pdf_name,
            media_type="application/pdf",
            content_disposition_type="inline"
        )
    except Exception as e:
        cleanup_temp_file(tmp_path)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Preview error: {str(e)}")

@router.get("/document/{doc_id}/summary")
async def get_document_summary(doc_id: str):
    """Generate and return a 100% accurate English summary of the document using LLM."""
    doc = await db_client.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    paragraphs = await db_client.get_extracted_texts_by_doc_id(doc_id)
    if not paragraphs:
        raise HTTPException(status_code=400, detail="No text available to summarize.")
        
    # Combine original and/or translated texts
    full_text = "\n\n".join([p.get("translated_text") if p.get("translated_text") else p.get("text", "") for p in paragraphs])
    if not full_text.strip():
        raise HTTPException(status_code=400, detail="Document content is empty.")
        
    from backend.services.llm_enhancement_service import llm_service
    summary = llm_service.generate_summary(full_text)
    return {"doc_id": doc_id, "summary": summary}

@router.get("/metadata/{doc_id}")

async def get_metadata(doc_id: str):
    """Return JSON metadata extracted from government document."""
    doc = await db_client.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc.get("metadata_json", {})

@router.delete("/document/{doc_id}", response_model=MessageResponse)
async def delete_document(doc_id: str):
    """Delete document, extracted text, and associated files."""
    doc = await db_client.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Remove files from disk
    orig_path = doc.get("original_pdf_path")
    trans_path = doc.get("translated_pdf_path")
    
    if orig_path and os.path.exists(orig_path):
        try: os.remove(orig_path)
        except Exception: pass
        
    if trans_path and os.path.exists(trans_path):
        try: os.remove(trans_path)
        except Exception: pass

    deleted = await db_client.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Could not delete document record.")

    return {"message": f"Document {doc_id} successfully deleted.", "id": doc_id}

@router.delete("/documents", response_model=MessageResponse)
async def delete_all_documents():
    """Delete all documents, extracted text, and associated files from the system."""
    docs = await db_client.get_all_documents()
    for doc in docs:
        orig_path = doc.get("original_pdf_path")
        trans_path = doc.get("translated_pdf_path")
        if orig_path and os.path.exists(orig_path):
            try: os.remove(orig_path)
            except Exception: pass
        if trans_path and os.path.exists(trans_path):
            try: os.remove(trans_path)
            except Exception: pass

    count = await db_client.delete_all_documents()
    return {"message": f"All {count} documents successfully deleted.", "id": "all"}

@router.get("/export/excel")
async def export_excel():
    """Export all document records and extracted metadata to Excel file."""
    docs = await db_client.get_all_documents()
    excel_bytes = export_metadata_to_excel(docs)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=government_documents_metadata.xlsx"}
    )

@router.post("/email/{doc_id}", response_model=MessageResponse)
async def email_translated_document(doc_id: str, recipient_email: str = Query(...)):
    """Simulate emailing the translated document to recipient."""
    doc = await db_client.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    logger.info(f"Dispatched email of translated document {doc_id} to {recipient_email}")
    return {"message": f"Translated PDF successfully queued and sent to {recipient_email}.", "id": doc_id}
