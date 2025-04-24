FROM python:3.10-slim

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y git ffmpeg libsm6 libxext6 && rm -rf /var/lib/apt/lists/*

# Copy files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5021
CMD ["python", "app.py"]
