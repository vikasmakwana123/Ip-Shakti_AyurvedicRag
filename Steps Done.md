# Steps Done

Updated: 2026-11-12

This log records work performed in the current `Ip-Shakti` workspace and the status of the reference project files supplied in the chat.

## What `fulltext.json` is

The supplied project archive contains `knowledge-base/fulltext.json`. Its `about` field says it is used by `ai-service/app/core/statute_parser.py` at seed time to parse official PDFs from `knowledge-base/source/`. It is an extraction configuration, not the extracted statutory text: it maps PDF filenames to titles and extraction rules such as `unit`, `start`, optional `end`, `last_number`, and `passages`. The parser reads the configured PDFs and creates full-text sections/rules/regulations during database seeding.

The file has seven parser entries covering six distinct PDFs: the Patents Act, Trade Marks Act, GI Act, Drugs and Magic Remedies Act, Drugs and Cosmetics Act, Drugs and Cosmetics Rules (also read from the Drugs and Cosmetics PDF), and FSSAI Ayurveda Aahara Regulations. It does not configure the Biological Diversity Act, its 2023 amendment, or the 2024 Rules.

The parser source `statute_parser.py` and seed command were not present in the supplied extracted files or current workspace, so the exact parser implementation could not be independently checked or run. The current [Ayushakti knowledge-base](./Ayushakti/knowledge-base/) has source PDFs and corpus files, but no `fulltext.json` or application/parser code. The reference `fulltext.json` has not been copied into it.

## Completed work

- [x] Inspected the Indian PDF source folder; it contains 13 PDFs.
- [x] Ran the EMA monograph section check: 20 records have fewer than 14 sections (13 fallback and 7 numbered). The numbered records need review; this was not treated as an extraction pass.
- [x] Reviewed EMA kind/status counts and selected adopted, non-superseded monographs and reports for conversion.
- [x] Created [india.json](./Ayushakti/knowledge-base/corpus/india.json) from the supplied project corpus reference. It preserves the 9 reference documents and adds 3 section-extracted documents: Copyright Act (104 chunks), Designs Act (48), and Protection of Plant Varieties and Farmers' Rights Act (96). The added documents are `pending_human_check`.
- [x] Created [eu_herbal.json](./Ayushakti/knowledge-base/corpus/eu_herbal.json): 71 adopted, non-superseded monograph/report documents and 3,079 chunks. The text and source URLs were checked against `eu_chunks.jsonl`; jurisdiction is `international`. All documents remain `pending_human_check`.
- [x] Added converters: [convert_indian_pdfs_to_corpus.py](./Data_extraction/scripts/convert_indian_pdfs_to_corpus.py) and [convert_eu_to_corpus.py](./Data_extraction/scripts/convert_eu_to_corpus.py).
- [x] Inspected the supplied `fulltext.json` configuration and identified which PDFs it currently registers.
- [x] Updated [NextSteps.md](./NextSteps.md) with results and outstanding work.

## Not completed

- [ ] Biological Diversity Act/Amendment/Rules entries have not been added to the seed-time `fulltext.json`; the parser implementation is not in the current workspace, so the regex behavior cannot yet be tested.
- [ ] Biological Diversity Rules, 2024 has not been added to the corpus. `pdftotext` returned visibly corrupted Hindi/Devanagari text; OCR or checked transcription is needed first.
- [ ] The full project has not been seeded or started, and no application-level questions have been tested.
- [ ] Human spot-checking of extracted Indian and EMA sections against source PDFs remains outstanding.
- [ ] The project `.gitignore` and script-copy cleanup have not been verified or changed.

## Validation performed

- Parsed the generated corpus JSON files and checked required document/chunk fields, unique source files/titles, jurisdictions, source URLs, and section-identifier length.
- Verified that all 3,079 EU output chunk texts and source URLs match their selected input JSONL records.
- Re-ran the Indian converter to confirm it skips already-present documents instead of duplicating them.
- Checked Python syntax for both converter scripts.

