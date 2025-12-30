# DeepRepo MCP Server Implementation Plan

This document outlines the complete plan to expose DeepRepo as an **MCP (Model Context Protocol) server**, enabling integration with Cursor, Claude Desktop, Antigravity, and other MCP-compatible AI assistants.

---

## 📖 Understanding MCP

### What is MCP?

The **Model Context Protocol (MCP)** is a standardized protocol created by Anthropic that allows AI assistants to connect to external data sources and tools. Think of it as a "USB-C for AI" — a universal interface that lets any MCP-compatible AI assistant use your tools and data.

### MCP Architecture

```
┌─────────────────┐    MCP Protocol    ┌─────────────────┐
│   AI Assistant  │◄─────────────────►│   MCP Server    │
│  (Cursor, etc)  │   (JSON-RPC over  │  (Your Tool)    │
│                 │    stdio/HTTP)     │                 │
└─────────────────┘                    └─────────────────┘
         │                                      │
         │ "Use deeprepo to query               │
         │  about authentication"               │
         ▼                                      ▼
    AI decides which tool              DeepRepo RAG Engine
    to call & parameters               executes and returns
```

### Core MCP Primitives

| Primitive | Purpose | DeepRepo Mapping |
|-----------|---------|------------------|
| **Tools** | Functions the AI can execute | `ingest()`, `query()`, `clear_history()` |
| **Resources** | Data the AI can read | Vector store stats, ingested chunks |
| **Prompts** | Pre-built templates | Code analysis templates |

---

## 🎯 DeepRepo MCP Design

### Tools to Expose

| Tool Name | Description | Parameters |
|-----------|-------------|------------|
| `ingest_codebase` | Ingest a directory into the vector store | `path: str`, `chunk_size: int`, `overlap: int` |
| `query_codebase` | Query the knowledge base with RAG | `question: str`, `top_k: int` |
| `get_stats` | Get vector store statistics | None |
| `clear_history` | Clear conversation history | None |
| `search_similar` | Find similar code chunks (no LLM) | `query: str`, `top_k: int` |

### Resources to Expose

| Resource URI | Description |
|--------------|-------------|
| `deeprepo://stats` | Current vector store statistics |
| `deeprepo://config` | Current provider configuration |
| `deeprepo://chunks/{index}` | Access individual chunks |

### Prompts to Provide

| Prompt Name | Purpose |
|-------------|---------|
| `analyze_codebase` | Template for codebase analysis |
| `explain_function` | Template for function explanation |
| `find_bugs` | Template for bug detection |

---

## 📁 File Structure

```
deeprepo_core/
├── src/deeprepo/
│   ├── mcp/                    # NEW: MCP module
│   │   ├── __init__.py
│   │   ├── server.py           # Main MCP server
│   │   ├── tools.py            # Tool definitions
│   │   ├── resources.py        # Resource definitions
│   │   └── prompts.py          # Prompt templates
│   └── ... (existing files)
├── pyproject.toml              # Update with MCP deps
└── mcp_server.py               # Entry point script
```

---

## 🛠️ Implementation Steps

### Phase 1: Setup Dependencies

**File: `deeprepo_core/pyproject.toml`**

Add MCP SDK dependency:

```toml
[project]
dependencies = [
    # ... existing deps
]

[project.optional-dependencies]
mcp = [
    "mcp>=1.2.0",
]
```

---

### Phase 2: Create MCP Server

**File: `deeprepo_core/src/deeprepo/mcp/server.py`**

```python
"""DeepRepo MCP Server - Expose DeepRepo as an MCP tool server."""

import logging
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("deeprepo")

# Configure logging (MCP requires stderr, not stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]  # Writes to stderr by default
)
logger = logging.getLogger("deeprepo-mcp")

# Global client instance (lazy loaded)
_client = None

def get_client():
    """Get or create the DeepRepo client instance."""
    global _client
    if _client is None:
        from deeprepo import DeepRepoClient
        _client = DeepRepoClient()
        logger.info("DeepRepo client initialized")
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
        result = client.ingest(path, chunk_size=chunk_size, overlap=overlap)
        return f"""✅ Ingestion Complete!
        
📁 Path: {path}
📊 Chunks processed: {result['chunks_processed']}
📄 Files scanned: {result['files_scanned']}
💾 Storage: {result.get('storage_path', 'vectors.json')}
"""
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return f"❌ Ingestion failed: {str(e)}"


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
        result = client.query(question, top_k=top_k)
        
        # Format sources
        sources = []
        for i, source in enumerate(result.get('sources', []), 1):
            sources.append(f"{i}. {source.get('source', 'Unknown')} (score: {source.get('score', 0):.2f})")
        
        sources_text = "\n".join(sources) if sources else "No sources found"
        
        return f"""📝 Answer:
{result['answer']}

📚 Sources:
{sources_text}
"""
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return f"❌ Query failed: {str(e)}"


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
        # Get embedding for query
        query_embedding = client.embedding_provider.embed(query)
        
        # Search vector store
        results = client.store.search(query_embedding, top_k=top_k)
        
        if not results:
            return "No similar chunks found. Have you ingested any documents?"
        
        output = []
        for i, chunk in enumerate(results, 1):
            output.append(f"""
--- Result {i} (score: {chunk.get('score', 0):.3f}) ---
📄 Source: {chunk.get('source', 'Unknown')}
📍 Lines: {chunk.get('start_line', '?')}-{chunk.get('end_line', '?')}

```
{chunk.get('text', '')[:500]}{'...' if len(chunk.get('text', '')) > 500 else ''}
```
""")
        
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"❌ Search failed: {str(e)}"


@mcp.tool()
def get_stats() -> str:
    """
    Get statistics about the current DeepRepo vector store.
    
    Returns information about how many chunks are stored,
    the embedding dimensions, and other metadata.
    
    Returns:
        Vector store statistics
    """
    client = get_client()
    try:
        stats = client.get_stats()
        return f"""📊 DeepRepo Statistics:

📦 Total chunks: {stats.get('total_chunks', 0)}
📐 Embedding dimension: {stats.get('embedding_dimension', 'N/A')}
💾 Storage file: {stats.get('storage_file', 'N/A')}
🔢 Unique sources: {stats.get('unique_sources', 'N/A')}
"""
    except Exception as e:
        logger.error(f"Stats failed: {e}")
        return f"❌ Failed to get stats: {str(e)}"


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
        return "✅ Conversation history cleared successfully!"
    except Exception as e:
        logger.error(f"Clear history failed: {e}")
        return f"❌ Failed to clear history: {str(e)}"


# ============================================================
# RESOURCES
# ============================================================

@mcp.resource("deeprepo://stats")
def get_stats_resource() -> str:
    """Get current vector store statistics as a resource."""
    client = get_client()
    stats = client.get_stats()
    return str(stats)


@mcp.resource("deeprepo://config")
def get_config_resource() -> str:
    """Get current DeepRepo configuration."""
    import os
    return f"""DeepRepo Configuration:
- LLM Provider: {os.environ.get('LLM_PROVIDER', 'ollama')}
- Storage Path: vectors.json
"""


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


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main():
    """Run the DeepRepo MCP server."""
    logger.info("Starting DeepRepo MCP server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

---

### Phase 3: Create Entry Point Script

**File: `deeprepo_core/mcp_server.py`**

```python
#!/usr/bin/env python3
"""Entry point for DeepRepo MCP server."""

from deeprepo.mcp.server import main

if __name__ == "__main__":
    main()
```

---

### Phase 4: Update pyproject.toml

Add entry point for MCP server:

```toml
[project.scripts]
deeprepo-mcp = "deeprepo.mcp.server:main"
```

---

## 🔧 Client Configuration

### For Cursor

Create/edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "deeprepo": {
      "command": "python",
      "args": ["-m", "deeprepo.mcp.server"],
      "cwd": "/path/to/your/project",
      "env": {
        "LLM_PROVIDER": "ollama"
      }
    }
  }
}
```

### For Claude Desktop

Create/edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "deeprepo": {
      "command": "python",
      "args": ["-m", "deeprepo.mcp.server"],
      "env": {
        "LLM_PROVIDER": "ollama"
      }
    }
  }
}
```

### For Antigravity

Antigravity (this tool) reads MCP configuration from `.gemini/mcp_servers.json` or follows workspace MCP settings.

---

## 🧪 Testing the MCP Server

### 1. Test with MCP Inspector

```bash
# Install MCP inspector
npm install -g @modelcontextprotocol/inspector

# Run inspector with your server
mcp-inspector python -m deeprepo.mcp.server
```

### 2. Manual Testing

```bash
# Start the server directly
python -m deeprepo.mcp.server

# In another terminal, send test commands via stdin
echo '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}' | python -m deeprepo.mcp.server
```

---

## 📊 Expected User Experience

After implementation, users can interact with DeepRepo through their AI assistant:

### Example Interactions

**User:** "Ingest the codebase at /Users/me/myproject"

**AI Assistant:**
> Using the `ingest_codebase` tool...
> 
> ✅ Ingestion Complete!
> 📁 Path: /Users/me/myproject
> 📊 Chunks processed: 234
> 📄 Files scanned: 45

**User:** "How does authentication work in this codebase?"

**AI Assistant:**
> Using the `query_codebase` tool...
> 
> Based on the codebase analysis, authentication is handled by...
> [detailed answer with source references]

---

## ⏱️ Estimated Implementation Time

| Phase | Task | Time |
|-------|------|------|
| Phase 1 | Setup dependencies | 5 min |
| Phase 2 | Create MCP server | 30 min |
| Phase 3 | Create entry point | 5 min |
| Phase 4 | Update pyproject.toml | 5 min |
| Phase 5 | Testing | 20 min |
| **Total** | | **~1 hour** |

---

## 🚀 Next Steps

1. **Review this plan** and confirm you want to proceed
2. **Choose providers** - which LLM provider should be default?
3. **I'll implement** the complete MCP server
4. **Test together** with Cursor or Claude Desktop

---

## 📚 References

- [MCP Documentation](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP Tutorial](https://gofastmcp.com/)
- [MCP Server Examples](https://github.com/modelcontextprotocol/servers)
