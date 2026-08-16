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
        ('DigitalizadorAgent.ico', '.'),
        ('VERSION', '.'),
    ],
    hiddenimports=[
        'api_client',
        'session_auth',
        'tray_ui',
        'agent_ui',
        'updater',
        'ruat_flow',
        'app_paths',
        'ensure_browsers',
        'playwright',
        'playwright.sync_api',
        'dotenv',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PIL.AvifImagePlugin',
        'PIL.WebPImagePlugin',
        'PIL.ImageTk',
        'PIL.ImageQt',
        'PIL.PdfImagePlugin',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Quitar códecs Pillow grandes que no usamos (bajar tamaño del instalador).
_DROP_PIL = ('_avif', '_webp', '_imagingft', '_imagingcms', '_imagingtk')
a.binaries = [b for b in a.binaries if not any(tok in str(b[0]).lower() for tok in _DROP_PIL)]

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='DigitalizadorAgent.ico',
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
