#!/usr/bin/env python3
"""
DeepRepo - Live Demo Script
============================

This script demonstrates the key features of DeepRepo
in a way that's perfect for interviews and presentations.

Usage:
    python demo_deeprepo.py

Make sure you have:
1. Installed deeprepo: cd deeprepo_core && pip install -e .
2. Ollama running with models pulled (or set different provider)
"""

import time
import json
from pathlib import Path
from deeprepo import DeepRepoClient


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def print_subsection(title: str):
    """Print a formatted subsection."""
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}\n")


def demo_initialization():
    """Demo 1: Initialize DeepRepo with different providers."""
    print_section("DEMO 1: Multi-Provider Initialization")
    
    print("🔧 DeepRepo supports 4 AI providers:")
    print("   1. Ollama (FREE, local, offline)")
    print("   2. HuggingFace (FREE tier, cloud)")
    print("   3. OpenAI (paid, best quality)")
    print("   4. Gemini (free tier, limited)")
    
    print("\n📦 Initializing with Ollama (FREE local provider)...")
    client = DeepRepoClient(provider_name="ollama", storage_path="demo_vectors.json")
    print("✅ Client initialized successfully!")
    
    print("\n💡 To switch providers, just change one parameter:")
    print('   client = DeepRepoClient(provider_name="openai")')
    
    return client


def demo_ingestion(client: DeepRepoClient):
    """Demo 2: Ingest a directory."""
    print_section("DEMO 2: Intelligent Code Ingestion")
    
    # For demo, let's ingest the deeprepo library itself
    demo_path = "./deeprepo_core/src/deeprepo"
    
    if not Path(demo_path).exists():
        print(f"⚠️  Demo path {demo_path} not found.")
        print("   Please update demo_path to point to your code directory.")
        return None
    
    print(f"📂 Ingesting code from: {demo_path}")
    print("\n🔄 What happens during ingestion:")
    print("   1. 📁 Scan directory (skip .git, binaries, etc.)")
    print("   2. ✂️  Chunk files (1000 chars + 100 char overlap)")
    print("   3. 🧠 Generate embeddings (convert text → vectors)")
    print("   4. 💾 Save to JSON (vectors.json)")
    
    print("\n⏳ Starting ingestion... (this may take a minute)\n")
    
    start_time = time.time()
    result = client.ingest(demo_path, chunk_size=1000, overlap=100)
    duration = time.time() - start_time
    
    print("\n✅ Ingestion Complete!")
    print(f"   • Files scanned: {result.get('files_scanned', 'N/A')}")
    print(f"   • Chunks created: {result.get('chunks_processed', 'N/A')}")
    print(f"   • Time taken: {duration:.2f} seconds")
    print(f"   • Speed: ~{result.get('files_scanned', 0) / duration:.1f} files/sec")
    
    return result


def demo_query(client: DeepRepoClient):
    """Demo 3: Query the knowledge base."""
    print_section("DEMO 3: Semantic Search & RAG Query")
    
    # Get stats first
    stats = client.get_stats()
    print(f"📊 Vector Store Stats:")
    print(f"   • Total chunks: {stats.get('total_chunks', 0):,}")
    print(f"   • Storage size: {stats.get('storage_size_mb', 0):.2f} MB")
    
    # Demo query 1: Technical question
    print_subsection("Query 1: Technical Question")
    question1 = "How does vector search work?"
    print(f"❓ Question: '{question1}'")
    print("\n🔄 What happens during query:")
    print("   1. 🧠 Embed question → query vector")
    print("   2. 🔍 Compute cosine similarity with all chunks")
    print("   3. 📊 Find top-5 most similar chunks (argpartition)")
    print("   4. 📝 Build context from retrieved chunks")
    print("   5. 🤖 Generate answer using LLM + context")
    
    print("\n⏳ Querying... (LLM is thinking)\n")
    
    start_time = time.time()
    response1 = client.query(question1, top_k=5)
    duration = time.time() - start_time
    
    print(f"💡 Answer (in {duration:.2f}s):")
    print(f"{'─'*70}")
    print(response1.get('answer', 'No answer'))
    print(f"{'─'*70}")
    
    print("\n📚 Sources (with similarity scores):")
    for i, source in enumerate(response1.get('sources', [])[:3], 1):
        metadata = source.get('metadata', {})
        score = source.get('score', 0)
        file = metadata.get('file', 'unknown')
        print(f"   {i}. {file} (similarity: {score:.3f})")
    
    # Demo query 2: Follow-up question
    print_subsection("Query 2: Follow-Up Question (Tests History)")
    question2 = "What algorithm is used for that?"
    print(f"❓ Follow-up: '{question2}'")
    print("   (Notice: 'that' refers to previous answer)")
    
    print("\n⏳ Querying with conversation history...\n")
    
    start_time = time.time()
    response2 = client.query(question2, top_k=5, include_history=True)
    duration = time.time() - start_time
    
    print(f"💡 Answer (in {duration:.2f}s):")
    print(f"{'─'*70}")
    print(response2.get('answer', 'No answer'))
    print(f"{'─'*70}")
    
    # Demo query 3: Show conversation history
    print_subsection("Conversation History")
    history = response2.get('history', [])
    print(f"📝 {len(history)} messages in conversation:")
    for i, msg in enumerate(history[-4:], 1):  # Show last 4 messages
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')[:100]  # Truncate for display
        print(f"\n   {i}. {role.upper()}:")
        print(f"      {content}...")
    
    return response1, response2


def demo_stats_and_monitoring(client: DeepRepoClient):
    """Demo 4: Monitoring and stats."""
    print_section("DEMO 4: Monitoring & Observability")
    
    stats = client.get_stats()
    
    print("📊 Comprehensive Statistics:")
    print(f"\n   Storage:")
    print(f"   • Total chunks: {stats.get('total_chunks', 0):,}")
    print(f"   • Storage file: {stats.get('storage_path', 'N/A')}")
    print(f"   • Size on disk: {stats.get('storage_size_mb', 0):.2f} MB")
    
    print(f"\n   Performance:")
    print(f"   • Average chunk size: ~1000 characters")
    print(f"   • Search complexity: O(n) for top-k")
    print(f"   • Embedding dimensions: 384-1536 (provider dependent)")
    
    print(f"\n   Configuration:")
    print(f"   • Provider: {stats.get('current_provider', 'unknown')}")
    print(f"   • Vector store: JSON (human-readable)")
    print(f"   • Similarity metric: Cosine similarity")


def demo_architecture_highlights():
    """Demo 5: Architecture and design patterns."""
    print_section("DEMO 5: Architecture Highlights")
    
    print("🏗️  Design Patterns Applied:")
    print("\n   1. REPOSITORY PATTERN")
    print("      • VectorStore decouples storage from logic")
    print("      • Can swap JSON → PostgreSQL without app changes")
    
    print("\n   2. STRATEGY PATTERN")
    print("      • LLMProvider interface allows runtime provider switching")
    print("      • Same code works with Ollama, OpenAI, Gemini, etc.")
    
    print("\n   3. REGISTRY PATTERN")
    print("      • @register_llm decorator for auto-discovery")
    print("      • Add new providers without modifying core code")
    
    print("\n   4. FACADE PATTERN")
    print("      • DeepRepoClient provides simple API")
    print("      • Hides complexity: just ingest() and query()")
    
    print("\n   5. SINGLETON PATTERN (FastAPI)")
    print("      • Load vectors.json once at startup")
    print("      • Reuse across requests (don't reload 1GB per request)")
    
    print("\n🚀 Performance Optimizations:")
    print("   • Lazy NumPy loading (only when needed)")
    print("   • argpartition for O(n) top-k vs O(n log n) sort")
    print("   • Vectorized operations (10-100x faster than Python loops)")
    print("   • Embeddings matrix caching")


def demo_code_walkthrough():
    """Demo 6: Quick code walkthrough."""
    print_section("DEMO 6: Code Simplicity")
    
    print("📝 That entire demo was powered by just 3 lines:")
    print(f"\n{'─'*70}")
    print("""
    from deeprepo import DeepRepoClient
    
    client = DeepRepoClient(provider_name="ollama")
    client.ingest("./my_code")
    response = client.query("How does auth work?")
    """)
    print(f"{'─'*70}")
    
    print("\n💪 Why DeepRepo?")
    print("   ✅ Raw Python - no LangChain/LlamaIndex black boxes")
    print("   ✅ 5 dependencies vs 100+ in competitors")
    print("   ✅ Full transparency - you understand every line")
    print("   ✅ FREE options - Ollama is unlimited and local")
    print("   ✅ Production-ready - Docker, FastAPI, tests included")


def main():
    """Run the full demo."""
    print("\n" + "="*70)
    print(" "*15 + "🚀 DEEPREPO LIVE DEMO 🚀")
    print("="*70)
    print("\nProduction-grade RAG engine built from scratch")
    print("No LangChain. No Vector DBs. Just Python, NumPy, and Smart Design.")
    
    try:
        # Demo 1: Initialize
        client = demo_initialization()
        
        # Demo 2: Ingest
        ingestion_result = demo_ingestion(client)
        
        if ingestion_result is None:
            print("\n⚠️  Skipping query demos (no data ingested)")
            demo_architecture_highlights()
            demo_code_walkthrough()
            return
        
        # Demo 3: Query
        demo_query(client)
        
        # Demo 4: Stats
        demo_stats_and_monitoring(client)
        
        # Demo 5: Architecture
        demo_architecture_highlights()
        
        # Demo 6: Code simplicity
        demo_code_walkthrough()
        
        # Final message
        print_section("DEMO COMPLETE")
        print("🎉 You just saw:")
        print("   • Multi-provider AI support")
        print("   • Intelligent code ingestion")
        print("   • Semantic search with cosine similarity")
        print("   • RAG (Retrieval Augmented Generation)")
        print("   • Conversation history")
        print("   • Production-ready monitoring")
        print("   • Clean architecture with 5 design patterns")
        
        print("\n📚 Next Steps:")
        print("   • Read PRESENTATION_GUIDE.md (comprehensive explanation)")
        print("   • Check INTERVIEW_CHEATSHEET.md (quick reference)")
        print("   • View VISUAL_DIAGRAMS.md (architecture diagrams)")
        print("   • Try the FastAPI web app: ./start_webapp.sh ollama")
        
        print("\n💡 Questions to expect in interviews:")
        print("   1. How does cosine similarity work?")
        print("   2. Why not use LangChain?")
        print("   3. What design patterns did you use?")
        print("   4. How does RAG reduce hallucinations?")
        print("   5. How would you scale this to 10M chunks?")
        
        print("\n🎯 Your answer: 'Check my PRESENTATION_GUIDE.md!'")
        print("\n" + "="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        print("\nTroubleshooting:")
        print("   1. Make sure deeprepo is installed: cd deeprepo_core && pip install -e .")
        print("   2. Check if Ollama is running (or set different provider)")
        print("   3. Verify demo_path points to existing code directory")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
