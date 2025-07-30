from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

import os
import logging
import pathlib

app = FastAPI()

# Enable CORS for all origins (development only)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set the working directory
HOME_DIR = str(pathlib.Path(__file__).parent.resolve())

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_directory_exists(directory: str):
    os.makedirs(directory, exist_ok=True)

def normalize_path(path: str) -> str:
    return path.replace("\\", "/")

def perform_vocal_removal(file_path: str) -> list:
    file_basename = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.join(HOME_DIR, "vocal_remover")
    ensure_directory_exists(output_dir)
    
    # Change to output dir before running
    os.chdir(output_dir)

    from moonarch_vocal_remover import VocalRemover
    VocalRemover(file_path).run()

    # Return relative output paths
    return [
        normalize_path(os.path.join("vocal_remover", file_basename, "vocals.wav")),
        normalize_path(os.path.join("vocal_remover", file_basename, "accompaniment.wav")),
    ]

@app.post("/process-audio/")
async def process_audio(audio_file: UploadFile = File(...)):
    """
    Accepts an uploaded audio file and performs vocal removal.
    """
    try:
        file_path = os.path.join(HOME_DIR, audio_file.filename)
        with open(file_path, "wb") as f:
            f.write(await audio_file.read())

        logger.info(f"File uploaded: {file_path}")
        output_files = perform_vocal_removal(file_path)

        return {
            "message": "Vocal removal completed successfully!",
            "output_files": output_files
        }

    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{full_path:path}")
async def download_file(full_path: str):
    """
    Downloads a processed file from vocal_remover directory.
    """
    if not full_path.startswith("vocal_remover"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    abs_path = os.path.join(HOME_DIR, full_path)
    if os.path.isfile(abs_path):
        return FileResponse(abs_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
