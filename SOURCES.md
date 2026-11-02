# Научные и технические источники

Проверено 2 ноября 2026 г. Ссылки на корпусные страницы используются как ориентиры для ручной проверки; включённые наборы данных сохраняют собственные лицензии и атрибуцию.

## Материалы рабочего сквозного сценария — 2 ноября 2026 г.

- Михеев, С. М. 2025. «Corrigenda epigraphica. Часть 1». *Русский язык в научном освещении* 1 (49), 266–288. https://rjano.ruslang.ru/sites/default/files/articles/2025/1/2025-1_266-288.pdf. С. 279–280: обсуждается недописанная ѣ, похожая на ь, в форме Славьнь <Славьнѣ>; автор допускает графическое исправление/описку. Это источник для осторожной проверки, не автоматического правила замены.
- «Берестяная грамота №336», описание СПбИИ РАН: https://gis.spbiiran.ru/cyrillic/cyrillic-alphabet-1217/acts/2710. Страница содержит дипломатическую форму, перевод, датировку и альтернативные орфографические/фонетические объяснения.
- «К вопросу о падении редуцированных гласных в древнерусском языке: хронология, фонологический механизм, отражение в памятниках»: https://vedicworld.org.ua/ru/stati/naucnaa-stata-k-padeniiu-reducirovannyh-glasnyh-v-drevnerusskom-azyke-hronologia. Обсуждает бытовые системы с меной ъ/о, ь/е/ѣ и предупреждает, что такие написания сами не доказывают фонетический переход. Для строгой научной цитаты следует сверить выходные данные и первоисточник, указанные на странице.
- Gramoty.ru, берестяная грамота №109: https://gramoty.ru/birchbark/document/show/novgorod/109/. Для фикстуры записаны опубликованные текст и перевод; формулировка контрольного перевода составлена заново и сохраняет варианты толкования. Изображение не копируется: условия повторного использования на странице не установлены.
- UD Old Church Slavonic PROIEL: https://github.com/UniversalDependencies/UD_Old_Church_Slavonic-PROIEL. Фикстуры A и C используют строки и золотую морфологическую разметку отложенного тестового корпуса; лицензия CC BY-NC-SA 4.0 указана в соседнем LICENSE-файле.
- Szeptyński, Rafał. “Nasal Vowels.” *Encyclopedia of Slavic Languages and Linguistics Online*, online 2024, updated 2025. https://doi.org/10.1163/2589-6229_ESLO_COM_038638. Обзор наследования, развития и графического обозначения славянских носовых гласных; само наблюдение букв ѫ/ѧ/ѩ/ѭ в конкретном памятнике не устанавливает произношение.
- Mareš, V. F. «Происхождение славянского носового ѫ». 1963. https://inslav.ru/images/stories/pdf/VSJa_7_%281963%29.pdf. Историко-сравнительный разбор реконструкции носовых; не источник для автоматической интерпретации отдельного написания без контекста.
- Параллельные переводы A/B/C: см. `data/translations/parallel_references.json`. A — контрольная русская версия Мф. 6:9–13, B — редакционный пересказ опубликованного перевода Gramoty.ru, C — непроверенный независимым филологом редакционный черновик. Приложение применяет только точное сопоставление полного текста.

## Корпуса

- Universal Dependencies, **UD Old East Slavic TOROT**: https://universaldependencies.org/treebanks/orv_torot/index.html — на странице указана лицензия CC BY-NC-SA 4.0. Это конверсия части TOROT; охватывает тексты разных средневековых и ранненововременных жанров. Страница отмечает ручную аннотацию с автоматической предварительной обработкой. Условия корпуса и лежащих в основе текстов надо читать перед повторным распространением.
- Universal Dependencies, **UD Old Church Slavonic PROIEL**: https://universaldependencies.org/treebanks/cu_proiel/index.html — на странице указана CC BY-NC-SA 4.0. Содержит выборку канонических старославянских текстов; леммы, POS и признаки частично преобразованы в UD из исходной схемы.
- Universal Dependencies, **лицензирование**: https://universaldependencies.org/contributing/licensing.html — лицензии отдельных деревьев различаются; следует проверить LICENSE.txt и метаданные выбранного корпуса.
- Universal Dependencies, **загрузки**: https://universaldependencies.org/download.html — официальные релизы доступны через LINDAT/CLARIAH-CZ.

## Параллельный корпус для специализированного перевода — 2 ноября 2026 г.

- Hugging Face `k-mktr/church_slavonic_bible_cu`: карточка датирует источник Елизаветинской Библией 1757 года, сообщает 31 307 стихов, Parquet 2.77 MB и объявляет текст общественным достоянием. Источник хранится в `data/raw/parallel_bibles/church_slavonic_bible_cu.parquet`; лицензия источника указана карточкой набора, а не проверена независимо: https://huggingface.co/datasets/k-mktr/church_slavonic_bible_cu
- Hugging Face `k-mktr/russian_synodal_ru`: карточка датирует перевод 1876 годом, сообщает 31 169 стихов, Parquet 2.79 MB и объявляет текст общественным достоянием. Источник хранится в `data/raw/parallel_bibles/russian_synodal_ru.parquet`; лицензия источника указана карточкой набора, а не проверена независимо: https://huggingface.co/datasets/k-mktr/russian_synodal_ru
- **Предупреждение о редакциях:** карточки описывают разные основы перевода (Елизаветинская редакция сверялась с Септуагинтой; Синодальный перевод — с еврейскими, арамейскими и греческими оригиналами). Поэтому одинаковая ссылка на стих не доказывает совпадение содержания. Скрипт `scripts/prepare_parallel_translation.py` соединяет строки только по названию книги, главе и стиху; расхождение `book_number`, `verse_id`, чисел и подозрительной длины сохраняется в отчёте как флаг. Все автоматические пары остаются `unreviewed` и не допускаются к обучению без ручного подтверждения.
- Номера книг в исходниках несовместимы: в демонстрационных строках набора cu книга Genesis имеет `book_number=1`, а первая строка Synodal с `book_number=13` — 1 Chronicles. Поэтому ordinal не используется для сопоставления.
- Split формируется по целым книгам с фиксированным seed; исходная строка сохраняется отдельно от минимального представления NFC + схлопнутые пробелы. Графемы ѣ/ъ/ь не модернизируются и не удаляются. Счётчики и несовпадения записываются в `data/processed/translation/alignment_report.json`.
- `google/mt5-small`: официальная карточка указывает Apache-2.0, архитектуру MT5ForConditionalGeneration, словарь 250 112, ширину 512, FFN 1 024 и 8 encoder/8 decoder слоёв. Карточка прямо говорит, что это только multilingual pretraining и checkpoint требует fine-tuning для downstream задачи: https://huggingface.co/google/mt5-small
- `i1oveMyse1f/old-slavic-mt`: репозиторий содержит обзор конвертеров многих источников, включая берестяные грамоты с переводами; корневой LICENSE-файл отсутствует, а права должны проверяться по каждому включённому источнику. Экспортированные оттуда данные не включались: https://github.com/i1oveMyse1f/old-slavic-mt
- UD Old East Slavic Birchbark: отдельный официальный treebank, основанный на Корпусе берестяных грамот РНК; README сообщает даты документов 1025–1500 и разнообразие бытовых жанров. `LICENSE.txt` конкретно этого набора объявляет CC BY-SA 4.0. Файлы `train/dev/test` включены в `data/raw/ud_birchbark/`; извлечено 2 087 пар полей `# text` / `# sent_transl_ru`, исходные split по документам не пересекаются. После схлопывания пробелов сохраняются исходные символы и редакционные скобки. Все записи помечены как `unreviewed`, так как исходный annotation ещё не прошёл ручную филологическую проверку. Переводы можно использовать отдельно от библейских пар: https://github.com/UniversalDependencies/UD_Old_East_Slavic-Birchbark

## Лексические справочники (внешняя сверка)

- ИРЯ РАН, **Словарь древнерусского языка XI–XIV вв.**: https://lexrus.ru/default.aspx?p=2641 — словарь включает около 30 000 слов древнерусских письменных памятников и снабжает статьи грамматическими пометами, толкованиями и иллюстрациями. Приложение не копирует его статьи; карточка слова открывает ресурс и показывает лишь отдельные модельные/корпусные кандидаты.
- Славянский институт АН Чешской Республики, **GORAZD: Электронный словарь языка старославянского**: https://gulliver.gorazd.org/ — электронная база на основе академического четырёхтомного *Slovník jazyka staroslověnského*. Использовать с учётом описанного словарём состава рукописей.
- University of Texas at Austin, **Old Church Slavonic Online · Master Glossary**: https://lrc.la.utexas.edu/eieol_master_gloss/ocsol/13 — учебный глоссарий словоформ со ссылками на контексты; не универсальный исторический словарь.
- ИРЯ РАН, **Большой словарь церковнославянского языка Нового времени**: https://ruslang.ru/node/1648 — страница проекта описывает электронную версию портала и её доступную часть (буквы А–В).
- И. И. Срезневский, **Материалы для словаря древнерусского языка**: https://www.oldrusdict.ru/dict.html — сторонняя поисковая электронная версия; при сверке нужно читать пометы редактора и отличать их от опубликованной статьи.

Локальные UDPipe-леммы и совпадения форм с корпусом не содержат словарных толкований и в карточке явно отделены от значения слова. Статьи внешних словарей не встраиваются и требуют интернета.

## Технические интеграции

- Ollama API: https://docs.ollama.com/api — локальный вызов структурированного ответа; пользователь сам устанавливает Ollama и модель.
- Qt for Python (PySide6): https://doc.qt.io/qtforpython-6/ — интерфейс приложения.
- OpenAlex API: https://docs.openalex.org/ — поиск метаданных научных работ. Библиографическая карточка не используется как доказательство тезиса.
- Crossref REST API: https://api.crossref.org/works — резервный каталог библиографических метаданных при ошибке OpenAlex.
- UDPipe 2 model catalogue (checked 2 Nov 2026): https://ufal.mff.cuni.cz/udpipe/2/models — includes OCS PROIEL, Old East Slavic TOROT, Birchbark and RNC models; the catalogue identifies UD 2.17 and CC BY-NC-SA 4.0. Their files and REST service were not reachable from the test machine during the 2 Nov check; no local comparison is claimed. The app still bundles the UDPipe 1.2 compatible PROIEL and TOROT baselines, explicitly marked as older UD 2.5 models.
- UDPipe implementation notes: https://ufal.mff.cuni.cz/udpipe — describes UDPipe 1 as small and fast with bindings and UDPipe 2 as a Python prototype with higher compute requirements.
- UDPipe model pack: https://github.com/jwijffels/udpipe.models.ud.2.5 — source for the bundled model files; model distribution declares CC BY-NC-SA 4.0.
- UD Old Church Slavonic PROIEL: https://universaldependencies.org/treebanks/cu_proiel/index.html — source corpus used for model attribution and test data; license CC BY-NC-SA 4.0.
- UD Old East Slavic TOROT: https://universaldependencies.org/treebanks/orv_torot/index.html — source corpus used for model attribution and test data; license CC BY-NC-SA 4.0.

## Политика источников

Приложение не утверждает, что найденная библиографическая запись подтверждает филологическое объяснение. Оно не извлекает цитаты из платных публикаций и не обходит ограничения доступа. Перед загрузкой или распространением любого корпуса следует дополнительно проверить его лицензионный файл.

Официальный train-файл TOROT и его LICENSE.txt включены в автономный комплект. При первом запуске приложение копирует корпус в локальную базу пользователя. Лицензия CC BY-NC-SA 4.0; источник и ссылка указаны в LICENSE.txt рядом с данными.

## Распознавание исторических текстов

- Kraken OCR/HTR: https://kraken.re/ — свободный движок для исторической и нелатинской письменности; официальный гайд указывает поддержку macOS ARM и ускорения Apple Metal (`mps`).
- Модель Cyr02full, запись Zenodo 7755483: https://zenodo.org/records/7755483 — обучена на образцах старой кириллицы из устава/полуустава, включая Menologion, Codex Suprasliensis и рукопись Кирилла Иерусалимского. Модель распространяется по CC BY 2.0; заявленная область — рукописные стили XI–XVI вв. Это не тест на всех печатных или рукописных материалах.
- PDFium через pypdfium2: https://pypdfium2.readthedocs.io/en/stable/readme.html — локальная растеризация страниц сканированного PDF; лицензии BSD-3-Clause/Apache-2.0 и уведомления зависимостей необходимо включать при бинарной публикации.
- Unicode Technical Note #41: https://www.unicode.org/notes/tn41/ — ориентир при работе с историческими кириллическими знаками. OCR-строки хранятся без автоматической NFKC-нормализации.
- LightOnOCR-2-1B-old-church-slavonic-line: https://huggingface.co/wjbmattingly/LightOnOCR-2-1B-old-church-slavonic-line — рассмотрена как альтернативная строковая VLM. Не включена: модель ожидает заранее вырезанную одиночную строку и требует отдельный стек Transformers/PyTorch; в текущей версии выбран Kraken.
- CRNN-CTC Church Slavonic: https://huggingface.co/achimrabus/crnn-ctc-church-slavonic — включён Apache-2.0 checkpoint CNN+BiLSTM+CTC; модельная карточка сообщает CER 2,89% на собственной валидационной выборке. Это не измерение «Палеослова» и не гарантия точности на пользовательском изображении.
- CRNN-CTC Prosta Mova: https://huggingface.co/achimrabus/crnn-ctc-prosta-mova — включён Apache-2.0 checkpoint для строк старопечатной восточнославянской письменности; модельная карточка сообщает CER 3,77% на собственной валидации. Не универсальная модель церковнославянской печати.
- Инференс CRNN использует grayscale line crops высотой 128 пикселей, сохранение пропорций, greedy CTC-декодирование и Kraken HPP для сегментации; оценка confidence не калибрована.

## Локальная языковая модель

- Ollama для macOS Apple Silicon: https://github.com/ollama/ollama — временный runtime для испытаний; проверяемая APFS-сборка на 2 ноября 2026 года не содержала его и не предоставляла встроенную генерацию.
- Qwen3-4B: https://huggingface.co/Qwen/Qwen3-4B и https://ollama.com/library/qwen3 — предыдущая конфигурация; ранее найденный неполный blob не является установленной моделью, поэтому включённость/готовность этой модели в текущей сборке не заявляется.
- Qwen2.5-1.5B-Instruct: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct и https://ollama.com/library/qwen2.5 — экспериментальная Apache-2.0 модель, Ollama Q4_K_M (986 МБ). На трёх незнакомых старославянских фрагментах в локальной проверке перевод оказался неприемлемым; модель не включена и не считается переводчиком.
- Сапожников Д. С. *Машинный перевод старославянских текстов на современный русский язык*. Выпускная работа НИУ ВШЭ, 2026: https://www.hse.ru/edu/vkr/1158669266 — описывает специальную cu→ru систему, итог NLLB-3.3B, SacreBLEU 16.50 / chrF++ 38.00 на 5 002 тестовых сегментах; веса/чекпойнт и отдельная лицензия на них на доступной странице не опубликованы. Эти результаты принадлежат работе и не являются тестом Палеослова.
