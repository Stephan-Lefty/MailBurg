"""Tests für MailBurg.

**Die Tests legen ihre Indizes woanders ab als der Betrieb.** Ein Archiv
hält seinen Suchindex bewusst außerhalb des Archivordners – auf einem
synchronisierten Laufwerk ginge SQLite sonst kaputt. Für die Tests heißt
das: Jedes wegwerfbare Archiv hinterlässt eine Indexdatei im echten
Datenverzeichnis des Anwenders, und die räumt niemand weg, weil der
temporäre Ordner ja gelöscht wird.

Bemerkt wurde das am 2026-08-26: 5.585 Dateien, 1,5 GB, davon zwei
echte. Bei einem Dutzend Testläufen am Tag wächst das ungebremst, und
auffallen kann es nicht – niemand sieht sich das Datenverzeichnis an,
wenn die Tests grün sind.

Deshalb wird ``XDG_DATA_HOME`` hier auf ein Verzeichnis unter ``/tmp``
gebogen, bevor irgendein MailBurg-Modul geladen wird. Das muss ganz oben
stehen: ``paths.data_dir()`` liest die Umgebung beim ersten Zugriff.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile

#: Hierhin schreiben die Tests. Wird beim Beenden wieder entfernt.
_WEGWERFBAR = tempfile.mkdtemp(prefix="mailburg-tests-")

os.environ["XDG_DATA_HOME"] = _WEGWERFBAR
os.environ["XDG_CONFIG_HOME"] = _WEGWERFBAR
os.environ["XDG_CACHE_HOME"] = _WEGWERFBAR


@atexit.register
def _aufraeumen() -> None:
    shutil.rmtree(_WEGWERFBAR, ignore_errors=True)


# **Qt vor dem Interpreter abbauen.**
#
# Am 2026-10-09 brach der Testlauf in der CI nach dem *letzten* Test mit
# einem Speicherzugriffsfehler ab, während alle Tests grün meldeten.
# Davor stand eine Zeile von Qt: »shared QObject was deleted directly.
# The program is malformed and may crash.«
#
# **Die Ursache ist die Reihenfolge beim Herunterfahren.** Die
# QApplication lebt als Klassenattribut in einem Dutzend Testklassen und
# damit bis zum Schluss. Räumt Python dann seine Module ab, kann ein
# Widget nach seiner Anwendung sterben – und Qt zerbricht daran, tief im
# C++-Teil, wo kein Python-Rahmen mehr steht (``faulthandler`` meldet
# genau das: »Current thread: <no Python frame>«).
#
# **Gemessen, nicht vermutet:** Zehn Tests, die nichts tun als
# ``assertTrue(True)``, reichen zum Absturz. Es liegt also nicht an
# einem bestimmten Test, sondern an der schieren Zahl – und damit hätte
# jeder künftige Test dieselbe Wirkung.
#
# ``atexit`` läuft, bevor Python die Module zerlegt. Hier zuletzt
# registriert, also zuerst ausgeführt: erst Qt, dann der Papierkorb.
@atexit.register
def _qt_zuerst_abbauen() -> None:
    import sys

    widgets = sys.modules.get("PySide6.QtWidgets")
    if widgets is None:          # Lauf ohne Oberfläche
        return
    anwendung = widgets.QApplication.instance()
    if anwendung is None:
        return
    for fenster in anwendung.topLevelWidgets():
        fenster.close()
        fenster.deleteLater()
    anwendung.processEvents()
    anwendung.quit()
