# -*- mode: python ; coding: utf-8 -*-
# Especificación de PyInstaller. Uso:  pyinstaller packaging/posteos.spec --noconfirm

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

RAIZ = Path(SPECPATH).parent

datos = [(str(RAIZ / "posteos" / "recursos"), "posteos/recursos")]
for paquete in ("anthropic", "google.genai", "ddgs"):
    datos += collect_data_files(paquete)
for distribucion in ("anthropic", "google-genai", "ollama", "ddgs", "keyring"):
    datos += copy_metadata(distribucion)

ocultos = collect_submodules("anthropic") + collect_submodules("google.genai") + collect_submodules("ddgs")
ocultos += collect_submodules("keyring.backends") + ["ollama", "primp"]
if sys.platform == "win32":
    ocultos += ["win32ctypes.core"]

a = Analysis(
    [str(RAIZ / "run.py")],
    pathex=[str(RAIZ)],
    datas=datos,
    hiddenimports=ocultos,
    excludes=["tkinter", "matplotlib", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore", "PySide6.QtQuick"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Posteos",
    console=False,
    icon=str(RAIZ / "packaging" / "posteos.ico"),
    version=str(RAIZ / "packaging" / "version_windows.txt") if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Posteos")
