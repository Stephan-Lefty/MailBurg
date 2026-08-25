"""Wo das Programm auf den drei Betriebssystemen seine Sachen ablegt.

Jedes System hat dafür eigene Gepflogenheiten, und wir halten uns daran,
statt überall ``~/.mailburg`` hinzuschreiben. Wer sein Benutzerverzeichnis
sichert, soll die Einstellungen mitbekommen und den wegwerfbaren Suchindex
nicht.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mailburg import APP_NAME


def _base(kind: str) -> Path:
    """Grundverzeichnis für ``config``, ``data`` oder ``cache``."""
    if sys.platform == "win32":
        # Windows trennt nur zwischen wanderndem und lokalem Profil.
        # Einstellungen dürfen mitwandern, der Index nicht – der kann
        # zweistellige Gigabyte erreichen.
        root = os.environ.get(
            "APPDATA" if kind == "config" else "LOCALAPPDATA",
            str(Path.home() / "AppData" / "Local"),
        )
        return Path(root) / APP_NAME

    if sys.platform == "darwin":
        home = Path.home() / "Library"
        return (home / "Preferences" if kind == "config" else home / "Application Support") / APP_NAME

    # Linux und die übrigen: XDG Base Directory
    variables = {
        "config": ("XDG_CONFIG_HOME", ".config"),
        "data": ("XDG_DATA_HOME", ".local/share"),
        "cache": ("XDG_CACHE_HOME", ".cache"),
    }
    env_name, fallback = variables[kind]
    root = os.environ.get(env_name) or str(Path.home() / fallback)
    return Path(root) / APP_NAME.lower()


def config_dir() -> Path:
    """Einstellungen und Kontenliste. Sicherungswürdig."""
    path = _base("config")
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    """Suchindizes. Jederzeit aus dem Archiv neu erzeugbar, also entbehrlich."""
    path = _base("data")
    path.mkdir(parents=True, exist_ok=True)
    return path


def index_path(archive_uuid: str) -> Path:
    """Der Suchindex zu einem bestimmten Archiv.

    Über die Kennung des Archivs, nicht über seinen Pfad: So findet das
    Programm den Index wieder, wenn das Archiv von der externen Platte
    einmal woanders eingehängt wird.
    """
    return data_dir() / "index" / f"{archive_uuid}.db"
