"""VectorStore - Repository Pattern implementation for vector storage.

Provides JSON-based persistence with optimized similarity search.
NumPy is used only for performance-critical vector operations.
"""

import json
from pathlib import Path
from typing import Any


class VectorStore:
    """A simple vector store using JSON for persistence.
    
    This class implements the Repository Pattern, decoupling storage logic
    from application logic. Vectors are stored as JSON (lists) and converted to
    NumPy arrays only when needed for efficient similarity calculations.
    
    Attributes:
        storage_path: Path to the vectors.json file.
        chunks: List of chunk dictionaries with text and embeddings.
    """
    
    def __init__(self, storage_path: str = "vectors.json"):
        """Initialize the VectorStore.
        Args:
            storage_path: Path to the JSON file for storing vectors.
                Defaults to 'vectors.json' in current directory.
        """
        self.storage_path = Path(storage_path)
        self.chunks: list[dict[str, Any]] = []
        self._embeddings_matrix = None  # Only created when needed for search
        
    def save(self, chunks: list[dict[str, Any]]) -> None:
        """Save chunks with embeddings to JSON storage.
        Args:
            chunks: List of dictionaries containing at minimum:
                - 'text': The text content of the chunk
                - 'embedding': The embedding vector as a list of floats
                - 'metadata': Optional metadata about the chunk
        """
        self.chunks = chunks
        self._embeddings_matrix = None  # Invalidate cache
        
        # Ensure parent directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert arrays to lists for JSON serialization (duck typing)
        serializable_chunks = []
        for chunk in chunks:
            serializable_chunk = chunk.copy()
            embedding = chunk.get('embedding')
            # Duck typing: if it has tolist(), it's array-like
            if embedding is not None and hasattr(embedding, 'tolist'):
                serializable_chunk['embedding'] = embedding.tolist()
            serializable_chunks.append(serializable_chunk)
        
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_chunks, f, indent=2)
            
    def load(self) -> list[dict[str, Any]]:
        """Load chunks from JSON storage.
        If the storage file doesn't exist, initializes as empty
        (fails gracefully per spec requirements).
        Returns:
            List of chunk dictionaries with embeddings as lists.
        """
        if not self.storage_path.exists():
            self.chunks = []
            self._embeddings_matrix = None
            return self.chunks
            
        with open(self.storage_path, 'r', encoding='utf-8') as f:
            self.chunks = json.load(f)
            
        # Keep embeddings as lists for minimal memory and no numpy dependency
        # They'll be converted to arrays only when search() is called
        self._embeddings_matrix = None  # Will be built on first search
        return self.chunks
        
    def _build_embeddings_matrix(self):
        """Build a matrix of all embeddings for efficient batch search.
        Lazily imports NumPy only when needed for search operations.
        Returns:
            NumPy array of shape (n_chunks, embedding_dim).
        """
        if self._embeddings_matrix is not None:
            return self._embeddings_matrix
            
        if not self.chunks:
            import numpy as np
            return np.array([])
            
        # Lazy import: only load numpy when actually doing search
        import numpy as np
        
        embeddings = []
        for chunk in self.chunks:
            if 'embedding' in chunk:
                emb = chunk['embedding']
                # Convert to numpy array if it's a list
                if isinstance(emb, list):
                    embeddings.append(np.array(emb, dtype=np.float32))
                else:
                    embeddings.append(emb)
        
        if not embeddings:
            return np.array([])
            
        self._embeddings_matrix = np.vstack(embeddings)
        return self._embeddings_matrix
        
    def _compute_cosine_similarities(self, query_vec, embeddings_matrix):
        """Compute cosine similarity between query and all embeddings.
        
        Cosine similarity formula: dot(A, B) / (norm(A) * norm(B))
        
        Args:
            query_vec: Query embedding as NumPy array.
            embeddings_matrix: Matrix of all chunk embeddings.
            
        Returns:
            NumPy array of similarity scores (one per chunk).
        """
        import numpy as np
        
        # Step 1: Calculate the magnitude (norm) of the query vector
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return np.zeros(len(self.chunks))
        
        # Step 2: Calculate the magnitude (norm) of each embedding
        embeddings_norms = np.linalg.norm(embeddings_matrix, axis=1)
        
        # Step 3: Initialize similarity scores to zero
        similarities = np.zeros(len(self.chunks))
        
        # Step 4: Only compute for embeddings with non-zero norms (avoid division by zero)
        valid_embeddings = embeddings_norms > 0
        
        if valid_embeddings.any():
            """
            # Pure Python equivalent, this is slow
            for i, embedding in enumerate(embeddings):
                if embeddings_norms[i] > 0:
                    dot_product = sum(a * b for a, b in zip(embedding, query_vec))
                    similarities[i] = dot_product / (embeddings_norms[i] * query_norm)
            """
            # Compute dot products for all valid embeddings at once (vectorized)
            dot_products = embeddings_matrix[valid_embeddings] @ query_vec
            
            # Compute cosine similarity: dot_product / (norm_A * norm_B)
            similarities[valid_embeddings] = dot_products / (
                embeddings_norms[valid_embeddings] * query_norm
            )
        
        return similarities
    
    def _get_top_k_indices(self, similarities, top_k):
        """Get indices of top-k most similar chunks using partial sorting.
        
        Uses argpartition for O(n) performance instead of O(n log n) full sort.
        This is optimal when k << n (e.g., top 5 from 10,000 chunks).
        
        Args:
            similarities: Array of similarity scores.
            top_k: Number of top results to return.
            
        Returns:
            Array of indices sorted by similarity (highest first).
        """
        import numpy as np
        
        n = len(similarities)
        #We could have used heapq but it's not as fast as argpartition
        if top_k >= n:
            # If requesting all or more items, just do a full sort
            return np.argsort(similarities)[::-1]
        
        # argpartition: O(n) - partially sorts so the k largest are at the end
        # We use -top_k to get the k largest (not smallest)
        top_k_indices = np.argpartition(similarities, -top_k)[-top_k:]
        
        # Sort only these k elements by their actual similarity scores (O(k log k))
        # This gives us the final ordering from highest to lowest
        top_k_indices = top_k_indices[np.argsort(similarities[top_k_indices])[::-1]]
        
        return top_k_indices
    
    def search(
        self, 
        query_vec: list[float] | Any,  # Accept list or array-like 
        top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Search for most similar chunks using cosine similarity.
        
        Implements cosine similarity: dot(A, B) / (norm(A) * norm(B))
        NumPy is used here for vectorized operations (10-100x faster than Python loops).
        
        Args:
            query_vec: Query embedding vector (list or array).
            top_k: Number of top results to return. Defaults to 5.
            
        Returns:
            List of chunk dictionaries sorted by similarity (highest first).
            Each chunk includes a 'score' field with the similarity score.
        """
        if not self.chunks:
            return []
        
        import numpy as np

        if isinstance(query_vec, list):
            query_vec = np.array(query_vec, dtype=np.float32)
        
        embeddings_matrix = self._build_embeddings_matrix()
        if embeddings_matrix.size == 0:
            return []
        
        similarities = self._compute_cosine_similarities(query_vec, embeddings_matrix)
        
        top_indices = self._get_top_k_indices(similarities, top_k)
        
        results = []
        for idx in top_indices:
            chunk_with_score = self.chunks[idx].copy()
            chunk_with_score['score'] = float(similarities[idx])
            results.append(chunk_with_score)
        
        return results
