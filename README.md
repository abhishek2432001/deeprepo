# DeepRepo — Local RAG Engine for Codebases

A production-grade Python library for performing RAG (Retrieval Augmented Generation) on local codebases. **No heavy frameworks, no external vector DBs, no cloud required.**

## What It Does

DeepRepo ingests a codebase and builds three things simultaneously:

| Layer | What it stores | Used for |
|---|---|---|
| **Code Knowledge Graph** | Classes, functions, imports, call edges (SQLite) | Symbol lookup, blast-radius analysis |
| **Embeddings + FTS index** | Semantic vectors + full-text search | Relevant code retrieval |
| **Hierarchical Wiki** | Plain-English `.md` files per module | AI explanations, chat context |

A smart **query router** classifies every question and picks the cheapest context strategy, reducing LLM token usage by 5–50x compared to naive RAG.

---

## Features

- **Zero dependencies on heavy frameworks** — pure Python, SQLite-backed
- **Multiple AI providers** — Ollama (free/local), OpenAI, Anthropic, Gemini, HuggingFace
- **CLI-first** — `deeprepo ingest .` / `deeprepo serve` / `deeprepo query "…"`
- **Wiki viewer** — browsable, searchable HTML wiki with in-page chat (`deeprepo serve`)
- **7 focused MCP tools** — drop DeepRepo into Cursor / Claude Desktop as an MCP server
- **Branch isolation** — per-branch SQLite databases with copy-on-write from base branches
- **3-tier retrieval** — Embeddings → FTS → Graph fallback for resilient search
- **Incremental ingestion** — unchanged files are skipped; only deltas re-processed

---

## Quick Start

### 1. Install

```bash
cd deeprepo_core
pip install -e .
```

For MCP server support:
```bash
pip install -e ".[mcp]"
```

### 2. Install Ollama (free, local — recommended)

```bash
# macOS
brew install ollama
ollama serve                          # keep this running

ollama pull nomic-embed-text          # embedding model
ollama pull llama3.1:8b               # LLM
```

### 3. Ingest your codebase

```bash
cd /path/to/your/project
deeprepo ingest .
```

### 4. Browse the wiki

```bash
deeprepo serve                        # opens http://localhost:8080
```

### 5. Ask questions

```bash
deeprepo query "how does authentication work?"
deeprepo query "what breaks if I change auth.py?"
```

---

## CLI Reference

```
deeprepo <command> [options]
```

| Command | What it does |
|---------|-------------|
| `deeprepo init` | Detect provider setup, print the ingest command |
| `deeprepo ingest [PATH]` | Scan repo → build graph + wiki + embeddings |
| `deeprepo wiki [PATH]` | Regenerate wiki pages only (skip re-indexing) |
| `deeprepo serve` | Launch wiki viewer + in-page chat at port 8080 |
| `deeprepo query "QUESTION"` | Ask a question, get an AI answer |
| `deeprepo status` | Show branch isolation & cache freshness |

### Common flags (all commands)

```bash
--llm ollama|openai|anthropic|gemini|huggingface   # LLM provider
--embed ollama|openai|huggingface                  # embedding provider (default: same as --llm)
--branch-isolation                                 # enable per-branch databases
--base-branch main                                 # seed feature-branch cache from main
--wiki-dir .deeprepo/wiki                          # override wiki output directory
```

### ingest flags

```bash
--chunk-size N      # chars per text chunk (default: 1000)
--overlap N         # overlap between chunks (default: 100)
--workers N         # wiki parallel workers (default: 3)
--no-wiki           # skip wiki generation
```

### serve flags

```bash
--port N            # HTTP port (default: 8080)
```

### Examples

```bash
# Ollama (free, fully local)
deeprepo ingest .

# OpenAI embeddings + Anthropic LLM
deeprepo ingest . --embed openai --llm anthropic

# Branch isolation for a feature branch
deeprepo ingest . --branch-isolation --base-branch main

# Serve wiki with chat on a custom port
deeprepo serve --llm openai --port 9000

# Query with specific top-k results
deeprepo query "where is AuthService defined?" --top-k 3
```

---

## Python API

```python
from deeprepo import DeepRepoClient

# Single provider (backward-compatible shorthand)
client = DeepRepoClient(provider_name="ollama")

# Split providers — Anthropic LLM + OpenAI embeddings
client = DeepRepoClient(
    embedding_provider_name="openai",
    llm_provider_name="anthropic",
)

# Branch isolation (team workflow)
client = DeepRepoClient(
    provider_name="ollama",
    branch_isolation=True,
    base_branches=["main"],
)

# Ingest (incremental — unchanged files are skipped)
result = client.ingest("/path/to/your/code")
print(f"Files: {result['files_scanned']}, Wiki pages: {result['wiki_generated']}")

# Query — smart routing selects the cheapest context strategy
response = client.query("How does authentication work?")
print(response['answer'])
print(f"Intent: {response['intent']}, Strategy: {response['strategy']}")
print(f"Sources: {response['sources']}")        # list of file paths

# Browse the generated wiki
print(f"Wiki at: {client.get_wiki_dir()}")
```

### `query()` return shape

```python
{
    "answer":         str,           # LLM-generated answer
    "sources":        list[str],     # file paths used as context
    "intent":         str,           # navigate | impact | explain | debug | review | general
    "strategy":       str,           # e.g. symbol_lookup, blast_radius, wiki_plus_skeleton, …
    "retrieval":      str,           # embeddings | fts | graph
    "token_estimate": int,           # estimated tokens consumed
    "history":        list[dict],    # conversation history (last N exchanges)
}
```

---

## Supported AI Providers

| Provider | Cost | Setup | Best For |
|----------|------|-------|----------|
| **Ollama** | FREE, unlimited | Install app + `ollama pull` | Local dev, privacy, offline |
| **OpenAI** | Paid | `OPENAI_API_KEY` | Production, best quality |
| **Anthropic** | Paid | `ANTHROPIC_API_KEY` | Production, excellent reasoning |
| **Gemini** | Free tier | `GEMINI_API_KEY` | Experimentation |
| **HuggingFace** | Free tier | `HUGGINGFACE_API_KEY` | Cloud embeddings, no GPU needed |

> **Note:** Anthropic has no embeddings API. Pair it with another provider:
> ```python
> client = DeepRepoClient(embedding_provider_name="openai", llm_provider_name="anthropic")
> ```

---

## Architecture

```
deeprepo_core/src/deeprepo/
├── client.py         # Main facade — branch isolation, freshness, provider wiring
├── graph.py          # SQLite store: graph nodes/edges, embeddings, wiki index, state
├── graph_builder.py  # Tree-sitter AST parser → code knowledge graph
├── wiki.py           # Hierarchical wiki engine — bottom-up LLM synthesis
├── router.py         # Intent classifier + 6 context strategy selectors
├── ingestion.py      # File scanner, chunker, language detection
├── interfaces.py     # Abstract base classes (EmbeddingProvider, LLMProvider)
├── registry.py       # @register_embedding / @register_llm decorator system
├── ui.py             # Wiki viewer (HTTP server + mermaid renderer + chat)
├── mcp/
│   └── server.py     # 7 MCP tools for AI assistants (Cursor, Claude Desktop)
└── providers/
    ├── ollama_v.py
    ├── openai_v.py
    ├── anthropic_v.py
    ├── gemini_v.py
    └── huggingface_v.py

.deeprepo/            # Generated (gitignore this)
├── default.db        # SQLite: graph + embeddings + wiki index + state
├── <branch>.db       # Per-branch database when branch_isolation=True
└── wiki/             # Browsable .md wiki files
    ├── overview.md   # Whole-repo narrative overview
    └── *.md          # One page per module
```

### Storage

Everything lives in a **single SQLite file per branch** — no Redis, no Postgres, no Chroma.

| Table | Contents |
|-------|----------|
| `nodes` | Files, classes, functions with metadata |
| `edges` | Import / call relationships between nodes |
| `embeddings` | Float vectors for semantic search |
| `wiki_pages` | Generated wiki markdown (key → content) |
| `wiki_fts` | Full-text search index over wiki |
| `state` | Per-file SHA-256 hashes for incremental updates |

### Design Patterns

- **Facade** — `DeepRepoClient` is the single entry point; internals are hidden
- **Strategy** — `LLMProvider` / `EmbeddingProvider` abstract interfaces; providers are swappable
- **Registry** — `@register_llm("ollama")` decorator auto-registers providers at import time
- **Bottom-up synthesis** — wiki pages generated leaves-first; parent pages consume child summaries
- **3-tier fallback** — Embeddings → FTS → Graph; queries work even when embeddings are cold
- **Copy-on-write branching** — feature branches start from base-branch cache, then delta-update

---

## MCP Server (AI Assistant Integration)

Connect DeepRepo as an MCP server so Cursor, Claude Desktop, or any MCP-compatible AI assistant can call it directly — without ever reading raw files.

### Setup

```bash
pip install deeprepo[mcp]
```

**Cursor** — create `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "deeprepo": {
      "command": "python",
      "args": ["-m", "deeprepo.mcp.server"],
      "env": {
        "LLM_PROVIDER": "ollama"
      }
    }
  }
}
```

**Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "deeprepo": {
      "command": "deeprepo-mcp",
      "env": {
        "EMBEDDING_PROVIDER": "openai",
        "LLM_PROVIDER": "anthropic",
        "OPENAI_API_KEY": "sk-...",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

### Available MCP Tools (7 tools)

| Tool | When to use | Token cost |
|------|-------------|-----------|
| `ingest_codebase` | One-time setup — index a repo directory | — |
| `find_symbol` | "Where is X defined / what line is X on" | ~50 tokens |
| `get_file_structure` | "Show me the API / functions in X" | ~150 tokens |
| `explain_file` | "How does X work / explain X / what does X do" | ~300 tokens |
| `find_change_impact` | "What breaks if I change X" | ~300 tokens |
| `ask_codebase` | Any open-ended question about the code | ~600–2000 tokens |
| `get_project_overview` | "Give me an overview / what does this project do" | ~600 tokens |

### Token Reduction vs Naive RAG

| Query type | Naive RAG | DeepRepo | Reduction |
|---|---|---|---|
| "where is X defined" | ~4 000 tokens | ~80 tokens | **50x** |
| "what breaks if I change X" | ~4 000 tokens | ~300 tokens | **13x** |
| "how does X work" | ~4 000 tokens | ~600 tokens | **7x** |
| "fix the bug in X" | ~4 000 tokens | ~900 tokens | **4x** |

### CLAUDE.md tip

Add this to your project's `CLAUDE.md` so Claude automatically uses DeepRepo:

```markdown
## Code navigation
Before reading any source file directly, use these MCP tools:
- `find_symbol(name)` to locate a class or function
- `get_file_structure(filepath)` to see a file's API without reading it
- `explain_file(filepath)` to understand what a file does
- `find_change_impact(filepath)` before editing any file
- `ask_codebase(question)` for open-ended questions
- `get_project_overview()` at the start of a new session

Only call Read/Grep on a file after the above tools have been tried.
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM provider name |
| `EMBEDDING_PROVIDER` | same as `LLM_PROVIDER` | Embedding provider name |
| `OPENAI_API_KEY` | — | Required for OpenAI |
| `ANTHROPIC_API_KEY` | — | Required for Anthropic |
| `GEMINI_API_KEY` | — | Required for Gemini |
| `HUGGINGFACE_API_KEY` / `HF_TOKEN` | — | Required for HuggingFace |
| `OLLAMA_MODEL` | `llama3.1:8b` | Ollama LLM model name |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TIMEOUT` | `300` | LLM response timeout (seconds) |

---

## Testing

```bash
# Full end-to-end test suite (runs ingest + all checks)
python3 test_deeprepo_flow.py

# Skip ingest, use cached index (faster iteration)
python3 test_deeprepo_flow.py --skip-ingest

# pytest unit tests
pytest tests/unit/ -v

# pytest with coverage
pytest tests/unit/ --cov=deeprepo --cov-report=html
```

The `test_deeprepo_flow.py` script tests all 7 sections end-to-end:
1. Client initialisation & branch flags
2. Ingest (graph + embeddings + wiki)
3. WikiEngine — page generation, caching, repo overview
4. Graph API — skeleton, blast-radius, symbol lookup
5. RAG / Router — intent classification, query execution
6. CLI commands — all subcommands + help
7. Branch isolation flag combinations

---

## Adding a New Provider

1. Create `src/deeprepo/providers/myprovider.py`
2. Implement `EmbeddingProvider` and/or `LLMProvider` interfaces
3. Decorate with `@register_embedding("myprovider")` / `@register_llm("myprovider")`
4. Auto-discovered at import time — no other changes needed

```python
from deeprepo.interfaces import EmbeddingProvider, LLMProvider
from deeprepo.registry import register_embedding, register_llm

@register_embedding("myprovider")
class MyEmbeddingProvider(EmbeddingProvider):
    def embed(self, text: str) -> list[float]:
        ...  # return a list of floats

@register_llm("myprovider")
class MyLLMProvider(LLMProvider):
    def generate(self, prompt: str, context: str | None = None) -> str:
        ...  # return generated text
```

---

## Documentation

- **[DEVELOPER_WORKFLOW_GUIDE.md](DEVELOPER_WORKFLOW_GUIDE.md)** — daily dev workflows and automation recipes
- **[deeprepo_core/README.md](deeprepo_core/README.md)** — package README (PyPI)
- **[docs/high-level-design.excalidraw](docs/high-level-design.excalidraw)** — process flow diagram
- **[docs/class-interaction-design.excalidraw](docs/class-interaction-design.excalidraw)** — class diagram

---

## License

MIT License — see LICENSE file for details.

---

*Built for developers who want full control over their RAG pipelines.*
