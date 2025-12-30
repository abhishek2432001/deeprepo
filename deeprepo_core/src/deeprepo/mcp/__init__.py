"""DeepRepo MCP Module - Model Context Protocol server for DeepRepo.

This module provides MCP server functionality, allowing AI assistants
like Cursor, Claude Desktop, and others to use DeepRepo for code analysis.
"""

from deeprepo.mcp.server import mcp, main

__all__ = ["mcp", "main"]
