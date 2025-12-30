"""Unit tests for client module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from deeprepo.client import DeepRepoClient


class TestDeepRepoClientInit:
    """Test client initialization."""
    
    @patch('deeprepo.client.get_llm_provider')
    @patch('deeprepo.client.get_embedding_provider')
    def test_init_with_default_provider(self, mock_embed, mock_llm):
        """Should initialize with default provider."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        client = DeepRepoClient()
        
        assert client is not None
        mock_llm.assert_called_once()
        mock_embed.assert_called_once()
    
    @patch('deeprepo.client.get_llm_provider')
    @patch('deeprepo.client.get_embedding_provider')
    def test_init_with_custom_provider(self, mock_embed, mock_llm):
        """Should initialize with specified provider."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        client = DeepRepoClient(provider_name="ollama")
        
        mock_llm.assert_called_with("ollama")
        mock_embed.assert_called_with("ollama")
    
    def test_init_with_custom_storage_path(self, tmp_path):
        """Should use custom storage path."""
        storage_path = tmp_path / "custom_vectors.json"
        
        with patch('deeprepo.client.get_llm_provider'), \
             patch('deeprepo.client.get_embedding_provider'):
            client = DeepRepoClient(storage_path=str(storage_path))
            
            assert client.storage.storage_path == storage_path


class TestDeepRepoClientMethods:
    """Test client public methods."""
    
    @patch('deeprepo.client.get_llm_provider')
    @patch('deeprepo.client.get_embedding_provider')
    def test_get_stats_returns_correct_data(self, mock_embed, mock_llm):
        """Should return storage statistics."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        client = DeepRepoClient()
        client.storage.chunks = [
            {"text": "test1", "metadata": {"filepath": "a.py"}},
            {"text": "test2", "metadata": {"filepath": "b.py"}},
        ]
        
        stats = client.get_stats()
        
        assert stats["total_chunks"] == 2
        assert stats["total_files"] == 2
        assert "storage_path" in stats
    
    @patch('deeprepo.client.get_llm_provider')
    @patch('deeprepo.client.get_embedding_provider')
    def test_clear_history_empties_list(self, mock_embed, mock_llm):
        """Should clear conversation history."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        client = DeepRepoClient()
        client.conversation_history = [("q1", "a1"), ("q2", "a2")]
        
        client.clear_history()
        
        assert len(client.conversation_history) == 0
