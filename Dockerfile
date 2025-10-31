# Dockerfile for Hivemind MCP Server on Railway
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/
COPY static/ ./static/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port (Railway will set $PORT)
EXPOSE 8080

# Run the MCP server
CMD python src/remote_mcp_server_fixed.py
