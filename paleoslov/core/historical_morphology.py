"""Local UDPipe morphology for Old Church Slavonic and Old East Slavic.

UDPipe predictions are model outputs, not manuscript evidence. We preserve the
user's spelling and attach the treebank/model provenance to every result.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import time


MODEL_SPECS = {
    "Старославянский": {
        "id": "old_church_slavonic-proiel-ud-2.5-191206",
        "filename": "old_church_slavonic-proiel-ud-2.5-191206.udpipe",
        "treebank": "UD Old Church Slavonic PROIEL",
        "source": "https://universaldependencies.org/treebanks/cu_proiel/index.html",
        "language_scope": "старославянский PROIEL; канонические тексты",
    },
    "Древнерусский": {
        "id": "old_russian-torot-ud-2.5-191206",
        "filename": "old_russian-torot-ud-2.5-191206.udpipe",
        "treebank": "UD Old East Slavic TOROT",
        "source": "https://universaldependencies.org/treebanks/orv_torot/index.html",
        "language_scope": "древнерусский TOROT; корпусная модель, не универсальная для всех памятников",
    },
}


@lru_cache(maxsize=4)
def _load_model(model_path: str):
    from ufal.udpipe import Model

    model = Model.load(model_path)
    if model is None:
        raise RuntimeError(f"UDPipe не смог загрузить модель: {model_path}")
    return model


class HistoricalMorphology:
    """Runs a local UDPipe 1 compatible model; no text is sent over network."""

    def __init__(self, model_dir: Path):
        self.model_dir = Path(model_dir)

    def available_traditions(self) -> list[str]:
        return [name for name, spec in MODEL_SPECS.items() if (self.model_dir / spec["filename"]).is_file()]

    def analyze(self, text: str, tradition: str) -> dict:
        started = time.perf_counter()
        if tradition == "Церковнославянский":
            return self._unavailable(
                "Для позднего церковнославянского модель не обучалась. Можно вручную запустить старославянскую PROIEL только как приблизительную подсказку; она не выбрана автоматически."
            )
        spec = MODEL_SPECS.get(tradition)
        if not spec:
            return self._unavailable("Выберите старославянскую или древнерусскую традицию вручную; автоматическая классификация недостаточно надёжна для выбора морфологической модели.")
        model_path = self.model_dir / spec["filename"]
        if not model_path.is_file():
            return self._unavailable(f"Локальная модель {spec['id']} отсутствует в комплекте.")

        from ufal.udpipe import Pipeline, ProcessingError

        model = _load_model(str(model_path.resolve()))
        pipeline = Pipeline(model, "tokenize", Pipeline.DEFAULT, Pipeline.DEFAULT, "conllu")
        error = ProcessingError()
        output = pipeline.process(text, error)
        if error.occurred():
            raise RuntimeError(error.message)
        rows = _parse_conllu(output, text)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return {
            "engine": "UDPipe 1.2 · локально",
            "model_id": spec["id"],
            "treebank": spec["treebank"],
            "source": spec["source"],
            "language_scope": spec["language_scope"],
            "license": "CC BY-NC-SA 4.0 · проверить уведомления поставки модели",
            "status": "модельный разбор; не подтверждён источником рукописи",
            "elapsed_ms": elapsed_ms,
            "tokens": rows,
            "alternatives_note": "UDPipe возвращает один основной разбор; альтернативные варианты для этой формы моделью не сформированы.",
            "warning": "Автоматические леммы, признаки и синтаксис могут ошибаться на графических вариантах и текстах вне обучающего корпуса. Сверяйте с памятником и научной разметкой.",
        }

    @staticmethod
    def _unavailable(message: str) -> dict:
        return {
            "engine": "UDPipe · локальный режим",
            "status": "не выполнен",
            "tokens": [],
            "warning": message,
        }


def _parse_conllu(conllu: str, source_text: str) -> list[dict]:
    rows: list[dict] = []
    cursor = 0
    for line in conllu.splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) != 10 or "-" in cols[0] or "." in cols[0]:
            continue
        form = cols[1]
        start = source_text.find(form, cursor)
        if start < 0:
            start = source_text.casefold().find(form.casefold(), cursor)
        end = start + len(form) if start >= 0 else None
        if end is not None:
            cursor = end
        rows.append({
            "id": cols[0], "form": form, "lemma": cols[2], "upos": cols[3],
            "xpos": cols[4], "features": {} if cols[5] == "_" else dict(item.split("=", 1) for item in cols[5].split("|") if "=" in item),
            "head": cols[6], "deprel": cols[7], "start": start if start >= 0 else None,
            "end": end, "source_verified": False,
        })
    return rows
