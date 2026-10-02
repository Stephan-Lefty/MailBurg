"""Ein Doppelklick, nach dem MailBurg im Browser offen ist.

**Woher der Wunsch kommt.** Stephan am 02.10.2026: »MailStore muss ich
auch per Hand starten, sonst passiert nix. Deshalb will ich für MailBurg
das rote Icon auf dem Desktop, was dann alle Dienste startet.«

**Der Unterschied, und er ist wichtig.** Bei MailStore startet man einen
*Client*. Hier läuft der Dienst schon – wenn er richtig eingerichtet ist,
seit dem Hochfahren. Dieses Programm startet also im Regelfall gar
nichts, es macht nur sichtbar, was ohnehin läuft.

Gebraucht wird es für den Fall, dass eben *nicht* alles läuft. Und dann
soll es nicht eine Fehlerseite im Browser geben, sondern den Weg
dorthin, wo sich das beheben lässt.

**Ohne Qt.** Ein Startknopf, der erst 150 MB Oberfläche lädt, bevor er
einen Browser öffnet, ist kein Startknopf. Qt kommt nur, wenn das
Einrichtungsfenster wirklich gebraucht wird.

**Warum das hier steht und nicht in ``server/``.** Dieses Programm
kennt beide Seiten: den Dienst, dessen Zustand es prüft, und das
Fenster, das es im Notfall öffnet. Der Server darf die Oberfläche aber
nicht kennen – er läuft auf einer Maschine ohne Bildschirm, wo PySide6
gar nicht installiert ist. Dieselbe Lage wie bei ``bilder.py``: Was zwei
Teile brauchen, gehört keinem von beiden.
"""

from __future__ import annotations

import sys
import time
import webbrowser

#: Wie lange auf einen anlaufenden Dienst gewartet wird. Windows startet
#: verzögerte Dienste erst eine Minute nach dem Hochfahren; wer dann
#: doppelklickt, soll nicht mit einer Fehlermeldung abgewiesen werden.
GEDULD = 20

#: Zwischen zwei Nachfragen. Kurz genug, dass es sich nicht hinzieht.
TAKT = 1.0


def _lage():
    from mailburg.core import paths  # noqa: F401  (setzt Umgebung auf)
    from mailburg.server.einstellungen import Serverlage

    return Serverlage.aus_umgebung()


def _adresse(lage) -> str:
    """Die Adresse für den Browser.

    **Immer 127.0.0.1, auch wenn der Dienst im Netz lauscht.** Dieses
    Programm läuft auf dem Server selbst; ``0.0.0.0`` ist keine Adresse,
    die ein Browser aufrufen kann – sie heißt »überall«, nicht »hier«.
    """
    hier = (
        "127.0.0.1" if lage.adresse in ("0.0.0.0", "::", "")  # noqa: S104
        else lage.adresse
    )
    if ":" in hier and not hier.startswith("["):
        hier = f"[{hier}]"
    return f"http://{hier}:{lage.anschluss}/"


def _antwortet(lage, zeit: float = 1.5) -> bool:
    """Ob die Weboberfläche da ist – gefragt wird ``/lebt``."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(  # noqa: S310
            f"{_adresse(lage)}lebt", timeout=zeit
        ) as antwort:
            return antwort.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _einrichtung_oeffnen(grund: str) -> int:
    """Das Einrichtungsfenster – mit dem Grund im Gepäck.

    **Nicht einfach aufgeben.** Wer doppelklickt und nichts bekommt,
    sucht als Nächstes im Browser; dort steht dann »nicht erreichbar«,
    und das sagt nichts über die Ursache.
    """
    print(grund, file=sys.stderr)
    try:
        from mailburg.ui.servereinrichtung import starten
    except ImportError:
        print(
            "Das Einrichtungsfenster fehlt (PySide6 nicht installiert).\n"
            "Nachrüsten mit:  pip install PySide6-Essentials",
            file=sys.stderr,
        )
        return 2
    return starten()


def oeffnen() -> int:
    """Nachsehen, notfalls starten, dann den Browser aufmachen."""
    from mailburg.server import einrichtung
    from mailburg.server.einstellungen import Fehlt

    try:
        lage = _lage()
    except Fehlt as fehler:
        return _einrichtung_oeffnen(
            f"Noch nicht eingerichtet: {fehler}"
        )

    # 1. Läuft schon? Dann ist nichts zu tun.
    if _antwortet(lage):
        webbrowser.open(_adresse(lage))
        return 0

    # 2. Vielleicht läuft er gerade an – Windows startet verzögerte
    #    Dienste erst eine Weile nach dem Hochfahren.
    zustand, _ = einrichtung.dienst_zustand()
    if zustand is einrichtung.Lage.ACHTUNG:  # »startet gerade«
        print("Der Dienst läuft gerade an …")
        for _ in range(int(GEDULD / TAKT)):
            time.sleep(TAKT)
            if _antwortet(lage):
                webbrowser.open(_adresse(lage))
                return 0

    # 3. Er steht. Starten – das braucht Rechte.
    if zustand is einrichtung.Lage.FEHLT:
        if not einrichtung.ist_administrator():
            return _einrichtung_oeffnen(
                "Der Dienst läuft nicht, und zum Starten fehlen die "
                "Rechte.\nBitte dieses Programm mit Rechtsklick → »Als "
                "Administrator ausführen« öffnen."
            )

        print("Starte den Dienst …")
        geklappt, ausgabe = einrichtung.dienst_starten()
        if geklappt:
            for _ in range(int(GEDULD / TAKT)):
                time.sleep(TAKT)
                if _antwortet(lage):
                    webbrowser.open(_adresse(lage))
                    return 0

        return _einrichtung_oeffnen(
            f"Der Dienst ließ sich nicht starten.\n{ausgabe}"
        )

    # 4. Er läuft, antwortet aber nicht – das ist der Fall, in dem es
    #    etwas zu sehen gibt.
    return _einrichtung_oeffnen(
        f"Der Dienst läuft, antwortet aber nicht auf {_adresse(lage)}.\n"
        f"Der Grund steht meistens im Ereignisprotokoll."
    )


def haupt() -> int:
    """Einstieg für den Startbefehl und das Symbol auf dem Schreibtisch."""
    import multiprocessing

    # Dieselbe Begründung wie in ``werkzeuge/start_gui.py``: Unter
    # Windows startet Python für jeden Arbeitsprozess die Datei erneut.
    multiprocessing.freeze_support()
    return oeffnen()


if __name__ == "__main__":
    raise SystemExit(haupt())
