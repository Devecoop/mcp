"""Tests for signed Kimai preview tokens."""

from __future__ import annotations

import pytest

from devecoop_mcp.kimai.tokens import create_token, read_token


def test_token_round_trip() -> None:
    payload = {"kind": "create", "user_id": 7, "entries": [{"begin": "2026-11-19T09:00:00"}]}

    token = create_token(payload)
    restored = read_token(token)

    assert restored["kind"] == "create"
    assert restored["user_id"] == 7
    assert restored["entries"] == [{"begin": "2026-11-19T09:00:00"}]
    assert restored["v"] == 1
    assert restored["exp"] > 0


def test_tampered_token_is_rejected() -> None:
    token = create_token({"kind": "create"})
    encoded_payload, encoded_signature = token.split(".")
    replacement = "A" if encoded_signature[0] != "A" else "B"
    tampered = f"{encoded_payload}.{replacement}{encoded_signature[1:]}"

    with pytest.raises(ValueError, match="Invalid or expired preview token"):
        read_token(tampered)


def test_expired_token_is_rejected() -> None:
    token = create_token({"kind": "create"}, ttl_seconds=-1)

    with pytest.raises(ValueError, match="Invalid or expired preview token"):
        read_token(token)


def test_malformed_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid or expired preview token"):
        read_token("not-a-valid-token")


def test_error_message_does_not_echo_the_token() -> None:
    token = create_token({"kind": "create"})

    with pytest.raises(ValueError) as exc_info:
        read_token(token + "x")

    message = str(exc_info.value)
    assert "Invalid or expired preview token" in message
    assert token not in message
