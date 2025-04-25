# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1  # Prevents python creating .pyc files
ENV PYTHONUNBUFFERED 1      # Force stdout/stderr streams to be unbuffered

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if any - e.g., build tools if needed by some packages)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
# Copying directories ensures their contents are included
COPY ./app ./app
COPY ./models ./models

# Expose the port the app runs on (must match waitress/gunicorn port)
EXPOSE 5010

# Command to run the application using Waitress
# waitress-serve --host=0.0.0.0 listens on all interfaces, --port specifies the port
# app.api:app refers to the 'app' instance within the 'api.py' file inside the 'app' folder/package
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5010", "app.api:app"]

# --- Alternative using Gunicorn (if preferred, usually for Linux deployments) ---
# Ensure 'gunicorn' is in requirements.txt
# WORKERS = os.cpu_count() * 2 + 1 # Common formula for worker count
# CMD ["gunicorn", "--bind", "0.0.0.0:5010", "-w", "4", "app.api:app"] # Example with 4 workers
