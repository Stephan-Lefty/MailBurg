"""Eine Mail aus dem Archiv zurück in ein Postfach oder in eine Datei.

Ein Archiv, aus dem nichts wieder herauskommt, ist ein Grab. Irgendwann
braucht man eine alte Rechnung wieder im Mailprogramm – um sie zu
beantworten, weiterzuleiten oder einfach im gewohnten Ordner zu haben.

**Zurück muss auch dann gehen, wenn es das ursprüngliche Postfach nicht
mehr gibt.** Post überlebt Arbeitgeber, Anbieter und Adressen. Deshalb
wird beim Zurücklegen frei gewählt, wohin – nicht automatisch dorthin,
wo die Mail einmal herkam.

**Hier schreibt MailBurg zum ersten Mal in ein Postfach.** Sonst gilt
strikt: nur lesen, ``EXAMINE`` statt ``SELECT``, ``BODY.PEEK[]`` statt
``BODY[]``. Diese Ausnahme ist eng gefasst – sie geschieht nur auf
ausdrücklichen Befehl, für einzelne, benannte Nachrichten, und niemals
im Hintergrund. Gelöscht oder geändert wird im Postfach weiterhin
nichts.

**Bytegenau.** Zurückgespielt wird, was archiviert wurde – Kopfzeilen
unverändert, Zeilenenden unverändert. Nur so bleibt eine vorhandene
DKIM-Signatur gültig, und nur so ist die Mail im Postfach dieselbe wie
die im Archiv.
"""

from __future__ import annotations

import imaplib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


class RueckgabeFehler(RuntimeError):
    """Das Zurücklegen ist gescheitert."""


def als_datei(rohdaten: bytes, ziel: Path) -> Path:
    """Schreibt die Mail als ``.eml`` – der Weg, der immer offensteht.

    Eine ``.eml``-Datei öffnet jedes Mailprogramm, und in Thunderbird
    lässt sie sich in einen beliebigen Ordner ziehen. Das braucht weder
    Zugangsdaten noch ein erreichbares Postfach, und es funktioniert auch
    für Konten, die es längst nicht mehr gibt.
    """
    ziel = Path(ziel)
    if ziel.suffix.lower() != ".eml":
        ziel = ziel.with_name(ziel.name + ".eml")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(rohdaten)
    return ziel


def _zeitstempel(rohdaten: bytes) -> str:
    """Das Versanddatum im Format, das IMAP für ``APPEND`` erwartet.

    Ohne diese Angabe setzt der Server das Datum von *heute*. Die Mail
    stünde dann im Mailprogramm ganz oben statt an ihrem Platz in der
    Zeit – bei einer zwanzig Jahre alten Nachricht ein sinnloser Anblick.
    """
    kopf = rohdaten.split(b"\r\n\r\n", 1)[0].split(b"\n\n", 1)[0]
    for zeile in kopf.splitlines():
        if zeile[:5].lower() == b"date:":
            try:
                wann = parsedate_to_datetime(zeile[5:].decode("utf-8", "replace"))
            except (TypeError, ValueError):
                break
            if wann is not None:
                return imaplib.Time2Internaldate(wann)
    return imaplib.Time2Internaldate(datetime.now(timezone.utc))


def ins_postfach(konto, passwort: str, ordner: str, rohdaten: bytes,
                 ungelesen: bool = True) -> None:
    """Legt eine Mail in einen Ordner eines Postfachs.

    **Standardmäßig ungelesen.** Auf den ersten Blick ist das eine
    Falschmeldung – gelesen wurde die Mail ja längst. Praktisch ist es
    aber der einzige Weg, sie wiederzufinden: Sie kommt mit ihrem
    ursprünglichen Datum zurück und steht damit nicht oben im
    Posteingang, sondern zwischen der Post von damals. Ungelesen
    erscheint sie hervorgehoben und im Zähler des Ordners; ein Klick
    darauf, und sie ist wieder gelesen.

    Wer das nicht will, schaltet es ab.
    """
    from mailburg.sources.imap import ImapFehler, ImapSource

    if not rohdaten:
        raise RueckgabeFehler("Die Nachricht ist leer.")

    try:
        quelle = ImapSource(konto, passwort)
    except ImapFehler as exc:
        raise RueckgabeFehler(str(exc)) from exc

    try:
        status, antwort = quelle._verbindung.append(
            _ordner_kodieren(ordner),
            "" if ungelesen else "\\Seen",
            _zeitstempel(rohdaten),
            rohdaten,
        )
        if status != "OK":
            raise RueckgabeFehler(
                f"Der Server hat die Nachricht nicht angenommen: "
                f"{_lesbar(antwort)}"
            )
    except imaplib.IMAP4.error as exc:
        raise RueckgabeFehler(
            f"Der Server hat die Nachricht nicht angenommen – {exc}"
        ) from exc
    finally:
        quelle.close()


def _ordner_kodieren(ordner: str) -> str:
    """Setzt den Ordnernamen in Anführungszeichen, wenn nötig."""
    if ordner.startswith('"') or " " not in ordner:
        return ordner
    return '"' + ordner.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _lesbar(antwort) -> str:
    if isinstance(antwort, (list, tuple)):
        antwort = b" ".join(t for t in antwort if isinstance(t, bytes))
    if isinstance(antwort, bytes):
        return antwort.decode("utf-8", "replace")
    return str(antwort)
