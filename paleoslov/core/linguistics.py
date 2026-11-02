from __future__ import annotations

from dataclasses import dataclass, field
import re
from .text import Token, tokenize


@dataclass(frozen=True)
class Observation:
    rule_id: str
    label: str
    detail: str
    evidence_status: str = "Наблюдение; требуется контекстная проверка"
    token_start: int | None = None
    token_end: int | None = None
    sources: tuple[dict[str, str], ...] = field(default_factory=tuple)
    alternatives: tuple[str, ...] = field(default_factory=tuple)


# This registry deliberately contains claims only where an identified scholarly
# source and a particular passage are available. A match is a research lead,
# never an automatic phonological or dialectal conclusion.
RULES = [
    {"id": "ORTH-YAT", "name": "Буква ѣ", "traditions": ["древнерусская", "старославянская", "церковнославянская"],
     "limit": "Одна графема не устанавливает этимон, произношение или говор.", "sources": [
         {"title": "Михеев С. М. Corrigenda epigraphica. Часть 1", "year": "2025", "url": "https://rjano.ruslang.ru/sites/default/files/articles/2025/1/2025-1_266-288.pdf", "passage": "С. 279–280: в надписи Славьнь <Славьнѣ> форма ѣ осталась недописанной и выглядит как ь; автор рассматривает возможность отдельной помарки, а не правила смешения."},
         {"title": "Описание берестяной грамоты № 336, СПбИИ РАН", "year": "описание 2022", "url": "https://gis.spbiiran.ru/cyrillic/cyrillic-alphabet-1217/acts/2710", "passage": "Строки 104–112: исправление Е на Ъ в РОЖЪНѢТОВИ; обсуждаются графическое и языковое объяснения, диалектные окончания и две версии ситуации."}
     ]},
    {"id": "ORTH-JERS", "name": "Редуцированные ъ и ь", "traditions": ["древнерусская", "старославянская", "церковнославянская"],
     "limit": "Позицию редуцированного и его рефлекс нельзя определять без этимологии, морфологии и датировки.", "sources": [
         {"title": "К вопросу о падении редуцированных гласных в древнерусском языке", "year": "2022", "url": "https://vedicworld.org.ua/ru/stati/naucnaa-stata-k-padeniiu-reducirovannyh-glasnyh-v-drevnerusskom-azyke-hronologia", "passage": "Раздел о бытовой графике: взаимные замены ъ/о и ь/е/ѣ могут иметь графическую природу; смешения сами по себе не доказывают фонетического изменения."}
     ]},
    {"id": "ORTH-NASAL", "name": "Юсы ѫ, ѧ и йотированные варианты", "traditions": ["старославянская", "церковнославянская"], "limit": "Буква показывает графическую традицию; фонетическое значение и рефлекс требуют датировки, письменной традиции и разбора конкретной формы.", "sources": [
        {"title": "Szeptyński, Rafał. Nasal Vowels", "year": "2024/2025", "url": "https://doi.org/10.1163/2589-6229_ESLO_COM_038638", "passage": "Обзор наследования славянских носовых гласных, их исторических изменений и графического обозначения в традициях."},
        {"title": "Mareš, V. F. Происхождение славянского носового ѫ", "year": "1963", "url": "https://inslav.ru/images/stories/pdf/VSJa_7_%281963%29.pdf", "passage": "Историко-сравнительное исследование реконструкции носовых гласных; конкретное написание памятника требует отдельного контекста."}
    ]},
    {"id": "ORTH-THETA", "name": "Буквы ѳ и ѵ", "traditions": ["книжная"], "limit": "Могут отражать книжную орфографическую традицию, но не доказывают происхождение текста.", "sources": []},
]


def analyze_orthography(text: str) -> list[Observation]:
    observations: list[Observation] = []
    tokens = tokenize(text)
    checks = [
        ("ѣ", "ORTH-YAT", "Найдена ѣ. Проверьте чтение по изображению, морфологию, этимон и параллели; пока нельзя заключить, что здесь ожидалось ь."),
        ("ъь", "ORTH-JERS", "Найдены ъ/ь. Определение сильной или слабой позиции требует этимона, морфологии, периода и традиции."),
        ("ѫѧѩѭ", "ORTH-NASAL", "Найдена графема из ряда юсов (включая йотированные ѩ/ѭ). Это графическое наблюдение: фонетическая интерпретация требует датировки, традиции, леммы и контекста; одного знака недостаточно для вывода о говоре."),
        ("ѳѵ", "ORTH-THETA", "Найдены ѳ/ѵ. Возможна книжная орфографическая традиция; это не доказательство происхождения текста."),
    ]
    by_id = {rule["id"]: rule for rule in RULES}
    for chars, rule_id, explanation in checks:
        rule = by_id[rule_id]
        for token in tokens:
            if any(char in token.text.casefold() for char in chars):
                observations.append(Observation(
                    rule_id, rule["name"], explanation, "Графическое наблюдение; этимология не подтверждена",
                    token.start, token.end, tuple(rule["sources"]),
                    ("Смешение графем в конкретной системе письма", "Палеографическая ошибка или исправление", "Этимологически регулярное написание", "OCR-ошибка") if rule_id == "ORTH-YAT" else (),
                ))
    # This is a documented text parallel, not a dialect classifier. The
    # bibliography page gives the reading and conditional date for gramota 247.
    parallel = re.search(r"а\s+замъке\s+кѣле\s+а\s+двьри\s+кѣлѣ", text, flags=re.IGNORECASE)
    if parallel:
        observations.append(Observation(
            "PARALLEL-NOVGOROD-247", "Текстовая параллель: берестяная грамота № 247",
            "Последовательность совпадает с чтением грамоты № 247 из Новгорода (условная дата 1025–1050). Это помогает сверить чтение и перевод фрагмента, но само совпадение не устанавливает происхождение всего анализируемого текста или его говор.",
            "Точная опубликованная параллель; не диалектологический вывод",
            parallel.start(), parallel.end(),
            ({"title": "Грамота № 247 · Древнерусские берестяные грамоты", "year": "условная дата 1025–1050", "url": "https://gramoty.ru/birchbark/document/show/novgorod/247/", "passage": "Строка 29: а замъке кѣле а двьри кѣлѣ; на странице приведены русский перевод и варианты интерпретации."},),
            ("В опубликованном переводе: «а замок цел и двери целы»", "Чтение следует проверить по изображению грамоты и контексту публикации"),
        ))
    return observations


def investigate_yat_vs_jer(form: str, *, verified_reading: bool | None = None,
                           lemma: str | None = None, grammatical_analysis: str | None = None,
                           date: str | None = None, tradition: str | None = None,
                           corpus_parallels: list[dict] | None = None) -> dict:
    """Conservative case report for a suspected ѣ : ь mismatch.

    The tool does not guess the expected grapheme. It makes the evidence needed
    to support that claim explicit and returns an insufficient-data status when
    a lemma, manuscript context, and parallels are missing.
    """
    stages = [
        {"check": "OCR / чтение по изображению", "status": "подтверждено" if verified_reading is True else "не проверено" if verified_reading is None else "есть сомнение"},
        {"check": "лемма и грамматическая форма", "status": "есть данные" if lemma and grammatical_analysis else "не установлены", "lemma": lemma, "analysis": grammatical_analysis},
        {"check": "датировка и письменная традиция", "status": "есть данные" if date and tradition else "не установлены", "date": date, "tradition": tradition},
        {"check": "корпусные параллели", "status": "есть совпадения" if corpus_parallels else "не найдены / не проверены", "matches": corpus_parallels or []},
    ]
    evidence_collected = verified_reading is True and bool(lemma and grammatical_analysis and date and tradition and corpus_parallels)
    return {
        "form": form,
        "claim": "В позиции ѣ предположительно ожидалось ь",
        "status": "данные собраны; вывод требует филологической проверки" if evidence_collected else "данных недостаточно для вывода",
        "checks": stages,
        "alternatives": ["бытовая/неполноразличительная графика", "исправление или особенность начертания", "графическая ошибка писца", "OCR неверно распознал знак", "этимологически ожидаемая ѣ; гипотеза о ь неверна"],
        "sources": by_rule_sources("ORTH-YAT", "ORTH-JERS"),
        "note": "Ни одно найденное совпадение отдельно не доказывает этимон или диалект; для заключения нужно сопоставить весь документ и систему письма.",
    }


def by_rule_sources(*rule_ids: str) -> list[dict[str, str]]:
    selected = set(rule_ids)
    return [source for rule in RULES if rule["id"] in selected for source in rule["sources"]]


def parse_conllu(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) != 10 or "-" in cols[0] or "." in cols[0]:
            continue
        rows.append(dict(zip(("id", "form", "lemma", "upos", "xpos", "feats", "head", "deprel", "deps", "misc"), cols)))
    return rows


def selected_token(text: str, start: int, end: int) -> Token | None:
    return next((t for t in tokenize(text) if t.start <= start < t.end or t.start < end <= t.end), None)
