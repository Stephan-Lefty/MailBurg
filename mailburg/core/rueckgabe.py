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
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from mailburg.core import paths


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


#: Wie lange eine geöffnete Nachricht liegen bleiben darf, in Sekunden.
#: Vier Stunden – lang genug für einen Arbeitstag mit Unterbrechungen,
#: kurz genug, dass nach dem Wochenende nichts mehr herumliegt.
HALTBARKEIT = 4 * 60 * 60


def _aufraeumen(ordner: Path, *, alles: bool = False) -> int:
    """Wirft weg, was niemand mehr braucht. Gibt die Zahl zurück.

    **Warum nicht sofort nach dem Öffnen löschen.** Das Mailprogramm
    startet nebenläufig; wer die Datei gleich wieder entfernt, nimmt sie
    ihm unter den Fingern weg. Deshalb bleibt sie liegen und wird beim
    *nächsten* Öffnen mit weggeräumt – und spätestens, wenn MailBurg
    endet.
    """
    weg = 0
    grenze = time.time() - HALTBARKEIT
    for datei in ordner.glob("*.eml"):
        try:
            if alles or datei.stat().st_mtime < grenze:
                datei.unlink()
                weg += 1
        except OSError:
            # Unter Windows lässt sich eine Datei nicht löschen, solange
            # das Mailprogramm sie offen hält. Dann eben beim nächsten
            # Mal – ein Aufräumen darf nichts abbrechen.
            continue
    return weg


def aufraeumen_beim_beenden() -> int:
    """Räumt alle geöffneten Nachrichten weg. Für das Programmende."""
    try:
        return _aufraeumen(paths.geoeffnet_dir(), alles=True)
    except OSError:
        return 0


def im_mailprogramm_oeffnen(rohdaten: bytes, betreff: str = "") -> Path:
    """Legt die Mail als ``.eml`` ab und übergibt sie dem System.

    Der dritte Weg aus dem Archiv, neben dem Zurücklegen ins Postfach
    und dem Speichern als Datei. Er ist der bequemste: ein Klick, und
    die alte Rechnung steht im gewohnten Mailprogramm – zum Lesen,
    Weiterleiten, Beantworten.

    **Die Datei ist der heikle Teil, nicht das Öffnen.** Eine ``.eml``
    ist die vollständige Nachricht: Text, Anhänge, Adressen. Sie liegt
    deshalb im Cache-Ordner des Benutzers mit ``0700``, nicht in
    ``/tmp``, und die Datei selbst bekommt ``0600`` – siehe
    ``paths.geoeffnet_dir()``.

    **Verschwinden muss sie auch wieder.** Sofort geht nicht, das
    Mailprogramm liest sie ja noch. Aufgeräumt wird deshalb zweimal:
    beim nächsten Öffnen alles, was älter als vier Stunden ist, und beim
    Beenden von MailBurg der ganze Ordner.

    Gibt den Pfad zurück – für die Tests und für den Fall, dass jemand
    dem Benutzer sagen will, wo die Datei liegt.
    """
    ordner = paths.geoeffnet_dir()
    _aufraeumen(ordner)

    # Der Betreff im Namen, damit im Mailprogramm nicht »tmp8f2a.eml«
    # im Fenstertitel steht. Die Zufallsziffern verhindern, dass zwei
    # Nachrichten mit gleichem Betreff einander überschreiben, während
    # beide offen sind.
    ziel = ordner / f"{_namensteil(betreff)}-{uuid.uuid4().hex[:8]}.eml"
    ziel.write_bytes(rohdaten)
    if sys.platform != "win32":
        ziel.chmod(0o600)

    _dem_system_uebergeben(ziel)
    return ziel


def _namensteil(betreff: str) -> str:
    """Ein Dateiname aus dem Betreff, der auf jedem System zulässig ist."""
    sauber = "".join(
        "-" if z in '\\/:*?"<>|' else z for z in (betreff or "Nachricht")
    ).strip()
    # Kürzer als beim Speichern von Hand: Hier kommen acht Zeichen
    # Unterscheidung und die Endung noch dazu, und Windows setzt bei
    # 260 Zeichen für den ganzen Pfad eine Grenze.
    return sauber[:60].rstrip(". ") or "Nachricht"


def _dem_system_uebergeben(datei: Path) -> None:
    """Öffnet die Datei mit dem Programm, das der Benutzer dafür gewählt hat.

    Drei Systeme, drei Wege. Unter Windows ist ``os.startfile`` der
    richtige – ``start`` wäre ein Befehl der Eingabeaufforderung und
    bräuchte eine Shell, mit allem, was ein Dateiname dann anrichten
    kann.
    """
    if sys.platform == "win32":
        os.startfile(datei)  # noqa: S606 – kein Shell-Aufruf
        return

    befehl = "open" if sys.platform == "darwin" else "xdg-open"
    try:
        subprocess.Popen(
            [befehl, str(datei)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise RueckgabeFehler(
            f"»{befehl}« ließ sich nicht starten. Auf schlanken "
            f"Arbeitsumgebungen fehlt es manchmal; unter Debian und "
            f"Ubuntu liegt es im Paket »xdg-utils«.\n\n"
            f"Die Nachricht liegt trotzdem bereit:\n{datei}"
        ) from exc


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
