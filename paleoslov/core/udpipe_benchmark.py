"""Reproducible evaluation against official held-out UD CoNLL-U sentences."""
from __future__ import annotations

from pathlib import Path
import time

from ufal.udpipe import Model, Pipeline, ProcessingError


def _sentences(path: Path):
    forms: list[str] = []
    gold: list[list[str]] = []
    text = ""
    for line in path.read_text(encoding="utf-8").splitlines() + [""]:
        if line.startswith("# text = "):
            text = line[len("# text = "):]
        elif line and not line.startswith("#"):
            cols = line.split("\t")
            if len(cols) == 10 and "-" not in cols[0] and "." not in cols[0]:
                gold.append(cols)
                forms.append(cols[1])
        elif not line and gold:
            yield text or " ".join(forms), gold
            forms, gold, text = [], [], ""


def evaluate_udpipe(model_path: Path, conllu_path: Path) -> dict:
    started = time.perf_counter()
    model = Model.load(str(model_path))
    if model is None:
        raise RuntimeError(f"Model.load failed: {model_path}")
    load_ms = round((time.perf_counter() - started) * 1000)
    pipeline = Pipeline(model, "tokenize", Pipeline.DEFAULT, Pipeline.DEFAULT, "conllu")
    totals = {k: 0 for k in ("sentences", "gold_tokens", "pred_tokens", "exact_token_sentences", "aligned_tokens", "lemma_correct", "upos_correct", "feats_correct", "head_correct", "deprel_correct", "las_correct")}
    inference_started = time.perf_counter()
    for source, gold in _sentences(conllu_path):
        err = ProcessingError()
        parsed = pipeline.process(source, err)
        if err.occurred():
            continue
        pred = [x.split("\t") for x in parsed.splitlines() if x and not x.startswith("#") and len(x.split("\t")) == 10 and "-" not in x.split("\t")[0] and "." not in x.split("\t")[0]]
        totals["sentences"] += 1
        totals["gold_tokens"] += len(gold)
        totals["pred_tokens"] += len(pred)
        if [x[1] for x in pred] != [x[1] for x in gold]:
            continue
        totals["exact_token_sentences"] += 1
        totals["aligned_tokens"] += len(gold)
        for p, g in zip(pred, gold):
            totals["lemma_correct"] += p[2] == g[2]
            totals["upos_correct"] += p[3] == g[3]
            totals["feats_correct"] += p[5] == g[5]
            head_ok = p[6] == g[6]
            relation_ok = p[7] == g[7]
            totals["head_correct"] += head_ok
            totals["deprel_correct"] += relation_ok
            totals["las_correct"] += head_ok and relation_ok
    elapsed_ms = round((time.perf_counter() - inference_started) * 1000)
    n = totals["gold_tokens"]
    aligned_n = totals["aligned_tokens"]
    return {
        "model": model_path.name,
        "test_file": conllu_path.name,
        "load_ms": load_ms,
        "inference_ms": elapsed_ms,
        "sentences": totals["sentences"],
        "gold_tokens": n,
        "predicted_tokens": totals["pred_tokens"],
        "exact_tokenization_sentences": totals["exact_token_sentences"],
        "tokenization_exact_sentence_rate": round(totals["exact_token_sentences"] / max(totals["sentences"], 1), 4),
        "aligned_tokens": aligned_n,
        "lemma_accuracy_on_exactly_aligned_sentences": round(totals["lemma_correct"] / max(aligned_n, 1), 4),
        "upos_accuracy_on_exactly_aligned_sentences": round(totals["upos_correct"] / max(aligned_n, 1), 4),
        "features_accuracy_on_exactly_aligned_sentences": round(totals["feats_correct"] / max(aligned_n, 1), 4),
        "uas_on_exactly_aligned_sentences": round(totals["head_correct"] / max(aligned_n, 1), 4),
        "las_on_exactly_aligned_sentences": round(totals["las_correct"] / max(aligned_n, 1), 4),
        "note": "Attribute accuracies are conditional on an exact word-for-word match of each sentence's tokenization; unmatched sentences are excluded and coverage is reported separately.",
    }
