# DeepRepo - Local RAG Engine

A production-grade Python library for performing RAG (Retrieval Augmented Generation) on local codebases.

## Features

- **Raw Python Implementation**: No heavy frameworks (LangChain/LlamaIndex), no external Vector DBs
- **Plug-and-Play Providers**: Supports OpenAI and Gemini with decorator-based registration
- **Vector Store**: NumPy-powered cosine similarity with JSON persistence
- **RESTful API**: FastAPI service for easy integration
- **Docker Ready**: Full containerization for deployment

## Installation

### From Source

```bash
cd deeprepo_core
pip install -e .
```

### With Docker

```bash
docker-compose up --build
```

## Quick Start

### Python Library

```python
from deeprepo import DeepRepoClient

# Initialize client (uses OPENAI_API_KEY env var by default)
client = DeepRepoClient()

# Ingest a codebase
result = client.ingest("/path/to/your/code")
print(f"Ingested {result['chunks_processed']} chunks from {result['files_scanned']} files")

# Query with RAG
response = client.query("How does the authentication work?")
print(response['answer'])
print(f"Sources: {response['sources']}")
```

### REST API

```bash
# Start the server
export OPENAI_API_KEY=your-key-here
uvicorn web_app.main:app --reload

# Ingest documents
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/code"}'

# Query
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What does this code do?"}'
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Provider to use (`openai` or `gemini`) | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | Required if using OpenAI |
| `GEMINI_API_KEY` | Google Gemini API key | Required if using Gemini |

### Using Gemini Instead of OpenAI

```bash
export LLM_PROVIDER=gemini
export GEMINI_API_KEY=your-gemini-key
```

## Architecture

```
deeprepo_core/
├── src/deeprepo/
│   ├── client.py       # Main facade (DeepRepoClient)
│   ├── storage.py      # VectorStore (JSON + NumPy)
│   ├── ingestion.py    # File scanning & chunking
│   ├── interfaces.py   # Abstract base classes
│   ├── registry.py     # Decorator-based registry
│   └── providers/
│       ├── openai_v.py # OpenAI implementation
│       └── gemini_v.py # Gemini implementation
```

### Design Patterns

- **Repository Pattern**: `VectorStore` decouples storage from application logic
- **Strategy Pattern**: `LLMProvider` and `EmbeddingProvider` abstract interfaces
- **Registry Pattern**: `@register_llm` decorator for dynamic provider discovery
- **Singleton Pattern**: FastAPI lifespan loads client once at startup

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/stats` | Get vector store statistics |
| POST | `/ingest` | Ingest documents from a directory |
| POST | `/chat` | Query with RAG |
| POST | `/clear-history` | Clear conversation history |

## License

MIT
