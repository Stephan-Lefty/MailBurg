"""Anmeldung per OAuth2 – für Anbieter, die kein Passwort mehr annehmen.

**Warum das sein muss.** Microsoft hat die einfache Anmeldung
abgeschaltet: Exchange Online am 1. Oktober 2022, private Konten
(outlook.com, hotmail.com, live.com) am 16. September 2024. Auch
App-Kennwörter wirken dort nicht mehr. Ohne OAuth2 kann MailBurg
Microsoft-Postfächer überhaupt nicht abrufen.

**Warum MailBurg keine eigenen Zugangsdaten mitbringt.** Für den vollen
IMAP-Zugriff verlangt Google den ``mail.google.com``-Scope, einen
»restricted scope«. Der setzt ein CASA-Sicherheitsaudit durch ein
zugelassenes Labor voraus, jährlich zu wiederholen, mit Kosten von
einigen hundert bis mehreren tausend Dollar. Für ein quelloffenes
Programm ohne Einnahmen ist das nicht tragbar.

Also registriert der Anwender seine eigene Anwendung und gibt MailBurg
deren Kennung mit. Bei Microsoft ist das kostenlos und ohne
Prüfverfahren. Die Anleitung dazu steht in ``docs/oauth2.md``.

**Öffentlicher Client mit PKCE, kein Geheimnis.** Ein Programm, das auf
fremden Rechnern läuft, kann kein Geheimnis bewahren – wer die Datei
hat, hat auch das Geheimnis. Beide Anbieter sehen für Desktop-Programme
deshalb den öffentlichen Client mit PKCE vor: Statt eines dauerhaften
Geheimnisses wird für jede Anmeldung ein neuer Zufallswert erzeugt und
sein Fingerabdruck vorab mitgeschickt.

**Was hier bewusst nicht steht:** der Browserteil. Wer das Fenster
öffnet und auf die Antwort wartet, ist Sache der Oberfläche; dieses
Modul rechnet nur und kennt kein Qt.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

#: Wie lange vor dem Ablauf ein Token erneuert wird.
#:
#: Nicht erst beim Ablauf: Zwischen »noch gültig« und dem Aufbau der
#: IMAP-Verbindung liegen Sekunden, und ein Abruf, der mitten im Lauf an
#: einem abgelaufenen Token scheitert, ist ärgerlicher als eine
#: Erneuerung, die eine Minute zu früh kam.
VORLAUF = 300


@dataclass(frozen=True)
class Anbieter:
    """Die Endpunkte eines Anbieters."""

    kennung: str
    name: str
    autorisierung: str
    token: str
    bereich: str
    """Der Scope – was die Anwendung darf."""

    hinweis: str = ""
    """Was der Anwender über die Registrierung wissen muss."""

    def fuer_mandanten(self, mandant: str) -> "Anbieter":
        """Dieselben Endpunkte, aber auf eine Organisation eingeschränkt.

        **Für Firmenkonten kann das nötig sein.** Microsoft erlaubt
        einer Organisation, den Zugriff auf ihren eigenen Mandanten zu
        beschränken; eine Anmeldung über ``common`` scheitert dann mit
        einer Meldung, die nach einem Fehler in der Anwendung aussieht.

        Am 2026-09-21 aufgefallen: Ein Kommentar versprach diesen Weg
        seit jeher, und es gab ihn nicht. Erst stand dort sogar das
        Gegenteil dessen, was der Code tat – siehe :data:`MICROSOFT`.

        Die Mandanten-ID steht im Azure-Portal bei der registrierten
        Anwendung (»Verzeichnis-ID«). Wer sie nicht kennt, braucht sie
        auch nicht: ``common`` ist die Vorgabe und deckt den Normalfall.
        """
        mandant = mandant.strip()
        if not mandant:
            return self
        if "/common/" not in self.autorisierung:
            raise ValueError(
                f"Für {self.name} gibt es keine Mandanten – die Angabe "
                f"passt nur zu Microsoft."
            )
        return Anbieter(
            kennung=self.kennung,
            name=f"{self.name}, Mandant {mandant}",
            autorisierung=self.autorisierung.replace(
                "/common/", f"/{mandant}/"),
            token=self.token.replace("/common/", f"/{mandant}/"),
            bereich=self.bereich,
            hinweis=self.hinweis,
        )


#: Microsoft: kostenlos registrierbar, kein Prüfverfahren.
#:
#: **``common``, und das mit Bedacht.** Hier stand bis zum 2026-09-21
#: ein Kommentar, der ``consumers`` behauptete – also nur private
#: Konten –, während der Code schon immer ``common`` nahm. Ein
#: Kommentar, der etwas anderes sagt als der Code, ist schlimmer als
#: keiner: Wer ihn liest, ändert im Zweifel den Code auf das, was
#: danebensteht.
#:
#: Richtig ist ``common``. Es nimmt private *und* geschäftliche Konten
#: an, und genau darauf kommt es an: Wer MailBurg in einer Firma
#: einsetzt, hat ein Exchange-Online-Konto – und seit Microsoft die
#: einfache Anmeldung für IMAP abgeschaltet hat, führt dorthin kein
#: anderer Weg mehr als OAuth2. Mit ``consumers`` liefe ausgerechnet
#: dieser Fall nicht.
#:
#: Wessen Organisation den Zugriff einschränkt, trägt statt ``common``
#: seine Mandanten-ID ein – das kann nur wissen, wer die Organisation
#: kennt. Der Weg dafür steht in ``docs/oauth2.md``.
MICROSOFT = Anbieter(
    kennung="microsoft",
    name="Microsoft (Outlook.com, Hotmail, Exchange)",
    autorisierung="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    token="https://login.microsoftonline.com/common/oauth2/v2.0/token",
    # offline_access liefert das Erneuerungs-Token. Ohne das müsste sich
    # der Anwender bei jedem Abruf neu anmelden - für einen Zeitplan im
    # Hintergrund undenkbar.
    bereich="https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
    hinweis=(
        "In Entra ID (früher Azure AD) eine Anwendung registrieren, Typ "
        "»Öffentlicher Client«, Umleitungsziel http://localhost. "
        "Kostenlos und ohne Prüfverfahren."
    ),
)

#: Google: technisch derselbe Ablauf, aber mit einer Hürde davor.
GOOGLE = Anbieter(
    kennung="google",
    name="Google (Gmail)",
    autorisierung="https://accounts.google.com/o/oauth2/v2/auth",
    token="https://oauth2.googleapis.com/token",
    bereich="https://mail.google.com/",
    hinweis=(
        "In der Google Cloud Console ein Projekt anlegen, OAuth-Zugangsdaten "
        "vom Typ »Desktop-App« erzeugen und sich selbst als Testnutzer "
        "eintragen. Achtung: Im Testmodus verfallen die Erneuerungs-Token "
        "nach sieben Tagen – für einen Zeitplan im Hintergrund ist das zu "
        "kurz. Bei Gmail funktionieren App-Passwörter weiterhin und sind "
        "vorerst der einfachere Weg."
    ),
)

ANBIETER = {a.kennung: a for a in (MICROSOFT, GOOGLE)}


@dataclass
class Token:
    """Was nach einer Anmeldung vorliegt."""

    zugriff: str
    erneuerung: str = ""
    gueltig_bis: float = 0.0
    """Zeitpunkt in Sekunden seit 1970, ab dem das Zugriffstoken abläuft."""

    def abgelaufen(self, jetzt: float | None = None) -> bool:
        """Ob es erneuert werden muss – mit Vorlauf."""
        return (jetzt or time.time()) + VORLAUF >= self.gueltig_bis

    def als_json(self) -> str:
        return json.dumps(
            {
                "zugriff": self.zugriff,
                "erneuerung": self.erneuerung,
                "gueltig_bis": self.gueltig_bis,
            }
        )

    @classmethod
    def aus_json(cls, roh: str) -> "Token | None":
        try:
            daten = json.loads(roh)
            return cls(
                zugriff=daten["zugriff"],
                erneuerung=daten.get("erneuerung", ""),
                gueltig_bis=float(daten.get("gueltig_bis", 0)),
            )
        except (ValueError, KeyError, TypeError):
            # Ein verhunzter Eintrag im Schlüsselbund darf das Programm
            # nicht aufhalten - dann eben neu anmelden.
            return None


class OAuthFehler(RuntimeError):
    """Etwas beim Anmelden oder Erneuern ist schiefgegangen."""


@dataclass
class Pruefer:
    """Das Zufallspaar für PKCE.

    Der ``verifizierer`` bleibt geheim und geht erst mit dem Tausch an
    den Anbieter; vorab bekommt der nur seinen Fingerabdruck. Fängt
    jemand die Umleitung ab, nützt ihm der Code nichts – ihm fehlt das
    Geheimnis, das nur dieser eine Anmeldevorgang kennt.
    """

    verifizierer: str = field(
        default_factory=lambda: secrets.token_urlsafe(64)[:128]
    )

    @property
    def fingerabdruck(self) -> str:
        roh = hashlib.sha256(self.verifizierer.encode("ascii")).digest()
        return base64.urlsafe_b64encode(roh).decode("ascii").rstrip("=")


def anmeldeadresse(anbieter: Anbieter, kennung: str, ziel: str,
                   pruefer: Pruefer, zustand: str) -> str:
    """Baut die Adresse, die im Browser geöffnet wird."""
    felder = {
        "client_id": kennung,
        "response_type": "code",
        "redirect_uri": ziel,
        "scope": anbieter.bereich,
        "code_challenge": pruefer.fingerabdruck,
        "code_challenge_method": "S256",
        "state": zustand,
    }
    if anbieter.kennung == "google":
        # Ohne das gibt Google beim zweiten Mal kein Erneuerungs-Token
        # mehr heraus - und der Zeitplan stünde nach einer Stunde still.
        felder["access_type"] = "offline"
        felder["prompt"] = "consent"
    return f"{anbieter.autorisierung}?{urllib.parse.urlencode(felder)}"


def _tauschen(anbieter: Anbieter, felder: dict) -> Token:
    """Schickt die Felder an den Token-Endpunkt und liest die Antwort."""
    anfrage = urllib.request.Request(
        anbieter.token,
        data=urllib.parse.urlencode(felder).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=30) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        roh = exc.read().decode("utf-8", "replace")
        raise OAuthFehler(_verstaendlich(roh, exc.code)) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise OAuthFehler(
            f"Der Anmeldedienst von {anbieter.name} ist nicht erreichbar: {exc}"
        ) from exc

    if "access_token" not in daten:
        raise OAuthFehler(_verstaendlich(json.dumps(daten), 0))

    return Token(
        zugriff=daten["access_token"],
        erneuerung=daten.get("refresh_token", ""),
        gueltig_bis=time.time() + float(daten.get("expires_in", 3600)),
    )


def _verstaendlich(roh: str, code: int) -> str:
    """Übersetzt die Fehlerkennungen der Anbieter in ganze Sätze.

    ``invalid_grant`` ist die häufigste und die unverständlichste: Sie
    heißt fast immer, dass das Erneuerungs-Token nicht mehr gilt – weil
    das Passwort geändert wurde, weil der Zugriff entzogen wurde, oder
    weil bei Google die sieben Tage des Testmodus um sind.
    """
    klein = roh.lower()
    if "invalid_grant" in klein:
        return (
            "Die gespeicherte Anmeldung gilt nicht mehr. Das passiert, wenn "
            "das Kontopasswort geändert oder der Zugriff entzogen wurde – "
            "bei Google im Testmodus außerdem nach sieben Tagen. Melden Sie "
            "das Postfach neu an."
        )
    if "invalid_client" in klein:
        return (
            "Die Anwendungskennung wird nicht anerkannt. Prüfen Sie sie in "
            "der Registrierung beim Anbieter – und ob die Anwendung als "
            "»öffentlicher Client« angelegt ist."
        )
    if "redirect_uri_mismatch" in klein or "invalid_redirect" in klein:
        return (
            "Das Umleitungsziel stimmt nicht mit dem überein, das bei der "
            "Registrierung hinterlegt wurde. Dort muss http://localhost "
            "eingetragen sein."
        )
    if "invalid_scope" in klein:
        return (
            "Der angeforderte Zugriff wurde nicht bewilligt. Bei Google "
            "verlangt der volle IMAP-Zugriff eine Überprüfung der Anwendung."
        )
    if "consent_required" in klein or "interaction_required" in klein:
        return "Der Anbieter verlangt eine erneute Anmeldung von Hand."
    return f"Der Anmeldedienst antwortete mit einem Fehler ({code}): {roh[:300]}"


def einloesen(anbieter: Anbieter, kennung: str, code: str, ziel: str,
              pruefer: Pruefer) -> Token:
    """Tauscht den Autorisierungscode gegen Token ein."""
    return _tauschen(anbieter, {
        "client_id": kennung,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": ziel,
        "code_verifier": pruefer.verifizierer,
    })


def erneuern(anbieter: Anbieter, kennung: str, token: Token) -> Token:
    """Holt ein frisches Zugriffstoken.

    Gibt der Anbieter kein neues Erneuerungs-Token heraus – Microsoft tut
    das meistens, Google nicht –, bleibt das alte gültig und wird
    weitergereicht. Ginge es dabei verloren, müsste sich der Anwender
    nach einer Stunde neu anmelden.
    """
    if not token.erneuerung:
        raise OAuthFehler(
            "Für dieses Postfach ist keine Erneuerung hinterlegt. Melden "
            "Sie es neu an."
        )
    neu = _tauschen(anbieter, {
        "client_id": kennung,
        "grant_type": "refresh_token",
        "refresh_token": token.erneuerung,
    })
    if not neu.erneuerung:
        neu.erneuerung = token.erneuerung
    return neu


def xoauth2_zeichenkette(benutzer: str, zugriff: str) -> str:
    """Der Anmeldesatz, den IMAP für ``AUTHENTICATE XOAUTH2`` erwartet.

    Das Format steht so in Googles und Microsofts Beschreibung: die
    Steuerzeichen ``\\x01`` gehören dazu, sie sind keine Zierde.
    """
    return f"user={benutzer}\x01auth=Bearer {zugriff}\x01\x01"
