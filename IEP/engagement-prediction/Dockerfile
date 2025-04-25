FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./IEP/engagement-prediction/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY ./IEP/engagement-prediction/app.py /app/app.py
COPY ./IEP/engagement-prediction/models /models
COPY ./IEP/engagement-prediction/text_encoder /text_encoder

EXPOSE 5010

CMD ["python", "app.py"]