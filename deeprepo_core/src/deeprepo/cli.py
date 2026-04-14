"""deeprepo command-line interface."""

from __future__ import annotations

import argparse
import os
import sys
import time
import textwrap
from pathlib import Path
from typing import Any

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
CYAN    = "\033[36m"
RED     = "\033[31m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"


def _c(text: str, *codes: str) -> str:
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + RESET


def ok(msg: str)   -> None: print(_c(f"  ✓  {msg}", GREEN))
def info(msg: str) -> None: print(_c(f"  →  {msg}", CYAN))
def warn(msg: str) -> None: print(_c(f"  ⚠  {msg}", YELLOW))
def err(msg: str)  -> None: print(_c(f"  ✗  {msg}", RED), file=sys.stderr)
def step(msg: str) -> None: print(_c(f"\n● {msg}", BOLD + BLUE))
def dim(msg: str)  -> None: print(_c(f"     {msg}", DIM))


def banner() -> None:
    print(_c("""
╔══════════════════════════════════════╗
║   deeprepo  —  codebase RAG engine  ║
╚══════════════════════════════════════╝
""", BOLD + CYAN))


class Spinner:
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, label: str) -> None:
        self.label = label
        self._i = 0
        self._start = time.time()
        self._active = sys.stdout.isatty()

    def tick(self) -> None:
        if not self._active:
            return
        frame = self.FRAMES[self._i % len(self.FRAMES)]
        elapsed = time.time() - self._start
        print(
            f"\r  {_c(frame, CYAN)}  {self.label}  "
            + _c(f"({elapsed:.1f}s)", DIM)
            + "   ",
            end="", flush=True,
        )
        self._i += 1

    def done(self, msg: str = "") -> None:
        if self._active:
            print("\r" + " " * 60 + "\r", end="", flush=True)
        ok(msg or self.label)


PROVIDER_KEYS: dict[str, str] = {
    "openai":      "OPENAI_API_KEY",
    "anthropic":   "ANTHROPIC_API_KEY",
    "gemini":      "GOOGLE_API_KEY",
    "ollama":      "",  # no key needed
    "huggingface": "HF_TOKEN",
}


def _detect_available_providers() -> list[str]:
    return [p for p, env in PROVIDER_KEYS.items() if not env or os.environ.get(env)]


def _assert_provider_key(provider: str) -> None:
    env = PROVIDER_KEYS.get(provider, "")
    if env and not os.environ.get(env):
        err(f"Provider '{provider}' requires {env} to be set.")
        print(f"\n  Export it first:\n\n    export {env}=<your-key>\n")
        sys.exit(1)


def _pick_default_provider() -> str:
    for p in ["openai", "anthropic", "gemini", "ollama"]:
        env = PROVIDER_KEYS.get(p, "")
        if not env or os.environ.get(env):
            return p
    return "openai"


def _resolve_provider(args: argparse.Namespace) -> tuple[str, str]:
    """Return (llm_provider, embedding_provider) from args then env."""
    llm = (
        getattr(args, "llm", None)
        or getattr(args, "provider", None)
        or os.environ.get("LLM_PROVIDER")
        or _pick_default_provider()
    )
    embed = (
        getattr(args, "embed", None)
        or getattr(args, "provider", None)
        or os.environ.get("EMBEDDING_PROVIDER")
        or llm
    )
    return llm, embed


def _build_client(args: argparse.Namespace) -> Any:
    from deeprepo import DeepRepoClient

    llm, embed = _resolve_provider(args)
    _assert_provider_key(llm)
    if embed != llm:
        _assert_provider_key(embed)

    branch_isolation = not getattr(args, "no_branch_isolation", False)

    # Flatten comma-separated values: --base-branch main,develop
    raw_bases: list[str] = getattr(args, "base_branch", []) or []
    base_branches = [b.strip() for raw in raw_bases for b in raw.split(",") if b.strip()]

    wiki_dir = getattr(args, "wiki_dir", ".deeprepo/wiki") or ".deeprepo/wiki"

    info(f"LLM provider       : {_c(llm, BOLD)}")
    info(f"Embedding provider : {_c(embed, BOLD)}")
    info(f"Branch isolation   : {_c(str(branch_isolation), BOLD)}")
    if base_branches:
        info(f"Base branches      : {_c(', '.join(base_branches), BOLD)}")
    info(f"Wiki directory     : {_c(wiki_dir, BOLD)}")

    return DeepRepoClient(
        llm_provider_name=llm,
        embedding_provider_name=embed,
        branch_isolation=branch_isolation,
        base_branches=base_branches,
        wiki_dir=wiki_dir,
        hierarchical_wiki=True,
    )


def _patch_wiki_progress(client: Any) -> dict:
    """Wrap WikiEngine generation methods to emit live progress lines."""
    engine = client.wiki_engine
    original_leaf     = engine.generate_leaf_page
    original_parent   = engine.generate_parent_page
    original_overview = engine.generate_repo_overview
    counters = {"done": 0, "total": 0}

    def _leaf(*a, **kw):
        module_name = a[0] if a else kw.get("module_name", "?")
        sp = Spinner(f"Wiki: {module_name}")
        sp.tick()
        result = original_leaf(*a, **kw)
        counters["done"] += 1
        if result:
            sp.done(f"Wiki page ready: {_c(module_name, BOLD)} ({counters['done']}/{counters['total']})")
        else:
            warn(f"Wiki skipped: {module_name}")
        return result

    def _parent(*a, **kw):
        module_name = a[0] if a else kw.get("module_name", "?")
        sp = Spinner(f"Roll-up: {module_name}")
        sp.tick()
        result = original_parent(*a, **kw)
        if result:
            sp.done(f"Roll-up page ready: {_c(module_name, BOLD)}")
        return result

    def _overview(*a, **kw):
        sp = Spinner("Generating project overview …")
        sp.tick()
        result = original_overview(*a, **kw)
        if result:
            sp.done("Project overview ready")
        return result

    engine.generate_leaf_page     = _leaf
    engine.generate_parent_page   = _parent
    engine.generate_repo_overview = _overview
    return counters


def cmd_ingest(args: argparse.Namespace) -> int:
    banner()
    path = Path(getattr(args, "path", None) or ".").resolve()
    if not path.exists():
        err(f"Path not found: {path}")
        return 1

    step("Initialising client")
    try:
        client = _build_client(args)
    except SystemExit:
        raise
    except Exception as e:
        err(f"Failed to initialise client: {e}")
        return 1

    if client.current_branch:
        ok(f"Git branch: {_c(client.current_branch, BOLD + MAGENTA)}")

    if not getattr(args, "no_wiki", False):
        step("Phase 1 — Scanning & generating concept wiki pages")
        dim("Scanning files …")
        try:
            from deeprepo.ingestion import ingest_directory
            _chunks, file_contents = ingest_directory(
                path,
                chunk_size=getattr(args, "chunk_size", 1000),
                overlap=getattr(args, "overlap", 100),
            )
            info(f"Found {len(file_contents)} source files")
        except Exception as e:
            err(f"File scan failed: {e}")
            return 1

        counters = _patch_wiki_progress(client)
        counters["total"] = len(file_contents)
        wiki_start = time.time()
        try:
            wiki_stats = client.wiki_engine.bulk_generate(
                file_contents=file_contents,
                graph_store=client.graph_store,
                max_workers=getattr(args, "workers", 3),
            )
            print()
            failed = wiki_stats.get("failed", 0)
            ok(
                f"Wiki complete in {time.time() - wiki_start:.1f}s — "
                f"{wiki_stats.get('generated', 0)} pages generated, "
                f"{wiki_stats.get('skipped', 0)} skipped"
                + (f", {failed} failed" if failed else "")
            )
            if failed and wiki_stats.get("last_error"):
                warn(f"Last failure reason: {wiki_stats['last_error']}")
            dim(f"Wiki saved to: {client.wiki_engine.get_wiki_dir()}")
        except Exception as e:
            warn(f"Wiki generation failed (continuing): {e}")

    step("Phase 2 — Building knowledge graph & embeddings")
    ingest_start = time.time()
    sp = Spinner("Ingesting codebase …")

    try:
        original_build = client.graph_builder.build_from_directory

        def _build_with_tick(*a, **kw):
            sp.tick()
            return original_build(*a, **kw)

        client.graph_builder.build_from_directory = _build_with_tick
        result = client.ingest(
            path,
            chunk_size=getattr(args, "chunk_size", 1000),
            overlap=getattr(args, "overlap", 100),
            generate_wiki=False,  # wiki already handled in Phase 1
        )
        sp.done("Knowledge graph & embeddings built")
    except Exception as e:
        print()
        err(f"Ingest failed: {e}")
        return 1

    step("Done")
    print()
    rows = [
        ("Files scanned",     result.get("files_scanned", 0)),
        ("Chunks processed",  result.get("chunks_processed", 0)),
        ("Graph nodes",       result.get("graph_nodes", 0)),
        ("Graph edges",       result.get("graph_edges", 0)),
        ("Wiki pages",        result.get("wiki_generated", 0)),
        ("Embeddings stored", result.get("embeddings_stored", 0)),
        ("Orphans pruned",    result.get("orphans_pruned", 0)),
        ("Branch",            client.current_branch or "—"),
        ("Total time",        f"{time.time() - ingest_start:.1f}s"),
    ]
    for label, value in rows:
        print(f"  {_c(label + ':', DIM):<30} {_c(str(value), BOLD)}")

    print()
    dim("Next steps:")
    dim('  deeprepo query "how does X work?"')
    dim("  deeprepo status")
    dim(f"  open {client.wiki_engine.get_wiki_dir()}/overview.md")
    print()
    return 0


def cmd_wiki(args: argparse.Namespace) -> int:
    banner()
    path = Path(getattr(args, "path", None) or ".").resolve()
    if not path.exists():
        err(f"Path not found: {path}")
        return 1

    step("Initialising client")
    try:
        client = _build_client(args)
    except SystemExit:
        raise
    except Exception as e:
        err(f"Failed to initialise client: {e}")
        return 1

    step("Scanning files")
    try:
        from deeprepo.ingestion import ingest_directory
        _chunks, file_contents = ingest_directory(path)
        info(f"Found {len(file_contents)} source files")
    except Exception as e:
        err(f"File scan failed: {e}")
        return 1

    step("Generating concept wiki pages")
    counters = _patch_wiki_progress(client)
    counters["total"] = len(file_contents)
    start = time.time()
    try:
        stats = client.wiki_engine.bulk_generate(
            file_contents=file_contents,
            graph_store=client.graph_store,
            max_workers=getattr(args, "workers", 3),
        )
    except Exception as e:
        err(f"Wiki generation failed: {e}")
        return 1

    print()
    ok(f"Done in {time.time() - start:.1f}s — {stats.get('generated', 0)} pages")
    dim(f"Wiki at: {client.wiki_engine.get_wiki_dir()}")
    print()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    banner()
    wiki_dir = getattr(args, "wiki_dir", ".deeprepo/wiki") or ".deeprepo/wiki"
    port     = getattr(args, "port", 8080)

    llm_provider = None
    llm_name, _ = _resolve_provider(args)
    if llm_name:
        try:
            _assert_provider_key(llm_name)
            from deeprepo.providers import get_llm
            llm_provider = get_llm(llm_name)
            ok(f"Chat enabled via {_c(llm_name, BOLD)}")
        except SystemExit:
            warn("No LLM provider key — chat will be disabled")
        except Exception as e:
            warn(f"Could not load LLM provider ({e}) — chat will be disabled")
    else:
        warn("No LLM provider — chat will be disabled")

    info(f"Wiki directory : {_c(wiki_dir, BOLD)}")
    info(f"Port           : {_c(str(port), BOLD)}")
    info(f"URL            : {_c(f'http://localhost:{port}', CYAN + BOLD)}")
    print()

    from deeprepo.ui import serve
    try:
        serve(wiki_dir=wiki_dir, port=port, llm_provider=llm_provider)
    except KeyboardInterrupt:
        print()
        warn("Server stopped.")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    question: str = " ".join(args.question)

    step("Initialising client")
    try:
        client = _build_client(args)
    except SystemExit:
        raise
    except Exception as e:
        err(f"Failed to initialise client: {e}")
        return 1

    step(f"Query: {_c(question, BOLD)}")
    sp = Spinner("Thinking …")
    sp.tick()

    try:
        result = client.query(question, top_k=getattr(args, "top_k", 5))
        sp.done("Answer ready")
    except Exception as e:
        print()
        err(f"Query failed: {e}")
        return 1

    print()
    print(_c("─" * 60, DIM))
    print()
    print(result.get("answer", "No answer generated"))
    print()
    print(_c("─" * 60, DIM))
    print()

    sources = result.get("sources", [])
    if sources:
        dim(f"Sources ({len(sources)}):")
        for s in sources:
            dim(f"  • {s}")

    dim(
        f"Intent: {result.get('intent', '?')}  |  "
        f"Strategy: {result.get('strategy', '?')}  |  "
        f"Retrieval: {result.get('retrieval', '?')}"
    )
    print()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    banner()

    step("Initialising client")
    try:
        client = _build_client(args)
    except SystemExit:
        raise
    except Exception as e:
        err(f"Failed to initialise client: {e}")
        return 1

    step("Knowledge base status")
    try:
        stats = client.get_stats()
        freshness = client.get_freshness_status()
    except Exception as e:
        err(f"Status check failed: {e}")
        return 1

    graph = stats.get("graph", {})
    wiki  = stats.get("wiki", {})

    print()
    rows = [
        ("Branch",           stats.get("current_branch") or "—"),
        ("Branch isolation", str(stats.get("branch_isolation", True))),
        ("Base branches",    ", ".join(stats.get("base_branches") or []) or "—"),
        ("Files indexed",    stats.get("total_files", 0)),
        ("Graph nodes",      graph.get("nodes", 0)),
        ("Graph edges",      graph.get("edges", 0)),
        ("Wiki pages",       wiki.get("pages", 0)),
        ("Wiki directory",   wiki.get("wiki_dir", "—")),
        ("Database",         stats.get("db_path", "—")),
        ("Last commit",      freshness.get("last_indexed_commit", "—") or "—"),
        ("HEAD commit",      freshness.get("head_commit", "—") or "—"),
        ("Pending changes",  freshness.get("diff_files", 0)),
    ]
    for label, value in rows:
        colour = RED if (label == "Pending changes" and int(value or 0) > 0) else BOLD
        print(f"  {_c(label + ':', DIM):<30} {_c(str(value), colour)}")

    base_status = freshness.get("base_status", [])
    if base_status:
        print()
        dim("Base branch cache health:")
        for b in base_status:
            flag = _c("STALE", RED + BOLD) if b.get("stale") else _c("fresh", GREEN)
            print(f"    {b['branch']:<20} {flag}")

    if freshness.get("diff_files", 0) > 0:
        print()
        warn(f"{freshness['diff_files']} files changed since last ingest — run: deeprepo ingest .")

    print()
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    banner()
    path = Path(getattr(args, "path", None) or ".").resolve()

    print(_c("  Welcome to deeprepo!  Let's set you up.\n", BOLD))

    import subprocess
    is_git = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True, cwd=str(path)
    ).returncode == 0

    if is_git:
        ok("Git repository detected")
    else:
        warn("Not a git repository — branch isolation will be disabled")

    available = _detect_available_providers()
    if not available:
        err("No provider API keys found in environment.")
        print(textwrap.dedent("""
  Set at least one of:
    export OPENAI_API_KEY=sk-...
    export ANTHROPIC_API_KEY=sk-ant-...
    export GOOGLE_API_KEY=...
    (or use Ollama — no key needed)
        """))
        return 1

    ok(f"Available providers: {', '.join(available)}")

    provider = available[0]
    info(f"Using provider: {_c(provider, BOLD)}  (override with --llm / --embed)")

    print()
    print(_c("  Run this to ingest your codebase:\n", BOLD))
    cmd_parts = [f"deeprepo ingest {path}", f"--llm {provider}"]
    if not is_git:
        cmd_parts.append("--no-branch-isolation")
    print(f"    {_c(' '.join(cmd_parts), CYAN + BOLD)}\n")

    print(_c("  All available flags:\n", DIM))
    flags = [
        ("--llm",                 "openai|anthropic|gemini|ollama", "LLM provider"),
        ("--embed",               "openai|anthropic|gemini|ollama", "Embedding provider (defaults to --llm)"),
        ("--no-branch-isolation", "",                               "Disable per-branch DB isolation"),
        ("--base-branch",         "main",                           "Seed new branches from this branch's cache"),
        ("--wiki-dir",            ".deeprepo/wiki",                 "Where to write wiki .md files"),
        ("--no-wiki",             "",                               "Skip wiki generation"),
        ("--workers",             "3",                              "Parallel wiki generation workers"),
        ("--chunk-size",          "1000",                           "Text chunk size in characters"),
        ("--overlap",             "100",                            "Chunk overlap in characters"),
    ]
    for flag, default, desc in flags:
        default_str = _c(f"  default: {default}", DIM) if default else ""
        print(f"    {_c(flag, CYAN):<35} {desc}{default_str}")

    print()
    return 0


def _add_provider_flags(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("provider")
    g.add_argument("--provider", metavar="NAME", help="Set both LLM and embedding provider")
    g.add_argument("--llm",      metavar="NAME", help="LLM provider (openai|anthropic|gemini|ollama)")
    g.add_argument("--embed",    metavar="NAME", help="Embedding provider (default: same as --llm)")


def _add_branch_flags(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("branching")
    g.add_argument(
        "--no-branch-isolation",
        action="store_true", dest="no_branch_isolation",
        help="Use a single shared DB instead of one per git branch",
    )
    g.add_argument(
        "--base-branch",
        action="append", metavar="NAME", dest="base_branch",
        help="Branch to seed new branches from (repeatable: --base-branch main --base-branch develop)",
    )
    g.add_argument(
        "--wiki-dir",
        metavar="PATH", default=".deeprepo/wiki", dest="wiki_dir",
        help="Directory to write wiki .md files (default: .deeprepo/wiki)",
    )


def _add_ingest_flags(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("ingest options")
    g.add_argument("--chunk-size", type=int, default=1000, metavar="N", help="Chunk size in chars (default: 1000)")
    g.add_argument("--overlap",    type=int, default=100,  metavar="N", help="Chunk overlap in chars (default: 100)")
    g.add_argument("--workers",    type=int, default=3,    metavar="N", help="Wiki parallel workers (default: 3)")
    g.add_argument("--no-wiki",    action="store_true",    dest="no_wiki", help="Skip wiki generation")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deeprepo",
        description=_c("deeprepo — codebase RAG engine", BOLD),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
examples:
  deeprepo init                                       # detect setup, print the ingest command
  deeprepo ingest .                                   # ingest current directory (autodetect provider)
  deeprepo ingest ./my-project --llm openai
  deeprepo ingest . --llm anthropic --embed openai    # split LLM / embedding providers
  deeprepo ingest . --no-branch-isolation
  deeprepo ingest . --base-branch main                # seed feature branches from main
  deeprepo wiki .                                     # regenerate wiki pages only
  deeprepo serve                                      # open wiki viewer (chat enabled if provider set)
  deeprepo serve --llm openai --port 9000
  deeprepo query "how does auth work?"
  deeprepo status
        """),
    )

    sub = parser.add_subparsers(dest="command", metavar="command")

    p_init = sub.add_parser("init", help="Interactive setup wizard")
    p_init.add_argument("path", nargs="?", default=".", metavar="PATH")

    p_ingest = sub.add_parser("ingest", help="Scan repo → wiki pages → graph & embeddings")
    p_ingest.add_argument("path", nargs="?", default=".", metavar="PATH",
                          help="Path to repo (default: current directory)")
    _add_provider_flags(p_ingest)
    _add_branch_flags(p_ingest)
    _add_ingest_flags(p_ingest)

    p_wiki = sub.add_parser("wiki", help="Regenerate concept wiki pages only")
    p_wiki.add_argument("path", nargs="?", default=".", metavar="PATH")
    _add_provider_flags(p_wiki)
    _add_branch_flags(p_wiki)
    p_wiki.add_argument("--workers", type=int, default=3, metavar="N")

    p_serve = sub.add_parser("serve", help="Launch the wiki viewer with in-page chat")
    p_serve.add_argument(
        "--port", type=int, default=8080, metavar="PORT",
        help="HTTP port (default: 8080)",
    )
    _add_provider_flags(p_serve)
    _add_branch_flags(p_serve)

    p_query = sub.add_parser("query", help="Ask a question about the codebase")
    p_query.add_argument("question", nargs="+", metavar="QUESTION")
    p_query.add_argument("--top-k", type=int, default=5, dest="top_k", metavar="N")
    _add_provider_flags(p_query)
    _add_branch_flags(p_query)

    p_status = sub.add_parser("status", help="Show branch isolation & freshness status")
    _add_provider_flags(p_status)
    _add_branch_flags(p_status)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "init":   cmd_init,
        "ingest": cmd_ingest,
        "wiki":   cmd_wiki,
        "serve":  cmd_serve,
        "query":  cmd_query,
        "status": cmd_status,
    }

    handler = dispatch.get(args.command)
    if not handler:
        parser.print_help()
        sys.exit(1)

    try:
        sys.exit(handler(args))
    except KeyboardInterrupt:
        print()
        warn("Interrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
