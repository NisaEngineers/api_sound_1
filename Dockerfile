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

# Explicitly download required Spleeter models
RUN python3 -m spleeter.download --model_name 4stems --output_dir ./pretrained_models
RUN python3 -m spleeter.download --model_name 2stems --output_dir ./pretrained_models

# Copy rest of the app
COPY . .

# Expose API port
EXPOSE 8000

# Start FastAPI with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
