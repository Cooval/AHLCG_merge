import os
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import gdown

# Konfiguracja ścieżki dla modułu lokalnego
import sys
sys.path.append(str(Path(__file__).parent.parent))

from card_merger import DeckMerger, CardError

app = FastAPI(title="AHLCG Merger API")

# Serwowanie plików frontendowych
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

@app.get("/")
async def read_index():
    return FileResponse(str(Path(__file__).parent / "static" / "index.html"))

def cleanup_temp_dir(temp_dir: str):
    """Asynchroniczne czyszczenie przestrzeni roboczej po zakończeniu zadania."""
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/api/merge/upload")
async def merge_upload(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """Endpoint przetwarzający wgrane pliki metodą drag&drop."""
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="Nie przesłano żadnych plików.")
        
    temp_dir = tempfile.mkdtemp(prefix="ahlcg_upload_")
    
    try:
        for uploaded_file in files:
            file_path = os.path.join(temp_dir, uploaded_file.filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(uploaded_file.file, f)
                
        output_pdf_path = os.path.join(temp_dir, "GotoweKarty.pdf")
        
        merger = DeckMerger(temp_dir)
        merger.parse_directory()
        
        if len(merger.cards) == 0:
            raise HTTPException(status_code=400, detail="W przesłanych plikach nie odnaleziono pasujących kart (upewnij się co do rozszerzeń .png oraz wzorca nazw).")
            
        stats = merger.generate_pdf(output_pdf_path, quiet=True)
        
        # Zaplanuj usunięcie folderu tuż po udanym zwrocie pliku użytkownikowi
        background_tasks.add_task(cleanup_temp_dir, temp_dir)
        
        return FileResponse(
            path=output_pdf_path,
            filename="Karty_Wygenerowane.pdf",
            media_type="application/pdf"
        )
        
    except CardError as e:
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=500, detail=f"Błąd wewnętrzny serwera: {str(e)}")


@app.post("/api/merge/gdrive")
async def merge_gdrive(background_tasks: BackgroundTasks, url: str = Form(...)):
    """Endpoint pobierający i przetwarzający pliki bezpośrednio ze wskazanego publicznego dysku Google."""
    if not url:
        raise HTTPException(status_code=400, detail="Nie podano poprawnego linku.")
        
    temp_dir = tempfile.mkdtemp(prefix="ahlcg_gdrive_")
    
    try:
        # use_cookies=False pomaga zablokować gdown przed problemami w czystych kontenerach dockera
        gdown.download_folder(url, output=temp_dir, quiet=True, use_cookies=False)
        
        # Wypłaszczenie struktury (wyciągnięcie plików z ewentualnych podfolderów na dysku google)
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith(".png"):
                    src = os.path.join(root, file)
                    dst = os.path.join(temp_dir, file)
                    if src != dst:
                        shutil.move(src, dst)
                        
        output_pdf_path = os.path.join(temp_dir, "GotoweKarty.pdf")
        
        merger = DeckMerger(temp_dir)
        merger.parse_directory()
        
        if len(merger.cards) == 0:
            raise HTTPException(
                status_code=400, 
                detail="W pobranym folderze nie odnaleziono prawidłowych plików graficznych (lub podany link na dysku Google nie jest folderem publicznym typu 'Każda osoba mająca link')."
            )
            
        stats = merger.generate_pdf(output_pdf_path, quiet=True)
        
        background_tasks.add_task(cleanup_temp_dir, temp_dir)
        
        return FileResponse(
            path=output_pdf_path,
            filename="Karty_GoogleDrive.pdf",
            media_type="application/pdf"
        )
        
    except CardError as e:
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=400, detail=f"Wystąpił błąd pobierania (link GDrive jest wadliwy lub prywatny): {str(e)}")
