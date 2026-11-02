import json
from pathlib import Path

from paleoslov.core.lexicon import lexical_lookup
from paleoslov.core.linguistics import analyze_orthography
from paleoslov.core.parallel_translation import ParallelTranslationIndex


def test_lexicon_keeps_ambiguous_contextual_candidates_separate():
    result = lexical_lookup("градъ", "Старославянский", [
        {"lemma": "градъ", "upos": "NOUN", "features": {"Case": "Nom", "Number": "Sing"}},
    ], [
        {"lemma": "градъ", "upos": "NOUN", "feats": "Case=Nom|Number=Sing", "corpus": "UD PROIEL"},
        {"lemma": "градъ", "upos": "NOUN", "feats": "Case=Acc|Number=Sing", "corpus": "UD PROIEL"},
    ])

    assert len(result["candidates"]) == 2
    assert result["dictionary_meanings"] == []
    assert "не является толкованием" in result["meaning_status"]
    assert any("GORAZD" in source["title"] for source in result["dictionary_sources"])


def test_dictionary_source_scope_tracks_selected_tradition():
    old_russian = lexical_lookup("грамота", "Древнерусский")
    church_slavonic = lexical_lookup("благослови", "Церковнославянский")

    assert any("XI–XIV" in source["title"] for source in old_russian["dictionary_sources"])
    assert any("Нового времени" in source["title"] for source in church_slavonic["dictionary_sources"])


def test_unseen_translation_references_are_not_injected_into_parallel_lookup():
    root = Path(__file__).parent
    fixtures = json.loads((root / "fixtures" / "translation-unseen.json").read_text(encoding="utf-8"))
    index = ParallelTranslationIndex(root.parent / "data" / "translations" / "parallel_references.json")

    assert all(index.lookup(item["text"]) is None for item in fixtures)


def test_novgorod_documented_parallel_is_not_misreported_as_dialect_detection():
    observations = analyze_orthography("а замъке кѣле а двьри кѣлѣ")
    parallel = next(item for item in observations if item.rule_id == "PARALLEL-NOVGOROD-247")

    assert parallel.token_start == 0
    assert parallel.token_end == len("а замъке кѣле а двьри кѣлѣ")
    assert "не устанавливает" in parallel.detail
    assert parallel.sources[0]["url"].endswith("/247/")
