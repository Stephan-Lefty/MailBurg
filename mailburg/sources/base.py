"""Die Schnittstelle, hinter der alle Mailquellen gleich aussehen.

Ob eine Mail aus einem IMAP-Postfach kommt, aus einer Thunderbird-Datei oder
später aus einem Outlook-Archiv, geht den Rest des Programms nichts an. Alles
unterhalb dieser Schicht kennt nur noch rohe Bytes und die Angabe, wo sie
herkamen.

Roh heißt roh: Eine Quelle liefert die Mail so aus, wie sie vorlag, ohne
etwas geradezuziehen. Nur so bleibt der Inhaltshash aussagekräftig und eine
DKIM-Signatur prüfbar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass
class RawMessage:
    """Eine Mail, wie sie die Quelle hergibt."""

    raw: bytes = field(repr=False)
    folder: str
    """Ordner in der Quelle, mit ``/`` getrennt – etwa ``Posteingang/2025``."""

    uid: int | None = None
    """Kennung im Postfach, falls es eine gibt. Für IMAP der UID."""

    flags: str = ""
    """Zustände wie gelesen oder beantwortet, als Text."""

    @property
    def size(self) -> int:
        return len(self.raw)


@dataclass
class SourceStats:
    """Wie ein Durchlauf ausging."""

    seen: int = 0
    added: int = 0
    duplicate: int = 0
    failed: int = 0
    skipped: int = 0
    """Durch eine Ausschlussregel übergangen – etwa als privat erkannt."""

    def __str__(self) -> str:
        parts = [f"{self.seen} gesehen", f"{self.added} neu"]
        if self.duplicate:
            parts.append(f"{self.duplicate} bereits vorhanden")
        if self.skipped:
            parts.append(f"{self.skipped} übergangen")
        if self.failed:
            parts.append(f"{self.failed} fehlgeschlagen")
        return ", ".join(parts)


class Source(ABC):
    """Etwas, aus dem sich Mails holen lassen."""

    #: Name des Kontos, unter dem die Mails im Archiv erscheinen.
    account: str

    @abstractmethod
    def iter_messages(self) -> Iterator[RawMessage]:
        """Gibt alle Mails der Quelle aus.

        Fehler bei einzelnen Mails sollen den Durchlauf nicht abbrechen –
        eine unlesbare Datei unter zehntausend darf nicht dazu führen, dass
        die übrigen neuntausendneunhundertneunundneunzig liegen bleiben.
        """

    @abstractmethod
    def describe(self) -> str:
        """Beschreibt die Quelle für Protokoll und Oberfläche."""

    def folders(self) -> list[str]:
        """Die Ordner der Quelle, falls im Voraus bekannt."""
        return []

    def close(self) -> None:
        """Gibt Verbindungen oder Dateien frei."""
