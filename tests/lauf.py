#!/usr/bin/env python3
"""Der Testläufer – wie ``unittest discover``, nur mit sauberem Schluss.

    python3 tests/lauf.py              alle Tests
    python3 tests/lauf.py "test_ui*"   nur, was auf das Muster passt

**Warum es das gibt.** Am 2026-10-09 brach der Testlauf in der CI
**nach** dem letzten Test ab – mal mit Signal 11, mal mit Signal 6 –,
während unittest zuvor »OK« gemeldet hatte. Davor stand eine Zeile von
Qt: »QObject: shared QObject was deleted directly. The program is
malformed and may crash.« ``python -X faulthandler`` zeigte, wo:
*Current thread: <no Python frame>*. Der Absturz liegt im C++-Teil von
Qt beim Herunterfahren des Interpreters, nicht in Python.

**Es lag nicht an einem bestimmten Test, sondern an der Zahl.** Zehn
Methoden, die nichts tun als ``assertTrue(True)``, auf den grünen Stand
davor gelegt – und der Lauf bricht ab. 2383 Tests gingen, 2393 nicht.
Damit hätte jeder künftige Test dieselbe Wirkung gehabt, und bei einem
Projekt, in dem jede Zusage einen Test schuldet, ist das eine Wand.

**Was dieser Läufer anders macht:** Er führt die Tests aus, merkt sich
das Ergebnis, räumt auf – und beendet den Prozess dann selbst, bevor
Python seine Module zerlegt und Qt dabei über die eigenen Füße fällt.

**Das behebt das Symptom, nicht die Ursache**, und das steht hier, weil
es jemand wissen muss, der später hier liest. Der eigentliche Fehler
sitzt in der Reihenfolge, in der Qt-Objekte beim Herunterfahren sterben;
fünf Versuche, ihn zu finden, sind an einem Vormittag gescheitert (die
Liste steht in der TODO). Dieser Weg ist in PySide-Projekten gebräuchlich
und macht die Suite wieder benutzbar.

**Der Preis, und er ist nicht klein:** Fehler, die *erst beim Aufräumen*
aufträten – eine nicht geschlossene Datei, ein hängender Faden –, fallen
damit nicht mehr auf. Wer so etwas sucht, lässt die Suite ohne diesen
Läufer laufen:

    PYTHONPATH="$PWD" python3 -m unittest discover -s tests

**Der Rückgabewert ist das Einzige, was hier wirklich zählt.** Ein
Läufer, der immer ``0`` liefert, wäre schlimmer als jeder Absturz: Die
CI wäre grün, und niemand sähe je wieder einen gescheiterten Test. Dafür
gibt es ``tests/test_testlaeufer.py``, der ihn in beide Richtungen
prüft – mit einem Test, der bestehen soll, und einem, der scheitern
muss.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

HIER = Path(__file__).resolve().parent
WURZEL = HIER.parent


def laufen(muster: str = "test*.py", wortreich: int = 1,
           start: Path | None = None, wurzel: Path | None = None,
           ausgabe=None) -> int:
    """Führt die Tests aus und gibt den Rückgabewert zurück.

    Getrennt von :func:`main`, damit der Testläufer selbst prüfbar
    bleibt, ohne dass dabei jemand den Prozess abschießt. ``start``,
    ``wurzel`` und ``ausgabe`` sind nur dafür da – im Betrieb stimmen
    die Vorgaben.

    ``ausgabe`` lenkt den Bericht um. Die eigenen Tests des Läufers
    lassen absichtlich scheiternde Proben laufen; ohne Umleitung stünde
    deren »FAILED (failures=1)« mitten in einem grünen Lauf, und wer
    das liest, sucht einen Fehler, den es nicht gibt.
    """
    # ``top_level_dir`` muss die Wurzel sein, nicht ``tests/``: Sonst
    # lädt unittest die Dateien als lose Module statt als Paket, und
    # ``tests/__init__.py`` liefe nicht – das biegt die Datenpfade nach
    # ``/tmp``, bevor ein MailBurg-Modul geladen wird.
    lader = unittest.TestLoader()
    suite = lader.discover(
        start_dir=str(start or HIER), pattern=muster,
        top_level_dir=str(wurzel or WURZEL),
    )
    laeufer = unittest.TextTestRunner(verbosity=wortreich, stream=ausgabe)
    ergebnis = laeufer.run(suite)
    return 0 if ergebnis.wasSuccessful() else 1


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv if argv is None else argv
    code = laufen(argv[1] if len(argv) > 1 else "test*.py")

    # **Erst aufräumen, dann abschießen** – aber nur den eigenen Haken.
    #
    # Hier stand zuerst ``atexit._run_exitfuncs()``, und das war genau
    # falsch: Der Aufruf führt *alle* registrierten Haken aus, auch den
    # von PySide6, der Qt abbaut. Damit stieß er denselben Absturz an,
    # den dieser Läufer vermeiden soll – der Prozess starb drei
    # Sekunden nach der Zeile »OK«, mit Signal 6.
    #
    # Gebraucht wird genau einer: der, der das Wegwerfverzeichnis der
    # Tests löscht. Ohne ihn bliebe nach jedem Lauf ein Ordner unter
    # ``/tmp`` zurück – der Müll, den ``tests/__init__.py`` am
    # 2026-08-26 abstellen sollte (5.585 Dateien, 1,5 GB).
    testpaket = sys.modules.get("tests")
    aufraeumen = getattr(testpaket, "_aufraeumen", None)
    if aufraeumen is not None:
        aufraeumen()

    # **Und erst danach die Puffer leeren.** ``os._exit`` schreibt
    # nichts mehr weg: Ohne das fehlte am Ende die Zeile »OK« – und ein
    # Testlauf ohne Ergebniszeile ist für den, der ihn liest, dasselbe
    # wie ein abgestürzter.
    sys.stdout.flush()
    sys.stderr.flush()

    os._exit(code)


if __name__ == "__main__":
    main()
