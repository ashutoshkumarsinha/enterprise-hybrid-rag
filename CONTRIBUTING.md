# Contributing

Thank you for contributing to Enterprise Hybrid RAG. This project is **spec-driven**: behavior is defined in `ENTERPRISE_HYBRID_RAG_SPEC.md` and sub-project `SPEC.md` files before (or alongside) code.

---

## Before you open a PR

1. **Read the developer guide** — [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)
2. **Follow coding standards** — [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md) (§23)
3. **Follow TDD** — [docs/TESTING.md](docs/TESTING.md) (TL-11)
4. **Update documentation** — [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) (NFR-25, FR-35)

---

## PR checklist

- [ ] Failing or updated tests for contract/kernel/MCP/pipeline changes (FR-33, FR-34)
- [ ] Sub-project `SPEC.md` and/or audience guide updated if behavior is user- or ops-visible
- [ ] New architecture/flow diagrams use **Mermaid** only (TL-12, FR-36)
- [ ] Public Python/TypeScript APIs have novice-readable docstrings (TL-13, FR-37)
- [ ] Code follows [CODING_STANDARDS.md](docs/CODING_STANDARDS.md) (FR-38)
- [ ] `make health` (or documented equivalent) still passes for touched sub-projects

---

## Code style

Follow **[docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md)** (platform spec §23):

- **Python 3.12+** for query and ingest; match existing imports and typing.
- **Black** + **Ruff** — root `pyproject.toml`; run `ruff check` / `black --check` before PR (TL-14).
- **Type hints** on all new public functions (TL-15).
- **Minimize scope** — one focused change per PR when possible.
- **No** vLLM/torch imports in query or ingest images (TL-02).
- **Structured logs** with `tenant_id` / `request_id` where applicable (TL-16).
- Comments explain **why** and **which spec requirement** — see [DOCUMENTATION.md](docs/DOCUMENTATION.md) §4.

---

## Documentation audiences

| If you change… | Update… |
|----------------|---------|
| MCP tools / streaming | `query/docs/`, [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |
| Ingest / ACL / quotas | `ingest/docs/`, [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) |
| Compose / bootstrap | `infra/docs/`, [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) |
| IF-* interfaces | [docs/ARCHITECT_GUIDE.md](docs/ARCHITECT_GUIDE.md), `SHARED_CONTRACTS.md` |

---

## Questions

Open a discussion or issue with the sub-project label (`query`, `ingest`, `infra`, etc.). Architects should start from [docs/ARCHITECT_GUIDE.md](docs/ARCHITECT_GUIDE.md).
