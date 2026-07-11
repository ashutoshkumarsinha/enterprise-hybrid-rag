"""Connector protocol and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator


@dataclass(frozen=True)
class SourceObject:
    key: str
    document_id: str
    etag: str | None = None
    mtime: datetime | None = None
    size: int = 0
    content_type: str | None = None


class Connector(ABC):
    @abstractmethod
    def list_objects(self, since: datetime | None = None) -> Iterator[SourceObject]:
        raise NotImplementedError

    @abstractmethod
    def fetch_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def metadata(self, key: str) -> dict[str, str]:
        raise NotImplementedError
