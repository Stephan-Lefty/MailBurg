"""Die Ablage – inhaltsadressierte Mailspeicherung.

Jede Mail liegt als eigene, gepackte Datei unter ``mail/``. Ihr Name ist der
SHA-256 ihres unveränderten Inhalts::

    mail/2026/08/3f/3f8a9c1e….eml.zst

Drei Überlegungen stecken darin:

**Der Inhalt bestimmt den Namen.** Wer dieselbe Quelle zweimal einliest,
erzeugt keine zweite Datei. Und wer wissen will, ob eine Mail seit der
Aufnahme verändert wurde, muss nur neu hashen.

**Bytegenau, ohne Nachbesserung.** Wir schreiben die Mail exakt so weg, wie
die Quelle sie geliefert hat – keine geglätteten Zeilenenden, keine
reparierten Kopfzeilen. Das ist einmal die Voraussetzung dafür, dass eine
DKIM-Signatur später noch prüfbar ist, und zum anderen genau das, was mit
Unveränderbarkeit gemeint ist. Der Preis: dieselbe Rundmail, die an drei
eigene Adressen ging, hat je eigene ``Received:``-Kopfzeilen und liegt daher
dreimal auf der Platte. Das ist der richtige Tausch – Plattenplatz ist
billig, Beweiswert nicht.

**Ordner nach Monat.** Eine halbe Million Dateien in einem Verzeichnis
bringt sowohl das Dateisystem als auch den Nextcloud-Client ins Straucheln.
Die Aufteilung nach Monat und Hash-Präfix hält die Verzeichnisse klein und
sorgt nebenbei dafür, dass alte Ordner sich nie wieder ändern – synchronisiert
werden sie damit genau einmal.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mailburg.core import compress

#: Monatsordner für Mails, deren Datum sich nicht ermitteln ließ.
UNDATED_BUCKET = "0000/00"

_BUCKET_RE = re.compile(r"^\d{4}/\d{2}$")


def content_hash(raw: bytes) -> str:
    """Der SHA-256 einer Mail – zugleich ihr Name in der Ablage."""
    return hashlib.sha256(raw).hexdigest()


def bucket_for(date: datetime | None) -> str:
    """Bestimmt den Monatsordner aus dem Datum der Mail."""
    if date is None:
        return UNDATED_BUCKET
    return f"{date.year:04d}/{date.month:02d}"


@dataclass(frozen=True)
class PutResult:
    """Was beim Ablegen einer Mail herauskam."""

    hash: str
    bucket: str
    stored: bool
    """``False``, wenn die Mail schon da war und nichts geschrieben wurde."""

    size: int


class Store:
    """Legt Mails ab und holt sie wieder."""

    def __init__(self, mail_dir: Path) -> None:
        self.mail_dir = mail_dir
        self.mail_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, digest: str, bucket: str) -> Path:
        """Der Ort einer Mail – allein aus Hash und Monat berechenbar.

        Dass sich der Pfad rein rechnerisch ergibt, ist der Grund, warum der
        Suchindex jederzeit wegwerfbar ist: Journal und Ablage genügen, um
        jede Mail wiederzufinden.
        """
        if not _BUCKET_RE.match(bucket):
            raise ValueError(f"Unplausibler Monatsordner: {bucket!r}")
        if len(digest) != 64 or not all(c in "0123456789abcdef" for c in digest):
            raise ValueError(f"Kein SHA-256: {digest!r}")
        return self.mail_dir / bucket / digest[:2] / digest

    def _find_existing(self, digest: str, bucket: str) -> Path | None:
        """Sucht die Datei zu einem Hash, gleich mit welcher Kompression."""
        base = self.path_for(digest, bucket)
        for suffix in (".eml" + s for s in compress.KNOWN_SUFFIXES):
            candidate = base.with_name(base.name + suffix)
            if candidate.exists():
                return candidate
        return None

    def put(self, raw: bytes, date: datetime | None) -> PutResult:
        """Legt eine Mail ab. War sie schon da, passiert nichts."""
        digest = content_hash(raw)
        bucket = bucket_for(date)

        if self._find_existing(digest, bucket) is not None:
            return PutResult(hash=digest, bucket=bucket, stored=False, size=len(raw))

        payload, suffix = compress.compress(raw)
        target = self.path_for(digest, bucket)
        target = target.with_name(target.name + ".eml" + suffix)
        target.parent.mkdir(parents=True, exist_ok=True)

        # Erst daneben schreiben, dann an den Platz rücken. Ein Absturz
        # hinterlässt so nie eine halbe Mail unter einem Namen, der
        # Vollständigkeit verspricht.
        temporary = target.with_name(target.name + ".neu")
        temporary.write_bytes(payload)
        os.replace(temporary, target)

        return PutResult(hash=digest, bucket=bucket, stored=True, size=len(raw))

    def get(self, digest: str, bucket: str) -> bytes:
        """Holt eine Mail zurück und prüft dabei ihre Unversehrtheit."""
        path = self._find_existing(digest, bucket)
        if path is None:
            raise FileNotFoundError(
                f"Mail {digest[:12]}… nicht in der Ablage (Monat {bucket})"
            )

        suffix = next(s for s in compress.KNOWN_SUFFIXES if path.name.endswith(s))
        raw = compress.decompress(path.read_bytes(), suffix)

        # Der Name ist der Hash – eine beschädigte Datei fällt hier auf,
        # ohne dass es dafür eine eigene Prüfsummenliste bräuchte.
        actual = content_hash(raw)
        if actual != digest:
            raise ValueError(
                f"Mail {digest[:12]}… ist beschädigt: Inhalt ergibt {actual[:12]}…"
            )
        return raw

    def exists(self, digest: str, bucket: str) -> bool:
        return self._find_existing(digest, bucket) is not None

    def remove(self, digest: str, bucket: str) -> bool:
        """Entfernt eine Mail von der Platte.

        Nur der Inhalt verschwindet. Dass es sie gab und dass sie entfernt
        wurde, hält das Journal in einem Grabstein fest – siehe
        :mod:`mailburg.core.journal`.
        """
        path = self._find_existing(digest, bucket)
        if path is None:
            return False
        path.unlink()
        return True

    def iter_all(self) -> Iterator[tuple[str, str]]:
        """Geht alle abgelegten Mails durch und liefert Hash und Monat.

        Dient dem Abgleich zwischen Ablage und Journal: eine Datei ohne
        Journaleintrag ist ebenso auffällig wie ein Eintrag ohne Datei.
        """
        for path in self.mail_dir.rglob("*.eml.*"):
            if path.name.endswith(".neu"):
                continue
            digest = path.name.split(".eml")[0]
            relative = path.relative_to(self.mail_dir)
            # mail/JJJJ/MM/xx/<hash>.eml.zst – die ersten beiden Ebenen sind der Monat
            if len(relative.parts) >= 3:
                yield digest, f"{relative.parts[0]}/{relative.parts[1]}"

    def disk_usage(self) -> int:
        """Belegter Platz der Ablage in Byte."""
        return sum(p.stat().st_size for p in self.mail_dir.rglob("*.eml.*"))
