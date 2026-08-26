"""Herausfinden, warum ein Zertifikat abgelehnt wurde – und was hilft.

Der häufigste Fall bei eigenen Domains: Der Mailserver steht bei einem
Massenhoster und weist sich mit dessen Zertifikat aus. ``imap.meinefirma.de``
zeigt per DNS auf ``s111.hoster.example``, das Zertifikat gilt aber nur für
``*.hoster.example``. Die Prüfung scheitert – zu Recht, denn dieser Name ist
nicht beglaubigt.

Mailprogramme lösen das üblicherweise, indem sie den Anwender einmal fragen
und die Ausnahme dann für immer speichern. Damit ist die Prüfung für diesen
Server dauerhaft ausgehebelt, und niemand denkt je wieder daran.

MailBurg geht den anderen Weg: Es sieht nach, **für welchen Namen** das
Zertifikat gilt, und schlägt ihn vor. Wer den Vorschlag annimmt, hat danach
eine vollständig geprüfte Verbindung statt einer stillschweigenden Ausnahme
– zum selben Server, über dieselbe Leitung.

Geht das nicht, bleibt es beim Fehler. Eine Möglichkeit, die Prüfung für
beliebige Server abzuschalten, gibt es bewusst nicht.
"""

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass, field

#: So lange wird beim Nachsehen gewartet. Kürzer als beim Abruf – hier
#: wartet jemand vor der Eingabeaufforderung.
ZEITGRENZE = 10


@dataclass
class Befund:
    """Was das Zertifikat eines Servers hergibt."""

    namen: list[str] = field(default_factory=list)
    """Alle Namen, für die es gilt – aus subjectAltName und CN."""

    rueckwaerts: str = ""
    """Der Name, unter dem die IP-Adresse bekannt ist."""

    vorschlag: str = ""
    """Ein Name, der zum Zertifikat passt und denselben Server meint."""

    def __bool__(self) -> bool:
        return bool(self.vorschlag)


def _namen_aus_zertifikat(zertifikat: dict) -> list[str]:
    """Sammelt alle Namen, auf die ein Zertifikat ausgestellt ist."""
    namen: list[str] = []
    for art, wert in zertifikat.get("subjectAltName", ()):
        if art == "DNS" and wert not in namen:
            namen.append(wert)
    for teil in zertifikat.get("subject", ()):
        for schluessel, wert in teil:
            if schluessel == "commonName" and wert not in namen:
                namen.append(wert)
    return namen


def passt(name: str, muster: str) -> bool:
    """Prüft einen Namen gegen einen Zertifikatseintrag, Platzhalter inbegriffen.

    ``*.hoster.example`` deckt ``s111.hoster.example`` ab, aber nicht
    ``a.b.hoster.example`` – ein Stern steht für genau eine Ebene. So steht es
    in RFC 6125, und so hält es auch Python selbst.
    """
    name, muster = name.lower().rstrip("."), muster.lower().rstrip(".")
    if not muster.startswith("*."):
        return name == muster
    rest = muster[2:]
    if not name.endswith("." + rest):
        return False
    davor = name[: -(len(rest) + 1)]
    return bool(davor) and "." not in davor


def _zertifikat_holen(server: str, port: int, starttls: bool) -> dict:
    """Holt das Zertifikat, ohne den Namen zu prüfen.

    Die Zertifizierungsstelle wird sehr wohl geprüft – nur eben nicht, ob
    der Name passt. Genau daran scheitert der Fall ja. Ein selbstsigniertes
    Zertifikat kommt hier gar nicht erst durch, und das ist beabsichtigt:
    Dann liegt kein Namensproblem vor, sondern ein anderes.
    """
    kontext = ssl.create_default_context()
    kontext.check_hostname = False

    verbindung = socket.create_connection((server, port), timeout=ZEITGRENZE)
    try:
        if starttls:
            # Bei STARTTLS kommt erst der IMAP-Vorspann, dann das Zertifikat.
            verbindung.recv(4096)
            verbindung.sendall(b"a001 STARTTLS\r\n")
            if b"OK" not in verbindung.recv(4096):
                return {}
        with kontext.wrap_socket(verbindung, server_hostname=server) as sicher:
            return sicher.getpeercert() or {}
    finally:
        try:
            verbindung.close()
        except OSError:
            pass


def untersuchen(server: str, port: int, *, starttls: bool = False) -> Befund:
    """Sucht einen Namen, unter dem dieser Server sauber zu erreichen ist.

    Der Rückgabewert ist ein *Vorschlag*, mehr nicht. Bestätigen muss ihn
    anschließend eine ganz gewöhnliche, vollständig geprüfte Verbindung.
    """
    befund = Befund()
    try:
        zertifikat = _zertifikat_holen(server, port, starttls)
    except (OSError, ssl.SSLError, socket.timeout):
        # Auch das Nachsehen kann scheitern. Dann bleibt es eben beim
        # ursprünglichen Fehler – eine Diagnose darf nie selbst zum
        # Problem werden.
        return befund

    befund.namen = _namen_aus_zertifikat(zertifikat)
    if not befund.namen:
        return befund

    # Der Name, unter dem der Hoster die Maschine führt, ist der beste
    # Kandidat: Er meint denselben Rechner und steht meist unter dem
    # Platzhalter des Zertifikats.
    try:
        adresse = socket.gethostbyname(server)
        befund.rueckwaerts = socket.gethostbyaddr(adresse)[0]
    except (OSError, socket.herror):
        befund.rueckwaerts = ""

    if befund.rueckwaerts and any(passt(befund.rueckwaerts, m) for m in befund.namen):
        befund.vorschlag = befund.rueckwaerts
    else:
        # Ohne Rückwärtsauflösung hilft nur ein fest eingetragener Name;
        # ein Platzhalter allein lässt sich nicht anwählen.
        for name in befund.namen:
            if not name.startswith("*."):
                befund.vorschlag = name
                break

    return befund


def erklaerung(server: str, befund: Befund) -> str:
    """Formuliert, was los ist und was hilft."""
    if not befund.namen:
        return ""

    zeilen = [
        f"Das Zertifikat gilt nicht für '{server}', sondern für: "
        f"{', '.join(befund.namen)}."
    ]
    if befund.rueckwaerts:
        zeilen.append(f"Der Server ist bekannt als '{befund.rueckwaerts}'.")

    if befund.vorschlag:
        zeilen.append(
            f"Das ist der übliche Fall bei einem Massenhoster: Der Mailserver "
            f"läuft unter dem Namen des Anbieters, '{server}' zeigt nur "
            f"dorthin. Verwenden Sie stattdessen den Servernamen "
            f"{befund.vorschlag} – das ist derselbe Rechner, nur unter dem "
            f"Namen, für den sein Zertifikat gilt."
        )
    else:
        zeilen.append(
            "Ein passender Name war nicht zu ermitteln. Der Betreiber des "
            "Servers kann sagen, unter welchem Namen er beglaubigt ist."
        )
    return "\n".join(zeilen)
