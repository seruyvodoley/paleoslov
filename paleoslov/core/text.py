from __future__ import annotations

import unicodedata
from dataclasses import dataclass


APOSTROPHES = {"’", "'", "ʼ"}


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    index: int


def tokenize(text: str) -> list[Token]:
    """Tokenize while retaining exact offsets and original Unicode spelling."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for pos, char in enumerate(text):
        category = unicodedata.category(char)
        is_letter = category.startswith("L")
        is_mark = category.startswith("M")
        apostrophe_inside = char in APOSTROPHES and start is not None and pos + 1 < len(text) and unicodedata.category(text[pos + 1]).startswith("L")
        if is_letter or (start is not None and is_mark) or apostrophe_inside:
            if start is None:
                start = pos
        elif start is not None:
            spans.append((start, pos))
            start = None
    if start is not None:
        spans.append((start, len(text)))
    return [Token(text[a:b], a, b, i) for i, (a, b) in enumerate(spans)]


def search_form(text: str) -> str:
    """A normalized copy for lookup only; never use it to replace source text."""
    return unicodedata.normalize("NFC", text).casefold()


def detect_tradition(text: str) -> tuple[str, str]:
    s = search_form(text)
    old_letters = sum(s.count(c) for c in "ѣѫѧѳѵѥѩѭ")
    modern_csl = sum(s.count(c) for c in "ѿ҇҃҄҅҆҈҉")
    if old_letters + modern_csl >= 2:
        return "Историческая кириллическая графика (языковая традиция не определена)", "низкая"
    if any(x in s for x in ("рци", "глаголи", "азъ", "рече", "бѣ", "естьством")):
        return "Возможная древнерусская или книжная традиция", "низкая"
    return "Традиция не определена", "низкая"
