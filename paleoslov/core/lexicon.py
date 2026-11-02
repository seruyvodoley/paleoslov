"""Source-aware lexical lookup helpers.

This module does not turn a treebank lemma into a dictionary definition. It
returns context-sensitive corpus candidates and links to searchable scholarly
lexica; lexical meanings are shown only when a licensed local entry exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class LexiconSource:
    title: str
    url: str
    scope: str
    kind: str


SOURCES = {
    "Древнерусский": (
        LexiconSource("Словарь древнерусского языка XI–XIV вв. (ИРЯ РАН)", "https://lexrus.ru/default.aspx?p=2641", "Древнерусская письменность XI–XIV вв.; словарные статьи с толкованиями и примерами", "scholarly"),
        LexiconSource("Материалы И. И. Срезневского: электронный поиск", "https://www.oldrusdict.ru/dict.html", "Древнерусская, старославянская и церковнославянская лексика; проверить статью и редакторские пометы", "reference"),
    ),
    "Старославянский": (
        LexiconSource("GORAZD: Электронный словарь языка старославянского", "https://gulliver.gorazd.org/", "Словник по историческим рукописям; проверять хронологический и текстовый охват", "scholarly"),
        LexiconSource("Old Church Slavonic Online · Master Glossary (UT Austin)", "https://lrc.la.utexas.edu/eieol_master_gloss/ocsol/13", "Учебный словарь форм с глоссами и переходами к контекстам", "reference"),
    ),
    "Церковнославянский": (
        LexiconSource("Большой словарь церковнославянского языка Нового времени", "https://xn--nxa.xn--80adbjsgcdgtdgcxue6e3i.xn--80asehdb/", "Электронный словарь; доступная часть и поиск зависят от портала", "scholarly"),
        LexiconSource("Материалы И. И. Срезневского: электронный поиск", "https://www.oldrusdict.ru/dict.html", "Исторические словарные статьи; поздние значения нужно проверять по статье", "reference"),
    ),
}

DEFAULT_SOURCES = (
    LexiconSource("Словарь древнерусского языка XI–XIV вв. (ИРЯ РАН)", "https://lexrus.ru/default.aspx?p=2641", "Древнерусская письменность XI–XIV вв.", "scholarly"),
    LexiconSource("GORAZD: электронные старославянские словари", "https://gorazd.org/", "Старославянские словари и тексты", "scholarly"),
)


def lexical_lookup(form: str, tradition: str, analyses: list[dict] | None = None,
                   corpus_matches: list[dict] | None = None) -> dict:
    """Assemble distinct context-sensitive analyses and auditable references."""
    candidates: list[dict] = []
    seen: dict[tuple[str, str, tuple[tuple[str, str], ...]], dict] = {}

    def add(lemma: str, upos: str, features: dict | str, source: str,
            source_url: str = "", source_verified: bool = False) -> None:
        if isinstance(features, str):
            feature_map = dict(part.split("=", 1) for part in features.split("|") if "=" in part)
            shown_features: dict | str = features
        else:
            feature_map = {str(k): str(v) for k, v in features.items()}
            shown_features = feature_map
        key = (str(lemma), str(upos or ""), tuple(sorted(feature_map.items())))
        item = seen.get(key)
        if item is None:
            item = {"lemma": str(lemma), "part_of_speech": upos or None,
                    "features": shown_features, "source": source,
                    "sources": [source], "source_verified": source_verified}
            if source_url:
                item["source_url"] = source_url
            seen[key] = item
            candidates.append(item)
        elif source not in item["sources"]:
            item["sources"].append(source)
            item["source"] = " · ".join(item["sources"])

    for row in analyses or []:
        lemma = row.get("lemma")
        if not lemma:
            continue
        features = row.get("features") or {}
        add(str(lemma), row.get("upos") or "", features, "UDPipe: модельная гипотеза")
    for row in corpus_matches or []:
        lemma = row.get("lemma")
        if not lemma:
            continue
        feats = row.get("feats") or ""
        add(str(lemma), row.get("upos") or "", feats, row.get("corpus", "Локальный корпус"),
            row.get("source_url", ""))
    sources = SOURCES.get(tradition, DEFAULT_SOURCES)
    return {
        "form": form,
        "tradition": tradition,
        "candidates": candidates,
        "dictionary_meanings": [],
        "meaning_status": "Встроенная словарная статья для этой формы не найдена; корпусная лемма не является толкованием.",
        "dictionary_sources": [source.__dict__ for source in sources],
        "lookup_term": quote((candidates[0]["lemma"] if candidates else form), safe=""),
        "alternatives_note": "Несколько анализов оставлены раздельно: выбор значения требует синтаксического контекста и сверки со словарной статьёй.",
    }
