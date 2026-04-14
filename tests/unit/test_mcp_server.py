"""Tests for the DeepRepo MCP server (7-tool interface)."""

import json
import pytest
from unittest.mock import MagicMock, patch


class TestMCPServerImport:
    """Test that the MCP server module imports correctly."""

    def test_mcp_module_import(self):
        from deeprepo.mcp import mcp, main
        assert mcp is not None
        assert main is not None

    def test_mcp_server_import(self):
        from deeprepo.mcp.server import (
            mcp,
            main,
            get_client,
            ingest_codebase,
            find_symbol,
            get_file_structure,
            explain_file,
            find_change_impact,
            ask_codebase,
            get_project_overview,
        )
        assert mcp is not None
        assert callable(main)
        assert callable(get_client)
        assert callable(ingest_codebase)
        assert callable(find_symbol)
        assert callable(get_file_structure)
        assert callable(explain_file)
        assert callable(find_change_impact)
        assert callable(ask_codebase)
        assert callable(get_project_overview)


class TestMCPTools:
    """Test MCP tool functions."""

    @patch('deeprepo.mcp.server.get_client')
    def test_ingest_codebase_success(self, mock_get_client):
        from deeprepo.mcp.server import ingest_codebase

        mock_client = MagicMock()
        mock_client.ingest.return_value = {
            'chunks_processed': 340,
            'files_scanned': 21,
            'graph_nodes': 252,
            'wiki_generated': 6,
            'branch': 'main',
            'message': 'Successfully ingested 21 files',
        }
        mock_get_client.return_value = mock_client

        result = ingest_codebase('/test/path', chunk_size=1000, overlap=100)

        assert '/test/path' in result
        assert '21' in result
        assert '340' in result

    @patch('deeprepo.mcp.server.get_client')
    def test_ingest_codebase_failure(self, mock_get_client):
        from deeprepo.mcp.server import ingest_codebase

        mock_client = MagicMock()
        mock_client.ingest.side_effect = Exception("Test error")
        mock_get_client.return_value = mock_client

        result = ingest_codebase('/test/path')
        assert 'failed' in result.lower()

    @patch('deeprepo.mcp.server.get_client')
    def test_find_symbol(self, mock_get_client):
        from deeprepo.mcp.server import find_symbol

        mock_client = MagicMock()
        mock_client.graph_store.get_symbol.return_value = {
            'name': 'DeepRepoClient',
            'type': 'class',
            'filepath': 'client.py',
            'line_start': 72,
            'signature': 'class DeepRepoClient:',
            'docstring': 'Main client facade.',
        }
        mock_get_client.return_value = mock_client

        result = find_symbol('DeepRepoClient')
        assert 'DeepRepoClient' in result
        assert 'client.py' in result
        assert '72' in result

    @patch('deeprepo.mcp.server.get_client')
    def test_find_symbol_not_found(self, mock_get_client):
        from deeprepo.mcp.server import find_symbol

        mock_client = MagicMock()
        mock_client.graph_store.get_symbol.return_value = None
        mock_get_client.return_value = mock_client

        result = find_symbol('NonExistent')
        assert 'not found' in result.lower()

    @patch('deeprepo.mcp.server.get_client')
    def test_get_file_structure(self, mock_get_client):
        from deeprepo.mcp.server import get_file_structure

        mock_client = MagicMock()
        mock_client.graph_store.get_file_skeleton.return_value = (
            "[class] class Foo: (line 10)\n[function] def bar(): (line 20)"
        )
        mock_get_client.return_value = mock_client

        result = get_file_structure('client.py')
        assert 'client.py' in result
        assert 'Foo' in result

    @patch('deeprepo.mcp.server.get_client')
    def test_explain_file(self, mock_get_client):
        from deeprepo.mcp.server import explain_file

        mock_client = MagicMock()
        mock_client.wiki_engine.get_page.return_value = "# client.py\n\nThis module does X."
        mock_get_client.return_value = mock_client

        result = explain_file('client.py')
        assert 'client.py' in result

    @patch('deeprepo.mcp.server.get_client')
    def test_find_change_impact(self, mock_get_client):
        from deeprepo.mcp.server import find_change_impact

        mock_client = MagicMock()
        mock_client.graph_store.get_blast_radius.return_value = [
            'api/views.py', 'tests/test_auth.py'
        ]
        mock_get_client.return_value = mock_client

        result = find_change_impact('auth/service.py', depth=2)
        assert 'auth/service.py' in result
        assert 'api/views.py' in result

    @patch('deeprepo.mcp.server.get_client')
    def test_ask_codebase(self, mock_get_client):
        from deeprepo.mcp.server import ask_codebase

        mock_client = MagicMock()
        mock_client.query.return_value = {
            'answer': 'The router classifies intent.',
            'sources': ['router.py'],
            'intent': 'explain',
            'strategy': 'wiki_plus_skeleton',
        }
        mock_get_client.return_value = mock_client

        result = ask_codebase('How does the router work?')
        assert 'router' in result.lower()
        assert 'explain' in result

    @patch('deeprepo.mcp.server.get_client')
    def test_get_project_overview(self, mock_get_client):
        from deeprepo.mcp.server import get_project_overview

        mock_client = MagicMock()
        mock_client.wiki_engine.get_repo_overview.return_value = (
            "# Project Overview\n\nThis project does RAG on codebases."
        )
        mock_get_client.return_value = mock_client

        result = get_project_overview()
        assert 'Overview' in result


class TestMCPResources:
    """Test MCP resource functions."""

    def test_config_resource(self):
        from deeprepo.mcp.server import get_config_resource

        result = get_config_resource()
        data = json.loads(result)
        assert 'llm_provider' in data
        assert 'embedding_provider' in data
        assert 'supported_providers' in data


class TestMCPPrompts:
    """Test MCP prompt templates."""

    def test_start_coding_session_prompt(self):
        from deeprepo.mcp.server import start_coding_session

        result = start_coding_session('/test/directory')
        assert '/test/directory' in result
        assert 'get_project_overview' in result

    def test_plan_code_change_prompt(self):
        from deeprepo.mcp.server import plan_code_change

        result = plan_code_change('auth/service.py')
        assert 'auth/service.py' in result
        assert 'find_change_impact' in result
