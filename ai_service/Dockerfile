FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed by PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching – only reinstalls if requirements change)
COPY requirements.txt .

# Install Python dependencies (no cache to keep image small)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories inside the container
RUN mkdir -p /app/data/chroma_db /app/data/documents

# Run as non-root user for security
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Expose service port
EXPOSE 8000

# Start uvicorn with production settings
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
