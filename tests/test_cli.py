"""Tests for the ``refresh`` and ``status`` CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from devecoop_mcp.cli import main
from devecoop_mcp.wiki.index import build_index


def _write_page(root: Path, relative_path: str, content: str) -> None:
    page_path = root / relative_path
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(content, encoding="utf-8")


def _fake_successful_pull(wiki_path: Path, *arguments: str, timeout: float = 5) -> str:
    return ""


def _fake_failed_pull(wiki_path: Path, *arguments: str, timeout: float = 5) -> str | None:
    return None


def test_refresh_builds_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir()
    _write_page(wiki_path, "home.md", "# Inicio\n")
    index_path = tmp_path / ".cache" / "wiki_index.sqlite3"
    monkeypatch.setenv("WIKI_PATH", str(wiki_path))
    monkeypatch.setenv("WIKI_INDEX_PATH", str(index_path))
    monkeypatch.setattr("devecoop_mcp.cli.read_git_output", _fake_successful_pull)

    exit_code = main(["refresh"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert index_path.is_file()
    assert "Indexed 1 pages" in captured.out


def test_refresh_aborts_when_pull_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir()
    _write_page(wiki_path, "home.md", "# Inicio\n")
    index_path = tmp_path / ".cache" / "wiki_index.sqlite3"
    monkeypatch.setenv("WIKI_PATH", str(wiki_path))
    monkeypatch.setenv("WIKI_INDEX_PATH", str(index_path))
    monkeypatch.setattr("devecoop_mcp.cli.read_git_output", _fake_failed_pull)

    exit_code = main(["refresh"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert not index_path.exists()
    assert "git pull" in captured.err


def test_status_reads_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir()
    _write_page(wiki_path, "home.md", "# Inicio\n")
    index_path = tmp_path / ".cache" / "wiki_index.sqlite3"
    build_index(wiki_path=wiki_path, index_path=index_path)
    monkeypatch.setenv("WIKI_PATH", str(wiki_path))
    monkeypatch.setenv("WIKI_INDEX_PATH", str(index_path))

    exit_code = main(["status"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Pages: 1" in captured.out
    assert "Wiki path:" in captured.out
