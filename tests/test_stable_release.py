from pathlib import Path

from PySide6.QtCore import QCoreApplication

from paleoslov.app.main import AnalyzeWorker


def test_stable_analysis_does_not_start_translation_or_copy_source(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    source = "І҆с҃ъ ѣсть слово"
    result = []
    errors = []
    worker = AnalyzeWorker(source, "Церковнославянский", tmp_path / "history.sqlite3", tmp_path / "missing-models")
    worker.done.connect(result.append)
    worker.failed.connect(errors.append)
    worker.run()
    app.processEvents()

    assert not errors
    assert result
    analysis = result[0]
    assert analysis["translation"] == ""
    assert analysis["reading"] == ""
    assert analysis["normalization"]["source"] == source
    assert analysis["normalization"]["changed"] is False
    assert analysis["translation_status"] == "Автоматический перевод отключён в этой версии."
    assert "Недоступ" in analysis["morphology"]["status"] or analysis["morphology"]["status"] == "не выполнен"

