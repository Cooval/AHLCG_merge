import os
import shutil
import tempfile
import zipfile
import threading
import queue
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import gdown

class ResolutionRequest(BaseModel):
    selected_back: str | None = None
    alt_keeps: List[str] = []
    old_keeps: List[str] = []
    unmatched_keeps: List[str] = []

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

# Helper function to generate PDF in a thread and send SSE events
def generate_pdf_thread(temp_dir: str, q: queue.Queue):
    try:
        q.put("Parsing directory...")
        merger = DeckMerger(temp_dir)
        merger.parse_directory()
        
        if len(merger.cards) == 0:
            q.put("ERROR: No matching cards found in uploaded files (check .png extensions and naming patterns).")
            return
            
        q.put(f"Found {len(merger.cards)} unique cards.")
        
        output_pdf_path = os.path.join(temp_dir, "Ready_Cards.pdf")
        
        def sse_callback(msg: str):
            q.put(msg)
            
        stats = merger.generate_pdf(output_pdf_path, quiet=False, callback=sse_callback)
        q.put("DONE")
        
    except Exception as e:
        q.put(f"ERROR: {str(e)}")

# Generator for SSE
def sse_generator(temp_dir: str):
    q = queue.Queue()
    thread = threading.Thread(target=generate_pdf_thread, args=(temp_dir, q))
    thread.start()
    
    while True:
        msg = q.get()
        if msg.startswith("ERROR:"):
            yield f"data: {msg}\n\n"
            break
        elif msg == "DONE":
            yield f"data: DONE\n\n"
            break
        else:
            yield f"data: {msg}\n\n"
            
    thread.join()

@app.post("/api/merge/upload")
async def merge_upload(files: List[UploadFile] = File(...)):
    """Endpoint processing uploaded files via drag&drop. Returns job_id for SSE."""
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files uploaded.")
        
    temp_dir = tempfile.mkdtemp(prefix="ahlcg_upload_")
    
    try:
        for uploaded_file in files:
            file_path = os.path.join(temp_dir, uploaded_file.filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(uploaded_file.file, f)
            
            # If the uploaded file is a ZIP, extract it immediately and delete the archive
            if uploaded_file.filename.lower().endswith(".zip"):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                os.remove(file_path)
                
        # Flatten the directory structure (pull files out of potential subfolders inside the ZIP)
        for root, dirs, extracted_files in os.walk(temp_dir):
            for file in extracted_files:
                if file.lower().endswith(".png"):
                    src = os.path.join(root, file)
                    dst = os.path.join(temp_dir, file)
                    if src != dst:
                        shutil.move(src, dst)
                        
        merger = DeckMerger(temp_dir)
        merger.parse_directory()
        
        conflicts = merger.get_conflicts()
        needs_back = merger.needs_global_back() and not merger.global_back
        back_candidates = merger.get_back_candidates() if needs_back else []
        
        if conflicts or needs_back:
            return {
                "job_id": os.path.basename(temp_dir),
                "status": "needs_resolution",
                "needs_back": needs_back,
                "back_candidates": back_candidates,
                "conflicts": conflicts
            }
            
        return {"job_id": os.path.basename(temp_dir), "status": "ready"}
        
    except Exception as e:
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.post("/api/merge/gdrive")
async def merge_gdrive(url: str = Form(...)):
    """Endpoint downloading files directly from a public Google Drive link. Returns job_id for SSE."""
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
                        
        merger = DeckMerger(temp_dir)
        merger.parse_directory()
        
        conflicts = merger.get_conflicts()
        needs_back = merger.needs_global_back() and not merger.global_back
        back_candidates = merger.get_back_candidates() if needs_back else []
        
        if conflicts or needs_back:
            return {
                "job_id": os.path.basename(temp_dir),
                "status": "needs_resolution",
                "needs_back": needs_back,
                "back_candidates": back_candidates,
                "conflicts": conflicts
            }
            
        return {"job_id": os.path.basename(temp_dir), "status": "ready"}
        
    except Exception as e:
        cleanup_temp_dir(temp_dir)
        error_msg = str(e)
        if "more than 50 files" in error_msg:
            raise HTTPException(status_code=400, detail="Google Drive public folder block: gdown can't download more than 50 files. Please download the folder as a ZIP file directly from Google Drive and upload it in the 'Upload from Disk' tab.")
        raise HTTPException(status_code=400, detail=f"Download error occurred (GDrive link is faulty or private): {error_msg}")


@app.get("/api/merge/process/{job_id}")
async def merge_process(job_id: str):
    """SSE endpoint for streaming processing progress."""
    temp_dir = os.path.join(tempfile.gettempdir(), job_id)
    if not os.path.exists(temp_dir):
        raise HTTPException(status_code=404, detail="Job ID not found")
        
    return StreamingResponse(sse_generator(temp_dir), media_type="text/event-stream")


@app.get("/api/merge/download/{job_id}")
async def merge_download(job_id: str, background_tasks: BackgroundTasks):
    """Endpoint to download the finished PDF."""
    temp_dir = os.path.join(tempfile.gettempdir(), job_id)
    output_pdf_path = os.path.join(temp_dir, "Ready_Cards.pdf")
    
    if not os.path.exists(output_pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found or not generated yet")
        
    background_tasks.add_task(cleanup_temp_dir, temp_dir)
    
    return FileResponse(
        path=output_pdf_path,
        filename="Ready_Cards.pdf",
        media_type="application/pdf"
    )

@app.get("/api/merge/preview/{job_id}/{filename}")
async def merge_preview(job_id: str, filename: str):
    """Endpoint to fetch a thumbnail of a candidate card back."""
    temp_dir = os.path.join(tempfile.gettempdir(), job_id)
    file_path = os.path.join(temp_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")
        
    return FileResponse(path=file_path)

@app.post("/api/merge/resolve_conflicts/{job_id}")
async def merge_resolve_conflicts(job_id: str, request: ResolutionRequest):
    """Endpoint handling all user resolutions from the UI."""
    temp_dir = os.path.join(tempfile.gettempdir(), job_id)
    if not os.path.exists(temp_dir):
        raise HTTPException(status_code=404, detail="Job ID not found")
        
    merger = DeckMerger(temp_dir)
    merger.parse_directory()
    
    # Resolve global back
    if request.selected_back:
        file_path = os.path.join(temp_dir, request.selected_back)
        if os.path.exists(file_path):
            dest_path = os.path.join(temp_dir, "back.png")
            shutil.move(file_path, dest_path)
            
    # Resolve alt conflicts
    # We must delete the files of cards that share an alt norm group but were not selected in alt_keeps
    from collections import defaultdict
    import re
    groups = defaultdict(list)
    for base_name, card in merger.cards.items():
        norm = re.sub(r'(?i)alt', '', base_name)
        norm = re.sub(r'\s*\((?![0-9]+\)).*?\)', '', norm).strip()
        groups[norm].append(card)
        
    for norm, cards in groups.items():
        if len(cards) > 1:
            for c in cards:
                if c.base_name not in request.alt_keeps:
                    if c.front_path and os.path.exists(c.front_path):
                        os.remove(c.front_path)
                    if c.back_path and os.path.exists(c.back_path):
                        os.remove(c.back_path)
                        
    # Resolve skipped OLD
    for p in merger.skipped_old:
        if p.name in request.old_keeps:
            import re
            # Safely remove -OLD- or -old- without destroying adjacent hyphens
            new_name = re.sub(r'(?i)-old(-?)', r'\1', p.name)
            
            # Ensure the new name actually matches the card pattern with a valid side_flag
            match = merger.FILENAME_PATTERN.match(new_name)
            valid = False
            if match:
                side_flag = match.group(3)
                if side_flag and side_flag.lower() in (merger.FRONT_FLAGS | merger.BACK_FLAGS):
                    valid = True
                    
            if not valid:
                new_name = new_name[:-4] + "-a.png"
                
            shutil.move(str(p), os.path.join(temp_dir, new_name))
        else:
            if p.exists():
                os.remove(str(p))
                
    # Resolve unmatched
    for p in merger.skipped_unmatched:
        if p.name in request.unmatched_keeps:
            # append -a.png to force treating it as a front side
            new_name = p.name[:-4] + "-a.png"
            shutil.move(str(p), os.path.join(temp_dir, new_name))
        else:
            if p.exists():
                os.remove(str(p))

    return {"status": "success"}
