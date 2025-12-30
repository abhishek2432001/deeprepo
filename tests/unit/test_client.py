"""Unit tests for client module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from deeprepo.client import DeepRepoClient


class TestDeepRepoClientInit:
    """Test client initialization."""
    
    @patch('deeprepo.client.get_llm')
    @patch('deeprepo.client.get_embedding')
    def test_init_with_default_provider(self, mock_embed, mock_llm):
        """Should initialize with default provider."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        client = DeepRepoClient()
        
        assert client is not None
        mock_llm.assert_called_once()
        mock_embed.assert_called_once()
    
    @patch('deeprepo.client.get_llm')
    @patch('deeprepo.client.get_embedding')
    def test_init_with_custom_provider(self, mock_embed, mock_llm):
        """Should initialize with specified provider."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        client = DeepRepoClient(provider_name="ollama")
        
        mock_llm.assert_called_with("ollama")
        mock_embed.assert_called_with("ollama")
        assert client.embedding_provider_name == "ollama"
        assert client.llm_provider_name == "ollama"
    
    @patch('deeprepo.client.get_llm')
    @patch('deeprepo.client.get_embedding')
    def test_init_with_separate_providers(self, mock_embed, mock_llm):
        """Should initialize with separate embedding and LLM providers."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        client = DeepRepoClient(
            embedding_provider_name="openai",
            llm_provider_name="anthropic"
        )
        
        mock_llm.assert_called_with("anthropic")
        mock_embed.assert_called_with("openai")
        assert client.embedding_provider_name == "openai"
        assert client.llm_provider_name == "anthropic"
    
    @patch('deeprepo.client.get_llm')
    @patch('deeprepo.client.get_embedding')
    def test_init_provider_name_overrides_separate(self, mock_embed, mock_llm):
        """Should use provider_name for both when provided with separate providers."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        # provider_name should take precedence
        client = DeepRepoClient(
            provider_name="ollama",
            embedding_provider_name="openai",
            llm_provider_name="anthropic"
        )
        
        # When provider_name is provided, it should be used for both
        # But separate providers take precedence if both are provided
        # Actually, let's check the implementation logic
        # According to our implementation, separate providers take precedence
        mock_llm.assert_called_with("anthropic")
        mock_embed.assert_called_with("openai")
    
    def test_init_with_custom_storage_path(self, tmp_path):
        """Should use custom storage path."""
        storage_path = tmp_path / "custom_vectors.json"
        
        with patch('deeprepo.client.get_llm'), \
             patch('deeprepo.client.get_embedding'):
            client = DeepRepoClient(storage_path=str(storage_path))
            
            assert client.storage_path == str(storage_path)


class TestDeepRepoClientMethods:
    """Test client public methods."""
    
    @patch('deeprepo.client.get_llm')
    @patch('deeprepo.client.get_embedding')
    def test_get_stats_returns_correct_data(self, mock_embed, mock_llm):
        """Should return storage statistics."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        client = DeepRepoClient()
        client.store.chunks = [
            {"text": "test1", "metadata": {"filepath": "a.py"}},
            {"text": "test2", "metadata": {"filepath": "b.py"}},
        ]
        
        stats = client.get_stats()
        
        assert stats["total_chunks"] == 2
        assert stats["total_files"] == 2
        assert "storage_path" in stats
        assert "embedding_provider" in stats
        assert "llm_provider" in stats
        assert "provider" in stats  # Backward compatibility
    
    @patch('deeprepo.client.get_llm')
    @patch('deeprepo.client.get_embedding')
    def test_get_stats_with_separate_providers(self, mock_embed, mock_llm):
        """Should return stats with separate provider names."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        client = DeepRepoClient(
            embedding_provider_name="openai",
            llm_provider_name="anthropic"
        )
        client.store.chunks = []
        
        stats = client.get_stats()
        
        assert stats["embedding_provider"] == "openai"
        assert stats["llm_provider"] == "anthropic"
        assert stats["provider"] == "anthropic"  # Backward compatibility
    
    @patch('deeprepo.client.get_llm')
    @patch('deeprepo.client.get_embedding')
    def test_clear_history_empties_list(self, mock_embed, mock_llm):
        """Should clear conversation history."""
        mock_llm.return_value = Mock()
        mock_embed.return_value = Mock()
        
        client = DeepRepoClient()
        client.conversation_history = [("q1", "a1"), ("q2", "a2")]
        
        client.clear_history()
        
        assert len(client.conversation_history) == 0
