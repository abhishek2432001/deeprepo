#!/usr/bin/env python3
"""
MCP Server Integration Test Script

This script tests the full MCP server flow including:
1. Server initialization
2. Ingestion
3. Querying
4. Search
5. Stats and utilities

Usage:
    # Set your provider (ollama recommended for local testing)
    export LLM_PROVIDER=ollama
    
    # Run the test
    python tests/integration/test_mcp_integration.py
    
    # Or test with a specific directory
    python tests/integration/test_mcp_integration.py /path/to/codebase
"""

import os
import sys
import tempfile
from pathlib import Path


def create_test_files(test_dir: Path):
    """Create sample files for testing."""
    # Create a simple Python file
    (test_dir / "sample.py").write_text('''
def hello_world():
    """A simple greeting function."""
    return "Hello, World!"

def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

class Calculator:
    """A simple calculator class."""
    
    def multiply(self, x, y):
        return x * y
    
    def divide(self, x, y):
        if y == 0:
            raise ValueError("Cannot divide by zero")
        return x / y
''')
    
    # Create a README
    (test_dir / "README.md").write_text('''
# Sample Project

This is a sample project for testing the MCP server.

## Features
- Simple math functions
- Calculator class
''')
    
    print(f"Created test files in: {test_dir}")


def test_mcp_flow(test_path: str = None):
    """Run the full MCP flow test."""
    
    print("=" * 60)
    print("MCP Server Integration Test")
    print("=" * 60)
    print()
    
    # Import MCP components
    print("1. Importing MCP server components...")
    try:
        from deeprepo.mcp.server import (
            mcp,
            get_client,
            ingest_codebase,
            query_codebase,
            search_similar,
            get_stats,
            clear_history,
            get_stats_resource,
            get_config_resource,
            analyze_codebase,
            explain_function,
        )
        print("   OK - All components imported successfully")
    except ImportError as e:
        print(f"   FAILED - Import error: {e}")
        print("   Make sure you've installed: pip install deeprepo[mcp]")
        return False
    
    print()
    
    # Check provider
    provider = os.environ.get("LLM_PROVIDER", "openai")
    print(f"2. Using LLM Provider: {provider}")
    print()
    
    # Determine test path
    if test_path:
        ingest_path = test_path
        cleanup = False
    else:
        # Create temporary test directory
        temp_dir = tempfile.mkdtemp(prefix="mcp_test_")
        ingest_path = temp_dir
        create_test_files(Path(temp_dir))
        cleanup = True
    
    print(f"3. Test directory: {ingest_path}")
    print()
    
    try:
        # Test: Get initial stats
        print("4. Testing get_stats() - Initial state:")
        stats_result = get_stats()
        print(f"   {stats_result.strip()}")
        print()
        
        # Test: Ingest
        print("5. Testing ingest_codebase():")
        ingest_result = ingest_codebase(ingest_path, chunk_size=500, overlap=50)
        print(f"   {ingest_result.strip()}")
        print()
        
        # Test: Get stats after ingestion
        print("6. Testing get_stats() - After ingestion:")
        stats_result = get_stats()
        # Just print first few lines
        for line in stats_result.strip().split('\n')[:6]:
            print(f"   {line.strip()}")
        print()
        
        # Test: Search similar
        print("7. Testing search_similar():")
        search_result = search_similar("calculator multiply", top_k=2)
        # Print first 500 chars
        preview = search_result[:500] + "..." if len(search_result) > 500 else search_result
        for line in preview.strip().split('\n')[:10]:
            print(f"   {line.strip()}")
        print()
        
        # Test: Query (uses LLM)
        print("8. Testing query_codebase() - This uses the LLM:")
        query_result = query_codebase("What functions are available in this codebase?", top_k=3)
        # Print first 500 chars
        preview = query_result[:500] + "..." if len(query_result) > 500 else query_result
        for line in preview.strip().split('\n')[:8]:
            print(f"   {line.strip()}")
        print()
        
        # Test: Resources
        print("9. Testing resources:")
        print("   Stats resource (JSON):")
        import json
        stats_json = get_stats_resource()
        stats_data = json.loads(stats_json)
        print(f"     total_chunks: {stats_data.get('total_chunks')}")
        print(f"     total_files: {stats_data.get('total_files')}")
        
        print("   Config resource (JSON):")
        config_json = get_config_resource()
        config_data = json.loads(config_json)
        print(f"     llm_provider: {config_data.get('llm_provider')}")
        print()
        
        # Test: Prompts
        print("10. Testing prompt templates:")
        prompt = analyze_codebase("/my/project")
        print(f"    analyze_codebase prompt: {prompt[:80]}...")
        
        prompt = explain_function("my_function")
        print(f"    explain_function prompt: {prompt[:80]}...")
        print()
        
        # Test: Clear history
        print("11. Testing clear_history():")
        clear_result = clear_history()
        print(f"    {clear_result}")
        print()
        
        print("=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if cleanup:
            import shutil
            shutil.rmtree(ingest_path, ignore_errors=True)
            print(f"\nCleaned up test directory: {ingest_path}")


def main():
    """Main entry point."""
    # Check for custom path argument
    test_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Check provider
    if "LLM_PROVIDER" not in os.environ:
        print("Note: LLM_PROVIDER not set. Defaulting to 'ollama'.")
        print("Set with: export LLM_PROVIDER=ollama")
        os.environ["LLM_PROVIDER"] = "ollama"
    
    success = test_mcp_flow(test_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
