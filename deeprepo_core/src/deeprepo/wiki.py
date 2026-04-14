"""Hierarchical wiki generator: LLM clusters files into feature modules,
generates one concept page per module, rolls up to parent pages and overview.

Optimisations vs v1
-------------------
- tiktoken-based exact token counting (falls back to len//4 if not installed)
- AST-based Python signature extraction + generic regex fallback reduces
  prompt size 50-70% for large files
- Dynamic max_workers (auto-scales with leaf count + CPU)
- LLM clustering result cached in SQLite — skipped when files unchanged
- Parent pages generated in parallel, grouped by depth level
- Dynamic token budget replaces hardcoded 5-file / 10K-char limits
- Two-tier model routing: cheap cluster_provider for grouping,
  full llm_provider for leaf pages
- Retry with exponential back-off + optional fallback provider
- Tiny-module merging (modules < MIN_TOKENS_TO_SPLIT merged into one call)
- progress_callback for real-time reporting
- Automatic parent-page invalidation when a child is regenerated
"""

import ast as _ast
import hashlib
import json
import logging
import os
import re
import shutil
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Token counting ────────────────────────────────────────────────────────────

try:
    import tiktoken as _tiktoken
    _enc = _tiktoken.get_encoding("cl100k_base")

    def _count_tokens(text: str) -> int:
        return len(_enc.encode(text, disallowed_special=()))

except ImportError:
    _tiktoken = None  # type: ignore[assignment]

    def _count_tokens(text: str) -> int:  # type: ignore[misc]
        return len(text) // 4


# ── Constants ─────────────────────────────────────────────────────────────────

# Files with more tokens than this threshold get signature-extracted.
COMPRESS_THRESHOLD_TOKENS = 1_500

# Modules whose combined token count is below this value are eligible
# for merging with adjacent small modules (saves one LLM round-trip).
MIN_TOKENS_TO_SPLIT = 400

# Maximum tokens sent in a single leaf-page LLM call.
MAX_TOKENS_PER_LEAF = 16_000

# Maximum concurrent LLM calls (hard ceiling regardless of cpu_count).
MAX_WORKERS_CEILING = 16

# Retry settings
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0  # seconds; doubles each attempt

# ── Language map ──────────────────────────────────────────────────────────────

EXTENSION_TO_LANGUAGE = {
    ".py": "python", ".md": "markdown", ".sh": "bash", ".json": "json",
    ".yaml": "yaml", ".yml": "yaml", ".java": "java", ".js": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".cpp": "cpp", ".cc": "cpp",
    ".cxx": "cpp", ".hpp": "cpp", ".c": "c", ".h": "c", ".cs": "csharp",
    ".kt": "kotlin", ".kts": "kotlin", ".php": "php", ".rb": "ruby",
    ".rs": "rust", ".go": "go", ".swift": "swift", ".r": "r", ".R": "r",
    ".sql": "sql", ".html": "html", ".css": "css", ".scss": "scss",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini", ".xml": "xml",
}

# ── Prompts ───────────────────────────────────────────────────────────────────

# Mermaid rules injected into every system prompt so the LLM has them
# in memory when it reaches the Architecture Diagram section.
_MERMAID_RULES = """

MERMAID DIAGRAM RULES — follow exactly or the diagram will fail to render:
1. Start with `graph TD` on its own line inside the ```mermaid fence
2. Node IDs: camelCase only — `fileScanner` ✓  `file-scanner` ✗  `file.scanner` ✗  `"file scanner"` ✗
3. Node labels: square brackets only — `nodeId[Label text]` ✓  `nodeId[[Label]]` ✗  `"nodeId"[Label]` ✗
4. Arrows: `-->` only — never `->` `==>` `<--` `-->[label]` `-->|label|`
5. 4–7 nodes maximum, all with REAL names from the actual code (not placeholder names)
6. No subgraphs, no style lines, no click lines, no prose inside the fence"""

LEAF_SYSTEM_PROMPT = (
    "You are a technical writer creating deep-dive wiki pages for a software codebase. "
    "Your audience is someone who has NEVER written code before — a complete beginner, intern, or non-technical stakeholder.\n\n"
    "Your job is to explain EVERY piece of logic in plain English:\n"
    "- What each major function does, step by step, as if explaining to a 10-year-old\n"
    "- Why the code makes each decision (use analogies like \"think of it like a library card catalogue...\")\n"
    "- What happens when something goes wrong\n"
    "- What data looks like at each stage (describe it in words, never copy raw code)\n\n"
    "Do NOT write API reference docs. Do NOT list function signatures. Write flowing prose with examples."
    + _MERMAID_RULES
)

PARENT_SYSTEM_PROMPT = (
    "You are a technical writer creating a deep-dive overview page for a group of related modules. "
    "Your audience is a complete beginner who has never written code.\n\n"
    "Explain how these modules work together as a team, using real-world analogies. "
    "Go deep on the collaboration — who does what, in what order, and why."
    + _MERMAID_RULES
)

REPO_OVERVIEW_SYSTEM_PROMPT = (
    "You are a technical writer creating the homepage for a codebase. "
    "Your audience is someone completely new to the project — possibly non-technical.\n\n"
    "Explain what the project does, why it was built, and how all the pieces fit together. "
    "Use analogies freely. Make it so someone can read this and confidently explain the project to others."
    + _MERMAID_RULES
)

LEAF_USER_PROMPT = """Read the source code below for the `{module_name}` module carefully. Then write a detailed wiki page that a complete beginner — someone who has never written code — can fully understand.

Files in this module:
{file_list}

Module context (where this fits in the overall system):
{module_tree}

Source code to explain:
{file_contents}

---
Write the wiki page using this exact structure. Be thorough — each section should have multiple paragraphs where needed. The goal is that after reading this page, even a non-programmer fully understands how this module works.

# {module_name}

## What is this?
Write 2-3 paragraphs explaining:
- What real-world problem this module solves (use an analogy — "think of this like...")
- Why it needs to exist as its own module (what would break if it wasn't there)
- Who uses this module and when

## Key Concepts
For each important idea or term in this module, write a bullet point that explains it like you're explaining it to a curious 12-year-old. Don't assume any programming knowledge. Include at least 4-6 concepts.

## Step-by-Step: How it Works
Walk through the logic step by step. For EACH major function or piece of logic:
- Give it a plain-English name (e.g. "**The File Scanner**" or "**The Chunker**")
- Explain exactly what it does in 2-4 sentences
- Explain what data goes in and what comes out (describe the data shape in plain English, not code)
- Explain any important decisions or edge cases it handles

Be thorough. If there are 5 functions, explain all 5.

## Data Flow
Describe how data moves through this module from start to finish. Use a concrete example: pick a realistic input (e.g. "imagine you point this at a folder with 3 Python files") and trace exactly what happens to it, step by step, until the module is done with it.

## Error Handling & Edge Cases
Explain what happens when things go wrong:
- What inputs would cause problems and how does the module handle them?
- What are the important limits or constraints?

## System Role
Explain in plain English:
- What other parts of the system call this module and why
- What this module depends on from other modules
- What would break or be impossible without this module

## Architecture Diagram
```mermaid
graph TD
```
Fill in the graph above with the real data flow of `{module_name}`. Use names from the actual code. 4–7 nodes, camelCase IDs, --> arrows only.
"""

PARENT_USER_PROMPT_TEMPLATE = """Read the child module summaries below and write a detailed overview page explaining how these modules work together as a system. Write for a complete beginner.

Module group: `{module_name}`
Child modules: {children_list}

Child module summaries:
{children_summaries}

---
Write the overview page using this structure:

# {module_name}

## What does this group do?
2-3 paragraphs: what capability does this collection of modules provide? Use an analogy to make it concrete.

## The Modules in This Group
For each child module, write a short paragraph (not just a bullet) explaining its specific role. Link each one: [module_name](module_name.md)

## How They Work Together
Write a narrative (4-6 sentences minimum) describing the collaboration step by step: who starts the process, who does what next, how data flows between them, and what the final output is.

## Key Design Decisions
3-5 bullets explaining the important architectural choices made in this area and why they were made that way.

## System Diagram
```mermaid
graph TD
```
Fill in the graph above with how `{module_name}` and its child modules connect. Use real module names. 4–7 nodes, camelCase IDs, --> arrows only.
"""

REPO_OVERVIEW_USER_PROMPT_TEMPLATE = """Read the module summaries below and write a detailed project homepage. Write for someone who has never seen this codebase — possibly non-technical.

Module summaries:
{module_summaries}

---
Write the homepage using this structure:

# Project Overview

## What is this project?
3-4 paragraphs:
- The problem this project solves (use a real-world analogy)
- Who would use this and in what situations
- What you get as output when you use it

## Core Capabilities
For each major capability, write a bullet with a 2-sentence explanation. Don't just list names — explain what each one does and why it's useful.

## How it Works End-to-End
Write a step-by-step narrative (6-10 sentences) walking through the entire process from the moment a user runs the tool to when they get a result. Be concrete: "First, the system scans your code folder and reads every file. Then it breaks each file into small chunks..."

## Feature Areas
| Area | What it does | Key module |
|------|-------------|------------|
Write one row per major module group. The "What it does" column should be a full sentence.

## System Architecture
```mermaid
graph TD
```
Fill in the graph above with the real end-to-end architecture of this project. Use real component names from the module summaries above. 5–8 nodes, camelCase IDs, --> arrows only.

## Where to Start
For 4-5 common tasks a developer or user would want to do, point them to exactly the right module doc with a 1-sentence explanation of why.
"""

CLUSTER_PROMPT = """Group the following source files into logical feature modules for documentation.
Each module should be a cohesive unit. Exclude files that are not essential (tests, configs, docs).

<MODULE_TREE>
{module_tree}
</MODULE_TREE>

<COMPONENTS>
{components}
</COMPONENTS>

Return ONLY a JSON object — no explanation, no markdown, no tags.
Module names must use only letters, digits, and underscores (no spaces, no +, no -, no dots).
Format:
{{
    "module_name": {{
        "path": "relative/path",
        "components": ["file1.py", "file2.py"]
    }}
}}"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_tag(response: str, tag: str) -> str:
    """Extract content between XML-style tags, falling back to full response.

    Still used by clustering code (GROUPED_COMPONENTS). For wiki/overview pages
    the prompts no longer request XML wrapping, so _clean_response() is used
    directly there instead.
    """
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, response, re.DOTALL)
    text = match.group(1).strip() if match else response.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip()
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text


def _clean_response(raw: str) -> str:
    """Strip markdown fences and whitespace from a raw LLM response.

    Used for wiki/overview pages where no XML tag wrapping is expected.
    """
    text = raw.strip()
    # Strip leading markdown code fence (e.g. ```markdown or ```\n)
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip()
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text


def _file_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


def _lang_for_file(filepath: str) -> str:
    return EXTENSION_TO_LANGUAGE.get(Path(filepath).suffix.lower(), "")


# ── Code compression ──────────────────────────────────────────────────────────

def _summarize_function_body(func_node: _ast.AST) -> str:
    """Produce a compact plain-English summary of a function body using AST.

    No LLM is involved — this is a deterministic, zero-cost extraction that
    gives the wiki-generation LLM enough semantic context to explain the
    function even when it has no docstring.

    Extracts:
    - What it returns (variable name or expression type)
    - External calls made (up to 5)
    - Iteration targets (for-loop variables)
    - Exception types raised
    - Key assignments (variables created at the top level of the body)
    - Presence of conditional branching / recursion
    """
    calls: list[str] = []
    returns: list[str] = []
    raises: list[str] = []
    iterates: list[str] = []
    assigns: list[str] = []
    has_branch = False
    has_recursion = False

    fn_name = getattr(func_node, "name", "")

    def _name_of(node: _ast.AST) -> str:
        if isinstance(node, _ast.Name):
            return node.id
        if isinstance(node, _ast.Attribute):
            return f"{_name_of(node.value)}.{node.attr}"
        if isinstance(node, _ast.Constant):
            return repr(node.value)[:20]
        if isinstance(node, _ast.Call):
            return _name_of(node.func)
        if isinstance(node, _ast.Subscript):
            return _name_of(node.value)
        if isinstance(node, _ast.Tuple):
            inner = [_name_of(e) for e in node.elts[:2]]
            return "(" + ", ".join(inner) + ")"
        return ""

    def _walk(node: _ast.AST, depth: int = 0) -> None:
        nonlocal has_branch, has_recursion
        for child in _ast.iter_child_nodes(node):
            if isinstance(child, _ast.Call):
                callee = _name_of(child.func)
                if callee and callee not in calls:
                    calls.append(callee)
                if fn_name and callee == fn_name:
                    has_recursion = True
            elif isinstance(child, _ast.Return) and child.value is not None:
                n = _name_of(child.value)
                if n:
                    returns.append(n)
            elif isinstance(child, _ast.Raise):
                if child.exc is not None:
                    n = _name_of(child.exc)
                    if n:
                        raises.append(n)
            elif isinstance(child, _ast.For):
                iterates.append(_name_of(child.iter))
            elif isinstance(child, (_ast.If, _ast.Match)):
                has_branch = True
            elif isinstance(child, (_ast.Assign, _ast.AnnAssign)) and depth == 0:
                if isinstance(child, _ast.Assign):
                    for t in child.targets:
                        n = _name_of(t)
                        if n:
                            assigns.append(n)
                else:
                    n = _name_of(child.target)
                    if n:
                        assigns.append(n)
            _walk(child, depth + 1)

    body = getattr(func_node, "body", [])
    # Skip docstring node when walking
    start = 1 if (
        body
        and isinstance(body[0], _ast.Expr)
        and isinstance(getattr(body[0], "value", None), _ast.Constant)
    ) else 0
    for stmt in body[start:]:
        _walk(stmt, depth=0)

    parts: list[str] = []

    # Calls (exclude built-ins that add noise)
    _noise = {"print", "len", "str", "int", "float", "bool", "list", "dict",
              "set", "tuple", "range", "enumerate", "zip", "map", "filter",
              "isinstance", "hasattr", "getattr", "setattr", "super"}
    meaningful_calls = [c for c in calls if c.split(".")[0] not in _noise][:5]
    if meaningful_calls:
        parts.append("calls " + ", ".join(meaningful_calls))

    if iterates:
        items = list(dict.fromkeys(iterates))[:3]
        parts.append("iterates over " + ", ".join(items))

    if has_branch:
        parts.append("branches conditionally")

    if has_recursion:
        parts.append("recursive")

    if raises:
        items = list(dict.fromkeys(raises))[:3]
        parts.append("raises " + ", ".join(items))

    if assigns:
        items = list(dict.fromkeys(assigns))[:4]
        parts.append("builds " + ", ".join(items))

    if returns:
        items = list(dict.fromkeys(returns))[:3]
        parts.append("returns " + ", ".join(items))

    return "; ".join(parts) if parts else "implementation omitted"


def _compress_python_ast(content: str) -> str:
    """Compress Python source while preserving full semantic understanding.

    For each function whose body exceeds the threshold, the body is replaced
    with an AST-derived plain-English summary comment so the wiki LLM still
    knows *what* the function does without reading every line.

    Example — undocumented function:
        def _build_inverted_index(tokens, weights):
            # iterates over tokens; builds result; calls sum; returns normalized
            ⋮----

    Example — documented function (docstring kept, body summarised):
        def process(self, text: str) -> list[str]:
            \"\"\"Split text into overlapping chunks.\"\"\"
            # calls re.split, self._chunk; iterates over parts; returns chunks
            ⋮----

    Functions with short bodies (≤ _SHORT_BODY_LINES lines) are sent in full.
    """
    _SHORT_BODY_LINES = 10  # bodies this size or smaller are never compressed

    try:
        tree = _ast.parse(content)
    except SyntaxError:
        return content

    lines = content.split("\n")

    # Map: (skip_start_0idx, skip_end_0idx) → summary string
    replacements: dict[tuple[int, int], str] = {}

    def _process(node: _ast.AST) -> None:
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            if not node.body:
                return

            # Locate docstring boundary
            has_docstring = (
                isinstance(node.body[0], _ast.Expr)
                and isinstance(getattr(node.body[0], "value", None), _ast.Constant)
                and isinstance(node.body[0].value.value, str)  # type: ignore[attr-defined]
            )
            if has_docstring:
                real_body_start_0: int = node.body[0].end_lineno  # 0-indexed = lineno (1-based end)
            else:
                real_body_start_0 = node.body[0].lineno - 1

            node_end_0: int = node.end_lineno - 1  # type: ignore[attr-defined]
            body_lines = node_end_0 - real_body_start_0 + 1

            if body_lines > _SHORT_BODY_LINES:
                summary = _summarize_function_body(node)
                replacements[(real_body_start_0, node_end_0)] = summary

            # Always recurse so nested functions are also handled
            for child in _ast.iter_child_nodes(node):
                _process(child)

        elif isinstance(node, _ast.ClassDef):
            for child in _ast.iter_child_nodes(node):
                _process(child)
        else:
            for child in _ast.iter_child_nodes(node):
                _process(child)

    for node in _ast.iter_child_nodes(tree):
        _process(node)

    if not replacements:
        return content

    # Build skip_set and a marker map: line_idx → (indent, summary)
    skip_set: set[int] = set()
    markers: dict[int, tuple[int, str]] = {}  # line_idx → (indent, summary)

    for (start, end), summary in replacements.items():
        for i in range(start, end + 1):
            skip_set.add(i)
        # Derive indent from the first line of the skipped range
        first_line = lines[start] if start < len(lines) else ""
        indent = len(first_line) - len(first_line.lstrip()) if first_line.strip() else 0
        markers[start] = (indent, summary)

    result: list[str] = []
    for i, line in enumerate(lines):
        if i in skip_set:
            if i in markers:
                indent, summary = markers[i]
                result.append(f"{' ' * indent}# {summary}")
                result.append(f"{' ' * indent}⋮----")
        else:
            result.append(line)

    return "\n".join(result)


def _compress_generic_regex(content: str, lang: str) -> str:
    """Light regex-based compression for non-Python languages.

    Keeps: import/use lines, class/struct/interface/function signatures,
    short lines (≤120 chars), and first line of multi-line blocks.
    Replaces large body blocks with ⋮----.
    """
    lines = content.split("\n")
    result: list[str] = []
    in_block = False
    block_indent = 0
    consecutive_skipped = 0

    sig_patterns = re.compile(
        r"^\s*("
        r"(public|private|protected|static|async|export|default|abstract|override|final|sealed)[\s\w<>\[\]\(\),?:*&|]+\s*[\({]"
        r"|func\s+\w+"
        r"|fn\s+\w+"
        r"|def\s+\w+"
        r"|class\s+\w+"
        r"|struct\s+\w+"
        r"|interface\s+\w+"
        r"|enum\s+\w+"
        r"|type\s+\w+"
        r"|impl\s"
        r"|import\s"
        r"|from\s"
        r"|use\s"
        r"|#include"
        r"|package\s"
        r")"
    )

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # Always keep blank lines
        if not stripped:
            result.append(line)
            consecutive_skipped = 0
            continue

        # Always keep short lines
        if len(line) <= 120:
            result.append(line)
            consecutive_skipped = 0
            continue

        # Keep signature-like lines
        if sig_patterns.match(line):
            result.append(line)
            consecutive_skipped = 0
            continue

        # Long line in a deep block — skip with marker
        if consecutive_skipped == 0:
            result.append(" " * indent + "⋮----")
        consecutive_skipped += 1

    return "\n".join(result)


def _compress_file(filepath: str, content: str) -> str:
    """Compress file content if it exceeds COMPRESS_THRESHOLD_TOKENS.

    Returns the original content unchanged when below the threshold.
    """
    if _count_tokens(content) <= COMPRESS_THRESHOLD_TOKENS:
        return content

    ext = Path(filepath).suffix.lower()
    lang = EXTENSION_TO_LANGUAGE.get(ext, "")

    if ext == ".py":
        compressed = _compress_python_ast(content)
        # Only use compressed version if it's meaningfully smaller
        if _count_tokens(compressed) < _count_tokens(content) * 0.85:
            return compressed
        return content

    if lang in ("javascript", "typescript", "java", "go", "rust", "cpp", "c",
                "csharp", "kotlin", "swift", "php", "ruby"):
        compressed = _compress_generic_regex(content, lang)
        if _count_tokens(compressed) < _count_tokens(content) * 0.85:
            return compressed

    # Final fallback: token-aware truncation
    tokens_target = COMPRESS_THRESHOLD_TOKENS
    lines = content.split("\n")
    result: list[str] = []
    used = 0
    for line in lines:
        lt = _count_tokens(line)
        if used + lt > tokens_target:
            remaining = _count_tokens(content) - used
            result.append(f"\n... ({remaining} more tokens truncated)")
            break
        result.append(line)
        used += lt
    return "\n".join(result)


# ── Module tree helpers ───────────────────────────────────────────────────────

def _format_module_tree(
    module_tree: dict[str, dict],
    highlight: str = "",
    max_lines: int = 80,
) -> str:
    """Format module tree as text. Caps at max_lines to avoid blowing LLM context."""
    lines: list[str] = []

    def _count_modules(tree: dict) -> int:
        count = len(tree)
        for info in tree.values():
            count += _count_modules(info.get("children", {}))
        return count

    total_modules = _count_modules(module_tree)
    # For large trees, emit structure only (no per-file component lists)
    structure_only = total_modules > 30

    def _walk(tree: dict[str, dict], indent: int = 0) -> None:
        for key, value in tree.items():
            if len(lines) >= max_lines:
                if len(lines) == max_lines:
                    lines.append("  ... (truncated)")
                return
            label = f"{key} (current module)" if key == highlight else key
            lines.append(f"{'  ' * indent}{label}")
            if not structure_only:
                by_file: dict[str, list[str]] = defaultdict(list)
                for c in value.get("components", []):
                    if "::" in c:
                        fpath, name = c.split("::", 1)
                        by_file[fpath].append(name)
                    else:
                        by_file[""].append(c)
                for fpath, names in by_file.items():
                    if len(lines) >= max_lines:
                        break
                    prefix = f"{fpath}: " if fpath else ""
                    lines.append(f"{'  ' * (indent + 1)}{prefix}{', '.join(names)}")
            children = value.get("children", {})
            if isinstance(children, dict) and children:
                if not structure_only:
                    lines.append(f"{'  ' * (indent + 1)}Children:")
                _walk(children, indent + 2 if not structure_only else indent + 1)

    _walk(module_tree)
    return "\n".join(lines)


def cluster_by_directory(file_contents: list[tuple[str, str]]) -> dict[str, dict]:
    dir_files: dict[str, list[str]] = defaultdict(list)
    for filepath, _ in file_contents:
        parent = str(Path(filepath).parent)
        dir_files["root" if parent == "." else parent].append(filepath)

    tree: dict[str, dict] = {}
    for dir_path, files in sorted(dir_files.items()):
        module_name = dir_path.replace("/", ".").replace("\\", ".")
        if module_name == ".":
            module_name = "root"
        tree[module_name] = {"path": dir_path, "components": files, "children": {}}

    root_tree: dict[str, dict] = {}
    for mod_name in sorted(tree.keys(), key=lambda k: k.count(".")):
        parts = mod_name.split(".")
        if len(parts) == 1:
            root_tree[mod_name] = tree[mod_name]
        else:
            parent_name = ".".join(parts[:-1])
            if parent_name in tree:
                tree[parent_name]["children"][mod_name] = tree[mod_name]
            else:
                root_tree[mod_name] = tree[mod_name]

    return root_tree if root_tree else tree


def get_processing_order(
    module_tree: dict[str, dict], _prefix: str = ""
) -> list[tuple[int, str]]:
    order: list[tuple[int, str]] = []

    def _walk(tree: dict[str, dict], depth: int) -> None:
        for name, info in tree.items():
            children = info.get("children", {})
            if children:
                _walk(children, depth + 1)
            order.append((depth, name))

    _walk(module_tree, 0)
    order.sort(key=lambda x: -x[0])
    return order


def is_leaf_module(module_info: dict) -> bool:
    return not module_info.get("children", {})


def _build_parent_map(module_tree: dict[str, dict]) -> dict[str, str]:
    """Return {child_name: parent_name} for every non-root module."""
    parent_map: dict[str, str] = {}

    def _walk(tree: dict[str, dict], parent: str | None) -> None:
        for name, info in tree.items():
            if parent is not None:
                parent_map[name] = parent
            children = info.get("children", {})
            if children:
                _walk(children, name)

    _walk(module_tree, None)
    return parent_map


# ── WikiEngine ────────────────────────────────────────────────────────────────

class WikiEngine:
    """Generates concept-level wiki pages: one page per feature module, not per file."""

    def __init__(
        self,
        wiki_dir: str = ".deeprepo/wiki",
        llm_provider: Any = None,
        graph_store: Any = None,
        cluster_provider: Any = None,
    ) -> None:
        self.wiki_dir = wiki_dir
        self.llm_provider = llm_provider
        # cluster_provider: cheap/fast model used only for file grouping.
        # Falls back to llm_provider when not supplied.
        self.cluster_provider = cluster_provider or llm_provider
        self.graph_store = graph_store
        self._cache: dict[str, dict[str, Any]] = {}
        self._load_cache_from_db()

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _load_cache_from_db(self) -> None:
        if self.graph_store is None:
            return
        try:
            conn = self.graph_store._get_conn()
            rows = conn.execute(
                "SELECT filepath, content_md, sha256 FROM wiki_pages"
            ).fetchall()
            for row in rows:
                self._cache[row["filepath"]] = {
                    "filepath": row["filepath"],
                    "summary": self._extract_first_sentence(row["content_md"]),
                    "content_md": row["content_md"],
                    "sha256": row["sha256"],
                }
        except Exception:
            pass

    @staticmethod
    def _extract_first_sentence(md_content: str) -> str:
        for line in md_content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("```"):
                dot = line.find(".")
                if dot > 0:
                    return line[: dot + 1]
                return line[:200]
        return ""

    @staticmethod
    def get_processing_order(module_tree: dict[str, dict]) -> list[tuple[int, str]]:
        return get_processing_order(module_tree)

    def _ensure_wiki_dir(self, subpath: str = "") -> str:
        full_dir = os.path.join(self.wiki_dir, subpath) if subpath else self.wiki_dir
        os.makedirs(full_dir, exist_ok=True)
        return full_dir

    def _write_md_file(self, md_path: str, content: str) -> None:
        os.makedirs(os.path.dirname(md_path), exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _read_md_file(self, md_path: str) -> str | None:
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, FileNotFoundError):
            return None

    def _filepath_to_md_path(self, filepath: str, module_name: str = "") -> str:
        stem = Path(filepath).stem
        parent = Path(filepath).parent
        return os.path.join(self.wiki_dir, str(parent / f"{stem}.md"))

    def _dual_write(
        self,
        filepath: str,
        md_path: str,
        content_md: str,
        module_name: str,
        module_path: str,
        is_leaf: bool,
        sha256: str,
        commit: str | None = None,
    ) -> None:
        self._write_md_file(md_path, content_md)
        if self.graph_store is not None:
            try:
                # Store md_path relative to wiki_dir so the DB is portable
                # across machines regardless of where wiki_dir is located.
                try:
                    rel_md_path = os.path.relpath(md_path, self.wiki_dir)
                except ValueError:
                    rel_md_path = md_path  # Windows cross-drive fallback
                self.graph_store.upsert_wiki_page(
                    filepath=filepath,
                    md_path=rel_md_path,
                    content_md=content_md,
                    module_name=module_name,
                    module_path=module_path,
                    is_leaf=is_leaf,
                    sha256=sha256,
                    commit=commit,
                    token_count=_count_tokens(content_md),
                )
            except Exception as exc:
                logger.warning("Failed to upsert wiki page %s: %s", filepath, exc)
        self._cache[filepath] = {
            "filepath": filepath,
            "summary": self._extract_first_sentence(content_md),
            "content_md": content_md,
            "sha256": sha256,
        }

    # ── LLM call wrapper with retry + fallback ────────────────────────────────

    def _llm_call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider: Any = None,
        fallback_provider: Any = None,
        label: str = "",
    ) -> str:
        """Call an LLM provider with retry and optional fallback.

        Retries on rate-limit and transient errors with exponential back-off.
        On token-limit errors, tries to compress the prompt before retrying.
        If all retries fail, attempts the fallback_provider once.
        """
        p = provider or self.llm_provider
        if p is None:
            raise RuntimeError("No LLM provider configured")

        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                return p.generate(prompt=prompt, system_prompt=system_prompt)
            except Exception as exc:
                err = str(exc).lower()
                last_exc = exc

                is_rate_limit = any(
                    kw in err for kw in ("rate limit", "429", "too many requests", "quota")
                )
                is_token_limit = any(
                    kw in err for kw in ("token", "context length", "maximum context", "max_tokens")
                )

                if is_token_limit and attempt == 0:
                    # Truncate prompt by 30% and retry immediately
                    tokens = _count_tokens(prompt)
                    target = int(tokens * 0.70)
                    lines = prompt.split("\n")
                    kept, used = [], 0
                    for line in lines:
                        lt = _count_tokens(line)
                        if used + lt > target:
                            kept.append(f"\n... (truncated to fit context window)")
                            break
                        kept.append(line)
                        used += lt
                    prompt = "\n".join(kept)
                    logger.warning("%s: token limit hit, retrying with shorter prompt", label)
                    continue

                if is_rate_limit or attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF_BASE ** attempt
                    logger.warning(
                        "%s: attempt %d/%d failed (%s), retrying in %.1fs",
                        label, attempt + 1, _MAX_RETRIES, exc, wait,
                    )
                    time.sleep(wait)
                    continue

                break

        # Try fallback provider once
        if fallback_provider is not None:
            try:
                logger.info("%s: primary provider failed, trying fallback", label)
                return fallback_provider.generate(prompt=prompt, system_prompt=system_prompt)
            except Exception as fb_exc:
                logger.warning("%s: fallback provider also failed: %s", label, fb_exc)

        raise RuntimeError(
            f"{label}: all {_MAX_RETRIES} retries exhausted"
        ) from last_exc

    # ── Cluster caching ───────────────────────────────────────────────────────

    def _cluster_cache_key(self, file_list_hash: str) -> str:
        return f"cluster_cache_{file_list_hash}"

    def _load_cached_clusters(self, file_list_hash: str) -> dict[str, dict] | None:
        if self.graph_store is None:
            return None
        try:
            raw = self.graph_store.get_state(self._cluster_cache_key(file_list_hash))
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def _save_cached_clusters(self, file_list_hash: str, clusters: dict[str, dict]) -> None:
        if self.graph_store is None:
            return
        try:
            self.graph_store.set_state(
                self._cluster_cache_key(file_list_hash),
                json.dumps(clusters),
            )
        except Exception as exc:
            logger.debug("Failed to cache cluster result: %s", exc)

    # ── Leaf page generation ──────────────────────────────────────────────────

    def generate_leaf_page(
        self,
        module_name: str,
        files: list[tuple[str, str]],
        module_tree: dict | None = None,
        commit: str | None = None,
        fallback_provider: Any = None,
    ) -> str | None:
        if self.llm_provider is None:
            return None

        combined = "".join(c for _, c in files)
        sha = _file_sha256(combined)
        tree_text = _format_module_tree(module_tree or {}, highlight=module_name)
        file_list = "\n".join(f"- `{fp}`" for fp, _ in files)

        parts = []
        for fp, content in files:
            lang = _lang_for_file(fp)
            compressed = _compress_file(fp, content)
            parts.append(f"### {fp}\n```{lang}\n{compressed}\n```")

        user_prompt = LEAF_USER_PROMPT.format(
            module_name=module_name,
            file_list=file_list,
            module_tree=tree_text or "(standalone module)",
            file_contents="\n\n".join(parts),
        )

        try:
            raw = self._llm_call(
                prompt=user_prompt,
                system_prompt=LEAF_SYSTEM_PROMPT,
                label=f"leaf:{module_name}",
                fallback_provider=fallback_provider,
            )
            content_md = _clean_response(raw)
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", module_name)
            # Filesystem limit is 255 bytes; cap well below to leave room for path
            if len(safe_name) > 180:
                import hashlib as _hl
                suffix = _hl.sha256(module_name.encode()).hexdigest()[:8]
                safe_name = safe_name[:170] + "_" + suffix
            md_path = os.path.join(self.wiki_dir, f"{safe_name}.md")

            self._dual_write(
                filepath=f"_module_{module_name}",
                md_path=md_path,
                content_md=content_md,
                module_name=module_name,
                module_path=json.dumps([files[0][0]] if files else []),
                is_leaf=True,
                sha256=sha,
                commit=commit,
            )
            for fp, _ in files:
                self._cache[fp] = self._cache.get(f"_module_{module_name}", {})
            return content_md

        except Exception as exc:
            logger.warning("Module wiki generation failed for %s: %s", module_name, exc)
            return None

    # ── LLM clustering ────────────────────────────────────────────────────────

    def _cluster_with_llm(
        self,
        file_contents: list[tuple[str, str]],
        module_tree: dict,
    ) -> dict[str, dict] | None:
        """Ask the LLM to group files into semantic feature modules.

        Uses cluster_provider (cheaper model) when available.
        Result is cached in SQLite keyed by a hash of the file list.
        """
        if self.cluster_provider is None and self.llm_provider is None:
            return None

        # Build a stable hash of the file list (not content — clustering
        # doesn't depend on content, only on which files exist).
        file_list_hash = _file_sha256(
            json.dumps(sorted(fp for fp, _ in file_contents))
        )

        # Check cache first
        cached = self._load_cached_clusters(file_list_hash)
        if cached is not None:
            logger.debug("Using cached LLM clusters (hash %s…)", file_list_hash[:8])
            return cached

        # For large repos, skip LLM clustering — directory fallback is better
        if len(file_contents) > 300:
            logger.info(
                "Repo has %d files — skipping LLM clustering, using directory structure",
                len(file_contents),
            )
            return None

        components_text = "\n".join(
            f"- {fp} ({len(content)} chars)" for fp, content in file_contents
        )
        prompt = CLUSTER_PROMPT.format(
            module_tree=_format_module_tree(module_tree),
            components=components_text,
        )

        provider = self.cluster_provider or self.llm_provider

        try:
            raw = self._llm_call(
                prompt=prompt,
                label="cluster",
                provider=provider,
            )
            # Try multiple extraction strategies for model compatibility
            raw_stripped = raw.strip()

            # 1. XML tag (older prompt format)
            tag_match = re.search(r"<GROUPED_COMPONENTS>(.*?)</GROUPED_COMPONENTS>", raw, re.DOTALL)
            # 2. Fenced JSON block
            fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            # 3. First {...} block in response
            bare_match = re.search(r"\{.*\}", raw, re.DOTALL)

            if tag_match:
                tagged = tag_match.group(1).strip()
            elif fence_match:
                tagged = fence_match.group(1).strip()
            elif bare_match:
                tagged = bare_match.group(0).strip()
            else:
                tagged = raw_stripped

            grouped = json.loads(tagged)
            result: dict[str, dict] = {}
            for mod_name, mod_info in grouped.items():
                if isinstance(mod_info, dict) and "components" in mod_info:
                    # Sanitize module name: only letters, digits, underscores
                    clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", mod_name)
                    result[clean_name] = {
                        "path": mod_info.get("path", mod_name),
                        "components": [c for c in mod_info["components"] if isinstance(c, str)],
                        "children": {},
                    }

            if result:
                self._save_cached_clusters(file_list_hash, result)
                return result

        except Exception as exc:
            logger.warning("LLM clustering failed, falling back to directory: %s", exc)

        return None

    # ── Parent page generation ────────────────────────────────────────────────

    def generate_parent_page(
        self,
        module_name: str,
        module_path: str,
        children_files: list[str],
        module_tree: dict | None = None,
        commit: str | None = None,
        force: bool = False,
        fallback_provider: Any = None,
    ) -> str | None:
        if self.llm_provider is None:
            return None

        children_parts = []
        children_names = []
        for child_fp in children_files:
            child_page = self._cache.get(child_fp)
            stem = Path(child_fp).stem
            children_names.append(f"[{stem}]({stem}.md)")
            if child_page:
                summary = child_page.get("summary", "")
                children_parts.append(f"- **{stem}**: {summary}")

        if not children_parts:
            return None

        children_list = ", ".join(children_names)
        children_summaries = "\n".join(children_parts)
        sha = _file_sha256(children_summaries)

        # Skip if unchanged and not forced
        if not force and not self.needs_update(f"_module_{module_name}", sha):
            return self._cache.get(f"_module_{module_name}", {}).get("content_md")

        user_prompt = PARENT_USER_PROMPT_TEMPLATE.format(
            module_name=module_name,
            children_list=children_list,
            children_summaries=children_summaries,
        )

        try:
            raw = self._llm_call(
                prompt=user_prompt,
                system_prompt=PARENT_SYSTEM_PROMPT,
                label=f"parent:{module_name}",
                fallback_provider=fallback_provider,
            )
            content_md = _clean_response(raw)
            _safe_part = re.sub(r"[^a-zA-Z0-9_]", "_", module_name.split(".")[-1])
            _safe_dir  = "/".join(
                re.sub(r"[^a-zA-Z0-9_]", "_", p) for p in module_path.split(".")
            )
            md_path = os.path.join(self.wiki_dir, _safe_dir, f"{_safe_part}.md")
            self._dual_write(
                filepath=f"_module_{module_name}",
                md_path=md_path,
                content_md=content_md,
                module_name=module_name,
                module_path=json.dumps(module_path.split(".")),
                is_leaf=False,
                sha256=sha,
                commit=commit,
            )
            return content_md

        except Exception as exc:
            logger.warning("Parent wiki generation failed for %s: %s", module_name, exc)
            return None

    def generate_repo_overview(
        self,
        module_tree: dict | None = None,
        commit: str | None = None,
        fallback_provider: Any = None,
    ) -> str | None:
        if self.llm_provider is None:
            return None

        summaries = self.get_all_summaries()
        if not summaries:
            return None

        module_parts = []
        for fp, summary in sorted(summaries.items()):
            doc_ref = f"[{Path(fp).stem}.md]({Path(fp).stem}.md)"
            module_parts.append(f"- **{fp}** ({doc_ref}): {summary}")
        module_summaries = "\n".join(module_parts)

        sha = _file_sha256(module_summaries)
        if not self.needs_update("_overview", sha):
            return self._cache.get("_overview", {}).get("content_md")

        user_prompt = REPO_OVERVIEW_USER_PROMPT_TEMPLATE.format(
            module_summaries=module_summaries,
        )

        try:
            raw = self._llm_call(
                prompt=user_prompt,
                system_prompt=REPO_OVERVIEW_SYSTEM_PROMPT,
                label="overview",
                fallback_provider=fallback_provider,
            )
            content_md = _clean_response(raw)
            md_path = os.path.join(self.wiki_dir, "overview.md")
            self._dual_write(
                filepath="_overview",
                md_path=md_path,
                content_md=content_md,
                module_name="_overview",
                module_path=json.dumps([]),
                is_leaf=False,
                sha256=sha,
                commit=commit,
            )
            return content_md

        except Exception as exc:
            logger.warning("Repo overview generation failed: %s", exc)
            return None

    # ── Bulk generation (main entry point) ────────────────────────────────────

    def bulk_generate(
        self,
        file_contents: list[tuple[str, str]],
        graph_store: Any = None,
        max_workers: int | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
        fallback_provider: Any = None,
    ) -> dict[str, int]:
        """Generate wiki pages: cluster → leaf pages (parallel) → roll-ups → overview.

        Args:
            file_contents: List of (filepath, content) tuples.
            graph_store: Optional GraphStore instance (overrides self.graph_store).
            max_workers: Concurrent LLM calls. Defaults to
                         min(MAX_WORKERS_CEILING, leaf_count, cpu_count * 2).
            progress_callback: Called after each leaf page with
                                (module_name, completed, total).
            fallback_provider: Secondary LLM provider used when primary fails.
        """
        if graph_store is not None:
            self.graph_store = graph_store

        stats: dict[str, Any] = {"generated": 0, "skipped": 0, "failed": 0, "last_error": ""}

        if self.llm_provider is None:
            logger.info("No LLM provider configured — skipping wiki generation")
            return stats

        # ── Step 1: Cluster files into modules ────────────────────────────────
        dir_tree = cluster_by_directory(file_contents)
        llm_clusters = self._cluster_with_llm(file_contents, dir_tree)
        module_tree = llm_clusters if llm_clusters else dir_tree
        logger.info(
            "Using %s clustering (%d modules)",
            "LLM-based" if llm_clusters else "directory-based",
            len(module_tree),
        )

        content_map: dict[str, str] = {fp: c for fp, c in file_contents}
        order = get_processing_order(module_tree)
        parent_map = _build_parent_map(module_tree)

        # ── Step 2: Collect leaf modules, apply token budget + tiny-merge ─────
        leaf_modules: list[tuple[str, list[tuple[str, str]]]] = []
        pending_merge: list[tuple[str, list[tuple[str, str]], int]] = []  # (name, files, tokens)

        def _flush_merge() -> None:
            """Merge accumulated tiny modules into a single leaf entry."""
            if not pending_merge:
                return
            if len(pending_merge) == 1:
                leaf_modules.append((pending_merge[0][0], pending_merge[0][1]))
            else:
                # Use a short hash-based name to avoid filesystem 255-char limit
                names_str = "+".join(n for n, _, _ in pending_merge)
                import hashlib as _hl
                short_hash = _hl.sha256(names_str.encode()).hexdigest()[:8]
                first_name = re.sub(r"[^a-zA-Z0-9_]", "_", pending_merge[0][0])[:40]
                combined_name = f"{first_name}_merged_{short_hash}"
                combined_files: list[tuple[str, str]] = []
                for _, files, _ in pending_merge:
                    combined_files.extend(files)
                leaf_modules.append((combined_name, combined_files))
            pending_merge.clear()

        for _depth, module_name in order:
            module_info = self._find_module(module_tree, module_name)
            if module_info is None or not is_leaf_module(module_info):
                continue

            raw_files = [
                (fp, content_map.get(fp, ""))
                for fp in module_info.get("components", [])
            ]
            if not raw_files:
                continue

            # Compress each file and build token-budget batches
            compressed_files = [(fp, _compress_file(fp, c)) for fp, c in raw_files]
            batches: list[list[tuple[str, str]]] = []
            current_batch: list[tuple[str, str]] = []
            current_tokens = 0

            for fp, compressed in compressed_files:
                t = _count_tokens(compressed)
                if current_tokens + t > MAX_TOKENS_PER_LEAF and current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
                current_batch.append((fp, compressed))
                current_tokens += t

            if current_batch:
                batches.append(current_batch)

            for idx, batch in enumerate(batches):
                if idx == 0:
                    batch_name = module_name
                else:
                    # Name after the primary file in this batch, not a generic counter
                    primary_stem = Path(batch[0][0]).stem
                    batch_name = f"{module_name}.{primary_stem}"
                combined_sha = _file_sha256("".join(c for _, c in batch))

                if not self.needs_update(f"_module_{batch_name}", combined_sha):
                    stats["skipped"] += 1
                    continue

                batch_tokens = sum(_count_tokens(c) for _, c in batch)

                # Tiny-module merging: accumulate small modules
                if batch_tokens < MIN_TOKENS_TO_SPLIT:
                    pending_merge.append((batch_name, batch, batch_tokens))
                    # Flush when accumulated batch would exceed threshold
                    total_pending = sum(t for _, _, t in pending_merge)
                    if total_pending >= MIN_TOKENS_TO_SPLIT:
                        _flush_merge()
                else:
                    _flush_merge()  # flush any pending tiny modules first
                    leaf_modules.append((batch_name, batch))

        _flush_merge()  # flush any remaining tiny modules

        # ── Step 3: Generate leaf pages in parallel ───────────────────────────
        if leaf_modules:
            total = len(leaf_modules)
            effective_workers = min(
                max_workers or MAX_WORKERS_CEILING,
                MAX_WORKERS_CEILING,
                total,
                (os.cpu_count() or 4) * 2,
            )
            logger.info(
                "Generating %d leaf wiki pages with %d workers",
                total, effective_workers,
            )

            # Track which modules were regenerated for parent invalidation
            regenerated_modules: set[str] = set()
            completed = 0

            def _gen_leaf(args: tuple) -> tuple[str, bool, str]:
                mod_name, mod_files = args
                try:
                    result = self.generate_leaf_page(
                        module_name=mod_name,
                        files=mod_files,
                        module_tree=module_tree,
                        fallback_provider=fallback_provider,
                    )
                    return mod_name, result is not None, ""
                except Exception as exc:
                    return mod_name, False, str(exc)

            with ThreadPoolExecutor(max_workers=effective_workers) as executor:
                futures = {
                    executor.submit(_gen_leaf, args): args[0]
                    for args in leaf_modules
                }
                for future in as_completed(futures):
                    mod_name = futures[future]
                    completed += 1
                    try:
                        _, success, err_msg = future.result()
                        if success:
                            stats["generated"] += 1
                            regenerated_modules.add(mod_name)
                            logger.info(
                                "[%d/%d] Generated: %s", completed, total, mod_name
                            )
                        else:
                            stats["failed"] += 1
                            if err_msg:
                                stats["last_error"] = err_msg
                            logger.warning(
                                "[%d/%d] Failed: %s — %s", completed, total, mod_name,
                                err_msg or "generate_leaf_page returned None",
                            )
                    except Exception as exc:
                        stats["failed"] += 1
                        stats["last_error"] = str(exc)
                        logger.warning("Wiki exception for %s: %s", mod_name, exc)
                    finally:
                        if progress_callback is not None:
                            try:
                                progress_callback(mod_name, completed, total)
                            except Exception:
                                pass

            # Determine which parent modules need forced re-generation
            stale_parents: set[str] = set()
            for mod_name in regenerated_modules:
                ancestor = parent_map.get(mod_name)
                while ancestor:
                    stale_parents.add(ancestor)
                    ancestor = parent_map.get(ancestor)
        else:
            regenerated_modules = set()
            stale_parents = set()

        # ── Step 4: Generate parent pages in parallel, depth by depth ─────────
        parent_order = [
            (depth, name)
            for depth, name in order
            if not is_leaf_module(self._find_module(module_tree, name) or {})
        ]

        if parent_order:
            # Group by depth so same-level nodes can be parallelised
            depth_groups: dict[int, list[str]] = defaultdict(list)
            for depth, name in parent_order:
                depth_groups[depth].append(name)

            for depth in sorted(depth_groups.keys()):
                group = depth_groups[depth]

                def _gen_parent(module_name: str) -> tuple[str, bool]:
                    module_info = self._find_module(module_tree, module_name)
                    if module_info is None:
                        return module_name, False
                    children = module_info.get("children", {})
                    children_files: list[str] = []
                    for child_info in children.values():
                        children_files.extend(child_info.get("components", []))
                    if not children_files:
                        return module_name, False
                    force = module_name in stale_parents
                    result = self.generate_parent_page(
                        module_name=module_name,
                        module_path=module_info.get("path", module_name),
                        children_files=children_files,
                        module_tree=module_tree,
                        force=force,
                        fallback_provider=fallback_provider,
                    )
                    return module_name, result is not None

                parent_workers = min(len(group), effective_workers if leaf_modules else 4)
                if parent_workers > 1:
                    with ThreadPoolExecutor(max_workers=parent_workers) as ex:
                        futures_p = {ex.submit(_gen_parent, n): n for n in group}
                        for fut in as_completed(futures_p):
                            n = futures_p[fut]
                            try:
                                _, ok = fut.result()
                                if ok:
                                    stats["generated"] += 1
                            except Exception as exc:
                                logger.warning("Parent page failed for %s: %s", n, exc)
                else:
                    for n in group:
                        _, ok = _gen_parent(n)
                        if ok:
                            stats["generated"] += 1

        # ── Step 5: Repo overview ─────────────────────────────────────────────
        if self.generate_repo_overview(
            module_tree=module_tree, fallback_provider=fallback_provider
        ):
            stats["generated"] += 1

        return stats

    # ── Module lookup ─────────────────────────────────────────────────────────

    def _find_module(self, tree: dict[str, dict], name: str) -> dict | None:
        if name in tree:
            return tree[name]
        for mod_info in tree.values():
            children = mod_info.get("children", {})
            if children and (found := self._find_module(children, name)):
                return found
        return None

    # ── Public query helpers ──────────────────────────────────────────────────

    def needs_update(self, filepath: str, current_sha256: str) -> bool:
        page = self._cache.get(filepath)
        return page is None or page.get("sha256") != current_sha256

    def get_page(self, filepath: str, concise: bool = True) -> str | None:
        page = self._cache.get(filepath)
        if not page:
            return None
        content = page.get("content_md", "")
        if not content:
            return None
        if concise:
            lines = content.split("\n")
            result_lines = []
            heading_count = 0
            for line in lines:
                if line.startswith("## ") and heading_count > 0:
                    break
                if line.startswith("## "):
                    heading_count += 1
                result_lines.append(line)
            result = "\n".join(result_lines).strip()
            return result[:500] if len(result) > 500 else result
        return content

    def get_summary(self, filepath: str) -> str:
        page = self._cache.get(filepath)
        return page.get("summary", "") if page else ""

    def get_all_summaries(self) -> dict[str, str]:
        return {
            fp: page.get("summary", "")
            for fp, page in self._cache.items()
            if page.get("summary") and not fp.startswith("_")
        }

    def invalidate(self, filepath: str) -> None:
        self._cache.pop(filepath, None)
        if self.graph_store:
            try:
                conn = self.graph_store._get_conn()
                conn.execute("DELETE FROM wiki_pages WHERE filepath = ?", (filepath,))
                conn.commit()
            except Exception:
                pass

    def search_wiki(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if self.graph_store is not None:
            try:
                results = self.graph_store.search_wiki_fts(query, limit=limit)
                if results:
                    return [{"filepath": fp, "summary": snippet, "_score": 1} for fp, snippet in results]
            except Exception:
                pass

        query_lower = query.lower()
        results = []
        for filepath, page in self._cache.items():
            score = 0
            summary = page.get("summary", "").lower()
            content = page.get("content_md", "").lower()
            for term in query_lower.split():
                if term in summary:
                    score += 3
                if term in content:
                    score += 1
                if term in filepath.lower():
                    score += 2
            if score > 0:
                results.append({"filepath": filepath, "summary": page.get("summary", ""), "_score": score})
        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:limit]

    def get_repo_overview(self, graph_store: Any = None) -> str:
        overview = self._cache.get("_overview")
        if overview:
            return overview.get("content_md", "")

        overview_path = os.path.join(self.wiki_dir, "overview.md")
        content = self._read_md_file(overview_path)
        if content:
            return content

        summaries = self.get_all_summaries()
        if not summaries:
            return "No wiki pages generated yet. Run ingest_codebase first."

        lines = ["# Repository Overview\n"]
        by_dir: dict[str, list[tuple[str, str]]] = {}
        for filepath, summary in summaries.items():
            by_dir.setdefault(str(Path(filepath).parent), []).append((filepath, summary))

        for directory, files in sorted(by_dir.items()):
            lines.append(f"\n## {directory or 'root'}")
            for filepath, summary in sorted(files):
                lines.append(f"- **{Path(filepath).name}**: {summary}")

        if graph_store is not None:
            try:
                gstats = graph_store.get_stats()
                lines.append(
                    f"\n## Graph Stats\n"
                    f"- {gstats['nodes']} nodes, {gstats['edges']} edges"
                    f" across {gstats['files_indexed']} files"
                )
            except Exception:
                pass

        return "\n".join(lines)

    def get_wiki_dir(self) -> str:
        return os.path.abspath(self.wiki_dir)

    def export_wiki(self, output_dir: str) -> dict[str, int]:
        if not os.path.exists(self.wiki_dir):
            return {"files_copied": 0}
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        shutil.copytree(self.wiki_dir, output_dir)
        return {"files_copied": sum(1 for _ in Path(output_dir).rglob("*.md"))}

    def prune_orphans(self, current_filepaths: set[str]) -> int:
        orphans = [fp for fp in self._cache if fp not in current_filepaths and not fp.startswith("_")]
        for fp in orphans:
            page = self._cache.pop(fp, None)
            if page:
                md_path = self._filepath_to_md_path(fp)
                if os.path.exists(md_path):
                    try:
                        os.remove(md_path)
                    except OSError:
                        pass
        return len(orphans)
