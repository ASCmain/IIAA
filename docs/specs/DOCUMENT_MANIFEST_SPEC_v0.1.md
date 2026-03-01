DOCUMENT_MANIFEST_SPEC v0.1 (IIAA – HTML-first legal/IFRS corpus)

Scope
This spec defines two JSONL artifacts:
1) Document manifest (document-level metadata, versioning, legal precedence, file/URL provenance).
2) Chunk records (chunk-level metadata for retrieval and citation), linked to the manifest via document_id.

Design principles
- Keep chunk records lean: repeat only what is needed for retrieval, routing, and citation.
- Store rich provenance/versioning once per document in the manifest.
- Support bilingual pairing (IT/EN) via doc_family_id.
- Support “latest wins” retrieval via precedence_rank + version_priority_date + scenario_tag.
- Maintain PDF references for traceability; when the corpus is sourced from HTML, PDF-specific fields remain null.
- Locator strategy is semantic-first: standard_id → section_path → paragraph_key (no DOM offsets).

Artifact A — Document manifest (JSONL)
One record per logical document (e.g., consolidated CELEX IT, consolidated CELEX EN, OJ IT, OJ EN, EFRAG report, etc.)

Required fields (minimum)
- document_id: string (unique, stable)
- doc_family_id: string (pairs translations/variants)
- source_system: enum ["eur-lex","efrag","iasb","big4","other"]
- doc_type: enum ["celex_consolidated","celex_base","oj","efrag_endorsement_report","other"]
- jurisdiction: enum ["EU","other"]
- normative_level: enum ["EU_regulation","EU_oj","endorsement_status","other"]
- language: enum ["IT","EN","--"]
- is_consolidated: boolean
- precedence_rank: integer (higher = more authoritative for retrieval)
- version_priority_date: date (YYYY-MM-DD) (used for “latest wins” ordering)
- scenario_tag: enum ["current_law","pre_endorsement","historical_cutoff"]

Normative identifiers (recommended)
- celex_id: string|null (e.g., "02023R1803-20250730", "32023R1803")
- oj_id: string|null (e.g., "OJ:L_202600338" or "L_202600338")
- oj_issue: string|null (e.g., "L 237")
- oj_publication_date: date|null
- oj_page_start: integer|null
- act_date: date|null
- consolidation_date: date|null
- edition_label: string|null (e.g., "005.002" if used)
- status: enum ["in_force","not_yet_effective","superseded","repealed","unknown"]

Provenance (required “two fields” for HTML and PDF)
- source_url_html: string|null
- source_url_pdf: string|null
- file_name_html: string|null
- file_name_pdf: string|null
- file_path_html: string|null
- file_path_pdf: string|null
- file_sha256_html: string|null
- file_sha256_pdf: string|null

Audit
- ingested_at_utc: datetime (ISO 8601 UTC)
- ingest_tool_version: string|null
- notes: string|null

Artifact B — Chunk records (JSONL)
One record per chunk (for now: 1 paragraph = 1 chunk).

Required fields (minimum)
- chunk_id: string (unique, stable; deterministic recommended)
- document_id: string (FK to manifest)
- language: enum ["IT","EN","--"]
- text: string
- text_len: integer
- standard_id: string|null (e.g., "IAS 36", "IFRS 9", "IFRIC 23", "SIC 12")
- section_path: array[string] (semantic headings path; may be empty)
- paragraph_key: string|null (e.g., "40", "39AK", "B5", "B5-B6")
- chunk_seq: integer (sequence within standard_id; 1-based recommended)
- cite_key: string (semantic citation label, e.g., "IAS 36 §141", "IFRS 1 §40")

Recommended flags
- is_deleted: boolean
- is_withdrawal_section: boolean
- markers: array[string]

Optional PDF traceability placeholders (null for HTML-first)
- pdf_page_start: integer|null
- pdf_page_end: integer|null

Retrieval ordering (“latest wins”)
- Rank candidate documents by:
  1) scenario_tag (match user scenario; default "current_law")
  2) precedence_rank (descending)
  3) version_priority_date (descending)
  4) language preference (query language)

Folder placement (recommended)
- data/manifests/document_manifest.jsonl
- data/manifests/_schemas/document_manifest.schema.json
- data/manifests/_schemas/chunk_record.schema.json
- data/manifests/samples/*.jsonl

Versioning
- Append-only updates for manifest records (new versions = new document_id; keep doc_family_id constant).
- Tag releases (semver) when changing schema: v0.1.0, v0.1.1, etc.
