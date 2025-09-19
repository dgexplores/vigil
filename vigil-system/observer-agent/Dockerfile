# Vigil Observer Agent - Continuous Transaction Monitoring
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main agent code
COPY agent.py .

# Copy the MCP stdio client module
COPY mcp_stdio_client.py .

# Copy the MCP cluster proxy for in-cluster communication
COPY mcp_cluster_proxy.py .

# Copy the MCP server files from parent mcp-server directory
COPY ../mcp-server/vigil_mcp_server.py .
COPY ../mcp-server/vigil_mcp_stdio_server.py .

# Copy the MCP server (for embedded/fallback mode)
COPY vigil_mcp_lowlevel.py .

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV MCP_SERVER_PATH=/app/vigil_mcp_stdio_server.py
ENV OBSERVER_PORT=8000
ENV POLLING_INTERVAL=5
ENV BATCH_SIZE=100

# Expose the A2A communication port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the agent
CMD ["python", "agent.py"]