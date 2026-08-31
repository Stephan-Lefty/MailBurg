"""Zeitstempel nach RFC 3161 – ein Datum von dritter Seite.

**Was die Hash-Kette nicht kann.** Sie beweist die *Reihenfolge* der
Einträge: Wer einen davon nachträglich ändert, zerreißt sie sichtbar.
Über den *Zeitpunkt* sagt sie nichts. Die Uhrzeit in einem Eintrag
stammt vom eigenen Rechner, und die lässt sich stellen – ein Archiv,
das sich selbst bescheinigt, wann es entstand, bescheinigt gar nichts.

Ein Zeitstempeldienst schließt diese Lücke. Er bekommt einen Hash,
schreibt seine Uhrzeit dazu, signiert beides und gibt es zurück. Damit
steht fest: Dieser Stand lag zu diesem Zeitpunkt bereits so vor.

**Was dabei übertragen wird, und was nicht.** Übertragen wird ein
SHA-256 – 32 Byte, das Ergebnis des letzten Journaleintrags. Aus ihm
lässt sich nichts zurückrechnen: keine Mail, keine Adresse, kein
Betreff, nicht einmal die Zahl der Nachrichten. Der Dienst erfährt, dass
jemand um 14:03 Uhr *etwas* gestempelt hat, und sonst nichts.

**Und trotzdem ist es eine Verbindung nach außen.** MailBurg
verspricht, sich nur mit den Mailservern zu verbinden, die man selbst
eingetragen hat. Deshalb ist der Zeitstempel **ausdrücklich
einzuschalten** und nirgends voreingestellt. Ein Programm, das dieses
Versprechen stillschweigend aufweicht, hat es nie gemeint.

**Was MailBurg prüft und was nicht.** Es prüft, dass der Stempel zu
diesem Siegel gehört – der Hash darin muss der gestempelte sein – und
liest die beglaubigte Zeit heraus. Es prüft **nicht** die Signatur des
Dienstes gegen dessen Zertifikatskette; dafür bräuchte es einen
vollständigen CMS-Prüfer. Der Weg dafür steht in der Anleitung und
führt über ``openssl ts -verify``.

Das ist ehrlicher, als eine Prüfung vorzutäuschen, die keine ist: Wer
den Zeitstempel vor Gericht braucht, prüft ihn ohnehin mit
Standardwerkzeugen und nicht mit dem Programm, dessen Archiv er belegen
soll.
"""

from __future__ import annotations

import hashlib
import os
import urllib.error
import urllib.request
from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime, timezone

from mailburg.core import der

#: SHA-256 als Objektbezeichner.
OID_SHA256 = "2.16.840.1.101.3.4.2.1"

#: Was ein Zeitstempeldienst als Anfrage und Antwort erwartet.
TYP_ANFRAGE = "application/timestamp-query"
TYP_ANTWORT = "application/timestamp-reply"

#: Wie lange auf den Dienst gewartet wird. Ein Siegel ist kein Vorgang,
#: bei dem jemand zusieht – aber eine Minute Hängen ohne Rückmeldung
#: sieht aus wie ein Absturz.
ZEITGRENZE = 20

#: Vorgeschlagene Dienste. Keiner davon ist voreingestellt.
#:
#: **Beide sind kostenlos, und das hat Folgen für den Beweiswert.**
#: Sie stempeln zuverlässig, aber niemand haftet dafür, dass sie es in
#: zehn Jahren noch tun oder dass ihre Zertifikate dann noch prüfbar
#: sind. Wer den Stempel wirklich vor Gericht braucht, nimmt einen
#: qualifizierten Vertrauensdiensteanbieter nach eIDAS – der kostet,
#: dafür steht seine Zeitangabe der einer Behörde gleich.
DIENSTE = {
    "freetsa": "https://freetsa.org/tsr",
    "dfn": "https://zeitstempel.dfn.de",
}


class ZeitstempelFehler(RuntimeError):
    """Der Stempel kam nicht zustande oder taugt nicht."""


# ------------------------------------------------------------- Die Anfrage


def anfrage(digest: bytes, nonce: int | None = None) -> tuple[bytes, int]:
    """Baut eine ``TimeStampReq`` und gibt sie mit ihrer Nonce zurück.

    **Die Nonce ist keine Förmlichkeit.** Ohne sie ließe sich eine
    einmal erhaltene Antwort später erneut vorlegen – ein Stempel von
    gestern für ein Siegel von heute. Mit ihr muss die Antwort dieselbe
    Zufallszahl tragen, die in die Anfrage ging.
    """
    if len(digest) != 32:
        raise ZeitstempelFehler(
            f"Gestempelt wird ein SHA-256, dieser Wert hat {len(digest)} Byte."
        )
    if nonce is None:
        nonce = int.from_bytes(os.urandom(8), "big")

    roh = der.folge(
        der.ganzzahl(1),
        der.folge(
            der.folge(der.oid(OID_SHA256), der.leer()),
            der.oktette(digest),
        ),
        der.ganzzahl(nonce),
        # certReq: Das Zertifikat des Dienstes soll mitkommen. Sonst
        # ließe sich der Stempel später nur prüfen, wenn man es sich
        # anderswo besorgt - und in zehn Jahren steht es womöglich
        # nirgends mehr.
        der.wert(0x01, b"\xff"),
    )
    return roh, nonce


def _status_lesen(antwort: bytes) -> None:
    """Wirft, wenn der Dienst den Stempel verweigert hat."""
    aeusseres = der.lesen(antwort)
    teile = aeusseres.teile()
    if not teile:
        raise ZeitstempelFehler("Die Antwort des Dienstes ist leer.")

    status = teile[0].teile()[0].als_zahl()
    if status in (0, 1):  # granted, grantedWithMods
        return

    # Was schiefging, steht als Text daneben - wenn der Dienst ihn
    # mitschickt. Er gehört in die Meldung: »Status 2« hilft niemandem.
    erklaerung = ""
    for element in teile[0].teile()[1:]:
        if element.ist_folge:
            for text in element.teile():
                if text.kennung == der.UTF8STRING:
                    erklaerung = text.inhalt.decode("utf-8", "replace")
                    break
    grund = f": {erklaerung}" if erklaerung else ""
    raise ZeitstempelFehler(
        f"Der Zeitstempeldienst hat abgelehnt (Status {status}){grund}"
    )


def _token(antwort: bytes) -> bytes:
    """Der ``TimeStampToken`` aus der Antwort – roh, wie er kam."""
    teile = der.lesen(antwort).teile()
    if len(teile) < 2:
        raise ZeitstempelFehler(
            "Die Antwort enthält keinen Stempel, obwohl sie ihn zusagt."
        )
    # Wieder in DER ausgeben, denn gespeichert wird das Token als
    # eigenständige Struktur - genau so, wie openssl es erwartet.
    return der.wert(teile[1].kennung, teile[1].inhalt)


# ------------------------------------------------------------- Das Ergebnis


@dataclass(frozen=True)
class Stempel:
    """Ein Zeitstempel, wie er im Journal landet."""

    token: str
    """Das Token, base64-kodiert."""

    zeit: datetime | None
    """Die beglaubigte Zeit, sofern lesbar."""

    dienst: str
    """Die Adresse, die ihn ausgestellt hat."""

    @property
    def rohdaten(self) -> bytes:
        return b64decode(self.token)


def holen(digest: bytes, url: str, *, zeitgrenze: int = ZEITGRENZE) -> Stempel:
    """Holt einen Zeitstempel für einen Hash.

    Wirft :class:`ZeitstempelFehler`, wenn der Dienst nicht erreichbar
    ist, ablehnt oder etwas zurückgibt, das nicht zur Anfrage passt.
    """
    roh, nonce = anfrage(digest)

    bitte = urllib.request.Request(
        url,
        data=roh,
        headers={
            "Content-Type": TYP_ANFRAGE,
            # Ohne Kennung weisen manche Dienste ab. Sie nennt das
            # Programm, nicht den Rechner oder den Benutzer.
            "User-Agent": "MailBurg",
        },
    )
    try:
        with urllib.request.urlopen(bitte, timeout=zeitgrenze) as antwort:
            rohantwort = antwort.read()
    except urllib.error.HTTPError as fehler:
        raise ZeitstempelFehler(
            f"Der Dienst {url} antwortete mit {fehler.code} {fehler.reason}."
        ) from fehler
    except (urllib.error.URLError, OSError) as fehler:
        raise ZeitstempelFehler(
            f"Der Dienst {url} war nicht erreichbar: {fehler}\n\n"
            f"Das Siegel selbst ist davon nicht betroffen – es lässt sich "
            f"ohne Stempel setzen und später nicht nachträglich stempeln. "
            f"Wer den Stempel braucht, versucht es erneut, sobald wieder "
            f"eine Verbindung besteht."
        ) from fehler

    try:
        _status_lesen(rohantwort)
        token = _token(rohantwort)
    except der.DerFehler as fehler:
        raise ZeitstempelFehler(
            f"Die Antwort von {url} ist kein Zeitstempel: {fehler}"
        ) from fehler

    geprueft = pruefen(token, digest)
    if geprueft.nonce is not None and geprueft.nonce != nonce:
        raise ZeitstempelFehler(
            "Der Stempel gehört zu einer anderen Anfrage. Entweder ist "
            "etwas auf dem Weg vertauscht worden, oder jemand hat eine "
            "alte Antwort erneut vorgelegt."
        )
    if not geprueft.passt:
        raise ZeitstempelFehler(
            "Der Stempel bezieht sich auf einen anderen Stand als den "
            "angefragten. Er wäre wertlos und wird nicht abgelegt."
        )

    return Stempel(
        token=b64encode(token).decode("ascii"),
        zeit=geprueft.zeit,
        dienst=url,
    )


# ------------------------------------------------------------- Das Prüfen


@dataclass(frozen=True)
class Befund:
    """Was sich einem Token ohne Zertifikatskette entnehmen lässt."""

    passt: bool
    """Ob der gestempelte Hash der erwartete ist."""

    zeit: datetime | None
    nonce: int | None
    hinweis: str = ""

    @property
    def ok(self) -> bool:
        return self.passt and self.zeit is not None


def pruefen(token: bytes, digest: bytes) -> Befund:
    """Hält einen Stempel gegen den Stand, zu dem er gehören soll.

    **Das beantwortet die halbe Frage.** Stimmt der Hash, gehört der
    Stempel zu diesem Siegel und zu keinem anderen. Ob der Dienst ihn
    wirklich ausgestellt hat, steht damit noch nicht fest – das sagt nur
    seine Signatur, und die prüft ``openssl ts -verify``.

    Nicht lesbar heißt nicht falsch: Ein Token, dessen Aufbau MailBurg
    nicht kennt, kann trotzdem gültig sein. Deshalb steht in solchen
    Fällen ein Hinweis statt eines Urteils.
    """
    try:
        inhalt = _tstinfo(token)
    except (der.DerFehler, ZeitstempelFehler) as fehler:
        return Befund(
            passt=False, zeit=None, nonce=None,
            hinweis=(
                f"Der Stempel ließ sich nicht auslesen ({fehler}). Das "
                f"heißt nicht, dass er falsch ist – prüfen Sie ihn mit "
                f"»openssl ts -verify«."
            ),
        )

    felder = inhalt.teile()
    gestempelt = b""
    zeit = None
    nonce = None

    for nummer, feld in enumerate(felder):
        if nummer == 2 and feld.ist_folge:
            # messageImprint: Verfahren und Hash.
            for teil in feld.teile():
                if teil.kennung == der.OCTETSTRING:
                    gestempelt = teil.inhalt
        elif feld.kennung == der.GENERALIZEDTIME and zeit is None:
            zeit = _zeit(feld.inhalt)
        elif feld.kennung == der.INTEGER and nummer > 3:
            # Nach genTime kann eine Nonce stehen; die Seriennummer
            # steht davor. Ohne Nummernvergleich hielte man die eine
            # fuer die andere.
            nonce = feld.als_zahl()

    return Befund(passt=bool(gestempelt) and gestempelt == digest,
                  zeit=zeit, nonce=nonce)


def _tstinfo(token: bytes) -> der.Element:
    """Gräbt die ``TSTInfo`` aus dem signierten Umschlag.

    Sie steckt als DER in einem OCTET STRING innerhalb der CMS-Struktur.
    Der Weg dorthin ist nicht überall gleich tief, deshalb wird gesucht
    statt gezählt – und weil ein OCTET STRING auch anderswo vorkommt,
    wird geprüft, ob der Inhalt überhaupt eine SEQUENCE ist.
    """
    rest = token
    while True:
        kandidat = der.suchen(rest, der.OCTETSTRING)
        if kandidat is None:
            raise ZeitstempelFehler("Im Stempel steckt keine lesbare TSTInfo.")
        try:
            innen = der.lesen(kandidat.inhalt)
            if innen.ist_folge and not innen.rest:
                return innen
        except der.DerFehler:
            pass
        if not kandidat.rest:
            raise ZeitstempelFehler("Im Stempel steckt keine lesbare TSTInfo.")
        rest = kandidat.rest


def _zeit(rohdaten: bytes) -> datetime | None:
    """``20260831140312Z`` und Verwandte in ein Datum.

    GeneralizedTime erlaubt Sekundenbruchteile; die interessieren hier
    nicht, ein Zeitstempel wird nicht auf Millisekunden verteidigt.
    """
    text = rohdaten.decode("ascii", "replace").strip()
    if not text.endswith("Z"):
        # Ortszeit mit Zonenangabe ist zulässig, kommt bei Stempeln aber
        # nicht vor - und raten wäre hier das Falscheste.
        return None
    kern = text[:-1].split(".")[0].split(",")[0]
    try:
        return datetime.strptime(kern, "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def digest_fuer(stand: str) -> bytes:
    """Was gestempelt wird: der Hash des Stands, den ein Siegel deckt.

    Der Journalhash ist schon ein SHA-256 in Hexschreibweise. Gestempelt
    wird der Hash *seiner Textform* – nicht die entpackten Bytes, damit
    beim Nachprüfen kein Zweifel bleibt, was genau gestempelt wurde.
    Zum Nachrechnen von außen:

        printf '%s' "<stand>" | openssl dgst -sha256
    """
    return hashlib.sha256(stand.encode("ascii")).digest()
