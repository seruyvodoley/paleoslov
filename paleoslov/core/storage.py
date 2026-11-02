from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, title TEXT NOT NULL, original TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY, document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE, tradition TEXT, reading TEXT, translation TEXT, explanation TEXT, observations TEXT NOT NULL DEFAULT '[]', morphology TEXT NOT NULL DEFAULT '{}', translation_alternatives TEXT NOT NULL DEFAULT '[]', historical_reviews TEXT NOT NULL DEFAULT '[]', research_records TEXT NOT NULL DEFAULT '[]', created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY, title TEXT, authors TEXT, year TEXT, doi TEXT, url TEXT, venue TEXT, accessed TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY, analysis_id INTEGER REFERENCES analyses(id) ON DELETE CASCADE, source_id INTEGER REFERENCES sources(id), excerpt TEXT, status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS corpus_tokens(id INTEGER PRIMARY KEY, corpus TEXT NOT NULL, license TEXT NOT NULL, form TEXT NOT NULL, form_key TEXT NOT NULL, lemma TEXT NOT NULL, upos TEXT NOT NULL, xpos TEXT NOT NULL, feats TEXT NOT NULL, deprel TEXT NOT NULL, source_url TEXT NOT NULL, UNIQUE(corpus,form_key,lemma,upos,feats));
        CREATE INDEX IF NOT EXISTS corpus_form_idx ON corpus_tokens(form_key);
        CREATE TABLE IF NOT EXISTS research_cache(query TEXT PRIMARY KEY, response TEXT NOT NULL, fetched TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rules(rule_id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, tradition TEXT NOT NULL, exceptions TEXT NOT NULL DEFAULT '', sources TEXT NOT NULL DEFAULT '[]');
        CREATE TABLE IF NOT EXISTS dialect_features(feature_id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, minimum_evidence TEXT NOT NULL, sources TEXT NOT NULL DEFAULT '[]');
        CREATE TABLE IF NOT EXISTS hypotheses(id INTEGER PRIMARY KEY, analysis_id INTEGER REFERENCES analyses(id) ON DELETE CASCADE, statement TEXT NOT NULL, status TEXT NOT NULL, evidence_for TEXT NOT NULL DEFAULT '[]', evidence_against TEXT NOT NULL DEFAULT '[]');
        CREATE VIRTUAL TABLE IF NOT EXISTS source_search USING fts5(title, authors, doi, content='sources', content_rowid='id');
        """)
        try:
            self.db.execute("ALTER TABLE analyses ADD COLUMN ocr_metadata TEXT NOT NULL DEFAULT '{}'")
        except sqlite3.OperationalError:
            pass
        try:
            self.db.execute("ALTER TABLE analyses ADD COLUMN morphology TEXT NOT NULL DEFAULT '{}'")
        except sqlite3.OperationalError:
            pass
        try:
            self.db.execute("ALTER TABLE analyses ADD COLUMN translation_metadata TEXT NOT NULL DEFAULT '{}'")
        except sqlite3.OperationalError:
            pass
        for column, default in (("translation_alternatives", "[]"), ("historical_reviews", "[]")):
            try:
                self.db.execute(f"ALTER TABLE analyses ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default}'")
            except sqlite3.OperationalError:
                pass
        try:
            self.db.execute("ALTER TABLE analyses ADD COLUMN research_records TEXT NOT NULL DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass
        self.db.execute("INSERT OR IGNORE INTO rules(rule_id,title,description,tradition,sources) VALUES('ORTH-YAT','Буква ѣ','Фиксируется графическое наличие буквы; историческое чтение зависит от формы и традиции.','historical_slavic','[]')")
        self.db.execute("INSERT OR IGNORE INTO rules(rule_id,title,description,tradition,sources) VALUES('ORTH-JERS','Редуцированные ъ и ь','Фиксируется графическое наличие; позиция редуцированного автоматически не определяется.','historical_slavic','[]')")
        self.db.commit()

    def save(self, title: str, original: str, result: dict) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            cur = self.db.execute("INSERT INTO documents(title,original,created,updated) VALUES(?,?,?,?)", (title or "Без названия", original, now, now))
            doc_id = cur.lastrowid
            self.db.execute("INSERT INTO analyses(document_id,tradition,reading,translation,explanation,observations,morphology,translation_alternatives,historical_reviews,research_records,created,ocr_metadata,translation_metadata) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (doc_id, result.get("tradition", ""), result.get("reading", ""), result.get("translation", ""), result.get("explanation", ""), json.dumps(result.get("observations", []), ensure_ascii=False), json.dumps(result.get("morphology", {}), ensure_ascii=False), json.dumps(result.get("translation_alternatives", []), ensure_ascii=False), json.dumps(result.get("historical_reviews", []), ensure_ascii=False), json.dumps(result.get("research_records", []), ensure_ascii=False), now, json.dumps(result.get("ocr", {}), ensure_ascii=False), json.dumps(result.get("translation_metadata", {}), ensure_ascii=False)))
        return int(doc_id)

    def update(self, doc_id: int, title: str, original: str, result: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute("UPDATE documents SET title=?,original=?,updated=? WHERE id=?", (title or "Без названия", original, now, doc_id))
            self.db.execute("INSERT INTO analyses(document_id,tradition,reading,translation,explanation,observations,morphology,translation_alternatives,historical_reviews,research_records,created,ocr_metadata,translation_metadata) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (doc_id, result.get("tradition", ""), result.get("reading", ""), result.get("translation", ""), result.get("explanation", ""), json.dumps(result.get("observations", []), ensure_ascii=False), json.dumps(result.get("morphology", {}), ensure_ascii=False), json.dumps(result.get("translation_alternatives", []), ensure_ascii=False), json.dumps(result.get("historical_reviews", []), ensure_ascii=False), json.dumps(result.get("research_records", []), ensure_ascii=False), now, json.dumps(result.get("ocr", {}), ensure_ascii=False), json.dumps(result.get("translation_metadata", {}), ensure_ascii=False)))

    def history(self) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT id,title,updated,original FROM documents ORDER BY updated DESC"))

    def load(self, doc_id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT d.*, a.tradition,a.reading,a.translation,a.explanation,a.observations,a.morphology,a.translation_alternatives,a.historical_reviews,a.research_records,a.ocr_metadata,a.translation_metadata FROM documents d LEFT JOIN analyses a ON a.document_id=d.id WHERE d.id=? ORDER BY a.id DESC LIMIT 1", (doc_id,)).fetchone()

    def delete(self, doc_id: int) -> None:
        with self.db:
            self.db.execute("DELETE FROM documents WHERE id=?", (doc_id,))

    def import_conllu(self, corpus: str, license: str, source_url: str, rows: list[dict[str, str]]) -> int:
        from .text import search_form
        values = [(corpus, license, r["form"], search_form(r["form"]), r["lemma"], r["upos"], r["xpos"], r["feats"], r["deprel"], source_url) for r in rows]
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO corpus_tokens(corpus,license,form,form_key,lemma,upos,xpos,feats,deprel,source_url) VALUES(?,?,?,?,?,?,?,?,?,?)", values)
        return len(values)

    def find_forms(self, form: str, limit: int = 20) -> list[sqlite3.Row]:
        from .text import search_form
        return list(self.db.execute("SELECT corpus,license,form,lemma,upos,xpos,feats,deprel,source_url FROM corpus_tokens WHERE form_key=? LIMIT ?", (search_form(form), limit)))

    def close(self) -> None:
        self.db.close()
