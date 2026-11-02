"""Independent stages for paleographic and linguistic work.

The stages deliberately keep source text immutable. OCR hypotheses, any edited
reading, translation, corpus matches, and research records remain separate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import time
from typing import Callable

from .linguistics import analyze_orthography, investigate_yat_vs_jer
from .historical_morphology import HistoricalMorphology
from .text import tokenize


@dataclass
class StageResult:
    value: object
    status: str
    elapsed_ms: int
    error: str = ""


def normalize_reading(text: str) -> dict:
    """Return an unchanged diplomatic reading; normalization needs explicit editorial review."""
    return {"source": text, "reading": text, "changed": False, "method": "identity; автоматическая нормализация отключена"}


def translate_to_russian(text: str, translator: Callable[[str], str]) -> StageResult:
    started = time.perf_counter()
    try:
        translation = translator(text)
        if not isinstance(translation, str) or not translation.strip():
            raise ValueError("Переводчик вернул пустой результат")
        if translation.strip() == text.strip():
            raise ValueError("Переводчик вернул исходную строку без перевода")
        cyrillic = sum("А" <= c <= "я" or c in "Ёё" for c in translation)
        historical = sum(c in "ѢѣѲѳѴѵѪѫѦѧѨѩѬѭѤѥ" for c in translation)
        if cyrillic < max(2, len(translation.strip()) // 8):
            raise ValueError("Результат не похож на перевод на современный русский язык")
        if historical > max(2, cyrillic // 5):
            raise ValueError("Ответ сохраняет слишком много исторических графем; перевод на современный русский не подтверждён")
        return StageResult(translation.strip(), "готово", round((time.perf_counter() - started) * 1000))
    except Exception as exc:
        return StageResult(None, "ошибка", round((time.perf_counter() - started) * 1000), str(exc))


def analyze_morphology(
    text: str,
    form_lookup: Callable[[str], list] | None = None,
    engine: HistoricalMorphology | None = None,
    tradition: str = "Автоматически",
) -> StageResult:
    """Run a local historical model and attach separate corpus attestations."""
    started = time.perf_counter()
    model_result = engine.analyze(text, tradition) if engine else {
        "engine": "не выбран", "status": "корпусный поиск без морфологической модели", "tokens": [],
        "warning": "Точные совпадения в корпусе не являются контекстным разбором.",
    }
    rows = model_result.get("tokens", [])
    lookup_cache: dict[str, list] = {}
    for row in rows:
        key = row["form"].casefold()
        if form_lookup and key not in lookup_cache:
            lookup_cache[key] = [dict(x) for x in form_lookup(row["form"])]
        row["corpus_matches"] = lookup_cache.get(key, [])
    if not rows:
        rows = []
        for token in tokenize(text):
            key = token.text.casefold()
            if form_lookup and key not in lookup_cache:
                lookup_cache[key] = [dict(x) for x in form_lookup(token.text)]
            rows.append({"form": token.text, "start": token.start, "end": token.end, "lemma": None, "upos": None,
                         "features": {}, "deprel": None, "source_verified": False,
                         "corpus_matches": lookup_cache.get(key, [])})
    model_result = {**model_result, "tokens": rows}
    elapsed = round((time.perf_counter() - started) * 1000)
    model_result["elapsed_ms"] = elapsed
    return StageResult(model_result, model_result.get("status", "без корпуса"), elapsed)


def detect_historical_features(text: str) -> StageResult:
    started = time.perf_counter()
    rows = [asdict(item) for item in analyze_orthography(text)]
    # A letter ѣ can be selected for a case review, but its expected etymon is
    # intentionally not guessed from spelling alone.
    reviews = [investigate_yat_vs_jer(text[row["token_start"]:row["token_end"]])
               for row in rows if row["rule_id"] == "ORTH-YAT" and row["token_start"] is not None]
    return StageResult({"observations": rows, "yat_jer_reviews": reviews}, "готово", round((time.perf_counter() - started) * 1000))


def research_explanations(query: str, search: Callable[[str], list[dict]]) -> StageResult:
    started = time.perf_counter()
    try:
        records = search(query)
        return StageResult(records, "найдены записи" if records else "нет записей", round((time.perf_counter() - started) * 1000))
    except Exception as exc:
        return StageResult(None, "ошибка", round((time.perf_counter() - started) * 1000), str(exc))


def validate_evidence(claim: str, sources: list[dict] | None = None) -> dict:
    """A bibliography hit is not evidence by itself; full-text verification stays explicit."""
    records = sources or []
    if not claim.strip():
        return {"claim": claim, "status": "нет проверяемого утверждения", "sources": []}
    if not records:
        return {"claim": claim, "status": "подтверждение не найдено", "sources": []}
    return {
        "claim": claim,
        "status": "требуется сверка полного текста источников",
        "sources": records,
        "note": "Наличие библиографической записи само по себе не подтверждает утверждение.",
    }


def analyze_user_text(text: str, tradition: str, llm_client, form_lookup: Callable[[str], list] | None = None, cancelled=None, on_update=None, *, deep: bool = False, morphology_engine: HistoricalMorphology | None = None, morphology_result: StageResult | None = None) -> dict:
    """Run deterministic stages first and keep the two generative stages independent."""
    normalized = normalize_reading(text)
    features = detect_historical_features(text)
    morphology = morphology_result or analyze_morphology(text, form_lookup, morphology_engine, tradition)
    llm = llm_client.analyze(text, tradition, cancelled, on_update, deep=deep, morphology=morphology.value if isinstance(morphology.value, dict) else None)
    return {
        "reading": normalized["reading"],
        "normalization": normalized,
        "translation": llm.translation,
        "explanation": llm.explanation,
        "observations": features.value["observations"],
        "historical_reviews": features.value["yat_jer_reviews"],
        "morphology": morphology.value,
        "component_errors": llm.component_errors,
        "timings_ms": {"morphology": morphology.elapsed_ms, "historical_features": features.elapsed_ms, **llm.timings_ms},
        "performance": llm.performance,
        "evidence_validation": validate_evidence(llm.explanation),
    }
