import os
import glob
import hashlib
import logging
from datetime import datetime
from sentence_transformers import SentenceTransformer
import sqlite3
import numpy as np

from db import DatabaseManager, EMBEDDING_DIM
from extractors import extract_file_content

logger = logging.getLogger(__name__)

# Initialize the embedding model globally so we don't reload it
embedding_model = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))

def hash_file(filepath: str) -> str:
    """Returns a hash of the file content for change detection."""
    h = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
    except Exception as e:
        logger.error(f"Error hashing file {filepath}: {e}")
        return ""
    return h.hexdigest()

def chunk_text(text: str, max_tokens: int = 300, overlap: int = 50) -> list[str]:
    """
    Very naive word-based chunking as an approximation for token-based chunking.
    In a real implementation, you might want to use a proper tokenizer.
    """
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + max_tokens])
        if chunk.strip():
            chunks.append(chunk)
        i += (max_tokens - overlap)
    return chunks

class Indexer:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def scan_and_index(self):
        """Scans all watched folders and indexes new/modified files."""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, path, date_filter, type_filter, ignore_patterns FROM WatchedFolders")
        folders = cursor.fetchall()
        
        for folder in folders:
            folder_path = folder['path']
            if not os.path.exists(folder_path):
                logger.warning(f"Watched folder {folder_path} does not exist. Skipping.")
                continue
                
            ignore_patterns = folder['ignore_patterns'].split(',') if folder['ignore_patterns'] else []
            ignore_patterns = [p.strip() for p in ignore_patterns if p.strip()]
            
            # Recursive walk
            for root, dirs, files in os.walk(folder_path):
                # Filter dirs
                dirs[:] = [d for d in dirs if not any(glob.fnmatch.fnmatch(d, p) for p in ignore_patterns) and not d.startswith('.')]
                
                for file in files:
                    # Check ignore patterns on file
                    if any(glob.fnmatch.fnmatch(file, p) for p in ignore_patterns):
                        continue
                        
                    filepath = os.path.join(root, file)
                    self.process_file(filepath, folder_path)
                    
        self.db.save_faiss()

    def process_file(self, filepath: str, folder_path: str):
        """Processes a single file: hash, chunk, embed, store."""
        try:
            stat = os.stat(filepath)
            size = stat.st_size
            max_size = int(os.getenv("MAX_FILE_SIZE_MB", 100)) * 1024 * 1024
            if size > max_size:
                logger.debug(f"Skipping {filepath}: Size {size} exceeds max {max_size}")
                return

            created = datetime.fromtimestamp(stat.st_ctime).isoformat()
            modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
            accessed = datetime.fromtimestamp(stat.st_atime).isoformat()
            extension = os.path.splitext(filepath)[1].lower()
            filename = os.path.basename(filepath)

            # Change detection
            content_hash = hash_file(filepath)
            if not content_hash:
                return

            cursor = self.db.conn.cursor()
            cursor.execute("SELECT id, content_hash FROM Files WHERE path = ?", (filepath,))
            row = cursor.fetchone()

            if row:
                if row['content_hash'] == content_hash:
                    return # No change
                logger.info(f"File modified: {filepath}. Re-indexing.")
                file_id = row['id']
                self._delete_file_chunks(file_id)
            else:
                logger.info(f"New file found: {filepath}. Indexing.")
                cursor.execute("""
                    INSERT INTO Files (path, filename, extension, size, created, modified, accessed, content_hash, last_indexed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (filepath, filename, extension, size, created, modified, accessed, content_hash, datetime.now().isoformat()))
                file_id = cursor.lastrowid

            self._extract_and_embed(filepath, file_id, extension, folder_path)
            
            # Update hash and time
            cursor.execute("UPDATE Files SET content_hash = ?, last_indexed = ? WHERE id = ?", 
                           (content_hash, datetime.now().isoformat(), file_id))
            self.db.conn.commit()

        except Exception as e:
            logger.error(f"Error processing file {filepath}: {e}")

    def _delete_file_chunks(self, file_id: int):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id FROM Chunks WHERE file_id = ?", (file_id,))
        chunk_ids = [r['id'] for r in cursor.fetchall()]
        
        if chunk_ids:
            # Remove from FAISS
            self.db.index.remove_ids(np.array(chunk_ids, dtype=np.int64))
            # Remove from SQLite
            cursor.execute("DELETE FROM Chunks WHERE file_id = ?", (file_id,))
            self.db.conn.commit()

    def _extract_and_embed(self, filepath: str, file_id: int, extension: str, folder_path: str):
        pages_data = extract_file_content(filepath, extension)
        if not pages_data:
            return

        chunks_to_insert = []
        texts_to_embed = []

        relative_path = os.path.relpath(filepath, folder_path)

        chunk_idx = 0
        for page in pages_data:
            page_text = page['text']
            page_num = page['page_or_slide']
            
            text_chunks = chunk_text(page_text)
            for chunk_str in text_chunks:
                # Prepend context
                context_prepended = f"File: {relative_path}\nFolder: {os.path.basename(folder_path)}\n\n{chunk_str}"
                
                chunks_to_insert.append({
                    "file_id": file_id,
                    "chunk_index": chunk_idx,
                    "page_or_slide": page_num,
                    "chunk_text": chunk_str  # Store original or context prepended? Storing prepended takes more space but easier to show context. Let's store prepended for simplicity.
                })
                texts_to_embed.append(context_prepended)
                chunk_idx += 1

        if not texts_to_embed:
            return

        # Embed in batches
        embeddings = embedding_model.encode(texts_to_embed)
        embeddings_np = np.array(embeddings).astype('float32')

        # Insert into SQLite first to get IDs for FAISS
        cursor = self.db.conn.cursor()
        for i, chunk in enumerate(chunks_to_insert):
            cursor.execute("""
                INSERT INTO Chunks (file_id, chunk_index, page_or_slide, chunk_text)
                VALUES (?, ?, ?, ?)
            """, (chunk['file_id'], chunk['chunk_index'], chunk['page_or_slide'], chunk['chunk_text']))
            chunk_id = cursor.lastrowid
            
            # Add to FAISS
            vector = np.expand_dims(embeddings_np[i], axis=0)
            self.db.index.add_with_ids(vector, np.array([chunk_id], dtype=np.int64))

        self.db.conn.commit()
