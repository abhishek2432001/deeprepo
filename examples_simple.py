#!/usr/bin/env python3
"""
Simple Example - Using DeepRepo with Different Providers

This script shows the simplest possible usage of each provider.
Choose the provider that works best for you!
"""

import os
from pathlib import Path

# ============================================================================
# EXAMPLE 1: Ollama (FREE, Unlimited, Local)
# ============================================================================
def example_ollama():
    """
    Using Ollama - 100% Free, Unlimited Usage
    
    Prerequisites:
    1. Install Ollama: brew install ollama
    2. Start service: ollama serve
    3. Pull models: ollama pull nomic-embed-text && ollama pull llama3.2
    """
    print("\n" + "="*80)
    print("Example 1: Using Ollama (FREE, Unlimited)")
    print("="*80 + "\n")
    
    from deeprepo import DeepRepoClient
    
    # Create client - NO API KEYS NEEDED!
    client = DeepRepoClient(
        provider_name="ollama",
        storage_path="ollama_vectors.json"
    )
    
    # Create a simple test document
    test_dir = Path("example_docs")
    test_dir.mkdir(exist_ok=True)
    
    doc = test_dir / "intro.txt"
    doc.write_text("""
    DeepRepo is a local RAG (Retrieval-Augmented Generation) engine.
    It allows you to build AI-powered search over your documents.
    You can use different providers: Ollama, HuggingFace, OpenAI, or Gemini.
    Ollama is completely free and runs on your computer.
    """)
    
    # Ingest documents
    print("📥 Ingesting documents...")
    result = client.ingest(str(test_dir))
    print(f"✓ Processed {result['chunks_processed']} chunks from {result['files_scanned']} files")
    
    # Query the knowledge base
    print("\n🔍 Querying: 'What is DeepRepo?'")
    response = client.query("What is DeepRepo?")
    print(f"\n💡 Answer:\n{response['answer']}\n")
    
    # Cleanup
    doc.unlink()
    test_dir.rmdir()
    Path("ollama_vectors.json").unlink(missing_ok=True)
    
    print("✓ Ollama example complete!\n")


# ============================================================================
# EXAMPLE 2: HuggingFace (FREE, Cloud-based)
# ============================================================================
def example_huggingface():
    """
    Using HuggingFace - Free tier with generous limits
    
    Prerequisites:
    1. Get API key from: https://huggingface.co/settings/tokens
    2. Set environment variable: export HUGGINGFACE_API_KEY='hf_your_key'
    """
    print("\n" + "="*80)
    print("Example 2: Using HuggingFace (FREE Cloud-based)")
    print("="*80 + "\n")
    
    # Check for API key
    if not os.environ.get("HUGGINGFACE_API_KEY") and not os.environ.get("HF_TOKEN"):
        print("⚠️  HUGGINGFACE_API_KEY not set. Skipping this example.")
        print("   Get your free key at: https://huggingface.co/settings/tokens")
        print("   Then run: export HUGGINGFACE_API_KEY='hf_your_key'\n")
        return
    
    from deeprepo import DeepRepoClient
    
    # Create client
    client = DeepRepoClient(
        provider_name="huggingface",
        storage_path="hf_vectors.json"
    )
    
    # Create test document
    test_dir = Path("example_docs")
    test_dir.mkdir(exist_ok=True)
    
    doc = test_dir / "intro.txt"
    doc.write_text("""
    HuggingFace hosts thousands of open-source AI models.
    You can use their inference API for free with rate limits.
    It's perfect for cloud-based applications that need AI.
    """)
    
    # Ingest and query
    print("📥 Ingesting documents...")
    result = client.ingest(str(test_dir))
    print(f"✓ Processed {result['chunks_processed']} chunks")
    
    print("\n🔍 Querying: 'What is HuggingFace good for?'")
    response = client.query("What is HuggingFace good for?")
    print(f"\n💡 Answer:\n{response['answer']}\n")
    
    # Cleanup
    doc.unlink()
    test_dir.rmdir()
    Path("hf_vectors.json").unlink(missing_ok=True)
    
    print("✓ HuggingFace example complete!\n")


# ============================================================================
# EXAMPLE 3: OpenAI (Paid, Most Reliable)
# ============================================================================
def example_openai():
    """
    Using OpenAI - Paid service with best quality
    
    Prerequisites:
    1. Get API key from: https://platform.openai.com/api-keys
    2. Set environment variable: export OPENAI_API_KEY='sk-your_key'
    """
    print("\n" + "="*80)
    print("Example 3: Using OpenAI (Paid, Production-Ready)")
    print("="*80 + "\n")
    
    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not set. Skipping this example.")
        print("   Get your key at: https://platform.openai.com/api-keys")
        print("   Then run: export OPENAI_API_KEY='sk-your_key'\n")
        return
    
    from deeprepo import DeepRepoClient
    
    # Create client
    client = DeepRepoClient(
        provider_name="openai",
        storage_path="openai_vectors.json"
    )
    
    # Create test document
    test_dir = Path("example_docs")
    test_dir.mkdir(exist_ok=True)
    
    doc = test_dir / "intro.txt"
    doc.write_text("""
    OpenAI provides the most advanced AI models available.
    GPT-4 and GPT-3.5 are used by millions of applications.
    The API is reliable, fast, and production-ready.
    Pricing is affordable at fractions of a cent per request.
    """)
    
    # Ingest and query
    print("📥 Ingesting documents...")
    result = client.ingest(str(test_dir))
    print(f"✓ Processed {result['chunks_processed']} chunks")
    
    print("\n🔍 Querying: 'Why use OpenAI for production?'")
    response = client.query("Why use OpenAI for production?")
    print(f"\n💡 Answer:\n{response['answer']}\n")
    
    # Cleanup
    doc.unlink()
    test_dir.rmdir()
    Path("openai_vectors.json").unlink(missing_ok=True)
    
    print("✓ OpenAI example complete!\n")


# ============================================================================
# EXAMPLE 4: Gemini (Free but Limited)
# ============================================================================
def example_gemini():
    """
    Using Gemini - Free tier with strict limits
    
    Prerequisites:
    1. Get API key from: https://makersuite.google.com/app/apikey
    2. Set environment variable: export GEMINI_API_KEY='your_key'
    """
    print("\n" + "="*80)
    print("Example 4: Using Gemini (Free tier, Limited)")
    print("="*80 + "\n")
    
    # Check for API key
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️  GEMINI_API_KEY not set. Skipping this example.")
        print("   Get your free key at: https://makersuite.google.com/app/apikey")
        print("   Then run: export GEMINI_API_KEY='your_key'\n")
        return
    
    from deeprepo import DeepRepoClient
    
    print("⚠️  Note: Gemini has strict rate limits (15 requests/minute)")
    
    # Create client
    client = DeepRepoClient(
        provider_name="gemini",
        storage_path="gemini_vectors.json"
    )
    
    # Create test document
    test_dir = Path("example_docs")
    test_dir.mkdir(exist_ok=True)
    
    doc = test_dir / "intro.txt"
    doc.write_text("""
    Google's Gemini is a powerful multimodal AI model.
    It has a free tier but with very strict rate limits.
    Best used for testing and small projects.
    For production, consider Ollama or OpenAI instead.
    """)
    
    # Ingest and query
    print("📥 Ingesting documents...")
    result = client.ingest(str(test_dir))
    print(f"✓ Processed {result['chunks_processed']} chunks")
    
    print("\n🔍 Querying: 'When should I use Gemini?'")
    response = client.query("When should I use Gemini?")
    print(f"\n💡 Answer:\n{response['answer']}\n")
    
    # Cleanup
    doc.unlink()
    test_dir.rmdir()
    Path("gemini_vectors.json").unlink(missing_ok=True)
    
    print("✓ Gemini example complete!\n")


# ============================================================================
# EXAMPLE 5: Switching Between Providers
# ============================================================================
def example_switching_providers():
    """
    Shows how easy it is to switch between providers
    """
    print("\n" + "="*80)
    print("Example 5: Switching Between Providers")
    print("="*80 + "\n")
    
    print("DeepRepo makes it easy to switch providers!")
    print("Just change the 'provider_name' parameter:\n")
    
    print("# Using Ollama (local, free)")
    print("client = DeepRepoClient(provider_name='ollama')\n")
    
    print("# Using HuggingFace (cloud, free)")
    print("client = DeepRepoClient(provider_name='huggingface')\n")
    
    print("# Using OpenAI (cloud, paid)")
    print("client = DeepRepoClient(provider_name='openai')\n")
    
    print("# Using Gemini (cloud, limited free)")
    print("client = DeepRepoClient(provider_name='gemini')\n")
    
    print("The same API works with all providers! 🎉\n")


# ============================================================================
# MAIN
# ============================================================================
def main():
    print("\n" + "="*80)
    print(" 🎯 DeepRepo Provider Examples")
    print("="*80)
    print("\nThis script demonstrates how to use each provider.")
    print("Run the examples you're interested in!\n")
    
    # Show what we're going to run
    print("Available examples:")
    print("  1. Ollama      - FREE, unlimited, local")
    print("  2. HuggingFace - FREE, cloud-based")
    print("  3. OpenAI      - Paid, most reliable")
    print("  4. Gemini      - Free tier (limited)")
    print("  5. Switching   - How to switch providers")
    print()
    
    # Run available examples
    examples = {
        'ollama': example_ollama,
        'huggingface': example_huggingface,
        'openai': example_openai,
        'gemini': example_gemini,
        'switching': example_switching_providers,
    }
    
    # If command line args provided, run those
    import sys
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg in examples:
                examples[arg]()
            else:
                print(f"Unknown example: {arg}")
    else:
        # Run all examples
        try:
            example_ollama()
        except Exception as e:
            print(f"❌ Ollama example failed: {e}\n")
        
        try:
            example_huggingface()
        except Exception as e:
            print(f"❌ HuggingFace example failed: {e}\n")
        
        try:
            example_openai()
        except Exception as e:
            print(f"❌ OpenAI example failed: {e}\n")
        
        try:
            example_gemini()
        except Exception as e:
            print(f"❌ Gemini example failed: {e}\n")
        
        example_switching_providers()
    
    print("="*80)
    print("✅ Examples complete!")
    print("="*80)
    print("\nNext steps:")
    print("  • Run the full test suite: python test_all_providers.py")
    print("  • Read the setup guide: cat PROVIDER_SETUP_GUIDE.md")
    print("  • Check provider status: ./setup_providers.sh")
    print("\nFor production use, we recommend Ollama (free) or OpenAI (paid)")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
