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
RUN wget https://github.com/deezer/spleeter/raw/master/audio_example.mp3
RUN spleeter separate -p spleeter:2stems -o output audio_example.mp3
RUN spleeter separate -p spleeter:4stems -o output audio_example.mp3

# Copy app code
COPY . .

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
