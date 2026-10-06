#!/usr/bin/env python3
"""Erzeugt die Bilder der Weboberfläche – aus erfundener Post.

    python werkzeuge/screenshots_server.py

Das Gegenstück zu ``screenshots.py``, das die Fenster der blauen
Fassung abbildet. Hier geht es um die rote: das Archiv im Browser, wie
es die Mitarbeiter einer Firma sehen.

**Warum ein eigenes Skript und nicht ein paar Zeilen mehr im anderen.**
Die Weboberfläche lässt sich nicht aufrufen wie ein Fenster. Es braucht
einen laufenden Webserver, eine Anmeldung mit Sitzungsmerkmal und einen
Browser, der die Seite tatsächlich setzt – drei Dinge mit eigenem
Lebenslauf. Dazu kommt, dass QtWebEngine seine Chromium-Umgebung vor
der ersten ``QApplication`` einrichten will; in einem Prozess, der
schon Fenster gezeichnet hat, ist das heikel.

**Warum QtWebEngine und nicht Playwright.** Playwright wäre der
übliche Weg, zöge aber eine Fremdabhängigkeit und einen eigenen
Browser-Download nach sich, nur um Bilder für eine Anleitung zu machen.
QtWebEngine liegt mit PySide6 ohnehin bereit – demselben Qt, mit dem
die blaue Fassung gebaut ist.

Die Bilder entstehen ohne Bildschirm (``QT_QPA_PLATFORM=offscreen``),
laufen also auch dort, wo niemand zusieht.

**Erfundene Post, wie drüben.** Das Archiv kommt aus
``screenshots.beispielarchiv`` – dieselbe Martha Muster, dieselben
``.example``-Absender. Ein Bilderwerkzeug, das die echten Postfächer
seines Erzeugers abbildet, hat dieses Projekt schon einmal gehabt; der
Kommentar bei ``_kontenbild`` in ``screenshots.py`` erzählt davon.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

# **Vor jedem Qt-Import.** Danach gelesen zu werden nützt nichts.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Ohne Grafikkarte muss Chromium in Software zeichnen. Ohne diese
# Fahnen bleibt das Bild weiß, und zwar ohne Fehlermeldung.
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--disable-gpu --disable-software-rasterizer --no-sandbox "
    "--disable-dev-shm-usage --in-process-gpu",
)

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
BILDER = WURZEL / "docs" / "bilder"

#: Der Zugang, mit dem die Bilder entstehen. Eine Sachbearbeiterin, die
#: zwei Postfächer sehen darf – nicht der Verwalter, denn die Bilder
#: sollen zeigen, was die Mitarbeiter sehen.
ANMELDENAME = "m.muster"
ANZEIGENAME = "Martha Muster"
PASSWORT = "nur-fuer-die-anleitung"

#: Breite und Höhe des gezeigten Browserfensters. Breiter als ein
#: Fensterbild, weil die Weboberfläche eine Postfachspalte hat und bei
#: schmalem Fenster auf das Handy-Layout umschaltet (``55rem``).
BREITE, HOEHE = 1280, 860

#: Wie lange auf eine Seite gewartet wird, bevor abgebrochen wird.
GEDULD = 20


def _serverlage(archiv: Path, anschluss: int):
    from mailburg.server.einstellungen import Serverlage

    return Serverlage(archiv=archiv, adresse="127.0.0.1", anschluss=anschluss)


def _freier_anschluss() -> int:
    """Einen Anschluss vom Betriebssystem geben lassen.

    Nicht 8383 fest verdrahten: Auf dem Rechner, der die Bilder macht,
    kann ein echter MailBurg-Server laufen. Dann knipste dieses Skript
    dessen Archiv – mit echter Post darauf.
    """
    import socket

    with socket.socket() as dose:
        dose.bind(("127.0.0.1", 0))
        return dose.getsockname()[1]


def _zugang_anlegen(archiv: Path) -> None:
    """Legt den Zugang an, mit dem die Bilder entstehen."""
    from mailburg.core.benutzer import Benutzer, Benutzerliste

    liste = Benutzerliste.lesen(archiv)
    eintrag = Benutzer(
        name=ANMELDENAME,
        anzeigename=ANZEIGENAME,
        # **Nicht alle Postfächer.** Die Bilder sollen die Spalte links
        # mit zwei Einträgen zeigen, nicht mit allen – so sieht man,
        # dass Rechte etwas bewirken.
        postfaecher=["martha@mailburg.example", "buero@mailburg.example"],
    )
    eintrag.passwort_setzen(PASSWORT)
    liste.hinzufuegen(eintrag)
    liste.schreiben(archiv)


class Webserver:
    """Der Dienst im Hintergrund, solange die Bilder entstehen."""

    def __init__(self, archiv: Path):
        self.anschluss = _freier_anschluss()
        self.archiv = archiv
        self._server = None
        self._faden = None

    @property
    def adresse(self) -> str:
        return f"http://127.0.0.1:{self.anschluss}"

    def __enter__(self) -> Webserver:
        import uvicorn

        from mailburg.server.dienst import anwendung

        einstellungen = uvicorn.Config(
            anwendung(_serverlage(self.archiv, self.anschluss)),
            host="127.0.0.1",
            port=self.anschluss,
            access_log=False,
            log_level="warning",
        )
        self._server = uvicorn.Server(einstellungen)
        self._faden = threading.Thread(target=self._server.run, daemon=True)
        self._faden.start()

        # **Auf das Hochkommen warten, nicht schlafen.** Ein fester
        # Wert wäre auf einem langsamen Rechner zu kurz und sonst zu
        # lang; beides fällt erst auf, wenn die Bilder leer sind.
        frist = time.monotonic() + GEDULD
        while time.monotonic() < frist:
            if getattr(self._server, "started", False):
                return self
            time.sleep(0.05)
        raise RuntimeError("Der Webserver kam nicht hoch.")

    def __exit__(self, *_) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._faden is not None:
            self._faden.join(timeout=GEDULD)


class Knipser:
    """Ein Browser ohne Bildschirm, der Seiten als Bild ablegt."""

    def __init__(self, adresse: str):
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWidgets import QApplication

        self.adresse = adresse
        self.anwendung = QApplication.instance() or QApplication([])
        self.blick = QWebEngineView()
        self.blick.resize(BREITE, HOEHE)
        self.blick.show()

    def _warten(self, bedingung, was: str) -> None:
        """Dreht Qts Schleife, bis die Bedingung eintritt."""
        frist = time.monotonic() + GEDULD
        while time.monotonic() < frist:
            self.anwendung.processEvents()
            if bedingung():
                return
            time.sleep(0.02)
        raise RuntimeError(f"Zeit abgelaufen: {was}")

    def oeffnen(self, pfad: str) -> None:
        from PySide6.QtCore import QUrl

        fertig = []
        verbindung = self.blick.loadFinished.connect(fertig.append)
        self.blick.load(QUrl(self.adresse + pfad))
        try:
            self._warten(lambda: bool(fertig), f"laden von {pfad}")
        finally:
            self.blick.loadFinished.disconnect(verbindung)
        if not fertig[0]:
            raise RuntimeError(f"Die Seite {pfad} ließ sich nicht laden.")
        self._beruhigen()

    def _beruhigen(self) -> None:
        """Dem Zeichnen Zeit lassen, bevor das Bild entsteht.

        ``loadFinished`` meldet, dass das HTML da ist – nicht, dass es
        gesetzt und gezeichnet wurde. Ohne diese Pause entstehen
        halbfertige Bilder, und zwar unzuverlässig: mal gut, mal weiß.
        """
        frist = time.monotonic() + 1.2
        while time.monotonic() < frist:
            self.anwendung.processEvents()
            time.sleep(0.02)

    def ausfuehren(self, js: str):
        """Führt JavaScript aus und wartet auf das Ergebnis."""
        antwort = []
        self.blick.page().runJavaScript(js, antwort.append)
        self._warten(lambda: bool(antwort), f"JavaScript: {js[:40]}")
        return antwort[0]

    def anmelden(self, name: str, passwort: str) -> None:
        self.oeffnen("/")
        self.ausfuehren(
            f"document.querySelector('input[name=name]').value = {name!r};"
            f"document.querySelector('input[name=passwort]').value"
            f" = {passwort!r};"
            "document.querySelector('form.anmeldung').submit();"
        )
        # Nach dem Absenden kommt eine neue Seite; auf sie warten.
        self._warten(
            lambda: "Anmelden" not in (self.ausfuehren(
                "document.querySelector('h1') "
                "? document.querySelector('h1').textContent : ''"
            ) or ""),
            "Anmeldung",
        )
        self._beruhigen()

    def thema(self, wahl: str) -> None:
        """Stellt Hell oder Dunkel ein – über denselben Weg wie der Mensch.

        ``/thema`` setzt einen Keks und leitet weiter; genau das macht
        auch der Umschalter oben rechts. Über den eigenen Weg zu gehen
        statt den Keks zu setzen hat einen Grund: Stimmt an der Route
        etwas nicht, fällt es hier auf und nicht erst im Betrieb.
        """
        self.oeffnen(f"/thema?wahl={wahl}&weiter=%2F")

    def ablegen(self, name: str) -> None:
        """Legt die Seite als Bild ab – auf Inhaltshöhe zugeschnitten.

        **Zwei Eingriffe, beide für die Anleitung und nicht fürs Auge.**

        Der Fokusrahmen fällt weg. Die Suchfelder tragen ``autofocus``,
        und den Rahmen dazu zeichnet jeder Browser anders – Chromium
        orange, Firefox blau. Auf einem Bild in der Anleitung sieht das
        aus wie eine Markierung, die etwas bedeutet. Sie bedeutet nur,
        dass die Seite gerade geladen wurde.

        Die Höhe richtet sich nach dem Inhalt. Eine Trefferliste mit
        drei Zeilen in einem Fenster von 860 Pixeln steht in einem Meer
        aus Weiß, und auf einer Repo-Seite schrumpft das Bild dadurch so
        weit, dass die Schrift nicht mehr lesbar ist.
        """
        self.ausfuehren(
            "if (document.activeElement) document.activeElement.blur();"
        )
        # **``body`` fragen, nicht ``documentElement``.** Dessen
        # ``scrollHeight`` ist bei kurzen Seiten die Fensterhöhe, nicht
        # die des Inhalts – gemessen am 2026-10-02: 860 für eine Seite,
        # deren Inhalt 565 Pixel hoch war. Die Zuschnitte wirkten
        # deshalb beim ersten Lauf gar nicht, ohne dass etwas schieflief.
        hoehe = self.ausfuehren(
            "Math.ceil(document.body.getBoundingClientRect().height)"
        )
        if isinstance(hoehe, (int, float)) and hoehe > 0:
            # Ein Rand unten, damit die Fußzeile nicht am Bildrand klebt.
            # Nach unten begrenzt, damit ein leerer Bereich nicht zu
            # einem Streifen wird; nach oben, damit die Hilfeseite ein
            # Bild bleibt und keine Tapete.
            gewuenscht = max(360, min(int(hoehe) + 24, 1600))
            self.blick.resize(BREITE, gewuenscht)
            self._beruhigen()

        BILDER.mkdir(parents=True, exist_ok=True)
        ziel = BILDER / f"{name}.png"
        self.blick.grab().save(str(ziel))
        print(f"  {ziel.relative_to(WURZEL)}")

        # Für die nächste Seite wieder die volle Höhe: Sonst erbte eine
        # lange Seite die Höhe der kurzen davor und bekäme einen
        # Rollbalken statt ihres Inhalts.
        self.blick.resize(BREITE, HOEHE)


def main() -> int:
    import screenshots

    zwischen = Path(tempfile.mkdtemp(prefix="mailburg-webbilder-"))

    # **Einstellungen und Daten umlenken, bevor etwas entsteht.**
    # Derselbe Grund wie in ``screenshots.py``: Ein Werkzeug, das Bilder
    # macht, darf am Rechner nichts ändern. Hier wiegt es schwerer, weil
    # der Suchindex entsteht – der läge sonst beim echten Anwender.
    from unittest import mock

    from mailburg.core import paths

    einstellungen = zwischen / "einstellungen"
    daten = zwischen / "daten"
    einstellungen.mkdir(parents=True)
    daten.mkdir(parents=True)
    umlenkung = [
        mock.patch.object(paths, "config_dir", return_value=einstellungen),
        mock.patch.object(paths, "data_dir", return_value=daten),
        mock.patch.object(paths, "index_path",
                          return_value=daten / "suchindex"),
    ]
    for patch in umlenkung:
        patch.start()

    try:
        ort = zwischen / "Geschaeftsarchiv"
        print("Lege das Vorführarchiv an …")
        archiv = screenshots.beispielarchiv(ort)
        # **Der Index muss stehen, bevor der Server startet.** Sonst
        # findet die Suche nichts, und die Trefferliste – das wichtigste
        # Bild – bliebe leer. Genau der Fehler, der am 2026-10-02 auf
        # dem echten Server zwei Stunden gekostet hat.
        archiv.rebuild_index()
        archiv.close()

        _zugang_anlegen(ort)

        print(f"Starte den Dienst …")
        with Webserver(ort) as server:
            knipser = Knipser(server.adresse)

            print("Bilder:")
            knipser.oeffnen("/")
            knipser.ablegen("server-anmelden")

            knipser.anmelden(ANMELDENAME, PASSWORT)
            knipser.ablegen("server-uebersicht")

            knipser.oeffnen("/?q=rechnung")
            knipser.ablegen("server-trefferliste")

            # **Einmal mit offener Postfachspalte.** Zugeschoben ist
            # seit der 1.8.0 die Vorgabe – damit sieht man auf dem Bild
            # oben die Spalte gar nicht mehr, und niemand käme auf die
            # Idee, dass es sie gibt.
            knipser.oeffnen("/postfaecher?wahl=auf&weiter=%2F%3Fq%3Drechnung")
            knipser.ablegen("server-postfaecher")
            knipser.oeffnen("/postfaecher?wahl=zu&weiter=%2F%3Fq%3Drechnung")

            # Die erste Nachricht öffnen – welche das ist, steht nicht
            # fest, deshalb über den ersten Treffer gehen.
            ziel = knipser.ausfuehren(
                "(function(){var a=document.querySelector('ol.treffer a');"
                "return a ? a.getAttribute('href') : '';})()"
            )
            if ziel:
                knipser.oeffnen(ziel)
                knipser.ablegen("server-lesen")
            else:
                print("  (keine Treffer – Lesebild übersprungen)")

            knipser.oeffnen("/hilfe")
            knipser.ablegen("server-hilfe")

            knipser.oeffnen("/einstellungen")
            knipser.ablegen("server-einstellungen")

            knipser.thema("dunkel")
            knipser.oeffnen("/?q=rechnung")
            knipser.ablegen("server-dunkel")

        print("\nFertig.")
        return screenshots._nachsehen()
    finally:
        for patch in umlenkung:
            patch.stop()
        import shutil

        shutil.rmtree(zwischen, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
