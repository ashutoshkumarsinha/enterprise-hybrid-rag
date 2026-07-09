# Parsers (hybrid-rag-ingest)

**Parent:** [SPEC.md](../SPEC.md) · Platform §5.1 · **[Docling](./DOCLING.md)**

---

## 1. Parser profiles (normative)

| Profile | Libraries | When |
|---------|-----------|------|
| `fast` (default) | PyMuPDF, python-docx, trafilatura, markdown-it-py | Bulk ingest, digital PDFs, NFR-04 throughput |
| `docling` | **[Docling](https://github.com/docling-project/docling)** | Complex PDF, tables, slides, multi-column, DOCX/PPTX |
| `auto` | Router heuristic | Low text yield or manifest `parser: docling` → Docling; else fast |

Config: `[parsers]` in `ingest.toml` — see [DOCLING.md](./DOCLING.md).

---

## 2. Supported formats (v1)

| Format | Default | Strategy |
|--------|---------|----------|
| PDF | PyMuPDF | Page + layout blocks; OCR hook for scans |
| PDF (complex) | Docling | Tables, reading order, multi-column |
| DOCX | python-docx | Heading styles + tables |
| DOCX / PPTX | Docling | Layout-aware when profile/manifest requests |
| HTML | trafilatura | DOM headings; BeautifulSoup fallback |
| Markdown | markdown-it-py | ATX / setext headings |
| Plain text | stdlib | Paragraph / sliding window |
| RTF, JSON, YAML, XML, CSV | stdlib (+ pandas) | Path / schema / row chunking |
| Images | vision LLM | VLM caption → text chunk; binary in MinIO |

---

## 3. Vision (deferred)

When `defer_vlm = true` (default), image captioning runs in Celery workers via `vllm_vision_url` — not in the parse pool.

---

## 4. Cross-reference mining

Collection manifest may define `reference_patterns` (regex → `document_id`). Mined refs populate chunk `references[]` and Neo4j `REFERENCES` edges.

---

## 5. Output contract

Each chunk MUST conform to [SHARED_CONTRACTS.md](../../modules/SHARED_CONTRACTS.md) before upsert.

---

## 6. Package layout

```text
app/parsers/
├── router.py       # fast | docling | auto dispatch
├── pdf.py          # PyMuPDF fast path
├── docling.py      # Docling adapter (PDF, DOCX, PPTX)
├── docx.py         # python-docx fast path
├── html.py         # trafilatura
├── markdown.py     # markdown-it-py
├── text.py
├── structured.py   # json/yaml/csv/xml
└── image.py        # enqueue VLM + MinIO upload
```

Dispatch from `pipeline.py` by MIME type, extension, and `parser_profile`.

---

## 7. Recommended dependencies

```text
# fast path (required)
pymupdf>=1.24.0
python-docx>=1.1.0
trafilatura>=1.12.0
beautifulsoup4>=4.12.0
markdown-it-py>=3.0.0

# docling tier (optional extra: pip install -r requirements-docling.txt)
docling>=2.0.0
```

See [DOCLING.md](./DOCLING.md) for CPU/RAM sizing and off-peak scheduling.
