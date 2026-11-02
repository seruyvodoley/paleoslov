"""JSON subprocess interface for CRNN OCR; keeps PyTorch out of the GUI process."""
from __future__ import annotations

import json
import os
import resource
import sys
from pathlib import Path

from paleoslov.core.crnn_ocr import recognize_pages


def main() -> int:
    if len(sys.argv) != 4:
        print("Использование: paleoslov-crnn JOBS.json MODEL_DIR DEVICE", file=sys.stderr)
        return 2
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    model_dir = Path(sys.argv[2])
    device = sys.argv[3]
    kind = manifest["model"]
    folder = model_dir / kind
    result = recognize_pages(
        [Path(x) for x in manifest["images"]],
        folder / "best_model.pt",
        folder / "model_config.json",
        device=device,
    )
    result["model_id"] = kind
    result["model_license"] = "Apache-2.0"
    result["peak_memory_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024), 1)
    Path(manifest["output"]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    # Torch may leave background runtime threads alive after inference. This dedicated helper
    # has already flushed its JSON result and must exit so the GUI can continue its pipeline.
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
