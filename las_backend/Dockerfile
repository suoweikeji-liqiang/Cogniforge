FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
RUN chmod +x /app/scripts/start.sh

# Create data directory for SQLite
RUN mkdir -p /app/data

EXPOSE 8000

# Run migrations and then start the API
CMD ["/app/scripts/start.sh"]
