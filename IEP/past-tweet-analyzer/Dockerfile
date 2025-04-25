FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY IEP/past-tweet-analyzer/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN python -m nltk.downloader stopwords punkt wordnet # Add wordnet if needed by cleaning/tokenizing

COPY IEP/past-tweet-analyzer/ .

EXPOSE 5005

CMD ["python", "app.py"]
