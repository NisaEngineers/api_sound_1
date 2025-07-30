from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

import uuid
import shutil
import os
import logging
import pathlib

from spleeter.separator import Separator

# FastAPI app
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
HOME_DIR = str(pathlib.Path(__file__).parent.resolve())
OUTPUT_BASE = os.path.join(HOME_DIR, "output")

# Mount static files under /app
app.mount(
    "/app",
    StaticFiles(directory=OUTPUT_BASE, html=False),
    name="output_files"
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track processing status
processing_status = {}

def process_audio_background(file_path: str, task_id: str):
    try:
        basename = os.path.splitext(os.path.basename(file_path))[0]
        safe_basename = basename.lower()

        # Separate stems
        separator = Separator("spleeter:2stems")
        separator.separate_to_file(file_path, OUTPUT_BASE)

        # Rename output dir to lowercase if needed
        original_dir = os.path.join(OUTPUT_BASE, basename)
        safe_dir = os.path.join(OUTPUT_BASE, safe_basename)
        if os.path.exists(original_dir) and original_dir != safe_dir:
            if os.path.exists(safe_dir):
                shutil.rmtree(safe_dir)
            os.rename(original_dir, safe_dir)
            logger.info(f"Renamed {original_dir} → {safe_dir}")

        # Update status
        processing_status[task_id] = {
            "status": "completed",
            "downloads": {
                "vocals": f"{safe_basename}/vocals.wav",
                "accompaniment": f"{safe_basename}/accompaniment.wav"
            }
        }
        logger.info(f"Task {task_id} completed")

        # Remove source file
        try:
            os.remove(file_path)
            logger.info(f"Removed uploaded file: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup failed for {file_path}: {e}")

    except Exception as e:
        logger.exception(f"Background processing failed for {task_id}: {e}")
        processing_status[task_id] = {
            "status": "error",
            "message": str(e)
        }

@app.post("/process-audio/")
async def process_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...)
):
    """
    1. Save uploaded file
    2. Start background processing
    3. Return task ID + URLs for status and downloads
    """
    try:
        os.makedirs(HOME_DIR, exist_ok=True)
        upload_path = os.path.join(HOME_DIR, audio_file.filename)
        with open(upload_path, "wb") as f:
            f.write(await audio_file.read())
        logger.info(f"Saved upload: {upload_path}")

        task_id = str(uuid.uuid4())
        basename = os.path.splitext(audio_file.filename)[0]
        safe_basename = basename.lower()
        processing_status[task_id] = {
            "status": "processing",
            "basename": basename,
            "safe_basename": safe_basename
        }

        background_tasks.add_task(
            process_audio_background,
            upload_path,
            task_id
        )

        # Build absolute URLs
        status_url = request.url_for("get_status", task_id=task_id)
        download_vocals = request.url_for(
            "output_files",
            path=f"{safe_basename}/vocals.wav"
        )
        download_accomp = request.url_for(
            "output_files",
            path=f"{safe_basename}/accompaniment.wav"
        )

        return {
            "message": "Audio processing started",
            "task_id": task_id,
            "status_url": status_url,
            "downloads": {
                "vocals": download_vocals,
                "accompaniment": download_accomp
            }
        }

    except Exception as e:
        logger.error(f"Error in /process-audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{task_id}")
def get_status(task_id: str):
    """Retrieve processing status for a given task"""
    status_info = processing_status.get(task_id)
    if not status_info:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return status_info

@app.get("/ping")
def ping():
    return {"status": "alive"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001)
