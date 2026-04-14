# Developer Workflow Guide

How to use DeepRepo in your daily development workflow — from first setup through CI, code review, and AI-IDE integration.

---

## Table of Contents

1. [First-Time Setup](#1-first-time-setup)
2. [Daily Developer Loop](#2-daily-developer-loop)
3. [Using the Wiki Viewer](#3-using-the-wiki-viewer)
4. [AI IDE Integration (MCP)](#4-ai-ide-integration-mcp)
5. [Python API Recipes](#5-python-api-recipes)
6. [Branch Isolation Workflow](#6-branch-isolation-workflow)
7. [Automation & CI Recipes](#7-automation--ci-recipes)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. First-Time Setup

### Install

```bash
cd deeprepo_core
pip install -e ".[mcp]"    # includes MCP server support
```

### Install Ollama (free, local — recommended)

```bash
# macOS
brew install ollama
ollama serve                          # keep this running in a terminal

ollama pull nomic-embed-text          # embedding model (~274 MB)
ollama pull llama3.1:8b               # LLM (~4.7 GB)
```

### Verify

```bash
deeprepo init                         # detects Ollama, prints the ingest command
```

### Index your project

```bash
cd /path/to/your/project
deeprepo ingest .
```

This builds three things in `.deeprepo/`:
- `default.db` — SQLite database (graph, embeddings, wiki index, file state)
- `wiki/` — browsable `.md` files, one per module

**Add `.deeprepo/` to your `.gitignore`** — it's a local cache, not source code.

---

## 2. Daily Developer Loop

### Morning: orient yourself

```bash
deeprepo serve                        # opens http://localhost:8080
# read the overview page, then navigate to files you'll work on today
```

Or from the terminal:
```bash
deeprepo query "what changed recently and what depends on it?"
deeprepo query "how does the auth flow work end-to-end?"
```

### Before editing a file

```bash
# understand what it does
deeprepo query "explain router.py"

# understand what you might break
deeprepo query "what breaks if I change router.py?"
```

### Re-ingest after making changes

```bash
deeprepo ingest .                     # incremental — only changed files are re-processed
```

### End of day: check freshness

```bash
deeprepo status                       # shows stale files vs current branch
```

---

## 3. Using the Wiki Viewer

```bash
deeprepo serve                        # default: http://localhost:8080
deeprepo serve --port 9000            # custom port
deeprepo serve --llm openai           # enable chat with OpenAI
deeprepo serve --llm anthropic --embed openai  # split providers
```

The wiki viewer provides:
- **Module overview page** — what the whole repo does, end-to-end data flow diagram
- **Per-module pages** — plain-English explanation + architecture diagram + key concepts
- **Full-text search** — search across all wiki pages in real time
- **In-page chat** — ask questions, get answers grounded in the wiki

Wiki `.md` files also live at `.deeprepo/wiki/` — you can open them directly in VS Code, Obsidian, or any Markdown viewer.

### Regenerate wiki without re-indexing

```bash
# Re-run LLM wiki generation on already-indexed files (faster than full ingest)
deeprepo wiki .
deeprepo wiki . --workers 5           # parallelise LLM calls
```

---

## 4. AI IDE Integration (MCP)

DeepRepo exposes 7 MCP tools. When connected, your AI assistant calls them automatically when it needs to understand your code — instead of reading raw files and burning tokens.

### Tool selection guide (for CLAUDE.md / system prompts)

| Query pattern | Tool automatically called | Token cost |
|---|---|---|
| "where is X defined" | `find_symbol` | ~50 |
| "show me the API of X" | `get_file_structure` | ~150 |
| "how does X work / explain X" | `explain_file` | ~300 |
| "what breaks if I change X" | `find_change_impact` | ~300 |
| Any open-ended question | `ask_codebase` | ~600–2000 |
| "overview of the project" | `get_project_overview` | ~600 |
| First-time setup | `ingest_codebase` | — |

### Configure Cursor

Create or edit `~/.cursor/mcp.json`:

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

For OpenAI + Anthropic split:

```json
{
  "mcpServers": {
    "deeprepo": {
      "command": "deeprepo-mcp",
      "env": {
        "EMBEDDING_PROVIDER": "openai",
        "LLM_PROVIDER": "anthropic",
        "OPENAI_API_KEY": "sk-...",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

### Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "deeprepo": {
      "command": "deeprepo-mcp",
      "env": {
        "LLM_PROVIDER": "ollama"
      }
    }
  }
}
```

### Add CLAUDE.md to your project

Create `.claude/CLAUDE.md` (or `CLAUDE.md`) at your project root. This tells Claude to prefer DeepRepo tools over raw file reads:

```markdown
## Code navigation with DeepRepo

This project is indexed with DeepRepo. Before reading any source file directly,
use these MCP tools — they are much cheaper in tokens:

- `get_project_overview()` — start here at the beginning of a session
- `find_symbol(name)` — locate a class or function by name
- `get_file_structure(filepath)` — see a file's public API without reading it
- `explain_file(filepath)` — understand what a file does in plain English
- `find_change_impact(filepath)` — always call this before editing a file
- `ask_codebase(question)` — any open-ended question about the code

Only use Read/Grep on a file after the above tools haven't answered your question.
```

### Start a session with the built-in prompt

In Claude Desktop or Cursor, you can trigger the built-in prompt:

```
use the start_coding_session prompt for /path/to/my-project
```

This walks the assistant through: overview → explain relevant files → impact analysis → targeted question answering.

---

## 5. Python API Recipes

### Basic setup

```python
from deeprepo import DeepRepoClient

# Ollama (free, local)
client = DeepRepoClient(provider_name="ollama")

# OpenAI
client = DeepRepoClient(provider_name="openai")   # needs OPENAI_API_KEY

# Split providers — Anthropic LLM + OpenAI embeddings
client = DeepRepoClient(
    embedding_provider_name="openai",
    llm_provider_name="anthropic",
)
```

### Ingest

```python
result = client.ingest("/path/to/project")
# result keys: files_scanned, chunks_processed, graph_nodes, graph_edges,
#              wiki_generated, wiki_skipped, embeddings_stored, message
print(f"Indexed {result['files_scanned']} files")
print(f"Wiki: {result['wiki_generated']} new, {result['wiki_skipped']} cached")
```

### Query

```python
response = client.query("How does the router detect intents?")

# response keys: answer, sources, intent, strategy, retrieval, token_estimate, history
print(response['answer'])
print(f"Intent: {response['intent']}")        # navigate | impact | explain | debug | review | general
print(f"Strategy: {response['strategy']}")    # e.g. wiki_plus_skeleton, blast_radius, symbol_lookup
print(f"Sources: {response['sources']}")      # list[str] — file paths used as context
print(f"Tokens used: {response['token_estimate']}")
```

### Graph API (zero-LLM operations)

```python
# Symbol lookup (~50 tokens equivalent)
symbol = client.graph_store.get_symbol("AuthService")
# {"name": "AuthService", "type": "class", "filepath": "auth/service.py",
#  "line_start": 42, "signature": "class AuthService:", "docstring": "…"}

# File API skeleton (~150 tokens)
skeleton = client.graph_store.get_file_skeleton("auth/service.py")
# "[class] class AuthService: (line 42)\n[function] def login(…): (line 55)\n…"

# Blast-radius analysis
affected = client.graph_store.get_blast_radius("auth/service.py", depth=2)
# ["api/views.py", "tests/test_auth.py", "middleware/auth.py"]

# Graph statistics
stats = client.graph_store.get_stats()
# {"nodes": 252, "edges": 1779, "files": 17}
```

### Wiki API

```python
# Get a module's wiki page
page = client.wiki_engine.get_page("auth/service.py")

# Get the whole-repo overview
overview = client.wiki_engine.get_repo_overview(graph_store=client.graph_store)

# Full-text search across all wiki pages
results = client.wiki_engine.search("authentication flow")
# [{"key": "_module_auth", "content": "…", "score": 0.95}, …]

# Regenerate wiki for all modules
client.wiki_engine.bulk_generate(
    module_map=client.graph_store.get_module_map(),
    workers=4,
)
```

### Freshness check

```python
status = client.get_freshness_status()
# {"branch": "feat/my-feature", "diff_files": 3, "stale_files": ["router.py", …]}
```

### Codebase explorer script

```python
#!/usr/bin/env python3
"""Quick codebase explorer — run: python explore.py /path/to/project"""
import sys
from deeprepo import DeepRepoClient

def explore(path):
    client = DeepRepoClient(provider_name="ollama")
    result = client.ingest(path)
    print(f"Indexed {result['files_scanned']} files\n")

    questions = [
        "What does this project do?",
        "What are the main components?",
        "What's the entry point?",
        "How do I run tests?",
    ]
    for q in questions:
        r = client.query(q)
        print(f"Q: {q}\nA: {r['answer']}\n")

    print("Interactive mode (type 'exit' to quit)")
    while True:
        q = input("You: ")
        if q.lower() in ("exit", "quit"):
            break
        r = client.query(q)
        print(f"A: {r['answer']}")
        if r['sources']:
            print(f"   Sources: {', '.join(r['sources'][:3])}\n")

if __name__ == "__main__":
    explore(sys.argv[1] if len(sys.argv) > 1 else ".")
```

---

## 6. Branch Isolation Workflow

DeepRepo supports per-branch SQLite databases. Feature branches start from the base-branch cache and only re-index changed files.

```bash
# Index main branch
git checkout main
deeprepo ingest . --branch-isolation

# Start feature branch — seeds from main's cache
git checkout -b feat/auth-refactor
deeprepo ingest . --branch-isolation --base-branch main
# Only changed files are re-processed; the rest is inherited from main

# Check status
deeprepo status
```

In Python:

```python
client = DeepRepoClient(
    provider_name="ollama",
    branch_isolation=True,
    base_branches=["main", "develop"],
)
```

Database files created:
- `main` branch → `.deeprepo/main.db`
- `feat/auth-refactor` → `.deeprepo/feat-auth-refactor.db`
- Wiki folders → `.deeprepo/wiki/` (default) and `.deeprepo/feat-auth-refactor-wiki/`

---

## 7. Automation & CI Recipes

### Pre-commit hook — blast-radius check

`.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Warn if changed files have many dependents

CHANGED=$(git diff --cached --name-only | grep '\.py$')
if [ -z "$CHANGED" ]; then exit 0; fi

python3 - <<'EOF'
import subprocess, sys
sys.path.insert(0, "deeprepo_core/src")
from deeprepo import DeepRepoClient

client = DeepRepoClient(provider_name="ollama")
files = subprocess.run(
    ["git", "diff", "--cached", "--name-only"],
    capture_output=True, text=True
).stdout.strip().split("\n")

for f in files:
    if not f.endswith(".py"):
        continue
    affected = client.graph_store.get_blast_radius(f, depth=2)
    if len(affected) > 5:
        print(f"⚠  {f} affects {len(affected)} files: {', '.join(affected[:5])} …")
EOF
```

### CI — freshness report

```python
# ci_freshness_check.py
from deeprepo import DeepRepoClient

client = DeepRepoClient(provider_name="ollama")
status = client.get_freshness_status()

if status["diff_files"] > 0:
    print(f"WARNING: {status['diff_files']} file(s) changed since last ingest:")
    for f in status.get("stale_files", []):
        print(f"  - {f}")
    print("Run: deeprepo ingest .")
```

### Auto-update wiki on merge

```bash
# .github/workflows/wiki.yml (example)
# Run deeprepo ingest after merging to main
# deeprepo ingest . --no-branch-isolation
# Then commit/upload the .deeprepo/wiki/ folder as GitHub Pages
```

### Code review assistant

```python
#!/usr/bin/env python3
"""Blast-radius report for a PR. Usage: python review.py main"""
import subprocess, sys
sys.path.insert(0, "deeprepo_core/src")
from deeprepo import DeepRepoClient

base = sys.argv[1] if len(sys.argv) > 1 else "main"
client = DeepRepoClient(provider_name="ollama")
client.ingest(".")

changed = subprocess.run(
    ["git", "diff", "--name-only", base],
    capture_output=True, text=True
).stdout.strip().split("\n")

print(f"Changed files vs {base}: {len(changed)}\n")
for f in changed:
    if not f:
        continue
    affected = client.graph_store.get_blast_radius(f, depth=2)
    impact = f"({len(affected)} dependents)" if affected else "(no dependents)"
    print(f"  {f}  {impact}")
    for dep in affected[:3]:
        print(f"      → {dep}")
```

---

## 8. Troubleshooting

### "Cannot connect to Ollama"

```bash
ollama serve                           # start the server
ollama list                            # verify models are pulled
ollama pull nomic-embed-text
ollama pull llama3.1:8b
```

### "No documents indexed yet"

```bash
deeprepo ingest .                      # run ingest first
deeprepo status                        # check what's indexed
```

### Ingest is slow

```bash
# Use more parallel wiki workers
deeprepo ingest . --workers 5

# Skip wiki generation if you only need graph/embeddings
deeprepo ingest . --no-wiki

# Regenerate wiki separately after indexing
deeprepo wiki .
```

### Wrong branch database being used

```bash
deeprepo status                        # shows current branch and db path
deeprepo ingest . --no-branch-isolation  # force using default.db
```

### Mermaid diagrams show "Syntax error"

The wiki viewer automatically sanitizes mermaid output from the LLM. If you still see errors:

```bash
# Re-generate wiki pages (forces LLM to regenerate all diagrams)
deeprepo wiki .
```

### Wiki pages show stale content

```bash
# Delete cached pages and regenerate
rm -rf .deeprepo/wiki/
deeprepo wiki .
```

### MCP server not picked up by Cursor

1. Verify the config file path: `~/.cursor/mcp.json`
2. Check that `deeprepo-mcp` is on PATH: `which deeprepo-mcp`
3. Restart Cursor after editing `mcp.json`
4. In Cursor settings → MCP, check the server status indicator

### API key errors

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
# Then re-run deeprepo
```

Or put them in a `.env` file and `source .env` before running.

---

## Quick Reference

```bash
# First time
deeprepo init
deeprepo ingest .

# Daily use
deeprepo serve                                       # wiki viewer + chat
deeprepo query "how does X work?"
deeprepo query "what breaks if I change X?"
deeprepo ingest .                                    # after making changes

# Feature branch
deeprepo ingest . --branch-isolation --base-branch main
deeprepo status

# Faster iteration
deeprepo wiki . --workers 5                          # regen wiki only
deeprepo ingest . --no-wiki                          # graph + embeddings only

# MCP server
deeprepo-mcp                                         # stdio transport for Cursor/Claude Desktop
```
