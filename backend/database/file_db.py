import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import settings
from backend.utils.logger import logger

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_FILE = os.path.join(DATA_DIR, "documents_db.json")

os.makedirs(DATA_DIR, exist_ok=True)

class FileDatabase:
    """Thread-safe, file-backed JSON database for storing document records and extracted text."""
    
    def __init__(self, db_filepath: str = DB_FILE):
        self.db_filepath = db_filepath
        self._async_lock = None
        self._ensure_db_file()

    @property
    def _lock(self):
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock


    def _ensure_db_file(self):
        if not os.path.exists(self.db_filepath):
            initial_data = {"documents": [], "extracted_texts": []}
            with open(self.db_filepath, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2, ensure_ascii=False)

    def _read_data_sync(self) -> Dict[str, Any]:
        try:
            with open(self.db_filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading DB file: {e}")
            return {"documents": [], "extracted_texts": []}

    def _write_data_sync(self, data: Dict[str, Any]):
        try:
            with open(self.db_filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error writing to DB file: {e}")

    async def get_all_documents(self) -> List[Dict[str, Any]]:
        async with self._lock:
            data = self._read_data_sync()
            return data.get("documents", [])

    async def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            data = self._read_data_sync()
            for doc in data.get("documents", []):
                if str(doc.get("id")) == str(doc_id):
                    return doc
            return None

    async def save_document(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            data = self._read_data_sync()
            docs = data.get("documents", [])
            
            # Check if updating or inserting
            doc_id = str(doc_data.get("id"))
            existing_idx = None
            for idx, d in enumerate(docs):
                if str(d.get("id")) == doc_id:
                    existing_idx = idx
                    break
            
            if existing_idx is not None:
                docs[existing_idx] = doc_data
            else:
                docs.append(doc_data)
                
            data["documents"] = docs
            self._write_data_sync(data)
            return doc_data

    async def update_document(self, doc_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with self._lock:
            data = self._read_data_sync()
            docs = data.get("documents", [])
            updated_doc = None
            for idx, d in enumerate(docs):
                if str(d.get("id")) == str(doc_id):
                    docs[idx].update(updates)
                    updated_doc = docs[idx]
                    break
            if updated_doc:
                data["documents"] = docs
                self._write_data_sync(data)
            return updated_doc


    async def save_extracted_texts(self, doc_id: str, paragraphs: List[Dict[str, Any]]):
        async with self._lock:
            data = self._read_data_sync()
            all_texts = data.get("extracted_texts", [])
            # Remove old entries for this doc_id if any
            all_texts = [t for t in all_texts if str(t.get("document_id")) != str(doc_id)]
            
            for idx, p in enumerate(paragraphs, start=1):
                all_texts.append({
                    "id": f"{doc_id}_p{idx}",
                    "document_id": str(doc_id),
                    "paragraph": p.get("paragraph", idx),
                    "page": p.get("page", 1),
                    "language": p.get("language", "Unknown"),
                    "text": p.get("text", ""),
                    "translated_text": p.get("translated_text", ""),
                    "confidence": p.get("confidence", 0.9)
                })
                
            data["extracted_texts"] = all_texts
            self._write_data_sync(data)

    async def get_extracted_texts_by_doc_id(self, doc_id: str) -> List[Dict[str, Any]]:
        async with self._lock:
            data = self._read_data_sync()
            return [t for t in data.get("extracted_texts", []) if str(t.get("document_id")) == str(doc_id)]

    async def delete_document(self, doc_id: str) -> bool:
        async with self._lock:
            data = self._read_data_sync()
            docs = data.get("documents", [])
            initial_count = len(docs)
            docs = [d for d in docs if str(d.get("id")) != str(doc_id)]
            
            if len(docs) == initial_count:
                return False
                
            data["documents"] = docs
            data["extracted_texts"] = [t for t in data.get("extracted_texts", []) if str(t.get("document_id")) != str(doc_id)]
            self._write_data_sync(data)
            return True

    async def delete_all_documents(self) -> int:
        async with self._lock:
            data = self._read_data_sync()
            docs = data.get("documents", [])
            count = len(docs)
            data["documents"] = []
            data["extracted_texts"] = []
            self._write_data_sync(data)
            return count

    async def search_documents(self, query: str = "", language: str = "", state: str = "", department: str = "") -> List[Dict[str, Any]]:
        async with self._lock:
            data = self._read_data_sync()
            docs = data.get("documents", [])
            all_texts = data.get("extracted_texts", [])
            
            # Map doc_id to combined text
            doc_texts_map = {}
            for t in all_texts:
                d_id = str(t.get("document_id"))
                combined = f"{t.get('text', '')} {t.get('translated_text', '')}"
                doc_texts_map[d_id] = doc_texts_map.get(d_id, "") + " " + combined

            results = []
            q_lower = query.lower().strip()
            lang_lower = language.lower().strip()
            state_lower = state.lower().strip()
            dept_lower = department.lower().strip()

            for doc in docs:
                d_id = str(doc.get("id"))
                meta = doc.get("metadata_json") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}

                # Language filter
                if lang_lower and lang_lower != "all":
                    if doc.get("language", "").lower() != lang_lower:
                        continue

                # State filter
                if state_lower and state_lower != "all":
                    doc_state = str(meta.get("state", "")).lower()
                    if state_lower not in doc_state:
                        continue

                # Department filter
                if dept_lower and dept_lower != "all":
                    doc_dept = str(meta.get("department", "")).lower()
                    if dept_lower not in doc_dept:
                        continue

                # Text search query (Searches across filename, metadata, original text, and translated text)
                if q_lower:
                    full_content = (
                        f"{doc.get('filename', '')} "
                        f"{doc.get('language', '')} "
                        f"{json.dumps(meta)} "
                        f"{doc_texts_map.get(d_id, '')}"
                    ).lower()
                    
                    if q_lower not in full_content:
                        continue

                results.append(doc)
            return results

db_client = FileDatabase()
