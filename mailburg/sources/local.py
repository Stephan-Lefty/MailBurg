"""Mailquellen auf der eigenen Platte: Maildir, MBOX, Thunderbird, EML.

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

#: Endungen, unter denen einzelne Mails abgelegt werden. ``.emlx`` ist
#: Apple Mails Fassung: dieselbe Mail, aber mit einer Längenangabe in der
#: ersten Zeile und einem Anhang aus Verwaltungsdaten am Ende.
_EML_ENDUNGEN = {".eml", ".emlx", ".msg_eml"}

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
        if not self._roots and self._enthaelt_ordnerdateien(self.profile):
            # Auch ein Verzeichnis, das die Ordnerdateien direkt enthält.
            # Wer in Thunderbird "Lokale Ordner" führt - der übliche Ort
            # für Post, die aus einem anderen Archivprogramm übernommen
            # wurde -, zeigt beim Import genau dorthin und nicht auf das
            # Profil darüber. Die Verschachtelung mit .sbd ist dieselbe.
            self._roots = [self.profile]
        if not self._roots:
            raise ValueError(
                f"In {self.profile} liegen weder Mail/ noch ImapMail/ noch "
                f"Ordnerdateien – das ist kein Thunderbird-Profil und auch "
                f"kein Ordnerverzeichnis."
            )

    @staticmethod
    def _enthaelt_ordnerdateien(verzeichnis: Path) -> bool:
        """Ob dort MBOX-Ordnerdateien liegen, wie Thunderbird sie anlegt.

        Erkannt am Beiwerk: Zu jeder Ordnerdatei legt Thunderbird eine
        gleichnamige ``.msf`` an. Am Inhalt zu prüfen wäre teurer und
        nicht sicherer – eine leere Ordnerdatei sieht aus wie jede andere
        leere Datei.
        """
        return any(verzeichnis.glob("*.msf")) or any(verzeichnis.glob("*.sbd"))

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


class EmlOrdnerSource(Source):
    """Ein Verzeichnis voller ``.eml``-Dateien, gegebenenfalls verschachtelt.

    Das ist das übliche Ergebnis, wenn ein anderes Archivprogramm seine
    Post herausrückt – MailStore, Outlook, ein Webmailer. Jede Mail eine
    Datei, die Ordnerstruktur als Verzeichnisse.

    **Die Verzeichnisnamen werden zu den Fundorten im Archiv.** Wer in
    seinem alten Programm eine Ablage aufgebaut hat, findet sie hier
    wieder; das ist oft die einzige Ordnung, die eine solche Sammlung
    noch hat.

    Was die Datei enthält, wird nicht geprüft und nicht geradegezogen.
    Eine ``.eml`` ist eine Mail in genau der Form, in der sie über das
    Netz ging – Bytes, wie sie sind. Genau darauf beruht der Inhaltshash.
    """

    def __init__(self, path: Path, account: str = "") -> None:
        self.path = Path(path).expanduser().resolve()
        self.account = account or self.path.name
        if not self.path.is_dir():
            raise ValueError(f"{self.path} ist kein Verzeichnis.")
        if not self._enthaelt_eml(self.path):
            raise ValueError(
                f"In {self.path} liegen keine .eml-Dateien – auch nicht in "
                f"Unterverzeichnissen."
            )

    @staticmethod
    def _enthaelt_eml(verzeichnis: Path) -> bool:
        """Ob irgendwo darunter eine Maildatei liegt.

        Bricht beim ersten Fund ab. Bei einer Sammlung aus
        Hunderttausenden Dateien ist der Unterschied zwischen »eine
        finden« und »alle zählen« der zwischen Sekundenbruchteil und
        Minuten.
        """
        for pfad in verzeichnis.rglob("*"):
            if pfad.is_file() and pfad.suffix.lower() in _EML_ENDUNGEN:
                return True
        return False

    def _dateien(self) -> Iterator[tuple[Path, str]]:
        """Alle Maildateien samt des Ordners, in dem sie lagen."""
        for pfad in sorted(self.path.rglob("*")):
            if not pfad.is_file() or pfad.suffix.lower() not in _EML_ENDUNGEN:
                continue
            if pfad.name.startswith("."):
                continue
            eltern = pfad.parent.relative_to(self.path)
            # Liegt die Mail unmittelbar im gewählten Verzeichnis, gibt es
            # keinen Ordner zu benennen. "." wäre ein Fundort, den niemand
            # so geschrieben hätte.
            yield pfad, "/".join(eltern.parts) if eltern.parts else self.account

    def folders(self) -> list[str]:
        return sorted({ordner for _, ordner in self._dateien()})

    def iter_messages(self) -> Iterator[RawMessage]:
        for pfad, ordner in self._dateien():
            try:
                roh = pfad.read_bytes()
            except OSError:
                # Eine unlesbare Datei darf den Import nicht anhalten. Was
                # fehlt, fällt beim Abgleich der Anzahl auf.
                continue
            if not roh:
                continue
            if pfad.suffix.lower() == ".emlx":
                roh = _emlx_auspacken(roh)
            yield RawMessage(raw=roh, folder=ordner)

    def describe(self) -> str:
        return f"EML-Verzeichnis {self.path}"


def _emlx_auspacken(roh: bytes) -> bytes:
    """Holt die eigentliche Mail aus einer ``.emlx``-Datei von Apple Mail.

    Der Aufbau: eine Zeile mit der Länge der Mail in Bytes, dann die Mail
    selbst, dann ein Property-List-Anhang mit Apples Verwaltungsdaten.
    Beides drumherum gehört nicht zur Mail und würde den Inhaltshash
    verfälschen – dieselbe Mail sähe unter macOS anders aus als überall
    sonst.

    Passt die Längenangabe nicht, wird die Datei unverändert
    durchgereicht: Eine Mail, die vielleicht etwas Beiwerk trägt, ist
    besser als gar keine.
    """
    kopf, _, rest = roh.partition(b"\n")
    try:
        laenge = int(kopf.strip())
    except ValueError:
        return roh
    if laenge <= 0 or laenge > len(rest):
        return roh
    return rest[:laenge]


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
        if ThunderbirdSource._enthaelt_ordnerdateien(path):
            # Ein Verzeichnis voller Ordnerdateien, etwa "Local Folders".
            return ThunderbirdSource(path, account)
        if EmlOrdnerSource._enthaelt_eml(path):
            # Zuletzt geprüft, weil am unspezifischsten: Eine einzelne
            # .eml kann auch in einem Thunderbird-Profil liegen.
            return EmlOrdnerSource(path, account)
        raise ValueError(
            f"{path} ist weder Thunderbird-Profil noch Maildir noch ein "
            f"Verzeichnis mit Ordnerdateien oder .eml-Dateien. Erwartet "
            f"wird ein Verzeichnis mit Mail/ bzw. ImapMail/, eines mit "
            f"cur/, eines mit Thunderbirds Ordnerdateien oder eines, in "
            f"dem einzelne Mails als .eml liegen."
        )

    return MboxSource(path, account)
