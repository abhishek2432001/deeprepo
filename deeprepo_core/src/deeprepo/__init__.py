"""DeepRepo - Local RAG engine for codebases."""

from deeprepo.client import DeepRepoClient, StaleBaseError, BranchMismatchError

__version__ = "0.2.0"
__all__ = ["DeepRepoClient", "StaleBaseError", "BranchMismatchError"]
