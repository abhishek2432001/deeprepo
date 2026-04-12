# DeepRepo - Local RAG Engine

A production-grade Python library for performing RAG (Retrieval Augmented Generation) on local codebases with **multiple AI provider support**.

## Features

- **Raw Python Implementation**: No heavy frameworks (LangChain/LlamaIndex), no external Vector DBs
- **Multiple AI Providers**: Supports Ollama (local), HuggingFace, OpenAI, Anthropic, and Gemini
- **MCP Server Support**: Integrate with Cursor, Claude Desktop, Antigravity, and other MCP clients
- **Decorator-Based Plugin System**: Easy provider registration and extensibility
- **SQLite-Backed Storage**: Graph, embeddings, wiki pages, and FTS in a single file per branch
- **Code Knowledge Graph**: SQLite-backed dependency graph with blast-radius analysis
- **Hierarchical Wiki Engine**: Auto-generated browsable markdown docs for every file (CodeWiki-style)
- **Smart Query Router**: Intent-based routing that reduces LLM token usage by 5-8x
- **Branch Isolation**: Per-branch caching with copy-on-write from base branches
- **3-Tier Retrieval**: Embeddings → FTS → Graph fallback for resilient search
- **RESTful API**: FastAPI service for easy integration
- **Docker Ready**: Full containerization for deployment

## Quick Start

### Installation

```bash
cd deeprepo_core
pip install -e .
```

See [INSTALLATION.md](INSTALLATION.md) for detailed setup instructions for each provider.

### Basic Usage

```python
from deeprepo import DeepRepoClient

# Initialize with Ollama (FREE, local)
client = DeepRepoClient(provider_name="ollama")

# Or with branch isolation for team workflows
client = DeepRepoClient(
    provider_name="ollama",
    branch_isolation=True,
    base_branches=["main"],
)

# Ingest documents (builds graph + wiki + embeddings)
result = client.ingest("/path/to/your/code")
print(f"Indexed {result['files_scanned']} files, {result['wiki_generated']} wiki pages")

# Query with smart routing (auto-selects optimal context strategy)
response = client.query("How does authentication work?")
print(response['answer'])
print(f"Intent: {response['intent']}, Strategy: {response['strategy']}")
print(f"Sources: {response['sources']}")

# Browse the generated wiki
print(f"Wiki available at: {client.get_wiki_dir()}")
```

## Supported AI Providers

| Provider | Cost | Speed | Best For |
|----------|------|-------|----------|
| **Ollama** | FREE | Fast | Local development, privacy, offline work |
| **HuggingFace** | FREE* | Medium | Cloud-based, no local setup |
| **OpenAI** | Paid | Very Fast | Production, best quality |
| **Anthropic** | Paid | Very Fast | Production, excellent reasoning |
| **Gemini** | FREE* | Medium | Testing, Google ecosystem |

*Free tier with rate limits

### Provider Examples

```python
# Same provider for both embeddings and LLM
# Ollama (Recommended - FREE and unlimited)
client = DeepRepoClient(provider_name="ollama")

# HuggingFace (FREE tier)
client = DeepRepoClient(provider_name="huggingface")

# OpenAI (Paid, best quality)
client = DeepRepoClient(provider_name="openai")

# Anthropic (Paid, excellent reasoning)
# Note: Anthropic doesn't have embeddings API, so use with another provider
client = DeepRepoClient(
    embedding_provider_name="openai",  # Use OpenAI for embeddings
    llm_provider_name="anthropic"     # Use Anthropic for LLM
)

# Gemini (Free tier, limited)
client = DeepRepoClient(provider_name="gemini")

# Mix and match providers
# Example: Use free HuggingFace for embeddings, paid OpenAI for LLM
client = DeepRepoClient(
    embedding_provider_name="huggingface",
    llm_provider_name="openai"
)
```

## Architecture

```
deeprepo_core/
├── src/deeprepo/
│   ├── client.py         # Main facade + branch isolation + freshness model
│   ├── graph.py          # SQLite graph store (nodes, edges, embeddings, wiki, state)
│   ├── graph_builder.py  # Tree-sitter AST parser → graph
│   ├── wiki.py           # Hierarchical wiki engine (CodeWiki-style, dual-write)
│   ├── router.py         # Intent classifier + context strategy selector
│   ├── ingestion.py      # File scanning & chunking
│   ├── interfaces.py     # Abstract base classes
│   ├── registry.py       # Decorator-based registry
│   ├── mcp/              # MCP server for AI assistants
│   │   └── server.py     # 15 MCP tools
│   └── providers/        # Ollama, OpenAI, Anthropic, Gemini, HuggingFace
├── .deeprepo/            # Generated (gitignored)
│   ├── main.db           # SQLite: graph + embeddings + wiki index + state
│   └── main-wiki/        # Browsable markdown wiki files
│       ├── overview.md
│       └── deeprepo/
│           ├── client.md
│           ├── graph.md
│           └── ...
└── docs/
    ├── high-level-design.excalidraw     # HLD process flow diagram
    └── class-interaction-design.excalidraw  # LLD class diagram
```

### Design Patterns

- **Facade Pattern**: `DeepRepoClient` orchestrates graph, wiki, router, and embeddings behind a single API
- **Strategy Pattern**: `LLMProvider` and `EmbeddingProvider` abstract interfaces
- **Registry Pattern**: `@register_llm` decorator for dynamic provider discovery
- **Singleton Pattern**: FastAPI lifespan loads client once at startup
- **Bottom-Up Synthesis**: Wiki pages generated leaves-first, then parents consume children's docs
- **3-Tier Fallback**: Embeddings → FTS → Graph ensures queries work even without embedding models
- **Copy-on-Write**: Branch caches inherit from base branch and delta-update

## MCP Server (AI Assistant Integration)

DeepRepo can be used as an MCP (Model Context Protocol) server, enabling integration with AI assistants like **Cursor**, **Claude Desktop**, and **Antigravity**.

### Install MCP Dependencies

```bash
pip install deeprepo[mcp]
```

### Run the MCP Server

```bash
# Using CLI command
deeprepo-mcp

# Or as Python module
python -m deeprepo.mcp.server
```

### Configure Cursor

Create or edit `~/.cursor/mcp.json`:

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

**Using separate providers:**

```json
{
  "mcpServers": {
    "deeprepo": {
      "command": "python",
      "args": ["-m", "deeprepo.mcp.server"],
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

### Available MCP Tools

| Tool | Phase | Description |
|------|-------|-------------|
| `ingest_codebase` | Core | Ingest a directory (graph + wiki + embeddings) |
| `query_codebase` | Core | Query with RAG |
| `search_similar` | Core | Semantic search without LLM |
| `get_stats` | Core | Knowledge base statistics |
| `clear_history` | Core | Clear conversation history |
| `get_blast_radius` | Graph | Files affected by a change |
| `get_file_skeleton` | Graph | Function/class signatures (~150 tokens) |
| `find_symbol` | Graph | Exact symbol lookup (~50 tokens) |
| `get_wiki_page` | Wiki | Auto-generated file documentation |
| `search_wiki` | Wiki | FTS search across wiki pages |
| `get_repo_overview` | Wiki | High-level repository overview |
| `smart_query` | Router | Intent-aware query with optimal context |
| `explain_routing` | Router | Show routing decision without executing |
| `get_freshness_status` | Branch | Branch + cache staleness info |
| `get_wiki_dir` | Wiki | Path to browsable wiki folder |

### Token Reduction by Query Type

| Query Type | Before (naive RAG) | After (smart routing) | Reduction |
|---|---|---|---|
| "where is X defined" | ~4000 tokens | ~80 tokens | **50x** |
| "what breaks if I change X" | ~4000 tokens | ~250 tokens | **16x** |
| "how does X work" | ~4000 tokens | ~600 tokens | **6.7x** |
| "fix bug in X" | ~4000 tokens | ~900 tokens | **4.4x** |

See [deeprepo_core/src/deeprepo/mcp/README.md](deeprepo_core/src/deeprepo/mcp/README.md) for detailed MCP configuration.

## REST API

Start the FastAPI server:

```bash
export OPENAI_API_KEY=your-key  # or use Ollama (no key needed)
uvicorn web_app.main:app --reload
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/stats` | Get vector store statistics |
| POST | `/ingest` | Ingest documents from a directory |
| POST | `/chat` | Query with RAG |
| POST | `/clear-history` | Clear conversation history |

### API Examples

```bash
# Ingest documents
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/code"}'

# Query
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What does this code do?"}'
```

## Docker Deployment

```bash
docker-compose up --build
```

The service will be available at `http://localhost:8000`.

## Provider Comparison

### Ollama (Recommended for Most Users)
- **100% FREE** and unlimited
- Runs locally (privacy + offline)
- Fast (no network latency)
-  Requires ~4GB disk space
- **Setup**: Install Ollama app, pull models

### HuggingFace
- **FREE** tier (300 requests/hour)
- No local installation
- Latest open-source models
- Rate limits on free tier
- **Setup**: Get free API key

### OpenAI
- Best quality responses
- Very fast and reliable
- Production-ready
- Paid (~$0.001 per query)
- **Setup**: Get API key, add payment method

### Anthropic
- Excellent reasoning and long context
- Very fast and reliable
- Production-ready
- Paid (~$0.003 per query)
- **Setup**: Get API key, add payment method
- **Important**: Anthropic does NOT provide a dedicated embeddings API
- **Recommended**: Use Anthropic for LLM with another provider (OpenAI, HuggingFace) for embeddings

### Gemini
- FREE tier available
- Very limited (15 requests/minute)
- Not recommended for production
- **Setup**: Get free API key

## Configuration

### Environment Variables

| Variable | Description | Required For |
|----------|-------------|--------------|
| `HUGGINGFACE_API_KEY` or `HF_TOKEN` | HuggingFace API token | HuggingFace provider |
| `OPENAI_API_KEY` | OpenAI API key | OpenAI provider |
| `ANTHROPIC_API_KEY` | Anthropic API key | Anthropic provider |
| `GEMINI_API_KEY` | Google Gemini API key | Gemini provider |
| `OLLAMA_MODEL` | Override Ollama LLM model | Ollama provider |
| `OLLAMA_EMBED_MODEL` | Override Ollama embedding model | Ollama provider |
| `OLLAMA_BASE_URL` | Override Ollama server URL | Ollama provider |

### Switching Providers

```python
# Same provider for both embeddings and LLM (backward compatible)
client = DeepRepoClient(
    provider_name="ollama",  # or "huggingface", "openai", "anthropic", "gemini"
)

# Different providers for embeddings and LLM
client = DeepRepoClient(
    embedding_provider_name="openai",    # Provider for embeddings
    llm_provider_name="anthropic",      # Provider for LLM
)

# With Ollama + custom model via environment variables
import os
os.environ["OLLAMA_MODEL"] = "gemma3"           # LLM model
os.environ["OLLAMA_EMBED_MODEL"] = "nomic-embed-text"  # Embedding model
client = DeepRepoClient(provider_name="ollama")
```

Or use environment variables:

```bash
# Single provider (backward compatible)
export LLM_PROVIDER=ollama
python your_script.py

# Separate providers
export EMBEDDING_PROVIDER=openai
export LLM_PROVIDER=anthropic
python your_script.py
```

**Common Use Cases:**
- **Anthropic for LLM**: Since Anthropic doesn't have embeddings, pair it with OpenAI or HuggingFace
- **Cost optimization**: Use free HuggingFace for embeddings, paid OpenAI for LLM
- **Performance**: Use fast OpenAI for embeddings, powerful Anthropic for LLM

## Testing

Professional test suite with unit and integration tests.

### Quick Start

```bash
# Run all unit tests (fast, no API keys needed)
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=deeprepo --cov-report=html

# Run all tests including integration
pytest tests/ -v
```

### Test Structure

- **Unit Tests** (`tests/unit/`) - Fast, isolated, no external dependencies
  - `test_storage.py` - Vector store and cosine similarity
  - `test_ingestion.py` - File scanning and text chunking
  - `test_client.py` - Client interface and initialization

- **Integration Tests** (`tests/integration/`) - End-to-end testing
  - `test_document.py` - Document processing pipeline
  - `test_all_providers.py` - Manual provider verification

### Manual Provider Testing

```bash
# Test specific providers
python tests/integration/test_all_providers.py ollama
python tests/integration/test_all_providers.py huggingface openai
```

See [tests/README.md](tests/README.md) for detailed testing documentation.


## Design Diagrams

The architecture is documented in two Excalidraw diagrams (open with [excalidraw.com](https://excalidraw.com) or the VS Code Excalidraw extension):

- **[High-Level Design](docs/high-level-design.excalidraw)** — Process flow: ingestion pipeline, query pipeline, branch isolation, freshness model, storage layout
- **[Class Interaction Design](docs/class-interaction-design.excalidraw)** — All classes with methods, interaction arrows, storage schema, 15 MCP tools

![Architecture Overview](docs/high-level-design.excalidraw)

## Documentation

- **[INSTALLATION.md](INSTALLATION.md)** - Detailed installation and setup for each provider
- **[PROJECT_SPEC.MD](PROJECT_SPEC.MD)** - Complete project architecture and specifications
- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Detailed implementation roadmap (Phases 1-4)
- **[DEVELOPER_WORKFLOW_GUIDE.md](DEVELOPER_WORKFLOW_GUIDE.md)** - AI-powered workflow automation

## Development

### Adding a New Provider

1. Create a new file in `src/deeprepo/providers/`
2. Implement `EmbeddingProvider` and `LLMProvider` interfaces
3. Use `@register_embedding` and `@register_llm` decorators
4. The provider will be auto-discovered!

Example:

```python
from deeprepo.interfaces import EmbeddingProvider, LLMProvider
from deeprepo.registry import register_embedding, register_llm

@register_embedding("my_provider")
class MyEmbeddingProvider(EmbeddingProvider):
    def embed(self, text: str) -> list[float]:
        # Your implementation
        pass

@register_llm("my_provider")
class MyLLM(LLMProvider):
    def generate(self, prompt: str, context: str = None) -> str:
        # Your implementation
        pass
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Built for developers who want full control over their RAG pipelines**
