#!/usr/bin/env python3
# api.py

import os
import logging
import nest_asyncio
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Ngrok & Uvicorn for public URL
from pyngrok import ngrok
import uvicorn

app = FastAPI(title="Moonarch Audio Processing API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # Development only
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use current working directory
HOME_DIR = os.getcwd()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_directory_exists(directory: str):
    if not os.path.exists(directory):
        os.makedirs(directory)

def process_audio(file_path: str, task: str) -> List[str]:
    """
    Handles only 'Vocal Remove' and 'Basic Split' on the uploaded audio.
    Returns relative paths to the generated WAV files.
    """
    os.chdir(HOME_DIR)
    basename = os.path.splitext(os.path.basename(file_path))[0]

    if task == "Vocal Remove":
        target = os.path.join(HOME_DIR, "vocal_remover")
        ensure_directory_exists(target)
        os.chdir(target)

        from moonarch_vocal_remover import VocalRemover
        VocalRemover(file_path).run()

        os.chdir(HOME_DIR)
        return [
            os.path.join("vocal_remover", basename, "vocals.wav").replace("\\", "/"),
            os.path.join("vocal_remover", basename, "accompaniment.wav").replace("\\", "/")
        ]

    elif task == "Basic Split":
        # Basic stems
        basic_dir = os.path.join(HOME_DIR, "basic_splits")
        ensure_directory_exists(basic_dir)
        os.chdir(basic_dir)

        from moonarch_basic import BasicSplitter
        BasicSplitter(file_path).run()

        os.chdir(HOME_DIR)
        # Vocals only (same remover)
        vocal_dir = os.path.join(HOME_DIR, "vocal_remover")
        ensure_directory_exists(vocal_dir)
        os.chdir(vocal_dir)

        from moonarch_vocal_remover import VocalRemover
        VocalRemover(file_path).run()

        os.chdir(HOME_DIR)
        return [
            os.path.join("vocal_remover", basename, "vocals.wav").replace("\\", "/"),
            os.path.join("basic_splits", basename, "other.wav").replace("\\", "/"),
            os.path.join("basic_splits", basename, "bass.wav").replace("\\", "/"),
            os.path.join("basic_splits", basename, "drums.wav").replace("\\", "/")
        ]

    else:
        raise HTTPException(status_code=400, detail="Unsupported task. Choose 'Vocal Remove' or 'Basic Split'.")

@app.post("/process-audio/", summary="Upload audio and select task")
async def process_audio_endpoint(
    task: str = Form(..., description="Vocal Remove or Basic Split"),
    audio_file: UploadFile = File(...)
):
    # Save upload
    file_path = os.path.join(HOME_DIR, audio_file.filename)
    with open(file_path, "wb") as f:
        f.write(await audio_file.read())
    logger.info(f"Uploaded file saved at {file_path}")

    # Process and return relative paths
    output_files = process_audio(file_path, task)
    return {"message": "Audio processed!", "output_files": output_files}

@app.get("/download/{full_path:path}", summary="Download a processed file")
async def download_file(full_path: str):
    valid = ("vocal_remover", "basic_splits")
    if not full_path.startswith(valid):
        raise HTTPException(status_code=400, detail="Invalid download path")
    path = os.path.join(HOME_DIR, full_path)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)

if __name__ == "__main__":
    # Launch public tunnel
    ngrok.set_auth_token("2wKmWsoYf8sEyWc9Xvrs30VZQd0_896xEsTsATQtH6HYHeohY")
    port = 8000
    public_url = ngrok.connect(port)
    print(f"\n🚀 Public URL: {public_url.public_url}/process-audio/\n")

    nest_asyncio.apply()
    uvicorn.run(app, host="0.0.0.0", port=port)
