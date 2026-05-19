# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Get the directory containing this spec file
SPEC_DIR = Path(SPECPATH).resolve()

# Collect customtkinter data files (themes, etc.)
ctk_datas = collect_data_files('customtkinter')

a = Analysis(
    [str(SPEC_DIR / 'main.py')],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=ctk_datas,
    hiddenimports=collect_submodules('customtkinter'),
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

# Check for icons (optional - will be None if not found)
icon_win = SPEC_DIR / 'assets' / 'icon.ico'
icon_mac = SPEC_DIR / 'assets' / 'icon.icns'
win_icon = str(icon_win) if icon_win.exists() else None
mac_icon = str(icon_mac) if icon_mac.exists() else None

exe = EXE(
    pyz,
    a.scripts,
    # Windows: include binaries/datas for a single-file exe
    # macOS: exclude them so COLLECT + BUNDLE can create the .app directory structure
    *([a.binaries, a.zipfiles, a.datas] if sys.platform != 'darwin' else []),
    [],
    exclude_binaries=(sys.platform == 'darwin'),
    name='adLibre',
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
    icon=win_icon if sys.platform == 'win32' else mac_icon,
    uac_admin=True if sys.platform == 'win32' else False,
)

# macOS app bundle
if sys.platform == 'darwin':
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='adLibre',
    )
    app = BUNDLE(
        coll,
        name='adLibre.app',
        icon=mac_icon,
        bundle_identifier='com.adlibre.dnsmanager',
        info_plist={
            'CFBundleName': 'adLibre',
            'CFBundleDisplayName': 'adLibre',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
            'LSUIElement': False,
        },
    )
