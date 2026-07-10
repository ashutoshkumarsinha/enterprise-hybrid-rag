"""Neo4j read client for graph enrichment (parent sections + cross-refs).

Spec: §4.3 graph schema · §6.13.2 context blocks · FR read-only sessions.
"""

from __future__ import annotations

import os
from typing import Any

_GRAPH_QUERY = """
UNWIND $uuids AS uuid
MATCH (c:Chunk {uuid: uuid, tenant_id: $tenant_id})
OPTIONAL MATCH (s:Section)-[:HAS_CHUNK]->(c)
OPTIONAL MATCH (ancestor:Section)-[:HAS_SECTION|HAS_SUBSECTION*1..2]->(s)
WITH c, collect(DISTINCT coalesce(ancestor.title, ancestor.name, ancestor.section_id)) AS parent_titles
OPTIONAL MATCH (d:Document {document_id: c.document_id, tenant_id: $tenant_id})-[:REFERENCES]->(ref:Document)
RETURN c.uuid AS uuid,
       [t IN parent_titles WHERE t IS NOT NULL] AS lineage,
       collect(DISTINCT ref.document_id) AS cross_refs,
       c.image_url AS image_url
"""


class Neo4jClient:
    """Read-only Neo4j client for ``graph_enrich``."""

    def __init__(
        self,
        *,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        max_cross_refs: int | None = None,
        max_section_parents: int | None = None,
    ) -> None:
        self.uri = uri or os.environ.get("NEO4J_URI", "")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "")
        self.max_cross_refs = max_cross_refs or int(os.environ.get("MAX_CROSS_REFS_PER_BLOCK", "5"))
        self.max_section_parents = max_section_parents or int(
            os.environ.get("MAX_SECTION_PARENTS", "2")
        )
        self._stub = os.environ.get("NEO4J_STUB", "").lower() in ("true", "1", "yes") or not self.uri
        self._driver = None
        if not self._stub:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )

    @property
    def is_stub(self) -> bool:
        return self._stub

    def healthcheck(self) -> bool:
        if self._stub:
            return True
        try:
            assert self._driver is not None
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def enrich_chunks(
        self,
        chunks: list[dict[str, Any]],
        *,
        tenant_id: str,
    ) -> dict[str, dict[str, Any]]:
        """Return graph metadata keyed by chunk ``uuid``."""
        if not chunks:
            return {}
        uuids = [str(c.get("uuid")) for c in chunks if c.get("uuid")]
        if not uuids:
            return {}
        if self._stub:
            return {uuid: _stub_graph_meta(chunk) for uuid, chunk in _uuid_chunk_pairs(chunks)}
        assert self._driver is not None
        meta: dict[str, dict[str, Any]] = {}
        with self._driver.session(default_access_mode="READ") as session:
            result = session.run(_GRAPH_QUERY, uuids=uuids, tenant_id=tenant_id)
            for record in result:
                uuid = str(record["uuid"])
                lineage = list(record["lineage"] or [])[: self.max_section_parents]
                cross_refs = [r for r in (record["cross_refs"] or []) if r][
                    : self.max_cross_refs
                ]
                meta[uuid] = {
                    "lineage": lineage,
                    "cross_refs": cross_refs,
                    "image_url": record.get("image_url"),
                }
        for uuid, chunk in _uuid_chunk_pairs(chunks):
            meta.setdefault(uuid, _fallback_graph_meta(chunk))
        return meta


def _uuid_chunk_pairs(chunks: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    pairs: list[tuple[str, dict[str, Any]]] = []
    for chunk in chunks:
        uuid = chunk.get("uuid")
        if uuid:
            pairs.append((str(uuid), chunk))
    return pairs


def _stub_graph_meta(chunk: dict[str, Any]) -> dict[str, Any]:
    section = chunk.get("section_title") or "Overview"
    refs = list(chunk.get("references") or [])
    if not refs:
        refs = ["related-doc"]
    return {
        "lineage": [f"Chapter → {section}"],
        "cross_refs": refs[:5],
        "image_url": chunk.get("image_url"),
        "stub": True,
    }


def _fallback_graph_meta(chunk: dict[str, Any]) -> dict[str, Any]:
    refs = [r for r in (chunk.get("references") or []) if r]
    return {
        "lineage": [],
        "cross_refs": refs[:5],
        "image_url": chunk.get("image_url"),
        "stub": False,
    }
