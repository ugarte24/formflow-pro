# -*- mode: python ; coding: utf-8 -*-
# Generar con: .\build_exe.ps1
# Salida: dist\DigitalizadorAgent\

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('selectors.json', '.'),
        ('.env.example', '.'),
        ('CALIBRACION.md', '.'),
        ('README.md', '.'),
    ],
    hiddenimports=[
        'api_client',
        'ruat_flow',
        'app_paths',
        'ensure_browsers',
        'playwright',
        'playwright.sync_api',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DigitalizadorAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DigitalizadorAgent',
)
