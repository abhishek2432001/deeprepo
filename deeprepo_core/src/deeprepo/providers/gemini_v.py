"""Gemini provider implementation.

Provides LLM and Embedding implementations using Google's Gemini API.
"""

import os

import google.generativeai as genai

from deeprepo.interfaces import EmbeddingProvider, LLMProvider
from deeprepo.registry import register_embedding, register_llm


@register_embedding("gemini")
class GeminiEmbedding(EmbeddingProvider):
    """Gemini embedding provider using embedding-001 model.
    
    Requires GEMINI_API_KEY environment variable to be set.
    """
    
    def __init__(self, model: str = "models/embedding-001"):
        """Initialize the Gemini embedding provider.
        
        Args:
            model: Gemini embedding model to use.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        genai.configure(api_key=api_key)
        self.model = model
        
    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text.
        
        Args:
            text: The text to embed.
            
        Returns:
            Embedding vector as a list of floats.
        """
        result = genai.embed_content(
            model=self.model,
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed.
            
        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []
            
        # Gemini API handles batch embedding
        result = genai.embed_content(
            model=self.model,
            content=texts,
            task_type="retrieval_document"
        )
        return result['embedding']


@register_llm("gemini")
class GeminiLLM(LLMProvider):
    """Gemini LLM provider using gemini-1.5-flash.
    
    Requires GEMINI_API_KEY environment variable to be set.
    """
    
    def __init__(self, model: str = "gemini-1.5-flash"):
        """Initialize the Gemini LLM provider.
        
        Args:
            model: Gemini model to use. Defaults to gemini-1.5-flash.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        
    def generate(
        self, 
        prompt: str, 
        context: str | None = None,
        system_prompt: str | None = None
    ) -> str:
        """Generate a response using Gemini.
        
        Args:
            prompt: The user's question.
            context: Optional context from retrieved documents.
            system_prompt: Optional system prompt.
            
        Returns:
            The model's response text.
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
        
        response = self.model.generate_content(full_prompt)
        
        return response.text
