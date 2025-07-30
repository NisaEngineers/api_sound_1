from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from spleeter.separator import Separator
import os
import logging
import pathlib

# FastAPI app
app = FastAPI()

# Enable CORS (allow all for development)
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

# Utility
def ensure_directory_exists(directory: str):
    os.makedirs(directory, exist_ok=True)

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
        print("Separation completed")

# === API Endpoints ===

@app.post("/process-audio/")
async def process_audio(audio_file: UploadFile = File(...)):
    """
    Accepts uploaded audio file and performs vocal removal.
    """
    try:
        file_path = os.path.join(HOME_DIR, audio_file.filename)
        with open(file_path, "wb") as f:
            f.write(await audio_file.read())

        logger.info(f"Uploaded file saved at: {file_path}")

        # Run embedded vocal remover
        remover = VocalRemover(file_path)
        remover.run()

        file_basename = os.path.splitext(os.path.basename(file_path))[0]
        return {
            "message": "Vocal removal completed successfully!",
            "output_files": [
                normalize_path(os.path.join("vocal_remover", file_basename, "vocals.wav")),
                normalize_path(os.path.join("vocal_remover", file_basename, "accompaniment.wav"))
            ]
        }

    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{full_path:path}")
async def download_file(full_path: str):
    """
    Download a file only if it resides in vocal_remover/ folder.
    """
    if not full_path.startswith("vocal_remover"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    abs_path = os.path.join(HOME_DIR, full_path)
    if os.path.isfile(abs_path):
        return FileResponse(abs_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")

# Uvicorn entrypoint
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
