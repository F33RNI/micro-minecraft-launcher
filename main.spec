# -*- mode: python ; coding: utf-8 -*-
import os
import platform

import PyInstaller.config

# Set working path
PyInstaller.config.CONF["workpath"] = "./build"

# Parse version from _version.py file
with open(os.path.join("src", "mml", "_version.py"), "r", encoding="utf-8") as file:
    version = file.read().strip().split("__version__")[-1].split('"')[1]

# Final name
COMPILE_NAME = f"micro-minecraft-launcher-{version}-{platform.system()}-{platform.machine()}".lower()

SOURCE_FILES = [os.path.join("src", "mml", "main.py")]
INCLUDE_FILES = [("LICENSE", ".")]
ICON = None  # [os.path.join("icons", "icon.ico")]

block_cipher = None

a = Analysis(
    SOURCE_FILES,
    pathex=[],
    binaries=[],
    datas=INCLUDE_FILES,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["_bootlocale"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=COMPILE_NAME,
    debug=False,
    bootloader_ignore_signals=True,
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
    icon=ICON,
)
