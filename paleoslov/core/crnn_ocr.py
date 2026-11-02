"""Native inference adapter for the small Church Slavonic CRNN-CTC checkpoints."""
from __future__ import annotations

from pathlib import Path
import json
import time

import torch
import torch.distributed.rpc  # PyTorch lazily exposes this namespace; frozen builds need it registered.
from torch import nn
from PIL import Image
import numpy as np


class CRNN(nn.Module):
    def __init__(self, num_classes: int, config: dict):
        super().__init__()
        height = int(config.get("img_height", 128))
        filters = config.get("cnn_filters", [12, 24, 48, 48])
        pools = config.get("cnn_poolsize", [2, 2, 0, 2])
        hidden = int(config.get("rnn_hidden", 256))
        layers = int(config.get("rnn_layers", 3))
        dropout = float(config.get("dropout", 0.5))
        self.cnn_poolsize = pools
        cnn_layers = []
        in_channels = 1
        for i, out_channels in enumerate(filters):
            cnn_layers.extend([nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1), nn.BatchNorm2d(out_channels), nn.LeakyReLU(0.2, inplace=True)])
            if pools[i] > 0:
                cnn_layers.append(nn.MaxPool2d(kernel_size=2, stride=2))
            in_channels = out_channels
        self.cnn = nn.Sequential(*cnn_layers)
        rnn_input = filters[-1] * (height // (2 ** sum(1 for p in pools if p > 0)))
        self.rnn = nn.LSTM(rnn_input, hidden, num_layers=layers, dropout=dropout if layers > 1 else 0, bidirectional=True)
        self.lin_dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden * 2, num_classes)

    def forward(self, x):
        conv = self.cnn(x)
        batch, channels, height, width = conv.shape
        sequence = conv.permute(3, 0, 1, 2).reshape(width, batch, channels * height)
        output, _ = self.rnn(sequence)
        return torch.nn.functional.log_softmax(self.fc(self.lin_dropout(output)), dim=2)


class CRNNLineRecognizer:
    def __init__(self, checkpoint: Path, config_path: Path, *, device: str = "cpu"):
        self.checkpoint_path = Path(checkpoint)
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        loaded = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
        state = loaded.get("model_state_dict", loaded.get("state_dict", loaded))
        self.idx2char = loaded.get("idx2char")
        if not isinstance(self.idx2char, dict) or "fc.weight" not in state:
            raise ValueError("Файл CRNN не содержит ожидаемую таблицу символов и веса модели.")
        self.model = CRNN(int(state["fc.weight"].shape[0]), config)
        self.model.load_state_dict(state, strict=True)
        if device == "mps" and torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")
        self.model.to(self.device).eval()

    def transcribe(self, image: Image.Image) -> tuple[str, float]:
        if image.mode != "L":
            image = image.convert("L")
        target_height = 128
        width = max(1, round(image.width * target_height / image.height))
        image = image.resize((width, target_height), Image.Resampling.LANCZOS)
        pixels = np.asarray(image, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(pixels).unsqueeze(0).unsqueeze(0)
        tensor = ((tensor - 0.5) / 0.5).to(self.device)
        with torch.inference_mode():
            output = self.model(tensor)
            probs = output.exp()[:, 0, :]
            confidence, indices = probs.max(dim=1)
        chars = []
        previous = -1
        scores = []
        for idx, score in zip(indices.tolist(), confidence.tolist()):
            if idx and idx != previous:
                char = self.idx2char.get(idx, "")
                if char in {"<space>", "<SPACE>"}:
                    char = " "
                chars.append(char)
                if char:
                    scores.append(score)
            previous = idx
        return "".join(chars), sum(scores) / len(scores) if scores else 0.0


def _recognize_with_model(image_path: Path, recognizer: CRNNLineRecognizer) -> list[dict]:
    from kraken.pageseg import segment
    original = Image.open(image_path).convert("L")
    segmentation = segment(original.convert("1"), text_direction="horizontal-lr")
    pad = max(4, round(original.height * 0.004))
    lines = []
    for line_number, row in enumerate(segmentation.lines):
        x0, y0, x1, y1 = [int(v) for v in row.bbox]
        crop = original.crop((max(0, x0 - pad), max(0, y0 - pad), min(original.width, x1 + pad), min(original.height, y1 + pad)))
        text, confidence = recognizer.transcribe(crop)
        lines.append({"text": text, "line": line_number, "bbox": [x0, y0, x1 - x0, y1 - y0], "confidence": confidence})
    return lines


def recognize_pages(image_paths: list[Path], checkpoint: Path, config_path: Path, *, device: str = "cpu") -> dict:
    """Load a model once and reuse it across pages; Kraken HPP segments page lines."""
    started = time.perf_counter()
    recognizer = CRNNLineRecognizer(checkpoint, config_path, device=device)
    pages = [_recognize_with_model(path, recognizer) for path in image_paths]
    return {
        "engine": "CRNN-CTC Church Slavonic" if "church-slavonic" in str(checkpoint) else "CRNN-CTC Prosta Mova",
        "model": checkpoint.name,
        "pages": pages,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "device": str(recognizer.device),
        "warning": "Страницы сегментированы эвристическим Kraken HPP; проверьте найденные строки и оригинальные знаки по изображению.",
    }
