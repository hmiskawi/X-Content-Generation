FROM python:3.10-slim

WORKDIR /app

COPY IEP/hashtag-generator/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY IEP/hashtag-generator/ .

EXPOSE 5002

CMD ["python", "app.py"]
