FROM python:3.9-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
WORKDIR /app/src

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]