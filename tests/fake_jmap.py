"""Ein nachgebildeter JMAP-Server für die Tests.

Denselben Zweck wie ``fake_imap.py``, aus demselben Grund: Ein Abruf
gegen einen echten Anbieter wäre keine Prüfung, sondern eine
Verabredung. Und für JMAP kommt hinzu, dass es kaum einen gibt – weder
Gmail noch Outlook, GMX, Web.de oder Proton sprechen es.

Nachgebildet ist, was RFC 8620 und RFC 8621 vorschreiben, samt der
Eigenheiten, an denen ein Abruf sonst stillschweigend vorbeiliefe:

* Das **Sitzungsobjekt** nennt ``apiUrl`` und ``downloadUrl`` getrennt,
  und die Download-Adresse enthält Platzhalter, die eingesetzt werden
  müssen.
* Eine Mail kann in **mehreren Ordnern zugleich** liegen. Bei Gmail ist
  das der Normalfall – dort sind Ordner in Wahrheit Etiketten.
* ``Email/changes`` kann einen Stand als **zu alt** ablehnen. Server
  halten ihre Änderungslisten nicht ewig; wer das nicht behandelt, holt
  irgendwann gar nichts mehr.
* Ordner tragen **Rollen** (``trash``, ``junk``, ``all``), nicht nur
  Namen. Nur darüber lässt sich verlässlich sagen, was übergangen
  gehört.

**Bewusst kein echter HTTP-Server.** Geprüft wird MailBurgs Umgang mit
den Antworten, nicht Pythons Fähigkeit, eine Verbindung aufzubauen.
Eingehängt wird über ``urllib.request.urlopen``.
"""

from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError

SITZUNG = "https://jmap.example.org/.well-known/jmap"
API = "https://jmap.example.org/api"
DOWNLOAD = "https://jmap.example.org/dl/{accountId}/{blobId}/{name}"
KONTO = "konto-1"

MAIL = "urn:ietf:params:jmap:mail"
KERN = "urn:ietf:params:jmap:core"


def mail_bauen(betreff: str, absender: str = "wer@example.org",
               tag: str = "01") -> bytes:
    """Eine Rohnachricht, wie sie über die Download-Adresse käme."""
    return (
        f"From: {absender}\r\n"
        f"To: ich@example.org\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: Mon, {tag} Sep 2026 09:30:00 +0000\r\n"
        f"Message-ID: <{betreff.replace(' ', '-')}@example.org>\r\n"
        f"\r\n"
        f"Inhalt von {betreff}.\r\n"
    ).encode("utf-8")


class FakeJmap:
    """Antwortet wie ein JMAP-Server – so weit MailBurg ihn befragt."""

    def __init__(self) -> None:
        #: Kennung -> (Name, übergeordnet, Rolle)
        self.ordner: dict[str, tuple[str, str | None, str]] = {
            "m1": ("INBOX", None, "inbox"),
            "m2": ("Rechnungen", "m1", ""),
            "m3": ("Papierkorb", None, "trash"),
            "m4": ("Spam", None, "junk"),
        }
        #: Kennung -> (Rohnachricht, Ordnerkennungen, Marken)
        self.mails: dict[str, tuple[bytes, list[str], dict]] = {}
        self.zustand = "z-1"

        #: Stände, die der Server nicht mehr auflösen kann.
        self.zu_alte_staende: set[str] = set()
        #: Was seit welchem Stand dazugekommen ist.
        self.aenderungen: dict[str, list[str]] = {}

        #: Was abgefragt wurde – für Tests, die das prüfen wollen.
        self.aufrufe: list[str] = []
        self.geholte_blobs: list[str] = []
        self.anmeldung: str = ""

    # ------------------------------------------------------------- Befüllen

    def mail_hinzufuegen(self, kennung: str, betreff: str,
                         ordner: list[str] | None = None,
                         marken: dict | None = None) -> None:
        self.mails[kennung] = (
            mail_bauen(betreff),
            ordner or ["m1"],
            marken or {},
        )

    # ---------------------------------------------------------- Als urlopen

    def urlopen(self, bitte, timeout=None):
        """Ersetzt ``urllib.request.urlopen``."""
        url = bitte.full_url if hasattr(bitte, "full_url") else str(bitte)
        self.anmeldung = (
            bitte.headers.get("Authorization", "")
            if hasattr(bitte, "headers") else ""
        )

        if url == SITZUNG:
            return _Antwort(json.dumps(self._sitzung()).encode())
        if url == API:
            anfrage = json.loads(bitte.data)
            return _Antwort(json.dumps(self._api(anfrage)).encode())
        if url.startswith("https://jmap.example.org/dl/"):
            return _Antwort(self._download(url))

        raise HTTPError(url, 404, "Not Found", {}, None)

    # ------------------------------------------------------------ Die Teile

    def _sitzung(self) -> dict:
        return {
            "capabilities": {
                KERN: {"maxCallsInRequest": 16, "maxSizeUpload": 50_000_000},
                MAIL: {"maxMailboxesPerEmail": None},
            },
            "accounts": {
                KONTO: {
                    "name": "ich@example.org",
                    "accountCapabilities": {KERN: {}, MAIL: {}},
                }
            },
            "primaryAccounts": {MAIL: KONTO},
            "apiUrl": API,
            "downloadUrl": DOWNLOAD,
            "state": self.zustand,
        }

    def _api(self, anfrage: dict) -> dict:
        antworten = []
        for name, argumente, kennung in anfrage.get("methodCalls", []):
            self.aufrufe.append(name)
            if name == "Mailbox/get":
                antworten.append(["Mailbox/get", self._mailbox_get(), kennung])
            elif name == "Email/query":
                antworten.append(
                    ["Email/query", self._email_query(argumente), kennung]
                )
            elif name == "Email/get":
                antworten.append(
                    ["Email/get", self._email_get(argumente, antworten), kennung]
                )
            elif name == "Email/changes":
                ergebnis = self._email_changes(argumente)
                if ergebnis is None:
                    antworten.append(
                        ["error", {"type": "cannotCalculateChanges"}, kennung]
                    )
                else:
                    antworten.append(["Email/changes", ergebnis, kennung])
            else:
                antworten.append(["error", {"type": "unknownMethod"}, kennung])
        return {"methodResponses": antworten, "sessionState": self.zustand}

    def _mailbox_get(self) -> dict:
        return {
            "accountId": KONTO,
            "state": self.zustand,
            "list": [
                {"id": kennung, "name": name, "parentId": eltern,
                 "role": rolle or None}
                for kennung, (name, eltern, rolle) in self.ordner.items()
            ],
            "notFound": [],
        }

    def _email_query(self, argumente: dict) -> dict:
        gesucht = _ordner_aus_filter(argumente.get("filter") or {})
        treffer = [
            kennung for kennung, (_, ordner, _m) in sorted(self.mails.items())
            if not gesucht or set(ordner) & gesucht
        ]
        return {
            "accountId": KONTO,
            "queryState": self.zustand,
            "ids": treffer,
            "position": 0,
        }

    def _email_get(self, argumente: dict, bisher: list) -> dict:
        kennungen = argumente.get("ids")
        if kennungen is None:
            # Rückbezug auf ein früheres Ergebnis (#ids).
            for antwort in bisher:
                if antwort[0] == "Email/query":
                    kennungen = antwort[1]["ids"]
                    break
        kennungen = kennungen or []

        liste = []
        for kennung in kennungen:
            if kennung not in self.mails:
                continue
            roh, ordner, marken = self.mails[kennung]
            liste.append({
                "id": kennung,
                "blobId": f"blob-{kennung}",
                "mailboxIds": {o: True for o in ordner},
                "keywords": marken,
                "size": len(roh),
            })
        return {
            "accountId": KONTO,
            "state": self.zustand,
            "list": liste,
            "notFound": [k for k in kennungen if k not in self.mails],
        }

    def _email_changes(self, argumente: dict) -> dict | None:
        seit = argumente.get("sinceState", "")
        if seit in self.zu_alte_staende:
            return None
        return {
            "accountId": KONTO,
            "oldState": seit,
            "newState": self.zustand,
            "hasMoreChanges": False,
            "created": list(self.aenderungen.get(seit, [])),
            "updated": [],
            "destroyed": [],
        }

    def _download(self, url: str) -> bytes:
        teile = url.rstrip("/").split("/")
        blob = teile[-2] if len(teile) >= 2 else ""
        self.geholte_blobs.append(blob)
        kennung = blob.removeprefix("blob-")
        if kennung not in self.mails:
            raise HTTPError(url, 404, "Not Found", {}, None)
        return self.mails[kennung][0]


def _ordner_aus_filter(filter_: dict) -> set[str]:
    """Zieht die Ordnerkennungen aus einem Filter heraus."""
    if "inMailbox" in filter_:
        return {filter_["inMailbox"]}
    gefunden = set()
    for bedingung in filter_.get("conditions", []):
        gefunden |= _ordner_aus_filter(bedingung)
    return gefunden


class _Antwort:
    """Was ``urlopen`` zurückgibt – nur so viel, wie gebraucht wird."""

    def __init__(self, daten: bytes) -> None:
        self._strom = BytesIO(daten)

    def read(self) -> bytes:
        return self._strom.read()

    def __enter__(self):
        return self

    def __exit__(self, *_egal):
        return False
