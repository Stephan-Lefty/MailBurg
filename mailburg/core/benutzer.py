"""Wer auf ein Archiv zugreifen darf – und auf welche Postfächer.

Für die Desktop-Fassung braucht es das nicht: Wer am Rechner sitzt, hat
das Archiv ohnehin. Für die Server Edition ist es die Grundlage, denn
dort greifen mehrere Menschen auf denselben Bestand zu und sollen
verschiedenes sehen.

**Die Benutzer liegen im Archiv**, nicht neben dem Dienst. Mit Stephan
am 2026-08-31 so entschieden. Der Grund ist die Nachweisbarkeit: Wer
später begründen muss, wer eine Mail gesehen oder eingestuft hat, will
das im selben Journal finden wie den Vorgang. Ein Rechtesystem daneben,
das eigene Wege geht, macht die Verfahrensdokumentation lückenhaft.

Der Preis gehört dazugesagt: Ein Archiv trägt damit Anmeldenamen und
Passwortprüfwerte in sich. Wer es kopiert, kopiert sie mit. Deshalb
liegt die Liste in einer eigenen Datei mit ``0600`` und nicht in
``archive.json`` – so lässt sie sich beim Weitergeben gezielt weglassen,
und die Beschreibung des Archivs bleibt frei von Geheimnissen.

**Zwei Rechte, getrennt gehalten:**

``verwalter`` darf Benutzer anlegen, Rechte vergeben und Zugänge
stilllegen. ``alle_postfaecher`` darf jede Post im Archiv lesen.

Das ist bewusst nicht dasselbe. Wer die Technik betreut, muss Zugänge
verwalten können, ohne deshalb die Geschäftspost lesen zu dürfen – und
wer alles lesen darf, muss nicht über die Zugänge anderer bestimmen.
Beides in einer Rolle zusammenzufassen wäre bequemer und datenschutz-
rechtlich schlechter.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

#: Die Datei im Archiv, in der die Benutzer stehen.
DATEI = "benutzer.json"

#: Aufbau der Datei. Steht mit drin, damit eine spätere Fassung eine
#: ältere erkennen und umstellen kann, statt sie misszuverstehen.
FASSUNG = 1

# -- Passwörter ------------------------------------------------------------
#
# **scrypt aus der Standardbibliothek, nicht Argon2id.** Argon2 wäre die
# heute übliche Wahl, braucht aber ``argon2-cffi``. Der Kern von MailBurg
# kommt ohne ein einziges Fremdpaket aus, und diese Regel für eine
# Anmeldung aufzugeben, hieße: Wer nur die Kommandozeile benutzt,
# installiert trotzdem eine Bibliothek für Passwörter, die er nie
# eingibt.
#
# scrypt ist speicherhart, seit RFC 7914 standardisiert und für diesen
# Zweck anerkannt. Der Prüfwert nennt sein Verfahren und seine Parameter
# selbst - so lässt sich später auf Argon2 wechseln, ohne dass alte
# Prüfwerte unlesbar werden.

#: Rechenaufwand. 2^14 mit r=8 belegt 16 MB je Prüfung. Höher wäre
#: sicherer, stößt aber an die Voreinstellung von OpenSSL für den
#: höchsten Speicherverbrauch - und eine Anmeldung, die eine halbe
#: Sekunde dauert, fällt bei 50 Menschen am Morgen auf.
KOSTEN, BLOCK, PARALLEL = 2 ** 14, 8, 1

#: Ein Prüfwert, gegen den geprüft wird, wenn es den Benutzer gar nicht
#: gibt. Ohne ihn wäre die Antwort bei unbekanntem Namen spürbar
#: schneller als bei falschem Passwort – und damit verriete die Uhr,
#: welche Anmeldenamen existieren.
_LEERLAUF = "scrypt$16384$8$1$AAAAAAAAAAAAAAAAAAAAAA$" + "A" * 43


def passwort_pruefwert(klartext: str) -> str:
    """Erzeugt den Prüfwert zu einem Passwort.

    Format: ``scrypt$n$r$p$salz$wert``, beides in URL-sicherem Base64
    ohne Füllzeichen. Das Verfahren steht vorn, damit ein späterer
    Wechsel möglich ist.
    """
    salz = secrets.token_bytes(16)
    wert = hashlib.scrypt(
        klartext.encode("utf-8"), salt=salz,
        n=KOSTEN, r=BLOCK, p=PARALLEL, maxmem=64 * 1024 * 1024, dklen=32,
    )
    return "scrypt${}${}${}${}${}".format(
        KOSTEN, BLOCK, PARALLEL, _kurz(salz), _kurz(wert)
    )


def passwort_stimmt(pruefwert: str, klartext: str) -> bool:
    """Prüft ein Passwort gegen seinen Prüfwert.

    Verglichen wird mit ``compare_digest``: Ein gewöhnlicher Vergleich
    bricht beim ersten abweichenden Zeichen ab, und aus der Dauer ließe
    sich der richtige Wert Zeichen für Zeichen erraten.
    """
    try:
        art, kosten, block, parallel, salz, wert = pruefwert.split("$")
        if art != "scrypt":
            return False
        erneut = hashlib.scrypt(
            klartext.encode("utf-8"), salt=_lang(salz),
            n=int(kosten), r=int(block), p=int(parallel),
            maxmem=64 * 1024 * 1024, dklen=len(_lang(wert)),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(erneut, _lang(wert))


def _kurz(rohdaten: bytes) -> str:
    return base64.urlsafe_b64encode(rohdaten).decode("ascii").rstrip("=")


def _lang(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# -- Anmeldenamen ----------------------------------------------------------

#: Was als Anmeldename zulässig ist. Bewusst eng: Der Name taucht in
#: Journaleinträgen, Protokollen und später in Webadressen auf.
NAME_MUSTER = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,30}[a-z0-9])$")


class BenutzerFehler(ValueError):
    """Ein Benutzer lässt sich so nicht anlegen oder ändern."""


def name_pruefen(name: str) -> str:
    """Vereinheitlicht einen Anmeldenamen und weist Unzulässiges ab.

    Kleingeschrieben, damit »Anna« und »anna« nicht zwei Zugänge sind –
    das wäre eine Verwechslung, die erst auffällt, wenn jemand Post
    sieht, die er nicht sehen sollte.
    """
    sauber = name.strip().casefold()
    if not NAME_MUSTER.match(sauber):
        raise BenutzerFehler(
            f"»{name}« geht als Anmeldename nicht. Erlaubt sind drei bis "
            f"32 Zeichen aus Kleinbuchstaben, Ziffern, Punkt, Strich und "
            f"Unterstrich; Anfang und Ende müssen Buchstabe oder Ziffer sein."
        )
    return sauber


# -- Der Benutzer ----------------------------------------------------------


@dataclass
class Benutzer:
    """Ein Zugang zum Archiv."""

    name: str
    pruefwert: str = ""
    anzeigename: str = ""

    #: Darf Benutzer anlegen, Rechte vergeben, Zugänge stilllegen.
    verwalter: bool = False

    #: Darf jede Post im Archiv lesen.
    #:
    #: **Als Schalter, nicht als Liste aller Postfächer.** Wer alles
    #: sehen darf, soll auch das Postfach sehen, das morgen dazukommt.
    #: Eine Liste müsste dafür nachgepflegt werden – und würde es nicht,
    #: bis jemand etwas vermisst.
    alle_postfaecher: bool = False

    #: Sonst: die Postfächer, die dieser Benutzer sehen darf.
    postfaecher: list[str] = field(default_factory=list)

    #: Ein stillgelegter Zugang meldet sich nicht mehr an, bleibt aber
    #: eingetragen – sein Name muss in alten Journaleinträgen lesbar
    #: bleiben, sonst stehen dort Vorgänge ohne Urheber.
    aktiv: bool = True

    angelegt: str = ""

    def __post_init__(self) -> None:
        self.name = name_pruefen(self.name)
        if not self.angelegt:
            self.angelegt = date.today().isoformat()

    def darf_sehen(self, konto: str) -> bool:
        """Ob dieser Benutzer die Post eines Postfachs sehen darf."""
        if not self.aktiv:
            return False
        return self.alle_postfaecher or konto in self.postfaecher

    def sichtbare_postfaecher(self, alle: list[str]) -> list[str]:
        """Welche der vorhandenen Postfächer dieser Benutzer sehen darf.

        Die Reihenfolge folgt der übergebenen Liste, damit die Anzeige
        überall gleich aussieht.
        """
        if not self.aktiv:
            return []
        if self.alle_postfaecher:
            return list(alle)
        erlaubt = set(self.postfaecher)
        return [konto for konto in alle if konto in erlaubt]

    def passwort_setzen(self, klartext: str) -> None:
        if len(klartext) < 10:
            raise BenutzerFehler(
                "Das Passwort ist zu kurz – mindestens zehn Zeichen. Bei "
                "einem Zugang, der aus dem Netz erreichbar ist, wird kurz "
                "und einfach durchprobiert."
            )
        self.pruefwert = passwort_pruefwert(klartext)

    def als_daten(self) -> dict:
        return {
            "name": self.name,
            "pruefwert": self.pruefwert,
            "anzeigename": self.anzeigename,
            "verwalter": self.verwalter,
            "alle_postfaecher": self.alle_postfaecher,
            "postfaecher": list(self.postfaecher),
            "aktiv": self.aktiv,
            "angelegt": self.angelegt,
        }

    @classmethod
    def aus_daten(cls, daten: dict) -> Benutzer:
        return cls(
            name=str(daten.get("name", "")),
            pruefwert=str(daten.get("pruefwert", "")),
            anzeigename=str(daten.get("anzeigename", "")),
            verwalter=bool(daten.get("verwalter", False)),
            alle_postfaecher=bool(daten.get("alle_postfaecher", False)),
            postfaecher=[
                str(k) for k in daten.get("postfaecher", []) if isinstance(k, str)
            ],
            aktiv=bool(daten.get("aktiv", True)),
            angelegt=str(daten.get("angelegt", "")),
        )


# -- Die Liste -------------------------------------------------------------


@dataclass
class Benutzerliste:
    """Alle Zugänge eines Archivs."""

    benutzer: list[Benutzer] = field(default_factory=list)

    def __iter__(self):
        return iter(self.benutzer)

    def __len__(self) -> int:
        return len(self.benutzer)

    def finden(self, name: str) -> Benutzer | None:
        try:
            gesucht = name_pruefen(name)
        except BenutzerFehler:
            return None
        for eintrag in self.benutzer:
            if eintrag.name == gesucht:
                return eintrag
        return None

    def anmelden(self, name: str, passwort: str) -> Benutzer | None:
        """Prüft Name und Passwort. Gibt den Benutzer zurück oder nichts.

        **Auch bei unbekanntem Namen wird gerechnet.** Sonst antwortete
        das Programm dort spürbar schneller, und die Uhr verriete, welche
        Anmeldenamen es gibt.

        Ein stillgelegter Zugang meldet sich nicht an – aber die Prüfung
        läuft trotzdem durch, aus demselben Grund.
        """
        gefunden = self.finden(name)
        pruefwert = gefunden.pruefwert if gefunden else _LEERLAUF
        stimmt = passwort_stimmt(pruefwert or _LEERLAUF, passwort)

        if gefunden is None or not stimmt or not gefunden.aktiv:
            return None
        return gefunden

    def hinzufuegen(self, eintrag: Benutzer) -> None:
        if self.finden(eintrag.name) is not None:
            raise BenutzerFehler(f"»{eintrag.name}« gibt es schon.")
        self.benutzer.append(eintrag)

    def entfernen(self, name: str) -> bool:
        """Nimmt einen Zugang ganz heraus.

        **Stilllegen ist meistens richtiger.** Wer entfernt wird,
        verschwindet aus der Liste – seine Spuren im Journal bleiben und
        zeigen dann auf einen Namen, den es nicht mehr gibt.
        """
        gefunden = self.finden(name)
        if gefunden is None:
            return False
        self.benutzer.remove(gefunden)
        return True

    @property
    def verwalter(self) -> list[Benutzer]:
        return [b for b in self.benutzer if b.verwalter and b.aktiv]

    def als_daten(self) -> dict:
        return {
            "fassung": FASSUNG,
            "benutzer": [b.als_daten() for b in self.benutzer],
        }

    @classmethod
    def aus_daten(cls, daten: dict) -> Benutzerliste:
        roh = daten.get("benutzer", []) if isinstance(daten, dict) else []
        liste = []
        for eintrag in roh:
            if not isinstance(eintrag, dict):
                continue
            try:
                liste.append(Benutzer.aus_daten(eintrag))
            except BenutzerFehler:
                # Ein unlesbarer Eintrag darf nicht das ganze Archiv
                # verschließen. Er fehlt dann eben - und fällt auf,
                # sobald sich jemand nicht anmelden kann.
                continue
        return cls(benutzer=liste)

    # -- Datei ------------------------------------------------------------

    @classmethod
    def lesen(cls, wo: Path) -> Benutzerliste:
        """Liest die Liste aus einem Archiv. Fehlt sie, ist sie leer."""
        try:
            inhalt = json.loads((wo / DATEI).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls.aus_daten(inhalt)

    def schreiben(self, wo: Path) -> None:
        """Schreibt die Liste – über eine Zwischendatei, mit ``0600``.

        Die Rechte sind hier kein Beiwerk: In der Datei stehen die
        Prüfwerte der Passwörter. Auf einem Server, auf dem mehrere
        Konten existieren, hat niemand sonst dort etwas zu suchen.
        """
        ziel = wo / DATEI
        neben = ziel.with_suffix(".json.neu")
        neben.write_text(
            json.dumps(self.als_daten(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if os.name != "nt":
            neben.chmod(0o600)
        neben.replace(ziel)
