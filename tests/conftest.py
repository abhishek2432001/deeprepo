"""Test configuration and shared fixtures for pytest."""

import os
import tempfile
from pathlib import Path
import pytest


@pytest.fixture
def temp_storage():
    """Provide a temporary storage path for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_vectors.json"


@pytest.fixture
def sample_chunks():
    """Provide sample chunks for testing."""
    return [
        {
            "text": "DeepRepo is a local RAG engine for code.",
            "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
            "metadata": {"filepath": "README.md", "chunk_index": 0}
        },
        {
            "text": "It supports multiple AI providers including Ollama.",
            "embedding": [0.2, 0.3, 0.4, 0.5, 0.6],
            "metadata": {"filepath": "README.md", "chunk_index": 1}
        },
        {
            "text": "Vector storage uses NumPy for cosine similarity.",
            "embedding": [0.3, 0.4, 0.5, 0.6, 0.7],
            "metadata": {"filepath": "docs/arch.md", "chunk_index": 0}
        }
    ]


@pytest.fixture
def sample_code_file(tmp_path):
    """Create a temporary Python file for testing."""
    code = '''"""Sample module for testing."""

def hello_world():
    """Print hello world."""
    print("Hello, World!")

class Calculator:
    """Simple calculator class."""
    
    def add(self, a, b):
        """Add two numbers."""
        return a + b
'''
    file_path = tmp_path / "sample.py"
    file_path.write_text(code)
    return file_path


@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables for consistent testing."""
    # Save original env vars
    original_env = {}
    env_vars = ["LLM_PROVIDER", "OPENAI_API_KEY", "GEMINI_API_KEY", 
                "HUGGINGFACE_API_KEY", "HF_TOKEN"]
    
    for var in env_vars:
        if var in os.environ:
            original_env[var] = os.environ[var]
    
    yield
    
    # Restore original env vars
    for var in env_vars:
        if var in original_env:
            os.environ[var] = original_env[var]
        elif var in os.environ:
            del os.environ[var]
