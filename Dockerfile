FROM python:3.9

RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add after installing requirements
# Force model download (as dummy run)
RUN python3 -m spleeter separate -i audio_example.mp3 -p spleeter:4stems -o output || true
RUN python3 -m spleeter separate -i audio_example.mp3 -p spleeter:2stems -o output || true
RUN rm -rf output


COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
