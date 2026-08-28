"""Einstieg für die gepackte Windows-Fassung.

PyInstaller braucht eine Datei, die es aufrufen kann – ein Modulpfad
wie ``mailburg.ui.app:main`` genügt ihm nicht.

**Die Datei ist beides.** Unter Linux gibt es zwei Startbefehle:
``mailburg`` für die Kommandozeile und ``mailburg-gui`` für das Fenster.
Unter Windows gibt es nur eine Datei, und die muss beides können – wer
doppelklickt, will das Fenster; wer sie aus einem Skript oder aus der
Aufgabenplanung aufruft, will den Befehl.

Ohne diese Weiche wurde jedes Argument als Archivpfad gedeutet:
``MailBurg.exe abrufen --leise C:\\Archiv`` öffnete ein Fenster mit dem
Archiv »abrufen«, fand dort keines und blieb mit einem Fehlerdialog
stehen. Bemerkt hätte man das nicht sofort – der eingerichtete Zeitplan
ruft genau so auf und hätte alle 30 Minuten ein Fenster geöffnet, statt
Post zu holen. Am 2026-08-28 aufgefallen, als ein Prüfschritt im
Bau-Workflow hängenblieb, weil er auf einen Klick wartete, den auf einem
Bauserver niemand macht.
"""

from __future__ import annotations

import multiprocessing
import sys


def _befehle() -> set[str]:
    """Die Unterbefehle der Kommandozeile.

    Abgefragt statt aufgezählt: Eine Liste hier würde beim nächsten neuen
    Befehl vergessen, und der fiele dann still auf die Oberfläche
    zurück – mit einem Fenster, wo eine Ausgabe erwartet wurde.
    """
    import argparse

    from mailburg.__main__ import build_parser

    for aktion in build_parser()._actions:
        if isinstance(aktion, argparse._SubParsersAction):
            return set(aktion.choices)
    return set()


if __name__ == "__main__":
    # **Ohne das startet sich das Programm endlos selbst neu.** Unter
    # Windows gibt es kein fork(); Python startet für jeden Arbeitsprozess
    # die Datei erneut. In einer gepackten Anwendung ist diese Datei aber
    # die Anwendung – also öffnet jeder Prozess ein neues Fenster, das
    # wieder Prozesse startet. MailBurg zerlegt Anhänge in einem
    # Prozesspool und liefe genau hinein.
    multiprocessing.freeze_support()

    if len(sys.argv) > 1 and sys.argv[1] in _befehle():
        from mailburg.__main__ import main as kommandozeile

        sys.exit(kommandozeile())

    from mailburg.ui.app import main

    sys.exit(main())
