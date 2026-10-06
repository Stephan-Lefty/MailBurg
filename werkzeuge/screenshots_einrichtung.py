#!/usr/bin/env python3
"""Bilder vom Einrichtungsfenster – mit erfundenen Befunden.

    python werkzeuge/screenshots_einrichtung.py

**Warum die Befunde erfunden sind.** Die Prüfliste misst den Rechner,
auf dem sie läuft. Auf einem Linux-Rechner ohne Windows-Dienst stünden
dort lauter rote Punkte – »kein Windows«, »kein Dienst«, »keine
Weboberfläche« –, und das Bild zeigte nicht das Fenster, sondern den
Bauplatz.

Dieselbe Begründung wie beim Vorführarchiv: *Was abgebildet wird, muss
aussehen wie der Betrieb.* Die Befunde hier sind deshalb gesetzt, nicht
gemessen, und die Pfade darin sind Beispiele.

**Zwei Bilder, weil die Ampel zwei Geschichten erzählt.** Grün zeigt,
wie es aussieht, wenn alles läuft. Rot zeigt, wofür es die Ampel gibt:
Der Satz oben nennt die erste offene Sache, und der Knopf daneben führt
dorthin.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
BILDER = WURZEL / "docs" / "bilder"

#: Breite des abgebildeten Fensters. Breiter als ein Dialog, weil die
#: Prüfliste drei Spalten hat: Zeichen, Titel, Text – und rechts noch
#: einen Knopf.
BREITE = 1180


def _befunde(gut: bool):
    """Die Prüfliste, wie sie auf einem eingerichteten Server aussieht.

    ``gut=False`` dreht drei Zeilen auf Rot und Gelb – und zwar die,
    die im Betrieb wirklich vorkommen: ein Dienst, der nicht läuft, ein
    fehlender Abruf und ein Tresor ohne Hauptschlüssel.
    """
    from mailburg.server.einrichtung import Befund, Gesamtbild, Lage

    liste = [
        Befund("Betriebssystem", Lage.GUT, "Windows."),
        Befund("Python", Lage.GUT, "Python 3.13 – ausreichend."),
        Befund("Fassung", Lage.UNKLAR, "1.8.0 – noch nicht nachgesehen.",
               abhilfe="nachsehen"),
        Befund("Pakete für den Dienst", Lage.GUT,
               "starlette und uvicorn sind da."),
        Befund("pywin32", Lage.GUT, "vorhanden."),
        Befund("keyring", Lage.GUT, "vorhanden."),
        Befund("cryptography", Lage.GUT, "vorhanden."),
        Befund("Rechte", Lage.GUT, "Als Administrator gestartet."),
        Befund("Archiv", Lage.GUT, r"D:\Firmenarchiv"),
        Befund("Zugänge", Lage.GUT, "5 mit Passwort."),
        Befund("Einstellungen", Lage.GUT, "Übernommen."),
        Befund("Dienst", Lage.GUT, "Läuft."),
        Befund("Start beim Hochfahren", Lage.GUT,
               "Automatisch (verzögert) – er kommt nach einem Neustart "
               "von selbst wieder."),
        Befund("Tresor", Lage.GUT, "7 Passwörter hinterlegt, "
                                   "Hauptschlüssel ist da."),
        Befund("Abruf", Lage.GUT, "Alle 30 Minuten. Ruhe von 17:10-04:00."),
        Befund("Weboberfläche", Lage.GUT, "Antwortet auf http://0.0.0.0:8383/"),
    ]

    if gut:
        return Gesamtbild(liste)

    ersatz = {
        "Dienst": Befund(
            "Dienst", Lage.FEHLT, "Eingerichtet, läuft aber nicht.",
            abhilfe="dienst_start"),
        "Tresor": Befund(
            "Tresor", Lage.ACHTUNG,
            "Nicht eingerichtet. Der Dienst stellt das Archiv bereit, "
            "holt aber keine neue Post.", abhilfe="tresor"),
        "Abruf": Befund(
            "Abruf", Lage.ACHTUNG,
            "Es wird keine Post geholt. Der Dienst stellt das Archiv "
            "bereit, aber es wächst nicht mehr.", abhilfe="abruf"),
        "Weboberfläche": Befund(
            "Weboberfläche", Lage.FEHLT,
            "Antwortet nicht auf Port 8383."),
    }
    return Gesamtbild([ersatz.get(b.titel, b) for b in liste])


def _durchatmen(anwendung) -> None:
    """Qt die Gelegenheit geben, aufzuräumen und zu zeichnen.

    **``deleteLater()`` wirkt erst in der Ereignisschleife.** Beim
    Auffrischen räumt das Fenster die alten Prüfzeilen so weg – wer
    gleich danach ein Bild nimmt, erwischt sie noch und bekommt
    übereinandergeschriebenen Text. Genau das ist beim ersten Lauf
    dieses Werkzeugs passiert.

    ``sendPostedEvents`` mit ``DeferredDelete`` arbeitet genau diese
    Warteschlange ab; ``processEvents`` allein tut es nicht.
    """
    from PySide6.QtCore import QCoreApplication, QEvent

    for _ in range(4):
        anwendung.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        anwendung.processEvents()


def _fenster(anwendung, gut: bool):
    from unittest import mock

    from mailburg.server import einrichtung
    from mailburg.ui.servereinrichtung import Einrichtungsfenster

    with mock.patch.object(
        einrichtung, "alles_pruefen", return_value=_befunde(gut)
    ):
        fenster = Einrichtungsfenster()
        fenster.archivfeld.setText(r"D:\Firmenarchiv")
        fenster.gemeinsamfeld.setText(r"D:\MailBurg-Daten")
        # Im Netz erreichbar – sonst fehlt der Warnsatz darunter, und
        # das Bild zeigte die zahmere von zwei Lagen.
        stelle = fenster.netz.findData("0.0.0.0")
        if stelle >= 0:
            fenster.netz.setCurrentIndex(stelle)
        fenster.protokoll.setPlainText(
            "systemweit: MAILBURG_ARCHIV=D:\\Firmenarchiv\n"
            "systemweit: MAILBURG_EINSTELLUNGEN=D:\\MailBurg-Daten\n"
            "am Dienst »MailBurgServer«: 7 Werte gesetzt, 0 unberührt\n"
            "Läuft der Dienst schon, muss er neu starten, damit er die "
            "neuen Werte liest."
        )
        fenster.auffrischen()
        fenster.show()
        _durchatmen(anwendung)

        # **Die Höhe kommt vom Inhalt, nicht vom Fenster.** Seit das
        # Fenster einen Rollbereich hat, meldet es als Wunschhöhe nur
        # noch, was ein Rollbereich eben braucht – und das Bild zeigte
        # die oberen vier Zeilen. Gefragt wird deshalb das Widget *im*
        # Rollbereich, das die ganze Liste trägt.
        innen = fenster.centralWidget()
        inhalt = innen.widget() if hasattr(innen, "widget") else innen
        hoehe = inhalt.sizeHint().height() + 24
        fenster.resize(BREITE, hoehe)
        _durchatmen(anwendung)
        return fenster


def _ablegen(fenster, name: str) -> None:
    BILDER.mkdir(parents=True, exist_ok=True)
    ziel = BILDER / f"{name}.png"
    fenster.grab().save(str(ziel))
    print(f"  {ziel.relative_to(WURZEL)}")


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from mailburg.ui import farben

    anwendung = QApplication.instance() or QApplication([])
    # Dieselben drei Zeilen wie beim Start des Fensters – sonst sähe das
    # Bild anders aus als das Programm.
    anwendung.setStyleSheet(farben.bereichsrahmen())
    farben.platzhalter_aufhellen(anwendung)
    farben.auswahlfelder_verbreitern(anwendung)

    print("Bilder:")
    for name, gut in (("einrichtung-server-gruen", True),
                      ("einrichtung-server-rot", False)):
        fenster = _fenster(anwendung, gut)
        _ablegen(fenster, name)
        fenster.close()

    print("\nFertig.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
