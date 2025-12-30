"""Provider factory and initialization.

This module ensures all providers are discovered when the package is imported.
"""

from deeprepo.registry import (
    discover_providers,
    get_embedding,
    get_llm,
    EMBEDDING_REGISTRY,
    LLM_REGISTRY,
)


# Auto-discover providers on import
discover_providers()


__all__ = [
    "get_llm",
    "get_embedding",
    "LLM_REGISTRY",
    "EMBEDDING_REGISTRY",
]
