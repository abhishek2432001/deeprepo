# DeepRepo Core

A production-grade Python library for RAG on local codebases with **code knowledge graph**, **hierarchical wiki engine**, **smart query routing**, and **branch isolation**.

> See the main [README.md](https://github.com/abhishek2432001/deeprepo/blob/main/README.md) for complete documentation.

## Quick Install

```bash
pip install deeprepo
```

## Quick Start

```python
from deeprepo import DeepRepoClient

# Initialize with Ollama (FREE, local)
client = DeepRepoClient(provider_name="ollama")

# Ingest your code (builds graph + wiki + embeddings)
result = client.ingest("/path/to/your/code")
print(f"Indexed {result['files_scanned']} files, {result['wiki_generated']} wiki pages")

# Query with smart routing
response = client.query("How does authentication work?")
print(response['answer'])

# Browse the auto-generated wiki
print(f"Wiki at: {client.get_wiki_dir()}")
```

## What's Inside

| Component | Purpose |
|---|---|
| `client.py` | Main facade + branch isolation + freshness model |
| `graph.py` | SQLite store: graph, embeddings, wiki index, state |
| `graph_builder.py` | Tree-sitter AST parser → code graph |
| `wiki.py` | Hierarchical wiki engine (browsable .md files + SQLite) |
| `router.py` | Intent classifier + 6 context strategies |
| `ingestion.py` | File scanning & chunking |
| `mcp/server.py` | 15 MCP tools for AI assistants |

## Design Diagrams

- **[High-Level Design](../docs/high-level-design.excalidraw)** — Process flow diagram
- **[Class Interaction Design](../docs/class-interaction-design.excalidraw)** — Class relationships

Open with [excalidraw.com](https://excalidraw.com) or the VS Code Excalidraw extension.

## License

MIT License - see LICENSE file for details.
