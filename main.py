from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

import os
import logging
import pathlib
from typing import List

app = FastAPI()

# Enable CORS for all origins (development only)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use the current working directory as the base home directory
HOME_DIR = str(pathlib.Path(__file__).parent.resolve())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_directory_exists(directory: str):
    """Create a directory if it does not exist."""
    os.makedirs(directory, exist_ok=True)

def normalize_path(path: str) -> str:
    """Normalize file paths to use forward slashes."""
    return path.replace("\\", "/")

def process_audio(file_path: str, task: str) -> List[str]:
    os.chdir(HOME_DIR)
    file_basename = os.path.splitext(os.path.basename(file_path))[0]

    if task == "Vocal Remove":
        target_dir = os.path.join(HOME_DIR, "vocal_remover")
        ensure_directory_exists(target_dir)
        os.chdir(target_dir)

        from moonarch_vocal_remover import VocalRemover
        VocalRemover(file_path).run()
        os.chdir(HOME_DIR)

        return [
            normalize_path(os.path.join("vocal_remover", file_basename, "vocals.wav")),
            normalize_path(os.path.join("vocal_remover", file_basename, "accompaniment.wav"))
        ]

    elif task == "Basic Split":
        # 1. Basic split
        basic_dir = os.path.join(HOME_DIR, "basic_splits")
        ensure_directory_exists(basic_dir)
        os.chdir(basic_dir)

        from moonarch_basic import BasicSplitter
        BasicSplitter(file_path).run()
        os.chdir(HOME_DIR)

        # 2. Vocal remover
        vocal_dir = os.path.join(HOME_DIR, "vocal_remover")
        ensure_directory_exists(vocal_dir)
        os.chdir(vocal_dir)

        from moonarch_vocal_remover import VocalRemover
        VocalRemover(file_path).run()
        os.chdir(HOME_DIR)

        return [
            normalize_path(os.path.join("vocal_remover", file_basename, "vocals.wav")),
            normalize_path(os.path.join("basic_splits", file_basename, "other.wav")),
            normalize_path(os.path.join("basic_splits", file_basename, "bass.wav")),
            normalize_path(os.path.join("basic_splits", file_basename, "drums.wav")),
        ]

    else:
        raise HTTPException(status_code=400, detail="Unsupported task")

@app.post("/process-audio/")
async def process_audio_endpoint(task: str = Form(...), audio_file: UploadFile = File(...)):
    """
    Accepts an uploaded audio file and a processing task.
    Returns relative paths to the processed outputs.
    """
    try:
        file_path = os.path.join(HOME_DIR, audio_file.filename)
        with open(file_path, "wb") as f:
            f.write(await audio_file.read())

        logger.info(f"Uploaded file saved at: {file_path}")
        output_files = process_audio(file_path, task)
        return {"message": "Audio processed successfully!", "output_files": output_files}

    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{full_path:path}")
async def download_file(full_path: str):
    """
    Downloads a processed file. Path must start with valid prefix.
    """
    valid_prefixes = ("vocal_remover", "basic_splits", "advance_splits")
    if not full_path.startswith(valid_prefixes):
        raise HTTPException(status_code=400, detail="Invalid file path")

    abs_path = os.path.join(HOME_DIR, full_path)
    if os.path.isfile(abs_path):
        return FileResponse(abs_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
