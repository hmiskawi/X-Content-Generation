# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# Specify the path relative to the build context root
COPY IEP/trend-analyzer/requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Optional: Download NLTK data if needed for cleaning (e.g., punkt) - Removed for now

# Copy the rest of the application code from the specific IEP directory into the container at /app
COPY IEP/trend-analyzer/ .

# Make port 5006 available
EXPOSE 5006

# Define the command to run the application
CMD ["python", "app.py"]
