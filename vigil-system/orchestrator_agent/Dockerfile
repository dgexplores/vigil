# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the orchestrator agent files into the container at /app
COPY vigil-system/orchestrator_agent/requirements.txt /app/
COPY vigil-system/orchestrator_agent/agent.py /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Run agent.py when the container launches
CMD ["python", "agent.py"]
