from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import httpx


class ResearchService:
    """Free bibliographic discovery; records metadata, not proof of a claim."""
    def __init__(self, timeout: float = 12):
        self.timeout = timeout

    def search(self, query: str, limit: int = 8, cache_db: Path | None = None) -> list[dict[str, str]]:
        if not query.strip():
            return []
        limit = max(1, min(int(limit), 20))
        cache_key = hashlib.sha256(f"{query.strip().casefold()}\0{limit}".encode("utf-8")).hexdigest()
        if cache_db:
            cached = self._read_cache(cache_db, cache_key)
            if cached is not None:
                return cached
        headers = {"User-Agent": "Paleoslov/0.1 (local scholarly metadata lookup)"}
        works = []
        provider = "OpenAlex"
        with httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            try:
                r = client.get("https://api.openalex.org/works", params={"search": query, "per-page": min(limit, 20), "select": "id,doi,title,publication_year,authorships,primary_location,open_access"})
                r.raise_for_status()
                works = r.json().get("results", [])
            except (httpx.HTTPError, ValueError):
                provider = "Crossref"
                r = client.get("https://api.crossref.org/works", params={"query.bibliographic": query, "rows": min(limit, 20)})
                r.raise_for_status()
                works = r.json().get("message", {}).get("items", [])
            if provider == "OpenAlex" and not works:
                provider = "Crossref"
                r = client.get("https://api.crossref.org/works", params={"query.bibliographic": query, "rows": min(limit, 20)})
                r.raise_for_status()
                works = r.json().get("message", {}).get("items", [])
        found = []
        for w in works:
            if provider == "OpenAlex":
                authors = [a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])]
                loc = w.get("primary_location") or {}
                src = loc.get("source") or {}
                title, year, doi, url, venue = w.get("title"), w.get("publication_year"), w.get("doi"), loc.get("landing_page_url") or w.get("id", ""), src.get("display_name", "")
            else:
                authors = [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in w.get("author", [])]
                dates = w.get("published-print") or w.get("published-online") or w.get("created") or {}
                parts = dates.get("date-parts", [[None]])
                title = (w.get("title") or [None])[0]
                year = parts[0][0] if parts and parts[0] else None
                doi = w.get("DOI")
                url = w.get("URL", "")
                venue = (w.get("container-title") or [""])[0]
            found.append({
                "provider": provider,
                "title": title or "Без названия",
                "authors": ", ".join(a for a in authors if a) or "Автор не указан в метаданных",
                "year": str(year or "Год не указан"),
                "doi": (doi or "").replace("https://doi.org/", ""),
                "url": url,
                "venue": venue,
                "open_access": str((w.get("open_access") or {}).get("is_oa", "неизвестно")),
                "accessed": datetime.now(timezone.utc).date().isoformat(),
                "status": "Библиографическая запись; содержание и подтверждение тезиса не проверены",
            })
        if cache_db:
            self._write_cache(cache_db, cache_key, found)
        return found

    @staticmethod
    def _read_cache(path: Path, key: str) -> list[dict[str, str]] | None:
        try:
            with sqlite3.connect(path, timeout=2) as db:
                row = db.execute("SELECT response,fetched FROM research_cache WHERE query=?", (key,)).fetchone()
            if not row:
                return None
            fetched = datetime.fromisoformat(row[1])
            if (datetime.now(timezone.utc) - fetched).total_seconds() > 30 * 24 * 60 * 60:
                return None
            value = json.loads(row[0])
            return value if isinstance(value, list) else None
        except (sqlite3.Error, OSError, ValueError, TypeError):
            return None

    @staticmethod
    def _write_cache(path: Path, key: str, records: list[dict[str, str]]) -> None:
        try:
            with sqlite3.connect(path, timeout=2) as db:
                db.execute("INSERT INTO research_cache(query,response,fetched) VALUES(?,?,?) ON CONFLICT(query) DO UPDATE SET response=excluded.response,fetched=excluded.fetched", (key, json.dumps(records, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
                db.commit()
        except (sqlite3.Error, OSError):
            pass
