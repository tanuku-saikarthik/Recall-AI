import os
import time
import shutil
import glob
import psutil
from datetime import datetime, timedelta
from indexer import Indexer
from db import DatabaseManager

DOWNLOADS_DIR = os.path.expanduser("~/Downloads")
BENCHMARK_DIR = "benchmark_data"

def prepare_benchmark_data():
    print(f"--- Preparing Benchmark Data from {DOWNLOADS_DIR} ---")
    if os.path.exists(BENCHMARK_DIR):
        shutil.rmtree(BENCHMARK_DIR)
    os.makedirs(BENCHMARK_DIR)
    
    one_week_ago = datetime.now() - timedelta(days=7)
    one_week_ago_ts = one_week_ago.timestamp()
    
    count = 0
    # Search for common document/code types
    for ext in ["*.pdf", "*.docx", "*.pptx", "*.xlsx", "*.txt", "*.md", "*.py", "*.csv", "*.json"]:
        for filepath in glob.glob(os.path.join(DOWNLOADS_DIR, "**", ext), recursive=True):
            try:
                stat = os.stat(filepath)
                if stat.st_mtime > one_week_ago_ts:
                    # File modified in last 7 days
                    if stat.st_size < 100 * 1024 * 1024: # Skip > 100MB
                        dest = os.path.join(BENCHMARK_DIR, os.path.basename(filepath))
                        # Handle name collisions
                        base, extension = os.path.splitext(dest)
                        counter = 1
                        while os.path.exists(dest):
                            dest = f"{base}_{counter}{extension}"
                            counter += 1
                            
                        shutil.copy2(filepath, dest)
                        count += 1
                        if count >= 100: # Cap at 100 for benchmark sanity
                            break
            except Exception:
                pass
            if count >= 100:
                break
        if count >= 100:
            break
            
    print(f"Copied {count} files to {BENCHMARK_DIR}")
    return count

def run_benchmark():
    count = prepare_benchmark_data()
    if count == 0:
        print("No files found to benchmark.")
        return
        
    print("\n--- Starting Benchmark ---")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO WatchedFolders (path, ignore_patterns, added_on) VALUES (?, ?, ?)", 
                   (os.path.abspath(BENCHMARK_DIR), ".*", time.time()))
    db.conn.commit()
    
    indexer = Indexer(db)
    
    # Get baseline chunks
    cursor.execute("SELECT COUNT(id) FROM Chunks")
    chunks_before = cursor.fetchone()[0]
    
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / 1024 / 1024
    
    start_time = time.time()
    indexer.scan_and_index()
    end_time = time.time()
    
    mem_after = process.memory_info().rss / 1024 / 1024
    
    cursor.execute("SELECT COUNT(id) FROM Chunks")
    chunks_after = cursor.fetchone()[0]
    
    chunks_processed = chunks_after - chunks_before
    time_taken = end_time - start_time
    
    print(f"\n--- Benchmark Results ---")
    print(f"Total Time: {time_taken:.2f} seconds")
    print(f"Files Processed: {count}")
    print(f"Chunks Embedded: {chunks_processed}")
    
    if time_taken > 0:
        print(f"Files / sec: {count / time_taken:.2f}")
        print(f"Chunks / sec: {chunks_processed / time_taken:.2f}")
    
    print(f"Peak RAM (Approximate): {max(mem_before, mem_after):.2f} MB")
    
if __name__ == "__main__":
    run_benchmark()
