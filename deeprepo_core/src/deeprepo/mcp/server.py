"""MCP server exposing DeepRepo as a tool server for AI assistants."""

import logging
import sys
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from deeprepo.client import BranchMismatchError

mcp = FastMCP("deeprepo")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]  # Explicitly use stderr
)
logger = logging.getLogger("deeprepo-mcp")

_client: Optional["DeepRepoClient"] = None  # type: ignore


def get_client():
    """Get or create the singleton DeepRepo client."""
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
        
        wiki_dir = result.get('wiki_dir', 'N/A')
        branch = result.get('branch', 'N/A')
        return f"""Ingestion Completed for {path}
                Chunks processed: {result.get('chunks_processed', 0)}
                Files scanned: {result.get('files_scanned', 0)}
                Branch: {branch}
                Wiki directory: {wiki_dir}
                Message: {result.get('message', '')}
            """
    except BranchMismatchError as e:
        return f"Branch mismatch: {str(e)}"
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
    except BranchMismatchError as e:
        return f"Branch mismatch: {str(e)}"
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
        
        # Search graph store embeddings
        results = client.graph_store.search_embeddings(query_embedding, top_k=top_k)

        if not results:
            return "No similar chunks found. Have you ingested any documents?"

        output = ["Search Results:"]
        for i, (filepath, score) in enumerate(results, 1):
            output.append(f"  {i}. {filepath} (score: {score:.3f})")
        
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
                    Branch: {stats.get('branch', 'N/A')}
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


@mcp.tool()
def get_blast_radius(filepath: str, depth: int = 2) -> str:
    """
    Get the minimal set of files affected by changes to a given file.

    Uses the code knowledge graph to trace callers, importers, and
    transitive dependents. Much faster and more precise than semantic search
    for impact analysis.

    Args:
        filepath: Relative path of the changed file (e.g. "src/auth.py")
        depth: BFS depth for traversal (default: 2)

    Returns:
        List of affected file paths with explanation
    """
    client = get_client()
    try:
        affected = client.graph_store.get_blast_radius(filepath, depth=depth)
        if not affected:
            return f"No dependents found for '{filepath}'. Either the file has no callers or hasn't been indexed yet."
        lines = [f"Files affected by changes to '{filepath}' (depth={depth}):"]
        for i, fp in enumerate(affected, 1):
            lines.append(f"  {i}. {fp}")
        lines.append(f"\nTotal: {len(affected)} file(s)")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Blast radius failed: {e}")
        return f"Blast radius analysis failed: {str(e)}"


@mcp.tool()
def get_file_skeleton(filepath: str) -> str:
    """
    Get function and class signatures for a file without implementation bodies.

    Returns a compact view of the file's public API - useful for understanding
    structure without loading full file content. Typical token cost: ~100-200
    tokens vs 1000+ for full file content.

    Args:
        filepath: Relative path of the file (e.g. "src/client.py")

    Returns:
        All function/class signatures with line numbers
    """
    client = get_client()
    try:
        skeleton = client.graph_store.get_file_skeleton(filepath)
        if not skeleton:
            return f"No skeleton found for '{filepath}'. File may not be indexed or has no functions/classes."
        return f"Skeleton for '{filepath}':\n\n{skeleton}"
    except Exception as e:
        logger.error(f"Skeleton failed: {e}")
        return f"Failed to get skeleton: {str(e)}"


@mcp.tool()
def find_symbol(name: str) -> str:
    """
    Find the exact definition location of any function or class by name.

    Uses the code knowledge graph symbol index for instant lookup -
    no embedding or semantic search needed. Typical token cost: ~50 tokens.

    Args:
        name: Function or class name to look up (e.g. "VectorStore", "ingest_directory")

    Returns:
        File path, line number, type, and signature of the symbol
    """
    client = get_client()
    try:
        symbol = client.graph_store.get_symbol(name)
        if not symbol:
            return f"Symbol '{name}' not found in the graph index. Has the codebase been ingested?"
        return (
            f"Symbol: {symbol['name']}\n"
            f"Type: {symbol['type']}\n"
            f"File: {symbol['filepath']}\n"
            f"Line: {symbol['line_start']}\n"
            f"Signature: {symbol.get('signature', 'N/A')}\n"
            f"Docstring: {symbol.get('docstring', 'N/A')}"
        )
    except Exception as e:
        logger.error(f"Symbol lookup failed: {e}")
        return f"Symbol lookup failed: {str(e)}"


@mcp.tool()
def get_wiki_page(filepath: str, concise: bool = True) -> str:
    """
    Get the auto-generated wiki page for a source file.

    Returns a structured summary including: what the file does, its public API,
    dependencies, and an architecture diagram. Token cost: ~150 tokens vs
    1000+ tokens for raw file content.

    Args:
        filepath: Relative path of the file (e.g. "src/deeprepo/client.py")
        concise: If True, return a shorter summary (default: True)

    Returns:
        Formatted wiki page with summary, API, dependencies, and diagram
    """
    client = get_client()
    try:
        content = client.wiki_engine.get_page(filepath, concise=concise)
        if not content:
            return (
                f"No wiki page for '{filepath}'. "
                "Either ingest the codebase first or this file has no generated page."
            )
        return content
    except Exception as e:
        logger.error(f"Wiki page failed: {e}")
        return f"Failed to get wiki page: {str(e)}"


@mcp.tool()
def search_wiki(query: str) -> str:
    """
    Search wiki pages by keyword across all file summaries and APIs.

    Faster than semantic search for finding which file owns specific
    functionality. Returns file summaries ranked by keyword match.

    Args:
        query: Keywords to search (e.g. "authentication", "vector search")

    Returns:
        Ranked list of matching files with their summaries
    """
    client = get_client()
    try:
        results = client.wiki_engine.search_wiki(query)
        if not results:
            return f"No wiki pages match '{query}'. Try ingesting the codebase first."
        lines = [f"Wiki search results for '{query}':\n"]
        for i, page in enumerate(results, 1):
            lines.append(f"{i}. {page['filepath']}")
            lines.append(f"   {page.get('summary', 'No summary')}\n")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Wiki search failed: {e}")
        return f"Wiki search failed: {str(e)}"


@mcp.tool()
def get_repo_overview() -> str:
    """
    Get a high-level overview of the entire repository from wiki summaries.

    Returns a structured view of all indexed files grouped by directory,
    with one-line summaries and graph statistics. Ideal for orientation
    before diving into specific files.

    Returns:
        Repository overview with file summaries and architecture stats
    """
    client = get_client()
    try:
        return client.wiki_engine.get_repo_overview(graph_store=client.graph_store)
    except Exception as e:
        logger.error(f"Repo overview failed: {e}")
        return f"Failed to get repo overview: {str(e)}"


@mcp.tool()
def smart_query(question: str, top_k: int = 5) -> str:
    """
    Query the codebase with automatic intent detection and optimal context strategy.

    Unlike query_codebase (which always uses standard RAG), smart_query detects
    your intent and selects the minimum context needed:
    - "where is X" → symbol lookup (~50 tokens)
    - "what breaks if I change X" → blast radius (~200 tokens)
    - "how does X work" → wiki + skeleton (~600 tokens)
    - "fix bug in X" → full chunk + structure (~900 tokens)
    - "review X" → file + neighbor skeletons (~950 tokens)

    Args:
        question: Your question about the codebase
        top_k: Number of vector search results to consider (default: 5)

    Returns:
        Answer with intent classification and token savings metadata
    """
    client = get_client()
    try:
        result = client.query(question, top_k=top_k)

        sources = result.get("sources", [])
        sources_text = "\n".join(f"  {i}. {s}" for i, s in enumerate(sources, 1)) or "  None"

        return (
            f"Intent: {result.get('intent', 'general')} "
            f"| Strategy: {result.get('strategy', 'standard_rag')} "
            f"| Retrieval: {result.get('retrieval', 'unknown')} "
            f"| Est. tokens: {result.get('token_estimate', '?')}\n\n"
            f"Answer:\n{result.get('answer', 'No answer generated')}\n\n"
            f"Sources:\n{sources_text}"
        )
    except BranchMismatchError as e:
        return f"Branch mismatch: {str(e)}"
    except Exception as e:
        logger.error(f"Smart query failed: {e}")
        return f"Smart query failed: {str(e)}"


@mcp.tool()
def explain_routing(question: str) -> str:
    """
    Show what context strategy would be used for a query without executing it.

    Useful for understanding why the router made a particular decision,
    or for debugging unexpected context choices.

    Args:
        question: The query to analyze

    Returns:
        Intent classification with matched pattern explanation
    """
    client = get_client()
    try:
        from deeprepo.router import INTENT_PATTERNS
        import re

        intent = client.router.classify(question)

        matched_pattern = "no pattern (general fallback)"
        for candidate_intent, patterns in INTENT_PATTERNS:
            for pattern in patterns:
                if re.search(pattern, question, re.IGNORECASE):
                    matched_pattern = f"/{pattern}/"
                    break
            if candidate_intent == intent and matched_pattern != "no pattern (general fallback)":
                break

        return (
            f"Query: {question}\n"
            f"Classified as: {intent.value.upper()}\n"
            f"Matched pattern: {matched_pattern}\n\n"
            f"Context strategy for this intent:\n"
            f"  NAVIGATE → symbol lookup (~50-80 tokens)\n"
            f"  IMPACT   → blast radius (~200-400 tokens)\n"
            f"  EXPLAIN  → wiki + skeleton (~600 tokens)\n"
            f"  DEBUG    → full chunk + structure (~900 tokens)\n"
            f"  REVIEW   → full + neighbor skeletons (~950 tokens)\n"
            f"  GENERAL  → standard RAG (~2000 tokens)"
        )
    except Exception as e:
        logger.error(f"Explain routing failed: {e}")
        return f"Explain routing failed: {str(e)}"


@mcp.tool()
def get_freshness_status() -> str:
    """
    Get freshness and branch isolation status for the current branch.

    Shows: current branch, base branch status (fresh/stale), last indexed commit,
    pending file changes, and module tree staleness. Useful for understanding
    whether the wiki and graph are up-to-date.

    Returns:
        JSON-formatted freshness status
    """
    client = get_client()
    try:
        import json
        status = client.get_freshness_status()
        return json.dumps(status, indent=2)
    except Exception as e:
        logger.error(f"Freshness status failed: {e}")
        return f"Freshness status failed: {str(e)}"


@mcp.tool()
def get_wiki_dir() -> str:
    """
    Get the absolute path to the wiki directory containing browsable .md files.

    The wiki directory contains physical markdown files generated during ingestion,
    organized by module hierarchy. You can open these in any markdown viewer.

    Returns:
        Absolute path to the wiki directory
    """
    client = get_client()
    try:
        wiki_dir = client.get_wiki_dir()
        import os
        if os.path.exists(wiki_dir):
            md_count = sum(1 for _ in Path(wiki_dir).rglob("*.md"))
            return f"Wiki directory: {wiki_dir}\nMarkdown files: {md_count}"
        return f"Wiki directory: {wiki_dir} (not yet created — run ingest_codebase first)"
    except Exception as e:
        logger.error(f"Wiki dir failed: {e}")
        return f"Failed to get wiki dir: {str(e)}"


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
        "mcp_server_version": "1.0.0",
        "supported_providers": ["openai", "gemini", "ollama", "huggingface", "anthropic"]
    }
    return json.dumps(config, indent=2)


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


def main():
    """Run the DeepRepo MCP server."""
    logger.info("Starting DeepRepo MCP server...")
    logger.info("Available tools: ingest_codebase, query_codebase, search_similar, get_stats, clear_history, "
                 "get_blast_radius, get_file_skeleton, find_symbol, get_wiki_page, search_wiki, "
                 "get_repo_overview, smart_query, explain_routing, get_freshness_status, get_wiki_dir")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
