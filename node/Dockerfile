FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for Ollama data
RUN mkdir -p /root/.ollama

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "Starting Ollama service..."\n\
ollama serve &\n\
OLLAMA_PID=$!\n\
\n\
# Wait for Ollama to be ready\n\
echo "Waiting for Ollama to start..."\n\
for i in {1..30}; do\n\
    if ollama list >/dev/null 2>&1; then\n\
        echo "Ollama is ready!"\n\
        break\n\
    fi\n\
    echo "Waiting... ($i/30)"\n\
    sleep 2\n\
done\n\
\n\
# Pull model if specified\n\
if [ ! -z "$OLLAMA_MODEL" ]; then\n\
    echo "Pulling model: $OLLAMA_MODEL"\n\
    ollama pull "$OLLAMA_MODEL" || echo "Warning: Failed to pull model, continuing anyway..."\n\
fi\n\
\n\
# Start the node server\n\
echo "Starting Ambient Intelligence Node..."\n\
exec python server.py\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
