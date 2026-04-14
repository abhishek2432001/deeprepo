"""SQLite-backed code knowledge graph for structure, embeddings, and wiki storage."""

import hashlib
import logging
import sqlite3
import struct
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2


class GraphStore:
    """SQLite-backed knowledge graph for code structure."""

    def __init__(self, db_path: str = "codegraph.db") -> None:
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn'):
            conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=15.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL,
                filepath    TEXT NOT NULL,
                line_start  INTEGER,
                line_end    INTEGER,
                signature   TEXT,
                docstring   TEXT
            );

            CREATE TABLE IF NOT EXISTS edges (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                src_id      INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                dst_name    TEXT NOT NULL,
                dst_file    TEXT,
                edge_type   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS file_hashes (
                filepath    TEXT PRIMARY KEY,
                sha256      TEXT NOT NULL,
                indexed_at  REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_filepath ON nodes(filepath);
            CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
            CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_id);
            CREATE INDEX IF NOT EXISTS idx_edges_dst_name ON edges(dst_name);

            CREATE TABLE IF NOT EXISTS _state (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS embeddings (
                filepath TEXT PRIMARY KEY,
                vector BLOB NOT NULL,
                dim INTEGER NOT NULL,
                source TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_embeddings_sha ON embeddings(sha256);

            CREATE TABLE IF NOT EXISTS wiki_pages (
                filepath TEXT PRIMARY KEY,
                md_path TEXT NOT NULL,
                module_name TEXT,
                module_path TEXT,
                is_leaf INTEGER,
                content_md TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                token_count INTEGER,
                last_indexed_commit TEXT,
                stale INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # FTS virtual table must be created outside executescript for some SQLite builds
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS wiki_pages_fts
            USING fts5(filepath, content_md)
        """)

        conn.commit()

    def save_file_nodes(
        self,
        filepath: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> None:
        """Replace all nodes and edges for a file."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM nodes WHERE filepath = ?", (filepath,))
            conn.commit()

            if not nodes:
                return

            name_to_id: dict[str, int] = {}
            for node in nodes:
                cur = conn.execute(
                    """INSERT INTO nodes (name, type, filepath, line_start, line_end, signature, docstring)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        node.get("name", ""),
                        node.get("type", "unknown"),
                        filepath,
                        node.get("line_start"),
                        node.get("line_end"),
                        node.get("signature"),
                        node.get("docstring"),
                    ),
                )
                name_to_id[node.get("name", "")] = cur.lastrowid  # type: ignore[assignment]

            for edge in edges:
                src_name = edge.get("src_name", "")
                src_id = name_to_id.get(src_name)
                if src_id is None:
                    continue
                conn.execute(
                    """INSERT INTO edges (src_id, dst_name, dst_file, edge_type)
                       VALUES (?, ?, ?, ?)""",
                    (
                        src_id,
                        edge.get("dst_name", ""),
                        edge.get("dst_file"),
                        edge.get("edge_type", "calls"),
                    ),
                )

            conn.commit()

    def update_file_hash(self, filepath: str, sha256: str) -> None:
        """Record SHA-256 hash for a file after successful indexing."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO file_hashes (filepath, sha256, indexed_at)
                   VALUES (?, ?, ?)""",
                (filepath, sha256, time.time()),
            )
            conn.commit()

    def clear_file(self, filepath: str) -> None:
        """Remove all nodes, edges, and hash record for a file."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM nodes WHERE filepath = ?", (filepath,))
            conn.execute("DELETE FROM file_hashes WHERE filepath = ?", (filepath,))
            conn.commit()

    def is_file_changed(self, filepath: str, current_sha256: str) -> bool:
        """Return True if file content differs from last indexed version."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT sha256 FROM file_hashes WHERE filepath = ?", (filepath,)
        ).fetchone()
        if row is None:
            return True  # never indexed
        return row["sha256"] != current_sha256

    def get_file_skeleton(self, filepath: str) -> str:
        """Return function/class signatures for a file (no implementations)."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT name, type, signature, line_start
               FROM nodes WHERE filepath = ?
               ORDER BY line_start""",
            (filepath,),
        ).fetchall()

        if not rows:
            return ""

        lines = []
        for row in rows:
            sig = row["signature"] or row["name"]
            lines.append(f"[{row['type']}] {sig}  (line {row['line_start']})")
        return "\n".join(lines)

    def get_symbol(self, name: str) -> dict[str, Any] | None:
        """Find exact definition of a symbol by name."""
        conn = self._get_conn()
        row = conn.execute(
            """SELECT name, type, filepath, line_start, signature, docstring
               FROM nodes WHERE name = ? LIMIT 1""",
            (name,),
        ).fetchone()
        return dict(row) if row else None

    def get_blast_radius(self, filepath: str, depth: int = 2) -> list[str]:
        """Compute minimal set of files affected by changes to *filepath*.

        Uses a recursive CTE for single-query traversal.
        """
        conn = self._get_conn()
        rows = conn.execute(
            """
            WITH RECURSIVE dependents(filepath, depth) AS (
                SELECT DISTINCT n.filepath, 0
                FROM nodes n
                WHERE n.filepath = ?

                UNION

                SELECT DISTINCT caller.filepath, d.depth + 1
                FROM dependents d
                JOIN nodes src    ON src.filepath = d.filepath
                JOIN edges e      ON e.dst_name   = src.name
                JOIN nodes caller ON caller.id     = e.src_id
                WHERE d.depth < ?
                  AND caller.filepath != ?
            )
            SELECT DISTINCT filepath
            FROM dependents
            WHERE filepath != ?
            """,
            (filepath, depth, filepath, filepath),
        ).fetchall()
        return [r["filepath"] for r in rows]

    def get_callers(self, node_name: str) -> list[dict[str, Any]]:
        """Return all nodes that call the given node name."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT n.name, n.filepath, n.line_start, n.signature
               FROM edges e
               JOIN nodes n ON n.id = e.src_id
               WHERE e.dst_name = ? AND e.edge_type = 'calls'""",
            (node_name,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_import_graph(self, filepath: str) -> dict[str, list[str]]:
        """Return direct imports made by functions in *filepath*."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT n.name as src_name, e.dst_name, e.dst_file
               FROM edges e
               JOIN nodes n ON n.id = e.src_id
               WHERE n.filepath = ? AND e.edge_type = 'imports'""",
            (filepath,),
        ).fetchall()
        graph: dict[str, list[str]] = {}
        for row in rows:
            graph.setdefault(row["src_name"], []).append(row["dst_name"])
        return graph

    def get_stats(self) -> dict[str, Any]:
        """Return graph statistics."""
        conn = self._get_conn()
        node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        file_count = conn.execute(
            "SELECT COUNT(DISTINCT filepath) FROM nodes"
        ).fetchone()[0]
        type_rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM nodes GROUP BY type"
        ).fetchall()
        type_breakdown = {r["type"]: r["cnt"] for r in type_rows}

        return {
            "nodes": node_count,
            "edges": edge_count,
            "files_indexed": file_count,
            "node_types": type_breakdown,
            "db_path": self.db_path,
        }

    def close(self) -> None:
        """Close the SQLite connection for the current thread."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            delattr(self._local, 'conn')


    def set_state(self, key: str, value: str) -> None:
        """Store a key-value pair in the _state table."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO _state (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()

    def get_state(self, key: str, default: str | None = None) -> str | None:
        """Retrieve a value from the _state table, or return default."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM _state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def prune_files(self, current_filepaths: set[str]) -> int:
        """Remove all data for filepaths NOT in *current_filepaths*."""
        with self._lock:
            conn = self._get_conn()

            all_fps: set[str] = set()
            for table, col in [
                ("nodes", "filepath"),
                ("file_hashes", "filepath"),
                ("wiki_pages", "filepath"),
                ("embeddings", "filepath"),
            ]:
                try:
                    rows = conn.execute(f"SELECT DISTINCT {col} FROM {table}").fetchall()
                    all_fps.update(r[0] for r in rows)
                except sqlite3.OperationalError:
                    pass

            stale = all_fps - current_filepaths
            if not stale:
                return 0

            stale_list = list(stale)
            placeholders = ",".join("?" for _ in stale_list)

            conn.execute(
                f"DELETE FROM nodes WHERE filepath IN ({placeholders})", stale_list
            )
            conn.execute(
                f"DELETE FROM file_hashes WHERE filepath IN ({placeholders})", stale_list
            )

            try:
                conn.execute(
                    f"DELETE FROM wiki_pages_fts WHERE filepath IN ({placeholders})",
                    stale_list,
                )
            except sqlite3.OperationalError:
                pass
            conn.execute(
                f"DELETE FROM wiki_pages WHERE filepath IN ({placeholders})", stale_list
            )

            conn.execute(
                f"DELETE FROM embeddings WHERE filepath IN ({placeholders})", stale_list
            )

            conn.commit()
            return len(stale_list)

    def upsert_embedding(
        self, filepath: str, vector: list[float] | Any, source: str, sha256: str
    ) -> None:
        """Store or update an embedding vector for a file."""
        with self._lock:
            conn = self._get_conn()
            dim = len(vector)
            blob = struct.pack(f"{dim}f", *vector)
            conn.execute(
                """INSERT OR REPLACE INTO embeddings (filepath, vector, dim, source, sha256, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (filepath, blob, dim, source, sha256),
            )
            conn.commit()

    def check_embedding_provider(self, provider_key: str) -> bool:
        """Return True if stored embeddings match provider_key, or if no embeddings exist yet.

        Call this at query time.  If it returns False the caller should warn
        the user that semantic search results will be unreliable and fall back
        to FTS / graph search instead.

        provider_key should be a stable string like "openai:text-embedding-3-small".
        """
        stored = self.get_state("embedding_provider")
        if stored is None:
            return True  # no embeddings written yet — no mismatch
        return stored == provider_key

    def set_embedding_provider(self, provider_key: str) -> None:
        """Persist the provider+model key used to generate embeddings."""
        self.set_state("embedding_provider", provider_key)

    def search_embeddings(
        self, query_vector: list[float] | Any, top_k: int = 5
    ) -> list[tuple[str, float]]:
        """Brute-force cosine-similarity search over stored embeddings."""
        import numpy as np

        conn = self._get_conn()
        rows = conn.execute(
            "SELECT filepath, vector, dim FROM embeddings"
        ).fetchall()

        if not rows:
            return []

        q = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm

        results: list[tuple[str, float]] = []
        for row in rows:
            dim = row["dim"]
            vec = np.array(
                struct.unpack(f"{dim}f", row["vector"]), dtype=np.float32
            )
            v_norm = np.linalg.norm(vec)
            if v_norm == 0:
                continue
            score = float(np.dot(q, vec / v_norm))
            results.append((row["filepath"], score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def upsert_wiki_page(
        self,
        filepath: str,
        md_path: str,
        content_md: str,
        module_name: str,
        module_path: str,
        is_leaf: bool,
        sha256: str,
        commit: str | None = None,
        token_count: int | None = None,
    ) -> None:
        """Insert or update a wiki page and its FTS index entry."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO wiki_pages
                   (filepath, md_path, module_name, module_path, is_leaf,
                    content_md, sha256, token_count, last_indexed_commit, stale, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)""",
                (
                    filepath,
                    md_path,
                    module_name,
                    module_path,
                    1 if is_leaf else 0,
                    content_md,
                    sha256,
                    token_count,
                    commit,
                ),
            )

            try:
                conn.execute(
                    "DELETE FROM wiki_pages_fts WHERE filepath = ?", (filepath,)
                )
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute(
                    "INSERT INTO wiki_pages_fts (filepath, content_md) VALUES (?, ?)",
                    (filepath, content_md),
                )
            except sqlite3.OperationalError:
                pass

            conn.commit()

    def get_wiki_page(self, filepath: str) -> dict | None:
        """Retrieve a wiki page by filepath."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM wiki_pages WHERE filepath = ?", (filepath,)
        ).fetchone()
        return dict(row) if row else None

    def search_wiki_fts(
        self, query: str, limit: int = 5
    ) -> list[tuple[str, str]]:
        """Full-text search over wiki pages."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT filepath, snippet(wiki_pages_fts, 1, '<b>', '</b>', '...', 32)
                   FROM wiki_pages_fts
                   WHERE wiki_pages_fts MATCH ?
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
            return [(r[0], r[1]) for r in rows]
        except sqlite3.OperationalError:
            return []

    def mark_wiki_stale(self, filepaths: list[str]) -> None:
        """Mark wiki pages as stale (needing regeneration)."""
        if not filepaths:
            return
        with self._lock:
            conn = self._get_conn()
            placeholders = ",".join("?" for _ in filepaths)
            conn.execute(
                f"UPDATE wiki_pages SET stale = 1 WHERE filepath IN ({placeholders})",
                filepaths,
            )
            conn.commit()

    def get_stale_wiki_pages(self) -> list[str]:
        """Return filepaths of all wiki pages marked as stale."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT filepath FROM wiki_pages WHERE stale = 1"
        ).fetchall()
        return [r["filepath"] for r in rows]
