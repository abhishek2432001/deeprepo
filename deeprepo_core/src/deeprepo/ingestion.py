"""File scanning and text chunking for ingestion."""

import os
from pathlib import Path
from typing import Generator

IGNORED_DIRS = {
    '.git',
    '__pycache__',
    'node_modules',
    '.venv',
    'venv',
    '.env',
    '.idea',
    '.vscode',
    'dist',
    'build',
    '.egg-info',
}
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
    '.mp3', '.mp4', '.wav', '.avi', '.mov',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.exe', '.dll', '.so', '.dylib',
    '.pyc', '.pyo', '.class', '.o',
    '.db', '.sqlite', '.sqlite3',
    '.woff', '.woff2', '.ttf', '.eot',
}


def is_binary_file(filepath: Path) -> bool:
    """Check if a file is binary based on extension or content."""
    if filepath.suffix.lower() in BINARY_EXTENSIONS:
        return True
        
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            if b'\x00' in chunk:
                return True
    except (IOError, PermissionError):
        return True  # Skip files we can't read
        
    return False


def scan_directory(root_path: str | Path) -> Generator[Path, None, None]:
    """Recursively yield text files, skipping ignored dirs and binaries."""
    root = Path(root_path)
    
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root_path}")
        
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")
    
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        
        for filename in filenames:
            filepath = Path(dirpath) / filename
            
            if filename.startswith('.'):
                continue
                
            if is_binary_file(filepath):
                continue
                
            yield filepath


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 100
) -> list[str]:
    """Split text into overlapping chunks."""
    if not text or not text.strip():
        return []
        
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end]
        
        if chunk.strip():  # Only add non-empty chunks
            chunks.append(chunk)
            
        start += chunk_size - overlap

        if chunk_size <= overlap:
            start = end
            
    return chunks


def ingest_directory(
    root_path: str | Path,
    chunk_size: int = 1000,
    overlap: int = 100
) -> tuple[list[dict], list[tuple[str, str]]]:
    """Scan directory, read text files, and return chunks with metadata."""
    root = Path(root_path)
    all_chunks = []
    file_contents: list[tuple[str, str]] = []  # (relative_path, content)

    for filepath in scan_directory(root):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except (IOError, PermissionError) as e:
            print(f"Warning: Could not read {filepath}: {e}")
            continue

        if not content.strip():
            continue

        relative_path = str(filepath.relative_to(root))
        file_contents.append((relative_path, content))

        file_chunks = chunk_text(content, chunk_size, overlap)

        for i, chunk_text_content in enumerate(file_chunks):
            all_chunks.append({
                'text': chunk_text_content,
                'metadata': {
                    'filepath': relative_path,
                    'chunk_index': i,
                    'total_chunks': len(file_chunks),
                }
            })

    return all_chunks, file_contents


def compute_file_hash(content: str) -> str:
    """SHA-256 hex digest of file content."""
    import hashlib
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
