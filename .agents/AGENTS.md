# Workspace Customization Rules for Multilingual OCR & Translation System

## Strict Translation & Quality Directives

1. **Indic Administrative Progress vs Salary Rule**:
   - **NEVER** map `प्रगति` / `प्रगती` or font-corrupted OCR variations like `पग्रɟत` / `पग्रत` to `Salary`.
   - **ALWAYS** reconstruct `पग्रɟत` / `पग्रत` $\rightarrow$ `प्रगति` / `प्रगती` and translate to **`Progress`**.

2. **Custom PDF Font CMAP Artifact Repair Rule**:
   - Always strip IPA noise glyphs (`ɟ`, `ɞ`, `ɝ`, `ɷ`, `ɢ`, `ɜ`, `ɣ`, `ɫ`) and embedded ASCII font digits (`न9न` $\rightarrow$ `नवीन`, `अध्3ापन` $\rightarrow$ `अध्यापन`, `प्रशि4क्षण` $\rightarrow$ `प्रशिक्षण`).
   - Always restore shifted matras and split halants (`जिलह्` $\rightarrow$ `जिल्हा`, `इमरिित` $\rightarrow$ `इमारत`, `उत्तरिाभिमुख` $\rightarrow$ `उत्तराभिमुख`, `पशम्चि` $\rightarrow$ `पश्चिम`, `बाजिूची` $\rightarrow$ `बाजूची`, `पूणर्या` $\rightarrow$ `पूर्ण`).

3. **Romanized Hinglish Table Cell Rule**:
   - **NEVER** bypass Romanized Indic phrases in table cells (e.g. `(Pine Ke Pani Ki Nai Pipeline)`).
   - Always evaluate table cells against custom dictionaries and `recover_corrupted_romanized_marathi` prior to checking English regex.

4. **Cache & Upload Freshness Rule**:
   - Always clear `TranslationService._cache` upon new file uploads so new glossary/dictionary rules immediately update in memory.

5. **Proper Noun Protection Rule**:
   - Maintain proper noun and place name mappings in `PROPER_NOUN_ENTITY_MAP` and `custom_dictionary.json` (`Rekha Vadekar` $\rightarrow$ `Rekha Wadekar`, `Pumpery` $\rightarrow$ `Pimpri`).
