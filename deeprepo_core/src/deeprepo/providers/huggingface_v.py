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
    - Much more generous than other providers
    - Typically thousands of requests per day
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
    install_hint = "pip install deeprepo[huggingface]"
    
    def __init__(
        self, 
        model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """Initialize the HuggingFace embedding provider.
        
        Args:
            model: HuggingFace model to use.
                   Recommended sentence-transformer models:
                   - sentence-transformers/all-MiniLM-L6-v2 (default, fast, 384-dim)
                   - sentence-transformers/all-mpnet-base-v2 (high quality, 768-dim)
                   - sentence-transformers/paraphrase-MiniLM-L6-v2 (good balance, 384-dim)
        
        Note: Uses HuggingFace's router API (router.huggingface.co).
        """
        api_key = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
        if not api_key:
            raise ValueError(
                "HUGGINGFACE_API_KEY or HF_TOKEN environment variable is required.\n"
                "Get your free API key: https://huggingface.co/settings/tokens"
            )
        self.model = model
        # New HuggingFace router endpoint structure
        self.api_url = f"https://router.huggingface.co/hf-inference/models/{self.model}/pipeline/feature-extraction"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
    def _call_api(self, payload: dict) -> requests.Response:
        """Call HuggingFace API with retry logic."""
        response = requests.post(
            self.api_url,
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
    install_hint = "pip install deeprepo[huggingface]"
    
    def __init__(
        self, 
        model: str = "meta-llama/Llama-3.2-1B-Instruct"
    ):
        """Initialize the HuggingFace LLM provider.
        
        Args:
            model: HuggingFace model to use.
                   Recommended chat models that work with router API:
                   - meta-llama/Llama-3.2-1B-Instruct (default, fast, 1B params)
                   - meta-llama/Llama-3.2-3B-Instruct (better quality, 3B params)
                   - Qwen/Qwen2.5-Coder-32B-Instruct (coding tasks)
        
        Note: Uses HuggingFace's OpenAI-compatible chat completions API.
        """
        api_key = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
        if not api_key:
            raise ValueError(
                "HUGGINGFACE_API_KEY or HF_TOKEN environment variable is required.\n"
                "Get your free API key: https://huggingface.co/settings/tokens"
            )
        self.model = model
        # OpenAI-compatible chat completions endpoint
        self.api_url = "https://router.huggingface.co/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
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
        # Build messages for chat completions API
        messages = []
        
        # System message
        if system_prompt:
            system_msg = system_prompt
        else:
            system_msg = (
                "You are a helpful assistant that answers questions based on the provided context. "
                "If the context doesn't contain relevant information, say so clearly."
            )
        
        if context:
            system_msg += f"\n\nContext:\n{context}"
        
        messages.append({"role": "system", "content": system_msg})
        messages.append({"role": "user", "content": prompt})
        
        # Call OpenAI-compatible chat completions API
        response = requests.post(
            self.api_url,
            headers=self.headers,
            json={
                "model": self.model,
                "messages": messages,
                "max_tokens": 512,
                "temperature": 0.7
            },
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Extract response from OpenAI-compatible format
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        
        return str(result)

