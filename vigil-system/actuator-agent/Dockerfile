# Vigil Actuator Agent - Protective Action Executor
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

# Copy the MCP server
COPY vigil_mcp_lowlevel.py ./vigil_mcp_lowlevel.py

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV MCP_SERVER_PATH=/app/vigil_mcp_lowlevel.py
ENV ACTUATOR_PORT=8002
ENV AUTO_EXECUTE_ACTIONS=false

# Expose the A2A communication port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Run the agent
CMD ["python", "agent.py"]