# Tests

Professional test suite for the DeepRepo library.

## Structure

```
tests/
├── conftest.py              # Shared pytest fixtures and configuration
├── unit/                    # Unit tests (fast, no external dependencies)
│   ├── test_storage.py      # Vector store tests
│   ├── test_ingestion.py    # Text processing tests
│   └── test_client.py       # Client interface tests
├── integration/             # Integration tests (slower, may use real APIs)
│   ├── test_document.py     # End-to-end document processing
│   └── test_all_providers.py # Manual provider verification
└── fixtures/                # Test data files
    ├── shopping_cart.py     # Sample Python code
    └── cart.py              # Minimal code sample
```

## Running Tests

### Run All Unit Tests (Recommended for CI/CD)

```bash
# From project root
pytest tests/unit/ -v

# With coverage
pytest tests/unit/ --cov=deeprepo --cov-report=html
```

### Run Specific Test Files

```bash
# Test storage module
pytest tests/unit/test_storage.py -v

# Test ingestion module
pytest tests/unit/test_ingestion.py -v

# Test client module
pytest tests/unit/test_client.py -v
```

### Run Integration Tests (Requires Provider Setup)

```bash
# Manual provider testing
python tests/integration/test_all_providers.py ollama

# Document integration test
pytest tests/integration/test_document.py -v
```

## Test Categories

### Unit Tests (`tests/unit/`)
- **Fast**: Run in < 5 seconds
- **Isolated**: No external dependencies or API calls
- **Mocked**: Use mocks for external services
- **Deterministic**: Same result every time

**Included:**
- `test_storage.py` - Vector math and storage operations
- `test_ingestion.py` - File scanning and text chunking
- `test_client.py` - Client initialization and methods

### Integration Tests (`tests/integration/`)
- **Slower**: May take 10-60 seconds
- **Real APIs**: May call actual AI providers
- **Manual**: Often run manually, not in CI/CD

**Included:**
- `test_all_providers.py` - Comprehensive provider testing (manual)
- `test_document.py` - End-to-end document processing

## Prerequisites

### For Unit Tests
```bash
pip install pytest pytest-cov
```

No API keys or external services needed!

### For Integration Tests

**Ollama** (if testing Ollama):
```bash
ollama serve
ollama pull nomic-embed-text
ollama pull llama3.2
```

**HuggingFace** (if testing HuggingFace):
```bash
export HUGGINGFACE_API_KEY="hf_your_token"
```

**OpenAI** (if testing OpenAI):
```bash
export OPENAI_API_KEY="sk-your_key"
```

## Continuous Integration

For CI/CD pipelines, run only unit tests:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    pip install pytest pytest-cov
    pytest tests/unit/ -v --cov=deeprepo
```

Integration tests should be run manually or in a separate workflow with proper API credentials.

## Writing New Tests

### Unit Test Template

```python
"""Unit tests for module_name."""

import pytest
from deeprepo.module import function_to_test


class TestFunctionName:
    """Test function_name functionality."""
    
    def test_basic_case(self):
        """Should handle basic input correctly."""
        result = function_to_test("input")
        assert result == "expected"
    
    def test_edge_case(self):
        """Should handle edge case."""
        result = function_to_test("")
        assert result is None
```

### Using Fixtures

```python
def test_with_temp_storage(temp_storage, sample_chunks):
    """Use shared fixtures from conftest.py."""
    store = VectorStore(temp_storage)
    store.save(sample_chunks)
    assert len(store.chunks) == len(sample_chunks)
```

## Test Coverage

Aim for >80% code coverage on core modules:
- `storage.py` - Vector operations
- `ingestion.py` - File processing
- `client.py` - Public API

Provider modules (`providers/*.py`) can have lower coverage as they often require live API keys.

## Performance Benchmarks

Expected test run times:

| Test Suite | Tests | Time | Notes |
|------------|-------|------|-------|
| Unit tests | ~20 | < 5s | Fast, no external deps |
| Integration | ~3 | 30-60s | Depends on provider speed |

## Troubleshooting

### Import Errors

```bash
# Install package in development mode
cd deeprepo_core
pip install -e .
```

### Missing Fixtures

Make sure `conftest.py` is in the `tests/` directory. Pytest auto-discovers fixtures from there.

### Integration Test Failures

Check provider setup:
```bash
./setup_providers.sh
```

See [INSTALLATION.md](../INSTALLATION.md) for provider configuration.

## Best Practices

1. **Keep unit tests fast** - No network calls, no file I/O (use temp dirs)
2. **Use fixtures** - Share common setup via conftest.py
3. **Test edge cases** - Empty inputs, None values, errors
4. **Clear names** - Test names should describe what they test
5. **One assertion focus** - Each test should primarily test one thing
6. **Arrange-Act-Assert** - Clear test structure

## Documentation

Each test file should have:
- Module docstring explaining what's tested
- Class docstrings for test groups
- Function docstrings for each test case

Good test names are self-documenting:
- `test_scan_ignores_git_directory`
- `test_scan_1` not good

---

For more information, see the main [README.md](../README.md) and [INSTALLATION.md](../INSTALLATION.md).
