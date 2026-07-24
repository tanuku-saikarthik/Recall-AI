import os
import sqlite3
import time
from indexer import Indexer
from db import DatabaseManager
from search import Searcher

def test_corrupt_file():
    print("--- Testing Corrupt File Handling ---")
    os.makedirs("test_robust", exist_ok=True)
    with open("test_robust/corrupt.pdf", "w") as f:
        f.write("This is not a real PDF file")
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO WatchedFolders (path, ignore_patterns, added_on) VALUES (?, ?, ?)", 
                   (os.path.abspath("test_robust"), ".*", time.time()))
    db.conn.commit()
    
    indexer = Indexer(db)
    indexer.scan_and_index()
    print("PASSED: Scanner did not crash on corrupt PDF.")

def test_faiss_deletes():
    print("--- Testing FAISS Chunk Deletions ---")
    filepath = "test_robust/mutable.txt"
    with open(filepath, "w") as f:
        f.write("This is the original unique text that should be deleted.")
        
    db = DatabaseManager()
    indexer = Indexer(db)
    indexer.scan_and_index()
    
    searcher = Searcher(db)
    res = searcher.search("original unique text")
    assert len(res) > 0, "Initial text not found!"
    print("Initial text successfully indexed.")
    
    # Modify the file
    time.sleep(1) # Ensure timestamp changes
    with open(filepath, "w") as f:
        f.write("This is the completely brand new replaced text.")
        
    indexer.scan_and_index()
    
    res_old = searcher.search("original unique text")
    res_new = searcher.search("completely brand new replaced text")
    
    old_found = any("original" in r['chunk_text'] for r in res_old)
    new_found = any("completely" in r['chunk_text'] for r in res_new)
    
    if old_found:
        print("FAILED: Old vector still exists in index! Leak detected.")
    else:
        print("PASSED: Old vector successfully purged from FAISS.")
        
    if new_found:
        print("PASSED: New vector successfully indexed.")
    else:
        print("FAILED: New vector not found.")

if __name__ == "__main__":
    test_corrupt_file()
    test_faiss_deletes()
    print("\nAll Robustness Tests Finished.")
