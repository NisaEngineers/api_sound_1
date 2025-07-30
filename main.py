from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import status
import uuid
import shutil

from spleeter.separator import Separator
import os
import logging
import pathlib

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

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track processing status
processing_status = {}

# Utility to normalize Windows paths
def normalize_path(path: str) -> str:
    return path.replace("\\", "/")

def process_audio_background(file_path: str, task_id: str):
    try:
        basename = os.path.splitext(os.path.basename(file_path))[0]
        safe_basename = basename.lower()
        
        # Create separator and process audio
        separator = Separator("spleeter:2stems")
        separator.separate_to_file(file_path, OUTPUT_BASE)
        
        # Handle case sensitivity by renaming to lowercase
        original_dir = os.path.join(OUTPUT_BASE, basename)
        safe_dir = os.path.join(OUTPUT_BASE, safe_basename)
        
        # Only rename if necessary (Linux case sensitivity)
        if os.path.exists(original_dir) and original_dir != safe_dir:
            if os.path.exists(safe_dir):
                shutil.rmtree(safe_dir)
            os.rename(original_dir, safe_dir)
            logger.info(f"Renamed {original_dir} to {safe_dir} for case consistency")
        
        # Update status
        processing_status[task_id] = {
            "status": "completed",
            "downloads": {
                "vocals": f"output/{safe_basename}/vocals.wav",
                "accompaniment": f"output/{safe_basename}/accompaniment.wav"
            }
        }
        logger.info(f"Processing completed for task {task_id}")
        
        # Clean up uploaded file
        try:
            os.remove(file_path)
            logger.info(f"Removed source file: {file_path}")
        except Exception as clean_error:
            logger.error(f"Error cleaning file {file_path}: {clean_error}")
            
    except Exception as e:
        logger.exception(f"Background processing failed: {e}")
        processing_status[task_id] = {
            "status": "error",
            "message": str(e)
        }

@app.post("/process-audio/")
async def process_audio(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
):
    """
    1. Save uploaded file
    2. Launch background task
    3. Return task ID for status tracking
    """
    try:
        # Create upload directory if needed
        os.makedirs(HOME_DIR, exist_ok=True)
        
        # Save uploaded file
        file_path = os.path.join(HOME_DIR, audio_file.filename)
        with open(file_path, "wb") as f:
            f.write(await audio_file.read())
        logger.info(f"Saved upload: {file_path}")
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        basename = os.path.splitext(audio_file.filename)[0]
        safe_basename = basename.lower()
        
        # Initialize status
        processing_status[task_id] = {
            "status": "processing",
            "basename": basename,
            "safe_basename": safe_basename
        }
        
        # Start background processing
        background_tasks.add_task(
            process_audio_background, 
            file_path, 
            task_id
        )

        return {
            "message": "Audio processing started",
            "task_id": task_id,
            "status_url": f"/status/{task_id}",
            "expected_paths": {
                "vocals": f"output/{safe_basename}/vocals.wav",
                "accompaniment": f"output/{safe_basename}/accompaniment.wav"
            }
        }

    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{task_id}")
def get_status(task_id: str):
    """Check processing status"""
    status_info = processing_status.get(task_id)
    if not status_info:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    
    return status_info

@app.get("/download/{full_path:path}")
async def download_file(full_path: str):
    """
    Serve files from the output/ directory with case insensitivity
    """
    # Normalize path and ensure it's under output/
    normalized = normalize_path(full_path).lower()
    if not normalized.startswith("output/"):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    # Resolve actual path
    parts = normalized.split("/")
    actual_path = os.path.join(OUTPUT_BASE, *parts[1:])
    
    # Case-insensitive file search
    if not os.path.exists(actual_path):
        # Try to find case-insensitive match
        dir_path = os.path.dirname(actual_path)
        file_name = os.path.basename(actual_path)
        
        if os.path.exists(dir_path):
            for f in os.listdir(dir_path):
                if f.lower() == file_name.lower():
                    actual_path = os.path.join(dir_path, f)
                    break
    
    # Final existence check
    if os.path.isfile(actual_path):
        return FileResponse(actual_path)
    
    logger.error(f"File not found: {full_path} (resolved: {actual_path})")
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/ping")
def ping():
    return {"status": "alive"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001)
