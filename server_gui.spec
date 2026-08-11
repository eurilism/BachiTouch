# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['server_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('static', 'static'),
        ('bg.jpg', '.'),
        ('icon.ico', '.'),
    ],
    hiddenimports=['pynput.keyboard._win32'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BachiTouch',
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
    icon=['icon.ico'],
    onefile=True,
)
