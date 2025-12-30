"""Anthropic provider implementation.

Provides LLM and Embedding implementations using Anthropic's API.
"""

import os

from anthropic import Anthropic

from deeprepo.interfaces import EmbeddingProvider, LLMProvider
from deeprepo.registry import register_embedding, register_llm


@register_embedding("anthropic")
class AnthropicEmbedding(EmbeddingProvider):
    """Anthropic embedding provider.
    
    Note: Anthropic does not currently provide a dedicated embeddings API.
    This provider uses Claude models to generate embeddings via text generation.
    For production use, consider using Anthropic for LLM and another provider (e.g., OpenAI) for embeddings.
    
    Requires ANTHROPIC_API_KEY environment variable to be set.
    """
    install_hint = "pip install deeprepo[anthropic]"
    package_requirement = "anthropic"
    
    def __init__(self, model: str = "claude-3-haiku-20240307"):
        """Initialize the Anthropic embedding provider.
        
        Args:
            model: Claude model to use for generating embeddings.
                   Note: This is a workaround as Anthropic doesn't have dedicated embeddings.
                   Consider using a different provider for embeddings.
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self.client = Anthropic(api_key=api_key)
        self.model = model
        
    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text.
        
        Note: Anthropic doesn't have a native embeddings API, so this uses
        a workaround. For production, use Anthropic for LLM and another provider for embeddings.
        
        Args:
            text: The text to embed.
            
        Returns:
            Embedding vector as a list of floats.
        """
        # Anthropic doesn't have a native embeddings endpoint
        # This is a placeholder implementation
        # In practice, users should use Anthropic for LLM and another provider for embeddings
        raise NotImplementedError(
            "Anthropic does not provide a dedicated embeddings API. "
            "Please use Anthropic for LLM queries and another provider (e.g., OpenAI, HuggingFace) for embeddings. "
            "Example: DeepRepoClient(provider_name='anthropic') for LLM with a separate embedding provider."
        )
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed.
            
        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []
        
        # Same limitation as single embed
        raise NotImplementedError(
            "Anthropic does not provide a dedicated embeddings API. "
            "Please use Anthropic for LLM queries and another provider for embeddings."
        )


@register_llm("anthropic")
class AnthropicLLM(LLMProvider):
    """Anthropic LLM provider using Claude models.
    
    Requires ANTHROPIC_API_KEY environment variable to be set.
    """
    install_hint = "pip install deeprepo[anthropic]"
    package_requirement = "anthropic"
    
    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        """Initialize the Anthropic LLM provider.
        
        Args:
            model: Claude model to use. Defaults to claude-3-5-sonnet-20241022.
                   Other options: claude-3-opus-20240229, claude-3-sonnet-20240229,
                   claude-3-haiku-20240307, claude-3-5-sonnet-20241022
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self.client = Anthropic(api_key=api_key)
        self.model = model
        
    def generate(
        self, 
        prompt: str, 
        context: str | None = None,
        system_prompt: str | None = None
    ) -> str:
        """Generate a response using Anthropic Claude.
        
        Args:
            prompt: The user's question.
            context: Optional context from retrieved documents.
            system_prompt: Optional system prompt.
            
        Returns:
            The model's response text.
        """
        messages = []
        
        # Build user message with context
        if context:
            user_content = f"Context:\n{context}\n\nQuestion: {prompt}"
        else:
            user_content = prompt
            
        messages.append({"role": "user", "content": user_content})
        
        # Set system prompt
        if not system_prompt:
            system_prompt = (
                "You are a helpful assistant that answers questions based on the provided context. "
                "If the context doesn't contain relevant information, say so clearly."
            )
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )
        
        return response.content[0].text

