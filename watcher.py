import time
import os
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from db import DatabaseManager
from indexer import Indexer

logger = logging.getLogger(__name__)

class IncrementalIndexer(FileSystemEventHandler):
    def __init__(self, indexer: Indexer):
        self.indexer = indexer
        self.folders = {} # map path to (type_filter, ignore_patterns)
        self._load_folders()

    def _load_folders(self):
        cursor = self.indexer.db.conn.cursor()
        cursor.execute("SELECT path, type_filter, ignore_patterns FROM WatchedFolders")
        for row in cursor.fetchall():
            self.folders[row['path']] = {
                'ignore_patterns': row['ignore_patterns'].split(',') if row['ignore_patterns'] else []
            }

    def _get_watched_folder_for_path(self, filepath):
        for folder_path in self.folders:
            if filepath.startswith(folder_path):
                return folder_path
        return None

    def on_created(self, event):
        if not event.is_directory:
            self.handle_event(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.handle_event(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            logger.info(f"File deleted: {event.src_path}")
            cursor = self.indexer.db.conn.cursor()
            cursor.execute("SELECT id FROM Files WHERE path = ?", (event.src_path,))
            row = cursor.fetchone()
            if row:
                self.indexer._delete_file_chunks(row['id'])
                cursor.execute("DELETE FROM Files WHERE id = ?", (row['id'],))
                self.indexer.db.conn.commit()

    def handle_event(self, filepath):
        folder_path = self._get_watched_folder_for_path(filepath)
        if folder_path:
            # Note: Debouncing can be implemented here by keeping a queue and a delay thread.
            # For this simple v1, we just call process_file. If it's called multiple times,
            # the content_hash check in process_file will handle skipping duplicates.
            time.sleep(1) # Simple debounce delay to let writes finish
            self.indexer.process_file(filepath, folder_path)
            self.indexer.db.save_faiss()

def start_watcher(db: DatabaseManager):
    indexer = Indexer(db)
    event_handler = IncrementalIndexer(indexer)
    observer = Observer()
    
    for folder_path in event_handler.folders:
        if os.path.exists(folder_path):
            observer.schedule(event_handler, folder_path, recursive=True)
            logger.info(f"Watching folder: {folder_path}")
        else:
            logger.warning(f"Cannot watch non-existent folder: {folder_path}")
            
    if not event_handler.folders:
        logger.warning("No folders to watch.")
        return

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
