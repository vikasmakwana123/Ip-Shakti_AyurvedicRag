# Steps to Create the IP-SAKTI Sahayak Project

## 1. Goal and current knowledge-base status

Build a multilingual, citation-grounded assistant for Ayurveda-related intellectual-property, biodiversity/ABS, and product-regulatory questions. Use Spring AI for retrieval and model orchestration and PostgreSQL with pgvector for embeddings and metadata.

The current knowledge base contains:

| File | Records | Chunks | Scope |
|---|---:|---:|---|
| `corpus/india.json` | 12 | 302 | Indian statutes and regulations |
| `corpus/international.json` | 4 | 16 | International treaties and instruments |
| `corpus/eu_herbal.json` | 71 | 3,079 | Adopted EMA/HMPC herbal monographs and assessment reports |

These are curated corpus files, not a complete legal database. Corpus entries currently require human verification. Three records in `india.json` do not yet have source URLs. The 2024 Biological Diversity Rules PDF is present in `source/`, but its embedded Hindi text was found to be garbled; do not ingest it until OCR or a checked transcription is available.

`fulltext.json` is different from the corpus JSON files. It is a seed-time PDF extraction configuration: entries identify a source PDF and provide section-splitting rules such as `unit`, `start`, `end`, and `passages`. The supplied configuration has seven entries covering six distinct PDFs. It does not itself contain full statutory text and does not, by itself, create vector embeddings. The parser/seed implementation must be included in the application before relying on that pipeline.

## 2. What to put in pgvector

Index **text chunks with provenance**, not PDF binaries, whole JSON files, or application data. Use one vector record per retrievable section or appropriately sized subsection.

### Existing content to prepare

1. Read each `corpus/*.json` file.
2. For every document, create a vector-store record for each `chunks[]` item.
3. Use `verbatim_text` as the primary text. Add the chunk `title`, `section_identifier`, and `retrieval_context` as searchable context where appropriate; avoid embedding a giant serialized JSON object.
4. Preserve source-document fields and chunk-level fields as metadata.
5. Also parse the PDFs configured in `fulltext.json` if the project parser is available. These records provide broader statutory coverage than the selected excerpts in `india.json`. Do not embed `fulltext.json` itself.
6. Treat `eu_herbal.json` as international-regime material with an EU/EMA region tag; “international” is the application-level top-level scope, not a claim that EMA guidance applies worldwide.

If full-text parser output overlaps curated corpus excerpts, retain canonical identifiers and deduplicate overlapping results at retrieval time. The curated corpus can carry useful retrieval labels and topic-specific excerpts; parsed full text can supply the surrounding statutory provisions. Do not silently combine different editions of the same law.

### Recommended metadata per vector record

At minimum, store:

- `jurisdiction`: `india` or `international`
- `region`: for example `india`, `eu`, `global`, or a treaty-party scope when known
- `regime`: for example `india_statute`, `india_regulation`, `treaty`, `ema_hmpc`
- `authority`, `document_type`, and `category`
- `document_id`, `source_file`, `source_url`, `version_tag`, and `retrieved_date`
- `section_identifier`, `chunk_id`, and page number/range when available
- `language` and, if translated, `source_language` and `translation_status`
- `verification_status`, such as `pending_human_check` or `verified`
- `effective_from` / `effective_to` where the dates are known and verified
- Any relevant `status`, such as adopted, draft, or superseded

Keep the original source text and citation fields in the record. Embeddings are for finding evidence; they are not a replacement for the source text used to quote and cite an answer.

## 3. India versus international retrieval

**Do not ask the LLM to separate jurisdictions after retrieving a mixed result set.** It may blend an Indian rule with a treaty or EMA guidance. Apply a server-side metadata filter to vector retrieval before the documents reach the model.

For an MVP, a single PostgreSQL database and one pgvector-backed store/table are sufficient. Keep the scopes separate through required metadata and retrieval filters:

- India-only request: retrieve with `jurisdiction = 'india'`.
- International request: retrieve with `jurisdiction = 'international'`; when the user has selected an export market or topic, further filter by `region`, `regime`, or document type.
- Cross-jurisdiction comparison: make separate India and international retrieval calls, then return visibly separate evidence and answer sections. Do not use one unfiltered search.

Use separate databases only if you later need hard operational isolation, different access controls, or independent deployments. A separate database is not necessary just to preserve jurisdictional clarity. A separate schema/table or collection is also optional; metadata filters are the important control.

Make scope selection explicit in the API, not an optional prompt hint. Validate allowed values on the server. If no scope is selected, either ask the user to select one or return clearly separated scopes—never silently default to a blended answer. For international requests, ask for a country/market where local rules matter; a treaty, EU guidance, and another country's domestic law are not interchangeable.

## 4. Ingestion and Spring AI implementation steps

1. **Keep the inputs version-controlled.** Store the corpus JSON, `fulltext.json`, source PDFs, and extraction/conversion scripts with a manifest of source, checksum, retrieval date, and edition.
2. **Validate before ingesting.** Reject missing text, unsupported jurisdiction values, duplicate document/version/section IDs, overlong fields, and source records without a traceable source. Keep malformed records in a review report rather than silently dropping them.
3. **Extract text.** Use the project statute parser for configured PDFs. Use OCR for image-only or broken-text PDFs, and visually spot-check OCR output. Keep the original PDF and extraction provenance.
4. **Normalize without changing legal meaning.** Remove only proven layout noise. Keep section headings, numbering, provisos, schedules, footnotes when legally material, and amendment/version notes. Mark uncertain or partial extraction.
5. **Chunk by legal structure.** Prefer one section, rule, article, or coherent monograph subsection per chunk. Split oversized sections at paragraph boundaries and include the parent section heading in each child chunk. Avoid chunks so small that they lose the governing section or so large that retrieval returns unrelated provisions.
6. **Create embeddings.** Use Spring AI's embedding abstraction and pgvector store integration. Choose and test a multilingual embedding model against English, Hindi, and other supported-language queries. Pin the model/version used for an index and re-embed when changing it.
7. **Upsert by stable identity.** Use a deterministic key based on document, edition/version, section, and chunk. Re-ingestion should update a changed edition without duplicating all prior chunks. Keep old versions inactive or explicitly superseded rather than mixing them with current law.
8. **Retrieve with metadata filters.** Apply jurisdiction, region, regime, language, and verification filters as part of vector search. Consider hybrid lexical + vector retrieval for section numbers, Act names, and exact legal terms.
9. **Rerank and deduplicate.** Rerank only the already scope-filtered candidate set. Collapse repeated chunks from the same document/section/version and prefer the most authoritative, applicable, current source.
10. **Generate with evidence only.** Require citations for material legal/regulatory claims. Give the model source title, provision, source URL, edition/effective date, and exact retrieved text. If evidence is insufficient or conflicting, say so and ask a clarifying question or abstain.
11. **Return structured citations.** Return the answer, scope, citations (document, provision, URL, edition and page if available), confidence/evidence status, and a legal-information disclaimer separately from generated prose.
12. **Evaluate before demo.** Test citation correctness, jurisdiction leakage, stale/superseded law, abstention, multilingual retrieval, and duplicate/contradictory sources.

Operational question logs, user profiles, and confidential formulation details do not belong in the legal vector store. Store only what the product requires, protect it with access control, and set retention/deletion rules.

## 5. Frontend questions — separate intake topic

Keep the intake short and conditional. Ask only follow-up questions needed for the selected task. Let users skip a question and explain when the missing detail limits the answer.

### A. Scope and language

1. **Which legal scope should this answer cover?** India / International / Compare India with another regime.
2. If international: **Which country or export market?** EU / United States / United Kingdom / Other / Not sure.
3. **Which language should we use?**
4. For a comparison: **Should we compare the same issue across India and the selected market?** Yes / No.

### B. User's task

5. **What are you trying to do?** Classify a product / Check patentability or another IP right / Check biodiversity access and benefit-sharing / Check licensing or marketing requirements / Check a label or advertisement / Find a form, registry, or official source / Other.
6. **What is your question in your own words?**

### C. Formulation classification (show only if relevant)

7. **What is the product intended to be used for?** Traditional medicinal use / Other therapeutic use / Food or supplement / Cosmetic / Research only / Not sure.
8. **What ingredients or biological resources does it contain?** Allow “not sure”; optionally ask plant/common name and botanical name.
9. **Is the formula and method taken from a named authoritative Ayurvedic text or the applicable First Schedule?** Yes / No / Not sure. If yes, ask for the text and reference if known.
10. **Is it a new combination, changed dose/form, extract, purified fraction, or standardized product?** Ask which one, if known.
11. **How will it be administered or used?** Oral / External / Other / Not sure.
12. **What claims will appear on the product or its advertising?** Optional free text; make clear users should not submit private medical information.

Do not make the user decide the legal classification. Use answers to explain likely categories, show uncertainty, and request a human review when the classification is consequential.

### D. IP and ABS checks (show only if relevant)

13. **Which protection or issue are you considering?** Patent / Trademark / GI / Design / Copyright / Plant variety / Trade secret / Not sure.
14. For a possible invention: **Has it been publicly disclosed, sold, demonstrated, or filed before?** Yes / No / Not sure; ask for dates only if needed.
15. **Where was the biological resource accessed or collected, and where will it be used?**
16. **Was associated traditional knowledge used?** Yes / No / Not sure. If yes, ask whether it is codified or community-held, without requiring the user to disclose confidential knowledge.
17. **Who will access/use the resource?** Individual / Indian entity / Foreign entity or non-resident / Research institution / Not sure.
18. **Is this for research, commercial utilization, an IP filing, or commercialization of an existing right?**

Do not collect sensitive community knowledge or confidential invention details unless essential and the user has been told how that data is protected.

### E. Regulatory or market-access checks (show only if relevant)

19. **Where will the product be manufactured and sold?**
20. **Is it already licensed, registered, or notified?** Ask the jurisdiction and category if known.
21. **What is the current stage?** Idea / Research / Trial / Manufacturing / Already marketed.
22. **What specific decision or deadline are you working toward?**

## 6. What should be added before production

### Corpus and provenance

- Add authoritative current sources and stable source URLs for the three Indian corpus documents that currently lack URLs.
- Register and extract the Biological Diversity Act, 2023 amendment, and 2024 Rules in the seed-time full-text pipeline. Fix or OCR the Hindi PDF and verify it against page images.
- Confirm which supplied statutory PDFs are current, consolidated, and complete. Record “as on” dates; do not treat an enactment PDF as current consolidated law.
- Add the missing regimes named in the problem statement as applicable: current Patents Rules and amendments, PCT, Madrid and Hague systems, Budapest Treaty, market-specific herbal-product rules, and reliable official registry guidance/records.
- Add source-level and chunk-level language, edition, effective dates, jurisdiction/region, document status, page references, and verification state.
- Have a qualified reviewer spot-check every high-impact extraction and maintain a verification sheet. Never promote `pending_human_check` material to verified automatically.
- Keep original-language text and reviewed translations linked. Do not present machine translation as an authoritative translation.

### Product and safety

- Build a source/corpus update workflow: detect changes, review them, version them, re-index them, and retain an audit trail.
- Add access controls, secret management, input/output logging with privacy protections, retention/deletion controls, and protections against prompt injection in retrieved documents.
- Add a standing “information, not legal advice” notice, safe abstention, human IP facilitator escalation, and an official-source path for every answer.
- Add evaluation sets for legal accuracy, citation-to-claim correctness, jurisdiction separation, stale-law handling, refusal/abstention, and each supported language.
- Add monitoring for embedding/retrieval failures, missing citations, source freshness, and user feedback. Keep LLM output from changing corpus records.

## 7. Suggested build order

1. Finish source inventory, provenance, and corpus verification.
2. Implement PostgreSQL/pgvector schema, migrations, Spring AI embedding, and repeatable ingestion.
3. Implement the mandatory scope filter and citation-bearing retrieval API.
4. Build the frontend scope selector and conditional intake questions above.
5. Add grounded answers, uncertainty/abstention, disclaimer, and human escalation.
6. Run jurisdiction, citation, and multilingual evaluations before a demo.
7. Add ABS workflow, formulation classifier, knowledge graph, voice/Bhashini, and permitted paid-source connectors as later phases.

