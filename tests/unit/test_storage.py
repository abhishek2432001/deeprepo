"""Unit tests for VectorStore.

Tests the core vector math (cosine similarity) and storage operations.
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from deeprepo.storage import VectorStore


class TestCosineSimiliarity:
    """Test cosine similarity calculations."""
    
    def test_identical_vectors_have_similarity_one(self):
        """Identical vectors should have cosine similarity of 1.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(Path(tmpdir) / "test.json")
            
            # Create identical vectors
            vec = [1.0, 0.0, 0.0]
            chunks = [
                {"text": "test", "embedding": vec, "metadata": {}}
            ]
            store.save(chunks)
            store.load()
            
            results = store.search(vec, top_k=1)
            
            assert len(results) == 1
            assert results[0]["score"] == pytest.approx(1.0, rel=1e-5)
    
    def test_orthogonal_vectors_have_similarity_zero(self):
        """Orthogonal vectors should have cosine similarity of 0.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(Path(tmpdir) / "test.json")
            
            # Create orthogonal vectors
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [0.0, 1.0, 0.0]
            
            chunks = [
                {"text": "test", "embedding": vec2, "metadata": {}}
            ]
            store.save(chunks)
            store.load()
            
            results = store.search(vec1, top_k=1)
            
            assert len(results) == 1
            assert results[0]["score"] == pytest.approx(0.0, abs=1e-5)
    
    def test_opposite_vectors_have_similarity_negative_one(self):
        """Opposite vectors should have cosine similarity of -1.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(Path(tmpdir) / "test.json")
            
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [-1.0, 0.0, 0.0]
            
            chunks = [
                {"text": "test", "embedding": vec2, "metadata": {}}
            ]
            store.save(chunks)
            store.load()
            
            results = store.search(vec1, top_k=1)
            
            assert len(results) == 1
            assert results[0]["score"] == pytest.approx(-1.0, rel=1e-5)


class TestVectorStore:
    """Test VectorStore save/load operations."""
    
    def test_save_and_load_preserves_data(self):
        """Save and load should preserve chunk data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "vectors.json"
            store = VectorStore(storage_path)
            
            chunks = [
                {
                    "text": "Hello world",
                    "embedding": [0.1, 0.2, 0.3],
                    "metadata": {"filepath": "test.py", "chunk_index": 0}
                },
                {
                    "text": "Goodbye world",
                    "embedding": [0.4, 0.5, 0.6],
                    "metadata": {"filepath": "test.py", "chunk_index": 1}
                }
            ]
            
            store.save(chunks)
            
            # Create new store instance and load
            store2 = VectorStore(storage_path)
            loaded = store2.load()
            
            assert len(loaded) == 2
            assert loaded[0]["text"] == "Hello world"
            assert loaded[1]["text"] == "Goodbye world"
            # Embeddings are stored as lists, not numpy arrays (minimal numpy usage)
            assert isinstance(loaded[0]["embedding"], list)
            assert loaded[0]["embedding"] == [0.1, 0.2, 0.3]
    
    def test_load_missing_file_returns_empty(self):
        """Loading a non-existent file should return empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "nonexistent.json"
            store = VectorStore(storage_path)
            
            loaded = store.load()
            
            assert loaded == []
    
    def test_search_empty_store_returns_empty(self):
        """Searching an empty store should return empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(Path(tmpdir) / "test.json")
            
            results = store.search([0.1, 0.2, 0.3], top_k=5)
            
            assert results == []
    
    def test_search_returns_top_k_results(self):
        """Search should return exactly top_k results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(Path(tmpdir) / "test.json")
            
            # Create 10 chunks
            chunks = []
            for i in range(10):
                vec = [float(i), 0.0, 0.0]
                chunks.append({
                    "text": f"Chunk {i}",
                    "embedding": vec,
                    "metadata": {"index": i}
                })
            
            store.save(chunks)
            store.load()
            
            # Search with top_k=3
            results = store.search([9.0, 0.0, 0.0], top_k=3)
            
            assert len(results) == 3
    
    def test_search_results_are_sorted_by_similarity(self):
        """Search results should be sorted by similarity (highest first)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(Path(tmpdir) / "test.json")
            
            chunks = [
                {"text": "Far", "embedding": [-1.0, 0.0, 0.0], "metadata": {}},
                {"text": "Close", "embedding": [0.9, 0.1, 0.0], "metadata": {}},
                {"text": "Closest", "embedding": [1.0, 0.0, 0.0], "metadata": {}},
            ]
            
            store.save(chunks)
            store.load()
            
            results = store.search([1.0, 0.0, 0.0], top_k=3)
            
            assert results[0]["text"] == "Closest"
            assert results[1]["text"] == "Close"
            assert results[2]["text"] == "Far"
