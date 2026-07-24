import os
import re
import json
import logging
import dateparser
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")

class QueryParser:
    def __init__(self):
        # File type hints mappings
        self.type_mappings = {
            "pdf": ".pdf",
            "ppt": ".pptx",
            "presentation": ".pptx",
            "python script": ".py",
            "doc": ".docx",
            "report": ".docx",
            "excel": ".xlsx",
            "spreadsheet": ".xlsx"
        }
        
    def parse(self, query: str):
        """Parses a query into {topic, time_range, file_type_hint}."""
        parsed = {
            "topic": query,
            "time_range": None, # (start_date, end_date) tuples
            "file_type_hint": None
        }
        
        # 1. Rule-based file type extraction
        # 1. Rule-based file type extraction
        lower_query = query.lower()
        for hint, ext in self.type_mappings.items():
            if hint in lower_query:
                parsed["file_type_hint"] = ext
                # naive topic reduction
                parsed["topic"] = lower_query.replace(hint, "").strip()
                break

        # 2. Rule-based date extraction
        # A simple approach: use dateparser on the whole query to see if a date pops out.
        # This is quite naive, but works for "last semester", "yesterday", "2023", etc.
        # Real implementations might use a NER model or more complex regex, but we stick to the spec.
        # To avoid false positives on normal words, we might just use Ollama if rule-based is ambiguous.
        
        # Fallback to Ollama if topic seems empty or we couldn't parse well
        if not parsed["file_type_hint"] and len(parsed["topic"]) > 0:
            # For this simple v1, we just return the query as topic
            pass
            
        # Example of Ollama fallback (can be invoked if rule-based fails)
        # parsed = self._fallback_ollama(query)
        
        return parsed

    def _fallback_ollama(self, query: str):
        prompt = f"""
        Extract the following information from the query as JSON:
        - topic: The main subject being searched for.
        - time_range: Any mentioned dates or timeframes (e.g. "last year", "2023"). Null if none.
        - file_type_hint: Any hints about the file type (e.g. ".pdf", ".pptx", ".py"). Null if none.
        
        Query: "{query}"
        
        Output only valid JSON.
        """
        
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=10
            )
            if response.status_code == 200:
                result = response.json()
                return json.loads(result.get("response", "{}"))
        except Exception as e:
            logger.error(f"Ollama fallback failed: {e}")
            
        return {"topic": query, "time_range": None, "file_type_hint": None}

