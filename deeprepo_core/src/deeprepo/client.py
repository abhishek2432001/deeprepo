"""DeepRepoClient - Main facade for the RAG engine.

Provides the primary interface for ingesting documents and querying
with retrieval-augmented generation.
"""

import os
from pathlib import Path
from typing import Any

from deeprepo.ingestion import ingest_directory
from deeprepo.storage import VectorStore
from deeprepo.providers import get_embedding, get_llm
from deeprepo.interfaces import EmbeddingProvider, LLMProvider


class DeepRepoClient:
    """Main client for DeepRepo RAG operations.
    
    This class serves as the facade (main entry point) for the library,
    coordinating ingestion, storage, and query operations.
    
    Attributes:
        embedding_provider_name: Name of the embedding provider being used.
        llm_provider_name: Name of the LLM provider being used.
        store: VectorStore instance for persisting embeddings.
        embedding_provider: Provider for generating embeddings.
        llm_provider: Provider for generating responses.
        conversation_history: List of past Q&A exchanges.
    """
    
    def __init__(
        self,
        provider_name: str | None = None,
        embedding_provider_name: str | None = None,
        llm_provider_name: str | None = None,
        storage_path: str = "vectors.json"
    ):
        """Initialize the DeepRepoClient.
        
        Args:
            provider_name: Name of the provider to use for both embeddings and LLM.
                This is a convenience parameter for backward compatibility.
                If provided, it will be used for both embedding_provider_name and llm_provider_name.
                Available options:
                - "openai" (requires: pip install deeprepo[openai])
                - "gemini" (requires: pip install deeprepo[gemini])
                - "ollama" (requires: Ollama installed separately, see https://ollama.ai)
                - "huggingface" (requires: pip install deeprepo[huggingface])
                - "anthropic" (requires: pip install deeprepo[anthropic])
                Defaults to LLM_PROVIDER env var, or "openai" if not set.
            embedding_provider_name: Name of the embedding provider to use.
                If not provided, defaults to provider_name or EMBEDDING_PROVIDER env var.
                This allows using different providers for embeddings and LLM.
                For example, use "openai" for embeddings and "anthropic" for LLM.
            llm_provider_name: Name of the LLM provider to use.
                If not provided, defaults to provider_name or LLM_PROVIDER env var.
                This allows using different providers for embeddings and LLM.
            storage_path: Path to the vector storage file.
        """
        # Determine embedding provider
        if embedding_provider_name:
            self.embedding_provider_name = embedding_provider_name
        elif provider_name:
            self.embedding_provider_name = provider_name
        else:
            self.embedding_provider_name = os.environ.get(
                "EMBEDDING_PROVIDER",
                os.environ.get("LLM_PROVIDER", "openai")
            )
        
        # Determine LLM provider
        if llm_provider_name:
            self.llm_provider_name = llm_provider_name
        elif provider_name:
            self.llm_provider_name = provider_name
        else:
            self.llm_provider_name = os.environ.get("LLM_PROVIDER", "openai")
        
        # For backward compatibility, keep provider_name attribute
        # It represents the LLM provider by default
        self.provider_name = self.llm_provider_name
        
        self.storage_path = storage_path
        
        # Initialize components
        self.store = VectorStore(storage_path)
        self.embedding_provider: EmbeddingProvider = get_embedding(self.embedding_provider_name)
        self.llm_provider: LLMProvider = get_llm(self.llm_provider_name)
        
        # Load existing vectors if available
        self.store.load()
        
        # Conversation history for context
        self.conversation_history: list[dict[str, str]] = []
        
    def ingest(
        self,
        path: str | Path,
        chunk_size: int = 1000,
        overlap: int = 100,
        batch_size: int = 100
    ) -> dict[str, Any]:
        """Ingest a directory into the vector store.
        
        Scans the directory, chunks files, generates embeddings,
        and saves to the vector store.
        
        Args:
            path: Path to the directory to ingest.
            chunk_size: Maximum characters per chunk. Defaults to 1000.
            overlap: Characters of overlap between chunks. Defaults to 100.
            batch_size: Number of chunks to embed in one API call. Defaults to 100.
            
        Returns:
            Dictionary with ingestion statistics:
                - 'chunks_processed': Number of chunks created
                - 'files_scanned': Number of files processed
        """
        path = Path(path)
        
        # Get all chunks from directory
        chunks = ingest_directory(path, chunk_size, overlap)
        
        if not chunks:
            return {
                'chunks_processed': 0,
                'files_scanned': 0,
                'message': 'No content found to ingest'
            }
        
        # Track unique files
        unique_files = set(chunk['metadata']['filepath'] for chunk in chunks)
        
        # Generate embeddings in batches
        print(f"Generating embeddings for {len(chunks)} chunks...")
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [chunk['text'] for chunk in batch]
            
            embeddings = self.embedding_provider.embed_batch(texts)
            
            for chunk, embedding in zip(batch, embeddings):
                chunk['embedding'] = embedding
                
            print(f"Processed {min(i + batch_size, len(chunks))}/{len(chunks)} chunks")
        
        # Save to vector store
        self.store.save(chunks)
        
        return {
            'chunks_processed': len(chunks),
            'files_scanned': len(unique_files),
            'message': f'Successfully ingested {len(unique_files)} files into {len(chunks)} chunks'
        }
    
    def query(
        self,
        question: str,
        top_k: int = 5,
        include_history: bool = True
    ) -> dict[str, Any]:
        """Query the knowledge base with RAG.
        
        Embeds the question, retrieves relevant context,
        and generates a response using the LLM.
        
        Args:
            question: The user's question.
            top_k: Number of context chunks to retrieve. Defaults to 5.
            include_history: Whether to include conversation history. Defaults to True.
            
        Returns:
            Dictionary containing:
                - 'answer': The LLM's response
                - 'sources': List of source file paths used
                - 'history': Conversation history including this exchange
        """
        # Embed the question
        query_embedding = self.embedding_provider.embed(question)
        
        # Search for relevant chunks
        results = self.store.search(query_embedding, top_k)
        
        if not results:
            answer = "I don't have any documents indexed yet. Please ingest some files first."
            return {
                'answer': answer,
                'sources': [],
                'history': self.conversation_history
            }
        
        # Build context from retrieved chunks
        context_parts = []
        sources = []
        
        for result in results:
            filepath = result.get('metadata', {}).get('filepath', 'unknown')
            chunk_idx = result.get('metadata', {}).get('chunk_index', 0)
            score = result.get('score', 0)
            
            context_parts.append(
                f"[Source: {filepath}, Chunk {chunk_idx}, Score: {score:.3f}]\n{result['text']}"
            )
            
            if filepath not in sources:
                sources.append(filepath)
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Build conversation history context if enabled
        history_context = ""
        if include_history and self.conversation_history:
            history_parts = []
            for exchange in self.conversation_history[-5:]:  # Last 5 exchanges
                history_parts.append(f"User: {exchange['question']}")
                history_parts.append(f"Assistant: {exchange['answer']}")
            history_context = "\n\nPrevious conversation:\n" + "\n".join(history_parts)
        
        # Generate response
        full_context = context + history_context if history_context else context
        answer = self.llm_provider.generate(question, context=full_context)
        
        # Update conversation history
        self.conversation_history.append({
            'question': question,
            'answer': answer,
            'sources': sources
        })
        
        return {
            'answer': answer,
            'sources': sources,
            'history': self.conversation_history
        }
    
    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.conversation_history = []
        
    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the current vector store.
        
        Returns:
            Dictionary with store statistics.
        """
        chunks = self.store.chunks
        
        if not chunks:
            return {
                'total_chunks': 0,
                'total_files': 0,
                'storage_path': str(self.storage_path),
                'embedding_provider': self.embedding_provider_name,
                'llm_provider': self.llm_provider_name,
                'provider': self.llm_provider_name  # For backward compatibility
            }
        
        unique_files = set(
            chunk.get('metadata', {}).get('filepath', 'unknown')
            for chunk in chunks
        )
        
        return {
            'total_chunks': len(chunks),
            'total_files': len(unique_files),
            'files': list(unique_files),
            'storage_path': str(self.storage_path),
            'embedding_provider': self.embedding_provider_name,
            'llm_provider': self.llm_provider_name,
            'provider': self.llm_provider_name  # For backward compatibility
        }
