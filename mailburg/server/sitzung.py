"""Anmeldung und Sitzung.

**Der Sitzungsschlüssel entsteht beim Start und wird nicht aufbewahrt.**
Ein Neustart des Dienstes meldet damit alle ab. Das klingt nach einem
Mangel und ist keiner: Ein Archivserver wird selten neu gestartet, und
ein Schlüssel, der nirgends liegt, kann auch nirgends abhandenkommen.
Ein weiterer Schlüssel, der verwaltet, gesichert und irgendwann
gewechselt werden müsste, wäre der schlechtere Tausch.

**Warum Fernet und nicht ein selbstgebautes Cookie.** Ein signiertes
Cookie ist im Kern ein HMAC – überschaubar genug, dass die Versuchung
naheliegt, es selbst zu schreiben. Nur gehören zu einer Sitzung auch
Ablaufzeit, Erneuerung und eine Kodierung, und dort schleichen sich die
Fehler ein. ``cryptography`` liegt für den Tresor ohnehin bei und
bringt beides mit: Signatur und Ablauf in einem.

**Anmeldeversuche werden begrenzt.** Ohne das probiert jemand in Ruhe
Passwörter durch – bei einem Dienst, der aus dem Netz erreichbar ist,
ist das keine Frage des Ob.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

#: Wie lange eine Sitzung gilt, in Sekunden. Acht Stunden – ein
#: Arbeitstag. Danach wieder anmelden.
DAUER = 8 * 60 * 60

#: Der Name des Cookies. Mit ``__Host-`` würde er strengere Regeln
#: erzwingen, verlangt dafür aber zwingend HTTPS – und im Firmennetz
#: hinter einem Reverse Proxy ist das nicht immer gegeben.
COOKIE = "mailburg_sitzung"

#: So oft darf ein Anmeldename in einem Zeitfenster scheitern.
VERSUCHE = 5
FENSTER = 5 * 60


class Anmeldesperre(RuntimeError):
    """Zu viele Fehlversuche in kurzer Zeit."""


@dataclass
class Sitzungen:
    """Verwaltet Anmeldungen für einen laufenden Dienst."""

    #: Der Schlüssel dieser Laufzeit. Siehe oben: bewusst flüchtig.
    schluessel: bytes = b""

    #: Fehlversuche je Anmeldename, als Zeitpunkte.
    _fehl: dict[str, list[float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.schluessel:
            from cryptography.fernet import Fernet

            self.schluessel = Fernet.generate_key()

    @property
    def _schloss(self):
        from cryptography.fernet import Fernet

        return Fernet(self.schluessel)

    # -- Anmeldeversuche --------------------------------------------------

    def _gesperrt(self, name: str, jetzt: float) -> bool:
        versuche = [t for t in self._fehl.get(name, []) if jetzt - t < FENSTER]
        self._fehl[name] = versuche
        return len(versuche) >= VERSUCHE

    def _gescheitert(self, name: str, jetzt: float) -> None:
        self._fehl.setdefault(name, []).append(jetzt)

    def anmelden(self, liste, name: str, passwort: str, jetzt=None):
        """Prüft die Anmeldung und gibt den Benutzer zurück – oder nichts.

        Wirft :class:`Anmeldesperre`, wenn zu oft hintereinander ein
        falsches Passwort kam. Gezählt wird je Anmeldename, nicht je
        Verbindung: Wer von zehn Rechnern aus probiert, soll nicht
        zehnmal so viele Versuche haben.
        """
        jetzt = time.time() if jetzt is None else jetzt
        schluessel = (name or "").strip().casefold()

        if self._gesperrt(schluessel, jetzt):
            raise Anmeldesperre(
                "Zu viele Fehlversuche. Bitte in einigen Minuten erneut "
                "versuchen."
            )

        benutzer = liste.anmelden(name, passwort)
        if benutzer is None:
            self._gescheitert(schluessel, jetzt)
            return None

        self._fehl.pop(schluessel, None)
        return benutzer

    # -- Das Cookie -------------------------------------------------------

    def ausstellen(self, benutzer) -> str:
        """Der Inhalt des Sitzungscookies für einen angemeldeten Benutzer.

        Darin steht nur der Anmeldename, nicht seine Rechte. **Das ist
        wesentlich:** Stünden die Rechte im Cookie, gälte eine
        Rechteänderung erst nach der nächsten Anmeldung – ein entzogenes
        Recht bliebe stundenlang wirksam. So wird bei jeder Anfrage neu
        im Archiv nachgesehen.
        """
        nutzlast = json.dumps({"name": benutzer.name}).encode("utf-8")
        return self._schloss.encrypt(nutzlast).decode("ascii")

    def einloesen(self, roh: str | None, liste):
        """Der angemeldete Benutzer zu einem Cookie – oder nichts.

        Gibt auch dann nichts zurück, wenn es den Zugang nicht mehr gibt
        oder er stillgelegt wurde. Ein Cookie ist kein Ausweis auf Zeit;
        entscheidend ist, was jetzt im Archiv steht.
        """
        if not roh:
            return None

        from cryptography.fernet import InvalidToken

        try:
            nutzlast = self._schloss.decrypt(roh.encode("ascii"), ttl=DAUER)
            name = json.loads(nutzlast).get("name", "")
        except (InvalidToken, ValueError, TypeError, UnicodeDecodeError):
            return None

        benutzer = liste.finden(name)
        if benutzer is None or not benutzer.aktiv:
            return None
        return benutzer
