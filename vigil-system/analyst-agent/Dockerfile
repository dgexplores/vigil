# Vigil Analyst Agent - Fraud Detection Cognitive Core
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
COPY config.yaml .

# Copy the MCP server
COPY vigil_mcp_lowlevel.py ./vigil_mcp_lowlevel.py

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV MCP_SERVER_PATH=/app/vigil_mcp_lowlevel.py
ENV RISK_THRESHOLD=75
ENV ANALYST_PORT=8001

# Expose the A2A communication port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the agent
CMD ["python", "agent.py"]