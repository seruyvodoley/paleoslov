from __future__ import annotations

import json
from collections.abc import Callable
import httpx
from pydantic import BaseModel, Field


class AnalysisResponse(BaseModel):
    reading: str = ""
    translation: str = ""
    translation_alternatives: list[str] = Field(default_factory=list)
    explanation: str = ""
    caveats: list[str] = Field(default_factory=list)
    component_errors: dict[str, str] = Field(default_factory=dict)
    timings_ms: dict[str, int] = Field(default_factory=dict)
    performance: dict[str, dict[str, float | int]] = Field(default_factory=dict)


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen3:4b", timeout: float = 180):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.last_generation_stats: dict[str, float | int] = {}
        self.last_translation_alternatives: list[str] = []

    def status(self) -> tuple[bool, list[str], str]:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=4)
            r.raise_for_status()
            names = [x.get("name", "") for x in r.json().get("models", [])]
            return True, names, "Ollama доступна"
        except (httpx.HTTPError, ValueError) as exc:
            return False, [], f"Ollama недоступна: {exc}"

    def _complete(self, prompt: str, cancelled: Callable[[], bool] | None = None, on_chunk: Callable[[str], None] | None = None) -> str:
        stats: dict[str, float | int] = {}
        with httpx.stream("POST", f"{self.base_url}/api/chat", json={
            "model": self.model,
            "stream": True,
            "think": False,
            "options": {"num_ctx": 4096, "num_predict": 768, "temperature": 0.1},
            "messages": [{"role": "user", "content": prompt}],
        }, timeout=self.timeout) as r:
            r.raise_for_status()
            pieces = []
            for line in r.iter_lines():
                if cancelled and cancelled():
                    raise InterruptedError("Анализ отменён пользователем")
                if not line:
                    continue
                event = json.loads(line)
                piece = event.get("message", {}).get("content", "")
                pieces.append(piece)
                if piece and on_chunk:
                    on_chunk(piece)
                if event.get("done"):
                    for key in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration", "done_reason"):
                        if key in event:
                            stats[key] = event[key]
                    break
            content = "".join(pieces)
        self.last_generation_stats = stats
        if stats.get("done_reason") == "length":
            raise RuntimeError("Ответ модели оборван ограничением длины; результат не считается готовым.")
        return content.strip()

    def translate_to_russian(self, text: str, tradition: str = "Авто", cancelled: Callable[[], bool] | None = None, on_chunk: Callable[[str], None] | None = None, morphology: dict | None = None) -> str:
        """Translate only; preserve the source reading and never substitute it for a failed translation."""
        hints = []
        for token in (morphology or {}).get("tokens", []):
            if token.get("lemma"):
                features = ", ".join(f"{k}={v}" for k, v in token.get("features", {}).items())
                matches = "; ".join(str(m.get("lemma", "")) for m in token.get("corpus_matches", [])[:3])
                hints.append(f"{token.get('form')} → {token['lemma']} ({token.get('upos') or '?'}; {features or 'признаки не заданы'}; корпусные леммы: {matches or 'нет точного совпадения'})")
        morphology_context = "\n".join(hints[:64]) or "Модельный морфологический разбор отсутствует; не придумывай грамматические сведения."
        result = self._complete(
            "Переведи следующий исходный текст на современный русский язык, используя данные морфологического анализатора только как предварительные подсказки. "
            "Не переписывай и не исправляй оригинал, не дополняй отсутствующие слова. "
            "Сомнительные места явно пометь квадратными скобками. В конце, если есть реальные неоднозначности, добавь отдельный блок "
            "НЕОДНОЗНАЧНОСТИ: и для каждой укажи исходную форму, основной вариант и краткую альтернативу. Не придумывай варианты. "
            f"Традиция (если известна): {tradition}.\nПредварительные формы и леммы (автоматический разбор, может ошибаться):\n{morphology_context}\nВерни русский перевод, затем только при наличии неоднозначностей отдельный блок НЕОДНОЗНАЧНОСТИ. Не повторяй оригинал и не добавляй общего анализа.\n\nИсходный текст:\n{text}", cancelled, on_chunk,
        )
        if "<think>" in result:
            if "</think>" not in result:
                raise RuntimeError("Модель вернула только незавершённый внутренний черновик, а не перевод.")
            result = result.rsplit("</think>", 1)[-1].strip()
        self.last_translation_alternatives = []
        lines = result.splitlines()
        ambiguity_at = next((i for i, line in enumerate(lines) if line.strip().casefold().startswith("неоднозначност")), None)
        if ambiguity_at is not None:
            self.last_translation_alternatives = [line.strip(" -*\t") for line in lines[ambiguity_at + 1:] if line.strip(" -*\t")]
            result = "\n".join(lines[:ambiguity_at]).strip()
        if result.casefold().startswith("перевод:"):
            result = result.split(":", 1)[1].strip()
        if not result or result.strip() == text.strip():
            raise RuntimeError("Модель не сформировала перевод и повторила исходный текст.")
        return result

    def research_explanations(self, text: str, tradition: str = "Авто", cancelled: Callable[[], bool] | None = None, on_chunk: Callable[[str], None] | None = None) -> str:
        """Produce a separate cautious linguistic explanation, without pretending it is sourced research."""
        return self._complete(
            "Ты помощник по исторической славянской филологии. Дай краткое толкование "
            "грамматики и лексики исходного фрагмента. Разделяй наблюдение и гипотезу; "
            "не выдумывай источники, страницы, этимологии, датировку или точную реконструкцию. "
            "Если данных недостаточно, прямо укажи это. Это предварительная гипотеза, "
            "а не подтверждённое научное заключение. "
            f"Традиция (если известна): {tradition}.\n\n{text}", cancelled, on_chunk,
        )

    def analyze(self, text: str, tradition: str = "Авто", cancelled: Callable[[], bool] | None = None, on_update: Callable[[str, str], None] | None = None, *, deep: bool = False, morphology: dict | None = None) -> AnalysisResponse:
        """Keep stages independent: the diplomatic reading is the user's text; translation and interpretation are separate calls."""
        import time

        result = AnalysisResponse(reading=text)
        operations = [("translation", self.translate_to_russian)]
        if deep:
            operations.append(("explanation", self.research_explanations))
        for field, operation in operations:
            if cancelled and cancelled():
                raise InterruptedError("Анализ отменён пользователем")
            started = time.perf_counter()
            try:
                if field == "translation":
                    value = operation(text, tradition, cancelled, (lambda chunk, stage=field: on_update(stage, chunk)) if on_update else None, morphology)
                else:
                    value = operation(text, tradition, cancelled, (lambda chunk, stage=field: on_update(stage, chunk)) if on_update else None)
                if not value:
                    raise ValueError("Модель вернула пустой результат")
                setattr(result, field, value)
                if field == "translation":
                    result.translation_alternatives = list(self.last_translation_alternatives)
                raw = dict(self.last_generation_stats)
                eval_duration = float(raw.get("eval_duration", 0) or 0)
                prompt_duration = float(raw.get("prompt_eval_duration", 0) or 0)
                result.performance[field] = {
                    **raw,
                    "tokens_per_second": round(float(raw.get("eval_count", 0)) / (eval_duration / 1e9), 2) if eval_duration else 0.0,
                    "prompt_tokens_per_second": round(float(raw.get("prompt_eval_count", 0)) / (prompt_duration / 1e9), 2) if prompt_duration else 0.0,
                }
            except InterruptedError:
                raise
            except Exception as exc:
                result.component_errors[field] = str(exc)
            finally:
                result.timings_ms[field] = round((time.perf_counter() - started) * 1000)
        return result
