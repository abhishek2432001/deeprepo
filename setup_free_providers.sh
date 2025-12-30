#!/bin/bash

# Quick Setup Script for FREE Providers
# Helps you set up free alternatives when hitting quota limits

echo "========================================================================"
echo "🚀 DeepRepo - FREE Provider Setup Guide"
echo "========================================================================"
echo ""
echo "Default providers (OpenAI & Gemini) included, but here are FREE alternatives:"
echo ""

# Check current status
echo "📊 Current Status:"
echo "========================================================================"

# Check Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama: READY"
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
    echo "Usage example:"
    echo "  export LLM_PROVIDER=huggingface"
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
    echo "     from deeprepo import DeepRepoClient"
    echo "     client = DeepRepoClient(provider_name='huggingface')"
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
    echo "Usage example:"
    echo "  export LLM_PROVIDER=ollama"
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
    echo "     export LLM_PROVIDER=ollama"
    echo "     from deeprepo import DeepRepoClient"
    echo "     client = DeepRepoClient(provider_name='ollama')"
fi
echo ""

echo "========================================================================"
echo "📋 Quick Usage Examples"
echo "========================================================================"
echo ""
echo "Using HuggingFace:"
echo "  export LLM_PROVIDER=huggingface"
echo "  export HUGGINGFACE_API_KEY=hf_your_token"
echo "  python test_full_rag_light.py  # Or use your own script"
echo ""
echo "Using Ollama:"
echo "  ollama serve  # Terminal 1 (if not already running)"
echo "  export LLM_PROVIDER=ollama"
echo "  python test_full_rag_light.py  # Or use your own script"
echo ""
echo "Using default providers (OpenAI/Gemini):"
echo "  export LLM_PROVIDER=openai  # or gemini"
echo "  export OPENAI_API_KEY=sk-your-key  # or GEMINI_API_KEY"
echo "  python test_full_rag_light.py"
echo ""

echo "========================================================================"
echo "💡 Recommendation"
echo "========================================================================"
echo ""
if [ "$OLLAMA_READY" = true ]; then
    echo "Use Ollama (already set up!)"
    echo "   export LLM_PROVIDER=ollama"
    echo "   python test_full_rag_light.py"
elif [ "$HF_READY" = true ]; then
    echo "Use HuggingFace (already set up!)"
    echo "   export LLM_PROVIDER=huggingface"
    echo "   python test_full_rag_light.py"
else
    echo "For fastest setup: Use HuggingFace (2 min)"
    echo "   Get token: https://huggingface.co/settings/tokens"
    echo ""
    echo "🏆 For best experience: Use Ollama (5 min)"
    echo "   Install: https://ollama.ai/download"
fi

echo ""
echo "========================================================================"
echo "📚 More Information"
echo "========================================================================"
echo "  • Full documentation: See README.md"
echo "  • Test examples: test_full_rag.py, test_full_rag_light.py"
echo "  • Provider comparison: See README.md Configuration section"
echo "========================================================================"

