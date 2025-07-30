from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

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

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Utility Functions ===

def normalize_path(path: str) -> str:
    return path.replace("\\", "/")

# === Embedded VocalRemover Class ===

class VocalRemover:
    def __init__(self, input_path, task='spleeter:2stems'):
        self.input_path = input_path
        self.task = task
        self.separator = Separator(self.task)

    def separate_audio(self):
        output_path = os.path.join(HOME_DIR, "vocal_remover")
        os.makedirs(output_path, exist_ok=True)
        self.separator.separate_to_file(self.input_path, output_path)

    def run(self):
        self.separate_audio()
        logger.info("Separation completed")

# === API Endpoints ===

@app.post("/process-audio/")
async def process_audio(background_tasks: BackgroundTasks, audio_file: UploadFile = File(...)):
    """
    Accepts uploaded audio file and performs vocal removal in the background.
    """
    try:
        # Save uploaded file
        file_path = os.path.join(HOME_DIR, audio_file.filename)
        with open(file_path, "wb") as f:
            f.write(await audio_file.read())

        logger.info(f"Uploaded file saved at: {file_path}")

        # Start background task for vocal separation
        background_tasks.add_task(VocalRemover(file_path).run)

        # Build expected output paths
        file_basename = os.path.splitext(os.path.basename(file_path))[0]
        output_dir = normalize_path(os.path.join("vocal_remover", file_basename))

        return {
            "message": "File uploaded successfully. Vocal separation is running in the background.",
            "download_paths": [
                os.path.join(output_dir, "vocals.wav"),
                os.path.join(output_dir, "accompaniment.wav")
            ]
        }

    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{full_path:path}")
async def download_file(full_path: str):
    """
    Allows downloading processed files only from vocal_remover directory.
    """
    if not full_path.startswith("vocal_remover"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    abs_path = os.path.join(HOME_DIR, full_path)
    if os.path.isfile(abs_path):
        return FileResponse(abs_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.get("/ping")
def ping():
    return {"status": "alive"}

# Entrypoint
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
