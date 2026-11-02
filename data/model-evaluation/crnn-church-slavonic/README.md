---
language:
- chu
tags:
- handwritten-text-recognition
- htr
- ocr
- historical-documents
- church-slavonic
- cyrillic
- crnn-ctc
- crnn
- ctc
license: apache-2.0
library_name: custom
---

# Church Slavonic HTR Model (Puigcerver CRNN)

A Handwritten Text Recognition (HTR) model for **Church Slavonic manuscripts**, based on the
CNN + BiLSTM + CTC architecture introduced in
[Puigcerver (2017)](https://www.jpuigcerver.net/pubs/jpuigcerver_icdar2017.pdf) and used as
the backbone of [PyLaia](https://github.com/jpuigcerver/PyLaia) and Transkribus.

This is a **clean-room PyTorch reimplementation** of that published architecture (PyLaia-inspired).
It does *not* use the PyLaia Python package and is not loadable by it —
training and inference run via plain PyTorch (see Usage below).

## Model Details

- **Architecture**: CNN encoder [12, 24, 48, 48 filters] + 3-layer Bidirectional LSTM (256 units) + CTC decoder ([Puigcerver 2017](https://www.jpuigcerver.net/pubs/jpuigcerver_icdar2017.pdf))
- **Input**: Grayscale line images, normalized to 128 px height with aspect ratio preserved
- **Output**: UTF-8 text (Church Slavonic characters including titlos, abbreviation marks, and diacritics)
- **Vocabulary**: 152 symbols (`symbols.txt`)
- **Framework**: Pure PyTorch — clean-room reimplementation of the Puigcerver (2017) architecture (PyLaia-inspired); the PyLaia package is not required

## Performance

| Metric | Value |
|--------|-------|
| Validation CER | **2.89%** |
| Training epochs | 59 |
| Training lines | 309,959 |
| Training pages | 2,643 |
| Validation lines | 20,679 |
| Validation pages | 205 |

## Training Data

Trained on Church Slavonic handwriting images transcribed and exported from
[Transkribus](https://www.transkribus.org/) (see the corresponding
[Transkribus model page](https://app.transkribus.org/models/public/text/generic-church-slavonic-handwriting-3)).
The dataset covers Old Cyrillic script styles (uncial and semi-uncial), primarily East Slavic
with South Slavic material included.

**Source manuscripts:**
- Codex Suprasliensis (10th–11th c., South Slavic recension)
- Catecheses of Cyril of Jerusalem (transmitted version: 11th c., East Slavic recension)
- Methodius of Olympus: *Symposion* (transmitted version: 17th c., East Slavic recension)
- Velikie Minei Četʹi (16th c., East Slavic recension): large parts of the March and May volumes, Apostolos from the June volume

Our CRNN-CTC model was trained on the full collection: 309,959 training lines (2,643 pages)
and 20,679 validation lines (205 pages), exported from Transkribus.

The Transkribus model was trained by Elena Renje as part of the
[QuantiSlav project](https://quantislav.badw.de/) and curated by Achim Rabus
(Slavic Department, University of Freiburg).

## Usage

### Requirements

The inference code lives in [polyscriptor](https://github.com/achimrabus/polyscriptor) and imports
other modules from it, so run it from a clone of the repository. Install into a fresh virtual
environment in one pip call; `requirements-kraken.txt` adds the Kraken segmentation used for full
pages below (for a GPU install, see the polyscriptor README):

```bash
git clone https://github.com/achimrabus/polyscriptor
cd polyscriptor
python3 -m venv htr_env && source htr_env/bin/activate
pip install -r requirements.txt -r requirements-kraken.txt
hf download achimrabus/crnn-ctc-church-slavonic --local-dir models/crnn-ctc-church-slavonic
```

### Inference

From the root of the clone:

```python
from inference_pylaia_native import PyLaiaInference
from PIL import Image

# Load model
model = PyLaiaInference(
    checkpoint_path="models/crnn-ctc-church-slavonic/best_model.pt",
    syms_path="models/crnn-ctc-church-slavonic/symbols.txt"
)

# Transcribe a line image
image = Image.open("line_image.jpg")
text, confidence = model.transcribe(image)
print(text, f"(confidence {confidence:.2f})")
```

> **Note**: Input should be a single **text line image**, not a full page.
> Preprocessing (grayscale conversion, height normalization, aspect ratio preservation) is handled
> automatically by `inference_pylaia_native.py`.

For full-page inference with automatic line segmentation, use `batch_processing.py`. The neural
Kraken segmenter (`kraken-blla`) is strongly recommended; the default projection-based segmenter
(`hpp`) is fast but can miss most lines on complex pages:

```bash
python batch_processing.py \
    --engine crnn-ctc \
    --model-path models/crnn-ctc-church-slavonic/best_model.pt \
    --segmentation-method kraken-blla \
    --input-folder images/ \
    --output-folder output/
```

### Web Interface (recommended)

[polyscriptor](https://github.com/achimrabus/polyscriptor)'s main interface runs in the browser:
upload page images or PDFs, segment them automatically (Kraken) or reuse existing PAGE XML,
transcribe, correct lines inline and export TXT, CSV or PAGE XML. It runs on a laptop or on a
remote server (via SSH tunnel), and CRNN-CTC models also work without a GPU.

The web interface picks up any folder under `models/` that contains `best_model.pt` and
`symbols.txt`, so after the download above it only needs to be started:

```bash
uvicorn web.polyscriptor_server:app --host 0.0.0.0 --port 8765
# open http://localhost:8765 and choose the model under CRNN-CTC
```

### Desktop GUI

polyscriptor also ships PyQt6 desktop interfaces: `transcription_gui_plugin.py` for interactive
single pages (automatic line segmentation, PAGE XML export) and `polyscriptor_batch_gui.py` for
whole folders (uses existing PAGE XML files, e.g. from Transkribus, when available).

## Intended Use

- Transcription of Church Slavonic historical manuscripts
- Research in Slavic medieval studies and digital humanities

## Limitations

- Full-page segmentation quality depends on the segmentation method used upstream

## Citation

If you use this model in your research, please cite the architecture paper and this model:

```bibtex
@article{puigcerver2017multidimensional,
  title     = {Are Multidimensional Recurrent Layers Really Necessary for Handwritten Text Recognition?},
  author    = {Puigcerver, Joan},
  journal   = {Proceedings of the 14th IAPR International Conference on Document Analysis and Recognition (ICDAR)},
  year      = {2017},
  url       = {https://www.jpuigcerver.net/pubs/jpuigcerver_icdar2017.pdf}
}

@misc{rabus2026polyscriptor,
  title  = {Polyscriptor: Multi-Engine HTR Training \& Comparison Tool},
  author = {Rabus, Achim},
  year   = {2026},
  url    = {https://github.com/achimrabus/polyscriptor}
}
```
