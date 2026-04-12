"""Ollama embedding and LLM providers (local, free)."""

import requests
from typing import Optional

from deeprepo.interfaces import EmbeddingProvider, LLMProvider
from deeprepo.registry import register_embedding, register_llm


class OllamaConnectionError(Exception):
    """Raised when Ollama is not accessible."""
    pass


@register_embedding("ollama")
class OllamaEmbedding(EmbeddingProvider):
    """Ollama embedding provider (requires Ollama running locally)."""
    install_hint = (
        "Ollama provider requires Ollama to be installed separately.\n"
        "See: https://ollama.ai/download\n"
        "Then start: ollama serve"
    )
    
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
    ):
        """Initialize with optional model and base_url overrides.

        Raises:
            OllamaConnectionError: If Ollama is not running.
        """
        import os
        self.model = model or os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip('/')
        self._check_connection()
        
    def _check_connection(self):
        """Verify Ollama server is reachable."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}\n\n"
                "Ollama is not running. Please:\n"
                "1. Install Ollama: https://ollama.ai/download\n"
                "2. Start the server: ollama serve\n"
                "3. Pull embedding model: ollama pull nomic-embed-text\n"
                "4. Pull LLM model: ollama pull llama3.2\n\n"
                "After setup, Ollama provides unlimited free usage."
            )
        except requests.exceptions.Timeout:
            raise OllamaConnectionError(
                f"Ollama server at {self.base_url} is not responding (timeout)\n"
                "Make sure Ollama is running: ollama serve"
            )
        except requests.exceptions.RequestException as e:
            raise OllamaConnectionError(
                f"Error connecting to Ollama at {self.base_url}: {e}\n"
                "Install Ollama: https://ollama.ai/download"
            )
        
    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for text."""
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                raise RuntimeError(
                    f"Model '{self.model}' not found in Ollama.\n"
                    f"Please pull the model: ollama pull {self.model}"
                )
            raise
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts (sequential)."""
        if not texts:
            return []
        
        embeddings = []
        for text in texts:
            embeddings.append(self.embed(text))
        return embeddings


@register_llm("ollama")
class OllamaLLM(LLMProvider):
    """Ollama LLM provider (requires Ollama running locally)."""
    install_hint = (
        "Ollama provider requires Ollama to be installed separately.\n"
        "See: https://ollama.ai/download\n"
        "Then start: ollama serve"
    )
    
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
    ):
        """Initialize with optional model and base_url overrides.

        Raises:
            OllamaConnectionError: If Ollama is not running.
        """
        import os
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.2")
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip('/')
        self._check_connection()
        
    def _check_connection(self):
        """Verify Ollama server is reachable."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}\n\n"
                "Ollama is not running. Please:\n"
                "1. Install Ollama: https://ollama.ai/download\n"
                "2. Start the server: ollama serve\n"
                "3. Pull LLM model: ollama pull llama3.2\n"
                "4. Pull embedding model: ollama pull nomic-embed-text\n\n"
                "After setup, Ollama provides unlimited free usage."
            )
        except requests.exceptions.Timeout:
            raise OllamaConnectionError(
                f"Ollama server at {self.base_url} is not responding (timeout)\n"
                "Make sure Ollama is running: ollama serve"
            )
        except requests.exceptions.RequestException as e:
            raise OllamaConnectionError(
                f"Error connecting to Ollama at {self.base_url}: {e}\n"
                "Install Ollama: https://ollama.ai/download"
            )
        
    def generate(
        self, 
        prompt: str, 
        context: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate a response using Ollama."""
        parts = []
        
        if system_prompt:
            parts.append(system_prompt)
        else:
            parts.append(
                "You are a helpful assistant that answers questions based on the provided context. "
                "If the context doesn't contain relevant information, say so clearly."
            )
        
        if context:
            parts.append(f"\nContext:\n{context}")
            
        parts.append(f"\nQuestion: {prompt}")
        
        full_prompt = "\n".join(parts)
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False
                },
                timeout=60
            )
            response.raise_for_status()
            
            return response.json()["response"]
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                raise RuntimeError(
                    f"Model '{self.model}' not found in Ollama.\n"
                    f"Please pull the model: ollama pull {self.model}\n\n"
                    f"Popular models: llama3.2, mistral, phi3, gemma2"
                )
            raise

