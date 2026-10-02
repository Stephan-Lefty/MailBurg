"""Einstieg für ``MailBurg-Server-Einrichten.exe``.

PyInstaller braucht eine Datei, die es aufrufen kann – ein Modulpfad wie
``mailburg.ui.servereinrichtung:starten`` genügt ihm nicht.

**Warum eine eigene Datei neben ``start_gui.py``.** Die beiden Programme
haben verschiedene Anwender: Das Archivfenster benutzt täglich, wer Post
sucht; dieses hier benutzt einmal, wer den Server aufsetzt. In eine
Datei gepackt müsste man beim Doppelklick raten, was gemeint ist – und
ein Einrichtungsprogramm, das als Archivfenster aufgeht, ist genauso
unbrauchbar wie umgekehrt.

**Mit Kommandozeile, aus demselben Grund wie dort.** Wer die Datei aus
einem Skript aufruft, will keine Oberfläche. ``--pruefen`` schreibt die
Prüfliste auf die Konsole und ist damit das, was man in eine
Überwachung hängt.
"""

from __future__ import annotations

import multiprocessing
import sys


def _konsole_anhaengen() -> None:
    """Sich an die Konsole hängen, aus der man aufgerufen wurde.

    **Sonst schreibt ``--pruefen`` ins Leere.** Die gepackte Fassung ist
    mit ``console=False`` gebaut – wer doppelklickt, soll kein schwarzes
    Fenster sehen. Damit hat der Prozess aber gar keine Standardausgabe,
    und eine Prüfliste, die niemand lesen kann, ist keine.

    Dieselbe Regel wie bei ``ui/app.py._sichtbar_melden()``: Vor jedem
    ``print`` in einem Weg, der grafisch beginnen kann, steht die Frage,
    wer das lesen soll. Hier ist die Antwort die PowerShell, aus der der
    Aufruf kam – ``AttachConsole`` mit ``ATTACH_PARENT_PROCESS``.

    Ohne Windows und ohne aufrufende Konsole passiert nichts; dann ist
    die Standardausgabe ohnehin da oder ohnehin weg.
    """
    if sys.platform != "win32" or sys.stdout is not None:
        return
    try:
        import ctypes

        if not ctypes.windll.kernel32.AttachConsole(-1):  # ATTACH_PARENT
            return
        sys.stdout = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115
        sys.stderr = sys.stdout
    except Exception:  # noqa: BLE001
        # **Weit gefangen, mit Grund:** Ohne Konsole bleibt es bei
        # keiner Ausgabe – das ist der Zustand von vorher und kein
        # Anlass, das Programm zu beenden.
        pass


def _pruefliste() -> int:
    """Die Prüfliste als Text – für Skripte und für Fehlerberichte."""
    _konsole_anhaengen()

    from mailburg.server import einrichtung
    from mailburg.server.einrichtung import Umgebung

    werte = einrichtung.gesetzte_variablen()
    from mailburg.server import einstellungen as lage
    from pathlib import Path

    ort = werte.get(lage.ARCHIV, "").strip()
    roh = werte.get(lage.ANSCHLUSS, "").strip()
    bild = einrichtung.alles_pruefen(Umgebung(
        archiv=Path(ort) if ort else None,
        adresse=werte.get(lage.ADRESSE, "").strip() or lage.STANDARD_ADRESSE,
        anschluss=int(roh) if roh.isdigit() else lage.STANDARD_ANSCHLUSS,
    ))

    zeichen = {"gut": "+", "fehlt": "-", "achtung": "!", "unklar": "?"}
    for befund in bild.befunde:
        print(f"{zeichen[befund.lage.value]} {befund.titel}: {befund.text}")
        if befund.einzelheiten:
            print(f"    {befund.einzelheiten}")

    # Rückgabe 0 nur, wenn nichts Zwingendes fehlt – damit ein Skript
    # danach entscheiden kann, ohne die Ausgabe zu lesen.
    return 0 if bild.bereit else 1


if __name__ == "__main__":
    # **Ohne das startet sich das Programm endlos selbst neu.** Unter
    # Windows gibt es kein fork(); in einer gepackten Anwendung ist
    # diese Datei die Anwendung, und jeder Arbeitsprozess öffnete ein
    # neues Fenster. Dieselbe Begründung wie in ``start_gui.py``.
    multiprocessing.freeze_support()

    if len(sys.argv) > 1 and sys.argv[1] in ("--pruefen", "/pruefen"):
        sys.exit(_pruefliste())

    from mailburg.ui.servereinrichtung import starten

    sys.exit(starten())
