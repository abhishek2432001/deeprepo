"""Tree-sitter AST parser and regex fallback for code knowledge graph construction."""

import hashlib
import importlib
import logging
import re
from pathlib import Path
from typing import Any

from deeprepo.graph import GraphStore

logger = logging.getLogger(__name__)

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
}

# Map language name -> (tree-sitter module name, language factory function name)
# Module is imported dynamically as `tree_sitter_{module_name}`.
# The factory function is called on the imported module to get the language object.
LANGUAGE_MODULE_MAP: dict[str, tuple[str, str]] = {
    "python": ("python", "language"),
    "javascript": ("javascript", "language"),
    "jsx": ("javascript", "language"),
    "typescript": ("typescript", "language_typescript"),
    "tsx": ("typescript", "language_tsx"),
    "go": ("go", "language"),
    "rust": ("rust", "language"),
    "java": ("java", "language"),
}

# Per-language regex patterns for fallback parsing.
_PY_FN = re.compile(r"^\s*def\s+(\w+)\s*[\(:]")
_PY_CLS = re.compile(r"^\s*class\s+(\w+)")
_PY_IMP = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)")
_JS_IMP = re.compile(r"""(?:import|require)\s*[\({'"]([\w\./@-]+)""")
_GO_FN = re.compile(r"^\s*func\s+(\w+)")
_RS_FN = re.compile(r"^\s*(?:pub\s+)?fn\s+(\w+)")
_RS_STRUCT = re.compile(r"^\s*(?:pub\s+)?struct\s+(\w+)")
_JAVA_CLS = re.compile(r"^\s*(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?class\s+(\w+)")
_JAVA_FN = re.compile(
    r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(?:\w+\s+)+(\w+)\s*\("
)
_JAVA_IMP = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)")

LANGUAGE_REGEX_MAP: dict[str, dict[str, re.Pattern[str]]] = {
    "python": {
        "function": _PY_FN,
        "class": _PY_CLS,
        "import": _PY_IMP,
    },
    "javascript": {
        "class": _PY_CLS,
        "import": _JS_IMP,
    },
    "typescript": {
        "class": _PY_CLS,
        "import": _JS_IMP,
    },
    "tsx": {
        "class": _PY_CLS,
        "import": _JS_IMP,
    },
    "go": {
        "function": _GO_FN,
        "struct": re.compile(r"^\s*type\s+(\w+)\s+struct"),
        "import": re.compile(r'^\s*"([\w\./]+)"'),
    },
    "rust": {
        "function": _RS_FN,
        "struct": _RS_STRUCT,
        "import": re.compile(r"^\s*use\s+([\w:]+)"),
    },
    "java": {
        "function": _JAVA_FN,
        "class": _JAVA_CLS,
        "import": _JAVA_IMP,
    },
}

def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


class GraphBuilder:
    """Parses source files into graph nodes and edges using tree-sitter or regex."""

    def __init__(self) -> None:
        self._parsers: dict[str, Any] = {}
        self._ts_available = self._check_tree_sitter()

    def _check_tree_sitter(self) -> bool:
        """Return True if tree-sitter core package is importable."""
        try:
            import tree_sitter  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "tree-sitter not installed. Using regex fallback for graph building. "
                "Install with: pip install 'deeprepo[graph]'"
            )
            return False

    def _get_parser(self, language: str) -> Any | None:
        """Lazily load and cache a Tree-sitter parser for a language."""
        if not self._ts_available:
            return None

        if language in self._parsers:
            return self._parsers[language]

        try:
            from tree_sitter import Language, Parser

            entry = LANGUAGE_MODULE_MAP.get(language)
            if entry is None:
                self._parsers[language] = None
                return None

            module_name, factory_fn = entry
            ts_mod = importlib.import_module(f"tree_sitter_{module_name}")
            lang_obj = Language(getattr(ts_mod, factory_fn)())

            parser = Parser()
            try:
                parser.language = lang_obj
            except AttributeError:
                # Older tree-sitter API
                parser.set_language(lang_obj)
            self._parsers[language] = parser
            return parser

        except Exception as exc:
            logger.debug("Could not load tree-sitter parser for %s: %s", language, exc)
            self._parsers[language] = None
            return None

    def parse_file(
        self, filepath: str, content: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Parse a source file into graph nodes and edges.

        Args:
            filepath: Relative file path (used for metadata).
            content: Full file content as a string.

        Returns:
            Tuple of (nodes, edges). Each node is a dict with keys:
                name, type, line_start, line_end, signature, docstring.
            Each edge is a dict with keys:
                src_name, dst_name, dst_file, edge_type.
        """
        suffix = Path(filepath).suffix.lower()
        language = LANGUAGE_MAP.get(suffix)

        if language:
            parser = self._get_parser(language)
            if parser is not None:
                try:
                    return self._parse_with_tree_sitter(parser, language, filepath, content)
                except Exception as exc:
                    logger.warning("Tree-sitter parse failed for %s: %s - using regex", filepath, exc)

        return self._parse_with_regex(filepath, content)

    def build_from_directory(
        self, root: str, store: GraphStore, file_contents: list[tuple[str, str]]
    ) -> dict[str, int]:
        """Parse all files and save to graph store.

        Only re-parses files whose SHA-256 hash has changed.

        Args:
            root: Root directory path (used for display only).
            store: GraphStore to write results into.
            file_contents: List of (relative_filepath, content) tuples.

        Returns:
            Dict with: files_parsed, files_skipped, nodes_created, edges_created.
        """
        stats = {"files_parsed": 0, "files_skipped": 0, "nodes_created": 0, "edges_created": 0}

        for filepath, content in file_contents:
            sha = _sha256(content)
            if not store.is_file_changed(filepath, sha):
                stats["files_skipped"] += 1
                continue

            try:
                nodes, edges = self.parse_file(filepath, content)
                store.save_file_nodes(filepath, nodes, edges)
                store.update_file_hash(filepath, sha)
                stats["files_parsed"] += 1
                stats["nodes_created"] += len(nodes)
                stats["edges_created"] += len(edges)
            except Exception as exc:
                logger.warning("Graph build failed for %s: %s", filepath, exc)

        return stats

    def _parse_with_tree_sitter(
        self, parser: Any, language: str, filepath: str, content: str
    ) -> tuple[list[dict], list[dict]]:
        """Extract nodes and edges using Tree-sitter AST."""
        tree = parser.parse(bytes(content, "utf-8"))
        root_node = tree.root_node
        lines = content.splitlines()

        nodes: list[dict] = []
        edges: list[dict] = []

        walker_map: dict[str, Any] = {
            "python": self._walk_python,
            "javascript": self._walk_js_ts,
            "jsx": self._walk_js_ts,
            "typescript": self._walk_js_ts,
            "tsx": self._walk_js_ts,
            "go": self._walk_go_rust,
            "rust": self._walk_go_rust,
            "java": self._walk_java,
        }
        walker = walker_map.get(language, self._walk_generic)
        walker(root_node, lines, filepath, nodes, edges)

        return nodes, edges

    def _walk_python(self, node: Any, lines: list[str], filepath: str, nodes: list, edges: list) -> None:
        """Walk Python AST for functions, classes, imports."""
        for child in node.children:
            if child.type == "function_definition":
                name_node = child.child_by_field_name("name")
                params_node = child.child_by_field_name("parameters")
                if name_node:
                    name = name_node.text.decode("utf-8")
                    params = params_node.text.decode("utf-8") if params_node else "()"
                    return_type = ""
                    ret_node = child.child_by_field_name("return_type")
                    if ret_node:
                        return_type = " -> " + ret_node.text.decode("utf-8").lstrip(": ")
                    sig = f"def {name}{params}{return_type}:"
                    docstring = self._extract_python_docstring(child)
                    nodes.append({
                        "name": name,
                        "type": "function",
                        "line_start": child.start_point[0] + 1,
                        "line_end": child.end_point[0] + 1,
                        "signature": sig,
                        "docstring": docstring,
                    })
                    body = child.child_by_field_name("body")
                    if body:
                        self._extract_python_calls(body, name, edges)

            elif child.type == "class_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8")
                    # Superclasses
                    bases = ""
                    args_node = child.child_by_field_name("superclasses")
                    if args_node:
                        bases = args_node.text.decode("utf-8")
                    sig = f"class {name}{bases}:"
                    nodes.append({
                        "name": name,
                        "type": "class",
                        "line_start": child.start_point[0] + 1,
                        "line_end": child.end_point[0] + 1,
                        "signature": sig,
                        "docstring": None,
                    })
                    # Recurse into class body
                    body = child.child_by_field_name("body")
                    if body:
                        self._walk_python(body, lines, filepath, nodes, edges)

            elif child.type in ("import_statement", "import_from_statement"):
                self._extract_python_imports(child, nodes, edges)

            else:
                self._walk_python(child, lines, filepath, nodes, edges)

    @staticmethod
    def _clean_docstring(raw: str) -> str | None:
        """Clean a raw docstring by stripping delimiters, whitespace, and blank lines."""
        import textwrap

        for delim in ('"""', "'''"):
            if raw.startswith(delim) and raw.endswith(delim):
                raw = raw[3:-3]
                break

        text = textwrap.dedent(raw)

        cleaned_lines: list[str] = []
        prev_blank = False
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                if cleaned_lines and not prev_blank:
                    cleaned_lines.append("")
                prev_blank = True
            else:
                cleaned_lines.append(stripped)
                prev_blank = False

        # Trim trailing blank entries
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()

        result = "\n".join(cleaned_lines).strip()
        return result[:200] if result else None

    def _extract_python_docstring(self, func_node: Any) -> str | None:
        """Extract and clean the docstring from a Python function node."""
        try:
            body = func_node.child_by_field_name("body")
            if body and body.children:
                first = body.children[0]
                if first.type == "expression_statement" and first.children:
                    expr = first.children[0]
                    if expr.type == "string":
                        return self._clean_docstring(expr.text.decode("utf-8"))
        except Exception:
            pass
        return None

    def _extract_python_calls(self, body_node: Any, src_name: str, edges: list) -> None:
        """Extract function call edges from a Python function body."""
        for node in self._iter_nodes(body_node):
            if node.type == "call":
                func_node = node.child_by_field_name("function")
                if func_node:
                    called = func_node.text.decode("utf-8").split("(")[0]
                    if called and not called.startswith(("'", '"', "0", "1")):
                        edges.append({
                            "src_name": src_name,
                            "dst_name": called,
                            "dst_file": None,
                            "edge_type": "calls",
                        })

    def _extract_python_imports(self, node: Any, nodes: list, edges: list) -> None:
        """Extract import edges from import statements."""
        try:
            if node.type == "import_statement":
                for alias in node.children:
                    if alias.type in ("dotted_name", "aliased_import"):
                        name = alias.text.decode("utf-8").split(" as ")[0]
                        edges.append({
                            "src_name": "__module__",
                            "dst_name": name,
                            "dst_file": None,
                            "edge_type": "imports",
                        })
            elif node.type == "import_from_statement":
                module_node = node.child_by_field_name("module_name")
                module = module_node.text.decode("utf-8") if module_node else ""
                for child in node.children:
                    if child.type == "dotted_name" and child != module_node:
                        edges.append({
                            "src_name": "__module__",
                            "dst_name": f"{module}.{child.text.decode('utf-8')}",
                            "dst_file": None,
                            "edge_type": "imports",
                        })
        except Exception:
            pass

    @staticmethod
    def _extract_jsdoc(node: Any) -> str | None:
        """Extract a JSDoc/Javadoc comment (/** ... */) from the preceding sibling."""
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            text = prev.text.decode("utf-8").strip()
            if text.startswith("/**") and text.endswith("*/"):
                body = text[3:-2]
                cleaned = []
                for line in body.splitlines():
                    line = line.strip().lstrip("* ").strip()
                    if line:
                        cleaned.append(line)
                result = "\n".join(cleaned).strip()
                return result[:200] if result else None
        return None

    def _walk_js_ts(self, node: Any, lines: list[str], filepath: str, nodes: list, edges: list) -> None:
        """Walk JavaScript/TypeScript AST for functions and classes."""
        for child in node.children:
            if child.type in ("function_declaration", "function"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8")
                    nodes.append({
                        "name": name,
                        "type": "function",
                        "line_start": child.start_point[0] + 1,
                        "line_end": child.end_point[0] + 1,
                        "signature": f"function {name}()",
                        "docstring": self._extract_jsdoc(child),
                    })

            elif child.type == "class_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8")
                    nodes.append({
                        "name": name,
                        "type": "class",
                        "line_start": child.start_point[0] + 1,
                        "line_end": child.end_point[0] + 1,
                        "signature": f"class {name}",
                        "docstring": self._extract_jsdoc(child),
                    })

            elif child.type in ("import_declaration", "import_statement"):
                try:
                    src_node = child.child_by_field_name("source")
                    if src_node:
                        src = src_node.text.decode("utf-8").strip("'\"")
                        edges.append({
                            "src_name": "__module__",
                            "dst_name": src,
                            "dst_file": None,
                            "edge_type": "imports",
                        })
                except Exception:
                    pass

            self._walk_js_ts(child, lines, filepath, nodes, edges)

    def _walk_go_rust(self, node: Any, lines: list[str], filepath: str, nodes: list, edges: list) -> None:
        """Walk Go/Rust AST for functions, types, and doc comments."""
        for child in node.children:
            if child.type in ("function_declaration", "method_declaration", "function_item"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8")
                    docstring = self._extract_line_comment_doc(child, lines)
                    nodes.append({
                        "name": name,
                        "type": "function",
                        "line_start": child.start_point[0] + 1,
                        "line_end": child.end_point[0] + 1,
                        "signature": lines[child.start_point[0]].strip() if child.start_point[0] < len(lines) else name,
                        "docstring": docstring,
                    })

            elif child.type in ("type_declaration", "type_spec", "struct_item", "impl_item"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8")
                    nodes.append({
                        "name": name,
                        "type": "class",
                        "line_start": child.start_point[0] + 1,
                        "line_end": child.end_point[0] + 1,
                        "signature": lines[child.start_point[0]].strip() if child.start_point[0] < len(lines) else name,
                        "docstring": self._extract_line_comment_doc(child, lines),
                    })

            self._walk_go_rust(child, lines, filepath, nodes, edges)

    def _walk_java(self, node: Any, lines: list[str], filepath: str, nodes: list, edges: list) -> None:
        """Walk Java AST for classes, methods, and Javadoc."""
        for child in node.children:
            if child.type == "method_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8")
                    docstring = self._extract_jsdoc(child)
                    nodes.append({
                        "name": name,
                        "type": "function",
                        "line_start": child.start_point[0] + 1,
                        "line_end": child.end_point[0] + 1,
                        "signature": lines[child.start_point[0]].strip() if child.start_point[0] < len(lines) else name,
                        "docstring": docstring,
                    })

            elif child.type == "class_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8")
                    nodes.append({
                        "name": name,
                        "type": "class",
                        "line_start": child.start_point[0] + 1,
                        "line_end": child.end_point[0] + 1,
                        "signature": f"class {name}",
                        "docstring": self._extract_jsdoc(child),
                    })
                    # Recurse into class body
                    body = child.child_by_field_name("body")
                    if body:
                        self._walk_java(body, lines, filepath, nodes, edges)
                    continue

            elif child.type in ("import_declaration",):
                try:
                    text = child.text.decode("utf-8")
                    m = re.match(r"import\s+(?:static\s+)?([\w.]+)", text)
                    if m:
                        edges.append({
                            "src_name": "__module__",
                            "dst_name": m.group(1),
                            "dst_file": None,
                            "edge_type": "imports",
                        })
                except Exception:
                    pass

            self._walk_java(child, lines, filepath, nodes, edges)

    @staticmethod
    def _extract_line_comment_doc(node: Any, lines: list[str]) -> str | None:
        """Extract consecutive ``//`` or ``///`` comment lines above a node."""
        start_line = node.start_point[0]
        idx = start_line - 1
        comment_lines: list[str] = []
        while idx >= 0:
            stripped = lines[idx].strip()
            if stripped.startswith("///"):
                comment_lines.append(stripped[3:].strip())
            elif stripped.startswith("//"):
                comment_lines.append(stripped[2:].strip())
            else:
                break
            idx -= 1
        if not comment_lines:
            return None
        comment_lines.reverse()
        result = "\n".join(l for l in comment_lines if l).strip()
        return result[:200] if result else None

    def _walk_generic(self, node: Any, lines: list[str], filepath: str, nodes: list, edges: list) -> None:
        """No-op walker for unsupported languages; regex fallback handles them."""
        pass

    def _iter_nodes(self, node: Any):
        """Yield all descendant nodes in depth-first order."""
        yield node
        for child in node.children:
            yield from self._iter_nodes(child)

    @staticmethod
    def _extract_regex_docstring(lines: list[str], decl_line_idx: int) -> str | None:
        """Extract a docstring or comment block near a declaration (0-indexed)."""
        # Python triple-quoted string on the next line
        if decl_line_idx + 1 < len(lines):
            next_line = lines[decl_line_idx + 1].strip()
            for delim in ('"""', "'''"):
                if next_line.startswith(delim):
                    doc_lines = []
                    # Single-line docstring
                    if next_line.endswith(delim) and len(next_line) > 3:
                        return next_line.strip(delim).strip()[:200] or None
                    # Multi-line docstring
                    doc_lines.append(next_line[3:])
                    for j in range(decl_line_idx + 2, len(lines)):
                        l = lines[j]
                        if delim in l:
                            doc_lines.append(l[:l.index(delim)].strip())
                            break
                        doc_lines.append(l.strip())
                    result = "\n".join(l for l in doc_lines if l).strip()
                    return result[:200] if result else None

        # Block comments (/* ... */ or /** ... */) above
        idx = decl_line_idx - 1
        if idx >= 0:
            prev = lines[idx].strip()
            if prev.endswith("*/"):
                comment_lines = []
                while idx >= 0:
                    l = lines[idx].strip()
                    comment_lines.append(l)
                    if l.startswith("/*"):
                        break
                    idx -= 1
                comment_lines.reverse()
                body = " ".join(
                    l.lstrip("/*").rstrip("*/").strip().lstrip("* ").strip()
                    for l in comment_lines
                )
                result = body.strip()
                return result[:200] if result else None

            if prev.startswith("//") or prev.startswith("#"):
                comment_lines = []
                while idx >= 0:
                    l = lines[idx].strip()
                    if l.startswith("//"):
                        comment_lines.append(l[2:].strip())
                    elif l.startswith("#"):
                        comment_lines.append(l[1:].strip())
                    else:
                        break
                    idx -= 1
                comment_lines.reverse()
                result = "\n".join(l for l in comment_lines if l).strip()
                return result[:200] if result else None

        return None

    def _parse_with_regex(
        self, filepath: str, content: str
    ) -> tuple[list[dict], list[dict]]:
        """Extract nodes via regex - works for any language."""
        nodes: list[dict] = []
        edges: list[dict] = []
        lines = content.splitlines()

        suffix = Path(filepath).suffix.lower()
        language = LANGUAGE_MAP.get(suffix)
        patterns = LANGUAGE_REGEX_MAP.get(language, {}) if language else {}

        import_pattern = patterns.get("import")
        decl_patterns = [
            (pattern, node_type)
            for node_type, pattern in patterns.items()
            if node_type != "import"
        ]

        for i, line in enumerate(lines, start=1):
            for pattern, node_type in decl_patterns:
                m = pattern.match(line)
                if m:
                    nodes.append({
                        "name": m.group(1),
                        "type": node_type,
                        "line_start": i,
                        "line_end": i,
                        "signature": line.strip(),
                        "docstring": self._extract_regex_docstring(lines, i - 1),
                    })
                    break

            if import_pattern:
                m = import_pattern.search(line)
                if m:
                    edges.append({
                        "src_name": "__module__",
                        "dst_name": m.group(1),
                        "dst_file": None,
                        "edge_type": "imports",
                    })

        return nodes, edges
