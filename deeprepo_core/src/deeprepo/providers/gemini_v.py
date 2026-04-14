"""Gemini provider implementation.

Provides LLM and Embedding implementations using Google's Gemini API.
"""

import os

from google import genai
from google.genai import types

from deeprepo.interfaces import EmbeddingProvider, LLMProvider
from deeprepo.registry import register_embedding, register_llm


@register_embedding("gemini")
class GeminiEmbedding(EmbeddingProvider):
    """Gemini embedding provider using text-embedding-004 model.
    
    Requires GEMINI_API_KEY environment variable to be set.
    """
    install_hint = "pip install deeprepo[gemini]"
    package_requirement = "google-genai"
    
    def __init__(self, model: str = "text-embedding-004"):
        """Initialize the Gemini embedding provider."""
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        
    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text."""
        result = self.client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        return result.embeddings[0].values
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []
            
        result = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        return [emb.values for emb in result.embeddings]


@register_llm("gemini")
class GeminiLLM(LLMProvider):
    """Gemini LLM provider using gemini-2.5-flash.
    
    Requires GEMINI_API_KEY environment variable to be set.
    """
    install_hint = "pip install deeprepo[gemini]"
    package_requirement = "google-genai"
    
    def __init__(self, model: str = "gemini-2.5-flash"):
        """Initialize the Gemini LLM provider."""
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        
    def generate(
        self, 
        prompt: str, 
        context: str | None = None,
        system_prompt: str | None = None
    ) -> str:
        """Generate a response using Gemini."""
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
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
        )
        
        return response.text
