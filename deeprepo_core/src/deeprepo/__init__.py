"""DeepRepo - A local RAG engine for codebases.

This package provides a production-grade solution for Retrieval Augmented
Generation on local code repositories.
"""

from deeprepo.client import DeepRepoClient, StaleBaseError, BranchMismatchError

__version__ = "0.2.0"
__all__ = ["DeepRepoClient", "StaleBaseError", "BranchMismatchError"]
