"""Gerade so viel ASN.1, wie ein Zeitstempel braucht.

**Warum von Hand und nicht mit einer Bibliothek.** Für RFC 3161 gibt es
fertige Pakete. Gebraucht wird davon aber ein Bruchteil: eine Anfrage
aus vier Feldern bauen und aus der Antwort drei Werte herausholen. Das
sind zweihundert Zeilen – gegen eine Abhängigkeit, die ein Archiv
mitschleppt, das noch in zwanzig Jahren zu öffnen sein soll.

**DER in drei Sätzen.** Jeder Wert steht als *Kennung, Länge, Inhalt*.
Die Kennung sagt, was es ist (2 = INTEGER, 4 = OCTET STRING, 48 =
SEQUENCE …). Die Länge steht kurz (ein Byte, wenn sie unter 128 liegt)
oder lang (ein Byte mit gesetztem obersten Bit, das sagt, wie viele
Längenbytes folgen). Der Inhalt ist bei zusammengesetzten Typen wieder
eine Folge solcher Werte.

Mehr steckt hier nicht drin. Wer etwas Größeres braucht – Signaturen
prüfen etwa –, nimmt dafür ``openssl``; das steht auch so in der
Anleitung.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Die Kennungen, die vorkommen.
INTEGER = 0x02
BITSTRING = 0x03
OCTETSTRING = 0x04
NULL = 0x05
OID = 0x06
UTF8STRING = 0x0C
SEQUENCE = 0x30
SET = 0x31
GENERALIZEDTIME = 0x18


class DerFehler(ValueError):
    """Die Bytes sind kein gültiges DER – oder nicht das erwartete."""


# ------------------------------------------------------------- Schreiben


def _laenge(anzahl: int) -> bytes:
    """Die Längenangabe vor einem Inhalt.

    Unter 128 passt sie in ein Byte. Darüber sagt ein erstes Byte mit
    gesetztem oberstem Bit, wie viele Längenbytes folgen – deshalb
    ``0x80 | anzahl_der_bytes``.
    """
    if anzahl < 0x80:
        return bytes([anzahl])
    roh = anzahl.to_bytes((anzahl.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(roh)]) + roh


def wert(kennung: int, inhalt: bytes) -> bytes:
    """Kennung, Länge, Inhalt – das ganze Format in einer Zeile."""
    return bytes([kennung]) + _laenge(len(inhalt)) + inhalt


def ganzzahl(zahl: int) -> bytes:
    """Eine Zahl als INTEGER.

    **Das führende Nullbyte ist kein Schmuck.** DER schreibt Zahlen mit
    Vorzeichen; ein Byte ab 0x80 gälte sonst als negativ. Eine Nonce ist
    Zufall, also trifft das in der Hälfte der Fälle zu – ohne diese
    Zeile wäre jede zweite Anfrage kaputt.
    """
    if zahl == 0:
        return wert(INTEGER, b"\x00")
    roh = zahl.to_bytes((zahl.bit_length() + 8) // 8, "big")
    return wert(INTEGER, roh)


def oid(punkte: str) -> bytes:
    """Ein Objektbezeichner, aus seiner Punktschreibweise.

    ``1.2.840.113549.1.1.11`` und Ähnliches. Die ersten beiden Zahlen
    stecken zusammen in einem Byte, der Rest ist Base-128 mit
    Fortsetzungsbit – so steht es in X.690.
    """
    zahlen = [int(teil) for teil in punkte.split(".")]
    if len(zahlen) < 2:
        raise DerFehler(f"Kein Objektbezeichner: {punkte!r}")

    inhalt = bytearray([zahlen[0] * 40 + zahlen[1]])
    for zahl in zahlen[2:]:
        gruppen = [zahl & 0x7F]
        zahl >>= 7
        while zahl:
            gruppen.append((zahl & 0x7F) | 0x80)
            zahl >>= 7
        inhalt.extend(reversed(gruppen))
    return wert(OID, bytes(inhalt))


def folge(*teile: bytes) -> bytes:
    """Eine SEQUENCE aus schon kodierten Teilen."""
    return wert(SEQUENCE, b"".join(teile))


def oktette(rohdaten: bytes) -> bytes:
    return wert(OCTETSTRING, rohdaten)


def leer() -> bytes:
    """NULL – steht als Parameter hinter Hashverfahren."""
    return wert(NULL, b"")


# ---------------------------------------------------------------- Lesen


@dataclass(frozen=True)
class Element:
    """Ein gelesener Wert, mit seinem Inhalt und dem, was dahinter kommt."""

    kennung: int
    inhalt: bytes
    rest: bytes

    @property
    def ist_folge(self) -> bool:
        return self.kennung in (SEQUENCE, SET)

    def teile(self) -> list[Element]:
        """Die Elemente innerhalb einer SEQUENCE oder eines SET."""
        if not self.ist_folge:
            raise DerFehler(f"Kennung {self.kennung:#04x} ist keine Folge")
        gefunden = []
        rest = self.inhalt
        while rest:
            element = lesen(rest)
            gefunden.append(element)
            rest = element.rest
        return gefunden

    def als_zahl(self) -> int:
        if self.kennung != INTEGER:
            raise DerFehler(f"Kennung {self.kennung:#04x} ist keine Zahl")
        return int.from_bytes(self.inhalt, "big")


def lesen(rohdaten: bytes) -> Element:
    """Liest den ersten Wert aus einer Folge von Bytes."""
    if len(rohdaten) < 2:
        raise DerFehler("Zu kurz für einen DER-Wert")

    kennung = rohdaten[0]
    erstes = rohdaten[1]
    if erstes < 0x80:
        laenge, ab = erstes, 2
    else:
        anzahl = erstes & 0x7F
        if anzahl == 0 or len(rohdaten) < 2 + anzahl:
            # Unbestimmte Länge gibt es in DER nicht, nur in BER.
            raise DerFehler("Unbrauchbare Längenangabe")
        laenge = int.from_bytes(rohdaten[2:2 + anzahl], "big")
        ab = 2 + anzahl

    if len(rohdaten) < ab + laenge:
        raise DerFehler(
            f"Angekündigt sind {laenge} Byte, vorhanden sind "
            f"{len(rohdaten) - ab}"
        )
    return Element(kennung, rohdaten[ab:ab + laenge], rohdaten[ab + laenge:])


def suchen(rohdaten: bytes, kennung: int, tiefe: int = 8) -> Element | None:
    """Sucht den ersten Wert einer Kennung, auch verschachtelt.

    Für den einen Fall, in dem der Weg dorthin nicht fest ist: Das
    ``eContent`` eines signierten Zeitstempels liegt je nach Dienst
    unterschiedlich tief. Der Weg von Hand nachzugehen hieße, sich auf
    eine Struktur festzulegen, die RFC 5652 gar nicht vorschreibt.
    """
    if tiefe <= 0:
        return None
    rest = rohdaten
    while rest:
        try:
            element = lesen(rest)
        except DerFehler:
            return None
        if element.kennung == kennung:
            return element
        if element.kennung & 0x20:  # zusammengesetzt, also hineinsehen
            treffer = suchen(element.inhalt, kennung, tiefe - 1)
            if treffer is not None:
                return treffer
        rest = element.rest
    return None
