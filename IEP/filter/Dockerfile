FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY ./IEP/filter/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./IEP/filter/ .
COPY ./IEP/filter/filtering_model /app/filtering_model

EXPOSE 5022
CMD ["python", "app.py"]
