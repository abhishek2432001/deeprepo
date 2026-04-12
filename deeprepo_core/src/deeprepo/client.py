"""DeepRepoClient — main facade for ingestion, graph, wiki, and RAG queries."""

import hashlib
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal

from deeprepo.ingestion import ingest_directory
from deeprepo.providers import get_embedding, get_llm
from deeprepo.interfaces import EmbeddingProvider, LLMProvider
from deeprepo.graph import GraphStore
from deeprepo.graph_builder import GraphBuilder
from deeprepo.wiki import WikiEngine
from deeprepo.router import QueryRouter, Intent

logger = logging.getLogger(__name__)


# Custom exceptions
class StaleBaseError(Exception):
    """Raised when copy-on-write detects a stale base branch cache."""
    pass


class BranchMismatchError(Exception):
    """Raised when the current git branch differs from client's bound branch."""
    pass


# Git helpers

def _git_cmd(*args: str, cwd: str | None = None) -> str | None:
    """Run a git command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _get_current_branch(cwd: str | None = None) -> str | None:
    """Get current git branch name, or short SHA for detached HEAD."""
    branch = _git_cmd("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    if branch == "HEAD":
        # Detached HEAD — use short SHA
        return _git_cmd("rev-parse", "--short", "HEAD", cwd=cwd)
    return branch


def _is_git_repo(cwd: str | None = None) -> bool:
    """Check if the current directory is inside a git repository."""
    return _git_cmd("rev-parse", "--git-dir", cwd=cwd) is not None


def _safe_branch_name(branch: str) -> str:
    """Convert branch name to filesystem-safe string."""
    return branch.replace("/", "-").replace("\\", "-").replace(" ", "-")


class DeepRepoClient:
    """Main client for DeepRepo RAG operations."""

    def __init__(
        self,
        provider_name: str | None = None,
        embedding_provider_name: str | None = None,
        llm_provider_name: str | None = None,
        branch_isolation: bool = True,
        base_branches: list[str] | None = None,
        cluster_strategy: Literal["directory", "llm"] = "directory",
        auto_refresh_base_on_pull: bool = True,
        hierarchical_wiki: bool = True,
        wiki_dir: str = ".deeprepo/wiki",
    ):
        if embedding_provider_name:
            self.embedding_provider_name = embedding_provider_name
        elif provider_name:
            self.embedding_provider_name = provider_name
        else:
            self.embedding_provider_name = os.environ.get(
                "EMBEDDING_PROVIDER",
                os.environ.get("LLM_PROVIDER", "openai")
            )

        if llm_provider_name:
            self.llm_provider_name = llm_provider_name
        elif provider_name:
            self.llm_provider_name = provider_name
        else:
            self.llm_provider_name = os.environ.get("LLM_PROVIDER", "openai")

        self.provider_name = self.llm_provider_name
        self.branch_isolation = branch_isolation
        self.base_branches = base_branches or []
        self.cluster_strategy = cluster_strategy
        self.auto_refresh_base_on_pull = auto_refresh_base_on_pull
        self.hierarchical_wiki = hierarchical_wiki
        self._wiki_dir_base = wiki_dir

        self.embedding_provider: EmbeddingProvider = get_embedding(self.embedding_provider_name)
        self.llm_provider: LLMProvider = get_llm(self.llm_provider_name)

        self._repo_root = self._find_repo_root()
        self.current_branch: str | None = None
        paths = self._resolve_storage_paths()

        self.graph_store = GraphStore(paths["db_path"])
        self.graph_builder = GraphBuilder()

        self.wiki_engine = WikiEngine(
            wiki_dir=paths["wiki_dir"],
            llm_provider=self.llm_provider,
            graph_store=self.graph_store,
        )

        self.router = QueryRouter()

        self.conversation_history: list[dict[str, str]] = []

    def _find_repo_root(self) -> str | None:
        """Find the git repository root directory."""
        root = _git_cmd("rev-parse", "--show-toplevel")
        return root

    def _resolve_storage_paths(self) -> dict[str, str]:
        """Resolve branch-aware storage paths."""
        deeprepo_dir = ".deeprepo"

        if self._repo_root and _is_git_repo(self._repo_root):
            branch = _get_current_branch(self._repo_root)
            self.current_branch = branch
        else:
            self.current_branch = None
            branch = None

        if not self.branch_isolation or branch is None:
            db_path = os.path.join(deeprepo_dir, "default.db")
            wiki_dir = self._wiki_dir_base
            safe_name = "default"
        else:
            safe_name = _safe_branch_name(branch)
            db_path = os.path.join(deeprepo_dir, f"{safe_name}.db")
            wiki_dir = os.path.join(os.path.dirname(self._wiki_dir_base), f"{safe_name}-wiki")

        os.makedirs(deeprepo_dir, exist_ok=True)

        return {
            "branch": branch or "default",
            "db_path": db_path,
            "wiki_dir": wiki_dir,
            "safe_branch_name": safe_name,
        }

    def _check_branch_mismatch(self) -> None:
        """Raise BranchMismatchError if git branch changed since init."""
        if not self.branch_isolation or not self._repo_root:
            return
        current = _get_current_branch(self._repo_root)
        if current and self.current_branch and current != self.current_branch:
            raise BranchMismatchError(
                f"Current branch '{current}' != client's branch '{self.current_branch}'. "
                f"Call client.refresh_branch() to rebind."
            )

    def _maybe_copy_from_base(self) -> str | None:
        """Copy-on-write: seed current branch from base branch cache if available."""
        if not self.branch_isolation or not self.base_branches:
            return None

        paths = self._resolve_storage_paths()
        if os.path.exists(paths["db_path"]):
            return "exists"

        # Find nearest ancestor base
        for base in self.base_branches:
            is_ancestor = _git_cmd(
                "merge-base", "--is-ancestor", base, "HEAD",
                cwd=self._repo_root,
            )
            if is_ancestor is not None:
                base_safe = _safe_branch_name(base)
                base_db = os.path.join(".deeprepo", f"{base_safe}.db")
                base_wiki = os.path.join(
                    os.path.dirname(self._wiki_dir_base), f"{base_safe}-wiki"
                )

                if not os.path.exists(base_db):
                    logger.warning("Base branch '%s' has no cache. Run ingest on base first.", base)
                    continue

                # Check staleness
                base_store = GraphStore(base_db)
                cached_commit = base_store.get_state("last_indexed_commit")
                base_head = _git_cmd("rev-parse", base, cwd=self._repo_root)
                base_store.close()

                if cached_commit and base_head and cached_commit != base_head:
                    raise StaleBaseError(
                        f"Base branch '{base}' cache is stale "
                        f"(cached: {cached_commit[:8]}, current: {base_head[:8]}). "
                        f"Run client.ingest() on '{base}' first to refresh."
                    )

                shutil.copy2(base_db, paths["db_path"])
                if os.path.exists(base_wiki):
                    if os.path.exists(paths["wiki_dir"]):
                        shutil.rmtree(paths["wiki_dir"])
                    shutil.copytree(base_wiki, paths["wiki_dir"])

                logger.info("Copied cache from base '%s' to branch '%s'", base, self.current_branch)
                return "copied"

        return "no_base"

    def refresh_branch(self) -> dict[str, Any]:
        """Rebind client to the current git branch."""
        old_branch = self.current_branch

        self.graph_store.close()

        paths = self._resolve_storage_paths()

        action = self._maybe_copy_from_base() or "reused"

        self.graph_store = GraphStore(paths["db_path"])
        self.wiki_engine = WikiEngine(
            wiki_dir=paths["wiki_dir"],
            llm_provider=self.llm_provider,
            graph_store=self.graph_store,
        )

        return {
            "from": old_branch,
            "to": self.current_branch,
            "action": action,
        }

    def _auto_refresh_bases(self) -> None:
        """Check if base branches have advanced and update their caches."""
        if not self.auto_refresh_base_on_pull or not self.base_branches:
            return

        for base in self.base_branches:
            base_safe = _safe_branch_name(base)
            base_db = os.path.join(".deeprepo", f"{base_safe}.db")

            if not os.path.exists(base_db):
                continue

            base_store = GraphStore(base_db)
            cached_commit = base_store.get_state("last_indexed_commit")
            local_head = _git_cmd("rev-parse", base, cwd=self._repo_root)

            if not cached_commit or not local_head or cached_commit == local_head:
                base_store.close()
                continue

            diff_output = _git_cmd(
                "diff", "--name-only", f"{cached_commit}..{local_head}",
                cwd=self._repo_root,
            )
            if not diff_output:
                base_store.close()
                continue

            changed_files = [f for f in diff_output.split("\n") if f.strip()]

            if len(changed_files) > 200:
                logger.warning(
                    "Base '%s' has %d changed files — too many for delta update. "
                    "Run full ingest on base.",
                    base, len(changed_files),
                )
                base_store.close()
                continue

            logger.info(
                "Auto-refreshing base '%s': %d files changed (%s..%s)",
                base, len(changed_files), cached_commit[:8], local_head[:8],
            )

            for filepath in changed_files:
                content = _git_cmd("show", f"{local_head}:{filepath}", cwd=self._repo_root)
                if content is not None:
                    try:
                        from deeprepo.ingestion import compute_file_hash
                        sha = compute_file_hash(content)
                        if base_store.is_file_changed(filepath, sha):
                            self.graph_builder.parse_and_store_file(
                                filepath, content, base_store
                            )
                    except Exception as exc:
                        logger.warning("Failed to refresh graph for %s: %s", filepath, exc)

            base_store.set_state("last_indexed_commit", local_head)
            base_store.close()

    def _compute_tree_fingerprint(self, file_contents: list[tuple[str, str]]) -> str:
        """SHA-256 of sorted (filepath, file_sha256) pairs."""
        pairs = sorted(
            (fp, hashlib.sha256(c.encode("utf-8", errors="ignore")).hexdigest())
            for fp, c in file_contents
        )
        raw = json.dumps(pairs, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _run_freshness_checks(
        self, file_contents: list[tuple[str, str]]
    ) -> dict[str, Any]:
        """Run 6-layer freshness checks. Return dict with changed files info."""
        current_files = {fp for fp, _ in file_contents}
        content_map = {fp: c for fp, c in file_contents}

        result: dict[str, Any] = {
            "orphans_pruned": 0,
            "tree_match": False,
            "changed_files": [],
            "module_tree_stale": False,
        }

        # Orphan pruning
        if self.graph_store:
            result["orphans_pruned"] = self.graph_store.prune_files(current_files)
            self.wiki_engine.prune_orphans(current_files)

        # Tree fingerprint
        fingerprint = self._compute_tree_fingerprint(file_contents)
        stored_fp = self.graph_store.get_state("tree_fingerprint") if self.graph_store else None
        if stored_fp == fingerprint:
            result["tree_match"] = True
            return result  # Nothing changed — fast return

        # Commit delta fast path
        changed_files = set()
        if self.graph_store:
            last_commit = self.graph_store.get_state("last_indexed_commit")
            if last_commit:
                diff_output = _git_cmd(
                    "diff", "--name-only", f"{last_commit}..HEAD",
                    cwd=self._repo_root,
                )
                if diff_output:
                    changed_files = {f.strip() for f in diff_output.split("\n") if f.strip()}

        # SHA-256 safety net
        for fp, content in file_contents:
            sha = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
            if self.graph_store and self.graph_store.is_file_changed(fp, sha):
                changed_files.add(fp)

        result["changed_files"] = list(changed_files)

        # Module-tree invalidation
        if result["orphans_pruned"] > 0 or len(changed_files) > len(file_contents) * 0.2:
            result["module_tree_stale"] = True

        # Dependency ripple
        if self.graph_store and changed_files:
            importer_files = set()
            for fp in changed_files:
                blast = self.graph_store.get_blast_radius(fp, depth=1)
                importer_files.update(blast)
            if importer_files:
                self.graph_store.mark_wiki_stale(list(importer_files))

        # Store fingerprint
        if self.graph_store:
            self.graph_store.set_state("tree_fingerprint", fingerprint)

        return result

    def ingest(
        self,
        path: str | Path,
        chunk_size: int = 1000,
        overlap: int = 100,
        batch_size: int = 100,
    ) -> dict[str, Any]:
        """Ingest a directory into the knowledge base."""
        self._check_branch_mismatch()
        path = Path(path)

        try:
            self._auto_refresh_bases()
        except Exception as exc:
            logger.warning("Auto-refresh bases failed (non-fatal): %s", exc)

        chunks, file_contents = ingest_directory(path, chunk_size, overlap)

        if not chunks:
            return {
                "chunks_processed": 0,
                "files_scanned": 0,
                "message": "No content found to ingest",
            }

        unique_files = set(chunk["metadata"]["filepath"] for chunk in chunks)

        freshness = {"changed_files": [fp for fp, _ in file_contents], "orphans_pruned": 0}
        try:
            freshness = self._run_freshness_checks(file_contents)
            if freshness.get("tree_match"):
                logger.info("Tree fingerprint unchanged, skipping ingest")
                return {
                    "chunks_processed": 0,
                    "files_scanned": len(unique_files),
                    "message": "No changes detected (tree fingerprint match)",
                    "freshness": freshness,
                }
        except Exception as exc:
            logger.warning("Freshness checks failed (falling back to full ingest): %s", exc)

        changed_files = set(freshness.get("changed_files", []))
        content_map = {fp: c for fp, c in file_contents}

        graph_stats = {"nodes_created": 0, "edges_created": 0, "files_parsed": 0}
        try:
            files_to_build = (
                [(fp, content_map[fp]) for fp in changed_files if fp in content_map]
                if changed_files
                else file_contents
            )
            graph_stats = self.graph_builder.build_from_directory(
                str(path), self.graph_store, files_to_build
            )
            logger.info("Graph: %d nodes, %d edges (%d files parsed)", graph_stats['nodes_created'], graph_stats['edges_created'], graph_stats['files_parsed'])
        except Exception as exc:
            logger.warning("Graph building failed (non-fatal): %s", exc)

        wiki_stats = {"generated": 0, "skipped": 0, "failed": 0}
        try:
            wiki_contents = (
                [(fp, content_map[fp]) for fp in changed_files if fp in content_map]
                if changed_files and len(changed_files) < len(file_contents)
                else file_contents
            )
            wiki_stats = self.wiki_engine.bulk_generate(
                file_contents=wiki_contents,
                graph_store=self.graph_store,
                max_workers=3,
            )
            logger.info("Wiki: %d generated, %d skipped", wiki_stats['generated'], wiki_stats['skipped'])
        except Exception as exc:
            logger.warning("Wiki generation failed (non-fatal): %s", exc)

        embed_count = 0
        try:
            for filepath, _ in file_contents:
                summary = self.wiki_engine.get_summary(filepath)
                if summary:
                    vec = self.embedding_provider.embed(summary)
                    sha = hashlib.sha256(summary.encode()).hexdigest()
                    self.graph_store.upsert_embedding(
                        filepath=filepath,
                        vector=vec,
                        source="wiki_page",
                        sha256=sha,
                    )
                    embed_count += 1
            logger.info("Embeddings: %d file-level embeddings stored", embed_count)
        except Exception as exc:
            logger.warning("Embedding generation failed (non-fatal): %s", exc)

        if self.graph_store:
            head = _git_cmd("rev-parse", "HEAD", cwd=self._repo_root)
            if head:
                self.graph_store.set_state("last_indexed_commit", head)
            if self.current_branch:
                self.graph_store.set_state("branch_name", self.current_branch)

        return {
            "chunks_processed": len(chunks),
            "files_scanned": len(unique_files),
            "graph_nodes": graph_stats.get("nodes_created", 0),
            "graph_edges": graph_stats.get("edges_created", 0),
            "wiki_generated": wiki_stats.get("generated", 0),
            "wiki_skipped": wiki_stats.get("skipped", 0),
            "embeddings_stored": embed_count,
            "orphans_pruned": freshness.get("orphans_pruned", 0),
            "message": f"Successfully ingested {len(unique_files)} files",
        }

    def _find_relevant_files(
        self, question: str, top_k: int = 5
    ) -> tuple[list[dict[str, Any]], str]:
        """Find relevant files using a 3-tier fallback: embeddings → FTS → graph."""
        try:
            query_embedding = self.embedding_provider.embed(question)
            results = self.graph_store.search_embeddings(query_embedding, top_k=top_k)
            if results:
                chunks = [
                    {
                        "text": self.wiki_engine.get_summary(fp) or fp,
                        "metadata": {"filepath": fp},
                        "score": score,
                    }
                    for fp, score in results
                ]
                return chunks, "embeddings"
        except Exception as exc:
            logger.debug("Embedding search unavailable, falling back to FTS: %s", exc)

        try:
            fts_results = self.wiki_engine.search_wiki(question, limit=top_k)
            if fts_results:
                chunks = [
                    {
                        "text": r.get("summary", r.get("filepath", "")),
                        "metadata": {"filepath": r["filepath"]},
                        "score": r.get("_score", 1.0),
                    }
                    for r in fts_results
                ]
                return chunks, "fts"
        except Exception as exc:
            logger.debug("FTS search unavailable, falling back to graph: %s", exc)

        try:
            stats = self.graph_store.get_stats()
            if stats.get("files_indexed", 0) > 0:
                conn = self.graph_store._get_conn()
                rows = conn.execute(
                    "SELECT DISTINCT filepath FROM nodes LIMIT ?", (top_k,)
                ).fetchall()
                if rows:
                    chunks = [
                        {
                            "text": self.wiki_engine.get_summary(r["filepath"]) or r["filepath"],
                            "metadata": {"filepath": r["filepath"]},
                            "score": 0.5,
                        }
                        for r in rows
                    ]
                    return chunks, "graph"
        except Exception as exc:
            logger.debug("Graph fallback failed: %s", exc)

        return [], "none"

    def query(
        self,
        question: str,
        top_k: int = 5,
        include_history: bool = True,
    ) -> dict[str, Any]:
        """Query the knowledge base with RAG."""
        self._check_branch_mismatch()

        top_chunks, retrieval_method = self._find_relevant_files(question, top_k)

        if not top_chunks:
            answer = "I don't have any documents indexed yet. Please ingest some files first."
            return {
                "answer": answer,
                "sources": [],
                "intent": Intent.GENERAL.value,
                "strategy": "none",
                "retrieval": "none",
                "history": self.conversation_history,
            }

        intent = self.router.classify(question)
        routing = self.router.build_context(
            query=question,
            intent=intent,
            top_chunks=top_chunks,
            graph_store=self.graph_store,
            wiki_engine=self.wiki_engine,
        )

        context = routing.context

        if include_history and self.conversation_history:
            history_parts = []
            for exchange in self.conversation_history[-5:]:
                history_parts.append(f"User: {exchange['question']}")
                history_parts.append(f"Assistant: {exchange['answer']}")
            context += "\n\nPrevious conversation:\n" + "\n".join(history_parts)

        answer = self.llm_provider.generate(question, context=context)

        self.conversation_history.append({
            "question": question,
            "answer": answer,
            "sources": routing.files_used,
        })

        return {
            "answer": answer,
            "sources": routing.files_used,
            "intent": intent.value,
            "strategy": routing.strategy,
            "retrieval": retrieval_method,
            "token_estimate": routing.token_estimate,
            "history": self.conversation_history,
        }

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.conversation_history = []

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the knowledge base."""
        graph_stats = {}
        try:
            graph_stats = self.graph_store.get_stats()
        except Exception:
            pass

        wiki_page_count = len(self.wiki_engine._cache)

        return {
            "total_files": graph_stats.get("files_indexed", 0),
            "current_branch": self.current_branch,
            "branch_isolation": self.branch_isolation,
            "base_branches": self.base_branches,
            "embedding_provider": self.embedding_provider_name,
            "llm_provider": self.llm_provider_name,
            "provider": self.llm_provider_name,
            "graph": graph_stats,
            "wiki": {
                "pages": wiki_page_count,
                "wiki_dir": self.wiki_engine.wiki_dir,
            },
            "db_path": self.graph_store.db_path,
        }

    def get_freshness_status(self) -> dict[str, Any]:
        """Return freshness status for the current branch."""
        head = _git_cmd("rev-parse", "HEAD", cwd=self._repo_root)
        last_commit = self.graph_store.get_state("last_indexed_commit") if self.graph_store else None
        fingerprint = self.graph_store.get_state("tree_fingerprint") if self.graph_store else None

        diff_count = 0
        if last_commit and head and last_commit != head:
            diff_output = _git_cmd("diff", "--name-only", f"{last_commit}..{head}", cwd=self._repo_root)
            if diff_output:
                diff_count = len([f for f in diff_output.split("\n") if f.strip()])

        base_status = []
        for base in self.base_branches:
            base_safe = _safe_branch_name(base)
            base_db = os.path.join(".deeprepo", f"{base_safe}.db")
            if os.path.exists(base_db):
                bs = GraphStore(base_db)
                cached = bs.get_state("last_indexed_commit")
                local = _git_cmd("rev-parse", base, cwd=self._repo_root)
                bs.close()
                base_status.append({
                    "branch": base,
                    "cached_commit": cached,
                    "local_commit": local,
                    "stale": cached != local if cached and local else True,
                })
            else:
                base_status.append({"branch": base, "cached_commit": None, "local_commit": None, "stale": True})

        return {
            "current_branch": self.current_branch,
            "base_branches": self.base_branches,
            "base_status": base_status,
            "last_indexed_commit": last_commit,
            "head_commit": head,
            "diff_files": diff_count,
            "tree_fingerprint_stored": fingerprint is not None,
            "module_tree_stale": self.graph_store.get_state("module_tree_stale") == "1" if self.graph_store else False,
        }

    def get_wiki_dir(self) -> str:
        """Return the absolute path to the wiki directory."""
        return self.wiki_engine.get_wiki_dir()

    def export_wiki(self, output_dir: str) -> dict[str, int]:
        """Export wiki files to an output directory."""
        return self.wiki_engine.export_wiki(output_dir)
