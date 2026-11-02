"""Leakage-safe grouping and conservative near-duplicate checks for MT data."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Iterable


GOSPEL_BOOKS = {"matthew", "mark", "luke", "john"}
RELATED_BIBLICAL_WORKS = {
    "historical_books": {"1 samuel", "2 samuel", "1 kings", "2 kings", "1 chronicles", "2 chronicles"},
    "ezra_nehemiah": {"ezra", "nehemiah"},
}


def text_key(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text or "")).casefold()
    text = text.translate(str.maketrans({"ѣ": "е", "Ѣ": "е", "і": "и", "І": "и", "ѳ": "ф", "Ѳ": "ф", "ѵ": "и", "Ѵ": "и"}))
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


def _shingles(value: str) -> set[tuple[str, ...]]:
    words = text_key(value).split()
    if len(words) < 6:
        return set()
    n = 3 if len(words) >= 12 else 2
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def near_duplicate_edges(
    rows: list[dict], fields: tuple[str, ...] = ("source_original", "target_reference"),
    threshold: float = 0.84, max_posting: int = 300,
) -> list[dict]:
    """Find likely near duplicates with indexed word shingles.

    This is a conservative leak detector, not a semantic-equivalence metric.
    Very common shingles are ignored to keep the inverted index bounded.
    """
    found: dict[tuple[str, str], dict] = {}
    for field in fields:
        grams_by_row: dict[str, set[tuple[str, ...]]] = {}
        postings: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for row in rows:
            row_id = str(row.get("pair_id", ""))
            grams = _shingles(str(row.get(field, "")))
            if not row_id or not grams:
                continue
            grams_by_row[row_id] = grams
            for gram in grams:
                postings[gram].append(row_id)
        shared: Counter[tuple[str, str]] = Counter()
        for ids in postings.values():
            if len(ids) > max_posting:
                continue
            unique = sorted(set(ids))
            for i, left in enumerate(unique):
                for right in unique[i + 1:]:
                    shared[(left, right)] += 1
        for (left, right), count in shared.items():
            a, b = grams_by_row[left], grams_by_row[right]
            if count < 2:
                continue
            similarity = count / len(a | b)
            if similarity < threshold:
                continue
            key = (left, right)
            edge = found.setdefault(key, {"pair_id_a": left, "pair_id_b": right, "fields": [], "similarity": 0.0})
            edge["fields"].append(field)
            edge["similarity"] = max(edge["similarity"], round(similarity, 4))
    return sorted(found.values(), key=lambda e: (e["pair_id_a"], e["pair_id_b"]))


class UnionFind:
    def __init__(self, items: Iterable[str]):
        self.parent = {item: item for item in items}
        self.rank = {item: 0 for item in self.parent}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        if self.rank[a] < self.rank[b]:
            a, b = b, a
        self.parent[b] = a
        if self.rank[a] == self.rank[b]:
            self.rank[a] += 1


def biblical_work_family(book: str) -> str:
    normalized = text_key(book)
    if normalized in GOSPEL_BOOKS:
        return "gospels"
    for family, members in RELATED_BIBLICAL_WORKS.items():
        if normalized in members:
            return family
    return normalized


def assign_leakage_safe_splits(
    rows: list[dict], group_field: str, seed: int = 20261102,
    ratios: dict[str, float] | None = None, extra_group_field: str | None = None,
) -> tuple[dict[str, str], dict]:
    """Assign records to splits, co-locating works/documents and duplicate text.

    Exact source/target matches, high-overlap near duplicates, and requested
    related-work families are unioned before deterministic size balancing.
    """
    import random

    ratios = ratios or {"train": 0.8, "dev": 0.1, "test": 0.1}
    ids = [str(row["pair_id"]) for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("pair_id must be unique before split assignment")
    uf = UnionFind(ids)
    group_owner: dict[tuple[str, str], str] = {}
    exact_owners: dict[tuple[str, str], str] = {}
    for row in rows:
        row_id = str(row["pair_id"])
        group_values = [(group_field, str(row.get(group_field, "")))]
        if extra_group_field and row.get(extra_group_field):
            group_values.append((extra_group_field, str(row[extra_group_field])))
        for field, value in group_values:
            if value:
                key = (field, value)
                if key in group_owner:
                    uf.union(row_id, group_owner[key])
                else:
                    group_owner[key] = row_id
        for field in ("source_original", "target_reference"):
            normalized = text_key(row.get(field, ""))
            if not normalized:
                continue
            key = (field, normalized)
            if key in exact_owners:
                uf.union(row_id, exact_owners[key])
            else:
                exact_owners[key] = row_id
    near = near_duplicate_edges(rows)
    for edge in near:
        uf.union(edge["pair_id_a"], edge["pair_id_b"])

    components: dict[str, list[str]] = defaultdict(list)
    for row_id in ids:
        components[uf.find(row_id)].append(row_id)
    rows_by_id = {str(row["pair_id"]): row for row in rows}
    components_list = list(components.values())
    random.Random(seed).shuffle(components_list)
    components_list.sort(key=len, reverse=True)
    total = len(rows)
    counts = {name: 0 for name in ratios}
    assigned: dict[str, str] = {}
    for component in components_list:
        split = min(ratios, key=lambda name: ((counts[name] + len(component)) / max(ratios[name], 1e-9), name))
        for row_id in component:
            assigned[row_id] = split
        counts[split] += len(component)
    component_ids: dict[str, str] = {}
    for component in components_list:
        group_hash = hashlib.sha256("\n".join(sorted(component)).encode()).hexdigest()[:16]
        for row_id in component:
            component_ids[row_id] = group_hash
    audit = audit_split_leaks(rows, assigned, near)
    audit.update({
        "split_counts": counts,
        "split_ratios_target": ratios,
        "components": len(components_list),
        "largest_component_records": max((len(c) for c in components_list), default=0),
        "near_duplicate_edges": len(near),
        "component_id_by_pair_id": component_ids,
        "component_record_counts": sorted((len(c) for c in components_list), reverse=True),
    })
    if any(audit[key] for key in ("exact_source_cross_split", "exact_target_cross_split", "near_duplicate_cross_split")):
        raise ValueError(f"Leakage remains after grouping: {audit}")
    return assigned, audit


def audit_split_leaks(rows: list[dict], assigned: dict[str, str], near_edges: list[dict] | None = None) -> dict:
    exact_cross: dict[str, set[str]] = {"source_original": set(), "target_reference": set()}
    owners: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        split = assigned[str(row["pair_id"])]
        for field in exact_cross:
            value = text_key(row.get(field, ""))
            if value:
                owners[(field, value)].add(split)
    for (field, value), splits in owners.items():
        if len(splits) > 1:
            exact_cross[field].add(value)
    near_edges = near_edges if near_edges is not None else near_duplicate_edges(rows)
    by_id = {str(row["pair_id"]): row for row in rows}
    near_cross = [edge for edge in near_edges if assigned[edge["pair_id_a"]] != assigned[edge["pair_id_b"]]]
    combinations = {}
    for a, b in (("train", "dev"), ("train", "test"), ("dev", "test")):
        ra = [r for r in rows if assigned[str(r["pair_id"])] == a]
        rb = [r for r in rows if assigned[str(r["pair_id"])] == b]
        combos = {}
        for field in exact_cross:
            A = {text_key(r.get(field, "")) for r in ra if text_key(r.get(field, ""))}
            B = {text_key(r.get(field, "")) for r in rb if text_key(r.get(field, ""))}
            combos[field] = len(A & B)
        combinations[f"{a}-{b}"] = combos
    return {
        "exact_source_cross_split": len(exact_cross["source_original"]),
        "exact_target_cross_split": len(exact_cross["target_reference"]),
        "near_duplicate_cross_split": len(near_cross),
        "cross_split_examples": near_cross[:50],
        "intersection_counts_by_pair": combinations,
    }
