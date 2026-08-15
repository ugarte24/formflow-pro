"""Rutas del agente: desarrollo vs .exe (PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Carpeta del .exe (o de main.py en desarrollo). Aquí vive .env y se pueden editar selectores."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_dir() -> Path:
    """Archivos empaquetados (PyInstaller _MEIPASS) o carpeta del código."""
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def resolve_data_file(name: str) -> Path:
    """Prioriza archivo junto al .exe (editable); si no, el empaquetado."""
    beside = app_dir() / name
    if beside.exists():
        return beside
    bundled = resource_dir() / name
    if bundled.exists():
        return bundled
    return beside


def browsers_dir() -> Path:
    """Firefox de Playwright junto al instalable (no depende del usuario de desarrollo)."""
    return app_dir() / "ms-playwright"
