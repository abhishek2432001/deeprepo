#!/bin/bash

# Quick Setup Script for FREE Providers
# Helps you set up free alternatives when hitting quota limits

echo "========================================================================"
echo "DeepRepo - FREE Provider Setup Guide"
echo "========================================================================"
echo ""
echo "Default providers (OpenAI & Gemini) included, but here are FREE alternatives:"
echo ""

# Check current status
echo "Current Status:"
echo "========================================================================"

# Check Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama: READY"
    OLLAMA_READY=true
else
    echo "Ollama: NOT INSTALLED"
    OLLAMA_READY=false
fi

# Check HuggingFace
if [ -n "$HUGGINGFACE_API_KEY" ]; then
    echo "HuggingFace: API KEY SET"
    HF_READY=true
else
    echo "HuggingFace: API KEY NOT SET"
    HF_READY=false
fi

# Check default providers
if [ -n "$OPENAI_API_KEY" ]; then
    echo "OpenAI: API KEY SET (default provider)"
else
    echo "OpenAI: API KEY NOT SET"
fi

if [ -n "$GEMINI_API_KEY" ]; then
    echo "Gemini: API KEY SET (default provider)"
else
    echo "Gemini: API KEY NOT SET"
fi

echo ""
echo "========================================================================"
echo "Setup Options for FREE Providers"
echo "========================================================================"
echo ""

# Option 1: HuggingFace
echo "OPTION 1: HuggingFace (Fastest - 2 minutes)"
echo "----------------------------------------"
echo "Pros: Fast setup, generous limits (1000s requests/day)"
echo "Cons: Requires internet, models can be slow to wake up"
echo ""
if [ "$HF_READY" = true ]; then
    echo "Status: READY TO USE"
    echo ""
    echo "Usage examples:"
    echo "  # Same provider for both embeddings and LLM:"
    echo "  export LLM_PROVIDER=huggingface"
    echo "  python -c \"from deeprepo import DeepRepoClient; client = DeepRepoClient(); print('Ready!')\""
    echo ""
    echo "  # Or use HuggingFace for embeddings with another LLM:"
    echo "  export EMBEDDING_PROVIDER=huggingface"
    echo "  export LLM_PROVIDER=openai  # or anthropic, etc."
    echo "  python -c \"from deeprepo import DeepRepoClient; client = DeepRepoClient(); print('Ready!')\""
else
    echo "Setup steps:"
    echo "  1. Install provider: pip install -e '.[huggingface]'"
    echo "  2. Visit: https://huggingface.co/settings/tokens"
    echo "  3. Click 'New token' → Create"
    echo "  4. Copy token and run:"
    echo "     export HUGGINGFACE_API_KEY=hf_your_token_here"
    echo "     export LLM_PROVIDER=huggingface"
    echo ""
    echo "  5. Use in Python:"
    echo "     # Same provider for both:"
    echo "     from deeprepo import DeepRepoClient"
    echo "     client = DeepRepoClient(provider_name='huggingface')"
    echo ""
    echo "     # Or separate providers:"
    echo "     client = DeepRepoClient("
    echo "         embedding_provider_name='huggingface',"
    echo "         llm_provider_name='openai'"
    echo "     )"
fi
echo ""

# Option 2: Ollama
echo "OPTION 2: Ollama (Best - 5 minutes)"
echo "----------------------------------------"
echo "Pros: Unlimited usage, works offline, fastest, 100% private"
echo "Cons: Initial download (~4GB), requires some disk space"
echo ""
if [ "$OLLAMA_READY" = true ]; then
    echo "Status: READY TO USE"
    echo ""
    echo "Usage examples:"
    echo "  # Same provider for both embeddings and LLM:"
    echo "  export LLM_PROVIDER=ollama"
    echo "  python -c \"from deeprepo import DeepRepoClient; client = DeepRepoClient(); print('Ready!')\""
    echo ""
    echo "  # Or use Ollama for embeddings with another LLM:"
    echo "  export EMBEDDING_PROVIDER=ollama"
    echo "  export LLM_PROVIDER=openai  # or anthropic, etc."
    echo "  python -c \"from deeprepo import DeepRepoClient; client = DeepRepoClient(); print('Ready!')\""
else
    echo "Setup steps:"
    echo "  1. Install Ollama:"
    echo "     macOS: brew install ollama"
    echo "     Linux: curl -fsSL https://ollama.ai/install.sh | sh"
    echo "     Or download: https://ollama.ai/download"
    echo ""
    echo "  2. Start Ollama (Terminal 1):"
    echo "     ollama serve"
    echo ""
    echo "  3. Pull models (Terminal 2):"
    echo "     ollama pull nomic-embed-text  # For embeddings"
    echo "     ollama pull llama3.2           # For LLM"
    echo ""
    echo "  4. Use in Python:"
    echo "     # Same provider for both:"
    echo "     export LLM_PROVIDER=ollama"
    echo "     from deeprepo import DeepRepoClient"
    echo "     client = DeepRepoClient(provider_name='ollama')"
    echo ""
    echo "     # Or separate providers:"
    echo "     client = DeepRepoClient("
    echo "         embedding_provider_name='ollama',"
    echo "         llm_provider_name='openai'"
    echo "     )"
fi
echo ""

echo "========================================================================"
echo "Quick Usage Examples"
echo "========================================================================"
echo ""
echo "Using HuggingFace (same provider for both):"
echo "  export LLM_PROVIDER=huggingface"
echo "  export HUGGINGFACE_API_KEY=hf_your_token"
echo "  python tests/integration/test_all_providers.py huggingface"
echo ""
echo "Using Ollama (same provider for both):"
echo "  ollama serve  # Terminal 1 (if not already running)"
echo "  export LLM_PROVIDER=ollama"
echo "  python tests/integration/test_all_providers.py ollama"
echo ""
echo "Using separate providers (NEW FEATURE!):"
echo "  # Free embeddings + Paid LLM (cost optimization):"
echo "  export EMBEDDING_PROVIDER=huggingface"
echo "  export LLM_PROVIDER=openai"
echo "  export HUGGINGFACE_API_KEY=hf_your_token"
echo "  export OPENAI_API_KEY=sk-your-key"
echo "  python tests/integration/test_all_providers.py openai"
echo ""
echo "  # Anthropic LLM + OpenAI embeddings (recommended):"
echo "  export EMBEDDING_PROVIDER=openai"
echo "  export LLM_PROVIDER=anthropic"
echo "  export OPENAI_API_KEY=sk-your-key"
echo "  export ANTHROPIC_API_KEY=sk-ant-your-key"
echo "  python tests/integration/test_all_providers.py anthropic"
echo ""
echo "Using default providers (OpenAI/Gemini):"
echo "  export LLM_PROVIDER=openai  # or gemini"
echo "  export OPENAI_API_KEY=sk-your-key  # or GEMINI_API_KEY"
echo "  python tests/integration/test_all_providers.py openai  # or gemini"
echo ""

echo "========================================================================"
echo "Recommendation"
echo "========================================================================"
echo ""
if [ "$OLLAMA_READY" = true ]; then
    echo "Use Ollama (already set up!)"
    echo "   export LLM_PROVIDER=ollama"
    echo "   python tests/integration/test_all_providers.py ollama"
    echo ""
    echo "Or mix with paid providers for better LLM:"
    echo "   export EMBEDDING_PROVIDER=ollama"
    echo "   export LLM_PROVIDER=openai  # or anthropic"
    echo "   python tests/integration/test_all_providers.py openai"
elif [ "$HF_READY" = true ]; then
    echo "Use HuggingFace (already set up!)"
    echo "   export LLM_PROVIDER=huggingface"
    echo "   python tests/integration/test_all_providers.py huggingface"
    echo ""
    echo "Or use for free embeddings with paid LLM:"
    echo "   export EMBEDDING_PROVIDER=huggingface"
    echo "   export LLM_PROVIDER=openai  # or anthropic"
    echo "   python tests/integration/test_all_providers.py openai"
else
    echo "For fastest setup: Use HuggingFace (2 min)"
    echo "   Get token: https://huggingface.co/settings/tokens"
    echo ""
    echo "For best experience: Use Ollama (5 min)"
    echo "   Install: https://ollama.ai/download"
    echo ""
    echo "💡 Pro tip: Use free providers for embeddings, paid for LLM!"
fi

echo ""
echo "========================================================================"
echo "🆕 NEW FEATURE: Separate Embedding and LLM Providers"
echo "========================================================================"
echo ""
echo "You can now use different providers for embeddings and LLM!"
echo ""
echo "Benefits:"
echo "  • Use Anthropic for LLM (excellent reasoning) + OpenAI for embeddings"
echo "  • Cost optimization: Free embeddings + Paid LLM"
echo "  • Performance: Fast embeddings + Powerful LLM"
echo ""
echo "Example in Python:"
echo "  from deeprepo import DeepRepoClient"
echo ""
echo "  # Same provider (backward compatible):"
echo "  client = DeepRepoClient(provider_name='ollama')"
echo ""
echo "  # Different providers:"
echo "  client = DeepRepoClient("
echo "      embedding_provider_name='huggingface',  # Free"
echo "      llm_provider_name='openai'              # Paid"
echo "  )"
echo ""
echo "========================================================================"
echo "📚 More Information"
echo "========================================================================"
echo "  • Full documentation: See README.md"
echo "  • Installation guide: See INSTALLATION.md"
echo "  • Test examples: python tests/integration/test_all_providers.py [provider]"
echo "  • Provider comparison: See README.md Configuration section"
echo "========================================================================"

