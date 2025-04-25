FROM python:3.10-slim

WORKDIR /app

COPY IEP/image-generator/requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY IEP/image-generator/ .

EXPOSE 5003

CMD ["python", "app.py"]
