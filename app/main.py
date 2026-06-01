import os
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import gdown

# Configure path for local module
import sys
sys.path.append(str(Path(__file__).parent.parent))

from card_merger import DeckMerger, CardError

app = FastAPI(title="AHLCG Merger API")

# Serve frontend files
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

@app.get("/")
async def read_index():
    return FileResponse(str(Path(__file__).parent / "static" / "index.html"))

def cleanup_temp_dir(temp_dir: str):
    """Asynchronous cleanup of the workspace after task completion."""
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/api/merge/upload")
async def merge_upload(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """Endpoint processing uploaded files via drag&drop."""
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files uploaded.")
        
    temp_dir = tempfile.mkdtemp(prefix="ahlcg_upload_")
    
    try:
        for uploaded_file in files:
            file_path = os.path.join(temp_dir, uploaded_file.filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(uploaded_file.file, f)
                
        output_pdf_path = os.path.join(temp_dir, "Ready_Cards.pdf")
        
        merger = DeckMerger(temp_dir)
        merger.parse_directory()
        
        if len(merger.cards) == 0:
            raise HTTPException(status_code=400, detail="No matching cards found in uploaded files (check .png extensions and naming patterns).")
            
        stats = merger.generate_pdf(output_pdf_path, quiet=True)
        
        # Schedule folder removal right after successfully returning the file
        background_tasks.add_task(cleanup_temp_dir, temp_dir)
        
        return FileResponse(
            path=output_pdf_path,
            filename="Generated_Cards.pdf",
            media_type="application/pdf"
        )
        
    except CardError as e:
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.post("/api/merge/gdrive")
async def merge_gdrive(background_tasks: BackgroundTasks, url: str = Form(...)):
    """Endpoint downloading and processing files directly from a public Google Drive link."""
    if not url:
        raise HTTPException(status_code=400, detail="No valid link provided.")
        
    temp_dir = tempfile.mkdtemp(prefix="ahlcg_gdrive_")
    
    try:
        # use_cookies=False prevents gdown issues in clean docker containers
        gdown.download_folder(url, output=temp_dir, quiet=True, use_cookies=False)
        
        # Flatten the structure (extract files from possible subfolders on google drive)
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith(".png"):
                    src = os.path.join(root, file)
                    dst = os.path.join(temp_dir, file)
                    if src != dst:
                        shutil.move(src, dst)
                        
        output_pdf_path = os.path.join(temp_dir, "Ready_Cards.pdf")
        
        merger = DeckMerger(temp_dir)
        merger.parse_directory()
        
        if len(merger.cards) == 0:
            raise HTTPException(
                status_code=400, 
                detail="No valid image files found in the downloaded folder (or the Google Drive link is not a public 'Anyone with the link' folder)."
            )
            
        stats = merger.generate_pdf(output_pdf_path, quiet=True)
        
        background_tasks.add_task(cleanup_temp_dir, temp_dir)
        
        return FileResponse(
            path=output_pdf_path,
            filename="Cards_GoogleDrive.pdf",
            media_type="application/pdf"
        )
        
    except CardError as e:
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=400, detail=f"Download error occurred (GDrive link is faulty or private): {str(e)}")
