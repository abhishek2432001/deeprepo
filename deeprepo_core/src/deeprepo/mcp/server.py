"""MCP server exposing DeepRepo as a tool server for AI assistants.

Exposes 7 focused tools — each named to match the natural language a developer
uses when asking about code, so the AI agent reliably picks the right one
without being told explicitly.

Tool selection guide (for system prompts / CLAUDE.md):
  find_symbol         → "where is X defined / what line is X on"
  get_file_structure  → "show me the structure / API / functions in X"
  explain_file        → "how does X work / explain X / what does X do"
  find_change_impact  → "what breaks if I change X / impact of editing X"
  ask_codebase        → any open-ended question about the codebase
  get_project_overview→ "give me an overview / what does this project do"
  ingest_codebase     → one-time setup: index a repo directory
"""

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
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("deeprepo-mcp")

_client: Optional["DeepRepoClient"] = None  # type: ignore


def get_client():
    """Get or create the singleton DeepRepo client."""
    global _client
    if _client is None:
        import os
        from deeprepo import DeepRepoClient

        _client = DeepRepoClient(
            embedding_provider_name=os.environ.get("EMBEDDING_PROVIDER"),
            llm_provider_name=os.environ.get("LLM_PROVIDER"),
        )
        logger.info(
            "DeepRepo client initialised — embedding: %s  llm: %s",
            _client.embedding_provider_name,
            _client.llm_provider_name,
        )
    return _client


# ── Tool 1 ─────────────────────────────────────────────────────────────────

@mcp.tool()
def ingest_codebase(path: str, chunk_size: int = 1000, overlap: int = 100) -> str:
    """Index a codebase directory so all other tools can query it.

    Run this once per repo (or after large changes). Scans every supported
    source file, builds a code knowledge graph, generates embeddings, and
    writes wiki pages. Subsequent calls are incremental — unchanged files
    are skipped.

    Args:
        path:       Absolute path to the repo root (e.g. "/home/user/myproject")
        chunk_size: Characters per text chunk (default 1000)
        overlap:    Overlap between consecutive chunks (default 100)

    Returns:
        Summary: files scanned, chunks processed, wiki pages generated.
    """
    client = get_client()
    try:
        result = client.ingest(path, chunk_size=chunk_size, overlap=overlap)
        return (
            f"Ingestion complete for {path}\n"
            f"  Files scanned    : {result.get('files_scanned', 0)}\n"
            f"  Chunks processed : {result.get('chunks_processed', 0)}\n"
            f"  Wiki pages built : {result.get('wiki_generated', 0)}\n"
            f"  Graph nodes      : {result.get('graph_nodes', 0)}\n"
            f"  Branch           : {result.get('branch', 'N/A')}\n"
            f"  {result.get('message', '')}"
        )
    except BranchMismatchError as e:
        return f"Branch mismatch: {e}"
    except Exception as e:
        logger.error("ingest_codebase failed: %s", e)
        return f"Ingestion failed: {e}"


# ── Tool 2 ─────────────────────────────────────────────────────────────────

@mcp.tool()
def find_symbol(name: str) -> str:
    """Find the exact file and line where a class or function is defined.

    Uses the code knowledge graph symbol index — instant lookup, no embedding
    or file reading needed. Use this before opening any file to pinpoint
    exactly where to navigate.

    Cost: ~50 tokens (vs 3 000–10 000 tokens for a raw file read).

    Args:
        name: Class or function name, e.g. "AuthService", "parse_token"

    Returns:
        File path, line number, type, and full signature.

    Examples:
        find_symbol("DeepRepoClient")
        find_symbol("ingest_directory")
        find_symbol("WikiEngine")
    """
    client = get_client()
    try:
        symbol = client.graph_store.get_symbol(name)
        if not symbol:
            return (
                f"'{name}' not found in the symbol index.\n"
                "Check the spelling or run ingest_codebase first."
            )
        return (
            f"Symbol   : {symbol['name']}\n"
            f"Type     : {symbol['type']}\n"
            f"File     : {symbol['filepath']}\n"
            f"Line     : {symbol['line_start']}\n"
            f"Signature: {symbol.get('signature', 'N/A')}\n"
            f"Docstring: {symbol.get('docstring', 'N/A')}"
        )
    except Exception as e:
        logger.error("find_symbol failed: %s", e)
        return f"Symbol lookup failed: {e}"


# ── Tool 3 ─────────────────────────────────────────────────────────────────

@mcp.tool()
def get_file_structure(filepath: str) -> str:
    """Show the public API of a file — all class and function signatures.

    Returns signatures and line numbers without implementation bodies.
    Use this to understand what a file exposes before deciding whether to
    read the full source.

    Cost: ~100–200 tokens (vs 1 000–8 000 tokens for the full file).

    Args:
        filepath: Relative file path, e.g. "src/auth.py", "client.py"

    Returns:
        Every class and function with its signature and line number.

    Examples:
        get_file_structure("deeprepo/wiki.py")
        get_file_structure("src/auth/service.py")
    """
    client = get_client()
    try:
        skeleton = client.graph_store.get_file_skeleton(filepath)
        if not skeleton:
            return (
                f"No structure found for '{filepath}'.\n"
                "The file may not be indexed or contains no classes/functions."
            )
        return f"Structure of '{filepath}':\n\n{skeleton}"
    except Exception as e:
        logger.error("get_file_structure failed: %s", e)
        return f"Failed to get file structure: {e}"


# ── Tool 4 ─────────────────────────────────────────────────────────────────

@mcp.tool()
def explain_file(filepath: str, concise: bool = True) -> str:
    """Explain what a source file does in plain English.

    Returns a structured wiki page: what problem the file solves, its key
    concepts, how its logic works step-by-step, and an architecture diagram.
    Generated at ingest time — no LLM call needed at query time.

    Cost: ~150–400 tokens (vs 1 000–8 000 tokens for raw source).

    Args:
        filepath: Relative file path, e.g. "src/router.py"
        concise:  True (default) for a shorter summary; False for full page

    Returns:
        Plain-English explanation with key concepts and data flow.

    Examples:
        explain_file("deeprepo/client.py")
        explain_file("src/auth/jwt.py")
        explain_file("utils/retry.py", concise=False)
    """
    client = get_client()
    try:
        content = client.wiki_engine.get_page(filepath, concise=concise)
        if not content:
            return (
                f"No explanation found for '{filepath}'.\n"
                "Run ingest_codebase first, or check the file path."
            )
        return content
    except Exception as e:
        logger.error("explain_file failed: %s", e)
        return f"Failed to explain file: {e}"


# ── Tool 5 ─────────────────────────────────────────────────────────────────

@mcp.tool()
def find_change_impact(filepath: str, depth: int = 2) -> str:
    """Find all files that would break or need updating if this file changes.

    Traces the code knowledge graph: importers → their callers → transitive
    dependents. Use this before editing any file to understand the blast
    radius and avoid unintended breakage.

    Cost: ~200–400 tokens (vs manually tracing imports across all files).

    Args:
        filepath: Relative path of the file you plan to change,
                  e.g. "src/models/user.py"
        depth:    How many hops to trace through the dependency graph (default 2)

    Returns:
        Ranked list of affected files with total count.

    Examples:
        find_change_impact("deeprepo/graph.py")
        find_change_impact("src/auth/service.py", depth=3)
    """
    client = get_client()
    try:
        affected = client.graph_store.get_blast_radius(filepath, depth=depth)
        if not affected:
            return (
                f"No dependents found for '{filepath}' (depth={depth}).\n"
                "The file may have no callers, or hasn't been indexed yet."
            )
        lines = [f"Changing '{filepath}' may affect {len(affected)} file(s):\n"]
        for i, fp in enumerate(affected, 1):
            lines.append(f"  {i}. {fp}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("find_change_impact failed: %s", e)
        return f"Impact analysis failed: {e}"


# ── Tool 6 ─────────────────────────────────────────────────────────────────

@mcp.tool()
def ask_codebase(question: str, top_k: int = 5) -> str:
    """Ask any question about the codebase and get an AI-generated answer.

    Automatically detects the intent behind your question and selects the
    minimum context needed — so you never pay for more tokens than necessary:

      "where is X"          → symbol lookup        (~50 tokens)
      "what breaks if…"     → blast radius          (~200 tokens)
      "how does X work"     → wiki + skeleton       (~600 tokens)
      "fix the bug in X"    → full chunk + skeleton (~900 tokens)
      "review X"            → file + neighbours     (~950 tokens)
      general question      → standard RAG          (~2 000 tokens)

    Args:
        question: Any natural-language question about the code
        top_k:    Max vector search results to consider (default 5)

    Returns:
        Answer with intent classification and sources cited.

    Examples:
        ask_codebase("how does the router detect intents?")
        ask_codebase("what is the retry strategy in the LLM call?")
        ask_codebase("where is the embedding cache stored?")
    """
    client = get_client()
    try:
        result = client.query(question, top_k=top_k)
        sources = result.get("sources", [])
        sources_text = (
            "\n".join(f"  {i}. {s}" for i, s in enumerate(sources, 1))
            or "  none"
        )
        return (
            f"Intent   : {result.get('intent', 'general')}\n"
            f"Strategy : {result.get('strategy', 'standard_rag')}\n"
            f"Sources  :\n{sources_text}\n\n"
            f"Answer:\n{result.get('answer', 'No answer generated')}"
        )
    except BranchMismatchError as e:
        return f"Branch mismatch: {e}"
    except Exception as e:
        logger.error("ask_codebase failed: %s", e)
        return f"Query failed: {e}"


# ── Tool 7 ─────────────────────────────────────────────────────────────────

@mcp.tool()
def get_project_overview() -> str:
    """Get a plain-English overview of the entire repository.

    Returns: what the project does, all major modules with one-line summaries,
    the end-to-end data flow, and a feature-area table. Use this at the start
    of a session to orient yourself before diving into specific files.

    Cost: ~400–800 tokens (vs reading every file in the repo).

    Returns:
        Full project homepage: purpose, modules, architecture, where to start.

    Examples:
        get_project_overview()
    """
    client = get_client()
    try:
        overview = client.wiki_engine.get_repo_overview(
            graph_store=client.graph_store
        )
        if not overview:
            return (
                "No overview available yet.\n"
                "Run ingest_codebase first to generate the project wiki."
            )
        return overview
    except Exception as e:
        logger.error("get_project_overview failed: %s", e)
        return f"Failed to get project overview: {e}"


# ── Resources ──────────────────────────────────────────────────────────────

@mcp.resource("deeprepo://config")
def get_config_resource() -> str:
    """Current DeepRepo configuration."""
    import os, json
    return json.dumps({
        "embedding_provider": os.environ.get("EMBEDDING_PROVIDER", "ollama"),
        "llm_provider":       os.environ.get("LLM_PROVIDER", "ollama"),
        "supported_providers": ["openai", "anthropic", "gemini", "ollama", "huggingface"],
    }, indent=2)


# ── Prompts ────────────────────────────────────────────────────────────────

@mcp.prompt()
def start_coding_session(directory: str) -> str:
    """Orient yourself in a codebase before making changes."""
    return (
        f"I'm about to work on the codebase at {directory}.\n\n"
        "1. Call get_project_overview() to understand the project at a high level.\n"
        "2. For any file I mention, call explain_file(filepath) before reading it directly.\n"
        "3. Before editing any file, call find_change_impact(filepath) to see what else might break.\n"
        "4. To locate a specific class or function, use find_symbol(name) instead of searching files.\n"
        "5. For open-ended questions, use ask_codebase(question).\n"
    )


@mcp.prompt()
def plan_code_change(filepath: str) -> str:
    """Build a safe change plan for a given file."""
    return (
        f"I want to change '{filepath}'. Help me plan this safely:\n\n"
        f"1. Call explain_file('{filepath}') to understand what it currently does.\n"
        f"2. Call get_file_structure('{filepath}') to see all functions/classes.\n"
        f"3. Call find_change_impact('{filepath}') to identify what else might break.\n"
        "4. Summarise: what is safe to change, what requires touching other files, "
        "and what tests should be updated.\n"
    )


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    logger.info(
        "DeepRepo MCP server starting — 7 tools: "
        "ingest_codebase, find_symbol, get_file_structure, explain_file, "
        "find_change_impact, ask_codebase, get_project_overview"
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
