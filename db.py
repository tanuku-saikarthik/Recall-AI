import sqlite3
import faiss
import os
import logging
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "metadata.db")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "vectors.faiss")
EMBEDDING_DIM = 384

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path=DB_PATH, faiss_path=FAISS_INDEX_PATH):
        self.db_path = db_path
        self.faiss_path = faiss_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_sqlite()
        self._init_faiss()

    def _init_sqlite(self):
        cursor = self.conn.cursor()
        # Enable WAL mode
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        # Files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                filename TEXT,
                extension TEXT,
                size INTEGER,
                created TEXT,
                modified TEXT,
                accessed TEXT,
                content_hash TEXT,
                last_indexed TEXT
            )
        """)
        
        # Chunks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Chunks (
                id INTEGER PRIMARY KEY,
                file_id INTEGER REFERENCES Files(id) ON DELETE CASCADE,
                chunk_index INTEGER,
                page_or_slide INTEGER,
                chunk_text TEXT
            )
        """)
        
        # WatchedFolders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS WatchedFolders (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                date_filter TEXT,
                type_filter TEXT,
                ignore_patterns TEXT,
                added_on TEXT
            )
        """)
        
        self.conn.commit()

    def _init_faiss(self):
        if os.path.exists(self.faiss_path):
            try:
                self.index = faiss.read_index(self.faiss_path)
                logger.info(f"Loaded existing FAISS index with {self.index.ntotal} vectors.")
            except Exception as e:
                logger.error(f"Error loading FAISS index: {e}. Recreating...")
                self._create_new_faiss_index()
        else:
            self._create_new_faiss_index()

    def _create_new_faiss_index(self):
        # IndexIDMap allows us to assign arbitrary IDs to vectors (matching our SQLite chunk IDs)
        base_index = faiss.IndexFlatIP(EMBEDDING_DIM)
        self.index = faiss.IndexIDMap(base_index)
        logger.info("Created new FAISS index.")

    def save_faiss(self):
        faiss.write_index(self.index, self.faiss_path)

    def close(self):
        self.conn.close()
        self.save_faiss()

if __name__ == '__main__':
    # Simple test
    logging.basicConfig(level=logging.INFO)
    db = DatabaseManager()
    print("Database initialized successfully.")
    db.close()
