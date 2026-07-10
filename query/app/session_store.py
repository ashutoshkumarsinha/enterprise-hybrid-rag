"""Conversation session persistence for MCP multi-turn history.

Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §7.11 · query/docs/SESSIONS.md.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from app.settings import Settings, get_settings

SessionRow = dict[str, Any]
MessageRow = dict[str, Any]


def _now() -> datetime:
    return datetime.now(UTC)


class SessionStore(ABC):
    @abstractmethod
    def create_session(
        self,
        *,
        tenant_id: str,
        principal: str,
        title: str | None = None,
        collection_id: str | None = None,
        document_id: str | None = None,
        version_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionRow:
        raise NotImplementedError

    @abstractmethod
    def list_sessions(
        self,
        *,
        tenant_id: str,
        principal: str,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> list[SessionRow]:
        raise NotImplementedError

    @abstractmethod
    def get_session(self, session_id: str, *, tenant_id: str, principal: str) -> SessionRow | None:
        raise NotImplementedError

    @abstractmethod
    def get_history(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        limit: int = 50,
    ) -> list[MessageRow]:
        raise NotImplementedError

    @abstractmethod
    def load_history(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        max_turns: int,
    ) -> list[dict[str, str]]:
        raise NotImplementedError

    @abstractmethod
    def update_session(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        title: str | None = None,
        collection_id: str | None = None,
        document_id: str | None = None,
        version_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionRow | None:
        raise NotImplementedError

    @abstractmethod
    def delete_session(self, session_id: str, *, tenant_id: str, principal: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def append_turn(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        user_content: str,
        assistant_content: str,
        rag_metadata: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRow] = {}
        self._messages: dict[str, list[MessageRow]] = {}

    def create_session(
        self,
        *,
        tenant_id: str,
        principal: str,
        title: str | None = None,
        collection_id: str | None = None,
        document_id: str | None = None,
        version_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionRow:
        session_id = str(uuid.uuid4())
        created_at = _now()
        row: SessionRow = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "principal": principal,
            "title": title,
            "collection_id": collection_id,
            "document_id": document_id,
            "version_id": version_id,
            "metadata": metadata or {},
            "message_count": 0,
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
            "deleted_at": None,
        }
        self._sessions[session_id] = row
        self._messages[session_id] = []
        return dict(row)

    def list_sessions(
        self,
        *,
        tenant_id: str,
        principal: str,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> list[SessionRow]:
        rows = [
            s
            for s in self._sessions.values()
            if s["tenant_id"] == tenant_id and s["principal"] == principal
        ]
        if not include_deleted:
            rows = [s for s in rows if s.get("deleted_at") is None]
        rows.sort(key=lambda s: s["updated_at"], reverse=True)
        return [dict(s) for s in rows[:limit]]

    def get_session(self, session_id: str, *, tenant_id: str, principal: str) -> SessionRow | None:
        row = self._sessions.get(session_id)
        if row is None or row.get("deleted_at") is not None:
            return None
        if row["tenant_id"] != tenant_id or row["principal"] != principal:
            return None
        return dict(row)

    def get_history(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        limit: int = 50,
    ) -> list[MessageRow]:
        if self.get_session(session_id, tenant_id=tenant_id, principal=principal) is None:
            return []
        messages = self._messages.get(session_id, [])
        return [dict(m) for m in messages[-limit:]]

    def load_history(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        max_turns: int,
    ) -> list[dict[str, str]]:
        messages = self.get_history(
            session_id, tenant_id=tenant_id, principal=principal, limit=max_turns * 2
        )
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def update_session(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        title: str | None = None,
        collection_id: str | None = None,
        document_id: str | None = None,
        version_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionRow | None:
        row = self.get_session(session_id, tenant_id=tenant_id, principal=principal)
        if row is None:
            return None
        stored = self._sessions[session_id]
        if title is not None:
            stored["title"] = title
        if collection_id is not None:
            stored["collection_id"] = collection_id
        if document_id is not None:
            stored["document_id"] = document_id
        if version_id is not None:
            stored["version_id"] = version_id
        if metadata is not None:
            stored["metadata"] = metadata
        stored["updated_at"] = _now().isoformat()
        return dict(stored)

    def delete_session(self, session_id: str, *, tenant_id: str, principal: str) -> bool:
        row = self.get_session(session_id, tenant_id=tenant_id, principal=principal)
        if row is None:
            return False
        self._sessions[session_id]["deleted_at"] = _now().isoformat()
        return True

    def append_turn(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        user_content: str,
        assistant_content: str,
        rag_metadata: dict[str, Any] | None = None,
    ) -> None:
        if self.get_session(session_id, tenant_id=tenant_id, principal=principal) is None:
            raise KeyError(session_id)
        now = _now().isoformat()
        messages = self._messages.setdefault(session_id, [])
        messages.append(
            {
                "message_id": str(uuid.uuid4()),
                "session_id": session_id,
                "tenant_id": tenant_id,
                "role": "user",
                "content": user_content,
                "created_at": now,
            }
        )
        messages.append(
            {
                "message_id": str(uuid.uuid4()),
                "session_id": session_id,
                "tenant_id": tenant_id,
                "role": "assistant",
                "content": assistant_content,
                "rag_metadata": rag_metadata,
                "created_at": now,
            }
        )
        stored = self._sessions[session_id]
        stored["message_count"] = stored.get("message_count", 0) + 2
        stored["updated_at"] = now


class PostgresSessionStore(SessionStore):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn)

    def create_session(
        self,
        *,
        tenant_id: str,
        principal: str,
        title: str | None = None,
        collection_id: str | None = None,
        document_id: str | None = None,
        version_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionRow:
        import json

        session_id = str(uuid.uuid4())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversation_sessions (
                        session_id, tenant_id, principal, title,
                        collection_id, document_id, version_id, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING created_at, updated_at, message_count
                    """,
                    (
                        session_id,
                        tenant_id,
                        principal,
                        title,
                        collection_id,
                        document_id,
                        version_id,
                        json.dumps(metadata or {}),
                    ),
                )
                created_at, updated_at, message_count = cur.fetchone()
            conn.commit()
        return {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "principal": principal,
            "title": title,
            "collection_id": collection_id,
            "document_id": document_id,
            "version_id": version_id,
            "metadata": metadata or {},
            "message_count": message_count,
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat(),
            "deleted_at": None,
        }

    def list_sessions(
        self,
        *,
        tenant_id: str,
        principal: str,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> list[SessionRow]:
        sql = """
            SELECT session_id, tenant_id, principal, title, collection_id, document_id,
                   version_id, metadata, message_count, created_at, updated_at, deleted_at
            FROM conversation_sessions
            WHERE tenant_id = %s AND principal = %s
        """
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        sql += " ORDER BY updated_at DESC LIMIT %s"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (tenant_id, principal, limit))
                rows = cur.fetchall()
        return [_session_from_row(r) for r in rows]

    def get_session(self, session_id: str, *, tenant_id: str, principal: str) -> SessionRow | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT session_id, tenant_id, principal, title, collection_id, document_id,
                           version_id, metadata, message_count, created_at, updated_at, deleted_at
                    FROM conversation_sessions
                    WHERE session_id = %s AND tenant_id = %s AND principal = %s
                      AND deleted_at IS NULL
                    """,
                    (session_id, tenant_id, principal),
                )
                row = cur.fetchone()
        return _session_from_row(row) if row else None

    def get_history(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        limit: int = 50,
    ) -> list[MessageRow]:
        if self.get_session(session_id, tenant_id=tenant_id, principal=principal) is None:
            return []
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT message_id, session_id, tenant_id, role, content, rag_metadata, created_at
                    FROM conversation_messages
                    WHERE session_id = %s
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (session_id, limit),
                )
                rows = cur.fetchall()
        return [_message_from_row(r) for r in rows]

    def load_history(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        max_turns: int,
    ) -> list[dict[str, str]]:
        messages = self.get_history(
            session_id,
            tenant_id=tenant_id,
            principal=principal,
            limit=max_turns * 2,
        )
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def update_session(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        title: str | None = None,
        collection_id: str | None = None,
        document_id: str | None = None,
        version_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionRow | None:
        import json

        if self.get_session(session_id, tenant_id=tenant_id, principal=principal) is None:
            return None
        fields: list[str] = []
        params: list[Any] = []
        if title is not None:
            fields.append("title = %s")
            params.append(title)
        if collection_id is not None:
            fields.append("collection_id = %s")
            params.append(collection_id)
        if document_id is not None:
            fields.append("document_id = %s")
            params.append(document_id)
        if version_id is not None:
            fields.append("version_id = %s")
            params.append(version_id)
        if metadata is not None:
            fields.append("metadata = %s::jsonb")
            params.append(json.dumps(metadata))
        if not fields:
            return self.get_session(session_id, tenant_id=tenant_id, principal=principal)
        fields.append("updated_at = now()")
        params.extend([session_id, tenant_id, principal])
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE conversation_sessions
                    SET {', '.join(fields)}
                    WHERE session_id = %s AND tenant_id = %s AND principal = %s AND deleted_at IS NULL
                    """,
                    params,
                )
            conn.commit()
        return self.get_session(session_id, tenant_id=tenant_id, principal=principal)

    def delete_session(self, session_id: str, *, tenant_id: str, principal: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE conversation_sessions
                    SET deleted_at = now(), updated_at = now()
                    WHERE session_id = %s AND tenant_id = %s AND principal = %s AND deleted_at IS NULL
                    RETURNING session_id
                    """,
                    (session_id, tenant_id, principal),
                )
                row = cur.fetchone()
            conn.commit()
        return row is not None

    def append_turn(
        self,
        session_id: str,
        *,
        tenant_id: str,
        principal: str,
        user_content: str,
        assistant_content: str,
        rag_metadata: dict[str, Any] | None = None,
    ) -> None:
        import json

        if self.get_session(session_id, tenant_id=tenant_id, principal=principal) is None:
            raise KeyError(session_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversation_messages (message_id, session_id, tenant_id, role, content)
                    VALUES (%s, %s, %s, 'user', %s)
                    """,
                    (str(uuid.uuid4()), session_id, tenant_id, user_content),
                )
                cur.execute(
                    """
                    INSERT INTO conversation_messages (
                        message_id, session_id, tenant_id, role, content, rag_metadata
                    ) VALUES (%s, %s, %s, 'assistant', %s, %s::jsonb)
                    """,
                    (
                        str(uuid.uuid4()),
                        session_id,
                        tenant_id,
                        assistant_content,
                        json.dumps(rag_metadata) if rag_metadata else None,
                    ),
                )
            conn.commit()


def _session_from_row(row: tuple) -> SessionRow:
    return {
        "session_id": str(row[0]),
        "tenant_id": row[1],
        "principal": row[2],
        "title": row[3],
        "collection_id": row[4],
        "document_id": row[5],
        "version_id": row[6],
        "metadata": row[7] if isinstance(row[7], dict) else dict(row[7] or {}),
        "message_count": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
        "deleted_at": row[11].isoformat() if row[11] else None,
    }


def _message_from_row(row: tuple) -> MessageRow:
    return {
        "message_id": str(row[0]),
        "session_id": str(row[1]),
        "tenant_id": row[2],
        "role": row[3],
        "content": row[4],
        "rag_metadata": row[5],
        "created_at": row[6].isoformat() if row[6] else None,
    }


def create_session_store(settings: Settings | None = None) -> SessionStore:
    settings = settings or get_settings()
    if settings.catalog_dsn_session:
        return PostgresSessionStore(settings.catalog_dsn_session)
    return InMemorySessionStore()
