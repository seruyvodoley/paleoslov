# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all
from pathlib import Path

def expand_without_appledouble(items):
    expanded = []
    for source, target in items:
        source_path = Path(source)
        if source_path.is_dir():
            for child in source_path.rglob('*'):
                relative = child.relative_to(source_path)
                if child.is_file() and not any(part.startswith('._') for part in relative.parts):
                    expanded.append((str(child), str(Path(target) / relative)))
        elif not source_path.name.startswith('._'):
            expanded.append((source, target))
    return expanded

pdf_datas, pdf_binaries, pdf_hidden = collect_all('pypdfium2')
raw_datas, raw_binaries, raw_hidden = collect_all('pypdfium2_raw')
pdf_datas.extend(raw_datas)
pdf_binaries.extend(raw_binaries)
pdf_hidden.extend(raw_hidden)
# The project lives on exFAT, where macOS stores resource forks as AppleDouble
# `._*` sidecars. collect_all can mistake these files for package resources and
# create broken links in the app bundle; never ship them.
pdf_datas = expand_without_appledouble(pdf_datas)
pdf_binaries = expand_without_appledouble(pdf_binaries)
pdf_datas.append(('data/models/Cyr02full_best.mlmodel', 'models'))
pdf_datas.extend([
    ('data/models/udpipe/old_church_slavonic-proiel-ud-2.5-191206.udpipe', 'models/udpipe'),
    ('data/models/udpipe/old_russian-torot-ud-2.5-191206.udpipe', 'models/udpipe'),
    ('data/models/udpipe/LICENSE.txt', 'models/udpipe'),
])
# The stable release intentionally ships no Ollama, Qwen or translator weights.
# Bundle the standalone Kraken helper so OCR works without a separate install.
ocr_worker = Path('build/ocr-dist/paleoslov-ocr')
if not ocr_worker.is_file():
    raise SystemExit('Missing self-contained OCR worker: build/ocr-dist/paleoslov-ocr')
pdf_datas.append((str(ocr_worker), 'ocr-engine'))
for model_id in ('crnn-church-slavonic', 'crnn-prosta-mova'):
    source = Path('data/model-evaluation') / model_id
    for filename in ('best_model.pt', 'model_config.json', 'symbols.txt', 'README.md'):
        item = source / filename
        if item.is_file():
            pdf_datas.append((str(item), f'model-evaluation/{model_id}'))
worker_root = Path('build/crnn-dist7/paleoslov-crnn')
if worker_root.is_dir():
    for item in worker_root.rglob('*'):
        if item.is_file() and not item.name.startswith('._'):
            target_dir = Path('crnn-worker') / item.relative_to(worker_root).parent
            pdf_datas.append((str(item), str(target_dir)))
pdf_datas.extend([
    ('data/corpora/orv_torot-ud-train.conllu', 'corpora'),
    ('data/corpora/LICENSE.txt', 'corpora'),
])
pdf_datas.extend([('LICENSES.md', '.'), ('SOURCES.md', '.')])
for item in Path('data/licenses').rglob('*'):
    if item.is_file() and not item.name.startswith('._'):
        pdf_datas.append((str(item), str(Path('licenses') / item.parent.relative_to('data/licenses'))))

a = Analysis(
    ['paleoslov/app/main.py'],
    pathex=['.'],
    binaries=pdf_binaries,
    datas=pdf_datas,
    hiddenimports=['pypdfium2', 'pypdfium2_raw', 'PIL', 'ufal.udpipe', *pdf_hidden],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Палеослов',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Палеослов',
)
app = BUNDLE(
    coll,
    name='Палеослов.app',
    icon=None,
    bundle_identifier='org.paleoslov.scriptorium',
    info_plist={
        'CFBundleDisplayName': 'Палеослов',
        'CFBundleShortVersionString': '0.1.1',
        'CFBundleVersion': '0.1.1',
        'LSMinimumSystemVersion': '12.0',
        'NSHighResolutionCapable': True,
    },
)
