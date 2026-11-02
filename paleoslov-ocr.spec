# -*- mode: python ; coding: utf-8 -*-
# Standalone CPU/MPS Kraken helper. PyInstaller runs this with the .venv-ocr env.
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

kraken_datas, kraken_binaries, kraken_hidden = collect_all('kraken')
hiddenimports = list(set(kraken_hidden + collect_submodules('kraken')))
tv_datas, tv_binaries, tv_hidden = collect_all('torchvision')
kraken_datas.extend(tv_datas)
kraken_binaries.extend(tv_binaries)
hiddenimports = list(set(hiddenimports + tv_hidden))
for distribution in ('rich', 'lightning', 'lightning-utilities', 'torchmetrics', 'torch', 'torchvision'):
    kraken_datas.extend(copy_metadata(distribution))
hiddenimports += [
    'torch.distributed.rpc',
    'torch._functorch.pyfunctorch',
    'torch.testing._comparison',
    'torch.fx.experimental._constant_symnode',
    'PIL._imaging',
]

a = Analysis(
    ['paleoslov/ocr_worker.py'],
    pathex=['.'],
    binaries=kraken_binaries,
    datas=kraken_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch.utils.tensorboard'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='paleoslov-ocr',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
