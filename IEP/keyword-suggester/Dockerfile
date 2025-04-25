# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# Specify the path relative to the build context root
COPY IEP/keyword-suggester/requirements.txt .

# Install system dependencies that might be needed by NLTK or its data downloads
RUN apt-get update && apt-get install -y --no-install-recommends \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download necessary NLTK data during the build process
# WordNet is the core lexicon/thesaurus
# punkt is needed for tokenization, often used implicitly by WordNet functions
RUN python -m nltk.downloader wordnet punkt

# Copy the rest of the application code from the specific IEP directory into the container at /app
COPY IEP/keyword-suggester/ .

# Make port 5004 available (using a different port)
EXPOSE 5004

# Define the command to run the application
CMD ["python", "app.py"]
