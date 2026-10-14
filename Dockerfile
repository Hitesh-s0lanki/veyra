# Dockerfile
FROM python:3.13-slim

# Prevent .pyc & force unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps (optional – drop build-essential if not needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ffmpeg \
  && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# App port (Render injects PORT; falls back to 8000 locally)
ENV PORT=8000
EXPOSE 8000

# Start FastAPI with uvicorn
# module:variable -> src/api.py : api
CMD ["sh", "-c", "uvicorn src.api:api --host 0.0.0.0 --port ${PORT}"]
