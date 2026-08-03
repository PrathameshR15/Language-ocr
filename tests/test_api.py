import unittest
from fastapi.testclient import TestClient
from main import app

class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_get_documents_list(self):
        response = self.client.get("/api/v1/documents")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total", data)
        self.assertIn("documents", data)

    def test_export_excel(self):
        response = self.client.get("/api/v1/export/excel")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_upload_and_rename_document(self):
        # Upload test text file
        file_content = b"Sample text for testing document upload and rename feature."
        response = self.client.post(
            "/api/v1/upload",
            files={"files": ("test_upload_doc.txt", file_content, "text/plain")}
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertGreater(len(data), 0)
        doc_id = data[0]["id"]
        
        # Test PUT rename
        rename_resp = self.client.put(
            f"/api/v1/document/{doc_id}",
            json={"filename": "Renamed_Test_Notice.txt"}
        )
        self.assertEqual(rename_resp.status_code, 200)
        updated_doc = rename_resp.json()
        self.assertEqual(updated_doc["filename"], "Renamed_Test_Notice.txt")

    def test_preview_pdf_endpoint(self):
        # Upload a test document to get a valid doc_id
        file_content = b"Content for testing PDF preview feature in UI."
        response = self.client.post(
            "/api/v1/upload",
            files={"files": ("test_preview_doc.txt", file_content, "text/plain")}
        )
        self.assertEqual(response.status_code, 201)
        doc_id = response.json()[0]["id"]

        # Call PDF preview endpoint
        preview_resp = self.client.get(f"/api/v1/preview/pdf/{doc_id}")
        self.assertEqual(preview_resp.status_code, 200)
        self.assertEqual(preview_resp.headers["content-type"], "application/pdf")
        self.assertIn("inline", preview_resp.headers.get("content-disposition", ""))

    def test_delete_all_documents(self):
        # Upload a test document first
        file_content = b"Content to be deleted via delete_all."
        upload_resp = self.client.post(
            "/api/v1/upload",
            files={"files": ("test_delete_all.txt", file_content, "text/plain")}
        )
        self.assertEqual(upload_resp.status_code, 201)

        # Call DELETE /api/v1/documents
        delete_resp = self.client.delete("/api/v1/documents")
        self.assertEqual(delete_resp.status_code, 200)
        data = delete_resp.json()
        self.assertIn("message", data)

        # Verify documents list is empty
        list_resp = self.client.get("/api/v1/documents")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["total"], 0)

if __name__ == "__main__":
    unittest.main()

