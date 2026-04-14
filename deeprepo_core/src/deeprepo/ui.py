"""Lightweight local wiki viewer for DeepRepo-generated documentation.

Features
--------
- Sidebar tree navigation with name-filter
- Full-text search across all wiki page content (/api/search)
- Page-aware chat panel: ask questions about the current wiki page (/api/chat)
- Mermaid diagram rendering, syntax highlighting, breadcrumb navigation
"""

import json
import logging
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DeepRepo Wiki</title>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">

    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>

    <style>
        :root {
            --bg-base:       #0f172a;
            --bg-nav:        rgba(30, 41, 59, 0.92);
            --bg-card:       rgba(30, 41, 59, 0.5);
            --bg-input:      rgba(15, 23, 42, 0.6);
            --text-main:     #f8fafc;
            --text-muted:    #94a3b8;
            --accent:        #3b82f6;
            --accent-hover:  #60a5fa;
            --accent-glow:   rgba(59, 130, 246, 0.3);
            --border:        rgba(255, 255, 255, 0.08);
            --border-strong: rgba(255, 255, 255, 0.15);
            --success:       #10b981;
            --error:         #ef4444;
            --chat-width:    360px;
            --user-bubble:   rgba(59, 130, 246, 0.18);
            --ai-bubble:     rgba(30, 41, 59, 0.8);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-base);
            color: var(--text-main);
            display: flex;
            height: 100vh;
            overflow: hidden;
            background-image:
                radial-gradient(at 0% 0%, rgba(59,130,246,0.12) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(139,92,246,0.08) 0px, transparent 50%);
        }

        /* ── Sidebar ──────────────────────────────────── */
        #sidebar {
            width: 300px; min-width: 300px;
            height: 100%;
            background: var(--bg-nav);
            backdrop-filter: blur(16px);
            border-right: 1px solid var(--border);
            display: flex; flex-direction: column;
            z-index: 10;
        }

        #nav-header { padding: 20px 20px 12px; border-bottom: 1px solid var(--border); }

        #nav-header h1 {
            font-size: 1.15rem; font-weight: 700;
            background: linear-gradient(135deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em; margin-bottom: 12px;
        }

        /* Search wrapper — relative so dropdown anchors to it */
        #search-wrap { position: relative; }

        #search-box {
            width: 100%; padding: 8px 32px 8px 12px;
            border-radius: 6px; border: 1px solid var(--border);
            background: var(--bg-input); color: var(--text-main);
            font-size: 0.85rem; font-family: inherit; outline: none;
            transition: border-color 0.2s;
        }
        #search-box:focus { border-color: var(--accent); }
        #search-box::placeholder { color: var(--text-muted); opacity: 0.6; }

        /* clear button */
        #search-clear {
            position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
            color: var(--text-muted); cursor: pointer; font-size: 1rem;
            display: none; line-height: 1; user-select: none;
        }
        #search-clear:hover { color: var(--text-main); }

        /* Full-text search results dropdown */
        #search-results {
            position: absolute; top: calc(100% + 4px); left: 0; right: 0;
            background: #1e293b; border: 1px solid var(--border-strong);
            border-radius: 8px; z-index: 100;
            max-height: 320px; overflow-y: auto;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            display: none;
        }
        #search-results.open { display: block; }

        .sr-header {
            padding: 6px 12px; font-size: 0.72rem; font-weight: 600;
            color: var(--text-muted); text-transform: uppercase;
            letter-spacing: 0.06em; border-bottom: 1px solid var(--border);
        }
        .sr-item {
            padding: 10px 12px; cursor: pointer;
            border-bottom: 1px solid var(--border);
            transition: background 0.15s;
        }
        .sr-item:last-child { border-bottom: none; }
        .sr-item:hover { background: rgba(255,255,255,0.05); }
        .sr-item-title { font-size: 0.84rem; font-weight: 600; color: var(--text-main); margin-bottom: 3px; }
        .sr-item-snippet {
            font-size: 0.78rem; color: var(--text-muted); line-height: 1.5;
            overflow: hidden; text-overflow: ellipsis;
            display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
        }
        .sr-item-snippet mark {
            background: rgba(59,130,246,0.35); color: var(--accent-hover);
            border-radius: 2px; padding: 0 2px;
        }
        .sr-empty { padding: 16px 12px; text-align: center; color: var(--text-muted); font-size: 0.82rem; }

        #tree-container { flex: 1; overflow-y: auto; padding: 8px 12px; }
        #tree-container::-webkit-scrollbar { width: 5px; }
        #tree-container::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

        /* ── Tree ─────────────────────────────────────── */
        .tree-node { margin: 1px 0; }
        .tree-label {
            display: flex; align-items: center; gap: 6px;
            padding: 6px 10px; cursor: pointer; border-radius: 5px;
            color: var(--text-muted); font-size: 0.84rem; font-weight: 500;
            transition: all 0.15s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .tree-label:hover { background: rgba(255,255,255,0.05); color: var(--text-main); }
        .tree-label.active { background: var(--accent-glow); color: var(--accent-hover); }
        .tree-label.hidden { display: none; }
        .tree-icon { font-size: 0.95rem; flex-shrink: 0; }
        .tree-children { margin-left: 12px; padding-left: 10px; border-left: 1px solid var(--border); display: none; }
        .tree-children.open { display: block; }

        /* ── Breadcrumb ───────────────────────────────── */
        #breadcrumb {
            padding: 12px 48px; font-size: 0.82rem; color: var(--text-muted);
            border-bottom: 1px solid var(--border);
            background: rgba(15,23,42,0.4); display: none;
            flex-shrink: 0;
        }
        #breadcrumb a { color: var(--accent); text-decoration: none; cursor: pointer; }
        #breadcrumb a:hover { text-decoration: underline; }
        #breadcrumb .sep { margin: 0 6px; opacity: 0.4; }

        /* ── Main view ────────────────────────────────── */
        #main-view { flex: 1; min-width: 0; height: 100%; display: flex; flex-direction: column; overflow: hidden; }

        /* top bar: breadcrumb + chat toggle */
        #top-bar {
            display: flex; align-items: center; flex-shrink: 0;
            border-bottom: 1px solid var(--border);
        }
        #breadcrumb { flex: 1; border-bottom: none; }

        #chat-toggle-btn {
            flex-shrink: 0; margin-right: 16px;
            padding: 6px 14px; border-radius: 6px;
            background: rgba(59,130,246,0.12); border: 1px solid rgba(59,130,246,0.3);
            color: var(--accent-hover); font-size: 0.82rem; font-weight: 500;
            cursor: pointer; white-space: nowrap; transition: all 0.2s;
            display: none; /* shown when a page is loaded */
        }
        #chat-toggle-btn:hover { background: rgba(59,130,246,0.22); border-color: var(--accent); }
        #chat-toggle-btn.active { background: rgba(59,130,246,0.25); border-color: var(--accent); }

        #content-scroll { flex: 1; overflow-y: auto; scroll-behavior: smooth; }
        #content-container { max-width: 920px; margin: 0 auto; padding: 40px 48px 80px; }

        /* ── Markdown ─────────────────────────────────── */
        .md { color: var(--text-main); line-height: 1.75; font-size: 0.98rem; }
        .md h1,.md h2,.md h3,.md h4 { margin-top: 2em; margin-bottom: 0.6em; font-weight: 600; letter-spacing: -0.02em; }
        .md h1 { font-size: 2.2rem; margin-top: 0; }
        .md h2 { font-size: 1.6rem; padding-bottom: 0.3em; border-bottom: 1px solid var(--border); }
        .md h3 { font-size: 1.25rem; }
        .md p,.md ul,.md ol { margin-bottom: 1.2em; color: #cbd5e1; }
        .md li { margin-bottom: 0.3em; }
        .md strong { color: var(--text-main); }
        .md a { color: var(--accent); text-decoration: none; }
        .md a:hover { color: var(--accent-hover); text-decoration: underline; }
        .md code { font-family: 'Fira Code',monospace; background: rgba(0,0,0,0.35); padding: 0.15em 0.4em; border-radius: 4px; font-size: 0.85em; }
        .md pre { background: #1a1b26 !important; padding: 16px; border-radius: 8px; overflow-x: auto; margin-bottom: 1.5em; border: 1px solid var(--border); }
        .md pre code { background: transparent; padding: 0; font-size: 0.88em; }
        .md blockquote { border-left: 3px solid var(--accent); padding: 12px 16px; margin: 0 0 1.2em; background: rgba(59,130,246,0.06); border-radius: 0 6px 6px 0; color: #94a3b8; }
        .md table { width: 100%; border-collapse: collapse; margin-bottom: 1.5em; font-size: 0.92rem; }
        .md th,.md td { padding: 10px 14px; border: 1px solid var(--border); text-align: left; }
        .md th { background: rgba(255,255,255,0.04); font-weight: 600; }
        .md tr:hover td { background: rgba(255,255,255,0.02); }
        .md hr { border: none; border-top: 1px solid var(--border); margin: 2em 0; }

        /* ── Mermaid ──────────────────────────────────── */
        .mermaid-container { background: #ffffff; border-radius: 8px; padding: 20px 16px; margin: 1.5em 0; overflow-x: auto; border: 1px solid var(--border-strong); }
        .mermaid-container svg { max-width: 100%; height: auto; }
        .mermaid-error { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2); border-radius: 8px; padding: 12px 16px; margin: 1.5em 0; font-size: 0.85rem; color: var(--text-muted); }
        .mermaid-error summary { cursor: pointer; color: var(--error); font-weight: 500; margin-bottom: 6px; }
        .mermaid-error pre { margin: 8px 0 0; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 0.82em; white-space: pre-wrap; word-break: break-word; border: none; }

        /* ── Chat panel ───────────────────────────────── */
        #chat-panel {
            width: 0; min-width: 0; height: 100%;
            background: var(--bg-nav);
            backdrop-filter: blur(16px);
            border-left: 1px solid var(--border);
            display: flex; flex-direction: column;
            overflow: hidden;
            transition: width 0.25s cubic-bezier(0.4,0,0.2,1),
                        min-width 0.25s cubic-bezier(0.4,0,0.2,1);
        }
        #chat-panel.open { width: var(--chat-width); min-width: var(--chat-width); }

        #chat-header {
            padding: 16px 16px 12px;
            border-bottom: 1px solid var(--border);
            flex-shrink: 0; display: flex; align-items: center; gap: 10px;
        }
        #chat-header-title { flex: 1; font-size: 0.9rem; font-weight: 600; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        #chat-context-label { font-size: 0.72rem; color: var(--text-muted); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        #chat-close { cursor: pointer; color: var(--text-muted); font-size: 1.1rem; flex-shrink: 0; transition: color 0.15s; }
        #chat-close:hover { color: var(--text-main); }

        #chat-messages {
            flex: 1; overflow-y: auto; padding: 12px 14px;
            display: flex; flex-direction: column; gap: 10px;
        }
        #chat-messages::-webkit-scrollbar { width: 4px; }
        #chat-messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

        .chat-msg { display: flex; flex-direction: column; gap: 3px; max-width: 100%; animation: fadeIn 0.2s ease; }
        .chat-msg.user { align-items: flex-end; }
        .chat-msg.ai { align-items: flex-start; }

        .chat-bubble {
            padding: 10px 13px; border-radius: 10px;
            font-size: 0.84rem; line-height: 1.55; word-break: break-word;
            max-width: 90%;
        }
        .chat-msg.user .chat-bubble { background: var(--user-bubble); border: 1px solid rgba(59,130,246,0.25); color: #e2e8f0; border-radius: 10px 10px 2px 10px; }
        .chat-msg.ai   .chat-bubble { background: var(--ai-bubble);   border: 1px solid var(--border); color: #cbd5e1; border-radius: 10px 10px 10px 2px; }

        .chat-bubble p { margin-bottom: 0.6em; }
        .chat-bubble p:last-child { margin-bottom: 0; }
        .chat-bubble code { font-family: 'Fira Code',monospace; background: rgba(0,0,0,0.3); padding: 0.1em 0.35em; border-radius: 3px; font-size: 0.82em; }
        .chat-bubble pre { background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; overflow-x: auto; margin: 6px 0; }
        .chat-bubble pre code { background: transparent; padding: 0; }

        .chat-meta { font-size: 0.7rem; color: var(--text-muted); padding: 0 2px; }

        .chat-thinking { display: flex; align-items: center; gap: 8px; padding: 10px 13px; color: var(--text-muted); font-size: 0.82rem; }
        .thinking-dots span { display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: var(--accent); animation: dot-bounce 1.2s infinite; }
        .thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
        .thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes dot-bounce { 0%,80%,100% { transform: scale(0.7); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }

        #chat-empty {
            flex: 1; display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            color: var(--text-muted); text-align: center; padding: 20px;
            gap: 8px;
        }
        #chat-empty .chat-empty-icon { font-size: 2rem; opacity: 0.4; }
        #chat-empty p { font-size: 0.82rem; line-height: 1.5; }

        #chat-input-area {
            padding: 12px 14px; border-top: 1px solid var(--border);
            flex-shrink: 0; display: flex; flex-direction: column; gap: 8px;
        }
        #chat-input {
            width: 100%; padding: 9px 12px; border-radius: 7px;
            border: 1px solid var(--border); background: var(--bg-input);
            color: var(--text-main); font-size: 0.84rem; font-family: inherit;
            outline: none; resize: none; min-height: 68px; max-height: 140px;
            transition: border-color 0.2s; line-height: 1.5;
        }
        #chat-input:focus { border-color: var(--accent); }
        #chat-input::placeholder { color: var(--text-muted); opacity: 0.6; }

        #chat-send-row { display: flex; align-items: center; justify-content: space-between; }
        #chat-hint { font-size: 0.72rem; color: var(--text-muted); }
        #chat-send {
            padding: 7px 16px; background: var(--accent); color: #fff;
            border: none; border-radius: 6px; font-size: 0.83rem; font-weight: 600;
            cursor: pointer; transition: background 0.2s;
        }
        #chat-send:hover { background: var(--accent-hover); }
        #chat-send:disabled { background: rgba(59,130,246,0.3); cursor: not-allowed; }

        #chat-no-provider {
            margin: 8px 14px; padding: 10px 12px;
            background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2);
            border-radius: 7px; font-size: 0.78rem; color: #fca5a5;
            display: none;
        }

        /* ── Misc ─────────────────────────────────────── */
        .loader { width: 40px; height: 40px; border: 3px solid rgba(255,255,255,0.08); border-radius: 50%; border-top-color: var(--accent); animation: spin 0.8s linear infinite; margin: 80px auto; }
        .welcome { text-align: center; padding: 120px 20px 40px; color: var(--text-muted); }
        .welcome h2 { font-size: 1.5rem; color: var(--text-main); margin-bottom: 8px; border: none; }
        .welcome .welcome-tips { margin-top: 24px; display: flex; flex-direction: column; gap: 6px; align-items: center; }
        .welcome-tip { font-size: 0.82rem; color: var(--text-muted); background: rgba(255,255,255,0.04); border: 1px solid var(--border); border-radius: 6px; padding: 7px 14px; }

        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        #content-container.loaded { animation: fadeIn 0.3s ease; }
    </style>
</head>
<body>

<!-- ── Sidebar ── -->
<nav id="sidebar">
    <div id="nav-header">
        <h1>DeepRepo Wiki</h1>
        <div id="search-wrap">
            <input type="text" id="search-box" placeholder="Search pages & content…" autocomplete="off">
            <span id="search-clear" title="Clear search">✕</span>
            <div id="search-results"></div>
        </div>
    </div>
    <div id="tree-container">
        <div class="loader" style="width:24px;height:24px;border-width:2px;margin:24px auto;"></div>
    </div>
</nav>

<!-- ── Main view ── -->
<div id="main-view">
    <div id="top-bar">
        <div id="breadcrumb"></div>
        <button id="chat-toggle-btn" title="Ask questions about this page">💬 Ask AI</button>
    </div>
    <div id="content-scroll">
        <div id="content-container">
            <div id="md-output" class="md">
                <div class="welcome">
                    <h2>Welcome to DeepRepo Wiki</h2>
                    <p>Select a page from the sidebar to view its documentation.</p>
                    <div class="welcome-tips">
                        <div class="welcome-tip">📄 Click any page in the sidebar to read it</div>
                        <div class="welcome-tip">🔍 Type in the search box to search page names <em>and</em> content</div>
                        <div class="welcome-tip">💬 Open a page, then click <strong>Ask AI</strong> to chat about it</div>
                    </div>
                </div>
            </div>
            <div id="page-loader" class="loader" style="display:none;"></div>
        </div>
    </div>
</div>

<!-- ── Chat panel ── -->
<div id="chat-panel">
    <div id="chat-header">
        <div style="flex:1;min-width:0;">
            <div id="chat-header-title">Ask AI</div>
            <div id="chat-context-label">No page selected</div>
        </div>
        <span id="chat-close" title="Close chat">✕</span>
    </div>
    <div id="chat-messages">
        <div id="chat-empty">
            <div class="chat-empty-icon">💬</div>
            <p>Ask anything about the<br>current wiki page.</p>
        </div>
    </div>
    <div id="chat-no-provider">
        ⚠ No LLM provider configured. Start the server with a connected client to enable chat.
    </div>
    <div id="chat-input-area">
        <textarea id="chat-input" placeholder="Ask about this page… (Ctrl+Enter to send)" rows="3"></textarea>
        <div id="chat-send-row">
            <span id="chat-hint">Ctrl+Enter to send</span>
            <button id="chat-send">Send</button>
        </div>
    </div>
</div>

<script>
// ── Mermaid ────────────────────────────────────────────────────────────────
mermaid.initialize({
    startOnLoad: false, theme: 'default',
    themeVariables: {
        primaryColor: '#dbeafe', primaryTextColor: '#1e293b',
        primaryBorderColor: '#3b82f6', lineColor: '#64748b',
        secondaryColor: '#f0fdf4', tertiaryColor: '#fefce8',
        fontFamily: 'Inter, sans-serif', fontSize: '14px'
    },
    flowchart: { htmlLabels: true, curve: 'basis', padding: 12 },
    sequence: { diagramMarginX: 40, diagramMarginY: 10, actorMargin: 60, mirrorActors: false },
    securityLevel: 'loose'
});

// ── Mermaid sanitizer ──────────────────────────────────────────────────────
// Handles every broken pattern LLMs produce so diagrams render on first try.
function sanitizeMermaid(raw) {

    // ── Stage 1: block-level fixes ──────────────────────────────────────────
    let code = raw
        // Arrow variant normalisation → -->
        .replace(/==>(?!>)/g,        '-->')   // double-equals arrow
        .replace(/-->>(?!\|)/g,      '-->')   // double-chevron
        .replace(/->>(?!\|)/g,       '-->')   // single-dash chevron
        .replace(/<--(?!>)/g,        '-->')   // backwards arrow
        .replace(/([^-<])->(?![-|>])/g, '$1-->')  // lone -> not part of --> or ->|
        // Pipe label trailing > artefact: |label|> → |label|
        .replace(/(\|[^|\n]*\|)>/g,  '$1')
        // Strip bracket immediately after arrow — LLM writes: --> [Code] nodeId
        .replace(/(-->|--x|--o|---)\s*\[[^\]]*\]\s*/g, '$1 ')
        // Strip markdown formatting that leaks into diagram body
        .replace(/\*\*([^*\n]+)\*\*/g, '$1')
        .replace(/\*([^*\n]+)\*/g,   '$1')
        .replace(/`([^`\n]+)`/g,     '$1')
        // sub → subgraph aliases
        .replace(/^\s*sub\s+"/gm,    'subgraph "')
        .replace(/^\s*sub\s+'/gm,    "subgraph '");

    // ── Stage 2: node token sanitizer ──────────────────────────────────────
    // Accepts any LLM-produced node token and returns valid mermaid.
    // Handles: quoted IDs, double-brackets, missing IDs, bad chars in IDs/labels,
    //          pipe content that ends up as a node, parens inside labels, etc.
    function fixNode(s) {
        s = s.trim();
        if (!s) return s;

        // Strip outer quotes wrapping the whole token
        s = s.replace(/^"(.*)"$/, '$1').replace(/^'(.*)'$/, '$1');

        // Normalise double-bracket subroutine shape [[...]] → [...]
        s = s.replace(/\[\[([^\]]*)\]\]/g, '[$1]');
        // Normalise double-paren cylinder shape ((...)) → (...)
        s = s.replace(/\(\(([^)]*)\)\)/g,  '($1)');

        // Parse: optional_id + optional_shape_suffix
        // Shape suffixes: [rect], (round), {diamond}, ([stadium]), [[sub]], >asymmetric]
        const bm = s.match(/^(.*?)(\[[^\]]*\]|\([^)]*\)|\{[^}]*\}|>\[[^\]]*\])$/);
        let nodeId = bm ? bm[1].trim() : s;
        let shape  = bm ? bm[2]        : '';

        // If no ID but we have a shape, derive a camelCase ID from the label text
        if (!nodeId && shape) {
            const inner = shape.slice(1, -1).trim();
            nodeId = inner
                .split(/\s+/)
                .map((w, i) => i === 0 ? w.toLowerCase() : w[0].toUpperCase() + w.slice(1).toLowerCase())
                .join('')
                .replace(/[^a-zA-Z0-9]/g, '')
                .slice(0, 28) || 'node';
        }

        // Sanitise node ID — only alphanumeric + underscore allowed
        nodeId = nodeId
            .replace(/[^a-zA-Z0-9_]/g, '_')  // replace ALL special chars with _
            .replace(/_+/g, '_')              // collapse runs of _
            .replace(/^_|_$/g, '');           // trim leading/trailing _

        // Must not start with a digit (invalid mermaid)
        if (/^\d/.test(nodeId)) nodeId = 'n' + nodeId;
        if (!nodeId) nodeId = 'node';

        // Sanitise label inner text
        if (shape) {
            const open  = shape[0];
            const close = shape[shape.length - 1];
            let inner   = shape.slice(1, -1);
            inner = inner.replace(/["`]/g,      '');      // strip quotes / backticks
            inner = inner.replace(/&/g,         'and');   // & → and
            inner = inner.replace(/</g,         ' lt ').replace(/>/g, ' gt '); // angle brackets
            inner = inner.replace(/\|/g,        ' or '); // pipe → or
            inner = inner.replace(/:/g,         ' -');   // colon → dash
            inner = inner.replace(/\[|\]/g,     '');     // stray brackets
            inner = inner.replace(/\s+/g,       ' ').trim();
            // Truncate extremely long labels (>60 chars) to avoid layout explosion
            if (inner.length > 60) inner = inner.slice(0, 57) + '...';
            shape = open + inner + close;
        }

        return nodeId + shape;
    }

    // ── Stage 3: pipe-label sanitizer ──────────────────────────────────────
    // Cleans |label| pipe syntax: strips quotes, colons, angle brackets.
    function fixPipeLabel(pl) {
        if (!pl) return '';
        let inner = pl.slice(1, -1);           // strip leading/trailing |
        inner = inner.replace(/["`]/g,   '');
        inner = inner.replace(/</g, ' ').replace(/>/g, ' ');
        inner = inner.replace(/:/g,      ' -');
        inner = inner.replace(/\s+/g,    ' ').trim();
        if (inner.length > 40) inner = inner.slice(0, 37) + '...';
        return '|' + inner + '|';
    }

    // ── Stage 4: line-by-line processing ───────────────────────────────────
    // Regex patterns
    // Graph / diagram type directives — pass through unchanged
    const GRAPH_DIR  = /^\s*(graph|flowchart|sequenceDiagram|erDiagram|gantt|pie|classDiagram|stateDiagram|%%)\b/;
    // subgraph opens a scope; end closes it — tracked for orphan-end detection
    const SUBGRAPH   = /^\s*subgraph\b/;
    const END_LINE   = /^\s*end\s*$/;
    // style / classDef / linkStyle — stripped (often reference stale IDs, non-essential)
    const STYLE_LINE = /^\s*(style|classDef|class\s|linkStyle)\b/;
    // Arrow line: [indent] [lhs] [arrow] [optional |pipe|] [rhs]
    const ARROW_LINE = /^(\s*)(.*?)\s*(-->|--x|--o|---|-\.->)\s*((\|[^|\n]*\|)\s*)?(.+?)\s*$/;
    // Standalone node definition: nodeId[Label] or nodeId(Label) etc.
    // Accepts multi-word IDs that will be fixed by fixNode
    const NODE_DEF   = /^(\s*)(.+?)(\[[^\]]+\]|\([^)]+\)|\{[^}]+\})\s*$/;
    // Plain single-word node ID with no shape
    const PLAIN_ID   = /^(\s*)([a-zA-Z][a-zA-Z0-9_]*)\s*$/;
    // Multi-source / multi-dest joined with &
    const MULTI_NODE = /^(.+?)\s*&\s*(.+)$/;

    let subgraphDepth = 0;

    const lines = code.split('\n').map(line => {
        const trimmed = line.trim();

        // 4a. Graph type directives pass through
        if (GRAPH_DIR.test(line)) return line;

        // 4b. subgraph — track depth, pass through
        if (SUBGRAPH.test(line)) { subgraphDepth++; return line; }

        // 4c. end — only keep if inside a subgraph (orphan `end` breaks mermaid)
        if (END_LINE.test(line)) {
            if (subgraphDepth > 0) { subgraphDepth--; return line; }
            return null;  // orphan end — remove it
        }

        // 4d. Style / classDef lines — strip entirely (non-essential, often stale)
        if (STYLE_LINE.test(line)) return null;

        // 4e. Blank lines pass through
        if (!trimmed) return line;

        // 4f. Arrow lines — sanitize both ends and the pipe label
        const am = line.match(ARROW_LINE);
        if (am) {
            const [, indent, lhsRaw, arrow, , pipeRaw, rhsRaw] = am;
            const fixSide = (s) => {
                const mm = s.match(MULTI_NODE);
                return mm ? fixNode(mm[1]) + ' & ' + fixNode(mm[2]) : fixNode(s);
            };
            return indent + fixSide(lhsRaw) + ' ' + arrow + fixPipeLabel(pipeRaw) + ' ' + fixSide(rhsRaw);
        }

        // 4g. Standalone node definitions: nodeId[Label] / nodeId(Label) / nodeId{Label}
        const nm = trimmed.match(NODE_DEF);
        if (nm) {
            const indent = line.match(/^(\s*)/)[1];
            return indent + fixNode(nm[2] + nm[3]);
        }

        // 4h. Plain single-word node ID (no shape) — valid, pass through
        if (PLAIN_ID.test(line)) return line;

        // 4i. Prose / injected text — remove clearly non-mermaid lines
        const isProse = (
            /^(REPLACE|Note[:\s]|NOTE[:\s]|Fill\s|This |The |Use |Do |See |Example|>>|TODO)/i.test(trimmed) ||
            (/[.?!]$/.test(trimmed) && trimmed.split(' ').length > 4) ||
            (trimmed.split(' ').length > 8 && !/[\[\]({>-]/.test(trimmed))
        );
        if (isProse) return null;

        // 4j. Anything else — pass through (might be valid syntax we don't recognise)
        return line;
    });

    return lines.filter(l => l !== null).join('\n');
}

const renderer = new marked.Renderer();
let mermaidCounter = 0;

renderer.code = function(codeObj) {
    const text = codeObj?.text ?? codeObj;
    const lang = codeObj?.lang ?? arguments[1] ?? '';

    if (lang && lang.toLowerCase() === 'mermaid') {
        const id = 'mermaid-block-' + (mermaidCounter++);
        const code = sanitizeMermaid(text);
        return `<div class="mermaid-container"><div class="mermaid" id="${id}">${escapeHtml(code)}</div></div>`;
    }
    const validLang = lang && hljs.getLanguage(lang) ? lang : '';
    let highlighted;
    if (validLang) {
        try { highlighted = hljs.highlight(text, { language: validLang }).value; }
        catch(_) { highlighted = escapeHtml(text); }
    } else { highlighted = escapeHtml(text); }
    return `<pre><code class="hljs${validLang ? ' language-' + validLang : ''}">${highlighted}</code></pre>`;
};

function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

marked.setOptions({ renderer, breaks: true, gfm: true, headerIds: true });

// ── State ──────────────────────────────────────────────────────────────────
let activePath = null;
let treeData   = null;
let chatOpen   = false;
let chatHasProvider = true;
const chatHistory = [];  // {role: 'user'|'ai', text: string}

// ── Tree ───────────────────────────────────────────────────────────────────
async function loadTree() {
    try {
        const res = await fetch('/api/tree');
        treeData = await res.json();
        renderTree(treeData);
        const overviewPath = findFile(treeData, 'overview.md', '');
        if (overviewPath) loadPage(overviewPath);
    } catch(e) {
        document.getElementById('tree-container').innerHTML =
            '<p style="color:var(--error);padding:12px;">Could not load wiki tree.</p>';
    }
}

function findFile(node, name, prefix) {
    if (node.files) for (const f of node.files) if (f.toLowerCase() === name.toLowerCase()) return prefix ? prefix+'/'+f : f;
    if (node.dirs) for (const [d,sub] of Object.entries(node.dirs)) { const r = findFile(sub,name,prefix?prefix+'/'+d:d); if(r) return r; }
    return null;
}

function renderTree(data) {
    const c = document.getElementById('tree-container');
    c.innerHTML = '';
    const root = buildTreeNode(data, 'Wiki', '');
    c.appendChild(root);
    const ch = root.querySelector('.tree-children');
    if (ch) ch.classList.add('open');
}

function buildTreeNode(node, name, path) {
    const el = document.createElement('div');
    el.className = 'tree-node';
    const isDir = node.type === 'directory';
    const label = document.createElement('div');
    label.className = 'tree-label';
    label.dataset.name = name.toLowerCase();
    const displayName = name.replace(/\.md$/,'').replaceAll('_',' ');
    label.innerHTML = `<span class="tree-icon">${isDir?'📁':'📄'}</span><span>${displayName}</span>`;
    if (isDir) {
        const cc = document.createElement('div'); cc.className = 'tree-children';
        const dirs = Object.keys(node.dirs||{}).sort();
        const files = (node.files||[]).sort();
        dirs.forEach(d => { const p = path?path+'/'+d:d; cc.appendChild(buildTreeNode(node.dirs[d],d,p)); });
        files.forEach(f => { const p = path?path+'/'+f:f; cc.appendChild(buildTreeNode({type:'file',path:p},f,p)); });
        label.onclick = () => { cc.classList.toggle('open'); label.querySelector('.tree-icon').textContent = cc.classList.contains('open')?'📂':'📁'; };
        el.appendChild(label); el.appendChild(cc);
    } else {
        label.onclick = () => loadPage(node.path);
        el.appendChild(label);
    }
    return el;
}

// ── Search ─────────────────────────────────────────────────────────────────
let _searchTimer = null;

document.addEventListener('DOMContentLoaded', () => {
    const box = document.getElementById('search-box');
    const clear = document.getElementById('search-clear');
    const results = document.getElementById('search-results');

    box.addEventListener('input', () => {
        const q = box.value.trim();
        clear.style.display = q ? 'block' : 'none';

        // Sidebar name filter (instant)
        const qLow = q.toLowerCase();
        document.querySelectorAll('.tree-node').forEach(n => {
            const lbl = n.querySelector(':scope > .tree-label');
            if (!lbl) return;
            const match = !q || (lbl.dataset.name||'').includes(qLow);
            lbl.classList.toggle('hidden', !match && !n.querySelector('.tree-label:not(.hidden)'));
        });
        if (q) document.querySelectorAll('.tree-children').forEach(c => { if (c.querySelector('.tree-label:not(.hidden)')) c.classList.add('open'); });

        // Debounced full-text search
        clearTimeout(_searchTimer);
        if (q.length >= 2) {
            _searchTimer = setTimeout(() => fetchSearchResults(q), 320);
        } else {
            closeSearchResults();
        }
    });

    // Close results when clicking outside
    document.addEventListener('click', e => {
        if (!document.getElementById('search-wrap').contains(e.target)) closeSearchResults();
    });

    clear.addEventListener('click', () => {
        box.value = '';
        clear.style.display = 'none';
        closeSearchResults();
        // reset tree filter
        document.querySelectorAll('.tree-label').forEach(l => l.classList.remove('hidden'));
    });

    loadTree();
});

async function fetchSearchResults(query) {
    try {
        const res = await fetch('/api/search?q=' + encodeURIComponent(query));
        const data = await res.json();
        renderSearchResults(query, data);
    } catch(e) { closeSearchResults(); }
}

function renderSearchResults(query, items) {
    const container = document.getElementById('search-results');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="sr-empty">No content matches found</div>';
        container.classList.add('open');
        return;
    }
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    function highlight(text) {
        let out = escapeHtml(text);
        terms.forEach(t => {
            const re = new RegExp(escapeHtml(t).replace(/[.*+?^${}()|[\]\\]/g,'\\$&'), 'gi');
            out = out.replace(re, m => `<mark>${m}</mark>`);
        });
        return out;
    }
    let html = `<div class="sr-header">Content matches (${items.length})</div>`;
    items.forEach(item => {
        html += `<div class="sr-item" onclick="loadPage(${JSON.stringify(item.path)}); closeSearchResults();">
            <div class="sr-item-title">${highlight(item.name)}</div>
            <div class="sr-item-snippet">${highlight(item.snippet)}</div>
        </div>`;
    });
    container.innerHTML = html;
    container.classList.add('open');
}

function closeSearchResults() {
    const r = document.getElementById('search-results');
    r.classList.remove('open');
    r.innerHTML = '';
}

// ── Page loading ───────────────────────────────────────────────────────────
async function loadPage(path) {
    activePath = path;
    closeSearchResults();

    const output = document.getElementById('md-output');
    const loader = document.getElementById('page-loader');
    const bc     = document.getElementById('breadcrumb');

    document.querySelectorAll('.tree-label').forEach(l => {
        l.classList.toggle('active', l.onclick && l.onclick.toString().includes(path));
    });

    output.style.display = 'none';
    loader.style.display = 'block';
    mermaidCounter = 0;

    try {
        const res = await fetch('/api/page?path=' + encodeURIComponent(path));
        if (!res.ok) throw new Error(res.statusText);
        let md = await res.text();
        md = md.replace(/<\/?WIKI>/g,'').replace(/<\/?OVERVIEW>/g,'');
        md = md.replace(/^```[a-zA-Z]*\r?\n?/i,'').replace(/\n?```\s*$/,'');

        output.innerHTML = marked.parse(md);
        output.style.display = 'block';
        output.parentElement.className = 'loaded';

        // Breadcrumb
        const parts = path.split('/');
        let acc = '';
        const crumbs = parts.map((p, i) => {
            acc += (i ? '/' : '') + p;
            const display = p.replace(/\.md$/,'').replaceAll('_',' ');
            return i < parts.length-1
                ? `<a onclick="expandToPath('${acc}')">${display}</a>`
                : `<span>${display}</span>`;
        });
        bc.innerHTML = crumbs.join('<span class="sep">/</span>');
        bc.style.display = 'block';

        // Show chat toggle
        const toggleBtn = document.getElementById('chat-toggle-btn');
        toggleBtn.style.display = 'block';

        // Update chat context label
        const pageName = parts[parts.length-1].replace(/\.md$/,'').replaceAll('_',' ');
        document.getElementById('chat-context-label').textContent = 'Page: ' + pageName;

        // Intercept .md links
        output.querySelectorAll('a[href]').forEach(a => {
            const href = a.getAttribute('href');
            if (href && href.endsWith('.md') && !href.startsWith('http')) {
                a.addEventListener('click', e => {
                    e.preventDefault();
                    const dir = path.includes('/') ? path.substring(0, path.lastIndexOf('/')) : '';
                    loadPage(dir ? dir+'/'+href : href);
                });
            }
        });

        await renderMermaidBlocks();
        document.getElementById('content-scroll').scrollTop = 0;

    } catch(e) {
        output.innerHTML = `<div style="color:var(--error);padding:40px;text-align:center;"><h3>Page not found</h3><p>${escapeHtml(path)}</p></div>`;
        output.style.display = 'block';
    } finally {
        loader.style.display = 'none';
    }
}

async function renderMermaidBlocks() {
    const blocks = document.querySelectorAll('.mermaid');
    for (const block of blocks) {
        const code = block.textContent;
        const container = block.parentElement;
        try {
            const { svg } = await mermaid.render(block.id || ('m-'+Math.random().toString(36).slice(2)), code);
            container.innerHTML = svg;
        } catch(err) {
            container.className = 'mermaid-error';
            container.innerHTML = `<details><summary>Diagram render failed</summary><pre>${escapeHtml(code)}</pre></details>`;
        }
    }
}

function expandToPath(path) {
    const segments = path.split('/');
    let container = document.getElementById('tree-container');
    segments.forEach(seg => {
        const labels = container.querySelectorAll(':scope > .tree-node > .tree-label');
        for (const l of labels) {
            if ((l.dataset.name||'').includes(seg.toLowerCase())) {
                const children = l.nextElementSibling;
                if (children && children.classList.contains('tree-children')) {
                    children.classList.add('open'); container = children;
                }
                break;
            }
        }
    });
}

// ── Chat ───────────────────────────────────────────────────────────────────
const chatPanel      = document.getElementById('chat-panel');
const chatMessages   = document.getElementById('chat-messages');
const chatInput      = document.getElementById('chat-input');
const chatSend       = document.getElementById('chat-send');
const chatEmpty      = document.getElementById('chat-empty');
const chatNoProvider = document.getElementById('chat-no-provider');
const chatToggleBtn  = document.getElementById('chat-toggle-btn');

chatToggleBtn.addEventListener('click', toggleChat);
document.getElementById('chat-close').addEventListener('click', () => setChat(false));

function toggleChat() { setChat(!chatOpen); }
function setChat(open) {
    chatOpen = open;
    chatPanel.classList.toggle('open', open);
    chatToggleBtn.classList.toggle('active', open);
    if (open) chatInput.focus();
}

chatSend.addEventListener('click', sendChat);
chatInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); sendChat(); }
});

function renderMarkdownInBubble(text) {
    // Simple inline-safe markdown render for chat bubbles
    try { return marked.parse(text); }
    catch(_) { return escapeHtml(text).replace(/\n/g,'<br>'); }
}

function appendMessage(role, text) {
    chatHistory.push({ role, text });
    if (chatEmpty) chatEmpty.style.display = 'none';

    const wrap = document.createElement('div');
    wrap.className = `chat-msg ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    bubble.innerHTML = renderMarkdownInBubble(text);

    const meta = document.createElement('div');
    meta.className = 'chat-meta';
    meta.textContent = role === 'user' ? 'You' : 'AI';

    wrap.appendChild(bubble);
    wrap.appendChild(meta);
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrap;
}

function appendThinking() {
    const wrap = document.createElement('div');
    wrap.className = 'chat-msg ai';
    wrap.innerHTML = `<div class="chat-thinking">
        <div class="thinking-dots"><span></span><span></span><span></span></div>
        <span>Thinking…</span></div>`;
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrap;
}

async function sendChat() {
    const q = chatInput.value.trim();
    if (!q || chatSend.disabled) return;

    chatInput.value = '';
    chatSend.disabled = true;
    appendMessage('user', q);

    const thinking = appendThinking();

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: q, page_path: activePath || '' })
        });
        const data = await res.json();
        thinking.remove();

        if (data.error) {
            if (data.error === 'no_provider') {
                chatNoProvider.style.display = 'block';
                chatSend.disabled = true;
            } else {
                appendMessage('ai', '⚠ ' + data.error);
            }
        } else {
            chatNoProvider.style.display = 'none';
            appendMessage('ai', data.answer || '(no response)');
        }
    } catch(e) {
        thinking.remove();
        appendMessage('ai', '⚠ Network error: ' + e.message);
    } finally {
        chatSend.disabled = false;
        chatInput.focus();
    }
}
</script>
</body>
</html>
"""


class _WikiHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the wiki viewer."""

    wiki_dir: str = ".deeprepo/wiki"
    llm_provider: object = None   # LLMProvider instance, injected by serve()
    graph_store: object = None    # GraphStore instance, injected by serve()

    def log_message(self, format, *args):  # noqa: A002
        logger.debug(format, *args)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            self._send_html(INDEX_HTML)
        elif path == "/api/tree":
            self._serve_tree()
        elif path == "/api/page":
            self._serve_page(query.get("path", [""])[0])
        elif path == "/api/search":
            self._serve_search(query.get("q", [""])[0])
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):  # noqa: N802
        if self.path == "/api/chat":
            self._handle_chat()
        else:
            self.send_error(404, "Not Found")

    # ── Responses ─────────────────────────────────────────────────────────

    def _send_html(self, html: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_json(self, obj: dict | list) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _send_text(self, text: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    # ── GET endpoints ──────────────────────────────────────────────────────

    def _serve_tree(self) -> None:
        wiki = self.__class__.wiki_dir
        if not os.path.isdir(wiki):
            self.send_error(404, "Wiki directory not found")
            return
        self._send_json(self._build_tree(wiki))

    def _serve_page(self, rel_path: str) -> None:
        if not rel_path:
            self.send_error(400, "Missing path parameter")
            return
        wiki = os.path.abspath(self.__class__.wiki_dir)
        full = os.path.abspath(os.path.join(wiki, rel_path))
        if not full.startswith(wiki):
            self.send_error(403, "Forbidden")
            return
        if not os.path.isfile(full):
            self.send_error(404, "File not found")
            return
        with open(full, "r", encoding="utf-8") as f:
            self._send_text(f.read())

    def _serve_search(self, query: str) -> None:
        """Full-text search across all wiki .md files."""
        query = query.strip()
        if not query or len(query) < 2:
            self._send_json([])
            return

        results = self._search_fulltext(query)
        self._send_json(results)

    def _search_fulltext(self, query: str) -> list[dict]:
        """Disk-based full-text search with ranked results and snippets."""
        wiki = self.__class__.wiki_dir
        if not os.path.isdir(wiki):
            return []

        terms = [t.lower() for t in query.lower().split() if t]
        scored: list[tuple[int, str, str, str]] = []  # (score, path, name, snippet)

        wiki_abs = os.path.abspath(wiki)
        for md_file in Path(wiki_abs).rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                content_lower = content.lower()

                # Score: title matches worth more than body matches
                name = md_file.stem.replace("_", " ")
                name_lower = name.lower()
                score = 0
                for t in terms:
                    score += name_lower.count(t) * 5
                    score += content_lower.count(t)

                if score == 0:
                    continue

                # Build snippet: find context around the first matching term
                snippet = ""
                for t in terms:
                    idx = content_lower.find(t)
                    if idx >= 0:
                        start = max(0, idx - 60)
                        end = min(len(content), idx + 140)
                        raw = content[start:end].replace("\n", " ").strip()
                        if start > 0:
                            raw = "…" + raw
                        if end < len(content):
                            raw = raw + "…"
                        snippet = raw
                        break

                rel = str(md_file.relative_to(wiki_abs))
                scored.append((score, rel, name, snippet))
            except Exception:
                pass

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"path": path, "name": name, "snippet": snippet}
            for _, path, name, snippet in scored[:12]
        ]

    # ── POST endpoint: chat ────────────────────────────────────────────────

    def _handle_chat(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send_json({"error": "invalid request body"})
            return

        question = body.get("question", "").strip()
        page_path = body.get("page_path", "").strip()

        if not question:
            self._send_json({"error": "empty question"})
            return

        provider = self.__class__.llm_provider
        if provider is None:
            self._send_json({"error": "no_provider"})
            return

        # Load the current page as context
        context = self._load_page_context(page_path)

        try:
            system_prompt = (
                "You are a helpful assistant answering questions about a software codebase. "
                "The user is reading a wiki page about the codebase and has a question. "
                "Use the wiki page content as your primary context. "
                "Be concise, precise, and developer-friendly. "
                "When referencing code concepts, use `backticks`. "
                "If the page doesn't contain enough info to answer, say so clearly."
            )
            if context:
                # Truncate to ~8K chars to stay within context limits
                ctx_truncated = context[:8000] + ("\n\n[…page truncated…]" if len(context) > 8000 else "")
                prompt = f"Wiki page content:\n\n{ctx_truncated}\n\n---\n\nQuestion: {question}"
            else:
                prompt = question

            answer = provider.generate(prompt=prompt, system_prompt=system_prompt)
            self._send_json({"answer": answer})

        except Exception as exc:
            logger.warning("Chat LLM call failed: %s", exc)
            self._send_json({"error": f"LLM error: {exc}"})

    def _load_page_context(self, rel_path: str) -> str:
        """Read a wiki page's markdown content for use as chat context."""
        if not rel_path:
            return ""
        wiki = os.path.abspath(self.__class__.wiki_dir)
        full = os.path.abspath(os.path.join(wiki, rel_path))
        if not full.startswith(wiki) or not os.path.isfile(full):
            return ""
        try:
            with open(full, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    # ── Helpers ────────────────────────────────────────────────────────────

    def _build_tree(self, root: str) -> dict:
        tree: dict = {"type": "directory", "dirs": {}, "files": []}
        try:
            for item in sorted(os.listdir(root)):
                if item.startswith("."):
                    continue
                full = os.path.join(root, item)
                if os.path.isdir(full):
                    tree["dirs"][item] = self._build_tree(full)
                elif item.endswith(".md"):
                    tree["files"].append(item)
        except OSError:
            pass
        return tree


def _resolve_wiki_dir(wiki_dir: str) -> str:
    """Resolve wiki directory, auto-detecting branch if the default path doesn't exist."""
    if os.path.isdir(wiki_dir):
        return wiki_dir
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch == "HEAD":
                result2 = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    capture_output=True, text=True, timeout=5,
                )
                branch = result2.stdout.strip() if result2.returncode == 0 else branch
            safe = branch.replace("/", "-").replace("\\", "-").replace(" ", "-")
            deeprepo_dir = os.path.dirname(wiki_dir) if wiki_dir != ".deeprepo/wiki" else ".deeprepo"
            candidate = os.path.join(deeprepo_dir, f"{safe}-wiki")
            if os.path.isdir(candidate):
                return candidate
    except Exception:
        pass
    deeprepo_dir = ".deeprepo"
    if os.path.isdir(deeprepo_dir):
        for entry in sorted(os.listdir(deeprepo_dir)):
            if entry.endswith("-wiki") and os.path.isdir(os.path.join(deeprepo_dir, entry)):
                return os.path.join(deeprepo_dir, entry)
    return wiki_dir


def serve(
    wiki_dir: str = ".deeprepo/wiki",
    port: int = 8080,
    llm_provider: object = None,
    graph_store: object = None,
) -> None:
    """Start the wiki viewer server.

    Args:
        wiki_dir:     Path to the wiki directory containing .md files.
        port:         Port number for the HTTP server.
        llm_provider: LLMProvider instance — enables the in-page chat feature.
                      If None, chat is disabled with a visible notice.
        graph_store:  GraphStore instance — currently reserved for future FTS
                      acceleration; disk-based search is used otherwise.
    """
    wiki_dir = _resolve_wiki_dir(wiki_dir)
    wiki_dir = str(Path(wiki_dir).resolve())

    if not os.path.isdir(wiki_dir):
        logger.warning("Wiki directory '%s' not found. Run ingest first.", wiki_dir)

    _WikiHandler.wiki_dir     = wiki_dir
    _WikiHandler.llm_provider = llm_provider
    _WikiHandler.graph_store  = graph_store

    httpd = HTTPServer(("", port), _WikiHandler)
    url = f"http://localhost:{port}"
    chat_status = "enabled" if llm_provider else "disabled (no LLM provider)"
    logger.info(
        "DeepRepo Wiki server at %s  (wiki=%s, chat=%s)",
        url, wiki_dir, chat_status,
    )

    threading.Thread(
        target=lambda: (time.sleep(0.5), webbrowser.open(url)),
        daemon=True,
    ).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
        logger.info("Server stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    serve()
