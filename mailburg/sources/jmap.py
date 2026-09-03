"""Mails über JMAP holen – RFC 8620 und RFC 8621.

**Der Nachfolger von IMAP, und für ein Archiv der interessantere Weg.**
IMAP ist ein Dialog: Ordner öffnen, UIDs erfragen, Nachrichten
nachfordern, Ordner schließen, nächster Ordner. Bei zwanzig Ordnern sind
das hundert Umläufe, bevor die erste Mail da ist.

JMAP ist JSON über HTTPS und kennt zwei Dinge, die IMAP fehlen:

*Stapelabfragen.* Mehrere Aufrufe gehen in einer Anfrage hinaus, und
spätere dürfen sich auf frühere beziehen – »hol mir die Mails aus dem
Ordner, den du gerade gefunden hast«, ohne dass der Ordner ein zweites
Mal über die Leitung geht.

*Änderungsverfolgung.* ``Email/changes`` beantwortet genau die Frage,
die ein Archiv bei jedem Lauf stellt: Was ist seit dem letzten Mal
dazugekommen? IMAP kann das nicht sagen; MailBurg baut es dort über
``UID n:*`` und Nachfiltern nach, und selbst das ist nur eine Näherung.

**Es wird nur gelesen.** JMAP hat keinen Seiteneffekt wie IMAPs
``SELECT``, das ungelesene Post als gelesen markieren kann – es gibt
schlicht keinen Aufruf, der etwas ändert, außer man ruft ihn
ausdrücklich. Diese Quelle ruft nur ``get``, ``query`` und ``changes``.

**Die Rohnachricht kommt über die Download-Adresse**, nicht aus dem
JSON. Das ist der entscheidende Punkt für ein Archiv: Was der Server
unter ``blobId`` herausgibt, ist die Nachricht Byte für Byte, wie sie
ankam – mit allen Kopfzeilen, mit prüfbarer DKIM-Signatur. Die zerlegte
Fassung im JSON wäre bequemer und für ein Archiv wertlos.

**Wer es benutzen kann.** Fastmail, Stalwart, Cyrus ab 3.6, Apache James.
Nicht: Gmail, Outlook, GMX, Web.de, Proton. Das ist heute die
Einschränkung – JMAP ist die bessere Technik und die seltenere.

**Noch nie gegen einen echten Anbieter gelaufen.** Geprüft ist alles
gegen einen nachgebauten Server in ``tests/fake_jmap.py``, also gegen
die eigenen Annahmen. Dasselbe gilt für OAuth2, und dort steht derselbe
Satz. Wer diese Quelle an einem echten Konto ausprobiert, sollte den
ersten Lauf mit ``mailburg pruefen`` nachfassen.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from base64 import b64encode
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from mailburg.sources.base import RawMessage, Source

#: Die Fähigkeiten, die MailBurg vom Server verlangt. Ohne die zweite
#: kann er zwar JMAP, aber keine Mail – JMAP ist ein allgemeines
#: Protokoll, Mail nur eine seiner Anwendungen.
KERN = "urn:ietf:params:jmap:core"
MAIL = "urn:ietf:params:jmap:mail"

#: So lange wird auf den Server gewartet. Wie bei IMAP: Ohne Grenze
#: bleibt ein Lauf an einem stummen Server hängen, gern über Nacht in
#: einer Zeitsteuerung.
ZEITGRENZE = 60

#: Und beim Prüfen in der Oberfläche, wo ein Mensch wartet.
ZEITGRENZE_PRUEFEN = 15

#: Wie viele Mails auf einmal angefordert werden. JMAP erlaubt große
#: Stapel; der Arbeitsspeicher nicht. Anders als bei IMAP kommen hier
#: nur die Kennungen, nicht die Nachrichten – deshalb darf es mehr sein.
BLOCK = 200

#: Ordnerrollen nach RFC 8621, die nicht ins Archiv gehören.
#:
#: **Rollen statt Namen.** Ein Ordner heißt je nach Sprache »Papierkorb«,
#: »Trash« oder »Corbeille«; seine Rolle heißt überall ``trash``. Bei
#: IMAP macht MailBurg dasselbe über RFC 6154.
UEBERGANGENE_ROLLEN = frozenset({"trash", "junk", "drafts"})

#: ``all`` ist der Gmail-Fall: ein Ordner, der sämtliche Mails ein
#: zweites Mal enthält. Er steht getrennt, weil er nicht »unerwünscht«
#: ist, sondern eine Dublette – und weil die Begründung eine andere ist.
ARCHIVROLLE_DOPPELT = "all"


class JmapFehler(RuntimeError):
    """Der Server antwortet nicht oder nicht wie erwartet."""


@dataclass
class Sitzung:
    """Was der Server über sich und das Konto sagt.

    Das Sitzungsobjekt ist der Einstieg in JMAP: eine einzige GET-Anfrage,
    die sagt, wohin die eigentlichen Aufrufe gehen, wo sich Anhänge
    herunterladen lassen und welche Konten es gibt.
    """

    api: str
    download: str
    konto: str
    faehigkeiten: dict[str, Any] = field(default_factory=dict)

    @property
    def hoechstens_aufrufe(self) -> int:
        """Wie viele Methodenaufrufe der Server je Anfrage annimmt.

        Steht in den Kernfähigkeiten. Wer mehr schickt, bekommt einen
        Fehler – und zwar für die ganze Anfrage, nicht nur für den
        überzähligen Aufruf.
        """
        return int(
            self.faehigkeiten.get(KERN, {}).get("maxCallsInRequest", 16)
        )


def _kopfzeilen(benutzer: str, passwort: str, marke: str = "") -> dict[str, str]:
    """Die Anmeldung, entweder mit Marke oder mit Benutzer und Passwort.

    **Beides kommt vor.** Fastmail vergibt Zugriffsmarken (»API tokens«),
    ein selbst betriebener Stalwart nimmt Benutzername und Passwort. Wer
    eine Marke hat, trägt sie ins Passwortfeld ein und lässt den
    Benutzernamen leer – dann wird daraus ein ``Bearer``.
    """
    if marke or not benutzer:
        wert = f"Bearer {marke or passwort}"
    else:
        roh = f"{benutzer}:{passwort}".encode("utf-8")
        wert = f"Basic {b64encode(roh).decode('ascii')}"
    return {
        "Authorization": wert,
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Nennt das Programm, nicht den Rechner oder den Benutzer.
        "User-Agent": "MailBurg",
    }


def _holen(url: str, kopf: dict[str, str], daten: bytes | None = None,
           zeitgrenze: int = ZEITGRENZE) -> bytes:
    """Eine Anfrage, mit verständlichen Fehlern statt Tracebacks."""
    bitte = urllib.request.Request(url, data=daten, headers=kopf)
    try:
        with urllib.request.urlopen(bitte, timeout=zeitgrenze) as antwort:
            return antwort.read()
    except urllib.error.HTTPError as fehler:
        if fehler.code in (401, 403):
            raise JmapFehler(
                f"Der Server hat die Anmeldung abgelehnt ({fehler.code}).\n\n"
                f"Bei JMAP ist das Passwort oft keine Anmeldung, sondern "
                f"eine eigens erzeugte Zugriffsmarke – bei Fastmail etwa "
                f"unter »Settings → Privacy & Security → API tokens«."
            ) from fehler
        raise JmapFehler(
            f"Der Server antwortete mit {fehler.code} {fehler.reason}."
        ) from fehler
    except (urllib.error.URLError, OSError) as fehler:
        raise JmapFehler(f"{url} war nicht erreichbar: {fehler}") from fehler


def sitzung_holen(url: str, benutzer: str, passwort: str, *,
                  marke: str = "", zeitgrenze: int = ZEITGRENZE) -> Sitzung:
    """Holt das Sitzungsobjekt – der erste Schritt jeder JMAP-Verbindung."""
    roh = _holen(url, _kopfzeilen(benutzer, passwort, marke),
                 zeitgrenze=zeitgrenze)
    try:
        daten = json.loads(roh)
    except json.JSONDecodeError as fehler:
        raise JmapFehler(
            f"Unter {url} antwortet kein JMAP-Server – die Antwort ist "
            f"kein JSON. Stimmt die Adresse?"
        ) from fehler

    faehigkeiten = daten.get("capabilities", {})
    if MAIL not in faehigkeiten:
        raise JmapFehler(
            "Dieser Server spricht JMAP, aber nicht für Mail "
            f"(»{MAIL}« fehlt in seinen Fähigkeiten). JMAP ist ein "
            "allgemeines Protokoll; Mail ist nur eine seiner Anwendungen."
        )

    konto = daten.get("primaryAccounts", {}).get(MAIL)
    if not konto:
        # Manche Server nennen kein primäres Konto, wenn es nur eines
        # gibt. Dann nehmen wir das einzige, das Mail kann.
        for kennung, angaben in (daten.get("accounts") or {}).items():
            if MAIL in (angaben.get("accountCapabilities") or {}):
                konto = kennung
                break
    if not konto:
        raise JmapFehler("Der Server nennt kein Mailkonto für diese Anmeldung.")

    api = daten.get("apiUrl")
    download = daten.get("downloadUrl")
    if not api or not download:
        raise JmapFehler(
            "Im Sitzungsobjekt fehlen »apiUrl« oder »downloadUrl«. Ohne "
            "beides lässt sich weder fragen noch herunterladen."
        )
    return Sitzung(api=api, download=download, konto=konto,
                   faehigkeiten=faehigkeiten)


class JmapSource(Source):
    """Ein JMAP-Postfach als Mailquelle."""

    def __init__(self, konto, passwort: str, *, marke: str = "",
                 seit_zustand: str = "", zeitgrenze: int = ZEITGRENZE) -> None:
        self.konto = konto
        self.account = konto.name
        self._passwort = passwort
        self._marke = marke
        self._zeitgrenze = zeitgrenze
        self._kopf = _kopfzeilen(konto.benutzer, passwort, marke)
        self._sitzung: Sitzung | None = None
        self._ordner: dict[str, str] = {}

        #: Der Stand, bis zu dem beim letzten Mal geholt wurde. Leer
        #: heißt: alles holen.
        self.seit_zustand = seit_zustand

        #: Der Stand nach diesem Lauf – gehört in den Abrufzustand.
        #: Er tritt bei JMAP an die Stelle von UIDVALIDITY und Höchststand.
        self.zustand = ""

    # ------------------------------------------------------------ Verbindung

    @property
    def sitzung(self) -> Sitzung:
        if self._sitzung is None:
            self._sitzung = sitzung_holen(
                self._sitzungsadresse(), self.konto.benutzer,
                self._passwort, marke=self._marke,
                zeitgrenze=self._zeitgrenze,
            )
        return self._sitzung

    def _sitzungsadresse(self) -> str:
        """Wo das Sitzungsobjekt liegt.

        Steht im Kontofeld ``server`` schon eine vollständige Adresse,
        gilt sie. Sonst der Weg, den RFC 8620 vorsieht: Der Server nennt
        sie unter ``/.well-known/jmap``.
        """
        server = self.konto.server.strip()
        if server.startswith(("http://", "https://")):
            return server
        return f"https://{server}/.well-known/jmap"

    def _aufrufen(self, *aufrufe) -> list:
        """Schickt einen Stapel Methodenaufrufe und gibt die Antworten.

        **Das ist der Gewinn gegenüber IMAP.** Wo dort jeder Schritt
        einen eigenen Umlauf braucht, gehen hier mehrere zusammen
        hinaus – und spätere dürfen sich auf frühere beziehen.
        """
        anfrage = {
            "using": [KERN, MAIL],
            "methodCalls": [list(a) for a in aufrufe],
        }
        roh = _holen(
            self.sitzung.api, self._kopf,
            json.dumps(anfrage).encode("utf-8"), self._zeitgrenze,
        )
        try:
            antwort = json.loads(roh)
        except json.JSONDecodeError as fehler:
            raise JmapFehler("Die Antwort des Servers ist kein JSON.") from fehler

        ergebnisse = antwort.get("methodResponses") or []
        for eintrag in ergebnisse:
            if eintrag and eintrag[0] == "error":
                art = (eintrag[1] or {}).get("type", "unbekannt")
                raise JmapFehler(f"Der Server meldet einen Fehler: {art}")
        return ergebnisse

    # --------------------------------------------------------------- Ordner

    def folders(self) -> list[str]:
        """Die Ordner des Postfachs, ohne die übergangenen."""
        self._ordner_laden()
        return sorted(self._ordner.values())

    def _ordner_laden(self) -> None:
        if self._ordner:
            return
        antworten = self._aufrufen(
            ["Mailbox/get", {"accountId": self.sitzung.konto,
                             "ids": None}, "o"]
        )
        if not antworten:
            raise JmapFehler("Der Server gab keine Ordner zurück.")

        alle = {}
        eltern = {}
        rollen = {}
        for kasten in antworten[0][1].get("list", []):
            kennung = kasten.get("id")
            if not kennung:
                continue
            alle[kennung] = kasten.get("name", "")
            eltern[kennung] = kasten.get("parentId")
            rollen[kennung] = (kasten.get("role") or "").lower()

        ausschluss = {a.lower() for a in (self.konto.ausschluss or [])}
        for kennung, name in alle.items():
            rolle = rollen.get(kennung, "")
            if rolle in UEBERGANGENE_ROLLEN:
                continue
            if rolle == ARCHIVROLLE_DOPPELT:
                # Der Gmail-Fall: enthält alles ein zweites Mal. Auf der
                # Platte gäbe das keine doppelte Datei, wohl aber einen
                # zweiten Fundort je Mail im Journal.
                continue
            pfad = self._pfad(kennung, alle, eltern)
            if pfad.lower() in ausschluss or name.lower() in ausschluss:
                continue
            self._ordner[kennung] = pfad

    @staticmethod
    def _pfad(kennung: str, alle: dict, eltern: dict) -> str:
        """Baut den vollen Ordnerpfad, mit ``/`` getrennt.

        JMAP nennt nur den eigenen Namen und die übergeordnete Kennung;
        das Archiv will »INBOX/Rechnungen«. Die Schleifenbremse ist kein
        Schmuck: Ein Server, der sich in den Elternangaben vertut, würde
        uns sonst ewig kreisen lassen.
        """
        teile = []
        gesehen = set()
        aktuell = kennung
        while aktuell and aktuell in alle and aktuell not in gesehen:
            gesehen.add(aktuell)
            teile.append(alle[aktuell])
            aktuell = eltern.get(aktuell)
        return "/".join(reversed(teile))

    # ----------------------------------------------------------------- Mails

    def iter_messages(self) -> Iterator[RawMessage]:
        """Gibt alle Mails aus, die neu sind."""
        self._ordner_laden()

        kennungen, self.zustand = self._welche_mails()
        if not kennungen:
            return

        for haeppchen in _stuecke(kennungen, BLOCK):
            for mail in self._mails_holen(haeppchen):
                yield mail

    def _welche_mails(self) -> tuple[list[str], str]:
        """Welche Mails zu holen sind – und der Stand danach.

        **Zwei Wege, und der zweite ist der Grund für JMAP.** Beim ersten
        Lauf fragen wir nach allem, was in den gewünschten Ordnern liegt.
        Danach fragen wir nur noch, was sich seit dem gemerkten Stand
        geändert hat – eine Anfrage für das ganze Postfach, statt Ordner
        für Ordner nachzurechnen.
        """
        if self.seit_zustand:
            neu, stand = self._geaenderte()
            if neu is not None:
                return neu, stand
            # Der Stand ist zu alt geworden - der Server hat seine
            # Änderungsliste inzwischen abgeschnitten. Dann bleibt nur
            # der vollständige Weg; doppelte erkennt das Archiv selbst.
        return self._alle()

    def _alle(self) -> tuple[list[str], str]:
        antworten = self._aufrufen(
            ["Email/query", {
                "accountId": self.sitzung.konto,
                "filter": {"operator": "OR", "conditions": [
                    {"inMailbox": kennung} for kennung in self._ordner
                ]} if len(self._ordner) > 1 else (
                    {"inMailbox": next(iter(self._ordner))}
                    if self._ordner else {}
                ),
                "sort": [{"property": "receivedAt", "isAscending": True}],
                "calculateTotal": False,
            }, "q"],
            ["Email/get", {
                "accountId": self.sitzung.konto,
                "#ids": {"resultOf": "q", "name": "Email/query",
                         "path": "/ids"},
                "properties": ["id"],
            }, "g"],
        )
        kennungen = list(antworten[0][1].get("ids") or [])
        stand = self._zustand_holen()
        return kennungen, stand

    def _geaenderte(self) -> tuple[list[str] | None, str]:
        """``Email/changes`` – was ist seit dem gemerkten Stand neu?

        Gibt ``None`` zurück, wenn der Server den Stand nicht mehr
        auflösen kann. Das ist kein Fehler, sondern vorgesehen: Server
        halten ihre Änderungslisten nicht ewig.
        """
        try:
            antworten = self._aufrufen(
                ["Email/changes", {
                    "accountId": self.sitzung.konto,
                    "sinceState": self.seit_zustand,
                    "maxChanges": BLOCK * 10,
                }, "c"],
            )
        except JmapFehler:
            return None, ""

        ergebnis = antworten[0][1]
        # Nur das Neue. Geändertes interessiert ein Archiv nicht - die
        # Mail selbst ändert sich nicht, nur ihre Marken, und die sind
        # dort ohnehin eine Momentaufnahme.
        return list(ergebnis.get("created") or []), ergebnis.get("newState", "")

    def _zustand_holen(self) -> str:
        """Der aktuelle Stand des Postfachs, für den nächsten Lauf."""
        try:
            antworten = self._aufrufen(
                ["Email/get", {"accountId": self.sitzung.konto,
                               "ids": [], "properties": ["id"]}, "s"],
            )
        except JmapFehler:
            return ""
        return antworten[0][1].get("state", "") if antworten else ""

    def _mails_holen(self, kennungen: list[str]) -> Iterator[RawMessage]:
        """Holt Rohnachrichten zu einer Reihe von Kennungen."""
        antworten = self._aufrufen(
            ["Email/get", {
                "accountId": self.sitzung.konto,
                "ids": kennungen,
                # blobId ist der Schlüssel zur Rohnachricht, mailboxIds
                # sagt, wo sie liegt, keywords sind die Marken.
                "properties": ["id", "blobId", "mailboxIds", "keywords"],
            }, "m"],
        )
        if not antworten:
            return

        for mail in antworten[0][1].get("list", []):
            blob = mail.get("blobId")
            if not blob:
                continue
            ordner = self._erster_ordner(mail.get("mailboxIds") or {})
            if ordner is None:
                # Liegt nur in Ordnern, die wir übergehen.
                continue
            try:
                roh = self._blob_holen(blob)
            except JmapFehler:
                # Eine Mail, die sich nicht holen lässt, darf den Lauf
                # nicht beenden - dieselbe Regel wie bei IMAP.
                continue
            yield RawMessage(
                raw=roh,
                folder=ordner,
                uid=None,
                flags=_marken(mail.get("keywords") or {}),
            )

    def _erster_ordner(self, kaesten: dict) -> str | None:
        """Welchem Ordner die Mail zugeschrieben wird.

        **JMAP kennt Mails in mehreren Ordnern gleichzeitig** – bei Gmail
        ist das der Normalfall, dort sind Ordner in Wahrheit Etiketten.
        Das Archiv braucht einen Fundort je Mail und Lauf; genommen wird
        der erste, den wir nicht übergehen, in stabiler Reihenfolge.
        """
        for kennung in sorted(kaesten):
            if kennung in self._ordner:
                return self._ordner[kennung]
        return None

    def _blob_holen(self, blob: str) -> bytes:
        """Lädt die Rohnachricht – Byte für Byte, wie sie ankam."""
        adresse = (
            self.sitzung.download
            .replace("{accountId}", self.sitzung.konto)
            .replace("{blobId}", blob)
            .replace("{type}", "message/rfc822")
            .replace("{name}", "mail.eml")
        )
        kopf = dict(self._kopf)
        kopf["Accept"] = "message/rfc822"
        return _holen(adresse, kopf, zeitgrenze=self._zeitgrenze)

    # ---------------------------------------------------------------- Sonst

    def describe(self) -> str:
        return f"JMAP {self.konto.server} ({self.konto.benutzer or 'Marke'})"

    def close(self) -> None:
        self._sitzung = None


def _marken(keywords: dict) -> str:
    """JMAP-Marken in dieselbe Schreibweise wie bei IMAP.

    ``$seen`` heißt dort ``\\Seen``. Gespeichert wird die IMAP-Form,
    damit im Archiv nicht zweierlei steht, je nachdem, woher eine Mail
    kam.
    """
    umschrift = {
        "$seen": "\\Seen", "$flagged": "\\Flagged",
        "$answered": "\\Answered", "$draft": "\\Draft",
    }
    return " ".join(
        sorted(umschrift.get(k, k) for k, an in keywords.items() if an)
    )


def _stuecke(werte: list, groesse: int) -> Iterator[list]:
    for anfang in range(0, len(werte), groesse):
        yield werte[anfang:anfang + groesse]


def pruefen(konto, passwort: str, *, marke: str = "") -> tuple[bool, str]:
    """Sieht nach, ob die Verbindung steht – für die Oberfläche.

    Gibt zurück, ob es geklappt hat, und einen Satz dazu.
    """
    quelle = JmapSource(konto, passwort, marke=marke,
                        zeitgrenze=ZEITGRENZE_PRUEFEN)
    try:
        ordner = quelle.folders()
    except JmapFehler as fehler:
        return False, str(fehler)
    finally:
        quelle.close()
    return True, f"Verbindung steht, {len(ordner)} Ordner gefunden."
