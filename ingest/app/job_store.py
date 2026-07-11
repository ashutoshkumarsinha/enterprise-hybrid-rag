"""Ingest job registry — Postgres catalog or in-memory dev store."""

from __future__ import annotations

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

_VALID_MODES = frozenset({"full", "incremental", "version"})
_VALID_STATUSES = frozenset({"pending", "running", "completed", "failed", "cancelled"})


class JobStore(ABC):
    @abstractmethod
    def healthcheck(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def create_job(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        mode: str = "incremental",
        job_type: str = "collection",
        metadata: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_job(self, job_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def mark_running(self, job_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def mark_completed(
        self,
        job_id: str,
        *,
        chunk_count: int = 0,
        files_done: int = 0,
        files_total: int = 0,
        error_count: int = 0,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def mark_failed(self, job_id: str, *, error_message: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def attach_task_id(self, job_id: str, task_id: str) -> dict[str, Any] | None:
        raise NotImplementedError


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _encode_manifest(job_type: str, metadata: dict[str, Any] | None) -> str:
    payload = {"job_type": job_type, **(metadata or {})}
    return json.dumps(payload)


def _decode_manifest(manifest_uri: str | None) -> dict[str, Any]:
    if not manifest_uri:
        return {}
    try:
        data = json.loads(manifest_uri)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {"manifest_uri": manifest_uri}


def _job_row(
    *,
    job_id: str,
    tenant_id: str,
    collection_id: str,
    status: str,
    mode: str,
    manifest_uri: str | None = None,
    files_total: int = 0,
    files_done: int = 0,
    chunk_count: int = 0,
    error_count: int = 0,
    error_message: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    meta = _decode_manifest(manifest_uri)
    return {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "status": status,
        "mode": mode,
        "job_type": meta.get("job_type", "collection"),
        "metadata": {k: v for k, v in meta.items() if k != "job_type"},
        "files_total": files_total,
        "files_done": files_done,
        "chunk_count": chunk_count,
        "error_count": error_count,
        "error_message": error_message,
        "started_at": started_at,
        "completed_at": completed_at,
        "created_at": created_at or _now_iso(),
        "stub": False,
    }


class InMemoryJobStore(JobStore):
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}

    def healthcheck(self) -> bool:
        return True

    def create_job(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        mode: str = "incremental",
        job_type: str = "collection",
        metadata: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        if mode not in _VALID_MODES:
            raise ValueError(f"invalid mode: {mode}")
        jid = job_id or str(uuid.uuid4())
        row = _job_row(
            job_id=jid,
            tenant_id=tenant_id,
            collection_id=collection_id,
            status="pending",
            mode=mode,
            manifest_uri=_encode_manifest(job_type, metadata),
        )
        self._jobs[jid] = row
        return dict(row)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self._jobs.get(job_id)
        return dict(row) if row else None

    def _update(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        row = self._jobs.get(job_id)
        if not row:
            return None
        row.update(fields)
        return dict(row)

    def mark_running(self, job_id: str) -> dict[str, Any] | None:
        return self._update(job_id, status="running", started_at=_now_iso())

    def mark_completed(
        self,
        job_id: str,
        *,
        chunk_count: int = 0,
        files_done: int = 0,
        files_total: int = 0,
        error_count: int = 0,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        return self._update(
            job_id,
            status="completed",
            chunk_count=chunk_count,
            files_done=files_done,
            files_total=files_total,
            error_count=error_count,
            error_message=error_message,
            completed_at=_now_iso(),
        )

    def mark_failed(self, job_id: str, *, error_message: str) -> dict[str, Any] | None:
        return self._update(
            job_id,
            status="failed",
            error_message=error_message,
            error_count=1,
            completed_at=_now_iso(),
        )

    def attach_task_id(self, job_id: str, task_id: str) -> dict[str, Any] | None:
        row = self._jobs.get(job_id)
        if not row:
            return None
        metadata = dict(row.get("metadata") or {})
        metadata["task_id"] = task_id
        row["metadata"] = metadata
        return dict(row)


class PostgresJobStore(JobStore):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn)

    def healthcheck(self) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return True
        except Exception:
            return False

    def _fetch_row(self, cur, job_id: str) -> dict[str, Any] | None:
        cur.execute(
            """
            SELECT job_id, tenant_id, collection_id, status, mode, manifest_uri,
                   files_total, files_done, chunk_count, error_count, error_message,
                   started_at, completed_at, created_at
            FROM ingest_jobs
            WHERE job_id = %s
            """,
            (job_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return _job_row(
            job_id=str(row[0]),
            tenant_id=row[1],
            collection_id=row[2],
            status=row[3],
            mode=row[4],
            manifest_uri=row[5],
            files_total=row[6],
            files_done=row[7],
            chunk_count=row[8],
            error_count=row[9],
            error_message=row[10],
            started_at=row[11].isoformat() if row[11] else None,
            completed_at=row[12].isoformat() if row[12] else None,
            created_at=row[13].isoformat() if row[13] else None,
        )

    def create_job(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        mode: str = "incremental",
        job_type: str = "collection",
        metadata: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        if mode not in _VALID_MODES:
            raise ValueError(f"invalid mode: {mode}")
        jid = job_id or str(uuid.uuid4())
        manifest = _encode_manifest(job_type, metadata)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ingest_jobs (
                        job_id, tenant_id, collection_id, status, mode, manifest_uri
                    )
                    VALUES (%s, %s, %s, 'pending', %s, %s)
                    RETURNING job_id
                    """,
                    (jid, tenant_id, collection_id, mode, manifest),
                )
            conn.commit()
        return self.get_job(jid) or _job_row(
            job_id=jid,
            tenant_id=tenant_id,
            collection_id=collection_id,
            status="pending",
            mode=mode,
            manifest_uri=manifest,
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                return self._fetch_row(cur, job_id)

    def mark_running(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ingest_jobs
                    SET status = 'running',
                        started_at = COALESCE(started_at, now())
                    WHERE job_id = %s
                    """,
                    (job_id,),
                )
            conn.commit()
        return self.get_job(job_id)

    def mark_completed(
        self,
        job_id: str,
        *,
        chunk_count: int = 0,
        files_done: int = 0,
        files_total: int = 0,
        error_count: int = 0,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ingest_jobs
                    SET status = 'completed',
                        chunk_count = %s,
                        files_done = %s,
                        files_total = %s,
                        error_count = %s,
                        error_message = %s,
                        completed_at = now()
                    WHERE job_id = %s
                    """,
                    (chunk_count, files_done, files_total, error_count, error_message, job_id),
                )
            conn.commit()
        return self.get_job(job_id)

    def mark_failed(self, job_id: str, *, error_message: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ingest_jobs
                    SET status = 'failed',
                        error_count = GREATEST(error_count, 1),
                        error_message = %s,
                        completed_at = now()
                    WHERE job_id = %s
                    """,
                    (error_message, job_id),
                )
            conn.commit()
        return self.get_job(job_id)

    def attach_task_id(self, job_id: str, task_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        metadata = {**(job.get("metadata") or {}), "task_id": task_id}
        manifest = _encode_manifest(job.get("job_type", "collection"), metadata)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ingest_jobs SET manifest_uri = %s WHERE job_id = %s",
                    (manifest, job_id),
                )
            conn.commit()
        return self.get_job(job_id)


_store: JobStore | None = None


def get_job_store() -> JobStore:
    global _store
    if _store is None:
        dsn = os.environ.get("CATALOG_DSN")
        _store = PostgresJobStore(dsn) if dsn else InMemoryJobStore()
    return _store


def reset_job_store() -> None:
    global _store
    _store = None
