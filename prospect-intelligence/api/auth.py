"""
API Authentication module for Coextend Prospect Intelligence MVP.
Enforces API key authentication via 'X-API-Key' header on all prospect/job endpoints.
"""
from __future__ import annotations

import secrets
from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from config import settings

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """
    Verify the X-API-Key header against settings.api_key.
    If settings.api_key is empty/None or unset, API key verification passes
    (enabling open local development if no key is configured).
    If settings.api_key is configured, requests must supply a matching X-API-Key header.
    """
    expected_key = settings.api_key
    if not expected_key:
        return "development"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Please provide the 'X-API-Key' header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not secrets.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key
