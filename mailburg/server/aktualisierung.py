"""Nachsehen, ob es eine neue Fassung gibt – und sie einspielen.

**Woher das kommt.** Am 02.10.2026 musste Stephan auf dem Windows Server
dreimal von Hand aktualisieren: ZIP laden, altes Verzeichnis löschen,
entpacken, ``pip install``, Dienst neu starten. Fünf Befehle, von denen
einer das Archiv mitgelöscht hätte, wenn es im Programmordner gelegen
hätte. Das gehört in einen Knopf.

**Zwei Festlegungen, die nicht ohne Grund aufgemacht werden sollten:**

*Gefragt wird nach Releases, nicht nach dem letzten Stand.* Auf
``main`` liegt, woran gerade gearbeitet wird; ein Archivserver soll
davon nichts mitbekommen. Eine Fassung mit Nummer ist eine Zusage, ein
Zwischenstand nicht.

*Installiert wird aus einem Wegwerfverzeichnis.* Das ZIP wird nach
``%TEMP%`` entpackt, und ``pip`` holt es von dort. Der Programmordner
bleibt unberührt – wer ihn löscht und neu entpackt, löscht irgendwann
auch das, was jemand hineingelegt hat. Genau das drohte am 02.10.

**Ohne Internet ist das kein Fehler.** Ein Archivserver steht oft in
einem Netz ohne Außenverbindung. Dann sagt die Prüfung »nicht
erreichbar« und sonst nichts; alles andere liefe weiter.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from mailburg import __version__

#: Woher die Auskunft kommt. Die GitHub-API, nicht die Webseite: Sie
#: antwortet mit JSON und ändert ihre Form seltener als eine HTML-Seite.
API = "https://api.github.com/repos/Stephan-Lefty/MailBurg/releases/latest"

#: Wie lange auf eine Antwort gewartet wird. **Kurz gehalten**: Steht der
#: Server in einem Netz ohne Außenverbindung, soll das Fenster nicht
#: sekundenlang hängen, bevor es die Prüfliste zeigt.
GEDULD = 4.0

#: Womit nachinstalliert wird. Dieselbe Liste wie in der Anleitung – wer
#: hier ein Extra hinzufügt, muss auch ``docs/server-einrichten.md``
#: nachziehen, sonst bekommt ein Update mehr als die Erstinstallation.
ZUSAETZE = "server-windows,imap,anhaenge,packen,oberflaeche"


@dataclass
class Stand:
    """Was draußen liegt – und ob es neuer ist als das hier."""

    hier: str
    draussen: str = ""
    seite: str = ""
    zip_adresse: str = ""
    fehler: str = ""

    @property
    def neuer(self) -> bool:
        if not self.draussen or self.fehler:
            return False
        return _zahlen(self.draussen) > _zahlen(self.hier)


def _zahlen(fassung: str) -> tuple[int, ...]:
    """»v1.7.10« → ``(1, 7, 10)``.

    **Nicht als Text vergleichen.** Zeichenweise wäre »1.7.10« kleiner
    als »1.7.7«, und ein Update bliebe genau dann aus, wenn es am
    nötigsten wäre. Was keine Zahl ist, zählt als 0 – eine Fassung mit
    Zusatz (»1.8.0rc1«) gilt damit als die Fassung ohne ihn und nicht
    als neuer.
    """
    teile = re.findall(r"\d+", fassung or "")
    return tuple(int(t) for t in teile[:3]) or (0,)


def nachsehen(zeit: float = GEDULD) -> Stand:
    """Fragt GitHub nach der neuesten veröffentlichten Fassung."""
    stand = Stand(hier=__version__)
    try:
        bitte = urllib.request.Request(  # noqa: S310
            API, headers={"Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(bitte, timeout=zeit) as antwort:  # noqa: S310
            daten = json.loads(antwort.read().decode("utf-8"))
    except urllib.error.URLError as fehler:
        stand.fehler = f"nicht erreichbar ({fehler.reason})"
        return stand
    except (OSError, ValueError) as fehler:
        stand.fehler = str(fehler)
        return stand

    stand.draussen = str(daten.get("tag_name", "")).lstrip("v")
    stand.seite = str(daten.get("html_url", ""))
    stand.zip_adresse = str(daten.get("zipball_url", ""))
    return stand


def einspielen(stand: Stand, melden=None) -> bool:
    """Lädt die neue Fassung und installiert sie.

    **Der Dienst wird nicht angefasst.** Erst installieren, dann – vom
    Aufrufer – neu starten. Andersherum stünde der Dienst still, während
    ``pip`` arbeitet, und bliebe unten, wenn dabei etwas schiefgeht.
    Solange er läuft, hat er seinen Code im Speicher; eine Installation
    daneben stört ihn nicht.

    ``melden`` bekommt jede Zeile – das Fenster schreibt sie mit, damit
    ein fehlgeschlagener Schritt nicht nur als »ging nicht« dasteht.
    """
    sagen = melden or (lambda _: None)

    if not stand.zip_adresse:
        sagen("Keine Bezugsquelle – erst nachsehen.")
        return False

    with tempfile.TemporaryDirectory(prefix="mailburg-update-") as ort:
        hier = Path(ort)
        paket = hier / "fassung.zip"

        sagen(f"Lade {stand.draussen} …")
        try:
            urllib.request.urlretrieve(stand.zip_adresse, paket)  # noqa: S310
        except (urllib.error.URLError, OSError) as fehler:
            sagen(f"Herunterladen ging nicht: {fehler}")
            return False

        sagen("Entpacken …")
        import zipfile

        try:
            with zipfile.ZipFile(paket) as zip_datei:
                zip_datei.extractall(hier)
        except (zipfile.BadZipFile, OSError) as fehler:
            sagen(f"Das Paket ließ sich nicht entpacken: {fehler}")
            return False

        # GitHub packt alles in einen Ordner mit Fassungsnamen darin;
        # wie der heißt, steht nirgends zugesagt. Gesucht wird deshalb
        # die ``pyproject.toml`` – das ist das, was ``pip`` braucht.
        wurzeln = list(hier.glob("*/pyproject.toml"))
        if not wurzeln:
            sagen("Im Paket steht keine pyproject.toml – falscher Inhalt?")
            return False
        quelle = wurzeln[0].parent

        sagen(f"Installieren aus {quelle.name} …")
        lauf = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "--disable-pip-version-check",
                f"{quelle}[{ZUSAETZE}]",
            ],
            capture_output=True, text=True, timeout=900,
            errors="replace",
        )
        for zeile in (lauf.stdout + lauf.stderr).splitlines()[-12:]:
            if zeile.strip():
                sagen(f"  {zeile.rstrip()}")

        if lauf.returncode:
            sagen("Die Installation ist fehlgeschlagen – es bleibt beim Alten.")
            return False

    sagen(f"Eingespielt: {stand.draussen}")
    return True
