"""Historical OCR adapter for Kraken, with provenance kept per recognized line."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import json
import os
import time
import xml.etree.ElementTree as ET


@dataclass
class OCRLine:
    text: str
    page: int
    line: int
    bbox: tuple[int, int, int, int] | None = None
    confidence: float | None = None
    alternatives: list[str] | None = None


@dataclass(frozen=True)
class OCRModel:
    id: str
    name: str
    family: str
    target: str
    installed: bool
    license: str
    note: str


OCR_MODELS = (
    OCRModel("kraken-cyr02", "Kraken · Cyr02full", "Kraken", "устав и полуустав, XI–XVI вв.", True, "CC BY 2.0", "Встроенная модель; обрабатывает страницы по очереди."),
    OCRModel("crnn-church-slavonic", "CRNN-CTC · церковнославянский", "PyTorch", "рукопись, отдельная строка", True, "Apache-2.0", "Около 41 МБ; для целой страницы сначала нужна сегментация строк."),
    OCRModel("crnn-prosta-mova", "CRNN-CTC · Prosta Mova", "PyTorch", "старопечатные восточнославянские книги", True, "Apache-2.0", "Около 41 МБ; модель не универсальна для печатного церковнославянского текста."),
    OCRModel("trocr-church-slavonic", "TrOCR · церковнославянский", "Transformers", "рукопись, отдельная строка", False, "Apache-2.0", "Требует отдельный стек Transformers и веса модели."),
    OCRModel("lighton-ocs-line", "LightOnOCR · OCS line", "Transformers/VLM", "рукописная строка", False, "Apache-2.0", "Только заранее вырезанная строка; не готов к автономному MPS-пайплайну."),
)


def ocr_catalog() -> tuple[OCRModel, ...]:
    """Catalog metadata only; this does not load or download any weights."""
    return OCR_MODELS


def classify_document_type(image: Path) -> tuple[str, str]:
    """Conservative placeholder classifier: do not guess print vs handwriting without a validated classifier."""
    if not image.is_file():
        return "unknown", "Файл изображения не найден."
    return "unknown", "Тип письма автоматически не подтверждён; выберите движок вручную и проверьте результат."


def parse_kraken_xml(path: Path, page: int = 0) -> list[OCRLine]:
    """Read either ALTO or PAGE XML output without normalizing recognized Unicode."""
    root = ET.parse(path).getroot()
    rows: list[OCRLine] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "TextLine":
            continue
        strings = [x for x in element.iter() if x.tag.rsplit("}", 1)[-1] == "String"]
        text_parts: list[str] = []
        confidences: list[float] = []
        for item in strings:
            value = item.attrib.get("CONTENT")
            if value is None:
                value = item.attrib.get("content", "")
            text_parts.append(value)
            try:
                confidences.append(float(item.attrib.get("WC", item.attrib.get("conf", ""))))
            except ValueError:
                pass
        if not text_parts:
            text_parts = [(x.text or "") for x in element.iter() if x.tag.rsplit("}", 1)[-1] == "Unicode"]
        text = " ".join(part for part in text_parts if part).strip()
        if not text:
            continue
        bbox = None
        shape = next((x for x in element if x.tag.rsplit("}", 1)[-1] in {"Shape", "Coords"}), None)
        if shape is not None:
            points = shape.attrib.get("POINTS") or shape.attrib.get("points", "")
            coords = [(int(float(x)), int(float(y))) for x, y in re.findall(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", points)]
            if coords:
                xs, ys = zip(*coords)
                bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        if bbox is None:
            attrs = {k.rsplit("}", 1)[-1].upper(): v for k, v in element.attrib.items()}
            try:
                bbox = (int(float(attrs["HPOS"])), int(float(attrs["VPOS"])), int(float(attrs["WIDTH"])), int(float(attrs["HEIGHT"])))
            except (KeyError, ValueError):
                bbox = None
        rows.append(OCRLine(text=text, page=page, line=len(rows), bbox=bbox, confidence=sum(confidences) / len(confidences) if confidences else None))
    return rows


def recognize_page(image: Path, model: Path, xml_out: Path, *, device: str = "mps", executable: Path | None = None) -> list[OCRLine]:
    """Run Kraken's baseline segmentation and historical recognition sequentially."""
    kraken = Path(executable) if executable else None
    if kraken and kraken.name == "paleoslov-ocr":
        command = [str(kraken), str(image), str(xml_out), str(model), device]
    else:
        command = [str(kraken or "kraken"), "--device", device, "-i", str(image), str(xml_out), "-a", "segment", "-bl", "ocr", "-m", str(model)]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if proc.returncode:
        details = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(details[-4000:] or f"Kraken завершился с кодом {proc.returncode}")
    if not xml_out.exists():
        raise RuntimeError("Kraken не создал файл разметки строк.")
    return parse_kraken_xml(xml_out)


def recognize_pages(images: list[Path], model: Path, outputs: list[Path], *, device: str, executable: Path, metrics: dict | None = None) -> list[list[OCRLine]]:
    """Recognize a full multipage document in one worker launch to avoid repeated model loading."""
    requested_device = device
    manifest = outputs[0].parent / "jobs.json"
    metrics_path = outputs[0].parent / "ocr-metrics.json"
    jobs = [{"image": str(a), "xml": str(b)} for a, b in zip(images, outputs)]

    def invoke(on_device: str):
        env = os.environ.copy()
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        if executable.name != "paleoslov-ocr":
            for image, output in zip(images, outputs):
                proc = subprocess.run([str(executable), "--device", on_device, "-i", str(image), str(output), "-a", "segment", "-bl", "ocr", "-m", str(model)], capture_output=True, text=True, timeout=900, env=env)
                if proc.returncode:
                    details = (proc.stderr or proc.stdout).strip()
                    raise RuntimeError(details[-4000:] or f"Kraken завершился с кодом {proc.returncode}")
        else:
            manifest.write_text(json.dumps({"jobs": jobs, "metrics": str(metrics_path)}), encoding="utf-8")
            proc = subprocess.run([str(executable), str(manifest), str(model), on_device], capture_output=True, text=True, timeout=1800, env=env)
            if proc.returncode:
                details = (proc.stderr or proc.stdout).strip()
                raise RuntimeError(details[-4000:] or f"OCR завершился с кодом {proc.returncode}")
        if not all(output.exists() for output in outputs):
            raise RuntimeError("OCR не создал разметку для одной или нескольких страниц.")

    actual_device = requested_device
    try:
        invoke(actual_device)
    except Exception:
        if requested_device != "mps":
            raise
        for output in outputs:
            output.unlink(missing_ok=True)
        invoke("cpu")
        actual_device = "cpu (резерв после ошибки MPS)"
    if metrics is not None:
        metrics["device"] = actual_device
        if metrics_path.exists():
            try:
                metrics.update(json.loads(metrics_path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
    return [parse_kraken_xml(output, page=i) for i, output in enumerate(outputs)]


def recognize_image(image: Path, model: Path, output: Path, *, device: str, executable: Path) -> dict:
    """Structured OCR stage result; input/output text is retained without Unicode normalization."""
    started = time.perf_counter()
    metrics: dict = {}
    lines = recognize_pages([image], model, [output], device=device, executable=executable, metrics=metrics)[0]
    return {
        "engine": "Kraken · Cyr02full_best",
        "image": str(image),
        "lines": [line.__dict__ for line in lines],
        "text": "\n".join(line.text for line in lines),
        "normalization": "не применялась",
        "elapsed_ms": metrics.get("elapsed_ms", round((time.perf_counter() - started) * 1000)),
        "peak_memory_mb": metrics.get("peak_memory_mb"),
        "device": metrics.get("device", device),
        "document_type": classify_document_type(image)[0],
        "alternatives": [],
    }
