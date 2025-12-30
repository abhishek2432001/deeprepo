# Publishing DeepRepo to PyPI

This guide will walk you through publishing **DeepRepo** to PyPI (Python Package Index) so anyone can install it with `pip install deeprepo`.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Publication Checklist](#pre-publication-checklist)
3. [Testing with TestPyPI (Recommended)](#testing-with-testpypi-recommended)
4. [Publishing to PyPI (Production)](#publishing-to-pypi-production)
5. [Post-Publication](#post-publication)
6. [Updating Your Package](#updating-your-package)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### 1. Create PyPI Accounts

You'll need accounts on both TestPyPI (for testing) and PyPI (production):

**TestPyPI (for testing):**
- Go to: https://test.pypi.org/account/register/
- Create an account
- Verify your email

**PyPI (production):**
- Go to: https://pypi.org/account/register/
- Create an account
- Verify your email

### 2. Install Required Tools

```bash
cd deeprepo_core
pip install build twine
```

Or install dev dependencies:
```bash
pip install -e ".[dev]"
```

### 3. Create API Tokens (Recommended)

Instead of using passwords, use API tokens for better security.

**For TestPyPI:**
1. Log in to https://test.pypi.org
2. Go to Account Settings → API tokens
3. Click "Add API token"
4. Name: "deeprepo-upload"
5. Scope: "Entire account" (or project-specific after first upload)
6. Copy the token (starts with `pypi-`)
7. Save it securely!

**For PyPI:**
1. Log in to https://pypi.org
2. Go to Account Settings → API tokens
3. Click "Add API token"
4. Name: "deeprepo-upload"
5. Scope: "Entire account"
6. Copy the token
7. Save it securely!

---

## Pre-Publication Checklist

### ✅ Essential Files

Make sure you have all required files:

```bash
# Check from repository root
ls -la deeprepo_core/

# Should have:
# - pyproject.toml ✓
# - README.md ✓
# - src/deeprepo/ (source code) ✓
# - LICENSE (in repo root) ✓
```

### ✅ Update Configuration

**1. Update `pyproject.toml`:**

Open `deeprepo_core/pyproject.toml` and update:

```toml
[project]
version = "0.1.0"  # Update version for releases
authors = [
    {name = "Your Name", email = "your.email@example.com"}  # ← UPDATE THIS
]

[project.urls]
Homepage = "https://github.com/YOUR_USERNAME/deeprepo"  # ← UPDATE THIS
Repository = "https://github.com/YOUR_USERNAME/deeprepo"  # ← UPDATE THIS
```

**2. Copy LICENSE to package:**

```bash
# From repository root
cp LICENSE deeprepo_core/
```

### ✅ Clean Previous Builds

```bash
cd deeprepo_core

# Remove old builds
rm -rf build/ dist/ *.egg-info

# Start fresh
```

### ✅ Verify Package Structure

```bash
# Your structure should look like:
deeprepo_core/
├── pyproject.toml
├── README.md
├── LICENSE
└── src/
    └── deeprepo/
        ├── __init__.py
        ├── client.py
        ├── storage.py
        ├── ingestion.py
        ├── interfaces.py
        ├── registry.py
        └── providers/
            ├── __init__.py
            ├── ollama_v.py
            ├── huggingface_v.py
            ├── openai_v.py
            └── gemini_v.py
```

---

## Testing with TestPyPI (Recommended)

**Always test on TestPyPI first!** This lets you catch issues before publishing to the real PyPI.

### Step 1: Build the Package

```bash
cd deeprepo_core

# Build distribution packages
python -m build
```

This creates:
- `dist/deeprepo-0.1.0.tar.gz` (source distribution)
- `dist/deeprepo-0.1.0-py3-none-any.whl` (wheel distribution)

### Step 2: Upload to TestPyPI

```bash
# Upload to TestPyPI
python -m twine upload --repository testpypi dist/*
```

You'll be prompted:
```
Enter your username: __token__
Enter your password: [paste your TestPyPI API token here]
```

**Note**: Username is literally `__token__` (with underscores), not your username!

### Step 3: Test Installation from TestPyPI

```bash
# Create a test environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    deeprepo
```

**Why `--extra-index-url`?** TestPyPI doesn't have all dependencies, so we also use regular PyPI for dependencies like numpy, openai, etc.

### Step 4: Test Your Package

```bash
# Test in Python
python
```

```python
>>> from deeprepo import DeepRepoClient
>>> client = DeepRepoClient(provider_name="ollama")
>>> print("DeepRepo installed successfully!")
>>> exit()
```

### Step 5: Clean Up Test Environment

```bash
deactivate
rm -rf test_env
```

---

## Publishing to PyPI (Production)

**⚠️ WARNING**: Once published to PyPI, you **cannot delete or re-upload** the same version. Make sure everything works on TestPyPI first!

### Step 1: Ensure Everything is Ready

- ✅ Tested on TestPyPI
- ✅ All tests pass: `pytest tests/`
- ✅ Version number is correct in `pyproject.toml`
- ✅ README.md looks good
- ✅ LICENSE is included

### Step 2: Build Fresh Distribution

```bash
cd deeprepo_core

# Clean old builds
rm -rf build/ dist/ *.egg-info

# Build fresh
python -m build
```

### Step 3: Upload to PyPI

```bash
# Upload to REAL PyPI
python -m twine upload dist/*
```

You'll be prompted:
```
Enter your username: __token__
Enter your password: [paste your PyPI API token here]
```

### Step 4: Verify Upload

Visit: https://pypi.org/project/deeprepo/

You should see your project page!

### Step 5: Test Installation

```bash
# In a fresh environment
pip install deeprepo

# Test it works
python -c "from deeprepo import DeepRepoClient; print('Success!')"
```

---

## Post-Publication

### 1. Update Your README

Add installation badge to your main `README.md`:

```markdown
[![PyPI version](https://badge.fury.io/py/deeprepo.svg)](https://badge.fury.io/py/deeprepo)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

```bash
pip install deeprepo
```
```

### 2. Create a Git Tag

Tag your release in Git:

```bash
# From repository root
git tag -a v0.1.0 -m "Release version 0.1.0"
git push origin v0.1.0
```

### 3. Create GitHub Release

1. Go to your GitHub repository
2. Click "Releases" → "Create a new release"
3. Choose tag: `v0.1.0`
4. Release title: "DeepRepo v0.1.0"
5. Description: Summarize what's new
6. Attach the distribution files from `deeprepo_core/dist/`
7. Click "Publish release"

### 4. Announce Your Package

Share your package:
- Twitter/X
- Reddit (r/Python, r/MachineLearning)
- Hacker News
- LinkedIn
- Dev.to blog post

---

## Updating Your Package

When you need to release a new version:

### 1. Update Version Number

Edit `deeprepo_core/pyproject.toml`:

```toml
[project]
version = "0.1.1"  # Increment version
```

**Version Numbering (Semantic Versioning):**
- `0.1.0` → `0.1.1`: Bug fix (patch)
- `0.1.0` → `0.2.0`: New features (minor)
- `0.1.0` → `1.0.0`: Breaking changes (major)

### 2. Update CHANGELOG

Create `CHANGELOG.md` if you don't have one:

```markdown
# Changelog

## [0.1.1] - 2025-01-15

### Fixed
- Fixed bug in vector search
- Improved error messages

### Added
- New provider: Anthropic Claude

## [0.1.0] - 2025-01-01

- Initial release
```

### 3. Test on TestPyPI First

```bash
cd deeprepo_core

# Clean and rebuild
rm -rf build/ dist/ *.egg-info
python -m build

# Upload to TestPyPI first
python -m twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    deeprepo==0.1.1
```

### 4. Publish to PyPI

```bash
# If TestPyPI worked, publish to real PyPI
python -m twine upload dist/*
```

### 5. Tag the Release

```bash
git tag -a v0.1.1 -m "Release version 0.1.1"
git push origin v0.1.1
```

---

## Troubleshooting

### Problem: "File already exists"

**Error**: `HTTPError: 400 Bad Request - File already exists`

**Solution**: You cannot re-upload the same version. Increment version in `pyproject.toml`:
```toml
version = "0.1.1"  # or 0.2.0, etc.
```

### Problem: ImportError after installation

**Error**: `ImportError: cannot import name 'DeepRepoClient'`

**Check**:
1. Is `__init__.py` exporting correctly?
   ```python
   # src/deeprepo/__init__.py
   from deeprepo.client import DeepRepoClient
   
   __all__ = ["DeepRepoClient"]
   ```

2. Rebuild and reinstall:
   ```bash
   rm -rf build/ dist/ *.egg-info
   python -m build
   pip install dist/*.whl --force-reinstall
   ```

### Problem: Missing dependencies

**Error**: `ModuleNotFoundError: No module named 'numpy'`

**Solution**: Check `pyproject.toml` has all dependencies:
```toml
dependencies = [
    "numpy>=1.24.0",
    "requests>=2.28.0",
    "openai>=1.0.0",
    "google-generativeai>=0.3.0",
]
```

### Problem: README not showing on PyPI

**Check**:
1. File is named exactly `README.md`
2. It's in the same directory as `pyproject.toml`
3. `pyproject.toml` has: `readme = "README.md"`

### Problem: "Invalid classifier"

**Error**: Invalid classifier in pyproject.toml

**Solution**: Check valid classifiers at: https://pypi.org/classifiers/

---

## Security Best Practices

### 1. Use API Tokens (Not Passwords)

Always use API tokens instead of passwords for uploads.

### 2. Configure `.pypirc` (Optional)

For convenience, create `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_API_TOKEN_HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR_TESTPYPI_TOKEN_HERE
```

**Security**: Make sure this file is not in version control!
```bash
chmod 600 ~/.pypirc  # Restrict permissions
```

### 3. Never Commit Tokens to Git

Add to `.gitignore`:
```
.pypirc
*.pypirc
build/
dist/
*.egg-info/
```

---

## Quick Reference Commands

### Build Package
```bash
cd deeprepo_core
rm -rf build/ dist/ *.egg-info
python -m build
```

### Upload to TestPyPI
```bash
python -m twine upload --repository testpypi dist/*
```

### Upload to PyPI
```bash
python -m twine upload dist/*
```

### Test Installation
```bash
# From TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    deeprepo

# From PyPI
pip install deeprepo
```

### Check Package
```bash
python -m twine check dist/*
```

---

## Checklist: First-Time Publication

Use this checklist for your first publication:

- [ ] Created PyPI account
- [ ] Created TestPyPI account
- [ ] Generated API tokens for both
- [ ] Updated `pyproject.toml` with your email
- [ ] Updated GitHub URLs in `pyproject.toml`
- [ ] Copied LICENSE to `deeprepo_core/`
- [ ] Installed build tools: `pip install build twine`
- [ ] Cleaned old builds: `rm -rf build/ dist/ *.egg-info`
- [ ] Built package: `python -m build`
- [ ] Checked package: `python -m twine check dist/*`
- [ ] Uploaded to TestPyPI: `python -m twine upload --repository testpypi dist/*`
- [ ] Tested installation from TestPyPI
- [ ] Verified it works in Python
- [ ] Uploaded to PyPI: `python -m twine upload dist/*`
- [ ] Tested installation from PyPI
- [ ] Created git tag: `git tag -a v0.1.0 -m "Release v0.1.0"`
- [ ] Pushed tag: `git push origin v0.1.0`
- [ ] Created GitHub release
- [ ] Updated main README with PyPI badge
- [ ] Announced on social media

---

## Need Help?

- **PyPI Documentation**: https://packaging.python.org/
- **Twine Documentation**: https://twine.readthedocs.io/
- **Packaging Guides**: https://packaging.python.org/tutorials/packaging-projects/

---

**Congratulations on publishing your Python package! 🎉**
