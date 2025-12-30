"""DeepRepo FastAPI Web Service.

Provides REST API endpoints for document ingestion and RAG queries.
Uses lifespan events to initialize the DeepRepoClient once at startup.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from deeprepo import DeepRepoClient


# Global state for the DeepRepo client (Singleton Pattern)
class AppState:
    """Application state container."""
    client: DeepRepoClient | None = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events.
    
    Initializes the DeepRepoClient once when the server starts,
    avoiding re-initialization on every request.
    
    Supports separate embedding and LLM providers via environment variables:
    - EMBEDDING_PROVIDER: Provider for embeddings
    - LLM_PROVIDER: Provider for LLM
    """
    import os
    
    # Startup: Initialize the client
    print("Initializing DeepRepoClient...")
    
    embedding_provider = os.environ.get("EMBEDDING_PROVIDER")
    llm_provider = os.environ.get("LLM_PROVIDER")
    
    if embedding_provider or llm_provider:
        app_state.client = DeepRepoClient(
            embedding_provider_name=embedding_provider,
            llm_provider_name=llm_provider
        )
        print(
            f"DeepRepoClient ready - "
            f"Embedding: {app_state.client.embedding_provider_name}, "
            f"LLM: {app_state.client.llm_provider_name}"
        )
    else:
        app_state.client = DeepRepoClient()
        print(f"DeepRepoClient ready. Provider: {app_state.client.provider_name}")
    
    yield
    
    # Shutdown: Cleanup if needed
    print("Shutting down DeepRepoClient...")
    app_state.client = None


# Create FastAPI app with lifespan
app = FastAPI(
    title="DeepRepo API",
    description="RAG engine for local codebases",
    version="0.1.0",
    lifespan=lifespan
)


# Request/Response Models

class IngestRequest(BaseModel):
    """Request model for document ingestion."""
    path: str = Field(..., description="Path to the directory to ingest")
    chunk_size: int = Field(default=1000, description="Max characters per chunk")
    overlap: int = Field(default=100, description="Overlap between chunks")


class IngestResponse(BaseModel):
    """Response model for ingestion results."""
    chunks_processed: int
    files_scanned: int
    message: str


class ChatRequest(BaseModel):
    """Request model for chat/query."""
    query: str = Field(..., description="The question to ask")
    top_k: int = Field(default=5, description="Number of context chunks to retrieve")


class ChatResponse(BaseModel):
    """Response model for chat results."""
    answer: str
    sources: list[str]
    history: list[dict[str, Any]]


class StatsResponse(BaseModel):
    """Response model for statistics."""
    total_chunks: int
    total_files: int
    files: list[str] = []
    storage_path: str
    embedding_provider: str = ""
    llm_provider: str = ""
    provider: str = ""  # For backward compatibility


# API Endpoints

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "DeepRepo API"}


@app.get("/stats", response_model=StatsResponse, tags=["Info"])
async def get_stats():
    """Get statistics about the current vector store."""
    if app_state.client is None:
        raise HTTPException(status_code=503, detail="Client not initialized")
    
    return app_state.client.get_stats()


@app.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def ingest_documents(request: IngestRequest):
    """Ingest documents from a directory.
    
    Scans the specified directory, chunks the files, generates embeddings,
    and stores them in the vector store.
    """
    if app_state.client is None:
        raise HTTPException(status_code=503, detail="Client not initialized")
    
    try:
        result = app_state.client.ingest(
            path=request.path,
            chunk_size=request.chunk_size,
            overlap=request.overlap
        )
        return IngestResponse(
            chunks_processed=result['chunks_processed'],
            files_scanned=result['files_scanned'],
            message=result['message']
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """Query the knowledge base with a question.
    
    Uses RAG to retrieve relevant context and generate an answer.
    """
    if app_state.client is None:
        raise HTTPException(status_code=503, detail="Client not initialized")
    
    try:
        result = app_state.client.query(
            question=request.query,
            top_k=request.top_k
        )
        return ChatResponse(
            answer=result['answer'],
            sources=result['sources'],
            history=result['history']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear-history", tags=["Chat"])
async def clear_history():
    """Clear the conversation history."""
    if app_state.client is None:
        raise HTTPException(status_code=503, detail="Client not initialized")
    
    app_state.client.clear_history()
    return {"message": "Conversation history cleared"}
