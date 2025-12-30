"""HuggingFace provider implementation.

Provides LLM and Embedding implementations using HuggingFace's FREE Inference API.
Much more generous rate limits than Gemini free tier!

Installation:
    pip install deeprepo[huggingface]
    # or just: pip install deeprepo (requests is in core dependencies)

Setup:
    1. Get free API key: https://huggingface.co/settings/tokens
    2. Set environment variable:
       export HUGGINGFACE_API_KEY=hf_your_token_here
    3. Use in Python:
       from deeprepo import DeepRepoClient
       client = DeepRepoClient(provider_name="huggingface")

Rate Limits (FREE tier):
    - Much more generous than Gemini
    - Typically thousands of requests per day
    - No credit card required
"""

import os
import requests
from typing import Optional

from deeprepo.interfaces import EmbeddingProvider, LLMProvider
from deeprepo.registry import register_embedding, register_llm


@register_embedding("huggingface")
class HuggingFaceEmbedding(EmbeddingProvider):
    """HuggingFace embedding provider using sentence-transformers.
    
    Uses HuggingFace's FREE Inference API with generous rate limits!
    
    Setup:
        1. Get free API key: https://huggingface.co/settings/tokens
        2. Set: export HUGGINGFACE_API_KEY=your_key_here
    
    Rate Limits (FREE tier):
        - Much more generous than Gemini
        - Typically thousands of requests per day
    """
    
    def __init__(
        self, 
        model: str = "sentence-transformers/all-MiniLM-L6-v2",
        api_url: str = "https://api-inference.huggingface.co/pipeline/feature-extraction"
    ):
        """Initialize the HuggingFace embedding provider.
        
        Args:
            model: HuggingFace model to use
            api_url: API endpoint
        """
        api_key = os.environ.get("HUGGINGFACE_API_KEY")
        if not api_key:
            raise ValueError(
                "HUGGINGFACE_API_KEY environment variable is required.\n"
                "Get your free API key: https://huggingface.co/settings/tokens"
            )
        self.model = model
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {api_key}"}
        
    def _call_api(self, payload: dict) -> requests.Response:
        """Call HuggingFace API with retry logic."""
        response = requests.post(
            f"{self.api_url}/{self.model}",
            headers=self.headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response
        
    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text.
        
        Args:
            text: The text to embed.
            
        Returns:
            Embedding vector as a list of floats.
        """
        response = self._call_api({"inputs": text})
        embedding = response.json()
        
        # Handle different response formats
        if isinstance(embedding, list):
            if isinstance(embedding[0], list):
                return embedding[0]  # Batch format
            return embedding
        return embedding
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed.
            
        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []
        
        # HuggingFace API supports batch processing
        response = self._call_api({"inputs": texts})
        embeddings = response.json()
        
        # Ensure we return list of embeddings
        if isinstance(embeddings, list) and len(embeddings) > 0:
            if isinstance(embeddings[0], list):
                if isinstance(embeddings[0][0], float):
                    return embeddings
        
        return embeddings


@register_llm("huggingface")
class HuggingFaceLLM(LLMProvider):
    """HuggingFace LLM provider using Inference API.
    
    Uses HuggingFace's FREE Inference API with generous rate limits!
    
    Setup:
        1. Get free API key: https://huggingface.co/settings/tokens
        2. Set: export HUGGINGFACE_API_KEY=your_key_here
    """
    
    def __init__(
        self, 
        model: str = "mistralai/Mistral-7B-Instruct-v0.2"
    ):
        """Initialize the HuggingFace LLM provider.
        
        Args:
            model: HuggingFace model to use
                   Good free options:
                   - mistralai/Mistral-7B-Instruct-v0.2
                   - google/flan-t5-large
                   - facebook/opt-1.3b
        """
        api_key = os.environ.get("HUGGINGFACE_API_KEY")
        if not api_key:
            raise ValueError(
                "HUGGINGFACE_API_KEY environment variable is required.\n"
                "Get your free API key: https://huggingface.co/settings/tokens"
            )
        self.model = model
        self.api_url = f"https://api-inference.huggingface.co/models/{model}"
        self.headers = {"Authorization": f"Bearer {api_key}"}
        
    def generate(
        self, 
        prompt: str, 
        context: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate a response using HuggingFace.
        
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
        
        # Call API
        response = requests.post(
            self.api_url,
            headers=self.headers,
            json={
                "inputs": full_prompt,
                "parameters": {
                    "max_new_tokens": 512,
                    "temperature": 0.7,
                    "return_full_text": False
                }
            },
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Extract text from response
        if isinstance(result, list) and len(result) > 0:
            if "generated_text" in result[0]:
                return result[0]["generated_text"]
            return str(result[0])
        
        return str(result)

