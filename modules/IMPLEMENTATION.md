# Implementation technology — platform reference

Normative detail: [ENTERPRISE_HYBRID_RAG_SPEC.md](../ENTERPRISE_HYBRID_RAG_SPEC.md) §1.3

| Component | Language / libraries |
|-----------|----------------------|
| hybrid-rag-query | Python 3.12+ (**LangGraph**, LangSmith, FastAPI) |
| hybrid-rag-ingest | Python 3.12+ (Celery; **PyMuPDF**, **Docling**, python-docx) |
| hybrid-rag-eval | **Ragas** (quality), **k6** / **Locust** (load) — `query/benchmarks/` |
| mod-chat (optional) | TypeScript |
| infra / observability | Compose + upstream images (no app runtime) |

| ID | Library | Role |
|----|---------|------|
| TL-08 | [Ragas](https://docs.ragas.io/) | Faithfulness, relevancy, context recall gates |
| TL-09 | [k6](https://k6.io/) / [Locust](https://locust.io/) | Load and soak tests |
| TL-10 | [Docling](https://github.com/docling-project/docling) | Complex PDF / Office parser tier |

| TL-11 | [TDD](https://en.wikipedia.org/wiki/Test-driven_development) — contract tests before implementation |

Performance: keep Python thin; call inference over HTTP (IF-4).  
Testing: [docs/TESTING.md](../docs/TESTING.md).
