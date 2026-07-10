"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from app.auth import resolve_auth_context
from app.models import AuthContext


async def get_auth_context(request: Request) -> AuthContext:
    return await resolve_auth_context(request)
