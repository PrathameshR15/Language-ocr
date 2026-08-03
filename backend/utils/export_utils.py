import io
import json
import pandas as pd
from typing import List, Dict, Any

def export_metadata_to_excel(documents: List[Dict[str, Any]]) -> bytes:
    """Exports list of document records & metadata to an Excel binary buffer."""
    records = []
    for doc in documents:
        meta = doc.get("metadata_json") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
                
        row = {
            "ID": doc.get("id"),
            "Filename": doc.get("filename"),
            "Detected Language": doc.get("language"),
            "Translated Language": doc.get("translated_language"),
            "Status": doc.get("status"),
            "Confidence Score": doc.get("confidence"),
            "Upload Time": doc.get("upload_time"),
            "Processing Time (s)": doc.get("processing_time"),
            "State": meta.get("state", "N/A"),
            "District": meta.get("district", "N/A"),
            "Department": meta.get("department", "N/A"),
            "Document Number": meta.get("doc_number", "N/A"),
            "Issue Date": meta.get("issue_date", "N/A"),
            "Subject": meta.get("subject", "N/A"),
            "Authority Name": meta.get("authority_name", "N/A"),
            "Taluka": meta.get("taluka", "N/A"),
            "PIN Code": meta.get("pin_code", "N/A")
        }
        records.append(row)
        
    df = pd.DataFrame(records)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Gov Documents')
    output.seek(0)
    return output.getvalue()
