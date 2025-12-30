"""OpenAI provider implementation.

Provides LLM and Embedding implementations using OpenAI's API.
"""

import os

from openai import OpenAI

from deeprepo.interfaces import EmbeddingProvider, LLMProvider
from deeprepo.registry import register_embedding, register_llm


@register_embedding("openai")
class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-small.
    
    Requires OPENAI_API_KEY environment variable to be set.
    """
    
    def __init__(self, model: str = "text-embedding-3-small"):
        """Initialize the OpenAI embedding provider.
        
        Args:
            model: OpenAI embedding model to use. Defaults to text-embedding-3-small.
        """
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text.
        
        Args:
            text: The text to embed.
            
        Returns:
            Embedding vector as a list of floats.
        """
        response = self.client.embeddings.create(
            input=text,
            model=self.model
        )
        return response.data[0].embedding
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in one API call.
        
        Args:
            texts: List of texts to embed.
            
        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []
            
        response = self.client.embeddings.create(
            input=texts,
            model=self.model
        )
        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]


@register_llm("openai")
class OpenAILLM(LLMProvider):
    """OpenAI LLM provider using GPT-4o-mini.
    
    Requires OPENAI_API_KEY environment variable to be set.
    """
    
    def __init__(self, model: str = "gpt-4o-mini"):
        """Initialize the OpenAI LLM provider.
        
        Args:
            model: OpenAI model to use. Defaults to gpt-4o-mini.
        """
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
    def generate(
        self, 
        prompt: str, 
        context: str | None = None,
        system_prompt: str | None = None
    ) -> str:
        """Generate a response using OpenAI chat completion.
        
        Args:
            prompt: The user's question.
            context: Optional context from retrieved documents.
            system_prompt: Optional system prompt.
            
        Returns:
            The model's response text.
        """
        messages = []
        
        # Add system prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": "You are a helpful assistant that answers questions based on the provided context. If the context doesn't contain relevant information, say so clearly."
            })
        
        # Build user message with context
        if context:
            user_content = f"Context:\n{context}\n\nQuestion: {prompt}"
        else:
            user_content = prompt
            
        messages.append({"role": "user", "content": user_content})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
        )
        
        return response.choices[0].message.content
