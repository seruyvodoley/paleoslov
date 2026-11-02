"""Conservative local lookup for verified or editorial parallel passages.

Only full normalized passage matches are eligible. Similar wording is never
substituted, because that could silently mix manuscript editions.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


def _key(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    # Ignore spaces and punctuation, but preserve every letter/combining mark.
    return "".join(ch for ch in text if ch.isalnum() or unicodedata.category(ch).startswith("M"))


class ParallelTranslationIndex:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: dict[str, dict] = {}
        if self.path.is_file():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw:
                if item.get("source_text") and item.get("translation"):
                    self.entries[_key(item["source_text"])] = item

    def lookup(self, text: str) -> dict | None:
        key = _key(text)
        if not key:
            return None
        item = self.entries.get(key)
        if not item:
            return None
        return {
            "text": item["translation"],
            "alternatives": list(item.get("alternatives", [])),
            "metadata": {
                "method": "точное совпадение с локальным параллельным текстом",
                "match": "exact",
                "title": item["title"],
                "source": item["source"],
                "translation_source": item["translation_source"],
                "status": item["status"],
                "caveat": item.get("caveat", ""),
            },
        }


def translate_from_index(text: str, index: ParallelTranslationIndex) -> dict | None:
    return index.lookup(text)
