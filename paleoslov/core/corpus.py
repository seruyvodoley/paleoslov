from __future__ import annotations

from pathlib import Path
import httpx

from .linguistics import parse_conllu


TOROT_LICENSE_URL = "https://raw.githubusercontent.com/UniversalDependencies/UD_Old_East_Slavic-TOROT/master/LICENSE.txt"
TOROT_DATA_URL = "https://raw.githubusercontent.com/UniversalDependencies/UD_Old_East_Slavic-TOROT/master/orv_torot-ud-train.conllu"
TOROT_SOURCE_URL = "https://universaldependencies.org/treebanks/orv_torot/index.html"
TOROT_LICENSE = "CC BY-NC-SA 4.0"


def download_torot(destination: Path) -> tuple[str, list[dict[str, str]]]:
    """Fetch only after explicit user action; verify the upstream license first."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Paleoslov/0.1 (local educational tool)"}
    with httpx.Client(timeout=60, follow_redirects=True, headers=headers) as client:
        license_response = client.get(TOROT_LICENSE_URL)
        license_response.raise_for_status()
        license_text = license_response.text
        if "Attribution-NonCommercial-ShareAlike 4.0" not in license_text:
            raise RuntimeError("Лицензия TOROT не совпала с ожидаемой CC BY-NC-SA 4.0; импорт остановлен.")
        response = client.get(TOROT_DATA_URL)
        response.raise_for_status()
        if len(response.content) > 80_000_000:
            raise RuntimeError("Файл корпуса неожиданно велик; импорт остановлен.")
        destination.write_bytes(response.content)
        destination.with_name("LICENSE.txt").write_text(license_text.strip() + f"\n\nSource: {TOROT_SOURCE_URL}\nRaw file: {TOROT_DATA_URL}\n", encoding="utf-8")
    rows = parse_conllu(destination.read_text(encoding="utf-8"))
    if not rows:
        raise RuntimeError("В загруженном файле не найдены корректные строки CoNLL-U.")
    return license_text, rows
