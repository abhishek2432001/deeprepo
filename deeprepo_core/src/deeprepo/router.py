"""Intent-based query router for context strategy selection."""

import logging
import re
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """Query intent categories."""
    NAVIGATE = "navigate"   # "where is X defined"
    IMPACT   = "impact"     # "what breaks if I change X"
    EXPLAIN  = "explain"    # "how does X work"
    DEBUG    = "debug"      # "why does X fail / fix bug in X"
    REVIEW   = "review"     # "review / improve X"
    GENERAL  = "general"    # catch-all → standard RAG

INTENT_PATTERNS: list[tuple[Intent, list[str]]] = [
    (Intent.NAVIGATE, [
        r"\bwhere\s+is\b",
        r"\bfind\b.{0,20}\bfunction\b",
        r"\bfind\b.{0,20}\bclass\b",
        r"\bwhich\s+file\b",
        r"\blocate\b",
        r"\bdefined\s+in\b",
    ]),
    (Intent.IMPACT, [
        r"\bwhat\s+(breaks?|changes?|is\s+affected)\b",
        r"\bblast\s+radius\b",
        r"\bdepends?\s+on\b",
        r"\bimpact\b.{0,20}\bchange\b",
        r"\bif\s+I\s+(change|modify|remove|delete|refactor)\b",
        r"\baffect(s|ed)?\b",
    ]),
    (Intent.DEBUG, [
        r"\b(bug|error|exception|traceback|crash)\b",
        r"\bwhy\s+does\b.{0,30}\b(fail|break|not\s+work|wrong)\b",
        r"\bfix\b",
        r"\bnot\s+work(ing)?\b",
        r"\bbroken\b",
        r"\bfails?\b",
    ]),
    (Intent.REVIEW, [
        r"\breview\b",
        r"\bimprove\b",
        r"\brefactor\b",
        r"\bbetter\s+way\b",
        r"\bcode\s+(quality|smell)\b",
        r"\boptimi[sz]e\b",
    ]),
    (Intent.EXPLAIN, [
        r"\bhow\s+does\b",
        r"\bwhat\s+is\b",
        r"\bexplain\b",
        r"\bwhat\s+does\b",
        r"\bdescribe\b",
        r"\bunderstand\b",
        r"\bwalk\s+me\s+through\b",
    ]),
]


class RoutingResult:
    """Container for routing decision and assembled context."""

    def __init__(
        self,
        intent: Intent,
        strategy: str,
        context: str,
        files_used: list[str],
        token_estimate: int,
    ) -> None:
        self.intent = intent
        self.strategy = strategy
        self.context = context
        self.files_used = files_used
        self.token_estimate = token_estimate

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "strategy": self.strategy,
            "files_used": self.files_used,
            "token_estimate": self.token_estimate,
        }


class QueryRouter:
    """Routes queries to optimal context strategies.

    Usage:
        router = QueryRouter()
        intent = router.classify("how does the vector search work")
        result = router.build_context(query, intent, top_chunks, graph_store, wiki_engine)
    """

    def classify(self, query: str) -> Intent:
        """Classify query into an intent.

        Matches against ordered pattern list — first match wins.
        Returns GENERAL if no pattern matches.

        Args:
            query: User query string.

        Returns:
            Matched Intent enum value.
        """
        for intent, patterns in INTENT_PATTERNS:
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    logger.debug("Query classified as %s (matched: %s)", intent.value, pattern)
                    return intent
        return Intent.GENERAL

    def build_context(
        self,
        query: str,
        intent: Intent,
        top_chunks: list[dict[str, Any]],
        graph_store: Any,
        wiki_engine: Any,
    ) -> RoutingResult:
        """Build minimum-sufficient context for the given intent.

        Args:
            query: Original user query.
            intent: Classified intent from .classify().
            top_chunks: Top-k chunks from vector search (always available as fallback).
            graph_store: GraphStore instance (may be None if not indexed).
            wiki_engine: WikiEngine instance (may be None if not initialized).

        Returns:
            RoutingResult with context string and metadata.
        """
        try:
            if intent == Intent.NAVIGATE:
                return self._navigate_strategy(query, top_chunks, graph_store, wiki_engine)
            elif intent == Intent.IMPACT:
                return self._impact_strategy(query, top_chunks, graph_store, wiki_engine)
            elif intent == Intent.EXPLAIN:
                return self._explain_strategy(query, top_chunks, graph_store, wiki_engine)
            elif intent == Intent.DEBUG:
                return self._debug_strategy(query, top_chunks, graph_store, wiki_engine)
            elif intent == Intent.REVIEW:
                return self._review_strategy(query, top_chunks, graph_store, wiki_engine)
            else:
                return self._general_strategy(top_chunks, wiki_engine)
        except Exception as exc:
            logger.warning("Routing strategy failed (%s): %s — falling back to general", intent.value, exc)
            return self._general_strategy(top_chunks, wiki_engine)

    def _navigate_strategy(self, query, chunks, graph_store, wiki_engine) -> RoutingResult:
        """NAVIGATE: extract symbol name, return exact definition location."""
        symbol_match = re.search(r"\b([A-Z][a-zA-Z0-9]+|[a-z_][a-z_0-9]+)\b", query)
        files_used: list[str] = []

        if graph_store and symbol_match:
            name = symbol_match.group(1)
            symbol = graph_store.get_symbol(name)
            if symbol:
                files_used = [symbol["filepath"]]
                context = (
                    f"Symbol found:\n"
                    f"  Name: {symbol['name']}\n"
                    f"  Type: {symbol['type']}\n"
                    f"  File: {symbol['filepath']}:{symbol['line_start']}\n"
                    f"  Signature: {symbol.get('signature', 'N/A')}\n"
                    f"  Docstring: {symbol.get('docstring', 'N/A')}"
                )
                return RoutingResult(Intent.NAVIGATE, "symbol_lookup", context, files_used, 80)

        # Fallback to first chunk
        return self._general_strategy(chunks[:1], wiki_engine, intent=Intent.NAVIGATE)

    def _impact_strategy(self, query, chunks, graph_store, wiki_engine) -> RoutingResult:
        """IMPACT: find blast radius for files mentioned in query."""
        file_mentions = re.findall(r"[\w/]+\.(?:py|js|ts|go|rs|java)", query)
        files_used: list[str] = []
        parts: list[str] = []

        if graph_store and file_mentions:
            for filepath in file_mentions:
                radius = graph_store.get_blast_radius(filepath)
                if radius:
                    files_used.extend(radius)
                    parts.append(f"Files affected by changes to '{filepath}':")
                    for fp in radius:
                        summary = wiki_engine.get_summary(fp) if wiki_engine else ""
                        line = f"  - {fp}"
                        if summary:
                            line += f": {summary[:100]}"
                        parts.append(line)

        if not parts:
            for chunk in chunks[:3]:
                fp = chunk.get("metadata", {}).get("filepath", "")
                if fp and graph_store:
                    radius = graph_store.get_blast_radius(fp)
                    files_used.extend(radius)
                    parts.append(f"Dependents of '{fp}': {', '.join(radius[:5])}")

        context = "\n".join(parts) if parts else self._chunks_to_context(chunks[:3])
        return RoutingResult(Intent.IMPACT, "blast_radius", context, list(set(files_used)), 250)

    def _explain_strategy(self, query, chunks, graph_store, wiki_engine) -> RoutingResult:
        """EXPLAIN: wiki summary + skeleton for top matched files."""
        files_used: list[str] = []
        parts: list[str] = []

        seen: set[str] = set()
        for chunk in chunks[:3]:
            fp = chunk.get("metadata", {}).get("filepath", "")
            if not fp or fp in seen:
                continue
            seen.add(fp)
            files_used.append(fp)

            if wiki_engine:
                page = wiki_engine.get_page(fp)
                if page:
                    parts.append(f"## {fp}\n{page['summary']}")
                    api = page.get("public_api", [])
                    if api:
                        parts.append("Public API:\n" + "\n".join(f"  {s}" for s in api[:5]))

            if graph_store:
                skeleton = graph_store.get_file_skeleton(fp)
                if skeleton:
                    parts.append(f"Structure:\n{skeleton}")

        if not parts:
            return self._general_strategy(chunks, wiki_engine, intent=Intent.EXPLAIN)

        context = "\n\n".join(parts)
        return RoutingResult(Intent.EXPLAIN, "wiki_plus_skeleton", context, files_used, 600)

    def _debug_strategy(self, query, chunks, graph_store, wiki_engine) -> RoutingResult:
        """DEBUG: full top chunk + caller signatures."""
        files_used: list[str] = []
        parts: list[str] = []

        if chunks:
            top = chunks[0]
            fp = top.get("metadata", {}).get("filepath", "")
            if fp:
                files_used.append(fp)

            parts.append(f"## Primary match ({fp}):\n{top.get('text', '')}")

            if graph_store and fp:
                skeleton = graph_store.get_file_skeleton(fp)
                if skeleton:
                    parts.append(f"File structure:\n{skeleton}")

            for chunk in chunks[1:3]:
                fp2 = chunk.get("metadata", {}).get("filepath", "")
                if fp2 and fp2 not in files_used:
                    files_used.append(fp2)
                parts.append(f"## Related ({fp2}):\n{chunk.get('text', '')[:500]}")

        context = "\n\n".join(parts)
        return RoutingResult(Intent.DEBUG, "full_chunk_plus_structure", context, files_used, 900)

    def _review_strategy(self, query, chunks, graph_store, wiki_engine) -> RoutingResult:
        """REVIEW: top matched files + their neighbors' skeletons."""
        files_used: list[str] = []
        parts: list[str] = []

        seen: set[str] = set()
        for chunk in chunks[:2]:
            fp = chunk.get("metadata", {}).get("filepath", "")
            if not fp or fp in seen:
                continue
            seen.add(fp)
            files_used.append(fp)

            parts.append(f"## {fp}:\n{chunk.get('text', '')}")

            if graph_store:
                radius = graph_store.get_blast_radius(fp, depth=1)
                for dep_fp in radius[:3]:
                    if dep_fp not in seen:
                        skeleton = graph_store.get_file_skeleton(dep_fp)
                        if skeleton:
                            parts.append(f"## Dependent: {dep_fp} (skeleton)\n{skeleton}")
                        seen.add(dep_fp)
                        files_used.append(dep_fp)

        context = "\n\n".join(parts)
        return RoutingResult(Intent.REVIEW, "full_plus_neighbor_skeleton", context, files_used, 950)

    def _general_strategy(self, chunks, wiki_engine, intent=Intent.GENERAL) -> RoutingResult:
        """GENERAL: standard RAG chunks with wiki summaries prepended."""
        files_used: list[str] = []
        wiki_parts: list[str] = []
        chunk_parts: list[str] = []
        seen: set[str] = set()

        for chunk in chunks:
            fp = chunk.get("metadata", {}).get("filepath", "")
            score = chunk.get("score", 0)
            chunk_parts.append(f"[{fp}, score={score:.3f}]\n{chunk.get('text', '')}")

            if fp and fp not in seen:
                seen.add(fp)
                files_used.append(fp)
                if wiki_engine:
                    summary = wiki_engine.get_summary(fp)
                    if summary:
                        wiki_parts.append(f"[{fp}]: {summary}")

        parts = []
        if wiki_parts:
            parts.append("File summaries:\n" + "\n".join(wiki_parts))
        parts.extend(chunk_parts)

        context = "\n\n---\n\n".join(parts)
        return RoutingResult(intent, "standard_rag", context, files_used, len(context) // 4)

    def _chunks_to_context(self, chunks: list[dict[str, Any]]) -> str:
        """Helper: flatten chunks into a plain context string."""
        parts = []
        for chunk in chunks:
            fp = chunk.get("metadata", {}).get("filepath", "")
            parts.append(f"[{fp}]\n{chunk.get('text', '')}")
        return "\n\n".join(parts)
