FROM python:3.11-slim

WORKDIR /app

# System dependencies for document processing and network
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure storage directories exist
RUN mkdir -p storage/cvs storage/jds

EXPOSE 8000

CMD ["python", "-m", "app.main", "--mode", "all", "--host", "0.0.0.0", "--port", "8000"]
