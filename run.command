#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  /opt/homebrew/bin/python3.12 -m venv --copies .venv 2>/dev/null || python3.12 -m venv --copies .venv
fi
if ! .venv/bin/python -c 'import PySide6.QtWidgets, httpx, pydantic' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -e .
fi
.venv/bin/python -m paleoslov.app.main
