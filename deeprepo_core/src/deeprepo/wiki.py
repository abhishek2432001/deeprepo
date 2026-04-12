"""Hierarchical bottom-up wiki generator with dual-write (files + SQLite)."""

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
from typing import Any

logger = logging.getLogger(__name__)

# Prompts

LEAF_WIKI_PROMPT = """<ROLE>
You are a senior software engineer writing internal developer documentation.
Your task is to create a clear, concise wiki page for a single source file.
</ROLE>

<OBJECTIVES>
1. Help developers quickly understand what this file does without reading all the code.
2. Document the public API so callers know how to use it.
3. Show dependencies so impact analysis is easy.
4. Include a mermaid diagram showing key relationships.
</OBJECTIVES>

<DOCUMENTATION_STRUCTURE>
Create a markdown document with these sections:
1. **Overview** - 2-3 sentences on purpose and role in the system
2. **Responsibilities** - Bullet list of what this module owns
3. **Public API** - Table or list of public functions/classes with brief descriptions
4. **Dependencies** - What this file imports and why
5. **Architecture** - Mermaid diagram (max 6 nodes) showing key relationships
</DOCUMENTATION_STRUCTURE>

<WORKFLOW>
1. Read the file content and skeleton below
2. Identify the core purpose and responsibilities
3. List the public interface (exported functions, classes)
4. Note imports and their purpose
5. Create a simple mermaid diagram
6. Wrap your entire output in <WIKI>...</WIKI> tags
</WORKFLOW>

File: {filepath}
Skeleton:
{skeleton}

Content (first 3000 chars):
{content_preview}
"""

PARENT_WIKI_PROMPT = """<ROLE>
You are a senior software engineer writing module-level documentation.
This module contains sub-modules whose documentation is already written.
</ROLE>

<OBJECTIVES>
1. Provide a high-level overview of what this module/package does.
2. Explain how the sub-modules work together.
3. Reference children docs instead of duplicating their content.
4. Include a mermaid diagram showing module relationships.
</OBJECTIVES>

<DOCUMENTATION_STRUCTURE>
Create a markdown document with:
1. **Overview** - What this module/package provides
2. **Sub-modules** - Brief description of each child with links to their docs
3. **How They Connect** - Data flow and dependencies between children
4. **Architecture** - Mermaid diagram showing sub-module relationships
</DOCUMENTATION_STRUCTURE>

<WORKFLOW>
1. Read the children's documentation summaries below
2. Synthesize a high-level overview
3. Describe relationships between children
4. Create a mermaid diagram of module structure
5. Wrap your entire output in <OVERVIEW>...</OVERVIEW> tags
</WORKFLOW>

Module: {module_name}
Children documentation:
{children_docs}
"""

REPO_OVERVIEW_PROMPT = """<ROLE>
You are a senior software architect writing the top-level README for a codebase.
All module documentation has already been written.
</ROLE>

<OBJECTIVES>
1. Give a developer their first orientation to this codebase.
2. Explain the high-level architecture and design decisions.
3. Show how the main modules connect.
4. Reference module docs for details instead of duplicating.
</OBJECTIVES>

<DOCUMENTATION_STRUCTURE>
Create a markdown document with:
1. **Project Overview** - What this project does (2-3 sentences)
2. **Architecture** - High-level design and key modules
3. **Module Index** - Table of all modules with one-line descriptions and links
4. **Key Design Decisions** - Important patterns and trade-offs
5. **Architecture Diagram** - Mermaid diagram of module relationships
</DOCUMENTATION_STRUCTURE>

<WORKFLOW>
1. Read all module summaries below
2. Identify the main architectural layers
3. Synthesize a project overview
4. Create the module index
5. Draw a high-level architecture diagram
6. Wrap your entire output in <OVERVIEW>...</OVERVIEW> tags
</WORKFLOW>

Repository modules:
{module_summaries}
"""

CLUSTER_PROMPT = """<ROLE>
You are organizing source files into logical modules for documentation.
</ROLE>

<OBJECTIVES>
Group the following source files into logical modules based on their
functionality and relationships. Each module should be a cohesive unit.
</OBJECTIVES>

Components to group:
{components}

Current module tree:
{module_tree}

Return your grouping wrapped in <GROUPED_COMPONENTS>...</GROUPED_COMPONENTS> tags.
Inside the tags, use this JSON format:
{{
    "module_name": {{
        "path": "relative/path",
        "components": ["file1.py", "file2.py"]
    }}
}}
"""


def parse_tag(response: str, tag: str) -> str:
    """Extract content between XML-style tags, falling back to full response."""
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()
    logger.warning("Tag <%s> not found in LLM response, using full text", tag)
    return response.strip()


def _file_sha256(content: str) -> str:
    """Compute SHA-256 of file content."""
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def cluster_by_directory(file_contents: list[tuple[str, str]]) -> dict[str, dict]:
    """Group files into modules by parent directory (zero-LLM clustering)."""
    dir_files: dict[str, list[str]] = defaultdict(list)
    for filepath, _ in file_contents:
        parent = str(Path(filepath).parent)
        if parent == ".":
            parent = "root"
        dir_files[parent].append(filepath)

    tree: dict[str, dict] = {}
    for dir_path, files in sorted(dir_files.items()):
        module_name = dir_path.replace("/", ".").replace("\\", ".")
        if module_name == ".":
            module_name = "root"
        tree[module_name] = {
            "path": dir_path,
            "components": files,
            "children": {},
        }

    root_tree: dict[str, dict] = {}
    sorted_modules = sorted(tree.keys(), key=lambda k: k.count("."))

    for mod_name in sorted_modules:
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
    """Return topological order (leaves first, then parents)."""
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
    """Check if a module has no children."""
    return not module_info.get("children", {})


class WikiEngine:
    """Hierarchical wiki generator with dual-write (files + SQLite)."""

    def __init__(
        self,
        wiki_dir: str = ".deeprepo/wiki",
        llm_provider: Any = None,
        graph_store: Any = None,
    ) -> None:
        self.wiki_dir = wiki_dir
        self.llm_provider = llm_provider
        self.graph_store = graph_store
        self._cache: dict[str, dict[str, Any]] = {}
        self._load_cache_from_db()

    def _load_cache_from_db(self) -> None:
        """Populate in-memory cache from SQLite."""
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
        """Extract first meaningful sentence from markdown."""
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
        """Static method wrapper for module-level function."""
        return get_processing_order(module_tree)


    def _ensure_wiki_dir(self, subpath: str = "") -> str:
        """Create wiki directory structure and return full path."""
        full_dir = os.path.join(self.wiki_dir, subpath) if subpath else self.wiki_dir
        os.makedirs(full_dir, exist_ok=True)
        return full_dir

    def _write_md_file(self, md_path: str, content: str) -> None:
        """Write a markdown file, creating parent dirs as needed."""
        os.makedirs(os.path.dirname(md_path), exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _read_md_file(self, md_path: str) -> str | None:
        """Read a markdown file, return None if missing."""
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, FileNotFoundError):
            return None

    def _filepath_to_md_path(self, filepath: str, module_name: str = "") -> str:
        """Convert source filepath to wiki .md path."""
        stem = Path(filepath).stem
        parent = Path(filepath).parent
        md_rel = str(parent / f"{stem}.md")
        return os.path.join(self.wiki_dir, md_rel)

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
        """Write wiki page to both physical file and SQLite."""
        # Physical .md file
        self._write_md_file(md_path, content_md)

        # SQLite
        if self.graph_store is not None:
            try:
                self.graph_store.upsert_wiki_page(
                    filepath=filepath,
                    md_path=md_path,
                    content_md=content_md,
                    module_name=module_name,
                    module_path=module_path,
                    is_leaf=is_leaf,
                    sha256=sha256,
                    commit=commit,
                    token_count=_estimate_tokens(content_md),
                )
            except Exception as exc:
                logger.warning("Failed to upsert wiki page to SQLite for %s: %s", filepath, exc)

        # In-memory cache
        self._cache[filepath] = {
            "filepath": filepath,
            "summary": self._extract_first_sentence(content_md),
            "content_md": content_md,
            "sha256": sha256,
        }


    def generate_leaf_page(
        self,
        filepath: str,
        content: str,
        skeleton: str = "",
        commit: str | None = None,
    ) -> str | None:
        """Generate wiki page for a single leaf file."""
        if self.llm_provider is None:
            return None

        sha = _file_sha256(content)
        prompt = LEAF_WIKI_PROMPT.format(
            filepath=filepath,
            skeleton=skeleton or "(no skeleton available)",
            content_preview=content[:3000],
        )

        try:
            raw = self.llm_provider.generate(prompt)
            content_md = parse_tag(raw, "WIKI")

            md_path = self._filepath_to_md_path(filepath)
            self._dual_write(
                filepath=filepath,
                md_path=md_path,
                content_md=content_md,
                module_name=Path(filepath).stem,
                module_path=json.dumps([str(Path(filepath).parent)]),
                is_leaf=True,
                sha256=sha,
                commit=commit,
            )
            return content_md

        except Exception as exc:
            logger.warning("Leaf wiki generation failed for %s: %s", filepath, exc)
            return None

    def generate_parent_page(
        self,
        module_name: str,
        module_path: str,
        children_files: list[str],
        commit: str | None = None,
    ) -> str | None:
        """Generate wiki page for a parent module from children's docs."""
        if self.llm_provider is None:
            return None

        children_docs_parts = []
        for child_fp in children_files:
            child_page = self._cache.get(child_fp)
            if child_page:
                summary = child_page.get("summary", "")
                children_docs_parts.append(f"### {child_fp}\n{summary}\n")

        if not children_docs_parts:
            return None

        children_docs = "\n".join(children_docs_parts)
        prompt = PARENT_WIKI_PROMPT.format(
            module_name=module_name,
            children_docs=children_docs,
        )

        try:
            raw = self.llm_provider.generate(prompt)
            content_md = parse_tag(raw, "OVERVIEW")

            md_path = os.path.join(self.wiki_dir, module_path.replace(".", "/"), f"{module_name.split('.')[-1]}.md")
            self._dual_write(
                filepath=f"_module_{module_name}",
                md_path=md_path,
                content_md=content_md,
                module_name=module_name,
                module_path=json.dumps(module_path.split(".")),
                is_leaf=False,
                sha256=_file_sha256(children_docs),
                commit=commit,
            )
            return content_md

        except Exception as exc:
            logger.warning("Parent wiki generation failed for %s: %s", module_name, exc)
            return None

    def generate_repo_overview(self, commit: str | None = None) -> str | None:
        """Generate the top-level repo overview from all module docs."""
        if self.llm_provider is None:
            return None

        summaries = self.get_all_summaries()
        if not summaries:
            return None

        module_parts = []
        for fp, summary in sorted(summaries.items()):
            module_parts.append(f"- **{fp}**: {summary}")
        module_summaries = "\n".join(module_parts)

        prompt = REPO_OVERVIEW_PROMPT.format(module_summaries=module_summaries)

        try:
            raw = self.llm_provider.generate(prompt)
            content_md = parse_tag(raw, "OVERVIEW")

            md_path = os.path.join(self.wiki_dir, "overview.md")
            self._dual_write(
                filepath="_overview",
                md_path=md_path,
                content_md=content_md,
                module_name="_overview",
                module_path=json.dumps([]),
                is_leaf=False,
                sha256=_file_sha256(module_summaries),
                commit=commit,
            )
            return content_md

        except Exception as exc:
            logger.warning("Repo overview generation failed: %s", exc)
            return None


    def bulk_generate(
        self,
        file_contents: list[tuple[str, str]],
        graph_store: Any = None,
        max_workers: int = 3,
    ) -> dict[str, int]:
        """Generate wiki pages hierarchically: leaves → parents → overview."""
        if graph_store is not None:
            self.graph_store = graph_store

        stats = {"generated": 0, "skipped": 0, "failed": 0}

        module_tree = cluster_by_directory(file_contents)

        order = get_processing_order(module_tree)

        content_map = {fp: content for fp, content in file_contents}

        leaf_files = []
        for filepath, content in file_contents:
            sha = _file_sha256(content)
            if not self.needs_update(filepath, sha):
                stats["skipped"] += 1
                continue
            leaf_files.append((filepath, content))

        if leaf_files:
            total = len(leaf_files)
            print(f"[wiki] Generating {total} leaf wiki pages...")

            def _gen_leaf(args: tuple) -> tuple[str, bool]:
                filepath, content = args
                skeleton = ""
                if self.graph_store is not None:
                    try:
                        skeleton = self.graph_store.get_file_skeleton(filepath)
                    except Exception:
                        pass
                result = self.generate_leaf_page(filepath, content, skeleton)
                return filepath, result is not None

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_gen_leaf, args): args[0] for args in leaf_files}
                for i, future in enumerate(as_completed(futures), 1):
                    filepath = futures[future]
                    try:
                        _, success = future.result()
                        if success:
                            stats["generated"] += 1
                            print(f"[wiki] {i}/{total} Generated: {filepath}")
                        else:
                            stats["failed"] += 1
                            print(f"[wiki] {i}/{total} Failed: {filepath}")
                    except Exception as exc:
                        stats["failed"] += 1
                        logger.warning("Wiki generation exception for %s: %s", filepath, exc)

        for depth, module_name in order:
            module_info = self._find_module(module_tree, module_name)
            if module_info is None:
                continue
            if is_leaf_module(module_info):
                continue  # Already handled above

            children = module_info.get("children", {})
            children_files = []
            for child_name, child_info in children.items():
                children_files.extend(child_info.get("components", []))

            if children_files:
                result = self.generate_parent_page(
                    module_name=module_name,
                    module_path=module_info.get("path", module_name),
                    children_files=children_files,
                )
                if result:
                    stats["generated"] += 1

        overview = self.generate_repo_overview()
        if overview:
            stats["generated"] += 1

        return stats

    def _find_module(self, tree: dict[str, dict], name: str) -> dict | None:
        """Recursively find a module in the tree by name."""
        if name in tree:
            return tree[name]
        for mod_name, mod_info in tree.items():
            children = mod_info.get("children", {})
            if children:
                found = self._find_module(children, name)
                if found:
                    return found
        return None


    def needs_update(self, filepath: str, current_sha256: str) -> bool:
        """Return True if the wiki page for filepath is missing or stale."""
        page = self._cache.get(filepath)
        if page is None:
            return True
        return page.get("sha256") != current_sha256

    def get_page(self, filepath: str, concise: bool = True) -> str | None:
        """Return wiki page content for a file."""
        page = self._cache.get(filepath)
        if page is None:
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
        """Return first sentence summary for a file."""
        page = self._cache.get(filepath)
        if page:
            return page.get("summary", "")
        return ""

    def get_all_summaries(self) -> dict[str, str]:
        """Return {filepath: summary} for all cached pages."""
        return {
            fp: page.get("summary", "")
            for fp, page in self._cache.items()
            if page.get("summary") and not fp.startswith("_")
        }

    def invalidate(self, filepath: str) -> None:
        """Remove a file's wiki page from cache and disk."""
        self._cache.pop(filepath, None)
        if self.graph_store:
            try:
                conn = self.graph_store._get_conn()
                conn.execute("DELETE FROM wiki_pages WHERE filepath = ?", (filepath,))
                conn.commit()
            except Exception:
                pass

    def search_wiki(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search wiki pages using FTS5 with keyword fallback."""
        # FTS5
        if self.graph_store is not None:
            try:
                results = self.graph_store.search_wiki_fts(query, limit=limit)
                if results:
                    return [
                        {"filepath": fp, "summary": snippet, "_score": 1}
                        for fp, snippet in results
                    ]
            except Exception:
                pass

        # Keyword fallback over in-memory cache
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
        """Get or generate the repo overview page content."""
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
            directory = str(Path(filepath).parent)
            by_dir.setdefault(directory, []).append((filepath, summary))

        for directory, files in sorted(by_dir.items()):
            lines.append(f"\n## {directory or 'root'}")
            for filepath, summary in sorted(files):
                fname = Path(filepath).name
                lines.append(f"- **{fname}**: {summary}")

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
        """Return the absolute path to the wiki directory."""
        return os.path.abspath(self.wiki_dir)

    def export_wiki(self, output_dir: str) -> dict[str, int]:
        """Copy all wiki .md files to an output directory."""
        if not os.path.exists(self.wiki_dir):
            return {"files_copied": 0}

        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        shutil.copytree(self.wiki_dir, output_dir)

        count = sum(1 for _ in Path(output_dir).rglob("*.md"))
        return {"files_copied": count}

    def prune_orphans(self, current_filepaths: set[str]) -> int:
        """Remove wiki pages for files that no longer exist."""
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
