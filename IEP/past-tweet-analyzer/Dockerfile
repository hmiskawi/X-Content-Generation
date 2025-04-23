# Use the full official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Update package list & install build tools (less likely needed but safe)
# No need for ca-certificates explicitly usually with full image + certifi
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY IEP/past-tweet-analyzer/requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download necessary NLTK data during the build process
RUN python -m nltk.downloader stopwords punkt wordnet # Add wordnet if needed by cleaning/tokenizing

# Copy the rest of the application code from the specific IEP directory into the container at /app
COPY IEP/past-tweet-analyzer/ .

# Make port 5005 available
EXPOSE 5005

# Define the command to run the application
CMD ["python", "app.py"]