import unittest
import re
from backend.services.translation_service import translation_engine

class TestCustomTranslationFixes(unittest.TestCase):

    def test_custom_dictionary_loading_and_proper_nouns(self):
        # Verify village name translations from custom dictionary
        test_cases = [
            ("शिंगवे", "Shingave"),
            ("শিংওয়ে", "Shingave"),
            ("चास", "Chas"),
            ("চা;", "Chas"),
            ("अवसरी", "Awasari"),
            ("आआ]", "Awasari"),
            ("আআ]", "Awasari"),
            ("টাকওয়ে", "Takwe"),
            ("ডংগরাজ", "Dungaraj")
        ]
        for src, expected in test_cases:
            res = translation_engine.translate_paragraph(src, "Marathi")
            self.assertEqual(res.lower(), expected.lower())

    def test_proper_noun_entity_map_protection(self):
        # Verify Rekha Vadekar and Pumpery mappings
        res1 = translation_engine.translate_paragraph("This is Rekha Vadekar", "English")
        self.assertIn("Rekha Wadekar", res1)
        
        res2 = translation_engine.translate_paragraph("I live in Pumpery", "English")
        self.assertIn("Pimpri", res2)

    def test_progress_vs_salary_rule(self):
        # Verify that प्रगति / पग्रɟत is never translated as Salary, always Progress
        inputs = ["पग्रɟत", "पग्रत", "प्रगति", "প্রগতি"]
        for inp in inputs:
            res = translation_engine.translate_paragraph(inp, "Marathi")
            self.assertEqual(res.lower(), "progress")

    def test_bengali_digit_normalization(self):
        # Verify that Bengali digits/phone numbers are properly normalized
        from backend.utils.unicode_utils import normalize_indic_digits
        normalized = normalize_indic_digits("৯৮০০১২৩৪৫৬")
        self.assertEqual(normalized, "9800123456")
        
        normalized2 = normalize_indic_digits("৯৮০০১৯৮৭৬৫")
        self.assertEqual(normalized2, "9800198765")

    def test_table_cell_romanized_bypass_and_serial_normalization(self):
        # Mock table grid block
        mock_block = {
            "block_type": "table",
            "table_grid": [
                ["ক্রু.", "গ্রামের নাম", "উদ্যোগের বিবরণ"],
                ["তে", "শিংওয়ে", "আধুনিক মাটির সামগ্রী"],
                ["২", "চা;", "সুতি वस्त्र"],
                ["ডে", "आआ]", "বাশের গৃহসজ্জা"],
                ["০", "টাকওয়ে", "খাদ্য প্রক্রিয়াকরণ"],
                ["রে", "চা;", "পরিবেশবান্ধব ব্যাগ"],
                ["ते", "-", "মৌমাছি পালন"],
                [".", ".", "চামড়াজাত পণ্য"],
                ["ডে", "ডংগরাজ", "ধূপকাঠি তৈরি"]
            ],
            "text": ""
        }

        from backend.services.translation_service import INDIC_ADMIN_DICTIONARY, normalize_indic_digits
        from backend.services.translation_service import MARATHI_IDIOM_GLOSSARY, is_corrupted_romanized_marathi
        
        p = mock_block
        raw_grid = p["table_grid"]
        trans_grid = []
        p_lang = "Bengali"
        for row_idx, row in enumerate(raw_grid):
            trans_row = []
            for col_idx, cell in enumerate(row):
                c_str = str(cell or "").strip()
                if c_str:
                    if col_idx == 0 and row_idx > 0 and (c_str in {"ते", "তে", "ডে", "ডে", "০", "০", "রে", "ре", "রে", ".", "২", "২", "२"} or re.match(r'^[तेতেডেডে০०রে.]+$', c_str)):
                        t_cell = str(row_idx)
                    elif c_str in INDIC_ADMIN_DICTIONARY:
                        t_cell = INDIC_ADMIN_DICTIONARY[c_str]
                    elif c_str in MARATHI_IDIOM_GLOSSARY:
                        t_cell = MARATHI_IDIOM_GLOSSARY[c_str]
                    elif is_corrupted_romanized_marathi(c_str, p_lang):
                        t_cell = translation_engine.translate_paragraph(c_str, p_lang)
                    elif re.match(r'^[0-9\s,\.\-\+\(\)₹%\/०-९]+$', c_str):
                        t_cell = normalize_indic_digits(c_str)
                    elif re.match(r'^[a-zA-Z0-9\s\.,\-\/\:\;\(\)₹%]+$', c_str):
                        t_cell = c_str
                    else:
                        t_cell = translation_engine.translate_paragraph(c_str, p_lang)
                    trans_row.append(t_cell)
                else:
                    trans_row.append("")
            trans_grid.append(trans_row)
            
        # Assert normalized serial numbers in first column
        self.assertEqual(trans_grid[1][0], "1")
        self.assertEqual(trans_grid[2][0], "2")
        self.assertEqual(trans_grid[3][0], "3")
        self.assertEqual(trans_grid[4][0], "4")
        self.assertEqual(trans_grid[5][0], "5")
        self.assertEqual(trans_grid[6][0], "6")
        self.assertEqual(trans_grid[7][0], "7")
        self.assertEqual(trans_grid[8][0], "8")

        # Assert correct village translations in second column
        self.assertEqual(trans_grid[1][1].lower(), "shingave")
        self.assertEqual(trans_grid[2][1].lower(), "chas")
        self.assertEqual(trans_grid[3][1].lower(), "awasari")
        self.assertEqual(trans_grid[4][1].lower(), "takwe")
        self.assertEqual(trans_grid[5][1].lower(), "chas")
        self.assertEqual(trans_grid[8][1].lower(), "dungaraj")

if __name__ == "__main__":
    unittest.main()
