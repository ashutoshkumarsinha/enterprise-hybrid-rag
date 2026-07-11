"""Neo4j write client for ingest graph merges."""

from __future__ import annotations

import os
from typing import Any

_MERGE_QUERY = """
UNWIND $rows AS row
MERGE (t:Tenant {tenant_id: row.tenant_id})
MERGE (col:Collection {tenant_id: row.tenant_id, collection_id: row.collection_id})
MERGE (t)-[:OWNS]->(col)
MERGE (d:Document {tenant_id: row.tenant_id, document_id: row.document_id})
MERGE (col)-[:CONTAINS]->(d)
MERGE (v:Version {
    tenant_id: row.tenant_id,
    document_id: row.document_id,
    version_id: row.version_id
})
MERGE (d)-[:HAS_VERSION]->(v)
MERGE (s:Section {section_graph_id: row.section_graph_id})
SET s.section_id = row.section_id,
    s.title = row.section_title,
    s.tenant_id = row.tenant_id,
    s.collection_id = row.collection_id,
    s.document_id = row.document_id
MERGE (d)-[:HAS_SECTION]->(s)
MERGE (c:Chunk {uuid: row.uuid, tenant_id: row.tenant_id})
SET c.document_id = row.document_id,
    c.version_id = row.version_id,
    c.text = row.text,
    c.type = row.type,
    c.image_url = row.image_url
MERGE (s)-[:HAS_CHUNK]->(c)
WITH row, d
UNWIND coalesce(row.references, []) AS ref_id
MERGE (ref:Document {tenant_id: row.tenant_id, document_id: ref_id})
MERGE (d)-[:REFERENCES]->(ref)
"""


class Neo4jWriter:
    """Merge chunk graph nodes for enrichment reads."""

    def __init__(
        self,
        *,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        unwind_batch: int | None = None,
    ) -> None:
        self.uri = uri or os.environ.get("NEO4J_URI", "")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "")
        self.unwind_batch = unwind_batch or int(os.environ.get("NEO4J_UNWIND_BATCH", "50"))
        self._stub = os.environ.get("NEO4J_STUB", "").lower() in ("true", "1", "yes") or not self.uri
        self._driver = None
        if not self._stub:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

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

    def merge_chunks(self, chunks: list[dict[str, Any]]) -> int:
        """Merge graph nodes for validated chunks; returns merged count."""
        if not chunks:
            return 0
        if self._stub:
            return len(chunks)
        assert self._driver is not None
        rows = [_chunk_row(chunk) for chunk in chunks]
        merged = 0
        with self._driver.session() as session:
            for start in range(0, len(rows), self.unwind_batch):
                batch = rows[start : start + self.unwind_batch]
                session.run(_MERGE_QUERY, rows=batch)
                merged += len(batch)
        return merged

    def prune_version(
        self,
        *,
        tenant_id: str,
        document_id: str,
        version_id: str,
    ) -> int:
        """Remove version node and chunk nodes for a pruned document version."""
        if self._stub:
            return 1
        assert self._driver is not None
        query = """
        OPTIONAL MATCH (c:Chunk {tenant_id: $tenant_id, document_id: $document_id, version_id: $version_id})
        WITH collect(c) AS chunks
        WITH size(chunks) AS deleted_chunks, chunks
        UNWIND chunks AS chunk
        DETACH DELETE chunk
        WITH deleted_chunks
        OPTIONAL MATCH (v:Version {tenant_id: $tenant_id, document_id: $document_id, version_id: $version_id})
        DETACH DELETE v
        RETURN deleted_chunks
        """
        with self._driver.session() as session:
            result = session.run(
                query,
                tenant_id=tenant_id,
                document_id=document_id,
                version_id=version_id,
            )
            record = result.single()
        return int(record["deleted_chunks"]) if record else 0

    def purge_tenant(self, *, tenant_id: str) -> int:
        """Remove all graph nodes scoped to a tenant."""
        if self._stub:
            return 1
        assert self._driver is not None
        query = """
        MATCH (n)
        WHERE n.tenant_id = $tenant_id
        WITH collect(n) AS nodes
        FOREACH (node IN nodes | DETACH DELETE node)
        RETURN size(nodes) AS deleted_nodes
        """
        with self._driver.session() as session:
            result = session.run(query, tenant_id=tenant_id)
            record = result.single()
        return int(record["deleted_nodes"]) if record else 0


def _chunk_row(chunk: dict[str, Any]) -> dict[str, Any]:
    tenant_id = chunk["tenant_id"]
    collection_id = chunk["collection_id"]
    document_id = chunk["document_id"]
    section_id = chunk.get("section_id") or "document"
    section_title = chunk.get("section_title") or chunk.get("title") or document_id
    section_graph_id = f"{tenant_id}:{collection_id}:{document_id}:{section_id}"
    return {
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "document_id": document_id,
        "version_id": chunk["version_id"],
        "uuid": chunk["uuid"],
        "text": chunk["text"],
        "type": chunk.get("type", "text"),
        "section_id": section_id,
        "section_title": section_title,
        "section_graph_id": section_graph_id,
        "references": list(chunk.get("references") or []),
        "image_url": chunk.get("image_url"),
    }
