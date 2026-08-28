"""Mitgelieferte Hilfsprogramme auffindbar machen.

MailBurg ruft für die Texterkennung zwei fremde Programme auf:
``pdftoppm`` aus poppler macht aus jeder PDF-Seite ein Bild, ``tesseract``
liest den Text daraus. Unter Linux installiert man beide mit einem Befehl
aus der Paketverwaltung, und ``shutil.which`` findet sie im Suchpfad.

**Unter Windows gibt es keine Paketverwaltung, auf die man verweisen
könnte.** Die Anleitung dorthin lautete bisher: poppler von einer
GitHub-Release-Seite herunterladen, ZIP entpacken, den ``bin``-Ordner in
die Umgebungsvariable ``PATH`` eintragen, dasselbe noch einmal für
tesseract, und die Sprachdaten für Deutsch nicht vergessen. Das ist
nichts, was jemand nebenbei erledigt – und wer es nicht erledigt, hat ein
Archiv, das eingescannte Rechnungen nicht findet. Damit wäre MailBurg
unter Windows eben doch nicht dieselbe Lösung wie unter Linux.

Die gepackte ``MailBurg.exe`` bringt beide Programme deshalb mit. Dieses
Modul stellt sie so bereit, dass der übrige Code nichts davon merken
muss: Es hängt den mitgelieferten Ordner vorn an ``PATH``, und alle
bestehenden ``shutil.which``-Abfragen finden sie von da an von selbst.

**Vorn, nicht hinten.** Wer tesseract selbst installiert hat, hat es
womöglich in einer anderen Fassung oder ohne deutsche Sprachdaten. Was
mitgeliefert wurde, ist erprobt; was auf dem Rechner steht, ist unbekannt.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

#: Der Unterordner, in dem die gepackte Fassung ihre Hilfsprogramme
#: ablegt. Steht auch in ``werkzeuge/mailburg.spec``.
ORDNER = "werkzeuge"

#: Ob schon einmal aufgeräumt wurde. ``bereitstellen`` wird aus mehreren
#: Ecken aufgerufen und soll ``PATH`` nicht bei jedem Mal verlängern.
_erledigt = False


def mitgeliefert() -> Path | None:
    """Wo die mitgelieferten Programme liegen – falls es welche gibt.

    Zwei Orte, in dieser Reihenfolge:

    * ``sys._MEIPASS`` – das Verzeichnis, in das sich die ``.exe`` beim
      Start entpackt. Der Normalfall.
    * neben dem Programm – für den, der die Werkzeuge nachträglich
      danebenlegt, etwa weil er eine andere tesseract-Fassung braucht.
    """
    kandidaten = []
    entpackt = getattr(sys, "_MEIPASS", "")
    if entpackt:
        kandidaten.append(Path(entpackt) / ORDNER)
    if getattr(sys, "frozen", False):
        kandidaten.append(Path(sys.executable).parent / ORDNER)

    for ort in kandidaten:
        if ort.is_dir():
            return ort
    return None


def bereitstellen() -> bool:
    """Hängt die mitgelieferten Programme vorn in den Suchpfad.

    Gibt zurück, ob etwas gefunden wurde. Mehrfaches Aufrufen schadet
    nicht.
    """
    global _erledigt

    ort = mitgeliefert()
    if ort is None:
        return False
    if _erledigt:
        return True

    os.environ["PATH"] = os.pathsep.join(
        [str(ort), os.environ.get("PATH", "")]
    ).rstrip(os.pathsep)

    # **Ohne das findet tesseract seine Sprachdaten nicht.** Es sucht sie
    # in einem Ordner, den es aus seinem eigenen Installationsort
    # ableitet – und der ist bei einer entpackten .exe ein
    # Zufallsverzeichnis unter %TEMP%. Es meldet dann nicht »Sprachdaten
    # fehlen«, sondern »Failed loading language 'deu'« und liefert
    # nichts. Am Ende stünde im Archiv eine leere Abschrift, und niemand
    # wüsste, warum.
    daten = ort / "tessdata"
    if daten.is_dir():
        os.environ["TESSDATA_PREFIX"] = str(daten)

    _erledigt = True
    return True


def lautlos() -> dict[str, int]:
    """Zusatzangaben für ``subprocess``, damit kein Fenster aufblitzt.

    **Warum das nötig ist.** ``pdftoppm``, ``pdftotext`` und ``tesseract``
    sind Konsolenprogramme. Startet eine Anwendung mit Fenster sie unter
    Windows, öffnet das System für jeden Aufruf eine Konsole – sie
    erscheint, blitzt auf und verschwindet wieder.

    Bei der Texterkennung geschieht das mehrfach je Seite. Stephan hat es
    am 2026-08-28 so beschrieben: »auf zu, auf, zu«. Über die Dauer einer
    Erkennung sind das dutzende Fenster, die sich vor alles andere
    schieben und den Rechner unbenutzbar machen. Wer das sieht, hält das
    Programm für kaputt – zu Recht.

    Unter Linux und macOS gibt es das Flag nicht; dort ist das Ergebnis
    ein leeres Wörterbuch und ändert nichts.
    """
    if os.name != "nt":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
