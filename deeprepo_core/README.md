# DeepRepo Core

A production-grade Python library for RAG on local codebases — **code knowledge graph**, **hierarchical wiki engine**, **smart query routing**, and **branch isolation**.

> See the main [README.md](https://github.com/abhishek2432001/deeprepo/blob/main/README.md) for complete documentation.

## Quick Install

```bash
pip install deeprepo

# With MCP server support
pip install deeprepo[mcp]
```

## Quick Start (CLI)

```bash
# Ingest current directory (Ollama, free and local)
deeprepo ingest .

# Browse the auto-generated wiki with in-page chat
deeprepo serve                     # → http://localhost:8080

# Ask questions directly
deeprepo query "how does authentication work?"
deeprepo query "what breaks if I change router.py?"
```

## Quick Start (Python API)

```python
from deeprepo import DeepRepoClient

# Initialize (defaults to Ollama if running, else OpenAI)
client = DeepRepoClient(provider_name="ollama")

# Ingest your code (incremental — unchanged files are skipped)
result = client.ingest("/path/to/your/code")
print(f"Indexed {result['files_scanned']} files, {result['wiki_generated']} wiki pages")

# Query with smart routing
response = client.query("How does authentication work?")
print(response['answer'])
print(f"Intent: {response['intent']}, Strategy: {response['strategy']}")
print(f"Sources: {response['sources']}")    # list of file paths

# Browse the wiki
print(f"Wiki at: {client.get_wiki_dir()}")
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `deeprepo init` | Detect provider setup, print the ingest command |
| `deeprepo ingest [PATH]` | Build graph + wiki + embeddings |
| `deeprepo wiki [PATH]` | Regenerate wiki pages only |
| `deeprepo serve` | Launch wiki viewer + chat at port 8080 |
| `deeprepo query "…"` | Ask a question, get an AI answer |
| `deeprepo status` | Show branch isolation & cache freshness |

## What's Inside

| Module | Purpose |
|--------|---------|
| `client.py` | Main facade — branch isolation, freshness, provider wiring |
| `graph.py` | SQLite store: graph nodes/edges, embeddings, wiki index, state |
| `graph_builder.py` | Tree-sitter AST parser → code knowledge graph |
| `wiki.py` | Hierarchical wiki engine — bottom-up LLM synthesis |
| `router.py` | Intent classifier + 6 context strategy selectors |
| `ingestion.py` | File scanner, chunker, language detection |
| `ui.py` | Wiki viewer (HTTP + mermaid renderer + chat) |
| `mcp/server.py` | 7 focused MCP tools for AI assistants |

## MCP Tools (7 tools)

Connect to Cursor / Claude Desktop as an MCP server:

```bash
deeprepo-mcp     # starts the MCP server on stdio
```

| Tool | Purpose |
|------|---------|
| `ingest_codebase` | Index a repo directory |
| `find_symbol` | Locate a class/function (~50 tokens) |
| `get_file_structure` | File API without reading source (~150 tokens) |
| `explain_file` | Plain-English file explanation (~300 tokens) |
| `find_change_impact` | Blast-radius analysis (~300 tokens) |
| `ask_codebase` | Open-ended question about the code |
| `get_project_overview` | Whole-repo narrative overview |

## Design Diagrams

- **[High-Level Design](../docs/high-level-design.excalidraw)** — Process flow diagram
- **[Class Interaction Design](../docs/class-interaction-design.excalidraw)** — Class relationships

Open with [excalidraw.com](https://excalidraw.com) or the VS Code Excalidraw extension.

## License

MIT License — see LICENSE file for details.
