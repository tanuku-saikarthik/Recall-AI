import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Any

from db import DatabaseManager
from query_parser import QueryParser
from indexer import embedding_model

logger = logging.getLogger(__name__)

class Searcher:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.parser = QueryParser()

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        parsed_query = self.parser.parse(query)
        topic = parsed_query.get("topic") or query
        file_type_hint = parsed_query.get("file_type_hint")
        
        logger.info(f"Parsed Query: topic='{topic}', type='{file_type_hint}'")
        
        # 1. Embed query
        query_embedding = embedding_model.encode([topic])[0]
        query_vector = np.expand_dims(query_embedding.astype('float32'), axis=0)
        
        # 2. FAISS nearest-neighbor search (get more than top_k to allow for filtering/aggregation)
        search_k = max(20, top_k * 4)
        if self.db.index.ntotal == 0:
            logger.warning("FAISS index is empty.")
            return []
            
        distances, indices = self.db.index.search(query_vector, search_k)
        
        if len(indices) == 0 or indices[0][0] == -1:
            return []

        # 3. Join with SQLite and aggregate by file
        cursor = self.db.conn.cursor()
        
        results = {}
        for i, chunk_id in enumerate(indices[0]):
            if chunk_id == -1:
                continue
                
            score = float(distances[0][i])
            
            cursor.execute("""
                SELECT c.chunk_text, c.page_or_slide, f.id, f.path, f.filename, f.extension, f.modified 
                FROM Chunks c
                JOIN Files f ON c.file_id = f.id
                WHERE c.id = ?
            """, (int(chunk_id),))
            
            row = cursor.fetchone()
            if not row:
                continue
                
            # Apply hard filters (file_type_hint)
            if file_type_hint and row['extension'] != file_type_hint:
                continue
                
            file_id = row['id']
            
            # Simple recency boost
            # e.g., slightly boost score if modified within last 30 days
            try:
                mod_time = datetime.fromisoformat(row['modified'])
                days_old = (datetime.now() - mod_time).days
                if days_old < 30:
                    score *= 1.1 # 10% boost for recent files
            except:
                pass
            
            if file_id not in results or results[file_id]['score'] < score:
                results[file_id] = {
                    'score': score,
                    'path': row['path'],
                    'filename': row['filename'],
                    'page': row['page_or_slide'],
                    'chunk_text': row['chunk_text'],
                    'modified': row['modified']
                }

        # 4. Sort and return top_k
        sorted_results = sorted(results.values(), key=lambda x: x['score'], reverse=True)
        return sorted_results[:top_k]

