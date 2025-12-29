"""Abstract interfaces for LLM and Embedding providers.

Defines the Strategy Pattern base classes that allow swapping providers.
"""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    Implement this interface to add support for different embedding
    services (OpenAI, Gemini, local models, etc.).
    """
    
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.
        Args:
            text: The text to embed.
        Returns:
            A list of floats representing the embedding vector.
        """
        pass
    
    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.
        Args:
            texts: List of texts to embed.
        Returns:
            List of embedding vectors.
        """
        pass


class LLMProvider(ABC):
    """Abstract base class for LLM providers.
    
    Implement this interface to add support for different LLM
    services (OpenAI, Gemini, Anthropic, etc.).
    """
    
    @abstractmethod
    def generate(
        self, 
        prompt: str, 
        context: str | None = None,
        system_prompt: str | None = None
    ) -> str:
        """Generate a response from the LLM.
        Args:
            prompt: The user's question or prompt.
            context: Optional context from retrieved documents.
            system_prompt: Optional system prompt to guide behavior.
        Returns:
            The LLM's response as a string.
        """
        pass
