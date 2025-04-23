# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# Specify the path relative to the build context root
COPY IEP/image-generator/requirements.txt .

# Install any needed packages specified in requirements.txt
# Add build dependencies needed by Pillow, then remove them
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application code from the specific IEP directory into the container at /app
COPY IEP/image-generator/ .

# Make port 5003 available (using a different port)
EXPOSE 5003

# Define the command to run the application
CMD ["python", "app.py"]