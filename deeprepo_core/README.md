# DeepRepo

A production-grade Python library for performing RAG (Retrieval Augmented Generation) on local codebases with **multiple AI provider support**.

> See the main [README.md](../README.md) in the repository root for complete documentation.

## Quick Install

```bash
pip install deeprepo
```

## Quick Start

```python
from deeprepo import DeepRepoClient

# Initialize with Ollama (FREE, local)
client = DeepRepoClient(provider_name="ollama")

# Ingest your code
client.ingest("/path/to/your/code")

# Query with RAG
response = client.query("How does authentication work?")
print(response['answer'])
```

## Documentation

For full documentation, visit: https://github.com/yourusername/deeprepo

## License

MIT License - see LICENSE file for details.
