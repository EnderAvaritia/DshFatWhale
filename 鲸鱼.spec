# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：pyinstaller 鲸鱼.spec
# 产物：dist/DshFatWhale.exe（双击即用，无需 Python）

a = Analysis(
    ['鲸鱼.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('台词表.md', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DshFatWhale',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
