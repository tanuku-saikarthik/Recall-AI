import argparse
import os
import sys
import logging
from datetime import datetime
from db import DatabaseManager
from indexer import Indexer
from search import Searcher
from watcher import start_watcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def add_folder(db: DatabaseManager, path: str):
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        print(f"Error: Path {abs_path} does not exist.")
        return
        
    cursor = db.conn.cursor()
    # Default ignore patterns
    default_ignore = "node_modules/,.git/,__pycache__/,venv/,.venv/,*.pyc,AppData/,$RECYCLE.BIN/,*.tmp,.*"
    
    try:
        cursor.execute("""
            INSERT INTO WatchedFolders (path, ignore_patterns, added_on)
            VALUES (?, ?, ?)
        """, (abs_path, default_ignore, datetime.now().isoformat()))
        db.conn.commit()
        print(f"Added folder: {abs_path}")
        print("Run 'scan' to index the contents.")
    except Exception as e:
        print(f"Error adding folder (maybe already added?): {e}")

def main():
    parser = argparse.ArgumentParser(description="LLM Personal File Retrieval Assistant")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add folder command
    parser_add = subparsers.add_parser("add-folder", help="Add a folder to be indexed")
    parser_add.add_argument("path", help="Path to the folder")

    # Scan command
    parser_scan = subparsers.add_parser("scan", help="Run a full scan and index on watched folders")

    # Watch command
    parser_watch = subparsers.add_parser("watch", help="Run the incremental indexer in the background")

    # Search command
    parser_search = subparsers.add_parser("search", help="Search for files")
    parser_search.add_argument("query", help="The search query")
    parser_search.add_argument("--top_k", type=int, default=5, help="Number of results to return")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    db = DatabaseManager()

    if args.command == "add-folder":
        add_folder(db, args.path)
    elif args.command == "scan":
        indexer = Indexer(db)
        print("Starting scan...")
        indexer.scan_and_index()
        print("Scan complete.")
    elif args.command == "watch":
        print("Starting watcher... Press Ctrl+C to stop.")
        start_watcher(db)
    elif args.command == "search":
        searcher = Searcher(db)
        results = searcher.search(args.query, top_k=args.top_k)
        
        if not results:
            print("No results found.")
            return
            
        for i, res in enumerate(results):
            print(f"--- Result {i+1} ---")
            print(f"File: {os.path.basename(res['path'])} (Score: {res['score']:.4f})")
            print(f"Path: {res['path']}")
            print(f"Page/Slide: {res['page']}")
            
            # Safely print on Windows cp1252 consoles without crashing on unicode characters
            safe_text = res['chunk_text'].encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
            print(f"Preview:\n{safe_text}\n")

if __name__ == "__main__":
    main()
