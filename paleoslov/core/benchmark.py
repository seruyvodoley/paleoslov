"""Reproducible OCR comparison metrics without orthographic cleanup."""
from __future__ import annotations

import re
from collections.abc import Sequence


HISTORICAL = set("ѢѣѲѳѴѵѪѫѦѧѨѩѬѭѤѥ҃҇҆҄҅҈")


def edit_distance(reference: Sequence, hypothesis: Sequence) -> int:
    """Levenshtein distance using O(min(n,m)) memory."""
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for i, left in enumerate(reference, 1):
        current = [i]
        for j, right in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def score_transcription(reference: str, hypothesis: str) -> dict[str, float | int]:
    """Report raw Unicode CER/WER and historical-character errors; do not canonicalize spelling."""
    ref_chars = list(reference)
    hyp_chars = list(hypothesis)
    ref_words = re.findall(r"\S+", reference)
    hyp_words = re.findall(r"\S+", hypothesis)
    historical_ref = [char for char in ref_chars if char in HISTORICAL]
    historical_hyp = [char for char in hyp_chars if char in HISTORICAL]
    return {
        "cer": edit_distance(ref_chars, hyp_chars) / max(1, len(ref_chars)),
        "wer": edit_distance(ref_words, hyp_words) / max(1, len(ref_words)),
        "historical_char_errors": edit_distance(historical_ref, historical_hyp),
        "historical_char_reference_count": len(historical_ref),
        "reference_characters": len(ref_chars),
        "reference_words": len(ref_words),
    }
