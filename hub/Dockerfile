# Use official Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1


# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY src/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ /app/src/

# Create required directories (these are typically overridden by mounted volumes)
RUN mkdir -p /app/src/crypto_keys \
    && mkdir -p /app/src/session_keys

# Set directory permissions
RUN chmod -R 755 /app/src/crypto_keys \
    && chmod -R 755 /app/src/session_keys

# Expose application port
EXPOSE 9000

# Default start command
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "2"]