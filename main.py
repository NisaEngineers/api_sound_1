import os
import uuid
import shutil
import logging
import pathlib
import json
import tempfile
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from spleeter.separator import Separator

# Paths
HOME_DIR = pathlib.Path(__file__).parent.resolve()
OUTPUT_BASE = HOME_DIR / "output"
AUDIO_OUTPUT_DIR = OUTPUT_BASE / "audio"
TASK_STATUS_DIR = OUTPUT_BASE / "task_status"

# Ensure directories exist
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)
os.makedirs(TASK_STATUS_DIR, exist_ok=True)

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
    StaticFiles(directory=str(AUDIO_OUTPUT_DIR), html=False),
    name="output_files",
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_audio_background(file_path: str, task_id: str):
    """Run Spleeter and organize outputs, then clean up"""
    status_file = TASK_STATUS_DIR / f"{task_id}.json"
    task_audio_dir = AUDIO_OUTPUT_DIR / task_id
    
    try:
        # Create task output directory
        os.makedirs(task_audio_dir, exist_ok=True)
        
        # Update status
        with open(status_file, "r+") as f:
            status_data = json.load(f)
            status_data["status"] = "processing"
            status_data["started_at"] = datetime.utcnow().isoformat()
            f.seek(0)
            json.dump(status_data, f)
            f.truncate()

        # Separate stems
        separator = Separator("spleeter:2stems")
        separator.separate_to_file(
            file_path,
            str(task_audio_dir),
            filename_format='{instrument}.wav'
        )

        # Final status update
        with open(status_file, "r+") as f:
            status_data = json.load(f)
            status_data["status"] = "completed"
            status_data["completed_at"] = datetime.utcnow().isoformat()
            status_data["stems"] = {
                "vocals": f"{task_id}/vocals.wav",
                "accompaniment": f"{task_id}/accompaniment.wav"
            }
            f.seek(0)
            json.dump(status_data, f)
            f.truncate()

        logger.info(f"Task {task_id} completed")

    except Exception as e:
        # Error handling
        logger.exception(f"Background processing failed: {e}")
        with open(status_file, "r+") as f:
            status_data = json.load(f)
            status_data["status"] = "error"
            status_data["error"] = str(e)
            status_data["completed_at"] = datetime.utcnow().isoformat()
            f.seek(0)
            json.dump(status_data, f)
            f.truncate()
    finally:
        # Cleanup original upload
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed upload: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

@app.post("/process-audio/")
async def process_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
):
    """Process audio file and start background separation"""
    try:
        # Save uploaded file
        file_ext = pathlib.Path(audio_file.filename).suffix
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=file_ext,
            dir=HOME_DIR
        )
        await audio_file.seek(0)
        content = await audio_file.read()
        temp_file.write(content)
        temp_file.close()
        
        # Create task
        task_id = str(uuid.uuid4())
        status_data = {
            "status": "pending",
            "task_id": task_id,
            "created_at": datetime.utcnow().isoformat(),
            "filename": audio_file.filename
        }
        
        # Save initial status
        status_file = TASK_STATUS_DIR / f"{task_id}.json"
        with open(status_file, "w") as f:
            json.dump(status_data, f)

        # Start processing
        background_tasks.add_task(
            process_audio_background, 
            temp_file.name, 
            task_id
        )

        # Build response URLs
        return {
            "message": "Processing started",
            "task_id": task_id,
            "status_url": str(request.url_for("get_status", task_id=task_id)),
            "downloads": {
                "vocals": str(request.url_for("output_files", path=f"{task_id}/vocals.wav")),
                "accompaniment": str(request.url_for("output_files", path=f"{task_id}/accompaniment.wav")),
                "all": str(request.url_for("download_all", task_id=task_id)),
            }
        }

    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(500, detail=str(e))

@app.get("/status/{task_id}")
def get_status(task_id: str):
    """Check processing status"""
    status_file = TASK_STATUS_DIR / f"{task_id}.json"
    if not status_file.exists():
        raise HTTPException(404, "Task not found")
    
    with open(status_file, "r") as f:
        return json.load(f)

@app.get("/download/{task_id}/all")
def download_all(task_id: str):
    """Download all stems as ZIP"""
    status_file = TASK_STATUS_DIR / f"{task_id}.json"
    if not status_file.exists():
        raise HTTPException(404, "Task not found")
    
    with open(status_file, "r") as f:
        status_data = json.load(f)
    
    if status_data["status"] != "completed":
        raise HTTPException(400, "Processing not completed")
    
    # Create temp ZIP
    task_dir = AUDIO_OUTPUT_DIR / task_id
    zip_path = shutil.make_archive(
        base_name=tempfile.mktemp(dir=HOME_DIR),
        format="zip",
        root_dir=task_dir
    )
    
    # Stream ZIP response
    return FileResponse(
        zip_path,
        filename=f"{task_id}_stems.zip",
        media_type="application/zip",
        background=BackgroundTask(lambda: os.remove(zip_path))
    )

@app.get("/ping")
def ping():
    return {"status": "alive"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001)
