"""Canonical source-task prefixes shared by mT5 training and token audits."""
from __future__ import annotations


def mt5_task_prefix(row: dict) -> str:
    tradition = str(row.get("source_tradition", ""))
    language = row.get("source_language")
    if "Elizabeth Bible" in tradition:
        return "translate 18th-century Church Slavonic to modern Russian: "
    if language == "Old East Slavic":
        return "translate Old East Slavic to modern Russian: "
    if language == "Old Church Slavonic":
        return "translate Old Church Slavonic to modern Russian: "
    return "translate historical Slavic to modern Russian: "
