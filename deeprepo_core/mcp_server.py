#!/usr/bin/env python3
"""Entry point for DeepRepo MCP server.

This script serves as a convenient entry point for running the MCP server.

Usage:
    python mcp_server.py
    
    # Or with specific provider
    LLM_PROVIDER=openai python mcp_server.py
"""

from deeprepo.mcp.server import main

if __name__ == "__main__":
    main()
