---
language:
- uk
- be
- ru
tags:
- handwritten-text-recognition
- htr
- ocr
- historical-documents
- ukrainian
- belarusian
- prosta-mova
- cyrillic
- crnn-ctc
- crnn
- ctc
license: apache-2.0
library_name: custom
---

# Prosta Mova HTR Model (Puigcerver CRNN)

A Handwritten Text Recognition (HTR) model for **Prosta Mova** — the Ruthenian language used in Ukrainian and Belarusian documents from the 16th to 18th centuries.
Trained on early printed books from the Ostroh Printery and Academy; suitable for
Ukrainian Church Slavonic texts as well as texts written in Prosta Mova.
Based on the CNN + BiLSTM + CTC architecture introduced in
[Puigcerver (2017)](https://www.jpuigcerver.net/pubs/jpuigcerver_icdar2017.pdf) and used as
the backbone of [PyLaia](https://github.com/jpuigcerver/PyLaia) and Transkribus.

This is a **clean-room PyTorch reimplementation** of that published architecture (PyLaia-inspired).
It does *not* use the PyLaia Python package and is not loadable by it —
training and inference run via plain PyTorch (see Usage below).

## Model Details

- **Architecture**: CNN encoder [12, 24, 48, 48 filters] + 3-layer Bidirectional LSTM (256 units) + CTC decoder ([Puigcerver 2017](https://www.jpuigcerver.net/pubs/jpuigcerver_icdar2017.pdf))
- **Input**: Grayscale line images, normalized to 128 px height with aspect ratio preserved
- **Output**: UTF-8 text (East/Ukrainian Church Slavonic and Prosta Mova Cyrillic with diacritical marks)
- **Vocabulary**: 186 symbols (`symbols.txt`), including punctuation and combining diacritics
- **Framework**: Pure PyTorch — clean-room reimplementation of the Puigcerver (2017) architecture (PyLaia-inspired); the PyLaia package is not required

## Performance

| Metric | Value |
|--------|-------|
| Validation CER | **3.77%** |
| Training epochs | 97 |
| Training lines | 58,843 |
| Training pages | 948 |
| Validation lines | 2,588 |
| Validation pages | 54 |

## Training Data

Trained on images of early printed books transcribed and exported from
[Transkribus](https://www.transkribus.org/) (see the corresponding
[Transkribus model page](https://app.transkribus.org/models/public/text/ukranian-church-slavonic-and-prosta-mova-printings)).
The dataset covers Church Slavonic Ruthenian printings from the Ostroh Printery and Academy
(end of the 16th to beginning of the 17th centuries).

**Source texts:**
- Ostroh Bible (1581)
- *Kniga o postničestvě* (1594)
- *Margarit* (1595)
- *Otpis na list v boze velebnogo otca Ipatija volodimirs'kago i berestejskogo episkopa* (1598)
- *Apokrisis* (1598–99)
- *Pravilo istinnago života christianskogo (Psaltir z vozsliduvannjam)* (1598)

The Transkribus training collection comprises 962 pages and 59,990 lines. Our CRNN-CTC model
was trained on a corresponding export: 58,843 training lines (948 pages) and 2,588 validation lines (54 pages). The dataset
was carefully preprocessed to correct EXIF rotation artifacts; aspect ratio preservation was applied to maintain character resolution.

The Transkribus model was created by Martin Meindl as part of the
[Continslav project](https://continslav.uni-freiburg.de/), building on a generic East Church
Slavonic printings model by Achim Rabus. Training data was prepared by Uliana Shtandenko
and Alexandre Trébuchon. Model curated by Achim Rabus (Slavic Department, University of Freiburg).

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
hf download achimrabus/crnn-ctc-prosta-mova --local-dir models/crnn-ctc-prosta-mova
```

### Inference

From the root of the clone:

```python
from inference_pylaia_native import PyLaiaInference
from PIL import Image

# Load model
model = PyLaiaInference(
    checkpoint_path="models/crnn-ctc-prosta-mova/best_model.pt",
    syms_path="models/crnn-ctc-prosta-mova/symbols.txt"
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
    --model-path models/crnn-ctc-prosta-mova/best_model.pt \
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

- Transcription of Prosta Mova and (Ukrainian) Church Slavonic early printed books
- Ukrainian and Belarusian historical document digitization (16th–18th centuries)
- Digital humanities research on early modern East Slavic texts 

## Limitations

- Optimized for Ostroh Printery-style printings; may underperform on other sources
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
