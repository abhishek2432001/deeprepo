"""Tests for the DeepRepo MCP server."""

import pytest
from unittest.mock import MagicMock, patch


class TestMCPServerImport:
    """Test that the MCP server module imports correctly."""
    
    def test_mcp_module_import(self):
        """Test that the MCP module can be imported."""
        from deeprepo.mcp import mcp, main
        
        assert mcp is not None
        assert main is not None
    
    def test_mcp_server_import(self):
        """Test that the MCP server module can be imported."""
        from deeprepo.mcp.server import (
            mcp,
            main,
            get_client,
            ingest_codebase,
            query_codebase,
            search_similar,
            get_stats,
            clear_history,
        )
        
        assert mcp is not None
        assert callable(main)
        assert callable(get_client)
        assert callable(ingest_codebase)
        assert callable(query_codebase)
        assert callable(search_similar)
        assert callable(get_stats)
        assert callable(clear_history)


class TestMCPTools:
    """Test MCP tool functions."""
    
    @patch('deeprepo.mcp.server.get_client')
    def test_get_stats_tool(self, mock_get_client):
        """Test the get_stats tool."""
        from deeprepo.mcp.server import get_stats
        
        # Mock the client
        mock_client = MagicMock()
        mock_client.get_stats.return_value = {
            'total_chunks': 100,
            'total_files': 10,
            'files': ['file1.py', 'file2.py'],
            'storage_path': 'vectors.json',
            'provider': 'ollama'
        }
        mock_get_client.return_value = mock_client
        
        # Call the tool
        result = get_stats()
        
        # Verify
        assert 'DeepRepo Statistics:' in result
        assert 'Total chunks: 100' in result
        assert 'Total files: 10' in result
        assert 'ollama' in result
    
    @patch('deeprepo.mcp.server.get_client')
    def test_clear_history_tool(self, mock_get_client):
        """Test the clear_history tool."""
        from deeprepo.mcp.server import clear_history
        
        # Mock the client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Call the tool
        result = clear_history()
        
        # Verify
        assert 'cleared' in result.lower()
        mock_client.clear_history.assert_called_once()
    
    @patch('deeprepo.mcp.server.get_client')
    def test_ingest_codebase_success(self, mock_get_client):
        """Test successful codebase ingestion."""
        from deeprepo.mcp.server import ingest_codebase
        
        # Mock the client
        mock_client = MagicMock()
        mock_client.ingest.return_value = {
            'chunks_processed': 50,
            'files_scanned': 5,
            'message': 'Success'
        }
        mock_client.storage_path = 'vectors.json'
        mock_get_client.return_value = mock_client
        
        # Call the tool
        result = ingest_codebase('/test/path', chunk_size=1000, overlap=100)
        
        # Verify
        assert 'Ingestion Completed' in result
        assert '/test/path' in result
        assert '50' in result
        assert '5' in result
    
    @patch('deeprepo.mcp.server.get_client')
    def test_ingest_codebase_failure(self, mock_get_client):
        """Test failed codebase ingestion."""
        from deeprepo.mcp.server import ingest_codebase
        
        # Mock the client to raise an exception
        mock_client = MagicMock()
        mock_client.ingest.side_effect = Exception("Test error")
        mock_get_client.return_value = mock_client
        
        # Call the tool
        result = ingest_codebase('/test/path')
        
        # Verify
        assert 'failed' in result.lower()
    
    @patch('deeprepo.mcp.server.get_client')
    def test_query_codebase_success(self, mock_get_client):
        """Test successful codebase query."""
        from deeprepo.mcp.server import query_codebase
        
        # Mock the client
        mock_client = MagicMock()
        mock_client.query.return_value = {
            'answer': 'This is the answer',
            'sources': ['file1.py', 'file2.py']
        }
        mock_get_client.return_value = mock_client
        
        # Call the tool
        result = query_codebase('How does X work?', top_k=3)
        
        # Verify
        assert 'Answer:' in result
        assert 'This is the answer' in result
        assert 'file1.py' in result


class TestMCPResources:
    """Test MCP resource functions."""
    
    @patch('deeprepo.mcp.server.get_client')
    def test_stats_resource(self, mock_get_client):
        """Test the stats resource."""
        from deeprepo.mcp.server import get_stats_resource
        import json
        
        # Mock the client
        mock_client = MagicMock()
        mock_client.get_stats.return_value = {
            'total_chunks': 100,
            'total_files': 10
        }
        mock_get_client.return_value = mock_client
        
        # Call the resource
        result = get_stats_resource()
        
        # Verify it's valid JSON
        data = json.loads(result)
        assert data['total_chunks'] == 100
        assert data['total_files'] == 10
    
    def test_config_resource(self):
        """Test the config resource."""
        from deeprepo.mcp.server import get_config_resource
        import json
        
        # Call the resource
        result = get_config_resource()
        
        # Verify it's valid JSON
        data = json.loads(result)
        assert 'llm_provider' in data
        assert 'storage_path' in data
        assert 'supported_providers' in data


class TestMCPPrompts:
    """Test MCP prompt templates."""
    
    def test_analyze_codebase_prompt(self):
        """Test the analyze_codebase prompt template."""
        from deeprepo.mcp.server import analyze_codebase
        
        result = analyze_codebase('/test/directory')
        
        assert '/test/directory' in result
        assert 'ingest' in result.lower()
        assert 'architecture' in result.lower()
    
    def test_explain_function_prompt(self):
        """Test the explain_function prompt template."""
        from deeprepo.mcp.server import explain_function
        
        result = explain_function('my_function')
        
        assert 'my_function' in result
        assert 'search' in result.lower()
        assert 'explain' in result.lower()
    
    def test_find_bugs_prompt(self):
        """Test the find_bugs prompt template."""
        from deeprepo.mcp.server import find_bugs
        
        result = find_bugs()
        
        assert 'bug' in result.lower()
        assert 'security' in result.lower()
