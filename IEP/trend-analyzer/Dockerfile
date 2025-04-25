FROM python:3.10-slim

WORKDIR /app

COPY IEP/trend-analyzer/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY IEP/trend-analyzer/ .

EXPOSE 5006

CMD ["python", "app.py"]
