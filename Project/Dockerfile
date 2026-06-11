# DEPRECATED: This Dockerfile targets the legacy Flask stack (Project/Api/, run_production.py).
# The Flask app was removed in 2026-06. The dashboard is now deployed on Vercel (see .vercel/).
# Scraper entry points (run.py, run_top5.py, run_outreach.py) can be invoked directly with Python.
# Kept for reference / future use with a different image (e.g., a Next.js standalone build).
#
# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Create log directory
RUN mkdir -p /var/log/home-ai

# DEPRECATED: port 5001/healthcheck were for the Flask app
# EXPOSE 5001
# HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
#     CMD curl -f http://localhost:5001/api/stats || exit 1

# Default: run the scraper pipeline. Override with `docker run <image> python run_top5.py` etc.
CMD ["python", "run.py"]