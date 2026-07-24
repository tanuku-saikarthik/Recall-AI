# ✨ Personal File Retrieval Assistant

A lightning-fast, fully local, and highly aesthetic Semantic Search Engine for your personal files. This tool monitors your local directories, intelligently extracts text from various file formats, embeds them using a local AI model, and lets you query your documents conceptually rather than relying on exact keyword matches.

---

## 🚀 What's in this Codebase? (Version 1.0)

This repository contains a full-stack, local-first retrieval system built with Python, SQLite, FAISS, and FastAPI.

### Core Components
- **`app.py`**: The FastAPI backend server that exposes the search and folder management APIs, and serves the Web UI.
- **`main.py`**: A powerful Command-Line Interface (CLI) to manage folders, trigger manual scans, search, and run background watchers.
- **`db.py`**: The database layer. Manages a high-performance SQLite database (using WAL mode) for metadata and a dense FAISS vector index (`IndexIDMap`) for embeddings.
- **`indexer.py`**: The pipeline that calculates file hashes (to detect changes), chunks text into overlapping segments, and generates 384-dimensional semantic embeddings using `sentence-transformers`.
- **`extractors.py`**: The parser layer. Effortlessly extracts text from PDFs (`PyMuPDF`), Word Documents (`python-docx`), PowerPoints (`python-pptx`), Excel Sheets (`openpyxl`), and standard text/code files.
- **`search.py`**: The retrieval engine. It computes the semantic distance between your query and the indexed chunks, applying a recency boost to newer files.
- **`watcher.py`**: A background daemon (`watchdog`) that listens for filesystem events (creates, modifies, deletes) to keep your index perfectly in sync without manual rescans.
- **`static/`**: The modern Web UI frontend featuring a Glassmorphism dark-theme, dynamic animations, and real-time search result rendering using Vanilla HTML/CSS/JS.

---

## 💡 Quick Start

### 1. Setup from Scratch
If you are setting this up on a new laptop (or after deleting the folder), run these commands in Powershell:

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/tanuku-saikarthik/Recall-AI.git
   cd Recall-AI
   ```
2. **Create and activate a virtual environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
4. **Configure your environment:**
   ```powershell
   Copy-Item .env.example .env
   ```
   *(Optional: You can open `.env` in Notepad to change the web server port or max file limits).*

### 2. Run the App
The easiest and most beautiful way to interact with your data.
1. Start the server:
   ```powershell
   python -m uvicorn app:app --port 8000
   ```
2. Open your browser to `http://localhost:8000`.
3. Click the **⚙️ Settings** icon in the top right and add a local folder to your watch-list.
4. **Magic Sync:** The moment you add a folder, it automatically extracts, chunks, and embeds your files in the background! Furthermore, any future changes you make to files in those folders are synced in real-time.
5. Use the central search bar to ask conceptual questions (e.g., *"What were the budget constraints for the Q4 marketing campaign?"*).

### 2. The Command-Line Interface (CLI)
For power users who want to script or run things headless.

- **Add a directory to watch:**
  ```powershell
  python main.py add-folder "C:\Users\YourName\Documents"
  ```
- **Force a manual index scan:**
  ```powershell
  python main.py scan
  ```
- **Run a semantic search:**
  ```powershell
  python main.py search "architecture diagram for redis caching"
  ```
- **Run the live filesystem watcher (incremental indexing):**
  *(Keeps your index up-to-date automatically as you save files)*
  ```powershell
  python main.py watch
  ```

---

## 🛠️ Tech Stack Highlights
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (Fast, lightweight, strictly local).
- **Vector Database:** `FAISS` (Facebook AI Similarity Search) for ultra-fast nearest-neighbor lookups.
- **Metadata Database:** `SQLite` with Write-Ahead Logging for concurrent reads/writes.
- **Backend:** `FastAPI` + `Uvicorn`.
- **Frontend:** Pure Vanilla HTML/CSS/JS (Zero-dependency, Glassmorphism aesthetic).

---

## 🔒 Privacy First
Everything runs **100% locally** on your machine. Your personal files, embeddings, and queries never leave your computer. No cloud APIs, no data telemetry.
