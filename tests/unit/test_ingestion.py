"""Unit tests for ingestion module."""

import pytest
from pathlib import Path
from deeprepo.ingestion import scan_directory, chunk_text


class TestScanDirectory:
    """Test directory scanning functionality."""
    
    def test_scan_finds_python_files(self, tmp_path):
        """Should find Python files in directory."""
        # Create test files
        (tmp_path / "file1.py").write_text("print('hello')")
        (tmp_path / "file2.py").write_text("print('world')")
        (tmp_path / "readme.txt").write_text("docs")
        
        files = scan_directory(str(tmp_path))
        py_files = [str(f) for f in files if str(f).endswith('.py')]
        
        assert len(py_files) == 2
    
    def test_scan_ignores_git_directory(self, tmp_path):
        """Should ignore .git directories."""
        # Create .git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")
        
        # Create regular file
        (tmp_path / "code.py").write_text("code")
        
        files = scan_directory(str(tmp_path))
        
        assert all(".git" not in str(f) for f in files)
    
    def test_scan_ignores_pycache(self, tmp_path):
        """Should ignore __pycache__ directories."""
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "module.pyc").write_text("compiled")
        
        files = list(scan_directory(str(tmp_path)))
        
        assert len(files) == 0


class TestChunkText:
    """Test text chunking functionality."""
    
    def test_chunk_creates_correct_number_of_chunks(self):
        """Should create correct number of chunks."""
        text = "a" * 1500  # 1500 characters
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        
        # Should create 3-4 chunks with this size
        assert 3 <= len(chunks) <= 4
    
    def test_chunks_have_correct_size(self):
        """Each chunk should not exceed chunk_size."""
        text =  "a" * 2000
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        
        for chunk in chunks:
            assert len(chunk) <= 500
    
    def test_chunks_have_overlap(self):
        """Adjacent chunks should share overlapping content."""
        text = "abcdefghijklmnopqrstuvwxyz" * 40  # 1040 chars
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        
        if len(chunks) > 1:
            # Check that end of chunk 1 appears in start of chunk 2
            end_of_first = chunks[0][-50:]
            start_of_second = chunks[1][:50]
            # Should have some overlap
            assert end_of_first in chunks[1] or start_of_second in chunks[0]
    
    def test_empty_text_returns_no_chunks(self):
        """Empty text should return no chunks."""
        chunks = chunk_text("", chunk_size=500, overlap=50)
        
        assert len(chunks) == 0
    
    def test_small_text_returns_single_chunk(self):
        """Text smaller than chunk_size should return single chunk."""
        text = "Small text"
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        
        assert len(chunks) == 1
        assert chunks[0] == text
