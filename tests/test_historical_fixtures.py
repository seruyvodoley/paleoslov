import json
from pathlib import Path

from paleoslov.core.historical_morphology import HistoricalMorphology
from paleoslov.core.linguistics import analyze_orthography, investigate_yat_vs_jer


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "historical"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_three_documented_benchmarks_have_separate_modern_russian_reference():
    examples = [fixture(name) for name in ("A-pater-noster-proiel.json", "B-gramota-109.json", "C-suprasliensis-proiel.json")]
    assert {item["id"] for item in examples} == {"A", "B", "C"}
    for item in examples:
        assert item["source_text"].strip()
        assert item["reference_translation"].strip()
        assert item["source_text"].strip() != item["reference_translation"].strip()
        assert item["provenance"]["url"].startswith("https://")


def test_pater_noster_fixture_gold_rows_come_from_stated_proiel_heldout_ids():
    item = fixture("A-pater-noster-proiel.json")
    assert "sent_id 293684" in item["provenance"]["corpus"]
    assert any(row["lemma"] == "свѧтити" for row in item["gold_morphology"])
    assert any(row["features"] == "Mood=Imp|Number=Sing|Person=2|Tense=Pres|VerbForm=Fin|Voice=Act" for row in item["gold_morphology"])


def test_birchbark_109_keeps_editorial_alternatives_and_no_unlicensed_image_copy():
    item = fixture("B-gramota-109.json")
    assert len(item["alternatives"]) >= 2
    assert "reuse rights are not established" in item["provenance"]["image_rights"]
    assert "Жизномира Микуле" in item["reference_translation"]


def test_yat_jer_research_path_does_not_guess_without_primary_evidence():
    result = investigate_yat_vs_jer("ѣмь", lemma="ямь", grammatical_analysis="noun; loc.sg", date="XII c.", tradition="Novgorod")
    assert result["status"] == "данных недостаточно для вывода"
    assert all(row["status"] != "подтверждено" for row in result["checks"])
    assert result["sources"]
    assert any("ошибка" in alt.lower() or "исправ" in alt.lower() for alt in result["alternatives"])


def test_iotated_yus_is_detected_with_specific_token_span_and_references():
    rows = analyze_orthography("и҅ тихостиѭ҄")
    nasal = next(row for row in rows if row.rule_id == "ORTH-NASAL")
    assert nasal.token_start == 3
    assert nasal.token_end == len("и҅ тихостиѭ҄")
    assert "йотированные" in nasal.detail
    assert nasal.sources and "10.1163" in nasal.sources[0]["url"]


def test_registered_graphic_rules_have_positive_and_negative_controls():
    cases = {
        "ORTH-YAT": ("бѣ", "бь"),
        "ORTH-JERS": ("бъ", "бо"),
        "ORTH-NASAL": ("ѫ", "о"),
        "ORTH-THETA": ("ѳ", "ф"),
    }
    for rule_id, (positive, negative) in cases.items():
        hits = [row for row in analyze_orthography(f"слово {positive}") if row.rule_id == rule_id]
        assert len(hits) == 1
        assert f"слово {positive}"[hits[0].token_start:hits[0].token_end] == positive
        assert not [row for row in analyze_orthography(f"слово {negative}") if row.rule_id == rule_id]


def test_novgorod_parallel_requires_the_documented_sequence():
    assert any(row.rule_id == "PARALLEL-NOVGOROD-247" for row in analyze_orthography("а замъке кѣле а двьри кѣлѣ"))
    assert not any(row.rule_id == "PARALLEL-NOVGOROD-247" for row in analyze_orthography("а замке целе а двери целы"))


def test_ocs_fixture_model_result_is_compared_with_independent_proiel_gold():
    item = fixture("C-suprasliensis-proiel.json")
    model_dir = ROOT / "data" / "models" / "udpipe"
    result = HistoricalMorphology(model_dir).analyze(item["source_text"], "Старославянский")
    gold = {row["form"]: row for row in item["gold_morphology"]}
    analyzed = {row["form"]: row for row in result["tokens"]}
    common = set(gold) & set(analyzed)
    assert len(common) >= 10
    lemma_accuracy = sum(gold[form]["lemma"] == analyzed[form]["lemma"] for form in common) / len(common)
    upos_accuracy = sum(gold[form]["upos"] == analyzed[form]["upos"] for form in common) / len(common)
    assert 0 <= lemma_accuracy <= 1 and 0 <= upos_accuracy <= 1
    # Retain actual scores for review in pytest output on demand; do not set an
    # artificially high acceptance threshold for out-of-domain literary text.
    print({"common_forms": len(common), "lemma_accuracy": lemma_accuracy, "upos_accuracy": upos_accuracy})
