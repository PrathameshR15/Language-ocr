import pytest
import asyncio
from backend.database.file_db import db_client

@pytest.mark.asyncio
async def test_documents_returned_newest_first():
    """Verify that newly created/saved documents appear at index 0 (top of list)."""
    doc1 = await db_client.save_document({
        "id": "test_order_1",
        "filename": "old_doc.pdf",
        "created_at": "2026-08-04T10:00:00Z"
    })
    
    doc2 = await db_client.save_document({
        "id": "test_order_2",
        "filename": "new_doc.pdf",
        "created_at": "2026-08-04T12:00:00Z"
    })

    docs = await db_client.get_all_documents()
    assert len(docs) >= 2
    assert docs[0]["id"] == "test_order_2" or docs[0]["filename"] == "new_doc.pdf"

    # Cleanup
    await db_client.delete_document("test_order_1")
    await db_client.delete_document("test_order_2")
