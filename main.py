import os
import uuid
import shutil
import logging
import pathlib

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from spleeter.separator import Separator

# Paths
HOME_DIR = pathlib.Path(__file__).parent.resolve()
OUTPUT_BASE = HOME_DIR / "output"

# Ensure that the output directory exists before mounting
os.makedirs(OUTPUT_BASE, exist_ok=True)

# FastAPI app
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static output directory at /app
app.mount(
    "/app",
    StaticFiles(directory=str(OUTPUT_BASE), html=False),
    name="output_files",
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In‐memory task status
processing_status = {}

def process_audio_background(file_path: str, task_id: str):
    try:
        basename = pathlib.Path(file_path).stem
        safe_basename = basename.lower()

        # Separate stems
        separator = Separator("spleeter:2stems")
        separator.separate_to_file(file_path, str(OUTPUT_BASE))

        # Rename output folder to lowercase (if needed)
        orig_dir = OUTPUT_BASE / basename
        safe_dir = OUTPUT_BASE / safe_basename
        if orig_dir.exists() and orig_dir != safe_dir:
            if safe_dir.exists():
                shutil.rmtree(safe_dir)
            orig_dir.rename(safe_dir)
            logger.info(f"Renamed {orig_dir} → {safe_dir}")

        # Mark complete
        processing_status[task_id] = {
            "status": "completed",
            "downloads": {
                "vocals": f"{safe_basename}/vocals.wav",
                "accompaniment": f"{safe_basename}/accompaniment.wav",
            },
        }
        logger.info(f"Task {task_id} completed")

        # Clean up original upload
        try:
            os.remove(file_path)
            logger.info(f"Removed upload: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error for {file_path}: {e}")

    except Exception as e:
        logger.exception(f"Background processing failed ({task_id}): {e}")
        processing_status[task_id] = {"status": "error", "message": str(e)}

@app.post("/process-audio/")
async def process_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
):
    """Save upload, kick off Spleeter in background, return task + URLs."""
    try:
        # Save upload to disk
        upload_path = HOME_DIR / audio_file.filename
        with open(upload_path, "wb") as f:
            f.write(await audio_file.read())
        logger.info(f"Saved upload to {upload_path}")

        # Create task record
        task_id = str(uuid.uuid4())
        basename = pathlib.Path(audio_file.filename).stem
        safe_basename = basename.lower()
        processing_status[task_id] = {
            "status": "processing",
            "basename": basename,
            "safe_basename": safe_basename,
        }

        # Launch background processing
        background_tasks.add_task(str(process_audio_background), str(upload_path), task_id)

        # Build absolute URLs
        status_url = request.url_for("get_status", task_id=task_id)
        vocals_url = request.url_for(
            "output_files", path=f"{safe_basename}/vocals.wav"
        )
        accomp_url = request.url_for(
            "output_files", path=f"{safe_basename}/accompaniment.wav"
        )

        return {
            "message": "Processing started",
            "task_id": task_id,
            "status_url": status_url,
            "downloads": {"vocals": vocals_url, "accompaniment": accomp_url},
        }

    except Exception as e:
        logger.error(f"/process-audio error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{task_id}")
def get_status(task_id: str):
    """Check background‐job status."""
    info = processing_status.get(task_id)
    if not info:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return info

@app.get("/ping")
def ping():
    return {"status": "alive"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001)
