# Catalog schema (APA-ready) — IIAA

Ogni record documento nel catalogo deve includere almeno:

Campi bibliografici (APA-ready):
- doc_id (string, stabile)
- standard (IAS/IFRS/...)
- title (string)
- authors (array di stringhe; es. ente autore)
- publisher (string)
- publication_date (string: "YYYY" oppure "YYYY-MM-DD" se noto)
- source_url (string, opzionale)
- accessed_at (string ISO 8601 con timezone Europe/Rome)

Campi tecnici (riproducibilità):
- language (string: "en"/"it")
- local_path (string: path relativo sotto corpus/original/)
- checksum_sha256 (string)
- notes (string, opzionale)
