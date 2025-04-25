FROM python:3.10-slim

WORKDIR /app

COPY IEP/keyword-suggester/requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN python -m nltk.downloader wordnet punkt

COPY IEP/keyword-suggester/ .

EXPOSE 5004

CMD ["python", "app.py"]
