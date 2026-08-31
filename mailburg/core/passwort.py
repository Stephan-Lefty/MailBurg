"""Woher das Passwort eines verschlüsselten Archivs kommt.

Verschlüsseln ist die eine Hälfte; die andere ist, dass MailBurg danach
noch benutzbar bleibt. Drei Betriebszustände wollen bedient sein, und
sie widersprechen einander:

**Am Arbeitsplatz** tippt jemand das Passwort ein. Einmal beim Öffnen,
nicht bei jedem Befehl.

**Im Zeitplan** ruft nachts um drei niemand etwas ein. Der Abruf läuft
ohne Terminal, und wenn er nach einem Passwort fragt, bleibt er stehen –
unsichtbar, bis Wochen später auffällt, dass nichts mehr archiviert
wurde. Das ist der gefährlichste Fehlerfall des ganzen Programms: kein
Krachen, nur Stille.

**Auf dem Server** startet ein Dienst ohne angemeldeten Benutzer. Dort
gilt dasselbe wie für die Postfachpasswörter, und die Antwort ist
dieselbe: der :mod:`~mailburg.core.tresor`.

Die Reihenfolge ist deshalb: Umgebung, dann Tresor, dann fragen. Von
»ausdrücklich gesetzt« über »eingerichtet« zu »jemand sitzt davor«.

**Und was das kostet, gehört gesagt.** Ein Passwort, das MailBurg ohne
Zutun findet, findet auch jeder andere, der als derselbe Benutzer
Programme ausführen kann. Wer den Zeitplan benutzt, tauscht einen Teil
des Schutzes gegen Selbsttätigkeit. Das ist eine vertretbare
Entscheidung – aber eine, die man bewusst trifft, und deshalb steht sie
in der Anleitung und nicht nur hier.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

#: Das Archivpasswort aus der Umgebung – für Zeitplan, Dienst, Container.
UMGEBUNG = "MAILBURG_ARCHIVPASSWORT"

#: Oder der Pfad zu einer Datei, die es enthält. Auf einem Server der
#: bessere Weg: Eine Umgebungsvariable steht in der Prozessliste mancher
#: Systeme und in Fehlerberichten, eine Datei nicht. Passend zu
#: ``systemd`` und seinem ``LoadCredential=``.
UMGEBUNG_DATEI = "MAILBURG_ARCHIVPASSWORTDATEI"


def _kennung(archiv: Path) -> str:
    """Die Archivkennung, ohne das Archiv zu öffnen.

    Sie ist der Name, unter dem das Passwort im Tresor liegt – nicht der
    Pfad. Ein Archiv wandert auf eine andere Platte oder in einen
    anderen Ordner; seine Kennung nicht.
    """
    try:
        meta = json.loads(
            (Path(archiv) / "archive.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return ""
    return str(meta.get("uuid", ""))


def tresorname(archiv: Path) -> str:
    """Unter welchem Namen das Passwort im Tresor steht."""
    kennung = _kennung(archiv)
    return f"archiv:{kennung}" if kennung else ""


def hinterlegt(archiv: Path) -> str | None:
    """Das Passwort, sofern es ohne Nachfrage zu haben ist.

    Gibt ``None`` zurück, wenn jemand gefragt werden muss. Wirft nicht:
    Ein nicht eingerichteter Tresor ist kein Fehler, sondern der
    Normalfall am Arbeitsplatz.
    """
    ort = os.environ.get(UMGEBUNG_DATEI, "").strip()
    if ort:
        try:
            inhalt = Path(ort).read_text(encoding="utf-8").strip()
        except OSError:
            inhalt = ""
        if inhalt:
            return inhalt

    aus_umgebung = os.environ.get(UMGEBUNG, "").strip()
    if aus_umgebung:
        return aus_umgebung

    return aus_tresor(archiv)


def aus_tresor(archiv: Path) -> str | None:
    """Nur der Tresor, ohne Umgebung. Für die Frage »ist es hinterlegt?«."""
    from mailburg.core import tresor

    name = tresorname(archiv)
    if not name or not tresor.verfuegbar():
        return None
    try:
        return tresor.holen(name)
    except tresor.TresorFehler:
        # Ein Tresor, der nicht aufgeht, darf nicht als »kein Passwort
        # hinterlegt« durchgehen - sonst fragt MailBurg nach etwas, das
        # längst da ist, und niemand kommt darauf, dass nur der
        # Hauptschlüssel fehlt. Die Meldung dazu kommt beim nächsten
        # ausdrücklichen Zugriff; hier ginge sie ins Leere.
        return None


def in_tresor(archiv: Path, passwort: str) -> None:
    """Legt das Passwort im Tresor ab, damit der Dienst ohne Nachfrage läuft."""
    from mailburg.core import tresor

    name = tresorname(archiv)
    if not name:
        raise tresor.TresorFehler(
            f"In {archiv} liegt kein Archiv – jedenfalls keines mit Kennung."
        )
    tresor.setzen(name, passwort)


def aus_tresor_entfernen(archiv: Path) -> None:
    from mailburg.core import tresor

    name = tresorname(archiv)
    if name:
        tresor.loeschen(name)
