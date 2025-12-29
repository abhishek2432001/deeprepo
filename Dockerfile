# Multi-stage Dockerfile for DeepRepo
# Builds and runs the RAG engine with FastAPI

FROM python:3.10-slim AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the core library
COPY deeprepo_core/ /app/deeprepo_core/

# Install the core library in editable mode
RUN pip install --no-cache-dir -e /app/deeprepo_core/

# Copy web app
COPY web-app/ /app/web_app/

# Install web app dependencies
RUN pip install --no-cache-dir -r /app/web_app/requirements.txt

# Create data directory for mounted volumes
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LLM_PROVIDER=openai

# Expose port
EXPOSE 8000

# Run the FastAPI server
CMD ["uvicorn", "web_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
