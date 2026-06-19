FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required to build reportlab and other compiled packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libjpeg-dev \
        zlib1g-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libopenjp2-7-dev \
        libharfbuzz-dev \
        libfribidi-dev \
        pkg-config \
        libssl-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Directory for collected static files
RUN mkdir -p /vol/static
ENV STATIC_ROOT=/vol/static

EXPOSE 8000

# Default command: run migrations then start Gunicorn
CMD ["bash", "-lc", "python manage.py migrate --noinput && gunicorn mukono.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
