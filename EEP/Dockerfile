FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY ./EEP/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN mkdir /tmp_uploads && chmod 777 /tmp_uploads

COPY ./EEP/UI/ /app/

EXPOSE 5050

ENTRYPOINT ["python", "ui.py"]