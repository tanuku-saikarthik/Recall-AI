import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional

from search import Searcher
from indexer import Indexer
from db import DatabaseManager
from watcher import BackgroundWatcher
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="File Retrieval Assistant API")

# Initialize backend instances
db = DatabaseManager()
searcher = Searcher(db)
indexer = Indexer(db)
watcher = BackgroundWatcher(indexer)

@app.on_event("startup")
def startup_event():
    logger.info("Starting background watcher...")
    watcher.start()

@app.on_event("shutdown")
def shutdown_event():
    logger.info("Stopping background watcher...")
    watcher.stop()

class FolderRequest(BaseModel):
    path: str

@app.get("/api/search")
def search_api(q: str, top_k: int = 5):
    """Semantic search across indexed files."""
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        results = searcher.search(q, top_k=top_k)
        # Results are dictionaries, as returned by searcher.search()
        return [
            {
                "file_path": r['path'],
                "score": float(r['score']),
                "page": r['page'],
                "preview": r['chunk_text'],
                "recency_boost": 0.0 # Placeholder since it's applied in score
            }
            for r in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/folders")
def get_folders():
    """Get list of watched folders."""
    cursor = db.conn.cursor()
    cursor.execute("SELECT id, path, added_on FROM WatchedFolders")
    folders = cursor.fetchall()
    return [{"id": f[0], "path": f[1], "added_on": f[2]} for f in folders]

@app.post("/api/folders")
def add_folder(req: FolderRequest, background_tasks: BackgroundTasks):
    """Add a new folder to watch and auto-scan."""
    abs_path = os.path.abspath(req.path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=400, detail="Path does not exist")
        
    try:
        cursor = db.conn.cursor()
        default_ignore = "node_modules/,.git/,__pycache__/,venv/,.venv/,*.pyc,AppData/,$RECYCLE.BIN/,*.tmp,.*"
        from datetime import datetime
        cursor.execute("INSERT INTO WatchedFolders (path, ignore_patterns, added_on) VALUES (?, ?, ?)", 
                       (abs_path, default_ignore, datetime.now().isoformat()))
        db.conn.commit()
        
        # Dynamically add to live watcher
        ignore_list = [p.strip() for p in default_ignore.split(',') if p.strip()]
        watcher.watch_new_folder(abs_path, ignore_list)
        
        # Auto-trigger scan for this newly added folder
        def run_scan():
            indexer.scan_and_index()
            
        background_tasks.add_task(run_scan)
        
        return {"status": "success", "message": f"Added {abs_path} and started scan."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Folder might already exist: {e}")

@app.post("/api/scan")
def trigger_scan(background_tasks: BackgroundTasks):
    """Trigger a background scan of all watched folders."""
    def run_scan():
        indexer.scan_and_index()
    
    background_tasks.add_task(run_scan)
    return {"status": "success", "message": "Scan started in background"}

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_index():
    return FileResponse(os.path.join(static_dir, "index.html"))

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    load_dotenv()
    
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run("app:app", host=host, port=port, reload=True)
