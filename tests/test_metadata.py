import unittest
from backend.services.metadata_service import metadata_service

class TestMetadataService(unittest.TestCase):
    def test_metadata_extraction(self):
        sample_text = """
        GOVERNMENT OF MAHARASHTRA
        Revenue Department, District Pune
        Outward No: REV-2026/894
        Date: 15/08/2026
        Subject: Land Record Circular for Taluka Haveli
        PIN Code: 411001 Phone: 9876543210 Email: revenue@maharashtra.gov.in
        """
        
        meta = metadata_service.extract_metadata(sample_text, "sample.pdf")
        self.assertEqual(meta["state"], "Maharashtra")
        self.assertEqual(meta["pin_code"], "411001")
        self.assertEqual(meta["doc_number"], "REV-2026/894")
        self.assertEqual(meta["date"], "15/08/2026")
        self.assertEqual(meta["email"], "revenue@maharashtra.gov.in")

if __name__ == "__main__":
    unittest.main()
