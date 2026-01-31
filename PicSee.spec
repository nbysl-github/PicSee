# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['PicSee.py'],
    pathex=[],
    binaries=[],
datas=[
    ('waterfall.html', '.'),
    ('preview.html', '.'),
    ('resources', 'resources'),
    ('lang', 'lang'),
    ('docs', 'docs'),
    ('使用说明.md', '.'),
    ('更新历史.md', '.'),
],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='PicSee',
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
    icon='resources/icon.ico',
)
