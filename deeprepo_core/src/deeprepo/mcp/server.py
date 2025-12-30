"""DeepRepo MCP Server - Expose DeepRepo as an MCP tool server.

This module implements the Model Context Protocol (MCP) server that allows
AI assistants like Cursor, Claude Desktop, and Antigravity to interact
with DeepRepo for code analysis and RAG operations.

Usage:
    # Run as a module
    python -m deeprepo.mcp.server
    
    # Or use the entry point
    deeprepo-mcp
    
Configuration:
    Set LLM_PROVIDER environment variable to choose the LLM provider:
    - "ollama" (default, free)
    - "openai"
    - "gemini"
    - "huggingface"
    - "anthropic"
    
    Optionally set EMBEDDING_PROVIDER to use a different provider for embeddings:
    - Useful when using Anthropic (which doesn't have embeddings API)
    - Example: EMBEDDING_PROVIDER=openai LLM_PROVIDER=anthropic
"""

import logging
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("deeprepo")

# Configure logging (MCP requires stderr, not stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]  # Explicitly use stderr
)
logger = logging.getLogger("deeprepo-mcp")

# Global client instance (lazy loaded)
_client: Optional["DeepRepoClient"] = None  # type: ignore


def get_client():
    """Get or create the DeepRepo client instance.
    
    Supports separate embedding and LLM providers via environment variables:
    - EMBEDDING_PROVIDER: Provider for embeddings (defaults to LLM_PROVIDER)
    - LLM_PROVIDER: Provider for LLM (defaults to "openai")
    
    Returns:
        DeepRepoClient: The singleton client instance
    """
    global _client
    if _client is None:
        import os
        from deeprepo import DeepRepoClient
        
        embedding_provider = os.environ.get("EMBEDDING_PROVIDER")
        llm_provider = os.environ.get("LLM_PROVIDER")
        
        if embedding_provider or llm_provider:
            _client = DeepRepoClient(
                embedding_provider_name=embedding_provider,
                llm_provider_name=llm_provider
            )
        else:
            # Backward compatibility: use single provider_name
            _client = DeepRepoClient()
        
        logger.info(
            f"DeepRepo client initialized - "
            f"Embedding: {_client.embedding_provider_name}, "
            f"LLM: {_client.llm_provider_name}"
        )
    return _client


# ============================================================
# TOOLS
# ============================================================

@mcp.tool()
def ingest_codebase(
    path: str,
    chunk_size: int = 1000,
    overlap: int = 100
) -> str:
    """
    Ingest a codebase directory into the DeepRepo vector store.
    
    This scans all supported files in the directory, chunks them,
    generates embeddings, and stores them for later querying.
    
    Args:
        path: Absolute path to the directory to ingest
        chunk_size: Size of text chunks in characters (default: 1000)
        overlap: Overlap between chunks in characters (default: 100)
    
    Returns:
        Summary of ingestion results including chunk count
    """
    client = get_client()
    try:
        logger.info(f"Starting ingestion of: {path}")
        result = client.ingest(path, chunk_size=chunk_size, overlap=overlap)
        
        return f"""Ingestion Completed for {path}
                Chunks processed: {result.get('chunks_processed', 0)}
                Files scanned: {result.get('files_scanned', 0)}
                Storage: {result.get('storage_path', client.storage_path)}
                Message: {result.get('message', '')}
            """
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return f"Ingestion failed: {str(e)}"


@mcp.tool()
def query_codebase(
    question: str,
    top_k: int = 5
) -> str:
    """
    Query the ingested codebase using RAG (Retrieval Augmented Generation).
    
    This embeds your question, finds the most relevant code chunks,
    and uses an LLM to generate an answer based on the context.
    
    Args:
        question: Your question about the codebase
        top_k: Number of relevant chunks to retrieve (default: 5)
    
    Returns:
        AI-generated answer with source references
    """
    client = get_client()
    try:
        logger.info(f"Processing query: {question[:100]}...")
        result = client.query(question, top_k=top_k)
        
        # Format sources
        sources = result.get('sources', [])
        if sources:
            sources_text = "\n".join(f"  {i}. {src}" for i, src in enumerate(sources, 1))
        else:
            sources_text = "  No specific sources found"
        
        return f"""Answer: {result.get('answer', 'No answer generated')}
                Sources:    {sources_text}
            """
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return f"Query failed: {str(e)}"


@mcp.tool()
def search_similar(
    query: str,
    top_k: int = 5
) -> str:
    """
    Search for similar code chunks without using the LLM.
    
    Useful for finding related code snippets based on semantic similarity.
    This is faster and doesn't consume LLM tokens.
    
    Args:
        query: Text to search for similar content
        top_k: Number of results to return (default: 5)
    
    Returns:
        List of most similar code chunks with similarity scores
    """
    client = get_client()
    try:
        logger.info(f"Searching for: {query[:100]}...")
        
        # Get embedding for query
        query_embedding = client.embedding_provider.embed(query)
        
        # Search vector store
        results = client.store.search(query_embedding, top_k=top_k)
        
        if not results:
            return "No similar chunks found. Have you ingested any documents?"
        
        output = ["Search Results:"]
        for i, chunk in enumerate(results, 1):
            text = chunk.get('text', '')
            preview = text[:400] + '...' if len(text) > 400 else text
            metadata = chunk.get('metadata', {})
            
            output.append(f"""
                Result {i} (score: {chunk.get('score', 0):.3f}) ---
                Source: {metadata.get('filepath', 'Unknown')}
                Lines: {metadata.get('start_line', '?')}-{metadata.get('end_line', '?')}
                Language: {metadata.get('language', 'Unknown')}

                ```
                {preview}
                ```
            """)
        
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Search failed: {str(e)}"


@mcp.tool()
def get_stats() -> str:
    """
    Get statistics about the current DeepRepo vector store.
    
    Returns information about how many chunks are stored,
    the number of files indexed, and other metadata.
    
    Returns:
        Vector store statistics
    """
    client = get_client()
    try:
        stats = client.get_stats()
        
        files_list = stats.get('files', [])
        files_preview = ""
        if files_list:
            # Show first 10 files
            preview_files = files_list[:10]
            files_preview = "\n".join(f"  - {f}" for f in preview_files)
            if len(files_list) > 10:
                files_preview += f"\n  ... and {len(files_list) - 10} more files"
        
        return f"""DeepRepo Statistics:
                    Total chunks: {stats.get('total_chunks', 0)}
                    Total files: {stats.get('total_files', 0)}
                    Provider: {stats.get('provider', 'Unknown')}
                    Storage file: {stats.get('storage_path', 'N/A')}
                    Indexed files:
                    {files_preview if files_preview else 'No files indexed yet'}
                """
    except Exception as e:
        logger.error(f"Stats failed: {e}")
        return f"Failed to get stats: {str(e)}"


@mcp.tool()
def clear_history() -> str:
    """
    Clear the conversation history in DeepRepo.
    
    Useful when you want to start a fresh conversation
    without context from previous queries.
    
    Returns:
        Confirmation message
    """
    client = get_client()
    try:
        client.clear_history()
        logger.info("Conversation history cleared")
        return "Conversation history cleared successfully!"
    except Exception as e:
        logger.error(f"Clear history failed: {e}")
        return f"Failed to clear history: {str(e)}"


# ============================================================
# RESOURCES
# ============================================================

@mcp.resource("deeprepo://stats")
def get_stats_resource() -> str:
    """Get current vector store statistics as a resource."""
    client = get_client()
    stats = client.get_stats()
    import json
    return json.dumps(stats, indent=2)


@mcp.resource("deeprepo://config")
def get_config_resource() -> str:
    """Get current DeepRepo configuration."""
    import os
    import json
    
    config = {
        "embedding_provider": os.environ.get("EMBEDDING_PROVIDER", os.environ.get("LLM_PROVIDER", "ollama")),
        "llm_provider": os.environ.get("LLM_PROVIDER", "ollama"),
        "storage_path": "vectors.json",
        "mcp_server_version": "1.0.0",
        "supported_providers": ["openai", "gemini", "ollama", "huggingface", "anthropic"]
    }
    return json.dumps(config, indent=2)


# ============================================================
# PROMPTS
# ============================================================

@mcp.prompt()
def analyze_codebase(directory: str) -> str:
    """Template for comprehensive codebase analysis."""
    return f"""Please analyze the codebase at {directory}:

1. First, ingest the codebase using ingest_codebase
2. Then query about the overall architecture
3. Identify the main entry points
4. List the key dependencies and patterns used
"""


@mcp.prompt()
def explain_function(function_name: str) -> str:
    """Template for explaining a specific function."""
    return f"""Please explain the function '{function_name}':

1. Search for the function using search_similar
2. Explain what it does and how it works
3. Describe its parameters and return value
4. Note any important side effects or dependencies
"""


@mcp.prompt()
def find_bugs() -> str:
    """Template for bug detection in the codebase."""
    return """Please analyze the codebase for potential bugs:

1. Query about error handling patterns
2. Search for common bug patterns (null checks, resource leaks, etc.)
3. Look for security vulnerabilities
4. Suggest improvements
"""


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main():
    """Run the DeepRepo MCP server."""
    logger.info("Starting DeepRepo MCP server...")
    logger.info("Available tools: ingest_codebase, query_codebase, search_similar, get_stats, clear_history")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
