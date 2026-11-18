"""Tests for GitLab wiki URL derivation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devecoop_mcp.wiki import urls

DEVECOOP_REMOTE = "git@gitlab.apps.devecoop.coop.ar:devecoop/wiki.wiki.git"
DEVECOOP_BASE = "https://gitlab.apps.devecoop.coop.ar/devecoop/wiki/-/wikis/"
DEVECOOP_PAGE = f"{DEVECOOP_BASE}reglas/vacaciones"


def test_parse_devecoop_remote() -> None:
    assert urls.parse_remote_url(DEVECOOP_REMOTE) == DEVECOOP_BASE


def test_parse_unsupported_remote_returns_none() -> None:
    assert urls.parse_remote_url("https://gitlab.example.com/group/project.git") is None


def test_derive_base_url_reads_origin(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert command == ["git", "-C", str(tmp_path), "remote", "get-url", "origin"]
        return subprocess.CompletedProcess(command, 0, stdout=DEVECOOP_REMOTE, stderr="")

    monkeypatch.setattr(urls.subprocess, "run", fake_run)

    assert urls.derive_base_url(tmp_path) == DEVECOOP_BASE


def test_derive_base_url_returns_none_on_git_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 128, stdout="", stderr="fatal")

    monkeypatch.setattr(urls.subprocess, "run", fake_run)

    assert urls.derive_base_url(tmp_path) is None


@pytest.mark.parametrize(
    ("page_path", "expected_slug"),
    [
        ("Reglas/vacaciones.md", "reglas/vacaciones"),
        (
            "Reglas/Abrir-tema-a-socies-+-Gestion-de-la-queja.md",
            "reglas/abrir-tema-a-socies-%2B-gestion-de-la-queja",
        ),
    ],
)
def test_page_path_to_slug(page_path: str, expected_slug: str) -> None:
    assert urls.page_path_to_slug(page_path) == expected_slug


@pytest.mark.parametrize(
    "base_url",
    [
        DEVECOOP_BASE,
        "https://gitlab.apps.devecoop.coop.ar/devecoop/wiki",
    ],
)
def test_page_url_builds_citation(base_url: str, tmp_path: Path) -> None:
    assert (
        urls.page_url(
            wiki_path=tmp_path,
            page_path="Reglas/vacaciones.md",
            base_url=base_url,
        )
        == DEVECOOP_PAGE
    )


def test_page_url_returns_none_without_base(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_derive_base_url(wiki_path: Path) -> str | None:
        assert wiki_path == tmp_path
        return None

    monkeypatch.setattr(urls, "derive_base_url", fake_derive_base_url)

    assert urls.page_url(wiki_path=tmp_path, page_path="Reglas/vacaciones.md") is None
