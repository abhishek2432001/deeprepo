# Installation Guide

Complete installation and setup instructions for DeepRepo with all supported AI providers.

## Table of Contents

- [System Requirements](#system-requirements)
- [Core Installation](#core-installation)
- [Provider Setup](#provider-setup)
  - [Ollama (Recommended)](#ollama-recommended---free--unlimited)
  - [HuggingFace](#huggingface---free-cloud-based)
  - [OpenAI](#openai---paid-production-ready)
  - [Anthropic](#anthropic---paid-production-ready)
  - [Gemini](#gemini---free-tier-limited)
- [Docker Installation](#docker-installation)
- [Verification](#verification)

## System Requirements

- **Python**: 3.10 or higher
- **OS**: macOS, Linux, or Windows
- **RAM**: 2GB minimum (8GB recommended for Ollama)
- **Disk Space**: 
  - Core library: ~100MB
  - Ollama (optional): ~4GB for models

## Core Installation

### 1. Clone or Download the Project

```bash
cd /path/to/deeprepo
```

### 2. Install the Library

```bash
cd deeprepo_core
pip install -e .
```

This installs the core library with minimal dependencies. Providers are loaded dynamically based on available packages and API keys.

### 3. Verify Installation

```bash
python -c "from deeprepo import DeepRepoClient; print('DeepRepo installed successfully')"
```

## Provider Setup

You can use **any combination** of providers. Set up only the ones you need.

---

## Ollama (Recommended) - FREE & Unlimited

**Best for**: Local development, privacy, offline work, unlimited usage

### Step 1: Install Ollama

**macOS:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from https://ollama.com/download

### Step 2: Start Ollama Service

```bash
ollama serve
```

Leave this running in a terminal. You can also set it to start automatically at boot.

### Step 3: Pull Required Models

```bash
# Embedding model (required)
ollama pull nomic-embed-text

# LLM model (choose one or both)
ollama pull llama3.2        # Recommended - 2GB
ollama pull llama3.1        # Alternative - 4.7GB
```

### Step 4: Verify Ollama

```bash
# Check service is running
curl http://localhost:11434/api/tags

# List installed models
ollama list
```

### Step 5: Use in Python

```python
from deeprepo import DeepRepoClient

# No API keys needed!
client = DeepRepoClient(provider_name="ollama")
```

**Ollama is now ready!**

---

## HuggingFace - FREE Cloud-Based

**Best for**: Cloud-based usage, no local installation, open-source models

### Step 1: Get API Key

1. Visit https://huggingface.co/settings/tokens
2. Click **"New token"**
3. Give it a name (e.g., "DeepRepo")
4. Select **"Read"** permission
5. Copy the token (starts with `hf_`)

### Step 2: Set Environment Variable

**Temporary (current session):**
```bash
export HUGGINGFACE_API_KEY="hf_your_token_here"
# Or use HF_TOKEN
export HF_TOKEN="hf_your_token_here"
```

**Permanent:**
```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export HUGGINGFACE_API_KEY="hf_your_token_here"' >> ~/.zshrc
source ~/.zshrc
```

### Step 3: Use in Python

```python
import os
os.environ["HUGGINGFACE_API_KEY"] = "hf_your_token"

from deeprepo import DeepRepoClient
client = DeepRepoClient(provider_name="huggingface")
```

**HuggingFace is now ready!**

**Rate Limits:**
- Free tier: 300 requests/hour (registered users)
- No credit card required

---

## OpenAI - Paid, Production Ready

**Best for**: Production applications, best quality, most reliable

### Step 1: Get API Key

1. Visit https://platform.openai.com/api-keys
2. Sign up or log in
3. Add a payment method (required)
4. Click **"Create new secret key"**
5. Copy the key (starts with `sk-`)

### Step 2: Set Environment Variable

```bash
# Temporary
export OPENAI_API_KEY="sk-your_key_here"

# Permanent
echo 'export OPENAI_API_KEY="sk-your_key_here"' >> ~/.zshrc
source ~/.zshrc
```

### Step 3: Use in Python

```python
import os
os.environ["OPENAI_API_KEY"] = "sk-your_key"

from deeprepo import DeepRepoClient
client = DeepRepoClient(provider_name="openai")
```

**OpenAI is now ready!**

**Pricing (approximate):**
- Embeddings: $0.00002 per 1K tokens (~$0.01 per 100 documents)
- GPT-3.5-Turbo: $0.0005 per 1K tokens
- GPT-4: $0.03 per 1K tokens

**Typical RAG costs:**
- Ingest 100 documents: ~$0.10
- 1000 queries: ~$0.50 (using GPT-3.5)

---

## Anthropic - Paid, Production Ready

**Best for**: Production applications, excellent reasoning, long context windows

### Step 1: Get API Key

1. Visit https://console.anthropic.com/
2. Sign up or log in
3. Add a payment method (required)
4. Navigate to **API Keys** section
5. Click **"Create Key"**
6. Copy the key (starts with `sk-ant-`)

### Step 2: Set Environment Variable

```bash
# Temporary
export ANTHROPIC_API_KEY="sk-ant-your_key_here"

# Permanent
echo 'export ANTHROPIC_API_KEY="sk-ant-your_key_here"' >> ~/.zshrc
source ~/.zshrc
```

### Step 3: Use in Python

```python
import os
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-your_key"

from deeprepo import DeepRepoClient
client = DeepRepoClient(provider_name="anthropic")
```

**Anthropic is now ready!**

** Important Note:**
- Anthropic does NOT provide a dedicated embeddings API
- **You must use a different provider for embeddings** when using Anthropic for LLM
- Recommended: Use OpenAI or HuggingFace for embeddings, Anthropic for LLM

**Example with separate providers:**
```python
from deeprepo import DeepRepoClient

# Use OpenAI for embeddings, Anthropic for LLM
client = DeepRepoClient(
    embedding_provider_name="openai",
    llm_provider_name="anthropic"
)
```

**Pricing (approximate):**
- Claude 3.5 Sonnet: $0.003 per 1K input tokens, $0.015 per 1K output tokens
- Claude 3 Opus: $0.015 per 1K input tokens, $0.075 per 1K output tokens
- Claude 3 Haiku: $0.00025 per 1K input tokens, $0.00125 per 1K output tokens

**Typical RAG costs:**
- 1000 queries: ~$1.50-$3.00 (using Claude 3.5 Sonnet)

---

## Gemini - Free Tier (Limited)

**Best for**: Testing, small projects (not recommended for production)

### Step 1: Get API Key

1. Visit https://makersuite.google.com/app/apikey
2. Sign in with Google account
3. Click **"Create API Key"**
4. Copy the key

### Step 2: Set Environment Variable

```bash
# Temporary
export GEMINI_API_KEY="your_key_here"

# Permanent
echo 'export GEMINI_API_KEY="your_key_here"' >> ~/.zshrc
source ~/.zshrc
```

### Step 3: Use in Python

```python
import os
os.environ["GEMINI_API_KEY"] = "your_key"

from deeprepo import DeepRepoClient
client = DeepRepoClient(provider_name="gemini")
```

**Gemini is now ready!**

**Important Limitations:**
- Free tier: **15 requests per minute** (very limited!)
- Easy to hit quota errors
- Not suitable for production use
- Consider using Ollama or HuggingFace instead

---

## Docker Installation

### Prerequisites

- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Docker Compose installed

### Quick Start

```bash
# Build and start
docker-compose up --build

# Run in background
docker-compose up -d
```

### Configuration

Edit `docker-compose.yml` to set your provider:

```yaml
environment:
  - LLM_PROVIDER=ollama  # or huggingface, openai, anthropic, gemini
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
  - HUGGINGFACE_API_KEY=${HUGGINGFACE_API_KEY}
```

### Accessing the API

The API will be available at `http://localhost:8000`

---

## Verification

### Check Provider Setup

Run the setup checker:

```bash
./setup_providers.sh
```

This will show which providers are ready to use.

### Run Tests

Test a specific provider:

```bash
# Test Ollama
python test_all_providers.py ollama

# Test HuggingFace
python test_all_providers.py huggingface

# Test OpenAI
python test_all_providers.py openai

# Test Anthropic
python test_all_providers.py anthropic

# Test all configured providers
python test_all_providers.py
```

### Expected Output

```
Provider        Status     Chunks     Ingest Time     Query Time     
------------------------------------------------------------------------
ollama          PASS      8          0.74s           3.91s          

ALL TESTS PASSED (1/1)
```

---

## Quick Reference

### Switching Providers

```python
# Same provider for both embeddings and LLM (backward compatible)
client = DeepRepoClient(provider_name="ollama")  # or any provider: huggingface, openai, anthropic, gemini

# Different providers for embeddings and LLM
client = DeepRepoClient(
    embedding_provider_name="openai",    # Provider for embeddings
    llm_provider_name="anthropic"        # Provider for LLM
)

# Via environment variables
import os
os.environ["LLM_PROVIDER"] = "ollama"
client = DeepRepoClient()  # Uses LLM_PROVIDER env var for both

# Separate providers via environment variables
os.environ["EMBEDDING_PROVIDER"] = "openai"
os.environ["LLM_PROVIDER"] = "anthropic"
client = DeepRepoClient()  # Uses separate providers
```

### Using Different Providers for Embeddings and LLM

DeepRepo supports using different providers for embeddings and LLM. This is especially useful when:

1. **Using Anthropic**: Anthropic doesn't have an embeddings API, so you must use another provider for embeddings
2. **Cost optimization**: Use free providers for embeddings, paid providers for LLM
3. **Performance**: Mix fast embedding providers with powerful LLM providers

**Examples:**

```python
# Anthropic LLM with OpenAI embeddings (recommended for Anthropic)
client = DeepRepoClient(
    embedding_provider_name="openai",
    llm_provider_name="anthropic"
)

# Cost optimization: Free embeddings, paid LLM
client = DeepRepoClient(
    embedding_provider_name="huggingface",  # Free
    llm_provider_name="openai"             # Paid
)

# Performance: Fast embeddings, powerful LLM
client = DeepRepoClient(
    embedding_provider_name="openai",       # Fast embeddings
    llm_provider_name="anthropic"          # Powerful LLM
)
```

**Environment Variables:**

```bash
# Set separate providers
export EMBEDDING_PROVIDER=openai
export LLM_PROVIDER=anthropic

# Or use single provider (backward compatible)
export LLM_PROVIDER=ollama
```

### Provider Selection Guide

**Choose Ollama if you want:**
- FREE and unlimited usage
- Complete privacy (local only)
- Offline capability
- Fastest performance (no network)

**Choose HuggingFace if you want:**
- FREE cloud-based solution
- No local installation
- Access from anywhere
- Can accept rate limits

**Choose OpenAI if you want:**
- Best quality responses
- Production reliability
- Excellent documentation
- Can pay for usage

**Choose Anthropic if you want:**
- Excellent reasoning capabilities
- Long context windows
- Production reliability
- Can pay for usage
- **Important**: Must use another provider (OpenAI, HuggingFace) for embeddings
- **Example**: `DeepRepoClient(embedding_provider_name="openai", llm_provider_name="anthropic")`

**Choose Gemini if you:**
- Only need very light testing
- Understand the strict limitations
- Use **Ollama or HuggingFace instead** for real work

---

## Troubleshooting

### Ollama Issues

**"Connection refused":**
```bash
# Start the Ollama service
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags
```

**"Model not found":**
```bash
# Pull the models
ollama pull nomic-embed-text
ollama pull llama3.2

# List installed models
ollama list
```

### HuggingFace Issues

**"Invalid API key":**
```bash
# Verify key is set and starts with "hf_"
echo $HUGGINGFACE_API_KEY

# Re-export if needed
export HUGGINGFACE_API_KEY="hf_your_token"
```

**"Rate limit exceeded":**
- Wait 1 hour for limit to reset
- Free tier: 300 requests/hour
- Consider using Ollama for unlimited usage

### OpenAI Issues

**"Incorrect API key":**
```bash
# Verify key starts with "sk-"
echo $OPENAI_API_KEY
```

**"Insufficient quota":**
- Add credits at https://platform.openai.com/billing
- Check usage at https://platform.openai.com/usage

### Anthropic Issues

**"Invalid API key":**
```bash
# Verify key starts with "sk-ant-"
echo $ANTHROPIC_API_KEY
```

**"Insufficient quota":**
- Add credits at https://console.anthropic.com/settings/billing
- Check usage at https://console.anthropic.com/settings/usage

**"Embeddings not supported":**
- Anthropic does NOT provide a dedicated embeddings API
- **You must use a different provider for embeddings** when using Anthropic
- Example: `DeepRepoClient(embedding_provider_name="openai", llm_provider_name="anthropic")`
- Or use a different provider entirely for both LLM and embeddings

### Gemini Issues

**"Quota exceeded":**
- Gemini free tier is very limited (15/minute)
- Wait a few minutes and try again
- **Recommended**: Use Ollama or HuggingFace instead

---

## Next Steps

After installation:

1. **Test your setup**: Run `python test_all_providers.py [provider]`
2. **Try the examples**: See usage examples in README.md
3. **Start building**: Use `DeepRepoClient` in your projects!

For more information, see [README.md](README.md).
