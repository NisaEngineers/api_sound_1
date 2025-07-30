FROM python:3.9

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Clean any old/corrupt models and prepare model directory
RUN rm -rf ./pretrained_models && mkdir -p ./pretrained_models

# ✅ Correct way to download models via CLI, not Python -m
RUN spleeter download --model_name 4stems --output_dir ./pretrained_models
RUN spleeter download --model_name 2stems --output_dir ./pretrained_models

# Copy app code
COPY . .

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
