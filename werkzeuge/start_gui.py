"""Einstieg für die gepackte Windows-Fassung.

PyInstaller braucht eine Datei, die es aufrufen kann – ein Modulpfad
wie ``mailburg.ui.app:main`` genügt ihm nicht. Diese Datei tut nichts
weiter, als genau das zu tun, was der Startbefehl ``mailburg-gui`` sonst
auch tut.

Sie steht in ``werkzeuge/``, weil sie zum Bauen gehört und nicht zum
Programm: Wer MailBurg über pip installiert, braucht sie nie.
"""

from __future__ import annotations

import multiprocessing
import sys

if __name__ == "__main__":
    # **Ohne das startet sich das Programm endlos selbst neu.** Unter
    # Windows gibt es kein fork(); Python startet für jeden Arbeitsprozess
    # die Datei erneut. In einer gepackten Anwendung ist diese Datei aber
    # die Anwendung – also öffnet jeder Prozess ein neues Fenster, das
    # wieder Prozesse startet. MailBurg zerlegt Anhänge in einem
    # Prozesspool und liefe genau hinein.
    multiprocessing.freeze_support()

    from mailburg.ui.app import main

    sys.exit(main())
