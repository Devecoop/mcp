# Devecoop MCP — Guidelines y alcance del MVP

**Resumen:** este repositorio construye un servidor MCP interno para automatizar tareas repetitivas de Devecoop. La v0.1 implementa el **Oráculo de la wiki**: búsqueda y lectura de la wiki local clonada desde GitLab, con respuestas basadas en evidencia y citas verificables. Las versiones siguientes agregan carga de horas en Kimai y el protocolo de vacaciones.

El objetivo es doble: resolver un problema real del equipo y demostrar, en un proyecto público y acotado, dominio de los conceptos de MCP, retrieval, testing y operación de servidores MCP.

---

## Quick path

1. Clonar la wiki de GitLab en una ruta local.
2. Copiar `.env.example` a `.env` y apuntar `WIKI_PATH` a esa ruta.
3. Ejecutar `uv run devecoop-mcp refresh` para clonar/actualizar y construir el índice.
4. Registrar el servidor en Claude Code u OpenCode.
5. Preguntar en lenguaje natural; la respuesta debe citar la URL de GitLab de la página usada.

---

## 1. Propósito y éxito del proyecto

### 1.1 Problema

El equipo discute decisiones en asambleas semanales y las deja asentadas en una wiki de GitLab. Con el tiempo, encontrar una decisión vieja implica abrir archivos uno por uno. Lo mismo pasa con reglamentos, licencias y documentación interna: la información existe, pero no es accesible en el momento de la pregunta.

### 1.2 Resultado esperado

Un servidor MCP local, instalable por cualquier socio, que permita preguntar en lenguaje natural sobre el contenido de la wiki y recibir una respuesta con la fuente exacta. El servidor no inventa: recupera evidencia textual y la entrega al cliente (Claude Code u OpenCode), que compone la respuesta final y cita la URL.

### 1.3 Definición de éxito

- Los tres flujos del proyecto quedan funcionando de punta a punta: Oráculo (v0.1), Kimai (v0.2) y vacaciones (v0.3).
- La instalación y el setup son sencillos y están documentados.
- El README permite que otra persona lo reproduzca sin ayuda.
- Todos los tests pasan y el pipeline de GitHub Actions valida tests y linting.
- Existe un documento de conceptos MCP que registra lo aprendido.

---

## 2. Principios del proyecto

| Principio | Decisión | Por qué |
|---|---|---|
| Monolito modular | Un solo servidor MCP, módulos por feature | Una instalación, un proceso, y cada feature se puede separar después |
| Read-only primero | v0.1 no escribe en la wiki ni en servicios externos | Menos riesgo, más fácil de testear y explicar |
| Evidencia sobre síntesis | El servidor recupera y cita; el cliente razona | Sin API keys, sin costo por consulta, resultados determinísticos |
| Configuración mínima | Una variable obligatoria: `WIKI_PATH` | La instalación no depende de archivos mágicos ni de un cwd específico |
| JSON como contrato | Las tools devuelven JSON estructurado | El modelo recibe campos claros y puede citar sin ambigüedad |
| Citas verificables | Cada resultado incluye `path` y `url` de GitLab | La respuesta se puede auditar |
| Tests mínimos y útiles | Solo comportamiento crítico, no internals | Evitar una suite grande que no aporta señal |
| Documentación para humanos | README en inglés; conceptos y guidelines en español | Portfolio para entrevistas + aprendizaje del equipo |

---

## 3. Alcance de la v0.1: Oráculo de la wiki

### 3.1 Historias de usuario

- **Como socio**, quiero preguntar "¿qué decidimos sobre el aumento de días de vacaciones?" y recibir una respuesta con la página y la URL exacta.
- **Como socio**, quiero preguntar "¿cómo salió la votación del servicio de limpieza?" y ver la minuta correspondiente.
- **Como socio**, quiero leer una página completa cuando el snippet no alcanza.
- **Como socio**, quiero listar las páginas de una sección (`minutas/2026`, `Reglas/`) para explorar.
- **Como dev**, quiero actualizar la wiki y el índice con un solo comando.
- **Como dev**, quiero que el servidor falle con un error claro si falta configuración o el índice no existe.

### 3.2 En alcance

- Servidor MCP local por **stdio**, single-user.
- Búsqueda full-text sobre un clon local de la wiki de GitLab.
- Lectura de páginas Markdown.
- Listado de páginas por prefijo.
- Estado del índice y del clon.
- Respuestas con snippet, path relativo y URL de GitLab.
- Comando `refresh` para `git pull --ff-only` + reconstrucción del índice.
- Tools MCP (solo tools).
- Tests mínimos y CI en GitHub Actions.
- README en inglés y documentación de conceptos MCP en español.

### 3.3 Fuera de alcance

- Kimai, Gmail, Google Calendar y el protocolo de vacaciones (v0.2 y v0.3).
- MCP resources y prompts: la v0.1 expone solo tools.
- Síntesis con un LLM dentro del servidor.
- Transporte HTTP remoto, OAuth o multiusuario.
- Búsqueda en la historia de Git (solo checkout actual).
- Auto-pull, cron o daemon dentro del servidor.
- Escritura en la wiki.
- Embeddings, RAG semántico o vector store.
- Exclusión de paths sensibles (decisión explícita para v0.1; ver riesgos).

---

## 4. Cómo funciona la v0.1

### 4.1 Flujo completo

```text
┌─────────────────────┐
│  Wiki local (.md)   │
│  clon de GitLab     │
└─────────┬───────────┘
          │ refresh: git pull --ff-only
          ▼
┌─────────────────────┐
│  Índice SQLite FTS5 │
│  .cache/wiki_index  │
└─────────┬───────────┘
          │ lectura
          ▼
┌─────────────────────┐      tools/list, tools/call      ┌──────────────────┐
│  Servidor MCP       │ ◄──────────────────────────────► │  Claude Code /   │
│  devecoop           │                                  │  OpenCode        │
└─────────────────────┘                                  └──────────────────┘
```

1. `devecoop-mcp refresh` actualiza el clon y reconstruye el índice.
2. El servidor MCP abre el índice en modo lectura.
3. El usuario pregunta en el cliente.
4. El modelo llama a `wiki_search` con los términos relevantes.
5. El servidor devuelve JSON con snippets, paths y URLs.
6. Si hace falta más contexto, el modelo llama a `wiki_read_page`.
7. El cliente redacta la respuesta y cita la URL de cada fuente.

> **Importante:** el servidor no genera la respuesta final. El JSON de las tools es lo que el modelo ve y usa como evidencia. Por eso el JSON debe ser pequeño, claro y con la cita incluida.

### 4.2 Fuente de datos

- Un clon local de la wiki de GitLab, configurado por cada usuario en `WIKI_PATH`.
- Solo se indexan archivos `.md`.
- Se excluyen `.git/`, `uploads/` y `_sidebar.md` (navegación redundante).
- No hay frontmatter: el título se toma del primer `# H1`; si no existe, del nombre del archivo.
- Los nombres de archivo son inconsistentes (`Minuta-DD-MM-YYYY.md`, `YYYY-MM-DD.md`, `N.md`, slugs). El índice no depende de esa convención.
- El corpus actual verificado tiene **401 archivos `.md`** y 721 KB de texto. El repo tiene 433 archivos totales (32 MB, incluyendo imágenes). En la historia hay 689 paths `.md` únicos; la v0.1 indexa solo el checkout actual.

### 4.3 Búsqueda

- SQLite **FTS5** con tokenizer `unicode61 remove_diacritics 2`.
- Ranking **BM25** con boost de título y headings.
- La recencia no se usa como señal principal; solo como desempate.
- Query saneada: se eliminan operadores de FTS5 y se citan los términos; se soportan frases entre comillas.
- Resultado por defecto: 8 páginas, snippet de ~400 caracteres alrededor del mejor match.
- `path_prefix` permite acotar a una sección (`minutas/`, `Reglas/`, etc.).
- Límite máximo de resultados: 20.

Medición sobre el corpus real: build del índice en **48 ms** y queries en **1–3 ms**. Para 401 documentos, no hace falta un servicio externo ni un vector store.

### 4.4 Citas y URLs

Cada resultado incluye:

- `path`: ruta relativa a la wiki, por ejemplo `Reglas/vacaciones.md`.
- `url`: URL de GitLab, por ejemplo `https://gitlab.apps.devecoop.coop.ar/devecoop/wiki.wiki/-/wikis/Reglas/vacaciones`.
- `snippet`: texto exacto que respalda la respuesta.
- `line`: línea aproximada donde empieza el snippet.

La URL se deriva del remote `origin` del clon de la wiki:

```text
git@gitlab.apps.devecoop.coop.ar:devecoop/wiki.wiki.git
→ https://gitlab.apps.devecoop.coop.ar/devecoop/wiki.wiki/-/wikis/<path-sin-.md>
```

Si el remote no se puede parsear, `url` es `null` y el modelo cita el `path`. `WIKI_BASE_URL` permite override explícito.

Se verificó que el formato de URL responde `200` para páginas anidadas y con caracteres especiales, por ejemplo:

- `/-/wikis/minutas/2026/Minuta-04-11-2026`
- `/-/wikis/Reglas/vacaciones`
- `/-/wikis/Abrir-tema-a-socies-+-Gestion-de-la-queja`

### 4.5 Superficie MCP

| Primitiva | Nombre | Quién la usa | Salida |
|---|---|---|---|
| Tool | `wiki_search` | El modelo | JSON con resultados, snippets y URLs |
| Tool | `wiki_read_page` | El modelo | JSON con contenido Markdown completo y URL |
| Tool | `wiki_list_pages` | El modelo | JSON con paths, títulos y URLs, filtrable por prefijo |
| Tool | `wiki_status` | El modelo o el usuario | JSON con estado del clon y del índice |

**Quién decide qué:**

- **Tools:** las elige el modelo según el pedido y las descripciones. Son la única superficie MCP de la v0.1.

> **Nota:** los resources y prompts MCP quedaron fuera del alcance de la v0.1; el servidor expone solo tools.

### 4.6 Contratos de las tools

#### `wiki_search`

Entrada:

```json
{
  "query": "días de vacaciones",
  "limit": 8,
  "path_prefix": "Reglas"
}
```

Salida:

```json
{
  "query": "días de vacaciones",
  "results": [
    {
      "path": "Reglas/vacaciones.md",
      "title": "Vacaciones",
      "url": "https://gitlab.apps.devecoop.coop.ar/devecoop/wiki.wiki/-/wikis/Reglas/vacaciones",
      "snippet": "Cada socie tiene 14 días de vacaciones y el total aumenta cada 5 años de antigüedad...",
      "line": 12,
      "score": 8.42
    }
  ],
  "total": 1
}
```

#### `wiki_read_page`

Entrada:

```json
{ "path": "Reglas/vacaciones.md" }
```

Salida:

```json
{
  "path": "Reglas/vacaciones.md",
  "title": "Vacaciones",
  "url": "https://gitlab.apps.devecoop.coop.ar/devecoop/wiki.wiki/-/wikis/Reglas/vacaciones",
  "content": "# Vacaciones\n\n...",
  "line_count": 80
}
```

#### `wiki_list_pages`

Entrada:

```json
{ "prefix": "minutas/2026", "limit": 50 }
```

Salida:

```json
{
  "pages": [
    {
      "path": "minutas/2026/Minuta-04-11-2026.md",
      "title": "Minuta 04/11/2026",
      "url": "https://gitlab.apps.devecoop.coop.ar/devecoop/wiki.wiki/-/wikis/minutas/2026/Minuta-04-11-2026"
    }
  ],
  "total": 44
}
```

#### `wiki_status`

Salida:

```json
{
  "wiki_path": "/home/alejandro/Escritorio/proyectos/wiki.wiki",
  "index_path": ".cache/wiki_index.sqlite3",
  "page_count": 401,
  "last_indexed_at": "2026-11-18T16:00:00-03:00",
  "git_commit": "c0cbec2",
  "git_remote": "git@gitlab.apps.devecoop.coop.ar:devecoop/wiki.wiki.git"
}
```

### 4.7 Configuración

Variables de entorno:

| Variable | Obligatoria | Default | Descripción |
|---|---|---|---|
| `WIKI_PATH` | Sí | — | Ruta absoluta al clon local de la wiki |
| `WIKI_INDEX_PATH` | No | `.cache/wiki_index.sqlite3` | Ruta del índice SQLite |
| `WIKI_BASE_URL` | No | derivada del remote | Base URL de GitLab para citas |
| `LOG_LEVEL` | No | `INFO` | Nivel de logging |

- `.env` se carga automáticamente para desarrollo local.
- En Claude Code y OpenCode, `WIKI_PATH` se pasa explícito en la configuración del cliente. El `.env` no es la única fuente de verdad.
- Si falta `WIKI_PATH`, el servidor falla con un mensaje que indica qué variable configurar.
- `.env` está en `.gitignore`; `.env.example` tiene un placeholder de path absoluto, porque cada usuario clona la wiki donde quiere.

### 4.8 CLI

| Comando | Qué hace |
|---|---|
| `devecoop-mcp` | Corre el servidor MCP por stdio |
| `devecoop-mcp refresh` | `git pull --ff-only` en la wiki + reconstrucción atómica del índice |
| `devecoop-mcp status` | Muestra path, cantidad de páginas, commit y última indexación |
| `devecoop-mcp --version` | Muestra la versión |

`refresh` es el único comando que hace red y escribe. Si el `git pull` falla (por ejemplo, por cambios locales), aborta sin tocar el índice.

El servidor no reconstruye el índice automáticamente. Si el índice no existe, falla con: `Index not found. Run 'devecoop-mcp refresh' first.`

### 4.9 Arquitectura

```text
src/devecoop_mcp/
  __init__.py
  server.py          # MCPServer("devecoop") + registro de features
  cli.py             # serve / refresh / status
  config.py          # Settings y carga de .env
  core/
    errors.py
    logging.py
  wiki/
    __init__.py
    tools.py         # wiki_search, wiki_read_page, wiki_list_pages, wiki_status
    search.py        # consultas FTS5 y ranking
    index.py         # build/refresh del índice y metadata
    urls.py          # derivación de URLs de GitLab
    models.py        # modelos Pydantic de entrada/salida
tests/
  test_config.py
  test_search.py
  test_path_safety.py
  test_index.py
  test_protocol_smoke.py
```

Un solo servidor MCP. Cada feature futura (`kimai/`, `vacations/`) se registra desde `server.py` y reutiliza lo que necesite.

### 4.10 Seguridad y privacidad

- **Path traversal:** `wiki_read_page` resuelve la ruta y verifica que siga dentro de `WIKI_PATH`. Se rechazan paths absolutos, `..`, symlinks que escapan y archivos que no sean `.md`.
- **Sin escritura:** el servidor no modifica la wiki ni servicios externos.
- **Sin red en `serve`:** el servidor solo lee el filesystem y el índice.
- **Refresh controlado:** `refresh` hace `git pull --ff-only` y reconstruye el índice en un archivo temporal, luego lo reemplaza de forma atómica.
- **Datos sensibles:** la wiki contiene información interna (fiscal, licencias, strikes, salud). El servidor es local, pero los snippets que devuelven las tools viajan al proveedor del modelo del cliente (Claude Code u OpenCode). Para v0.1 se acepta ese riesgo y se documenta; no hay exclusiones por defecto. Si el equipo define una política de datos, se agrega `WIKI_EXCLUDE_PATHS` en una versión futura.
- **Secretos:** `.env` no se commitea. No hay tokens en la v0.1.

---

## 5. Criterios de aceptación

### 5.1 Funcionales

- [ ] Con `WIKI_PATH` válido, `devecoop-mcp refresh` construye el índice y `devecoop-mcp status` reporta la cantidad real de páginas, el commit y la fecha de indexación.
- [ ] `wiki_search("días de vacaciones")` devuelve al menos la página de vacaciones, con snippet, `path` y `url`.
- [ ] `wiki_search` respeta `path_prefix` y `limit`.
- [ ] `wiki_read_page("Reglas/vacaciones.md")` devuelve el contenido completo y la URL.
- [ ] `wiki_list_pages(prefix="minutas/2026")` devuelve solo páginas de esa sección.
- [ ] `wiki_status` refleja el estado real del clon y del índice.
- [ ] Sin `WIKI_PATH`, el servidor falla con un error claro.
- [ ] Sin índice, el servidor falla con un mensaje que indica ejecutar `refresh`.
- [ ] `wiki_read_page("../etc/passwd")`, un path absoluto y un symlink que escapa son rechazados.
- [ ] Los outputs de las tools son JSON válidos y contienen `path`, `title`, `url` y evidencia textual.

### 5.2 Protocolo MCP

- [ ] `tools/list` muestra las cuatro tools con descripciones y annotations de solo lectura.
- [ ] El servidor funciona en Claude Code con `claude mcp add`.
- [ ] El servidor funciona en OpenCode con `mcp.servers.devecoop`.
- [ ] `mcp dev` / Inspector muestra las tools sin errores.

### 5.3 Calidad

- [ ] `ruff check .` pasa.
- [ ] `ruff format --check .` pasa.
- [ ] `mypy src` pasa.
- [ ] `pytest` pasa.
- [ ] GitHub Actions ejecuta lint, typecheck y tests en Python 3.12.
- [ ] La suite es mínima: configuración, búsqueda/citas, path safety, índice y smoke test de protocolo. No se testean internals de FTS5 ni helpers triviales.

### 5.4 Documentación y demo

- [ ] `README.md` en inglés: clonar la wiki, configurar `.env`, `refresh`, Claude Code, OpenCode, ejemplos de uso, arquitectura, privacidad y desarrollo.
- [ ] `docs/mcp-concepts.md` en español: protocolo, ciclo de vida, JSON-RPC, tools/resources/prompts, stdio, schemas, annotations, errores, testing y clientes.
- [ ] `docs/project-guidelines.md` en español (este documento).
- [ ] `LICENSE` MIT.
- [ ] Demo con cinco preguntas reales, cada una con su URL:
  - días de vacaciones,
  - cambio de OSDE 260,
  - strikes,
  - votación del servicio de limpieza,
  - trabajo externo fuera de Devecoop.

### 5.5 Definition of done

La v0.1 está terminada cuando una persona distinta del autor puede clonar el repo, clonar la wiki, seguir el README, registrar el servidor en Claude Code u OpenCode, hacer las cinco preguntas de demo y obtener respuestas con citas correctas; y cuando CI está verde.

---

## 6. Decisiones técnicas

| Área | Decisión |
|---|---|
| Repositorio | `https://github.com/Devecoop/mcp` (público) |
| Licencia | MIT |
| Nombre del servidor MCP | `devecoop` |
| Distribución / CLI | `devecoop-mcp` |
| Módulo Python | `devecoop_mcp` |
| Lenguaje | Python 3.12 |
| SDK | `mcp` 2.3.0 (oficial) |
| API del SDK | `from mcp.server.mcpserver import MCPServer` |
| Transporte | stdio |
| Dependency manager | `uv` + `uv.lock` |
| Lint / format | `ruff` |
| Typecheck | `mypy` (estricto en `src/`) |
| Tests | `pytest` + `pytest-asyncio`/`anyio` para el smoke test |
| Índice | SQLite FTS5 en `.cache/wiki_index.sqlite3` (gitignored) |
| Config | `pydantic-settings` + `.env` |
| CI | GitHub Actions |
| Versionado | SemVer; v0.1.0 para el Oráculo |

### 6.1 Configuración de clientes

**Claude Code (CLI):**

```bash
claude mcp add --transport stdio \
  --env WIKI_PATH=/absolute/path/to/wiki.wiki \
  devecoop -- uv run --directory /absolute/path/to/mcp devecoop-mcp
```

**OpenCode:**

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

> Para v0.1 se recomienda clonar el repo y usar `uv run --directory`. `uvx` queda documentado como opción, pero requiere `WIKI_INDEX_PATH` explícito para no depender del cwd.

---

## 7. Roadmap

### v0.2 — Kimai

- Cargar horas en Kimai desde lenguaje natural.
- Reutilizar un módulo `kimai/` con cliente API, modelos y tools.
- Confirmación humana antes de escribir.
- Idempotencia y detección de duplicados.
- Riesgo abierto: identidad bot + zero-config + atribución por usuario. Un token de bot compartido en cada máquina es un problema de seguridad y de atribución; hay que definirlo antes de implementar.

### v0.3 — Protocolo de vacaciones

- Email de pedido a administración.
- Notificación al equipo.
- Carga de días en Kimai.
- Evento en el calendario compartido.
- Estado multi-día y disparo del paso "un día antes".
- Riesgo abierto: un MCP por stdio no es un scheduler; definir si el flujo es orquestado por el agente o por un worker separado.

### Evoluciones posibles

- Búsqueda en historia de Git para minutas borradas/renombradas.
- Embeddings o búsqueda híbrida si el eval muestra que FTS5 no alcanza.
- Transporte HTTP remoto y OAuth para uso compartido.
- `WIKI_EXCLUDE_PATHS` para políticas de datos.
- Observabilidad y métricas de retrieval.

---

## 8. Riesgos y decisiones abiertas

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El clon local queda viejo | Respuestas desactualizadas | `refresh` explícito; `wiki_status` muestra el commit |
| `git pull` falla por cambios locales | Índice no se actualiza | `refresh` aborta sin tocar el índice y reporta el error |
| URL de GitLab no derivable | Citas sin link | Fallback a `path`; `WIKI_BASE_URL` override |
| Ranking FTS5 insuficiente | Respuestas pobres | Eval con preguntas reales antes de agregar embeddings |
| Datos sensibles al proveedor del modelo | Riesgo de privacidad | Documentado; política de datos y exclusiones en una versión futura |
| Bot + zero-config en Kimai | Atribución y seguridad | Resolver antes de v0.2 |
| Scheduler de vacaciones | Un MCP stdio no corre en background | Definir worker o flujo orquestado antes de v0.3 |

---

## 9. Notas de investigación y fuentes

### 9.1 Hechos verificados

- PyPI: `mcp` **2.3.0**, requiere Python `>=3.10`.
- El SDK oficial v2 renombró `FastMCP` a `MCPServer`; el import es `from mcp.server.mcpserver import MCPServer`.
- Claude Code soporta servidores MCP stdio, resources vía `@server:...`, y prompts como comandos (`/server:prompt`).
- OpenCode soporta servidores MCP locales por stdio, resources vía `list_mcp_resources`/`read_mcp_resource`, y prompts como comandos (`/server:prompt`).
- GitLab wiki usa URLs `/-/wikis/<slug>`; las páginas anidadas usan `/` y los espacios se convierten en guiones. Se verificaron URLs reales con respuesta `200`.
- El corpus actual tiene 401 `.md` (721 KB de texto); el repo completo tiene 433 archivos (32 MB con imágenes). La historia tiene 689 paths `.md` únicos.
- SQLite FTS5: build de 48 ms y queries de 1–3 ms sobre el corpus actual.

### 9.2 Fuentes

- PyPI — MCP Python SDK: <https://pypi.org/project/mcp/>
- MCP Python SDK v2.3.0: <https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0>
- MCP specification: <https://modelcontextprotocol.io/specification>
- Claude Code — MCP: <https://code.claude.com/docs/en/mcp>
- OpenCode — MCP servers: <https://opencode.ai/docs/mcp-servers/>
- GitLab — Wiki: <https://docs.gitlab.com/user/project/wiki/>
- GitLab — Wiki-specific Markdown: <https://docs.gitlab.com/user/project/wiki/markdown/>
- SQLite FTS5: <https://www.sqlite.org/fts5.html>

---

## 10. Próximos pasos

- [ ] Scaffold del proyecto: `pyproject.toml`, `src/devecoop_mcp/`, `tests/`, `README.md`, `.gitignore`, `.env.example`, `LICENSE`.
- [ ] Implementar configuración y carga de `.env`.
- [ ] Implementar índice FTS5 y `refresh`.
- [ ] Implementar `wiki_search`, `wiki_read_page`, `wiki_list_pages`, `wiki_status`.
- [ ] Implementar CLI `serve`/`refresh`/`status`.
- [ ] Tests mínimos.
- [ ] GitHub Actions.
- [ ] README y `docs/mcp-concepts.md`.
- [ ] Demo con las cinco preguntas.
