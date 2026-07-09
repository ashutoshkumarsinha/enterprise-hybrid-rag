# Docling parser tier (hybrid-rag-ingest)

**Parent:** [PARSERS.md](./PARSERS.md) · Platform §5.1.1, **TL-10**  
**Library:** [Docling](https://github.com/docling-project/docling) (IBM)

---

## 1. Role

Docling is the **quality-tier** parser for complex office and PDF layouts. It is **not** the default hot path — use when:

- Multi-column PDFs, nested tables, or poor reading order with PyMuPDF
- DOCX / **PPTX** with dense tables or figures
- Collection manifest sets `parser: docling`
- `parser_profile = docling` or `auto` routes by heuristic (low extracted char count)

**Fast path** remains PyMuPDF + python-docx for throughput (NFR-04).

---

## 2. Configuration

```toml
# ingest.toml
[parsers]
profile = "auto"              # fast | docling | auto
docling_enabled = true
docling_formats = ["pdf", "docx", "pptx"]
docling_off_peak_only = false # true when sharing CPU with query peak hours
docling_max_pages = 500       # guardrail per document
```

Manifest override (per collection):

```yaml
parser: docling
```

---

## 3. Integration

```text
pipeline.py → router.py
  ├─ fast:    parsers/pdf.py (PyMuPDF)
  └─ docling: parsers/docling.py
                └─ Docling DocumentConverter → structured blocks → chunk builder
```

Output blocks map to chunk `section_title`, `text`, `page_number`, and optional `image_url` (figure export → MinIO `images/`).

---

## 4. Performance

| Concern | Guidance |
|---------|----------|
| CPU | Docling is CPU-heavy — cap `parse_workers` when profile includes Docling |
| RAM | ~2–4 GB per concurrent Docling job; size Celery parse pool accordingly |
| Throughput | Expect **5–15× slower** than PyMuPDF per page — use off-peak for bulk |
| GPU | Docling CPU by default; do not colocate with vLLM on same GPU |

**NFR-18:** Set `docling_off_peak_only = true` when ingest shares hosts with query.

---

## 5. Install

```bash
pip install -r requirements-docling.txt
# or: pip install "docling>=2.0.0"
```

Optional compose profile `docling` with higher CPU limits — future `ingest/compose` extension.

---

## 6. When not to use Docling

| Case | Use instead |
|------|-------------|
| Plain digital PDF, text-selectable | PyMuPDF (`fast`) |
| Markdown / HTML / CSV | Native parsers |
| Latency-sensitive incremental sync | `fast` unless manifest requires Docling |
| CI mock ingest (no parsers) | `benchmark_ingest.py --mock` |
