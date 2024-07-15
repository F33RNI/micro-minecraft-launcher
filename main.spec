# -*- mode: python ; coding: utf-8 -*-

"""
This file is part of the micro-minecraft-launcher distribution.
See <https://github.com/F33RNI/micro-minecraft-launcher> for more info.

Copyright (C) 2024 Fern Lane

This program is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, version 3.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.
If not, see <http://www.gnu.org/licenses/>.
"""

import glob
import os
import platform

import PyInstaller.config
from PyInstaller.utils.hooks import collect_data_files

# Set working path
PyInstaller.config.CONF["workpath"] = "./build"

# Parse version from _version.py file
with open(os.path.join("src", "mml", "_version.py"), "r", encoding="utf-8") as file:
    version = file.read().strip().split("__version__")[-1].split('"')[1]

# Final name
COMPILE_NAME = f"micro-minecraft-launcher-{version}-{platform.system()}-{platform.machine()}".lower()

SOURCE_FILES = glob.glob(os.path.join("src", "mml", "*.py"))
INCLUDE_FILES = [("LICENSE", ".")]
ICON = None  # [os.path.join("icons", "icon.ico")]

# Fix SSL: CERTIFICATE_VERIFY_FAILED
INCLUDE_FILES.extend(collect_data_files("certifi"))

block_cipher = None

a = Analysis(
    SOURCE_FILES,
    pathex=[],
    binaries=[],
    datas=INCLUDE_FILES,
    hiddenimports=["certifi"],
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
