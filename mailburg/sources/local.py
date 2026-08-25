"""Mailquellen auf der eigenen Platte: Maildir, MBOX, Thunderbird.

Der Weg über die lokalen Dateien hat einen Vorteil, den IMAP nicht bietet:
Er kommt auch an Postfächer heran, die es online längst nicht mehr gibt. Ein
Konto, das vor acht Jahren gekündigt wurde, liegt im Thunderbird-Profil noch
vollständig vor.
"""

from __future__ import annotations

import configparser
import mailbox
import os
import sys
from collections.abc import Iterator
from pathlib import Path

from mailburg.sources.base import RawMessage, Source

#: Dateien, die im Mailverzeichnis liegen, aber keine Mails enthalten.
#: ``.msf`` ist Thunderbirds eigener Index, der Rest ist Verwaltungskram.
_NOT_MAIL = {".msf", ".dat", ".json", ".sqlite", ".log", ".bak", ".tmp"}
_SKIP_NAMES = {"msgFilterRules.dat", "filterlog.html", "Trash", "Junk"}


class MaildirSource(Source):
    """Ein Maildir-Verzeichnis, gegebenenfalls mit Unterordnern."""

    def __init__(self, path: Path, account: str = "") -> None:
        self.path = Path(path).expanduser().resolve()
        self.account = account or self.path.name
        if not (self.path / "cur").is_dir():
            raise ValueError(f"{self.path} sieht nicht wie ein Maildir aus (kein cur/).")
        self._box = mailbox.Maildir(str(self.path), factory=None, create=False)

    def folders(self) -> list[str]:
        return ["INBOX", *sorted(self._box.list_folders())]

    def iter_messages(self) -> Iterator[RawMessage]:
        yield from self._walk(self._box, "INBOX")
        for name in self._box.list_folders():
            try:
                yield from self._walk(self._box.get_folder(name), name)
            except mailbox.Error:
                continue

    def _walk(self, box: mailbox.Maildir, folder: str) -> Iterator[RawMessage]:
        for key in box.keys():
            try:
                raw = box.get_bytes(key)
            except (mailbox.Error, OSError, KeyError):
                continue
            if raw:
                yield RawMessage(raw=raw, folder=folder, flags=self._flags(key))

    @staticmethod
    def _flags(key: str) -> str:
        """Maildir kodiert den Zustand in den Dateinamen, hinter ``:2,``."""
        _, _, info = key.partition(":2,")
        return info

    def describe(self) -> str:
        return f"Maildir {self.path}"

    def close(self) -> None:
        self._box.close()


class MboxSource(Source):
    """Eine einzelne MBOX-Datei."""

    def __init__(self, path: Path, account: str = "", folder: str = "") -> None:
        self.path = Path(path).expanduser().resolve()
        self.account = account or self.path.stem
        self.folder = folder or self.path.stem
        self._box = mailbox.mbox(str(self.path), factory=None, create=False)

    def iter_messages(self) -> Iterator[RawMessage]:
        for key in self._box.keys():
            try:
                raw = self._box.get_bytes(key)
            except (mailbox.Error, OSError, KeyError):
                continue
            if raw:
                yield RawMessage(raw=raw, folder=self.folder)

    def folders(self) -> list[str]:
        return [self.folder]

    def describe(self) -> str:
        return f"MBOX-Datei {self.path}"

    def close(self) -> None:
        self._box.close()


class ThunderbirdSource(Source):
    """Ein ganzes Thunderbird-Profil mit allen Konten und Ordnern.

    Thunderbird legt jeden Ordner als MBOX-Datei ohne Endung ab.
    Unterordner stehen in einem gleichnamigen Verzeichnis mit der Endung
    ``.sbd``. Aus dieser Verschachtelung bauen wir die Ordnerpfade nach, wie
    der Benutzer sie in Thunderbird sieht.
    """

    def __init__(self, profile: Path, account: str = "") -> None:
        self.profile = Path(profile).expanduser().resolve()
        self.account = account or self.profile.name
        self._roots = [
            d for d in (self.profile / "Mail", self.profile / "ImapMail") if d.is_dir()
        ]
        if not self._roots:
            raise ValueError(
                f"In {self.profile} liegen weder Mail/ noch ImapMail/ – "
                f"das ist kein Thunderbird-Profil."
            )

    def _mbox_files(self) -> Iterator[tuple[Path, str]]:
        """Findet alle Ordnerdateien samt ihres Pfades in der Anzeige."""
        for root in self._roots:
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix in _NOT_MAIL:
                    continue
                if path.name in _SKIP_NAMES or path.name.startswith("."):
                    continue
                if path.stat().st_size == 0:
                    continue

                # Aus .../ImapMail/server/Archives.sbd/2024 wird
                # "server/Archives/2024".
                parts = [
                    p[:-4] if p.endswith(".sbd") else p
                    for p in path.relative_to(root).parts
                ]
                yield path, "/".join(parts)

    def folders(self) -> list[str]:
        return [folder for _, folder in self._mbox_files()]

    def iter_messages(self) -> Iterator[RawMessage]:
        for path, folder in self._mbox_files():
            try:
                box = mailbox.mbox(str(path), factory=None, create=False)
            except (mailbox.Error, OSError):
                continue
            try:
                for key in box.keys():
                    try:
                        raw = box.get_bytes(key)
                    except (mailbox.Error, OSError, KeyError):
                        continue
                    if raw:
                        yield RawMessage(raw=raw, folder=folder)
            finally:
                box.close()

    def describe(self) -> str:
        return f"Thunderbird-Profil {self.profile}"


def thunderbird_profile_dirs() -> list[Path]:
    """Wo Thunderbird auf diesem System seine Profile ablegen könnte."""
    home = Path.home()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(home / "AppData" / "Roaming"))
        return [Path(appdata) / "Thunderbird"]
    if sys.platform == "darwin":
        return [home / "Library" / "Thunderbird"]
    return [
        home / ".thunderbird",
        home / ".mozilla-thunderbird",
        # Flatpak sperrt die Anwendung in ein eigenes Verzeichnis.
        home / ".var" / "app" / "org.mozilla.Thunderbird" / ".thunderbird",
        # Snap tut dasselbe, nur woanders.
        home / "snap" / "thunderbird" / "common" / ".thunderbird",
    ]


def find_thunderbird_profiles() -> list[Path]:
    """Sucht die Thunderbird-Profile des angemeldeten Benutzers.

    Zuerst über ``profiles.ini`` – das ist die verlässliche Quelle. Führt
    das zu nichts, wird nach den typischen ``xxxxxxxx.default``-Ordnern
    gesehen, denn bei alten oder von Hand angelegten Profilen fehlt der
    Eintrag manchmal.
    """
    found: list[Path] = []

    for base in thunderbird_profile_dirs():
        if not base.is_dir():
            continue

        ini = base / "profiles.ini"
        if ini.exists():
            parser = configparser.ConfigParser()
            try:
                parser.read(ini, encoding="utf-8")
            except (configparser.Error, UnicodeDecodeError):
                parser = None  # type: ignore[assignment]

            if parser:
                for section in parser.sections():
                    if not section.startswith("Profile"):
                        continue
                    path_value = parser.get(section, "Path", fallback="")
                    if not path_value:
                        continue
                    relative = parser.getboolean(section, "IsRelative", fallback=True)
                    candidate = (base / path_value) if relative else Path(path_value)
                    if candidate.is_dir() and candidate not in found:
                        found.append(candidate)

        for candidate in base.glob("*.default*"):
            if candidate.is_dir() and candidate not in found:
                found.append(candidate)

    # Nur Profile, in denen tatsächlich Mails liegen.
    return [p for p in found if (p / "Mail").is_dir() or (p / "ImapMail").is_dir()]


def open_path(path: Path, account: str = "") -> Source:
    """Errät, was für eine Mailquelle unter ``path`` liegt, und öffnet sie."""
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{path} gibt es nicht.")

    if path.is_dir():
        if (path / "Mail").is_dir() or (path / "ImapMail").is_dir():
            return ThunderbirdSource(path, account)
        if (path / "cur").is_dir():
            return MaildirSource(path, account)
        raise ValueError(
            f"{path} ist weder Thunderbird-Profil noch Maildir. Erwartet wird "
            f"ein Verzeichnis mit Mail/ bzw. ImapMail/ oder mit cur/."
        )

    return MboxSource(path, account)
