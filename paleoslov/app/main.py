from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from html import escape
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt, QSize
from PySide6.QtGui import QAction, QFont, QTextCursor, QImageReader, QPixmap, QPainter, QPen, QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QListWidget, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QPlainTextEdit, QSplitter, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout,
    QWidget, QInputDialog, QMenu, QFrame, QScrollArea,
)

from paleoslov import __version__
from paleoslov.core.linguistics import parse_conllu, selected_token
from paleoslov.core.corpus import TOROT_LICENSE, TOROT_SOURCE_URL
from paleoslov.core.research import ResearchService
from paleoslov.core.storage import Store
from paleoslov.core.text import detect_tradition
from paleoslov.core.historical_ocr import OCRLine, ocr_catalog, recognize_image, recognize_pages
from paleoslov.core.historical_morphology import HistoricalMorphology
from paleoslov.core.lexicon import lexical_lookup
from paleoslov.core.pipeline import analyze_morphology, detect_historical_features


LIGHT_QSS = """
QMainWindow, QWidget { background:#f0e4c9; color:#30251d; font-family:'Baskerville','Times New Roman'; font-size:14px; }
QLabel#eyebrow { color:#67785e; letter-spacing:1px; font-size:11px; }
QLabel#title { color:#30251d; font-size:31px; font-weight:600; }
QLabel#section { color:#8c3534; font-size:17px; font-weight:600; }
QPlainTextEdit, QTextEdit, QTextBrowser, QListWidget, QLineEdit { background:#fbf7ed; border:1px solid #d1c3a4; border-radius:9px; padding:10px; selection-background-color:#b08a4c; }
QPushButton { background:#8c3534; color:#fff8e9; border:0; border-radius:9px; padding:9px 16px; font-weight:600; }
QPushButton:hover { background:#71302e; }
QPushButton:disabled { background:#b8a894; }
QPushButton#quiet { background:transparent; color:#675a4c; border:1px solid #c9b999; }
QComboBox { background:#fbf7ed; border:1px solid #d1c3a4; border-radius:8px; padding:7px; }
QTabWidget::pane { border:1px solid #d1c3a4; border-radius:10px; }
QTabBar::tab { background:#e8dcc1; padding:9px 14px; margin-right:3px; border-top-left-radius:8px; border-top-right-radius:8px; }
QTabBar::tab:selected { background:#fbf7ed; color:#8c3534; }
QSplitter::handle { background:#d1c3a4; width:2px; }
QProgressBar { border:0; background:#e0d3b6; border-radius:4px; height:7px; text-align:center; }
QProgressBar::chunk { background:#67785e; border-radius:4px; }
"""


class AnalyzeWorker(QThread):
    done = Signal(dict)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(str, str)

    def __init__(self, text: str, tradition: str, corpus_path: Path | None = None, morphology_dir: Path | None = None):
        super().__init__()
        self.text, self.tradition, self.corpus_path, self.morphology_dir = text, tradition, corpus_path, morphology_dir

    def run(self):
        try:
            label, confidence = detect_tradition(self.text) if self.tradition == "Автоматически" else (self.tradition, "не оценивалась")
            features = detect_historical_features(self.text)
            lookup = None
            store = None
            if self.corpus_path and self.corpus_path.exists():
                store = Store(self.corpus_path)
                lookup = store.find_forms
            morphology_engine = HistoricalMorphology(self.morphology_dir) if self.morphology_dir else None
            morphology = analyze_morphology(self.text, lookup, morphology_engine, label)
            result = {
                "tradition": label,
                "confidence": confidence,
                "observations": features.value["observations"],
                "historical_reviews": features.value["yat_jer_reviews"],
                "reading": "",
                "translation": "",
                "explanation": "",
                "normalization": {"source": self.text, "reading": "", "changed": False, "method": "отдельное прочтение не сформировано; исходный текст сохранён без изменений"},
                "translation_status": "Автоматический перевод отключён в этой версии.",
                "explanation_status": "Автоматическое толкование отключено в этой версии.",
                "morphology": morphology.value,
                "timings_ms": {"morphology": morphology.elapsed_ms, "historical_features": features.elapsed_ms},
            }
            if store:
                store.close()
            self.done.emit(result)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class ResearchWorker(QThread):
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, query: str, cache_db: Path | None = None):
        super().__init__()
        self.query, self.cache_db = query, cache_db

    def run(self):
        try:
            self.done.emit(ResearchService().search(self.query, cache_db=self.cache_db))
        except Exception as exc:
            self.failed.emit(str(exc))


class OCRWorker(QThread):
    done = Signal(list, dict)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, pages: list[Path], model: Path, executable: Path, device: str = "auto", engine: str = "kraken-cyr02", project_root: Path | None = None, model_base: Path | None = None):
        super().__init__()
        self.pages, self.model, self.executable, self.device = pages, model, executable, device
        self.engine, self.project_root, self.model_base = engine, project_root, model_base

    def run(self):
        rows = []
        import time
        started = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix="paleoslov-ocr-") as td:
                temp = Path(td)
                if self.engine in {"crnn-church-slavonic", "crnn-prosta-mova"}:
                    output = temp / "crnn-result.json"
                    manifest = temp / "jobs.json"
                    if not self.model_base:
                        raise RuntimeError("Папка CRNN-моделей не настроена.")
                    manifest.write_text(json.dumps({"images": [str(x) for x in self.pages], "model": self.engine, "output": str(output)}, ensure_ascii=False), encoding="utf-8")
                    if getattr(sys, "frozen", False):
                        contents = Path(sys.executable).resolve().parent.parent
                        worker_candidates = [
                            contents / "Frameworks" / "crnn-worker" / "paleoslov-crnn",
                            contents / "Resources" / "crnn-worker" / "paleoslov-crnn",
                        ]
                        worker = next((item for item in worker_candidates if item.is_file()), worker_candidates[0])
                        if not worker.is_file():
                            raise RuntimeError("В приложении отсутствует встроенный CRNN worker.")
                        command = [str(worker), str(manifest), str(self.model_base), self.device if self.device != "auto" else "cpu"]
                    else:
                        python = (self.project_root or Path.cwd()) / ".venv-ocr" / "bin" / "python"
                        command = [str(python), "-m", "paleoslov.crnn_worker", str(manifest), str(self.model_base), self.device if self.device != "auto" else "cpu"]
                    proc = subprocess.run(command, cwd=str(self.project_root or Path.cwd()), capture_output=True, text=True, timeout=1800)
                    if proc.returncode:
                        raise RuntimeError((proc.stderr or proc.stdout).strip()[-4000:] or "CRNN worker завершился с ошибкой.")
                    data = json.loads(output.read_text(encoding="utf-8"))
                    for page_no, lines in enumerate(data.get("pages", [])):
                        for line in lines:
                            rows.append(OCRLine(line["text"], page_no, line["line"], tuple(line["bbox"]), line.get("confidence")))
                    self.done.emit(rows, {"device": data.get("device", "cpu"), "elapsed_ms": data.get("elapsed_ms", round((time.perf_counter() - started) * 1000)), "peak_memory_mb": data.get("peak_memory_mb"), "engine": data.get("engine", self.engine), "model_license": data.get("model_license", "Apache-2.0"), "model_size_mb": round(self.model.stat().st_size / (1024 * 1024), 1), "warning": data.get("warning")})
                    return
                xmls = [temp / f"page-{i:04}.xml" for i in range(len(self.pages))]
                device = self.device
                # Kraken's current CLI does not complete this model's MPS path on this Mac;
                # keep the validated CPU path as Auto until end-to-end MPS passes.
                if device == "auto":
                    device = "cpu"
                if len(self.pages) == 1:
                    single = recognize_image(self.pages[0], self.model, xmls[0], device=device, executable=self.executable)
                    pages = [[OCRLine(**line) for line in single["lines"]]]
                    runtime_metrics = single
                else:
                    runtime_metrics = {}
                    pages = recognize_pages(self.pages, self.model, xmls, device=device, executable=self.executable, metrics=runtime_metrics)
                for i, lines in enumerate(pages):
                    rows.extend(OCRLine(x.text, i, x.line, x.bbox, x.confidence, x.alternatives) for x in lines)
                    self.progress.emit(i + 1, len(self.pages))
            self.done.emit(rows, {"device": runtime_metrics.get("device", device), "elapsed_ms": runtime_metrics.get("elapsed_ms", round((time.perf_counter() - started) * 1000)), "peak_memory_mb": runtime_metrics.get("peak_memory_mb"), "engine": "Kraken · Cyr02full_best", "model_size_mb": round(self.model.stat().st_size / (1024 * 1024), 1)})
        except Exception as exc:
            self.failed.emit(str(exc))


class ImportWorker(QThread):
    done = Signal(str, object)
    failed = Signal(str)

    def __init__(self, source: Path, destination: Path):
        super().__init__()
        self.source, self.destination = source, destination

    def run(self):
        try: self.done.emit(str(self.source), render_source(self.source, self.destination))
        except Exception as exc: self.failed.emit(str(exc))


class ImagePreview(QWidget):
    lineClicked = Signal(int)

    def __init__(self):
        super().__init__()
        self.image = QPixmap()
        self.lines: list[OCRLine] = []
        self.page = 0
        self.selected = -1
        self.setMinimumSize(320, 360)
        self.setMouseTracking(True)

    def set_page(self, image_path: Path | None, page: int, lines: list[OCRLine]):
        self.image = QPixmap(str(image_path)) if image_path else QPixmap()
        self.page, self.lines, self.selected = page, lines, -1
        self.update()

    def select_line(self, line: int):
        self.selected = line
        self.update()

    def _rect(self):
        if self.image.isNull(): return None
        scaled = self.image.size().scaled(self.size() - QSize(20, 20), Qt.AspectRatioMode.KeepAspectRatio)
        return (self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2, scaled.width(), scaled.height()

    def paintEvent(self, event):
        p = QPainter(self); p.fillRect(self.rect(), QColor("#e9dcc0"))
        rect = self._rect()
        if not rect:
            p.setPen(QColor("#7b6b55")); p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Перетащите скан сюда\nили откройте файл")
            return
        x, y, w, h = rect
        p.drawPixmap(x, y, w, h, self.image)
        iw, ih = self.image.width(), self.image.height()
        sx, sy = w / max(1, iw), h / max(1, ih)
        for line in self.lines:
            if line.page != self.page or not line.bbox: continue
            bx, by, bw, bh = line.bbox
            p.setPen(QPen(QColor("#c0463b") if line.line == self.selected else QColor(170, 105, 32, 170), 2 if line.line == self.selected else 1))
            p.drawRect(x + bx * sx, y + by * sy, bw * sx, bh * sy)

    def mousePressEvent(self, event):
        rect = self._rect()
        if not rect or self.image.isNull(): return
        x, y, w, h = rect
        px, py = event.position().x(), event.position().y()
        if not (x <= px <= x + w and y <= py <= y + h): return
        ix = (px - x) * self.image.width() / w
        iy = (py - y) * self.image.height() / h
        for line in self.lines:
            if line.page == self.page and line.bbox:
                bx, by, bw, bh = line.bbox
                if bx <= ix <= bx + bw and by <= iy <= by + bh:
                    self.selected = line.line; self.update(); self.lineClicked.emit(line.line); break


class OCRHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.uncertain: set[int] = set()
        self.format = QTextCharFormat(); self.format.setBackground(QColor("#f2d6ce"))

    def set_lines(self, lines: list[OCRLine]):
        self.uncertain = {i for i, line in enumerate(lines) if line.confidence is not None and line.confidence < 0.8}
        self.rehighlight()

    def highlightBlock(self, text: str):
        if self.currentBlock().blockNumber() in self.uncertain:
            self.setFormat(0, len(text), self.format)


def render_source(path: Path, destination: Path) -> list[Path]:
    """Render PDF pages or decode image/multipage TIFF into stable PNG page files."""
    destination.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(path))
        output = []
        for i in range(len(doc)):
            page = doc[i]
            target = destination / f"page-{i+1:04}.png"
            # 3 px per PDF point (~216 dpi) gives small historical glyphs
            # enough room for line segmentation without claiming to restore detail.
            page.render(scale=3).to_pil().save(target, format="PNG"); output.append(target)
            page.close()
        doc.close()
        return output
    reader = QImageReader(str(path)); reader.setAutoTransform(True)
    output = []
    i = 0
    while True:
        image = reader.read()
        if image.isNull():
            if i == 0: raise RuntimeError(reader.errorString() or "Не удалось открыть изображение")
            break
        target = destination / f"page-{i+1:04}.png"
        if not image.save(str(target), "PNG"):
            raise RuntimeError(f"Не удалось подготовить страницу {i+1}")
        output.append(target); i += 1
        if not reader.jumpToNextImage(): break
    return output


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        if getattr(sys, "frozen", False):
            bundle_root = Path(sys.executable).resolve().parents[2]
            nearby_project = bundle_root.parent
            if (nearby_project / "pyproject.toml").exists():
                app_root = nearby_project
                app_data = app_root / "data"
            else:
                app_root = bundle_root
                app_data = Path.home() / "Library" / "Application Support" / "Палеослов"
        else:
            app_root = Path(__file__).resolve().parents[2]
            app_data = app_root / "data"
        app_data.mkdir(parents=True, exist_ok=True)
        self.data_dir = app_data
        self.store = Store(app_data / "paleoslov.sqlite3")
        if getattr(sys, "frozen", False) and self.store.db.execute("SELECT count(*) FROM corpus_tokens").fetchone()[0] == 0:
            corpus = Path(sys.executable).resolve().parent.parent / "Resources" / "corpora" / "orv_torot-ud-train.conllu"
            if corpus.is_file():
                rows = parse_conllu(corpus.read_text(encoding="utf-8"))
                self.store.import_conllu("UD Old East Slavic TOROT (train)", "CC BY-NC-SA 4.0", TOROT_SOURCE_URL, rows)
        self.current_result: dict = {}
        self.current_doc_id: int | None = None
        self.current_doc_title = ""
        self.source_path: Path | None = None
        self.page_paths: list[Path] = []
        self.ocr_lines: list[OCRLine] = []
        self.current_page = 0
        self.project_root = app_root
        self.morphology_dir = (Path(sys.executable).resolve().parent.parent / "Resources" / "models" / "udpipe") if getattr(sys, "frozen", False) else (app_root / "data" / "models" / "udpipe")
        self.setWindowTitle(f"Палеослов · цифровой скрипторий {__version__}")
        self.resize(1440, 940)
        self.setMinimumSize(1050, 700)
        self.setStyleSheet(LIGHT_QSS)
        self._build_menu()
        self._build_ui()
        self.refresh_history()
        self.status.setText("Локальный анализ без генеративных моделей")

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("Файл")
        actions = [("Открыть рукопись / PDF…", self.open_manuscript), ("Вставить изображение из буфера", self.paste_image), ("Открыть текст…", self.open_text), ("Импорт CoNLL-U…", self.import_conllu), ("Экспорт Markdown…", self.export_markdown), ("Экспорт JSON…", self.export_json)]
        for title, callback in actions:
            action = QAction(title, self)
            action.triggered.connect(callback)
            file_menu.addAction(action)

    def _build_ui(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 16, 24, 18)
        mast = QHBoxLayout()
        lefthead = QVBoxLayout()
        eyebrow = QLabel("ФИЛОЛОГИЧЕСКИЙ ИНСТРУМЕНТ · ЛОКАЛЬНАЯ РАБОТА")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Палеослов")
        title.setObjectName("title")
        subtitle = QLabel("Цифровой скрипторий для исторических славянских текстов")
        lefthead.addWidget(eyebrow); lefthead.addWidget(title); lefthead.addWidget(subtitle)
        mast.addLayout(lefthead); mast.addStretch()
        self.status = QLabel("Локальный анализ без генеративных моделей")
        mast.addWidget(self.status)
        outer.addLayout(mast)

        toolbar = QHBoxLayout()
        self.tradition = QComboBox()
        self.tradition.addItems(["Автоматически", "Древнерусский", "Старославянский", "Церковнославянский", "Неопределённая / смешанная"])
        self.mode = QComboBox(); self.mode.addItems(["Быстрый анализ", "Углублённое исследование"])
        self.analyze_btn = QPushButton("Разобрать текст")
        self.analyze_btn.clicked.connect(self.analyze)
        self.cancel_btn = QPushButton("Остановить"); self.cancel_btn.setObjectName("quiet"); self.cancel_btn.setEnabled(False); self.cancel_btn.clicked.connect(self.cancel_analysis)
        self.save_btn = QPushButton("Сохранить разбор"); self.save_btn.setObjectName("quiet"); self.save_btn.clicked.connect(self.save_result)
        toolbar.addWidget(QLabel("Традиция")); toolbar.addWidget(self.tradition); toolbar.addSpacing(14)
        toolbar.addWidget(self.mode); toolbar.addStretch(); toolbar.addWidget(self.save_btn); toolbar.addWidget(self.cancel_btn); toolbar.addWidget(self.analyze_btn)
        outer.addLayout(toolbar)

        manuscript_tools = QHBoxLayout()
        self.open_image_btn = QPushButton("Открыть рукопись"); self.open_image_btn.clicked.connect(self.open_manuscript)
        self.paste_image_btn = QPushButton("Вставить снимок"); self.paste_image_btn.setObjectName("quiet"); self.paste_image_btn.clicked.connect(self.paste_image)
        self.run_ocr_btn = QPushButton("Распознать строки"); self.run_ocr_btn.clicked.connect(self.run_ocr)
        self.page_selector = QComboBox(); self.page_selector.setMinimumWidth(110); self.page_selector.currentIndexChanged.connect(self.change_page)
        manuscript_tools.addWidget(self.open_image_btn); manuscript_tools.addWidget(self.paste_image_btn); manuscript_tools.addWidget(self.run_ocr_btn); manuscript_tools.addStretch(); manuscript_tools.addWidget(self.page_selector)
        outer.addLayout(manuscript_tools)

        split = QSplitter(Qt.Orientation.Horizontal)
        manuscript = QWidget(); ml = QVBoxLayout(manuscript); ml.setContentsMargins(0, 8, 8, 0)
        label = QLabel("Рукопись · нажмите строку для сверки"); label.setObjectName("section"); ml.addWidget(label)
        self.image_preview = ImagePreview(); ml.addWidget(self.image_preview, 1)

        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(8, 8, 8, 0)
        label = QLabel("Дипломатическая транскрипция"); label.setObjectName("section"); ll.addWidget(label)
        self.editor = QPlainTextEdit(); self.editor.setPlaceholderText("Откройте фотографию или PDF и нажмите «Распознать строки». Проверяйте каждую строку по изображению; написание не нормализуется автоматически.")
        self.editor.setFont(QFont("Baskerville", 16)); self.ocr_highlighter = OCRHighlighter(self.editor.document()); ll.addWidget(self.editor, 1)
        symbolrow = QHBoxLayout()
        symbolrow.addWidget(QLabel("Исторические знаки:"))
        for symbol in "ѣ Ѣ ѫ Ѫ ѧ Ѧ ѳ Ѳ ѵ Ѵ ѥ ѩ ѭ".split():
            b = QPushButton(symbol); b.setObjectName("quiet"); b.setFixedWidth(42)
            b.clicked.connect(lambda checked=False, s=symbol: self.editor.insertPlainText(s))
            symbolrow.addWidget(b)
        ll.addLayout(symbolrow)

        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(10, 8, 0, 0)
        self.tabs = QTabWidget()
        self.reading = QTextBrowser(); self.translation = QTextBrowser(); self.translation.setOpenExternalLinks(True); self.explanation = QTextBrowser()
        self.reading.setHtml("<span style='color:#8b7c65'>Сначала вставьте фрагмент слева и нажмите «Разобрать текст». Исходное написание останется без изменений.</span>")
        self.translation.setHtml("<span style='color:#8b7c65'>Автоматический перевод отключён в этой сборке. Приложение не подставляет исходный текст или ответ языковой модели вместо перевода. Ранее сохранённые переводы остаются в истории.</span>")
        self.explanation.setHtml("<span style='color:#8b7c65'>Генеративное толкование отключено. Здесь показываются локальные морфологические и графические наблюдения с указанием их ограничений.</span>")
        self.tabs.addTab(self.reading, "Прочтение")
        self.tabs.addTab(self.translation, "Перевод · недоступен")
        self.tabs.addTab(self.explanation, "Толкование")
        rl.addWidget(self.tabs, 1)
        self.word_card = QTextBrowser(); self.word_card.setMaximumHeight(210); self.word_card.setPlaceholderText("Выберите слово в оригинале, чтобы увидеть сведения о форме")
        rl.addWidget(self.word_card)
        split.addWidget(manuscript); split.addWidget(left); split.addWidget(right); split.setSizes([520, 520, 600])

        lower = QTabWidget(); lower.setMaximumHeight(210)
        self.phenomena = QTextBrowser(); self.phenomena.setOpenExternalLinks(True); lower.addTab(self.phenomena, "Исторические явления")
        self.grammar = QTextBrowser(); lower.addTab(self.grammar, "Грамматика")
        self.sources = QTextBrowser(); lower.addTab(self.sources, "Источники и исследование")
        self.phenomena.setHtml("<span style='color:#8b7c65'>После анализа здесь появятся отмеченные графические особенности и предупреждения о том, что по ним нельзя заключать автоматически.</span>")
        self.grammar.setHtml("<span style='color:#8b7c65'>Выберите «Древнерусский» или «Старославянский», затем разберите текст. Модельный разбор будет отделён от корпусных совпадений.</span>")
        self.sources.setHtml("<span style='color:#8b7c65'>В режиме углублённого исследования можно искать библиографические записи OpenAlex и Crossref. Карточка публикации сама по себе не подтверждает вывод.</span>")
        self.history_list = QListWidget(); self.history_list.itemDoubleClicked.connect(self.load_history_item); lower.addTab(self.history_list, "История разборов")
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.history_menu)
        self.settings_page = self._settings_widget(); lower.addTab(self.settings_page, "Настройки")
        self.statusline = QLabel("Готово · локальные наблюдения не заменяют научную проверку")
        self.progress = QProgressBar(); self.progress.setRange(0, 1); self.progress.setValue(0); self.progress.setMaximumHeight(8)
        self.progress.setTextVisible(False)
        outer.addWidget(split, 1); outer.addWidget(lower); outer.addWidget(self.progress); outer.addWidget(self.statusline)
        self.setCentralWidget(root)
        self.editor.selectionChanged.connect(self.show_selected_word)
        self.editor.cursorPositionChanged.connect(self.sync_text_cursor_to_image)
        self.image_preview.lineClicked.connect(self.sync_image_line_to_text)
        self.setAcceptDrops(True)

    def _settings_widget(self):
        pane = QWidget(); layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        install = QLabel("Автоматический перевод и генеративное толкование отключены. Текст не отправляется в Ollama и не передаётся языковой модели. Словарные ссылки и библиографические записи показываются с явным указанием происхождения.")
        install.setWordWrap(True)
        layout.addWidget(install)
        layout.addWidget(QLabel("Распознавание текста"))
        ocr_row = QHBoxLayout()
        self.ocr_engine_combo = QComboBox()
        self.ocr_engine_combo.addItem("Автовыбор · установленный движок", "auto")
        catalog = ocr_catalog()
        self.ocr_engine_combo.addItem("Kraken · Cyr02full (установлена)", "kraken-cyr02")
        for index, model in enumerate(catalog):
            if model.id == "kraken-cyr02":
                continue
            self.ocr_engine_combo.addItem(f"{model.name} · {'в комплекте' if model.installed else 'не установлена'}", model.id)
            item = self.ocr_engine_combo.model().item(self.ocr_engine_combo.count() - 1)
            if item and not model.installed:
                item.setEnabled(False)
                item.setToolTip(model.note)
        self.ocr_device_combo = QComboBox()
        self.ocr_device_combo.addItem("Авто · проверенный CPU-режим", "auto")
        self.ocr_device_combo.addItem("CPU", "cpu")
        self.ocr_device_combo.addItem("Apple MPS · экспериментально", "mps")
        ocr_row.addWidget(self.ocr_engine_combo, 2)
        ocr_row.addWidget(self.ocr_device_combo, 1)
        layout.addLayout(ocr_row)
        ocr_choice_note = QLabel("Авто использует Kraken на CPU. CRNN — отдельные строковые модели: сначала строки выделяются Kraken HPP, затем распознаются выбранной CRNN. Для CRNN проверен CPU; MPS остаётся экспериментальным. Точность на конкретном памятнике оценивайте по исходному изображению.")
        ocr_choice_note.setWordWrap(True)
        layout.addWidget(ocr_choice_note)
        corpus_info = QLabel("Корпус древнерусского языка TOROT включён в приложение и подготовлен для поиска без интернета. Лицензия CC BY-NC-SA 4.0; источник и атрибуция указаны в комплекте.")
        corpus_info.setWordWrap(True)
        layout.addWidget(corpus_info)
        ocr_info = QLabel("Доступны Kraken/Cyr02full (старый устав и полуустав), CRNN Church Slavonic (рукописная церковнославянская строка) и CRNN Prosta Mova (старопечатная восточнославянская строка). Обе CRNN требуют сегментации; результаты на разных почерках и шрифтах будут отличаться. Авто не угадывает традицию по одному символу.")
        ocr_info.setWordWrap(True)
        layout.addWidget(ocr_info)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(pane)
        return scroll

    def _plain(self, value: str) -> str:
        return escape(value).replace("\n", "<br>")

    def show_selected_word(self):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            return
        text = self.editor.toPlainText()
        tok = selected_token(text, cursor.selectionStart(), cursor.selectionEnd())
        if tok:
            morphology = self.current_result.get("morphology", {})
            rows = morphology.get("tokens", []) if isinstance(morphology, dict) else []
            parsed = next((x for x in rows if x.get("start") == tok.start and x.get("end") == tok.end), None)
            corpus_matches = self.store.find_forms(tok.text)
            lexical = lexical_lookup(tok.text, self.current_result.get("tradition", "Автоматически"),
                                     [parsed] if parsed else [], [dict(x) for x in corpus_matches])
            body = f"<b>Словоформа:</b> {self._plain(tok.text)} &nbsp; <span style='color:#67785e'>символы {tok.start}–{tok.end}</span>"
            if parsed and parsed.get("lemma"):
                feats = ", ".join(f"{self._plain(k)}={self._plain(v)}" for k, v in parsed.get("features", {}).items()) or "грамматические признаки не назначены"
                body += f"<br><br><b>UDPipe · модельный разбор:</b> лемма <b>{self._plain(parsed['lemma'])}</b>; {self._plain(parsed.get('upos') or 'часть речи не определена')}; {feats}; связь: {self._plain(parsed.get('deprel') or 'не определена')}"
                body += "<br><i>Автоматическая гипотеза; сверяйте с изданием памятника.</i>"
            elif morphology.get("warning"):
                body += f"<br><br><i>{self._plain(morphology['warning'])}</i>"
            body += f"<br><br><b>Лексикон</b><br>{self._plain(lexical['meaning_status'])}"
            if lexical["candidates"]:
                candidates = []
                for item in lexical["candidates"][:12]:
                    features = item.get("features") or {}
                    if isinstance(features, dict):
                        features = ", ".join(f"{k}={v}" for k, v in features.items()) or "признаки не указаны"
                    candidates.append(f"{self._plain(item['lemma'])} · {self._plain(item.get('part_of_speech') or 'часть речи не определена')} · {self._plain(str(features))} · {self._plain(item['source'])}")
                body += "<br><br><b>Контекстные кандидаты</b> (модель/корпус, не словарное значение):<br>" + "<br>".join(candidates)
            body += "<br><br><b>Проверить словарную статью</b> (внешние научные ресурсы):"
            for source in lexical["dictionary_sources"]:
                url = escape(source["url"], quote=True)
                body += f"<br><a href='{url}'>{self._plain(source['title'])}</a> · {self._plain(source['scope'])}"
            if lexical["candidates"]:
                body += f"<br><span style='color:#67785e'>Искать лемму: {self._plain(lexical['candidates'][0]['lemma'])}</span>"
            else:
                body += f"<br><span style='color:#67785e'>Искать форму: {self._plain(tok.text)}</span>"
            specific = [x for x in self.current_result.get("observations", []) if x.get("token_start") == tok.start and x.get("token_end") == tok.end]
            for item in specific:
                body += f"<br><br><b>{self._plain(item.get('label','Историческое наблюдение'))}</b> · {self._plain(item.get('evidence_status',''))}<br>{self._plain(item.get('detail',''))}"
                for source in item.get("sources", []):
                    url = escape(source.get("url", ""), quote=True)
                    title = self._plain(source.get("title", "Научный источник"))
                    body += f"<br><a href='{url}'>{title}</a> · {self._plain(source.get('passage',''))}"
            self.word_card.setHtml(body)

    def open_manuscript(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть рукопись или скан", str(Path.home()), "Изображения и документы (*.png *.jpg *.jpeg *.tif *.tiff *.webp *.heic *.heif *.pdf);;Все файлы (*)")
        if path: self.load_manuscript(Path(path))

    def load_manuscript(self, path: Path):
        if hasattr(self, "ocr_worker") and self.ocr_worker.isRunning():
            self.statusline.setText("Дождитесь окончания распознавания документа")
            return
        if hasattr(self, "import_worker") and self.import_worker.isRunning():
            self.statusline.setText("Дождитесь окончания подготовки открытого документа")
            return
        folder = self.data_dir / "manuscripts" / uuid.uuid4().hex
        self.open_image_btn.setEnabled(False); self.paste_image_btn.setEnabled(False); self.run_ocr_btn.setEnabled(False)
        self.progress.setRange(0, 0); self.statusline.setText("Подготавливаю страницы локально…")
        self.import_worker = ImportWorker(path, folder)
        self.import_worker.done.connect(self.manuscript_loaded); self.import_worker.failed.connect(self.manuscript_import_failed)
        self.import_worker.start()

    def manuscript_loaded(self, source: str, pages: list[Path]):
        path = Path(source)
        self.source_path = path
        self.page_paths = pages
        self.ocr_lines = []
        self.page_selector.blockSignals(True); self.page_selector.clear()
        for i in range(len(pages)): self.page_selector.addItem(f"Страница {i+1}", i)
        self.page_selector.setEnabled(len(pages) > 1)
        self.page_selector.blockSignals(False); self.page_selector.setCurrentIndex(0)
        self.current_page = 0
        self.image_preview.set_page(pages[0], 0, [])
        self.editor.clear()
        self.ocr_highlighter.set_lines([])
        self.current_doc_id = None; self.current_doc_title = path.stem; self.current_result = {}
        from PySide6.QtGui import QImage
        image = QImage(str(pages[0]))
        self.statusline.setText(f"Загружено страниц: {len(pages)} · {image.width()}×{image.height()} пикселей · исходный файл не изменён")
        self.tabs.setCurrentIndex(0)
        self.open_image_btn.setEnabled(True); self.paste_image_btn.setEnabled(True); self.run_ocr_btn.setEnabled(True)
        self.progress.setRange(0, 1); self.progress.setValue(1)

    def manuscript_import_failed(self, error: str):
        self.open_image_btn.setEnabled(True); self.paste_image_btn.setEnabled(True); self.run_ocr_btn.setEnabled(True)
        self.progress.setRange(0, 1); self.progress.setValue(0)
        self.statusline.setText("Не удалось подготовить изображение")
        QMessageBox.warning(self, "Не удалось открыть рукопись", error)

    def paste_image(self):
        image = QApplication.clipboard().image()
        if image.isNull():
            QMessageBox.information(self, "Буфер обмена", "В буфере нет изображения. Скопируйте снимок или перетащите файл в окно."); return
        folder = self.data_dir / "manuscripts" / uuid.uuid4().hex
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "clipboard.png"
        if not image.save(str(path), "PNG"):
            QMessageBox.warning(self, "Буфер обмена", "Не удалось сохранить изображение из буфера."); return
        self.load_manuscript(path)

    def change_page(self, index: int):
        if not (0 <= index < len(self.page_paths)): return
        self.current_page = index
        self.image_preview.set_page(self.page_paths[index], index, self.ocr_lines)

    def run_ocr(self):
        if not self.page_paths:
            QMessageBox.information(self, "Нет изображения", "Сначала откройте изображение, многостраничный TIFF или сканированный PDF."); return
        selected_engine = self.ocr_engine_combo.currentData() if hasattr(self, "ocr_engine_combo") else "auto"
        model_base = (Path(sys.executable).resolve().parent.parent / "Resources" / "model-evaluation") if getattr(sys, "frozen", False) else (self.project_root / "data" / "model-evaluation")
        if selected_engine in {"crnn-church-slavonic", "crnn-prosta-mova"}:
            checkpoint = model_base / selected_engine / "best_model.pt"
            if not checkpoint.is_file():
                QMessageBox.warning(self, "OCR не готов", "Не найдены локальные веса выбранной модели."); return
        if getattr(sys, "frozen", False):
            model_candidates = [Path(sys.executable).parent.parent / "Resources" / "models" / "Cyr02full_best.mlmodel", Path(getattr(sys, "_MEIPASS", "")) / "models" / "Cyr02full_best.mlmodel"]
            contents = Path(sys.executable).resolve().parent.parent
            executable_candidates = [
                contents / "Frameworks" / "ocr-engine" / "paleoslov-ocr",
                contents / "Resources" / "ocr-engine" / "paleoslov-ocr",
            ]
            executable = next((item for item in executable_candidates if item.is_file()), executable_candidates[0])
            model = next((x for x in model_candidates if x.exists()), model_candidates[0])
        else:
            model = self.project_root / "data" / "models" / "Cyr02full_best.mlmodel"
            executable = self.project_root / ".venv-ocr" / "bin" / "kraken"
        if selected_engine in {"auto", "kraken-cyr02"} and (not model.exists() or not executable.exists()):
            QMessageBox.warning(self, "OCR не готов", "На SSD не найдена установленная модель Kraken или программа распознавания. Проверьте вкладку «Настройки»."); return
        self.run_ocr_btn.setEnabled(False); self.analyze_btn.setEnabled(False); self.open_image_btn.setEnabled(False); self.paste_image_btn.setEnabled(False); self.progress.setRange(0, 0)
        self.statusline.setText("OCR: сегментация и распознавание строк · страницы обрабатываются по очереди")
        selected_device = self.ocr_device_combo.currentData() if hasattr(self, "ocr_device_combo") else "auto"
        self.ocr_worker = OCRWorker(self.page_paths, model, executable, selected_device, selected_engine, self.project_root, model_base)
        self.ocr_worker.done.connect(self.ocr_done); self.ocr_worker.failed.connect(self.ocr_failed); self.ocr_worker.progress.connect(self.ocr_progress)
        self.ocr_worker.start()

    def ocr_progress(self, done: int, total: int):
        self.statusline.setText(f"OCR: обработана страница {done} из {total} · строки связаны с координатами изображения")

    def ocr_done(self, lines: list, metrics: dict):
        self.ocr_lines = lines
        self.editor.setPlainText("\n".join(row.text for row in lines))
        self.ocr_highlighter.set_lines(lines)
        self.image_preview.set_page(self.page_paths[self.current_page], self.current_page, lines)
        uncertain = sum(row.confidence is not None and row.confidence < 0.8 for row in lines)
        conf_note = f" · строк с низкой оценкой: {uncertain}" if any(x.confidence is not None for x in lines) else " · движок не вернул оценки уверенности"
        default_license = "Apache-2.0" if self.ocr_engine_combo.currentData() in {"crnn-church-slavonic", "crnn-prosta-mova"} else "CC BY 2.0"
        self.current_result = {"ocr": {"engine": metrics.get("engine", "Kraken · Cyr02full_best"), "source": str(self.source_path or ""), "page_images": [str(x) for x in self.page_paths], "raw_lines": [row.__dict__ for row in lines], "model_license": metrics.get("model_license", default_license), "normalization": "не применялась", "device": metrics.get("device"), "elapsed_ms": metrics.get("elapsed_ms"), "model_size_mb": metrics.get("model_size_mb")}}
        self.progress.setRange(0, 1); self.progress.setValue(1); self.run_ocr_btn.setEnabled(True); self.analyze_btn.setEnabled(True); self.open_image_btn.setEnabled(True); self.paste_image_btn.setEnabled(True)
        if lines:
            elapsed_s = metrics.get("elapsed_ms", 0) / 1000
            memory = f" · пик {metrics['peak_memory_mb']:.0f} МБ" if metrics.get("peak_memory_mb") else ""
            self.statusline.setText(f"Распознано строк: {len(lines)}{conf_note} · {metrics.get('device', 'CPU')} · {elapsed_s:.1f} с{memory} · сверьте оригинал")
        else:
            self.statusline.setText("Строки не обнаружены · исходное изображение сохранено, текст не подставлялся автоматически")
            QMessageBox.information(self, "Строки не обнаружены", "Kraken не выделил строки на этой странице. Это возможно для шрифтов и почерков вне обучения модели. Попробуйте более чёткий скан или другой фрагмент; OCR не будет подставлять предполагаемый текст.")

    def ocr_failed(self, error: str):
        self.progress.setRange(0, 1); self.progress.setValue(0); self.run_ocr_btn.setEnabled(True); self.analyze_btn.setEnabled(True); self.open_image_btn.setEnabled(True); self.paste_image_btn.setEnabled(True)
        self.statusline.setText("OCR не выполнен · исходное изображение сохранено")
        QMessageBox.warning(self, "Ошибка распознавания", error)

    def sync_image_line_to_text(self, line_no: int):
        target = next((i for i, row in enumerate(self.ocr_lines) if row.page == self.current_page and row.line == line_no), None)
        if target is None: return
        cursor = self.editor.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(target): cursor.movePosition(QTextCursor.MoveOperation.Down)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor); self.editor.setTextCursor(cursor); self.editor.setFocus()

    def sync_text_cursor_to_image(self):
        if not self.ocr_lines: return
        idx = self.editor.textCursor().blockNumber()
        if not (0 <= idx < len(self.ocr_lines)): return
        row = self.ocr_lines[idx]
        if self.current_page != row.page:
            self.page_selector.setCurrentIndex(row.page)
        self.image_preview.select_line(row.line)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".heif", ".pdf"}:
                self.load_manuscript(path); break

    def analyze(self):
        text = self.editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Нет текста", "Вставьте текст для анализа."); return
        self.analyze_btn.setEnabled(False); self.run_ocr_btn.setEnabled(False); self.progress.setRange(0, 0)
        self.statusline.setText("Локальный разбор · графика и морфология")
        self._analysis_streamed = set()
        self.translation.setHtml("<span style='color:#8b7c65'>Автоматический перевод отключён. Исходный текст не выдаётся за перевод.</span>")
        self.explanation.setHtml("<span style='color:#8b7c65'>Генеративное толкование отключено в этой сборке.</span>")
        self.worker = AnalyzeWorker(text, self.tradition.currentText(), self.data_dir / "paleoslov.sqlite3", self.morphology_dir)
        self.worker.done.connect(self.analysis_done); self.worker.failed.connect(self.analysis_failed); self.worker.cancelled.connect(self.analysis_cancelled); self.worker.progress.connect(self.stream_analysis); self.worker.start(); self.cancel_btn.setEnabled(True)

    def stream_analysis(self, stage: str, chunk: str):
        target = self.translation if stage == "translation" else self.explanation
        if stage not in self._analysis_streamed:
            target.clear()
            self._analysis_streamed.add(stage)
        cursor = target.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        target.setTextCursor(cursor)

    def cancel_analysis(self):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.requestInterruption()
            self.statusline.setText("Останавливаю локальный запрос…")

    def analysis_cancelled(self):
        self.progress.setRange(0, 1); self.progress.setValue(0); self.analyze_btn.setEnabled(True); self.run_ocr_btn.setEnabled(True); self.cancel_btn.setEnabled(False)
        self.statusline.setText("Анализ остановлен")

    def analysis_done(self, result: dict):
        if self.current_result.get("ocr"):
            result["ocr"] = self.current_result["ocr"]
        self.current_result = result
        reading = result.get("reading")
        normalization = result.get("normalization", {})
        if not reading and not normalization.get("changed"):
            reading = "Отдельное нормализованное прочтение не сформировано. Исходная транскрипция слева сохранена без изменений."
        self.reading.setHtml(self._plain(reading or "Прочтение не сформировано."))
        translation_message = result.get("translation") or result.get("translation_status") or "Автоматический перевод отключён в этой сборке."
        alternatives = result.get("translation_alternatives", [])
        alternatives_html = "<br><br><b>Неоднозначные места</b><br>" + "<br>".join(self._plain(item) for item in alternatives) if alternatives else ""
        translation_meta = result.get("translation_metadata", {})
        translation_note = ""
        if translation_meta:
            source_url = translation_meta.get("source", "")
            title = self._plain(translation_meta.get("title", "Источник перевода"))
            source = f"<a href='{escape(source_url, quote=True)}'>{title}</a>" if source_url else title
            source_note = f" · {self._plain(translation_meta.get('translation_source',''))}" if translation_meta.get("translation_source") and not source_url else ""
            translation_note = f"<br><br><b>{self._plain(translation_meta.get('method',''))}</b> · {source}{source_note}<br>{self._plain(translation_meta.get('status',''))}"
            if translation_meta.get("caveat"):
                translation_note += f"<br><i>{self._plain(translation_meta['caveat'])}</i>"
        self.translation.setHtml(self._plain(translation_message) + alternatives_html + translation_note)
        note = result.get("explanation", "") or result.get("explanation_status", "")
        errors = result.get("component_errors", {})
        if errors:
            note += "\n\n" + "\n".join(f"Не выполнено ({self._plain(name)}): {self._plain(error)}" for name, error in errors.items())
        if result.get("llm_status"): note += "\n\n" + result["llm_status"]
        self.explanation.setHtml(self._plain(note))
        label = result.get("tradition", "Не определена")
        phenomenon_rows = []
        for x in result.get("observations", []):
            sources = "<br>".join(f"Источник: <a href='{escape(s.get('url',''), quote=True)}'>{self._plain(s.get('title','Научный источник'))}</a> ({self._plain(s.get('year',''))}) — {self._plain(s.get('passage',''))}" for s in x.get("sources", []))
            alternatives = "<br>Альтернативы: " + "; ".join(self._plain(a) for a in x.get("alternatives", [])) if x.get("alternatives") else ""
            phenomenon_rows.append(f"<b>{self._plain(x['label'])}</b> · <b>{self._plain(x.get('evidence_status',''))}</b><br>{self._plain(x['detail'])}{alternatives}<br>{sources}")
        reviews = result.get("historical_reviews", [])
        review_html = ""
        if reviews:
            review_html = "<hr><b>Проверка гипотезы «ѣ вместо ь»</b><br>" + "<br><br>".join(f"Форма <b>{self._plain(v.get('form',''))}</b>: <b>{self._plain(v.get('status',''))}</b> — {self._plain(v.get('note',''))}<br>Проверить: " + "; ".join(f"{self._plain(s['check'])}: {self._plain(s['status'])}" for s in v.get("checks", [])) for v in reviews)
        self.phenomena.setHtml(f"<b>Традиция:</b> {self._plain(label)} (уверенность: {self._plain(result.get('confidence',''))})<br><b>Диалектология:</b> недостаточно данных для определения говора; одна буква или форма не устанавливает диалект.<br><i>Правила ниже отмечают графику, а не автоматически установленное произношение.</i><br><br>" + ("<br><br>".join(phenomenon_rows) or "В реестре правил совпадений нет. Это не доказывает отсутствие исторических явлений.") + review_html)
        morphology = result.get("morphology", {})
        morph_rows = morphology.get("tokens", []) if isinstance(morphology, dict) else []
        morph_html = "<br>".join(f"<b>{self._plain(x.get('form',''))}</b> → {self._plain(x.get('lemma') or '—')} · {self._plain(x.get('upos') or '—')} · {self._plain(', '.join(f'{k}={v}' for k,v in x.get('features',{}).items()) or '—')} · {self._plain(x.get('deprel') or '—')}" for x in morph_rows)
        morph_meta = f"<b>{self._plain(morphology.get('engine',''))}</b> · {self._plain(morphology.get('status',''))}"
        morph_source = f"<br>Модель: {self._plain(morphology.get('model_id',''))} · <a href='{self._plain(morphology.get('source',''))}'>{self._plain(morphology.get('treebank',''))}</a>" if morphology.get("source") else ""
        morph_warn = f"<br><i>{self._plain(morphology.get('warning',''))}</i>" if morphology.get("warning") else ""
        morph_alternatives = f"<br>{self._plain(morphology['alternatives_note'])}" if morphology.get("alternatives_note") else ""
        self.grammar.setHtml(morph_meta + morph_source + "<br><br>" + (morph_html or "Для выбранной традиции нет подходящих модельных разборов.") + morph_alternatives + morph_warn)
        self.statusline.setText("Анализ завершён · автоматические гипотезы отделены от источников")
        self.progress.setRange(0, 1); self.progress.setValue(1); self.analyze_btn.setEnabled(True); self.run_ocr_btn.setEnabled(True); self.cancel_btn.setEnabled(False)
        self.sources.setHtml("Источники ещё не искались. Включите «Углублённое исследование» перед разбором, чтобы ввести запрос для библиографического поиска.")
        if self.mode.currentIndex() == 1: self.research_prompt()

    def analysis_failed(self, error: str):
        self.progress.setRange(0, 1); self.progress.setValue(0); self.analyze_btn.setEnabled(True); self.run_ocr_btn.setEnabled(True); self.cancel_btn.setEnabled(False)
        self.statusline.setText("Ошибка анализа"); QMessageBox.warning(self, "Ошибка", error)

    def research_prompt(self):
        query, ok = QInputDialog.getText(self, "Научный поиск", "Введите конкретное явление, форму или исследовательский вопрос:")
        if ok and query.strip():
            self.statusline.setText("Поиск библиографических записей OpenAlex…")
            self.progress.setRange(0, 0)
            self.research_worker = ResearchWorker(query, self.data_dir / "paleoslov.sqlite3")
            self.research_worker.done.connect(self.research_done); self.research_worker.failed.connect(self.research_failed); self.research_worker.start()

    def research_done(self, items: list):
        self.progress.setRange(0, 1); self.progress.setValue(1)
        if not hasattr(self, "current_result"):
            self.current_result = {}
        self.current_result["research_records"] = items
        if not items:
            self.sources.setHtml("По запросу не найдено библиографических записей."); return
        self.sources.setHtml(f"<b>{self._plain(items[0].get('provider','Научный каталог'))} · библиографический поиск</b><br>Карточка публикации не подтверждает конкретное утверждение.<br><br>" + "<hr>".join(f"<b>{self._plain(x['title'])}</b> · {self._plain(x['year'])}<br>{self._plain(x['authors'])}<br>{self._plain(x['venue'])}<br>{self._plain(x['doi'] or 'DOI не указан в записи')}<br><a href='{self._plain(x['url'])}'>{self._plain(x['url'])}</a><br><i>{self._plain(x['status'])}</i>" for x in items))
        self.statusline.setText(f"Найдено записей: {len(items)} · проверяйте содержание публикаций")

    def research_failed(self, error: str):
        self.progress.setRange(0, 1); self.progress.setValue(0); self.statusline.setText(f"Поиск недоступен: {error}")

    def save_result(self):
        text = self.editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Нет текста", "Сначала добавьте текст."); return
        default_title = self.current_doc_title if self.current_doc_id is not None else text[:60].replace("\n", " ")
        title, ok = QInputDialog.getText(self, "Сохранить разбор", "Название документа:", text=default_title)
        if ok:
            if self.current_doc_id is None:
                self.current_doc_id = self.store.save(title, text, self.current_result)
            else:
                self.store.update(self.current_doc_id, title, text, self.current_result)
            self.current_doc_title = title
            self.refresh_history(); self.statusline.setText("Разбор сохранён в локальную базу")

    def refresh_history(self):
        self.history_list.clear()
        for row in self.store.history():
            item = self.history_list.addItem(f"{row['id']} · {row['title']} · {row['updated'][:16]}")

    def load_history_item(self, item):
        try: doc_id = int(item.text().split("·", 1)[0].strip())
        except ValueError: return
        row = self.store.load(doc_id)
        if row:
            self.current_doc_id = doc_id
            self.current_doc_title = row["title"]
            self.editor.setPlainText(row["original"])
            saved_reading = row["reading"] or ""
            if saved_reading.strip() == row["original"].strip():
                saved_reading = "Отдельная нормализация не сохранена; отображается исходная транскрипция."
            self.reading.setHtml(self._plain(saved_reading))
            self.explanation.setHtml(self._plain(row["explanation"] or "Генеративное толкование недоступно в этой сборке."))
            try: ocr = json.loads(row["ocr_metadata"] or "{}")
            except (KeyError, json.JSONDecodeError, TypeError): ocr = {}
            try: morphology = json.loads(row["morphology"] or "{}")
            except (KeyError, json.JSONDecodeError, TypeError): morphology = {}
            try: research_records = json.loads(row["research_records"] or "[]")
            except (KeyError, json.JSONDecodeError, TypeError): research_records = []
            observations = json.loads(row["observations"] or "[]")
            try: translation_metadata = json.loads(row["translation_metadata"] or "{}")
            except (KeyError, json.JSONDecodeError, TypeError): translation_metadata = {}
            try: translation_alternatives = json.loads(row["translation_alternatives"] or "[]")
            except (KeyError, json.JSONDecodeError, TypeError): translation_alternatives = []
            try: historical_reviews = json.loads(row["historical_reviews"] or "[]")
            except (KeyError, json.JSONDecodeError, TypeError): historical_reviews = []
            self.current_result = {"tradition": row["tradition"], "reading": row["reading"], "translation": row["translation"], "translation_metadata": translation_metadata, "translation_alternatives": translation_alternatives, "historical_reviews": historical_reviews, "explanation": row["explanation"], "observations": observations, "morphology": morphology, "ocr": ocr, "research_records": research_records}
            tm = self.current_result["translation_metadata"]
            translation_note = f"<br><br><i>{self._plain(tm.get('status',''))}</i>" if tm else ""
            saved_translation = row["translation"] or ""
            if saved_translation.strip() == row["original"].strip():
                translation_html = "Сохранённый ранее текст совпадает с оригиналом; он скрыт, чтобы не выдавать оригинал за перевод."
            elif saved_translation:
                translation_html = "<b>Результат, сохранённый ранее</b><br>Он не создаётся и не проверяется этой сборкой.<br><br>" + self._plain(saved_translation)
            else:
                translation_html = "Автоматический перевод отключён в этой сборке."
            self.translation.setHtml(translation_html + translation_note)
            if research_records:
                self.sources.setHtml(f"<b>Сохранённые библиографические записи</b><br>Карточки не подтверждают конкретное утверждение.<br><br>" + "<hr>".join(f"<b>{self._plain(x.get('title',''))}</b> · {self._plain(x.get('year',''))}<br>{self._plain(x.get('authors',''))}<br>{self._plain(x.get('venue',''))}<br><a href='{escape(x.get('url',''), quote=True)}'>{self._plain(x.get('url',''))}</a><br><i>{self._plain(x.get('status',''))}</i>" for x in research_records))
            else:
                self.sources.setHtml("В этой записи нет сохранённых результатов библиографического поиска.")
            phenomenon_rows = [f"<b>{self._plain(x.get('label',''))}</b> · {self._plain(x.get('evidence_status',''))}<br>{self._plain(x.get('detail',''))}" for x in observations]
            self.phenomena.setHtml("<b>Диалектология:</b> недостаточно данных для определения говора.<br><i>Графические совпадения не доказывают произношение или диалект.</i><br><br>" + ("<br><br>".join(phenomenon_rows) or "В сохранённом анализе нет зарегистрированных графических наблюдений."))
            rows = morphology.get("tokens", []) if isinstance(morphology, dict) else []
            html = "<br>".join(f"<b>{self._plain(x.get('form',''))}</b> → {self._plain(x.get('lemma') or '—')} · {self._plain(x.get('upos') or '—')} · {self._plain(', '.join(f'{k}={v}' for k,v in x.get('features',{}).items()) or '—')} · {self._plain(x.get('deprel') or '—')}" for x in rows)
            morph_alt = f"<br>{self._plain(morphology['alternatives_note'])}" if morphology.get("alternatives_note") else ""
            self.grammar.setHtml(f"<b>{self._plain(morphology.get('engine',''))}</b> · {self._plain(morphology.get('status',''))}<br><br>{html or self._plain(morphology.get('warning','Морфология не сохранена.'))}{morph_alt}")
            self.ocr_lines = [OCRLine(**x) for x in ocr.get("raw_lines", [])]
            self.ocr_highlighter.set_lines(self.ocr_lines)
            saved_pages = [Path(x) for x in ocr.get("page_images", []) if Path(x).exists()]
            if saved_pages:
                self.source_path = Path(ocr.get("source", "")) if ocr.get("source") else None
                self.page_paths = saved_pages
                self.page_selector.clear()
                for i in range(len(saved_pages)): self.page_selector.addItem(f"Страница {i+1}", i)
                self.page_selector.setEnabled(len(saved_pages) > 1)
                self.page_selector.setCurrentIndex(0); self.current_page = 0
                self.image_preview.set_page(saved_pages[0], 0, self.ocr_lines)

    def history_menu(self, pos):
        item = self.history_list.itemAt(pos)
        if item is None: return
        menu = QMenu(self)
        delete_action = menu.addAction("Удалить разбор")
        if menu.exec(self.history_list.mapToGlobal(pos)) == delete_action:
            try: doc_id = int(item.text().split("·", 1)[0].strip())
            except ValueError: return
            self.store.delete(doc_id)
            if self.current_doc_id == doc_id:
                self.current_doc_id = None; self.current_doc_title = ""; self.current_result = {}
            self.refresh_history()
            self.statusline.setText("Разбор удалён из локальной истории")

    def open_text(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть текст", str(Path.home()), "Текст (*.txt *.md *.conllu);;Все файлы (*)")
        if path:
            self.editor.setPlainText(Path(path).read_text(encoding="utf-8"))
            self.ocr_lines = []; self.ocr_highlighter.set_lines([])

    def import_conllu(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт CoNLL-U", str(Path.home()), "CoNLL-U (*.conllu *.conll *.txt)")
        if not path: return
        rows = parse_conllu(Path(path).read_text(encoding="utf-8"))
        if not rows:
            QMessageBox.information(self, "CoNLL-U", "Не найдены корректные строки с 10 колонками."); return
        corpus, ok = QInputDialog.getText(self, "Источник корпуса", "Название корпуса:", text=Path(path).stem)
        if not ok or not corpus.strip(): return
        license_name, ok = QInputDialog.getText(self, "Лицензия корпуса", "Лицензия (проверьте LICENSE.txt источника):", text="Не указана — уточнить до дальнейшего распространения")
        if not ok: return
        source_url, ok = QInputDialog.getText(self, "Источник корпуса", "Ссылка на источник и LICENSE.txt:")
        if not ok: return
        count = self.store.import_conllu(corpus, license_name, source_url, rows)
        self.word_card.setHtml(f"<b>Импортировано строк:</b> {count}<br><b>Источник:</b> {self._plain(corpus)}<br><b>Лицензия:</b> {self._plain(license_name)}<br>Теперь выделите словоформу в оригинале: приложение покажет точные корпусные совпадения. Выводы будут обозначены как корпусные примеры, не как гарантированный анализ данного контекста.")

    def export_markdown(self):
        if not self.current_result:
            QMessageBox.information(self, "Нет результата", "Сначала выполните анализ."); return
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт Markdown", "Разбор.md", "Markdown (*.md)")
        if path:
            r = self.current_result
            ocr = r.get("ocr", {})
            raw_lines = "\n".join(f"- стр. {x['page']+1}, строка {x['line']+1}: {x['text']}" for x in ocr.get("raw_lines", []))
            alternatives = "\n".join(f"- {x}" for x in r.get("translation_alternatives", [])) or "Не отмечены моделью."
            reviews = "\n".join(f"- {x.get('form','')}: {x.get('status','')} — {x.get('note','')}" for x in r.get("historical_reviews", [])) or "Нет."
            morphology = r.get("morphology", {})
            grammar = "\n".join(f"- {x.get('form','')} → {x.get('lemma') or '—'} · {x.get('upos') or '—'} · {x.get('features') or {}}" for x in morphology.get("tokens", [])) or "Не выполнен."
            observations = "\n".join(f"- {x.get('label','')}: {x.get('detail','')} [{x.get('evidence_status','')}]" for x in r.get("observations", [])) or "Совпадений нет."
            tm = r.get("translation_metadata", {})
            translation_provenance = " · ".join(str(tm.get(k, "")) for k in ("method", "title", "translation_source", "status") if tm.get(k))
            research = "\n\n".join(f"- {x.get('title','')} ({x.get('year','')}); {x.get('authors','')}; {x.get('url','')} — {x.get('status','')}" for x in r.get("research_records", [])) or "Библиографические записи не искались."
            reading = r.get("reading") or "Отдельная нормализация не выполнена."
            translation = r.get("translation") or "Автоматический перевод отключён в этой сборке."
            body = f"# Палеослов — разбор\n\n## Исправленная транскрипция\n\n{self.editor.toPlainText()}\n\n## Исходный OCR\n\nДвижок: {ocr.get('engine', 'ручной ввод')} · автоматическая нормализация: {ocr.get('normalization', 'не применялась')}\n\n{raw_lines}\n\n## Традиция\n\n{r.get('tradition','')}\n\n## Прочтение\n\n{reading}\n\n## Перевод\n\n{translation}\n\n{translation_provenance}\n\n## Альтернативы перевода\n\n{alternatives}\n\n## Толкование\n\n{r.get('explanation') or 'Генеративное толкование отключено в этой сборке.'}\n\n## Грамматика\n\n{grammar}\n\n## Исторические явления\n\n{observations}\n\n## Проверка ѣ / ь\n\n{reviews}\n\n## Библиографические записи\n\n{research}\n\n## Статус\n\nМорфологический разбор — автоматическая гипотеза. Библиографическая запись сама по себе не подтверждает вывод. OCR требуется сверить с изображением.\n"
            Path(path).write_text(body, encoding="utf-8")

    def export_json(self):
        if not self.current_result:
            QMessageBox.information(self, "Нет результата", "Сначала выполните анализ."); return
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт JSON", "Разбор.json", "JSON (*.json)")
        if path:
            payload = {"original": self.editor.toPlainText(), **self.current_result}
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def closeEvent(self, event):
        self.store.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Палеослов")
    app.setStyle("Fusion")
    window = MainWindow(); window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
