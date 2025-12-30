# 🚀 Quick Start: Publishing DeepRepo to PyPI

This is a quick reference for publishing your package. See [PUBLISHING_GUIDE.md](PUBLISHING_GUIDE.md) for the full detailed guide.

## ⚡ Super Quick Start (5 minutes)

### 1. **Update Configuration** (Do this FIRST!)

Edit `deeprepo_core/pyproject.toml`:

```toml
authors = [
    {name = "Your Name", email = "your.email@example.com"}  # ← UPDATE THIS
]

[project.urls]
Homepage = "https://github.com/YOUR_USERNAME/deeprepo"  # ← UPDATE THIS
Repository = "https://github.com/YOUR_USERNAME/deeprepo"  # ← UPDATE THIS
```

### 2. **Create Accounts**

- **TestPyPI**: https://test.pypi.org/account/register/ (for testing)
- **PyPI**: https://pypi.org/account/register/ (production)

### 3. **Get API Tokens**

- **TestPyPI**: https://test.pypi.org → Account Settings → API tokens
- **PyPI**: https://pypi.org → Account Settings → API tokens

Save these tokens securely!

### 4. **Test Publication** (Recommended!)

```bash
# Make script executable (first time only)
chmod +x publish.sh

# Test on TestPyPI first
./publish.sh test
```

When prompted:
- Username: `__token__`
- Password: `pypi-AgEIc...` (your TestPyPI token)

### 5. **Verify Test Installation**

```bash
# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    deeprepo

# Test it works
python -c "from deeprepo import DeepRepoClient; print('Success!')"
```

### 6. **Publish to PyPI** (Production!)

```bash
# If test worked, publish for real
./publish.sh prod
```

When prompted:
- Username: `__token__`
- Password: `pypi-AgEIc...` (your PyPI token)

### 7. **Done!** 🎉

Your package is now live! Anyone can install it:

```bash
pip install deeprepo
```

View it at: https://pypi.org/project/deeprepo/

---

## 📋 Manual Method (Without Script)

If you prefer to run commands manually:

### Build

```bash
cd deeprepo_core

# Install tools
pip install build twine

# Clean and build
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

---

## 🔄 Updating Your Package

When releasing a new version:

### 1. Update Version

Edit `deeprepo_core/pyproject.toml`:

```toml
version = "0.1.1"  # Increment version
```

### 2. Build and Publish

```bash
# Test first
./publish.sh test

# Then production
./publish.sh prod
```

### 3. Tag Release

```bash
git tag -a v0.1.1 -m "Release v0.1.1"
git push origin v0.1.1
```

---

## 🆘 Common Issues

### "File already exists"

You cannot re-upload the same version. Increment version in `pyproject.toml`.

### "Username or password incorrect"

- Username should be: `__token__` (literally, with underscores)
- Password should be your API token starting with `pypi-`

### Package not importing after install

Make sure `src/deeprepo/__init__.py` exports correctly:

```python
from deeprepo.client import DeepRepoClient

__all__ = ["DeepRepoClient"]
```

---

## 📚 Full Documentation

See [PUBLISHING_GUIDE.md](PUBLISHING_GUIDE.md) for:
- Detailed step-by-step instructions
- Troubleshooting guide
- Security best practices
- Post-publication checklist
- And more!

---

## ✅ Pre-Publication Checklist

Before publishing, make sure:

- [ ] Updated author email in `pyproject.toml`
- [ ] Updated GitHub URLs in `pyproject.toml`
- [ ] All tests pass: `pytest tests/`
- [ ] README.md looks good
- [ ] LICENSE is in `deeprepo_core/` directory
- [ ] Created PyPI and TestPyPI accounts
- [ ] Generated API tokens for both
- [ ] Tested on TestPyPI first
- [ ] Verified installation works

---

## 🎯 Quick Commands Reference

```bash
# Test on TestPyPI
./publish.sh test

# Publish to PyPI
./publish.sh prod

# Manual build
cd deeprepo_core && python -m build

# Manual upload (TestPyPI)
python -m twine upload --repository testpypi dist/*

# Manual upload (PyPI)
python -m twine upload dist/*

# Check package
python -m twine check dist/*
```

---

**Need help?** Read the full [PUBLISHING_GUIDE.md](PUBLISHING_GUIDE.md)

**Ready to publish?** Run: `./publish.sh test` 🚀
