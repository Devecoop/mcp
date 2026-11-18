# Devecoop MCP

A local [Model Context Protocol](https://modelcontextprotocol.io) server that turns the
Devecoop GitLab wiki into a searchable knowledge source for AI clients. The server
retrieves evidence from the wiki and returns structured JSON with the page path and
its GitLab URL, so the client can answer with verifiable citations.

> **Status: v0.1 scaffold.** The project structure, configuration, CLI entry point and
> MCP server boot are in place. Wiki search, page reading, indexing and the CLI
> `refresh`/`status` commands are **not implemented yet**; they are tracked as
> explicit `TODO(v0.1)` placeholders.

## Overview

The wiki is a GitLab wiki cloned locally as plain Markdown. Instead of reading files
one by one, a team member asks a natural-language question in Claude Code or OpenCode.
The model calls the wiki tools exposed by this server, gets back snippets, paths and
GitLab URLs, and composes the final answer citing the source pages.

The server never calls an LLM and never writes to the wiki. It is a deterministic,
read-only retrieval layer.

## v0.1 scope

Planned for the first release:

- Local MCP server over **stdio**, single user.
- Full-text search over a local wiki clone using **SQLite FTS5** and BM25 ranking.
- Read a Markdown page by relative path.
- List pages by path prefix.
- Report index and clone status.
- Results include a snippet, relative `path`, approximate `line` and GitLab `url`.
- `devecoop-mcp refresh` to run `git pull --ff-only` and rebuild the index atomically.
- MCP tools (`wiki_search`, `wiki_read_page`, `wiki_list_pages`, `wiki_status`),
  a `wiki://page/{path}` resource and an `ask_wiki` prompt.
- Minimal tests and GitHub Actions CI.

Out of scope for v0.1: Kimai time tracking, vacation workflows, LLM synthesis inside
the server, remote HTTP/OAuth transports, semantic search/embeddings, and any writes
to the wiki.

## Requirements

- Python **3.12**
- [uv](https://docs.astral.sh/uv/)
- Git, plus access to the Devecoop GitLab wiki
- Claude Code or OpenCode as the MCP client

## Installation

```bash
git clone https://github.com/Devecoop/mcp.git
cd mcp
uv sync --all-groups
```

`uv` installs Python 3.12 if needed and creates the project virtual environment.

## Clone the wiki

Clone the Devecoop wiki wherever you prefer. The server only needs the absolute path.

```bash
git clone git@gitlab.apps.devecoop.coop.ar:devecoop/wiki.wiki.git /absolute/path/to/wiki.wiki
```

## Configuration

Copy the example file and set `WIKI_PATH` to the absolute path of the clone:

```bash
cp .env.example .env
```

```dotenv
WIKI_PATH=/absolute/path/to/wiki.wiki
WIKI_INDEX_PATH=.cache/wiki_index.sqlite3
WIKI_BASE_URL=
LOG_LEVEL=INFO
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `WIKI_PATH` | Yes | — | Absolute path to the local wiki clone. |
| `WIKI_INDEX_PATH` | No | `.cache/wiki_index.sqlite3` | SQLite index path. |
| `WIKI_BASE_URL` | No | derived from the git remote | Base URL used to build citation links. |
| `LOG_LEVEL` | No | `INFO` | Log level. Logs go to stderr. |

`.env` is loaded automatically for local development and is gitignored. In MCP client
configuration, pass `WIKI_PATH` explicitly; the `.env` file is not the only source of
truth.

## Refresh the index

```bash
uv run devecoop-mcp refresh
```

This command is **not implemented in the current scaffold**: it prints a placeholder
message and exits with a non-zero code. Once implemented, it will be the only command
that touches the network or writes files.

## Register the server

### Claude Code

```bash
claude mcp add --transport stdio \
  --env WIKI_PATH=/absolute/path/to/wiki.wiki \
  devecoop -- uv run --directory /absolute/path/to/mcp devecoop-mcp
```

### OpenCode

Add the server to your OpenCode configuration:

```jsonc
{
  "mcp": {
    "servers": {
      "devecoop": {
        "type": "local",
        "command": ["uv", "run", "--directory", "/absolute/path/to/mcp", "devecoop-mcp"],
        "environment": {
          "WIKI_PATH": "/absolute/path/to/wiki.wiki"
        }
      }
    }
  }
}
```

The recommended setup is a local checkout with `uv run --directory`. `uvx` is possible
but requires an explicit `WIKI_INDEX_PATH` so the index does not depend on the current
working directory.

## Usage

Once the wiki feature lands, typical prompts will look like:

- "What did we decide about increasing vacation days?"
- "How did the vote on the cleaning service go?"
- "Read the full minutes for November 4, 2026."
- "List the pages under `minutas/2026`."

The model uses `wiki_search` first, then `wiki_read_page` when the snippet is not
enough, and answers with the GitLab URL of each page it cites. Prompts are available
as `/devecoop:ask_wiki` in the clients.

## Development

```bash
uv sync --all-groups
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Type checking is strict for `src/`; tests are not type-checked. CLI checks:

```bash
uv run devecoop-mcp --help
uv run devecoop-mcp --version
```

## Architecture

```text
src/devecoop_mcp/
  __init__.py        # package version
  server.py          # MCPServer("devecoop") and feature registration
  cli.py             # serve / refresh / status entry point
  config.py          # pydantic-settings configuration and .env loading
  core/
    errors.py        # shared exception types
    logging.py       # stderr logging setup (stdio-safe)
  wiki/
    tools.py         # wiki_search, wiki_read_page, wiki_list_pages, wiki_status
    resources.py     # wiki://page/{path}
    prompts.py       # ask_wiki
    search.py        # FTS5 queries and ranking
    index.py         # index build/refresh and metadata
    urls.py          # GitLab URL derivation
    models.py        # Pydantic contracts for tool input/output
tests/
  test_smoke.py
```

One MCP server, one process, one feature package per capability. Future features
(`kimai/`, `vacations/`) will register from `server.py` and reuse `core/`.

## Roadmap

- **v0.1** — Wiki oracle: full-text search, page reading, listing, status, citations.
- **v0.2** — Kimai time tracking with human confirmation before writes.
- **v0.3** — Vacation request protocol.
- **Later** — Git history search, hybrid retrieval, remote transport with OAuth,
  configurable path exclusions.

## Privacy

The wiki contains internal information. The server is local and read-only, but tool
outputs (snippets, page content) are sent to the model provider of whichever client
you use. This trade-off is documented and accepted for v0.1; there are no path
exclusions yet.

## License

MIT. Copyright (c) 2026 Devecoop. See [LICENSE](LICENSE).
