#!/bin/bash

# Quick Setup Script for All Providers
# This script helps you quickly set up API keys for testing

echo "╔═══════════════════════════════════════════════════════════════════════╗"
echo "║                                                                         ║"
echo "║      DeepRepo Provider Setup - Quick Configuration                    ║"
echo "║                                                                         ║"
echo "╚═══════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a service is running
check_service() {
    curl -s "$1" >/dev/null 2>&1
}

echo "Checking your current provider setup..."
echo ""

# Check Ollama
echo "═══════════════════════════════════════════════════════════════════════"
echo "1. OLLAMA (FREE, Unlimited, Local)"
echo "═══════════════════════════════════════════════════════════════════════"

if command_exists ollama; then
    echo -e "${GREEN}[OK]${NC} Ollama is installed"
    
    if check_service "http://localhost:11434/api/tags"; then
        echo -e "${GREEN}[OK]${NC} Ollama service is running"
        
        # Check for models
        if ollama list | grep -q "nomic-embed-text"; then
            echo -e "${GREEN}[OK]${NC} Embedding model (nomic-embed-text) is installed"
        else
            echo -e "${YELLOW}WARNING:${NC} Embedding model not found"
            echo "  Run: ollama pull nomic-embed-text"
        fi
        
        if ollama list | grep -q "llama3.2"; then
            echo -e "${GREEN}[OK]${NC} LLM model (llama3.2) is installed"
        else
            echo -e "${YELLOW}WARNING:${NC} LLM model not found"
            echo "  Run: ollama pull llama3.2"
        fi
        
        echo -e "${GREEN}[OK] Ollama is ready to use!${NC}"
    else
        echo -e "${YELLOW}WARNING:${NC} Ollama is installed but not running"
        echo "  Run: ollama serve"
    fi
else
    echo -e "${RED}[FAIL]${NC} Ollama is not installed"
    echo "  Install with: brew install ollama"
    echo "  Or download from: https://ollama.ai/download"
fi

echo ""

# Check HuggingFace
echo "═══════════════════════════════════════════════════════════════════════"
echo "2. HUGGINGFACE (FREE, Cloud-based)"
echo "═══════════════════════════════════════════════════════════════════════"

if [ -n "$HUGGINGFACE_API_KEY" ] || [ -n "$HF_TOKEN" ]; then
    KEY="${HUGGINGFACE_API_KEY:-$HF_TOKEN}"
    echo -e "${GREEN}[OK]${NC} API key is set: ${KEY:0:10}..."
    echo -e "${GREEN}[OK] HuggingFace is ready to use!${NC}"
else
    echo -e "${RED}[FAIL]${NC} API key not found"
    echo "  Get your free key at: https://huggingface.co/settings/tokens"
    echo "  Then set: export HUGGINGFACE_API_KEY='hf_your_key'"
    echo ""
    read -p "  Would you like to set your HuggingFace API key now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "  Enter your HuggingFace API key: " hf_key
        export HUGGINGFACE_API_KEY="$hf_key"
        echo "  export HUGGINGFACE_API_KEY='$hf_key'" >> ~/.zshrc
        echo -e "${GREEN}[OK]${NC} API key saved to ~/.zshrc"
    fi
fi

echo ""

# Check OpenAI
echo "═══════════════════════════════════════════════════════════════════════"
echo "3. OPENAI (Paid, Most Reliable)"
echo "═══════════════════════════════════════════════════════════════════════"

if [ -n "$OPENAI_API_KEY" ]; then
    echo -e "${GREEN}[OK]${NC} API key is set: ${OPENAI_API_KEY:0:10}..."
    echo -e "${GREEN}[OK] OpenAI is ready to use!${NC}"
else
    echo -e "${RED}[FAIL]${NC} API key not found"
    echo "  Get your key at: https://platform.openai.com/api-keys"
    echo "  Then set: export OPENAI_API_KEY='sk-your_key'"
    echo ""
    read -p "  Would you like to set your OpenAI API key now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "  Enter your OpenAI API key: " openai_key
        export OPENAI_API_KEY="$openai_key"
        echo "  export OPENAI_API_KEY='$openai_key'" >> ~/.zshrc
        echo -e "${GREEN}[OK]${NC} API key saved to ~/.zshrc"
    fi
fi

echo ""

# Check Gemini
echo "═══════════════════════════════════════════════════════════════════════"
echo "4. GEMINI (Free tier, Limited)"
echo "═══════════════════════════════════════════════════════════════════════"

if [ -n "$GEMINI_API_KEY" ]; then
    echo -e "${GREEN}[OK]${NC} API key is set: ${GEMINI_API_KEY:0:10}..."
    echo -e "${GREEN}[OK] Gemini is ready to use!${NC}"
else
    echo -e "${RED}[FAIL]${NC} API key not found"
    echo "  Get your free key at: https://makersuite.google.com/app/apikey"
    echo "  Then set: export GEMINI_API_KEY='your_key'"
    echo ""
    read -p "  Would you like to set your Gemini API key now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "  Enter your Gemini API key: " gemini_key
        export GEMINI_API_KEY="$gemini_key"
        echo "  export GEMINI_API_KEY='$gemini_key'" >> ~/.zshrc
        echo -e "${GREEN}[OK]${NC} API key saved to ~/.zshrc"
    fi
fi

echo ""

# Check Anthropic
echo "═══════════════════════════════════════════════════════════════════════"
echo "5. ANTHROPIC (Paid, Excellent Reasoning)"
echo "═══════════════════════════════════════════════════════════════════════"

if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo -e "${GREEN}✓${NC} API key is set: ${ANTHROPIC_API_KEY:0:10}..."
    echo -e "${GREEN}✓ Anthropic is ready to use!${NC}"
    echo -e "${YELLOW}⚠${NC} Note: Anthropic doesn't have embeddings API"
    echo "  Use Anthropic for LLM with another provider for embeddings:"
    echo "  export EMBEDDING_PROVIDER=openai"
    echo "  export LLM_PROVIDER=anthropic"
else
    echo -e "${RED}✗${NC} API key not found"
    echo "  Get your key at: https://console.anthropic.com/"
    echo "  Then set: export ANTHROPIC_API_KEY='sk-ant-your_key'"
    echo ""
    read -p "  Would you like to set your Anthropic API key now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "  Enter your Anthropic API key: " anthropic_key
        export ANTHROPIC_API_KEY="$anthropic_key"
        echo "  export ANTHROPIC_API_KEY='$anthropic_key'" >> ~/.zshrc
        echo -e "${GREEN}✓${NC} API key saved to ~/.zshrc"
        echo -e "${YELLOW}⚠${NC} Remember: Use another provider for embeddings!"
    fi
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "SETUP SUMMARY"
echo "═══════════════════════════════════════════════════════════════════════"

READY_COUNT=0

# Count ready providers
if command_exists ollama && check_service "http://localhost:11434/api/tags"; then
    echo -e "${GREEN}[OK]${NC} Ollama: Ready"
    ((READY_COUNT++))
else
    echo -e "${RED}[FAIL]${NC} Ollama: Not ready"
fi

if [ -n "$HUGGINGFACE_API_KEY" ] || [ -n "$HF_TOKEN" ]; then
    echo -e "${GREEN}[OK]${NC} HuggingFace: Ready"
    ((READY_COUNT++))
else
    echo -e "${RED}[FAIL]${NC} HuggingFace: Not ready"
fi

if [ -n "$OPENAI_API_KEY" ]; then
    echo -e "${GREEN}[OK]${NC} OpenAI: Ready"
    ((READY_COUNT++))
else
    echo -e "${RED}[FAIL]${NC} OpenAI: Not ready"
fi

if [ -n "$GEMINI_API_KEY" ]; then
    echo -e "${GREEN}[OK]${NC} Gemini: Ready"
    ((READY_COUNT++))
else
    echo -e "${RED}[FAIL]${NC} Gemini: Not ready"
fi

if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo -e "${GREEN}✓${NC} Anthropic: Ready (LLM only, use another for embeddings)"
    ((READY_COUNT++))
else
    echo -e "${RED}✗${NC} Anthropic: Not ready"
fi

echo ""
echo "Ready providers: $READY_COUNT/5"
echo ""

if [ $READY_COUNT -gt 0 ]; then
    echo -e "${GREEN}You can now test your providers!${NC}"
    echo ""
    echo "Run the test script:"
    echo "  python tests/integration/test_all_providers.py"
    echo ""
    echo "Or test specific providers:"
    if command_exists ollama && check_service "http://localhost:11434/api/tags"; then
        echo "  python tests/integration/test_all_providers.py ollama"
    fi
    if [ -n "$HUGGINGFACE_API_KEY" ] || [ -n "$HF_TOKEN" ]; then
        echo "  python tests/integration/test_all_providers.py huggingface"
    fi
    if [ -n "$OPENAI_API_KEY" ]; then
        echo "  python tests/integration/test_all_providers.py openai"
    fi
    if [ -n "$GEMINI_API_KEY" ]; then
        echo "  python tests/integration/test_all_providers.py gemini"
    fi
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        echo "  python tests/integration/test_all_providers.py anthropic"
    fi
    echo ""
    echo "═══════════════════════════════════════════════════════════════════════"
    echo "🆕 NEW FEATURE: Separate Embedding and LLM Providers"
    echo "═══════════════════════════════════════════════════════════════════════"
    echo ""
    echo "You can now use different providers for embeddings and LLM!"
    echo ""
    echo "Examples:"
    echo ""
    echo "1. Anthropic LLM + OpenAI Embeddings (Recommended for Anthropic):"
    echo "   export EMBEDDING_PROVIDER=openai"
    echo "   export LLM_PROVIDER=anthropic"
    echo "   python -c \"from deeprepo import DeepRepoClient; client = DeepRepoClient()\""
    echo ""
    echo "2. Cost optimization (Free embeddings + Paid LLM):"
    echo "   export EMBEDDING_PROVIDER=huggingface"
    echo "   export LLM_PROVIDER=openai"
    echo "   python -c \"from deeprepo import DeepRepoClient; client = DeepRepoClient()\""
    echo ""
    echo "3. Same provider for both (backward compatible):"
    echo "   export LLM_PROVIDER=ollama"
    echo "   python -c \"from deeprepo import DeepRepoClient; client = DeepRepoClient()\""
    echo ""
    echo "Or in Python code:"
    echo "   from deeprepo import DeepRepoClient"
    echo "   client = DeepRepoClient("
    echo "       embedding_provider_name='openai',"
    echo "       llm_provider_name='anthropic'"
    echo "   )"
else
    echo -e "${YELLOW}WARNING: No providers are ready yet${NC}"
    echo ""
    echo "See INSTALLATION.md for detailed setup instructions"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
