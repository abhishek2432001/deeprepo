"""
Registry Pattern for dynamic provider discovery.
Provides decorators for registering LLM and embedding providers
and auto-discovery of provider modules.
"""

import importlib
import pkgutil
from typing import Type

from deeprepo.interfaces import EmbeddingProvider, LLMProvider


# Global registries for providers
LLM_REGISTRY: dict[str, Type[LLMProvider]] = {}
EMBEDDING_REGISTRY: dict[str, Type[EmbeddingProvider]] = {}


def register_llm(name: str):
    """Decorator to register an LLM provider class.
    Usage:
        @register_llm("openai")
        class OpenAILLM(LLMProvider):    
    Args:
        name: The name to register the provider under (e.g., "openai", "gemini").
    Returns:
        Decorator function that registers the class.
    """
    def decorator(cls: Type[LLMProvider]) -> Type[LLMProvider]:
        LLM_REGISTRY[name] = cls
        return cls
    return decorator


def register_embedding(name: str):
    """Decorator to register an embedding provider class.
    Usage:
        @register_embedding("openai")
        class OpenAIEmbedding(EmbeddingProvider):    
    Args:
        name: The name to register the provider under (e.g., "openai", "gemini").
    Returns:
        Decorator function that registers the class.
    """
    def decorator(cls: Type[EmbeddingProvider]) -> Type[EmbeddingProvider]:
        EMBEDDING_REGISTRY[name] = cls
        return cls
    return decorator


def discover_providers():
    """Auto-discover and import all provider modules.
    Uses pkgutil to find and import all modules in the providers package,
    triggering their decorator registrations.
    """
    from deeprepo import providers
    
    package_path = providers.__path__
    package_name = providers.__name__
    
    for _, module_name, _ in pkgutil.iter_modules(package_path):
        full_module_name = f"{package_name}.{module_name}"
        try:
            importlib.import_module(full_module_name)
        except ImportError as e:
            print(f"Warning: Could not import provider {full_module_name}: {e}")


def get_llm(name: str) -> LLMProvider:
    """Get an LLM provider instance by name.
    Args:
        name: The registered name of the provider.
    Returns:
        An instance of the requested LLM provider.
    Raises:
        KeyError: If the provider name is not registered.
    """
    if name not in LLM_REGISTRY:
        available = list(LLM_REGISTRY.keys())
        raise KeyError(f"LLM provider '{name}' not found. Available: {available}")
    return LLM_REGISTRY[name]()


def get_embedding(name: str) -> EmbeddingProvider:
    """Get an embedding provider instance by name.
    Args:
        name: The registered name of the provider.
    Returns:
        An instance of the requested embedding provider.
    Raises:
        KeyError: If the provider name is not registered.
    """
    if name not in EMBEDDING_REGISTRY:
        available = list(EMBEDDING_REGISTRY.keys())
        raise KeyError(f"Embedding provider '{name}' not found. Available: {available}")
    return EMBEDDING_REGISTRY[name]()
