FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY mcp-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules directly to app directory and create shared symlink
COPY shared/vigil_mcp_lowlevel.py .
COPY shared/bank_api_client.py .
RUN mkdir -p /app/shared && ln -s /app/bank_api_client.py /app/shared/bank_api_client.py

# Copy application code from mcp-server directory
COPY mcp-server/vigil_mcp_server.py .
COPY mcp-server/vigil_mcp_rest_wrapper.py .
COPY mcp-server/vigil_mcp_stdio_server.py .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash vigil
USER vigil

# Expose the port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the lowlevel MCP server with SSE transport
CMD ["python", "vigil_mcp_lowlevel.py", "--transport", "sse", "--port", "8000"]
