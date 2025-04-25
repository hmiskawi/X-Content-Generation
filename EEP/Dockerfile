# Dockerfile for EEP Orchestrator

# Use a standard Python slim image
FROM python:3.9-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker caching
COPY requirements.txt .

# Install dependencies for the orchestrator
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the orchestrator code and any necessary configuration files
COPY ./orchestrator ./orchestrator
# COPY ./config ./config # Uncomment if you have a config directory

# Create the output directory structure expected by the script
# The script uses relative path "../generated_content", so we create it one level up
# relative to where the script will eventually run inside orchestrator.
# An alternative is to modify the script to write to a path relative to WORKDIR e.g. /app/output
RUN mkdir -p /app/generated_content/images

# Define the entrypoint to run the main orchestrator script
# This allows passing command-line arguments (username, keyword, etc.) when running the container
ENTRYPOINT ["python", "orchestrator/main_generator.py"]

# Expose is not needed as this container runs a script and exits,
# it doesn't host a long-running server process itself.
# If this were ever turned into an API itself (e.g., triggered via HTTP),
# then you would add EXPOSE and change CMD/ENTRYPOINT to run a server.
