"""Signed preview tokens for Kimai write operations.

The token is an integrity token, not an encrypted secret: the payload is
readable but cannot be modified without the per-process secret.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, cast

_SECRET = secrets.token_bytes(32)
_INVALID_TOKEN_MESSAGE = "Invalid or expired preview token. Run the preview again."


def _base64url_encode(value: bytes) -> str:
    """Encode bytes as unpadded base64url."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    """Decode unpadded base64url bytes."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_token(payload: dict[str, Any], ttl_seconds: int = 900) -> str:
    """Return a signed token containing ``payload`` and an expiry."""
    token_payload = dict(payload)
    token_payload.setdefault("v", 1)
    token_payload["exp"] = int(time.time()) + ttl_seconds
    payload_bytes = json.dumps(
        token_payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(_SECRET, payload_bytes, hashlib.sha256).digest()
    return f"{_base64url_encode(payload_bytes)}.{_base64url_encode(signature)}"


def read_token(token: str) -> dict[str, Any]:
    """Verify ``token`` and return its payload.

    Raises:
        ValueError: If the token is malformed, has an invalid signature, or expired.
    """
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError(_INVALID_TOKEN_MESSAGE)

    encoded_payload, encoded_signature = parts
    try:
        payload_bytes = _base64url_decode(encoded_payload)
        signature = _base64url_decode(encoded_signature)
    except ValueError:
        raise ValueError(_INVALID_TOKEN_MESSAGE) from None

    expected_signature = hmac.new(_SECRET, payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError(_INVALID_TOKEN_MESSAGE)

    try:
        payload = json.loads(payload_bytes)
    except ValueError:
        raise ValueError(_INVALID_TOKEN_MESSAGE) from None
    if not isinstance(payload, dict):
        raise ValueError(_INVALID_TOKEN_MESSAGE)

    expiration = payload.get("exp")
    if not isinstance(expiration, int | float) or isinstance(expiration, bool):
        raise ValueError(_INVALID_TOKEN_MESSAGE)
    if expiration <= time.time():
        raise ValueError(_INVALID_TOKEN_MESSAGE)

    return cast(dict[str, Any], payload)
