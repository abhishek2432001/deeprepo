"""Ingestion Engine - File scanning and text chunking.

Provides utilities for traversing directories and splitting files into
chunks suitable for embedding.
"""

import os
from pathlib import Path
from typing import Generator


# Directories to ignore during scanning
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

# Binary file extensions to skip
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
    """Check if a file is binary based on extension or content.
    
    Args:
        filepath: Path to the file to check.
        
    Returns:
        True if the file appears to be binary, False otherwise.
    """
    # Check extension first
    if filepath.suffix.lower() in BINARY_EXTENSIONS:
        return True
        
    # Try reading first few bytes to detect binary content
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            # Check for null bytes (common in binary files)
            if b'\x00' in chunk:
                return True
    except (IOError, PermissionError):
        return True  # Skip files we can't read
        
    return False


def scan_directory(root_path: str | Path) -> Generator[Path, None, None]:
    """Recursively scan a directory for text files.
    
    Ignores .git, __pycache__, node_modules, and binary files.
    
    Args:
        root_path: Root directory to scan.
        
    Yields:
        Path objects for each valid text file found.
    """
    root = Path(root_path)
    
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root_path}")
        
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")
    
    for dirpath, dirnames, filenames in os.walk(root):
        # Modify dirnames in-place to skip ignored directories
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        
        for filename in filenames:
            filepath = Path(dirpath) / filename
            
            # Skip hidden files
            if filename.startswith('.'):
                continue
                
            # Skip binary files
            if is_binary_file(filepath):
                continue
                
            yield filepath


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 100
) -> list[str]:
    """Split text into overlapping chunks.
    
    Uses character-based chunking with overlap to preserve context
    at chunk boundaries.
    
    Args:
        text: The text to split into chunks.
        chunk_size: Maximum characters per chunk. Defaults to 1000.
        overlap: Number of overlapping characters between chunks. Defaults to 100.
        
    Returns:
        List of text chunks.
    """
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
            
        # Move start forward by (chunk_size - overlap)
        start += chunk_size - overlap
        
        # Prevent infinite loop if overlap >= chunk_size
        if chunk_size <= overlap:
            start = end
            
    return chunks


def ingest_directory(
    root_path: str | Path,
    chunk_size: int = 1000,
    overlap: int = 100
) -> list[dict]:
    """Ingest all files in a directory into chunks.
    
    Scans the directory recursively, reads each text file, and splits
    content into overlapping chunks with metadata.
    
    Args:
        root_path: Root directory to ingest.
        chunk_size: Maximum characters per chunk. Defaults to 1000.
        overlap: Number of overlapping characters between chunks. Defaults to 100.
        
    Returns:
        List of chunk dictionaries containing:
            - 'text': The chunk text content
            - 'metadata': Dict with 'filepath', 'chunk_index', 'total_chunks'
    """
    root = Path(root_path)
    all_chunks = []
    
    for filepath in scan_directory(root):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except (IOError, PermissionError) as e:
            print(f"Warning: Could not read {filepath}: {e}")
            continue
            
        if not content.strip():
            continue
            
        file_chunks = chunk_text(content, chunk_size, overlap)
        relative_path = filepath.relative_to(root)
        
        for i, chunk_text_content in enumerate(file_chunks):
            all_chunks.append({
                'text': chunk_text_content,
                'metadata': {
                    'filepath': str(relative_path),
                    'chunk_index': i,
                    'total_chunks': len(file_chunks),
                }
            })
            
    return all_chunks
