# Лицензии и атрибуция

Код приложения «Палеослов» распространяется с сохранением исключительных прав; открытая лицензия на него не выдана, а публикация репозитория не предоставляет права переиспользовать код. Сторонние библиотеки, модели и корпусные данные поставляются только на условиях их собственных лицензий ниже.

- Условия сторонних компонентов относятся только к этим компонентам и не распространяют лицензию на код «Палеослова».
- PySide6 Essentials и динамические библиотеки Qt включены в локальную сборку `.app`; PySide6 Essentials 6.12.0 объявляет `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. См. [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html) и [LGPLv3](https://www.gnu.org/licenses/lgpl-3.0.html). Для публичного распространения отдельно проверить соблюдение LGPL, сохранение уведомлений и возможность заменять динамические библиотеки.
- PyInstaller: загрузчик распространяется по GPL с исключением для приложений, собранных PyInstaller; см. [PyInstaller license](https://pyinstaller.org/en/stable/license.html).
- Python 3.12: PSF License; см. [Python license](https://docs.python.org/3/license.html).
- HTTPX: BSD-3-Clause.
- Pydantic: MIT.
- Beautiful Soup: MIT.
- pypdfium2 and bundled PDFium: BSD-3-Clause / Apache-2.0 plus dependency notices; include their license files with distributions: https://pypdfium2.readthedocs.io/en/stable/readme.html
- Kraken OCR/HTR: Apache-2.0 (check current notices from the installed distribution before redistribution): https://github.com/mittagessen/kraken
- PyTorch runtime used by the optional CRNN OCR worker: BSD-3-Clause. Its license and bundled third-party notices are copied under `data/licenses/pytorch-2.14.0/`; upstream: https://github.com/pytorch/pytorch/blob/main/LICENSE
- Kraken, NumPy, SciPy, scikit-image, and Pillow runtime notices for the OCR worker are copied under `data/licenses/`; the installed versions and license texts are preserved there for the app bundle.
- `Cyr02full_best.mlmodel`: CC BY 2.0, attributed to Achim Rabus, Walker Riggs Thompson, and Daniel Stökl Ben Ezra; source record https://zenodo.org/records/7755483
- CRNN-CTC Church Slavonic and CRNN-CTC Prosta Mova checkpoints: Apache-2.0 as declared by their Hugging Face model cards; include the upstream model README attribution. The model cards report validation CER, which is not a result measured by this application.
- UDPipe 1.2 models for Old Church Slavonic PROIEL and Old East Slavic TOROT: the redistributed model pack declares CC BY-NC-SA 4.0. Included for non-commercial use with attribution; notices in `data/models/udpipe/LICENSE.txt` and source repository https://github.com/jwijffels/udpipe.models.ud.2.5. The underlying treebanks have their own CC BY-NC-SA 4.0 notices.
- `ufal.udpipe` Python binding 1.4.0.1: see the package metadata and upstream license at https://github.com/ufal/udpipe.
- pytest: MIT.
- TOROT включён в приложение для локального поиска. На странице UD TOROT и в LICENSE.txt указана CC BY-NC-SA 4.0; атрибуция и копия лицензии входят в комплект. PROIEL не включён.
- Ollama, Qwen3, mT5 и исследовательские переводные корпуса не входят в стабильную сборку приложения. Их файлы и экспериментальные веса хранятся отдельно и не устанавливаются вместе с DMG.
- `k-mktr/church_slavonic_bible_cu` and `k-mktr/russian_synodal_ru`: the dataset cards declare the 1757 Elizabeth Bible and 1876 Synodal Bible public domain. That declaration is from the dataset publisher and has not been independently legally verified. The downloaded source files and metadata remain outside the `.app`; any redistribution or model release needs attribution, provenance, and a fresh rights review: https://huggingface.co/datasets/k-mktr/church_slavonic_bible_cu and https://huggingface.co/datasets/k-mktr/russian_synodal_ru
- The public `i1oveMyse1f/old-slavic-mt` GitHub repository has no root LICENSE file and aggregates scraped datasets whose source rights differ. Its data are not copied into this project or used for training unless individual source licenses are established: https://github.com/i1oveMyse1f/old-slavic-mt
- UD Old East Slavic Birchbark (`data/raw/ud_birchbark/`): official treebank LICENSE.txt declares CC BY-SA 4.0. Preserve the attribution and share-alike terms for derived redistributions; do not silently bundle the extracted text in the app. Source: https://github.com/UniversalDependencies/UD_Old_East_Slavic-Birchbark

В DMG включены notices и тексты лицензий собранных компонентов в папке `licenses` и файле `LICENSES.md`. Условия отдельных компонентов продолжают действовать независимо от условий кода приложения. `.app` не нотариализован: macOS может потребовать подтверждение первого запуска через Finder.
