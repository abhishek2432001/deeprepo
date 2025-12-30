# DeepRepo - Local RAG Engine

A production-grade Python library for performing RAG (Retrieval Augmented Generation) on local codebases with **multiple AI provider support**.

## Features

- **Raw Python Implementation**: No heavy frameworks (LangChain/LlamaIndex), no external Vector DBs
- **Multiple AI Providers**: Supports Ollama (local), HuggingFace, OpenAI, and Gemini
- **Decorator-Based Plugin System**: Easy provider registration and extensibility
- **Vector Store**: NumPy-powered cosine similarity with JSON persistence
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

# Ingest documents
result = client.ingest("/path/to/your/code")
print(f"Ingested {result['chunks_processed']} chunks")

# Query with RAG
response = client.query("How does authentication work?")
print(response['answer'])
print(f"Sources: {response['sources']}")
```

## 🤖 Supported AI Providers

| Provider | Cost | Speed | Best For |
|----------|------|-------|----------|
| **Ollama** | FREE | Fast | Local development, privacy, offline work |
| **HuggingFace** | FREE* | Medium | Cloud-based, no local setup |
| **OpenAI** | Paid | Very Fast | Production, best quality |
| **Gemini** | FREE* | Medium | Testing, Google ecosystem |

*Free tier with rate limits

### Provider Examples

```python
# Ollama (Recommended - FREE and unlimited)
client = DeepRepoClient(provider_name="ollama")

# HuggingFace (FREE tier)
client = DeepRepoClient(provider_name="huggingface")

# OpenAI (Paid, best quality)
client = DeepRepoClient(provider_name="openai")

# Gemini (Free tier, limited)
client = DeepRepoClient(provider_name="gemini")
```

## 📊 Architecture

```
deeprepo_core/
├── src/deeprepo/
│   ├── client.py       # Main facade
│   ├── storage.py      # Vector store (JSON + NumPy)
│   ├── ingestion.py    # File scanning & chunking
│   ├── interfaces.py   # Abstract base classes
│   ├── registry.py     # Decorator-based registry
│   └── providers/
│       ├── ollama_v.py      # Ollama (local, FREE)
│       ├── huggingface_v.py # HuggingFace (cloud, FREE)
│       ├── openai_v.py      # OpenAI (paid)
│       └── gemini_v.py      # Gemini (free tier)
```

### Design Patterns

- **Repository Pattern**: `VectorStore` decouples storage from application logic
- **Strategy Pattern**: `LLMProvider` and `EmbeddingProvider` abstract interfaces
- **Registry Pattern**: `@register_llm` decorator for dynamic provider discovery
- **Singleton Pattern**: FastAPI lifespan loads client once at startup

## 🌐 REST API

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

## 🐳 Docker Deployment

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

### Gemini
- FREE tier available
- Very limited (15 requests/minute)
- Not recommended for production
- **Setup**: Get free API key

## 📝 Configuration

### Environment Variables

| Variable | Description | Required For |
|----------|-------------|--------------|
| `HUGGINGFACE_API_KEY` or `HF_TOKEN` | HuggingFace API token | HuggingFace provider |
| `OPENAI_API_KEY` | OpenAI API key | OpenAI provider |
| `GEMINI_API_KEY` | Google Gemini API key | Gemini provider |

### Switching Providers

```python
# Set provider when initializing client
client = DeepRepoClient(
    provider_name="ollama",  # or "huggingface", "openai", "gemini"
    storage_path="vectors.json"
)
```

Or use environment variable:

```bash
export LLM_PROVIDER=ollama  # Default provider
python your_script.py
```

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


## 📚 Documentation

- **[INSTALLATION.md](INSTALLATION.md)** - Detailed installation and setup for each provider
- **[PROJECT_SPEC.MD](PROJECT_SPEC.MD)** - Complete project architecture and specifications

## 🔧 Development

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

## 📄 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 💡 Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Built with ❤️ for developers who want full control over their RAG pipelines**
