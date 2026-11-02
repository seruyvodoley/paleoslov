from pathlib import Path
import hashlib
import json

from paleoslov.core.linguistics import analyze_orthography, parse_conllu
from paleoslov.core.storage import Store
from paleoslov.core.text import search_form, tokenize
from paleoslov.core.historical_ocr import parse_kraken_xml
from paleoslov.core.pipeline import analyze_morphology, detect_historical_features, normalize_reading, translate_to_russian, validate_evidence
from paleoslov.core.historical_morphology import HistoricalMorphology
from paleoslov.core.llm import OllamaClient
from paleoslov.core.research import ResearchService
from paleoslov.core.benchmark import score_transcription


def test_historical_unicode_and_offsets_are_preserved():
    text = "ѣсть ѫ"
    tokens = tokenize(text)
    assert [t.text for t in tokens] == ["ѣсть", "ѫ"]
    assert text[tokens[0].start:tokens[0].end] == "ѣсть"
    assert search_form("ѣ") == "ѣ"


def test_orthographic_observation_is_not_phonology_claim():
    found = analyze_orthography("бѣ")
    assert found and found[0].rule_id == "ORTH-YAT"
    assert "нельзя заключить" in found[0].detail


def test_conllu_parse_ignores_comments_and_multiword_rows():
    rows = parse_conllu("# sent_id = 1\n1\tбѣ\tбыти\tAUX\tV\tMood=Ind\t0\troot\t_\t_\n1-2\tfoo\t_\t_\t_\t_\t_\t_\t_\t_\n")
    assert len(rows) == 1 and rows[0]["lemma"] == "быти"


def test_store_persists_history_sources_and_corpus(tmp_path):
    db = Store(tmp_path / "p.sqlite3")
    records = [{"title": "Словарь", "authors": "Автор", "url": "https://example.org", "status": "библиографическая запись"}]
    doc_id = db.save("test", "ѣсть", {"tradition": "unknown", "observations": [], "morphology": {"engine": "UDPipe", "tokens": [{"form": "ѣсть"}]}, "translation_alternatives": ["вариант"], "translation_metadata": {"method": "exact", "status": "reference"}, "historical_reviews": [{"form": "ѣсть", "status": "недостаточно данных"}], "research_records": records})
    db.import_conllu("test-corpus", "CC BY-NC-SA 4.0", "https://example.invalid", [{"form": "ѣсть", "lemma": "быти", "upos": "AUX", "xpos": "", "feats": "", "deprel": "root"}])
    assert db.load(doc_id)["original"] == "ѣсть"
    assert '"UDPipe"' in db.load(doc_id)["morphology"]
    assert json.loads(db.load(doc_id)["translation_alternatives"]) == ["вариант"]
    assert json.loads(db.load(doc_id)["translation_metadata"]) == {"method": "exact", "status": "reference"}
    assert json.loads(db.load(doc_id)["historical_reviews"])[0]["form"] == "ѣсть"
    assert json.loads(db.load(doc_id)["research_records"]) == records
    assert db.find_forms("ѣсть")[0]["lemma"] == "быти"
    db.close()


def test_store_migrates_existing_analysis_table_without_losing_rows(tmp_path):
    import sqlite3
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE documents(id INTEGER PRIMARY KEY, title TEXT NOT NULL, original TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
        CREATE TABLE analyses(id INTEGER PRIMARY KEY, document_id INTEGER, tradition TEXT, reading TEXT, translation TEXT, explanation TEXT, observations TEXT NOT NULL DEFAULT '[]', created TEXT NOT NULL);
        INSERT INTO documents VALUES(1,'saved','ѣсть','2026-01-01','2026-01-01');
        INSERT INTO analyses(id,document_id,tradition,reading,translation,explanation,observations,created) VALUES(1,1,'old','ѣсть','','','[]','2026-01-01');
        """)
    store = Store(path)
    row = store.load(1)
    assert row["original"] == "ѣсть" and row["reading"] == "ѣсть"
    assert json.loads(row["historical_reviews"]) == []
    assert json.loads(row["research_records"]) == []
    new_id = store.save("new", "ѣ", {"historical_reviews": [{"form": "ѣ"}]})
    assert json.loads(store.load(new_id)["historical_reviews"])[0]["form"] == "ѣ"
    store.close()


def test_kraken_page_xml_keeps_historical_unicode_and_coordinates(tmp_path):
    page = tmp_path / "page.xml"
    page.write_text('<PcGts><Page><TextRegion><TextLine><Coords points="10,20 210,20 210,55 10,55"/><TextEquiv><Unicode>ѣ ѫ б҃гъ</Unicode></TextEquiv></TextLine></TextRegion></Page></PcGts>', encoding="utf-8")
    rows = parse_kraken_xml(page, page=2)
    assert len(rows) == 1
    assert rows[0].text == "ѣ ѫ б҃гъ"
    assert rows[0].page == 2
    assert rows[0].bbox == (10, 20, 200, 35)


def test_diplomatic_reading_is_never_silently_normalized():
    source = "і҆с҃ъ ѣсть ъ"
    result = normalize_reading(source)
    assert result["reading"] == source
    assert result["changed"] is False


def test_morphology_looks_up_unique_forms_in_a_batch():
    calls = []
    result = analyze_morphology("бѣсть бѣсть ѣсть", lambda form: calls.append(form) or [])
    assert calls == ["бѣсть", "ѣсть"]
    assert result.status == "корпусный поиск без морфологической модели"
    assert [row["form"] for row in result.value["tokens"]] == ["бѣсть", "бѣсть", "ѣсть"]


def test_udpipe_ocs_model_returns_separate_unverified_analysis():
    models = Path(__file__).parents[1] / "data" / "models" / "udpipe"
    source = "въ начало бѣ слово"
    result = HistoricalMorphology(models).analyze(source, "Старославянский")
    assert result["model_id"].startswith("old_church_slavonic-proiel")
    assert source == "въ начало бѣ слово"
    be = next(token for token in result["tokens"] if token["form"] == "бѣ")
    assert be["lemma"] == "бꙑти"
    assert be["features"]["Tense"] == "Past"
    assert be["source_verified"] is False


def test_translation_failure_is_explicit_not_a_copy_of_the_source():
    result = translate_to_russian("бѣсть", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    assert result.value is None
    assert result.status == "ошибка"
    assert result.error == "offline"


def test_translation_stage_rejects_source_echo():
    result = translate_to_russian("бѣсть", lambda _: "бѣсть")
    assert result.status == "ошибка"
    assert "пустой результат" not in result.error


def test_translation_stage_rejects_old_script_only_output():
    result = translate_to_russian("бѣ", lambda _: "Бѣ")
    assert result.status == "ошибка"
    assert "современный русский" in result.error


def test_translation_model_separates_ambiguity_section_from_translation():
    client = OllamaClient(model="test")
    client._complete = lambda *args, **kwargs: "Перевод: В начале было Слово.\nНЕОДНОЗНАЧНОСТИ:\n- слово «начало»: также «начале» как формула евангельского зачина."
    translation = client.translate_to_russian("Въ начало бѣ слово")
    assert translation == "В начале было Слово."
    assert client.last_translation_alternatives and "начало" in client.last_translation_alternatives[0]


def test_historical_feature_stage_returns_structured_observations():
    result = detect_historical_features("бѣ")
    assert result.status == "готово"
    assert result.value["observations"][0]["rule_id"] == "ORTH-YAT"
    assert result.value["observations"][0]["token_start"] == 0
    assert result.value["yat_jer_reviews"][0]["status"] == "данных недостаточно для вывода"


def test_bibliographic_records_are_not_claimed_as_verified_evidence():
    record = {"title": "Example", "url": "https://example.invalid"}
    result = validate_evidence("утверждение", [record])
    assert result["status"] == "требуется сверка полного текста источников"


def test_research_cache_serves_recent_records_without_network(tmp_path):
    db_path = tmp_path / "p.sqlite3"
    Store(db_path).close()
    key = hashlib.sha256(("гавлик\0" + "8").encode("utf-8")).hexdigest()
    row = [{"title": "Кэшированная карточка", "status": "библиография"}]
    ResearchService._write_cache(db_path, key, row)
    assert ResearchService().search("Гавлик", cache_db=db_path) == row


def test_benchmark_preserves_historical_letters_and_uses_word_edits():
    result = score_transcription("ѣсть слово", "есть слово")
    assert result["cer"] > 0
    assert result["wer"] == 0.5
    assert result["historical_char_errors"] == 1
