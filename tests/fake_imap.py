"""Ein nachgebildeter IMAP-Server für die Tests.

Der Abruf gegen einen echten Server zu prüfen, hieße: ein Postfach
einrichten, Zugangsdaten hinterlegen und hoffen, dass die Leitung steht.
Das wäre kein Test, sondern eine Verabredung. Stattdessen antwortet dieses
Objekt genau so, wie ``imaplib`` es täte – bis hin zu den Eigenheiten, an
denen der Code sonst stillschweigend vorbeiliefe:

* ``UID n:*`` liefert immer mindestens die höchste UID, auch wenn die
  kleiner als ``n`` ist. Genau das steht in RFC 3501, und genau daran
  scheitern Abrufe, die es nicht wissen.
* ``BODY.PEEK[]`` lässt die Mail ungelesen, ``BODY[]`` nicht. Der Server
  merkt sich hier, wonach gefragt wurde, damit ein Test es prüfen kann.
* Ordnernamen kommen im abgewandelten UTF-7 zurück.

Seit dem 2026-09-04 kann er auch **schreiben** – ``CREATE`` und
``APPEND``, für das Zurückspielen ganzer Ordner. Der Server vergibt
dabei neue UIDs und legt bei jedem ``APPEND`` eine neue Kopie an, auch
wenn dieselbe Nachricht schon dort liegt: Genau so verhält sich ein
echter Server, und genau daran scheitert ein Restore, der nicht vorher
nachsieht.
"""

from __future__ import annotations

import imaplib
import re
from datetime import date

_BEREICH = re.compile(r"UID\s+(\d+):\*")
_VOR = re.compile(r"BEFORE\s+(\d{2}-[A-Za-z]{3}-\d{4})")

#: Monatskürzel, wie IMAP sie verlangt – englisch und unabhängig von der
#: Spracheinstellung des Rechners.
_MONATE = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _datum_lesen(text: str) -> date:
    """Wandelt ``07-Mar-2026`` in ein Datum."""
    tag, monat, jahr = text.split("-")
    return date(int(jahr), _MONATE.index(monat) + 1, int(tag))


class FakeOrdner:
    """Ein Ordner im nachgebildeten Postfach."""

    def __init__(self, roh: str, mails: dict[int, bytes], uidvalidity: int = 1000,
                 merkmale: str = "\\HasNoChildren",
                 empfangen: dict[int, "date"] | None = None) -> None:
        self.roh = roh
        self.mails = dict(mails)
        self.uidvalidity = uidvalidity
        self.merkmale = merkmale

        #: Wann die Mails beim Server ankamen – nur für ``BEFORE`` nötig.
        #: Ohne Angabe gelten alle als alt: Wer den Abgleich prüft, will in
        #: der Regel, dass sämtliche Mails in die Prüfung fallen.
        self.empfangen = dict(empfangen or {})


class FakeImap:
    """Genug von ``imaplib.IMAP4``, um den Abruf zu prüfen."""

    def __init__(self, ordner: list[FakeOrdner], trenner: str = "/") -> None:
        self.ordner = {o.roh: o for o in ordner}
        self.trenner = trenner
        self.aktuell: FakeOrdner | None = None

        #: Womit die Ordner geöffnet wurden – zum Nachweis, dass nur
        #: gelesen wird.
        self.nur_lesend: list[bool] = []
        #: Alle FETCH-Anforderungen im Wortlaut.
        self.abgefragt: list[str] = []
        #: Was angelegt wurde – auch die Versuche auf schon Vorhandenes.
        self.angelegt: list[str] = []
        #: Jede angehängte Nachricht: Ordner, Marken, Datum, Bytes.
        self.angehaengt: list[tuple] = []
        self.abgemeldet = False

    # ------------------------------------------------------- imaplib-Ersatz

    def list(self, directory: str = '""', pattern: str = "*"):
        zeilen = [
            f'({o.merkmale}) "{self.trenner}" "{o.roh}"'.encode()
            for o in self.ordner.values()
        ]
        return "OK", zeilen

    def select(self, mailbox: str = "INBOX", readonly: bool = False):
        name = mailbox.strip('"')
        if name not in self.ordner:
            return "NO", [b"Mailbox doesn't exist"]
        self.aktuell = self.ordner[name]
        self.nur_lesend.append(readonly)
        return "OK", [str(len(self.aktuell.mails)).encode()]

    def response(self, code: str):
        if code == "UIDVALIDITY" and self.aktuell is not None:
            return code, [str(self.aktuell.uidvalidity).encode()]
        return code, [None]

    def uid(self, befehl: str, *args):
        if self.aktuell is None:
            return "NO", [b"No mailbox selected"]
        if befehl.upper() == "SEARCH":
            return self._suchen(args[-1])
        if befehl.upper() == "FETCH":
            return self._holen(args[0], args[1])
        raise AssertionError(f"Unerwarteter Befehl: {befehl}")

    def create(self, mailbox: str):
        """Legt einen Ordner an – oder sagt, dass es ihn schon gibt."""
        name = mailbox.strip('"')
        self.angelegt.append(name)
        if name in self.ordner:
            return "NO", [b"Mailbox already exists"]
        self.ordner[name] = FakeOrdner(name, {}, uidvalidity=4711)
        return "OK", [b"Create completed"]

    def append(self, mailbox: str, flags, date_time, message):
        """Hängt eine Nachricht an – **immer als neue Kopie.**

        Das ist der Punkt, um den es beim Zurückspielen geht: Ein
        zweiter Lauf, der nicht vorher nachsieht, was schon da ist,
        verdoppelt den ganzen Ordner. Der Server hilft dabei nicht; er
        vergibt nur eine neue UID.
        """
        name = mailbox.strip('"')
        if name not in self.ordner:
            return "NO", [b"Mailbox doesn't exist"]
        if isinstance(message, str):
            message = message.encode()
        ziel = self.ordner[name]
        naechste = max(ziel.mails, default=0) + 1
        ziel.mails[naechste] = message
        self.angehaengt.append((name, flags or "", date_time, message))
        return "OK", [f"[APPENDUID {ziel.uidvalidity} {naechste}] Append completed".encode()]

    def logout(self):
        self.abgemeldet = True
        return "BYE", [b"Logging out"]

    # ------------------------------------------------------------- Innerei

    def _suchen(self, ausdruck: str):
        vorhanden = sorted(self.aktuell.mails)
        if not vorhanden:
            return "OK", [b""]

        vor = _VOR.search(ausdruck)
        if vor:
            # BEFORE bezieht sich auf den Zeitpunkt, zu dem die Mail beim
            # Server ankam - nicht auf das Date: im Kopf.
            grenze = _datum_lesen(vor.group(1))
            gefunden = [
                u for u in vorhanden
                if self.aktuell.empfangen.get(u, date.min) < grenze
            ]
            return "OK", [" ".join(str(u) for u in gefunden).encode()]

        treffer = _BEREICH.search(ausdruck)
        if treffer:
            ab = int(treffer.group(1))
            gefunden = [u for u in vorhanden if u >= ab]
            # Die Eigenheit aus RFC 3501: Der Stern ist die höchste UID,
            # und ein Bereich wird nie leer geliefert. Fragt jemand nach
            # 900:* und die höchste ist 800, kommt 800 zurück.
            if not gefunden:
                gefunden = [vorhanden[-1]]
        else:
            gewuenscht = {
                int(t) for t in ausdruck.replace("UID", "").split(",") if t.strip().isdigit()
            }
            gefunden = [u for u in vorhanden if u in gewuenscht]

        return "OK", [" ".join(str(u) for u in gefunden).encode()]

    def _holen(self, bereich: str, was: str):
        self.abgefragt.append(was)
        # »1:*« heißt: alles, was da ist. So fragt der Abgleich beim
        # Zurückspielen einen ganzen Zielordner ab.
        offen = _BEREICH.match("UID " + bereich.strip()) or re.match(
            r"^(\d+):\*$", bereich.strip()
        )
        if offen:
            ab = int(offen.group(1))
            uids = [u for u in sorted(self.aktuell.mails) if u >= ab]
        else:
            uids = [int(t) for t in bereich.split(",") if t.strip().isdigit()]

        if "RFC822.SIZE" in was and "BODY" not in was:
            zeilen = [
                f"{n} (UID {u} RFC822.SIZE {len(self.aktuell.mails[u])})".encode()
                for n, u in enumerate(uids, 1)
                if u in self.aktuell.mails
            ]
            return "OK", zeilen

        # Nur bestimmte Kopfzeilen - so fragt der Abgleich beim
        # Zurückspielen nach den Message-ID eines ganzen Ordners.
        if "HEADER.FIELDS" in was.upper():
            felder = was.upper().split("HEADER.FIELDS", 1)[1]
            gesucht = [f.strip("() []").lower() for f in felder.split()]
            antwort = []
            for n, uid in enumerate(uids, 1):
                roh = self.aktuell.mails.get(uid)
                if roh is None:
                    continue
                zeilen = [
                    z for z in roh.split(b"\r\n")
                    if any(z.lower().startswith(f.encode() + b":") for f in gesucht)
                ]
                stueck = b"\r\n".join(zeilen) + b"\r\n\r\n"
                antwort.append(
                    (f"{n} (UID {uid} BODY[HEADER.FIELDS] {{{len(stueck)}}}".encode(),
                     stueck)
                )
                antwort.append(b")")
            return "OK", antwort

        antwort = []
        for n, uid in enumerate(uids, 1):
            roh = self.aktuell.mails.get(uid)
            if roh is None:
                continue
            kopf = f"{n} (UID {uid} FLAGS (\\Seen) BODY[] {{{len(roh)}}}".encode()
            antwort.append((kopf, roh))
            antwort.append(b")")
        return "OK", antwort


class AblehnenderImap(FakeImap):
    """Ein Server, der bei einem bestimmten Ordner die Mitarbeit verweigert."""

    def __init__(self, ordner, sperrt: str) -> None:
        super().__init__(ordner)
        self.sperrt = sperrt

    def select(self, mailbox: str = "INBOX", readonly: bool = False):
        if mailbox.strip('"') == self.sperrt:
            raise imaplib.IMAP4.error("Server temporarily unavailable")
        return super().select(mailbox, readonly)


def mail(betreff: str, groesse: int = 0) -> bytes:
    """Eine kleine, gültige Mail – bei Bedarf auf Länge gebracht."""
    roh = (
        f"From: Absender <absender@example.org>\r\n"
        f"To: empfaenger@example.org\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: Mon, 25 Aug 2026 10:00:00 +0200\r\n"
        f"Message-ID: <{betreff.replace(' ', '-')}@example.org>\r\n"
        f"\r\n"
        f"Inhalt von {betreff}.\r\n"
    ).encode("utf-8")
    if groesse > len(roh):
        roh += b"x" * (groesse - len(roh))
    return roh
