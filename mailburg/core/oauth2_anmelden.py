"""Der interaktive Teil der OAuth2-Anmeldung.

Der Anwender meldet sich im Browser bei seinem Anbieter an. Der leitet
danach auf ``http://localhost`` um und hängt den Autorisierungscode an
die Adresse. MailBurg lauscht dort einen Augenblick lang, nimmt den Code
entgegen und tauscht ihn gegen Token ein.

**Warum ein eigener Kurzzeit-Server und keine Copy-Paste-Lösung.** Man
könnte den Anwender bitten, den Code aus der Adresszeile
herauszukopieren. Das funktioniert – aber es funktioniert auch dann,
wenn er versehentlich etwas anderes kopiert, und dann steht eine
Fehlermeldung da, die niemand deuten kann. Der Umweg über localhost ist
das, was beide Anbieter für Desktop-Programme vorsehen.

**Nur auf dem eigenen Rechner.** Gelauscht wird ausschließlich auf
``127.0.0.1``, nie auf allen Adressen. Der Server nimmt genau eine
Anfrage an und verschwindet danach. Und der ``state``-Wert wird
geprüft: Wer von außen eine Anfrage einschleusen wollte, müsste den
Zufallswert kennen, der nur in diesem einen Vorgang existiert.
"""

from __future__ import annotations

import http.server
import secrets
import socket
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass

from mailburg.core.oauth2 import (
    Anbieter,
    OAuthFehler,
    Pruefer,
    Token,
    anmeldeadresse,
    einloesen,
)

#: Wie lange auf die Rückkehr aus dem Browser gewartet wird.
#:
#: Fünf Minuten: Wer sich anmeldet, muss vielleicht erst sein Passwort
#: suchen, eine Zwei-Faktor-Abfrage beantworten und die Berechtigungen
#: durchlesen. Weniger wäre knapp; mehr hieße, dass ein vergessenes
#: Fenster den Rechner ewig blockiert.
WARTEZEIT = 300

#: Was der Browser nach dem Umleiten anzeigt.
_SEITE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<title>MailBurg</title>
<style>
 body {{ font-family: system-ui, sans-serif; max-width: 34em;
        margin: 4em auto; padding: 0 1em; line-height: 1.5; }}
 h1 {{ font-size: 1.4em; }}
 .gut {{ color: #1a7f37; }} .schlecht {{ color: #b3261e; }}
</style></head><body>
<h1 class="{art}">{titel}</h1>
<p>{text}</p>
<p><small>Dieses Fenster können Sie schließen.</small></p>
</body></html>"""


@dataclass
class _Ergebnis:
    code: str = ""
    fehler: str = ""


class _Empfaenger(http.server.BaseHTTPRequestHandler):
    """Nimmt die Umleitung des Anbieters entgegen."""

    ergebnis: _Ergebnis
    erwarteter_zustand: str

    def do_GET(self) -> None:  # noqa: N802 – von der Basisklasse vorgegeben
        felder = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query
        )
        zustand = felder.get("state", [""])[0]

        if zustand != self.erwarteter_zustand:
            # Kein Fehler des Anwenders, sondern ein Hinweis darauf, dass
            # die Antwort nicht zu dieser Anmeldung gehört.
            self.ergebnis.fehler = (
                "Die Antwort des Anbieters gehört nicht zu dieser Anmeldung."
            )
            self._antworten(
                "Abgelehnt", "Die Antwort passt nicht zu dieser Anmeldung.",
                "schlecht",
            )
            return

        if "error" in felder:
            beschreibung = felder.get("error_description", [""])[0]
            self.ergebnis.fehler = beschreibung or felder["error"][0]
            self._antworten(
                "Nicht angemeldet", self.ergebnis.fehler, "schlecht"
            )
            return

        self.ergebnis.code = felder.get("code", [""])[0]
        if not self.ergebnis.code:
            self.ergebnis.fehler = "Der Anbieter hat keinen Code geschickt."
            self._antworten(
                "Nicht angemeldet", self.ergebnis.fehler, "schlecht"
            )
            return

        self._antworten(
            "Angemeldet",
            "MailBurg kann dieses Postfach jetzt abrufen. Die Anmeldung "
            "liegt im Schlüsselbund Ihres Systems, nicht in einer Datei.",
            "gut",
        )

    def _antworten(self, titel: str, text: str, art: str) -> None:
        seite = _SEITE.format(titel=titel, text=text, art=art).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(seite)))
        self.end_headers()
        self.wfile.write(seite)

    def log_message(self, *_args) -> None:
        """Kein Protokoll auf der Konsole – das gehört hier niemandem."""


def freier_anschluss() -> int:
    """Sucht einen freien Anschluss auf dem eigenen Rechner.

    Kein fester: Auf einem Rechner läuft manchmal schon etwas auf dem
    naheliegenden Anschluss, und dann scheiterte die Anmeldung mit einer
    Meldung, die den Grund nicht nennt.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as buchse:
        buchse.bind(("127.0.0.1", 0))
        return buchse.getsockname()[1]


def anmelden(anbieter: Anbieter, kennung: str, *,
             oeffnen=webbrowser.open, wartezeit: int = WARTEZEIT) -> Token:
    """Führt die Anmeldung durch und gibt die Token zurück.

    ``oeffnen`` ist herausgezogen, damit die Tests keinen Browser
    starten – und damit eine Oberfläche stattdessen ihr eigenes Fenster
    aufmachen kann.
    """
    anschluss = freier_anschluss()
    ziel = f"http://localhost:{anschluss}"
    pruefer = Pruefer()
    zustand = secrets.token_urlsafe(24)
    ergebnis = _Ergebnis()

    klasse = type(
        "_GebundenerEmpfaenger",
        (_Empfaenger,),
        {"ergebnis": ergebnis, "erwarteter_zustand": zustand},
    )
    server = http.server.HTTPServer(("127.0.0.1", anschluss), klasse)
    server.timeout = wartezeit

    faden = threading.Thread(target=server.handle_request, daemon=True)
    faden.start()

    try:
        oeffnen(anmeldeadresse(anbieter, kennung, ziel, pruefer, zustand))
        faden.join(wartezeit)
    finally:
        server.server_close()

    if faden.is_alive():
        raise OAuthFehler(
            f"Innerhalb von {wartezeit // 60} Minuten kam keine Antwort aus "
            f"dem Browser. Wurde das Fenster geschlossen?"
        )
    if ergebnis.fehler:
        raise OAuthFehler(ergebnis.fehler)
    if not ergebnis.code:
        raise OAuthFehler("Die Anmeldung wurde abgebrochen.")

    return einloesen(anbieter, kennung, ergebnis.code, ziel, pruefer)
