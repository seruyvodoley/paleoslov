"""Self-contained subprocess entrypoint packaged with the macOS app."""
from __future__ import annotations

import sys
import json
import multiprocessing
import resource
import time
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print("Использование: paleoslov-ocr JOBS.json MODEL DEVICE", file=sys.stderr)
        return 2
    jobs_path, model, device = sys.argv[1:]
    manifest = json.loads(Path(jobs_path).read_text(encoding="utf-8"))
    jobs = manifest.get("jobs", []) if isinstance(manifest, dict) else manifest
    metrics_path = Path(manifest["metrics"]) if isinstance(manifest, dict) and manifest.get("metrics") else None
    # Kraken's Click CLI provides the same segmentation + recognition pipeline
    # in development and in the frozen self-contained worker.
    from kraken.kraken import cli
    sys.argv = ["kraken", "--device", device]
    for job in jobs:
        sys.argv.extend(["-i", job["image"], job["xml"]])
    sys.argv.extend(["-a", "segment", "-bl", "ocr", "-m", model])
    started = time.perf_counter()
    # Click's default standalone mode raises SystemExit(0) after a successful run,
    # which would skip writing the resource metrics consumed by the app.
    cli.main(standalone_mode=False)
    if metrics_path:
        # macOS reports ru_maxrss in bytes (Linux reports KiB).
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
        metrics_path.write_text(json.dumps({"elapsed_ms": round((time.perf_counter() - started) * 1000), "peak_memory_mb": round(peak, 1)}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    # The frozen worker is reused by PyTorch/Kraken's spawned child processes.
    # Handle their --multiprocessing-fork invocation before parsing our own CLI.
    multiprocessing.freeze_support()
    raise SystemExit(main())
