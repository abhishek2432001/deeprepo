"""Ollama provider implementation.

Provides LLM and Embedding implementations using Ollama (100% free, local).
No API key required!

Installation:
    Ollama is a separate application that must be installed on your system.
    
    1. Install Ollama:
       - macOS/Linux: https://ollama.ai/download
       - Or via Homebrew: brew install ollama
    
    2. Start Ollama server:
       ollama serve
    
    3. Pull required models:
       ollama pull nomic-embed-text  # For embeddings
       ollama pull llama3.2          # For LLM (or any other model)
    
    4. Use in Python:
       from deeprepo import DeepRepoClient
       client = DeepRepoClient(provider_name="ollama")

Note:
    This provider is completely FREE with unlimited usage. No pip package needed,
    but Ollama must be running as a background service.
"""

import requests
from typing import Optional

from deeprepo.interfaces import EmbeddingProvider, LLMProvider
from deeprepo.registry import register_embedding, register_llm


class OllamaConnectionError(Exception):
    """Raised when Ollama is not accessible."""
    pass


@register_embedding("ollama")
class OllamaEmbedding(EmbeddingProvider):
    """Ollama embedding provider using nomic-embed-text model.
    
    Completely free and runs locally. No API key or pip package required!
    Requires Ollama to be installed and running.
    
    Setup:
        1. Install Ollama: https://ollama.ai/download
        2. Start: ollama serve
        3. Pull model: ollama pull nomic-embed-text
        4. That's it!
    """
    install_hint = (
        "Ollama provider requires Ollama to be installed separately.\n"
        "See: https://ollama.ai/download\n"
        "Then start: ollama serve"
    )
    
    def __init__(
        self, 
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434"
    ):
        """Initialize the Ollama embedding provider.
        
        Args:
            model: Ollama embedding model to use. Default: nomic-embed-text
            base_url: Ollama server URL. Default: http://localhost:11434
            
        Raises:
            OllamaConnectionError: If Ollama is not running or not installed
        """
        self.model = model
        self.base_url = base_url.rstrip('/')
        self._check_connection()
        
    def _check_connection(self):
        """Check if Ollama server is running.
        
        Raises:
            OllamaConnectionError: If Ollama is not accessible with setup instructions
        """
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
                "After setup, Ollama provides UNLIMITED FREE usage!"
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
        """Generate an embedding for a single text.
        
        Args:
            text: The text to embed.
            
        Returns:
            Embedding vector as a list of floats.
            
        Raises:
            OllamaConnectionError: If Ollama is not accessible
            RuntimeError: If the model is not available
        """
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
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed.
            
        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []
        
        # Ollama doesn't have native batch support, so we call individually
        embeddings = []
        for text in texts:
            embeddings.append(self.embed(text))
        return embeddings


@register_llm("ollama")
class OllamaLLM(LLMProvider):
    """Ollama LLM provider.
    
    Completely free and runs locally. No API key or pip package required!
    Requires Ollama to be installed and running.
    
    Setup:
        1. Install Ollama: https://ollama.ai/download
        2. Start: ollama serve
        3. Pull a model: ollama pull llama3.2 (or any other model)
    """
    install_hint = (
        "Ollama provider requires Ollama to be installed separately.\n"
        "See: https://ollama.ai/download\n"
        "Then start: ollama serve"
    )
    
    def __init__(
        self, 
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434"
    ):
        """Initialize the Ollama LLM provider.
        
        Args:
            model: Ollama model to use. Default: llama3.2
                   Other good options: mistral, phi3, gemma2, qwen2.5
            base_url: Ollama server URL. Default: http://localhost:11434
            
        Raises:
            OllamaConnectionError: If Ollama is not running or not installed
        """
        self.model = model
        self.base_url = base_url.rstrip('/')
        self._check_connection()
        
    def _check_connection(self):
        """Check if Ollama server is running.
        
        Raises:
            OllamaConnectionError: If Ollama is not accessible with setup instructions
        """
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
                "After setup, Ollama provides UNLIMITED FREE usage!"
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
        """Generate a response using Ollama.
        
        Args:
            prompt: The user's question.
            context: Optional context from retrieved documents.
            system_prompt: Optional system prompt.
            
        Returns:
            The model's response text.
            
        Raises:
            OllamaConnectionError: If Ollama is not accessible
            RuntimeError: If the model is not available
        """
        # Build the full prompt
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

