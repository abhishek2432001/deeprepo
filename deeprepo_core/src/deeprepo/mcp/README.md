# DeepRepo MCP Server

This directory contains the MCP (Model Context Protocol) server implementation for DeepRepo, allowing AI assistants like Cursor, Claude Desktop, and Antigravity to interact with your codebase.

## Quick Start

### 1. Install Dependencies

```bash
# Install deeprepo with MCP support
pip install deeprepo[mcp]

# Or if developing locally
cd deeprepo_core
pip install -e ".[mcp]"
```

### 2. Run the MCP Server

```bash
# Using the CLI command
deeprepo-mcp

# Or run as a Python module
python -m deeprepo.mcp.server

# Or run the entry point script
python mcp_server.py
```

### 3. Configure Your AI Assistant

See the configuration sections below for Cursor, Claude Desktop, and other clients.

---

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `ingest_codebase` | Ingest a directory into the vector store | `path`, `chunk_size`, `overlap` |
| `query_codebase` | Query the knowledge base with RAG | `question`, `top_k` |
| `search_similar` | Find similar code without LLM | `query`, `top_k` |
| `get_stats` | Get vector store statistics | None |
| `clear_history` | Clear conversation history | None |

## Available Resources

| URI | Description |
|-----|-------------|
| `deeprepo://stats` | Current vector store statistics (JSON) |
| `deeprepo://config` | Current configuration (JSON) |

## Available Prompts

| Prompt | Description |
|--------|-------------|
| `analyze_codebase` | Template for comprehensive codebase analysis |
| `explain_function` | Template for explaining a specific function |
| `find_bugs` | Template for bug detection |

---

## Client Configuration

### Cursor

Create or edit `~/.cursor/mcp.json`:

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

### Claude Desktop (macOS)

Create or edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

### Claude Desktop (Windows)

Create or edit `%APPDATA%\Claude\claude_desktop_config.json`:

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

### Antigravity / Gemini

The MCP configuration can be set in `.gemini/mcp_servers.json`:

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

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | AI provider to use | `ollama` |
| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI) | - |
| `GOOGLE_API_KEY` | Google API key (if using Gemini) | - |
| `HF_API_KEY` | HuggingFace API key (if using HuggingFace) | - |

---

## Testing the MCP Server

### Using MCP Inspector

```bash
# Install the MCP inspector
npm install -g @modelcontextprotocol/inspector

# Run inspector with your server
mcp-inspector python -m deeprepo.mcp.server
```

### Manual Testing

```bash
# Start the server and see available tools
python -c "from deeprepo.mcp.server import mcp; print(mcp)"
```

---

## Example Usage

Once configured, you can interact with DeepRepo through your AI assistant:

**User:** "Ingest the codebase at /Users/me/myproject"

**AI:** Using the `ingest_codebase` tool...
> Ingestion Complete!
> Path: /Users/me/myproject
> Chunks processed: 234
> Files scanned: 45

**User:** "How does authentication work in this codebase?"

**AI:** Using the `query_codebase` tool...
> Based on the codebase analysis, authentication is handled by...
> [detailed answer with source references]

---

## Troubleshooting

### Server won't start
1. Ensure Python 3.10+ is installed
2. Verify `mcp` package is installed: `pip install mcp>=1.2.0`
3. Check that DeepRepo is properly installed: `python -c "import deeprepo; print('OK')"`

### LLM not responding
1. For Ollama: Ensure Ollama is running (`ollama serve`)
2. For OpenAI/Gemini: Check API keys are set
3. Check the stderr output for error messages

### Tools not appearing
1. Restart your AI assistant after configuration changes
2. Verify the configuration file path is correct
3. Check the MCP server logs for any errors
