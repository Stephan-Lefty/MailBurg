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
