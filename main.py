import os
import imageio_ffmpeg as _ffmpeg
import logging
from pydub import AudioSegment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Attempt to use bundled ffmpeg, fall back to system ffmpeg if unavailable
try:
    _ffmpeg_path = _ffmpeg.get_ffmpeg_exe()
    if os.path.exists(_ffmpeg_path):
        _ffmpeg_dir = os.path.dirname(_ffmpeg_path)
        os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        os.environ["FFMPEG_BINARY"] = _ffmpeg_path
        os.environ["FFMPEG_PATH"] = _ffmpeg_path
        AudioSegment.converter = _ffmpeg_path
        logger.info(f"Using bundled ffmpeg from imageio-ffmpeg at: {_ffmpeg_path}")
    else:
        logger.warning("Bundled ffmpeg not found, relying on system ffmpeg")
except Exception as e:
    logger.warning(f"Error accessing bundled ffmpeg: {e}, relying on system ffmpeg")

# Rest of your code...

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

import os
import logging
from typing import List


# ← end of insertion ←

app = FastAPI()



# Use the current working directory as the home directory.
HOME_DIR = os.getcwd()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_directory_exists(directory: str):
    """Creates a directory if it doesn't exist."""
    if not os.path.exists(directory):
        os.makedirs(directory)

def process_audio(file_path: str, task: str) -> List[str]:
    """
    Processes the given audio file based on the selected task.
    The output files are generated inside predetermined locations:
    
    • For "Vocal Remove": files go to HOME_DIR/vocal_remover/<file_basename>/  
      (expected outputs: vocals.wav, accompaniment.wav)
    
    • For "Basic Split": basic splitter outputs to HOME_DIR/basic_splits/<file_basename>/  
      and a separate call to the vocal remover creates vocals in HOME_DIR/vocal_remover/<file_basename>/  
      (expected outputs: vocals.wav, other.wav, bass.wav, drums.wav)
    
    • For "Advanced Split": files go to HOME_DIR/advance_splits/<file_basename>/  
      (expected outputs: vocals.wav, other.wav, bass.wav, drums.wav, piano.wav)
    """
    # Always start in the home directory.
    os.chdir(HOME_DIR)
    file_basename = os.path.splitext(os.path.basename(file_path))[0]

    if task == "Vocal Remove":
        # Set and ensure target folder under HOME_DIR/vocal_remover.
        target_dir = os.path.join(HOME_DIR, "vocal_remover")
        ensure_directory_exists(target_dir)
        original_dir = os.getcwd()
        os.chdir(target_dir)
        
        # Run the vocal remover; it should create a folder named file_basename under 'vocal_remover'
        from moonarch_vocal_remover import VocalRemover
        vocal_remover_instance = VocalRemover(file_path)
        vocal_remover_instance.run()
        
        os.chdir(original_dir)
        
        # Return the relative paths (from HOME_DIR) to the generated files.
        #relative_vocals = os.path.join("vocal_remover", file_basename, "vocals.wav")
        #relative_accompaniment = os.path.join("vocal_remover", file_basename, "accompaniment.wav")
        relative_vocals = os.path.join("vocal_remover", file_basename, "vocals.wav").replace("\\", "/")
        relative_accompaniment = os.path.join("vocal_remover", file_basename, "accompaniment.wav").replace("\\", "/")
        logger.info(f"Processed files: {relative_vocals}, {relative_accompaniment}")
        return [relative_vocals, relative_accompaniment]

    elif task == "Basic Split":
        # Run the basic splitter in its dedicated directory.
        target_dir_basic = os.path.join(HOME_DIR, "basic_splits")
        ensure_directory_exists(target_dir_basic)
        original_dir = os.getcwd()
        os.chdir(target_dir_basic)
        
        from moonarch_basic import BasicSplitter
        splitter = BasicSplitter(file_path)
        splitter.run()
        
        os.chdir(original_dir)
        logger.info("Basic split process completed.")
        
        # Now run Vocal Remover (for vocals only) in its dedicated directory.
        target_dir_vocal = os.path.join(HOME_DIR, "vocal_remover")
        ensure_directory_exists(target_dir_vocal)
        original_dir = os.getcwd()
        os.chdir(target_dir_vocal)
        
        from moonarch_vocal_remover import VocalRemover
        music_sep = VocalRemover(file_path)
        music_sep.run()
        
        os.chdir(original_dir)
        logger.info("Vocal remover process completed for Basic Split.")
        
        return [
            os.path.join("vocal_remover", file_basename, "vocals.wav"),
            os.path.join("basic_splits", file_basename, "other.wav"),
            os.path.join("basic_splits", file_basename, "bass.wav"),
            os.path.join("basic_splits", file_basename, "drums.wav")
        ]
    
  

@app.post("/process-audio/")
async def process_audio_endpoint(task: str = Form(...), audio_file: UploadFile = File(...)):
    """
    Endpoint to process an uploaded audio file.
    
    Form parameters:
      - task: one of "Vocal Remove", "Basic Split", or "Advanced Split"
      - audio_file: the audio file to be processed
    
    Returns:
      - A JSON with a message and the relative paths to the generated files.
    """
    try:
        # Save the uploaded file in the HOME_DIR with its original name.
        file_path = os.path.join(HOME_DIR, audio_file.filename)
        with open(file_path, "wb") as f:
            f.write(await audio_file.read())
        logger.info(f"Saved uploaded file at: {file_path}")
        
        # Process the file with the chosen task.
        output_files = process_audio(file_path, task)
        return {"message": "Audio processed successfully!", "output_files": output_files}
    
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{full_path:path}")
async def download_file(full_path: str):
    """
    Download a processed file by specifying its relative path.
    Acceptable paths must begin with one of these directories:
      - vocal_remover
      - basic_splits
      - advance_splits
  
    Example:
      /download/vocal_remover/audio_example/vocals.wav
    """
    valid_prefixes = ("vocal_remover", "basic_splits")

    if not full_path.startswith(valid_prefixes):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    file_path = os.path.join(HOME_DIR, full_path)
    logger.info(f"Attempting to download file: {file_path}")
    
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        logger.error("File not found")
        raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
