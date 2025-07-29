FROM python:3.9.21-slim-bullseye

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# First install numpy separately to prevent conflicts
RUN pip install --no-cache-dir numpy==1.26.4

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Clean up build artifacts
RUN find /usr/local/lib/python3.9 -type d -name '__pycache__' -exec rm -rf {} + && \
    find /usr/local/lib/python3.9 -name '*.pyc' -delete

COPY . .

ENV HOME_DIR=/app
ENV PYTHONUNBUFFERED=1
ENV TF_CPP_MIN_LOG_LEVEL=2  # Reduce TensorFlow logging

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
