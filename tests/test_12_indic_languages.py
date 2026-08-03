import os
import sys
import time
import tracemalloc
import unittest
import asyncio

sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding='utf-8')

# Load .env
with open('.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

from backend.services.language_detection_service import LanguageDetectionService
from backend.services.translation_service import translation_engine
from backend.services.metadata_service import metadata_service
from backend.services.pdf_generation_service import pdf_generator
from backend.services.document_parser_service import document_parser

# Test Samples across 12 Indic Languages
INDIC_TEST_SAMPLES = {
    "Hindi": "उत्तर प्रदेश सरकार राजस्व विभाग अधिसूचना संख्या REV-2026/894. रहिवासी पुरावा तथा जन्मतारीख दर्शविणारा पुरावा जमा करें।",
    "Marathi": "महाराष्ट्र शासन महसूल विभाग परिपत्रक क्रमांक 1021. रहिवासी पुरावा आणि जन्मतारीख दर्शविणारा पुरावा सोबत जोडणे आवश्यक आहे. जिल्हा निवडणूक अधिकारी.",
    "Gujarati": "ગુજરાત સરકાર મહેસૂલ વિભાગ પરિપત્ર. રહેઠાણનો પુરાવો અને જન્મ તારીખનો પુરાવો રજૂ કરવો.",
    "Tamil": "தமிழ்நாடு அரசு வருவாய்த்துறை அறிவிப்பு. முகவரி சான்று மற்றும் பிறப்பு சான்றிதழ் சமர்ப்பிக்கவும்.",
    "Telugu": "తెలంగాణ ప్రభుత్వం రెవెన్యూ శాఖ నోటీసు. నివాస నిరూపణ మరియు పుట్టిన తేదీ నిరూపణ సమర్పించాలి.",
    "Kannada": "ಕರ್ನಾಟಕ ಸರ್ಕಾರ ಕಂದಾಯ ಇಲಾಖೆ ಸೂಚನೆ. ವಾಸಸ್ಥಳದ ಪುರಾವೆ ಸಲ್ಲಿಸುವುದು.",
    "Malayalam": "കേരള സർക്കാർ റവന്യൂ വകുപ്പ് വിജ്ഞാപനം. താമസ രേഖ ഹാജരാക്കുക.",
    "Punjabi": "ਪੰਜਾਬ ਸਰਕਾਰ ਮਾਲ ਵਿਭਾਗ ਨੋਟਿਸ. ਰਿਹਾਇਸ਼ੀ ਸਬੂਤ ਜਮ੍ਹਾਂ ਕਰੋ।",
    "Bengali": "পশ্চিমবঙ্গ সরকার রাজস্ব বিভাগ বিজ্ঞপ্তি. স্থায়ী বাসস্থানের প্রমাণপত্র জমা দিন।",
    "Urdu": "حکومت اتر پردیش محکمہ مال نوٹس۔ رہائش کا ثبوت پیش کریں۔",
    "Odia": "ଓଡ଼ିଶା ସରକାର ରାଜସ୍ୱ ବିଭାଗ ବିଜ୍ଞପ୍ତି। ବାସସ୍ଥାନର ପ୍ରମାଣପତ୍ର।",
    "Assamese": "অসম চৰকাৰ ৰাজহ বিভাগ জাননী. বাসস্থানৰ প্ৰমাণপত্ৰ।"
}

class Test12IndicLanguages(unittest.TestCase):

    def test_translation_exact_terms(self):
        """Test specific government term corrections requested by user."""
        term_checks = [
            ("रहिवासी पुरावा", "Proof of Residence"),
            ("जन्मतारीख दर्शविणारा पुरावा", "Proof of Date of Birth"),
            ("पासपोर्ट आकाराचा फोटो", "Passport-size Photograph"),
            ("जिल्हा निवडणूक अधिकारी", "District Election Officer"),
            ("मुख्य निवडणूक अधिकारी", "Chief Electoral Officer"),
            ("मतदार नोंदणी", "Voter Registration"),
            ("मतदार यादी", "Electoral Roll"),
            ("अर्ज", "Application"),
            ("शासकीय", "Government"),
            ("सार्वजनिक सूचना", "Public Notice"),
            ("अधिकृत संकेतस्थळ", "Official Website")
        ]
        print("\n--- Verifying Exact Government Term Translations ---")
        for orig_term, expected_eng in term_checks:
            trans = translation_engine.translate_paragraph(orig_term, "Marathi")
            print(f"'{orig_term}' -> '{trans}'")
            self.assertEqual(trans, expected_eng)

    def test_12_indic_languages_pipeline(self):
        """Pipeline execution, language detection, translation, and performance benchmarks across 12 languages."""
        print("\n--- Running Automated Pipeline Tests Across 12 Indic Languages ---")
        tracemalloc.start()
        
        for lang_name, text in INDIC_TEST_SAMPLES.items():
            start_time = time.time()
            
            # Step 1: Language Detection
            t_det_start = time.time()
            detected_lang = LanguageDetectionService.detect_language(text)
            t_det_time = round((time.time() - t_det_start) * 1000, 2)
            
            # Step 2: Translation
            t_trans_start = time.time()
            translated = translation_engine.translate_paragraph(text, detected_lang)
            t_trans_time = round((time.time() - t_trans_start) * 1000, 2)
            
            # Step 3: PDF Generation
            t_pdf_start = time.time()
            tmp_pdf = f"tests/temp_{lang_name}.pdf"
            pdf_generator.generate_translated_pdf(
                doc_id=f"test_{lang_name.lower()}",
                filename=f"test_{lang_name.lower()}.txt",
                paragraphs=[{"text": text, "translated_text": translated}],
                metadata={"state": lang_name, "doc_number": "REV-2026/894"},
                output_path=tmp_pdf
            )
            t_pdf_time = round((time.time() - t_pdf_start) * 1000, 2)
            
            total_time = round((time.time() - start_time) * 1000, 2)
            
            # Clean up temp file
            if os.path.exists(tmp_pdf):
                os.remove(tmp_pdf)

            print(f"[{lang_name:10s}] Detected: {detected_lang:10s} | Det: {t_det_time}ms | Trans: {t_trans_time}ms | PDF: {t_pdf_time}ms | Total: {total_time}ms")
            print(f"  Orig:  {text[:60]}...")
            print(f"  Trans: {translated[:60]}...\n")
            
            self.assertIsNotNone(translated)
            self.assertTrue(len(translated) > 0)

        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(f"Peak RAM Memory Usage during 12-Language Test: {round(peak_mem / (1024 * 1024), 2)} MB")

if __name__ == "__main__":
    unittest.main()
