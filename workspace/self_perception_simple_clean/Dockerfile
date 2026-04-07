FROM python:3.11-slim

LABEL maintainer="lobster"
LABEL description="Self-Perception + Dream Memory System (Consolidated)"

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Additional deps for all services
RUN pip install --no-cache-dir \
    httpx \
    chromadb \
    sentence-transformers \
    psutil \
    pyyaml \
    structlog

# Copy all source code
COPY src/ ./src/
COPY frontend/ ./frontend/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Create empty data directories
RUN mkdir -p /app/data/logs /app/data/vector_store

# Entry: supervisor manages all services
CMD ["python", "src/supervisor/supervisor.py"]
