FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libtesseract-dev \
        libleptonica-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend
ENV OMP_THREAD_LIMIT=1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1