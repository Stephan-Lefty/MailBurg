"""Was der Dienst wissen muss, bevor er startet.

Ein Dienst hat niemanden, den er fragen kann. Alles, was die
Desktop-Fassung erfragt – welches Archiv, wohin gesichert wird –, muss
hier vorher feststehen.

**Aus Umgebungsvariablen, nicht aus einer eigenen Datei.** Das ist der
Weg, den systemd, Docker und die Windows-Dienstverwaltung alle
gleichermaßen kennen; eine zusätzliche Konfigurationsdatei wäre ein
vierter Ort, an dem etwas stehen kann. Der Hauptschlüssel des Tresors
geht denselben Weg (siehe :mod:`mailburg.core.tresor`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: Welches Archiv der Dienst ausliefert.
ARCHIV = "MAILBURG_ARCHIV"

#: Auf welcher Adresse er lauscht.
ADRESSE = "MAILBURG_ADRESSE"
ANSCHLUSS = "MAILBURG_PORT"

#: **Die Vorgabe ist der eigene Rechner.** Ein Archivdienst, der beim
#: ersten Start ungefragt im ganzen Netz lauscht, ist eine böse
#: Überraschung. Wer ihn im Firmennetz erreichbar machen will, sagt es
#: ausdrücklich – und hat dann hoffentlich vorher über den Rest
#: nachgedacht.
STANDARD_ADRESSE = "127.0.0.1"
STANDARD_ANSCHLUSS = 8383


class Fehlt(RuntimeError):
    """Eine Angabe fehlt, ohne die der Dienst nicht starten kann."""


@dataclass(frozen=True)
class Serverlage:
    """Wo der Dienst steht und was er ausliefert."""

    archiv: Path
    adresse: str = STANDARD_ADRESSE
    anschluss: int = STANDARD_ANSCHLUSS

    @property
    def oeffentlich(self) -> bool:
        """Ob er über den eigenen Rechner hinaus erreichbar ist."""
        return self.adresse not in ("127.0.0.1", "::1", "localhost")

    @classmethod
    def aus_umgebung(cls) -> Serverlage:
        ort = os.environ.get(ARCHIV, "").strip()
        if not ort:
            raise Fehlt(
                f"Es ist kein Archiv angegeben. Setzen Sie »{ARCHIV}« auf "
                f"den Ordner, den der Dienst ausliefern soll."
            )

        archiv = Path(ort).expanduser()
        if not (archiv / "archive.json").is_file():
            raise Fehlt(
                f"In »{archiv}« liegt kein MailBurg-Archiv. Erwartet wird "
                f"ein Ordner mit einer »archive.json« darin."
            )

        roh = os.environ.get(ANSCHLUSS, "").strip()
        try:
            anschluss = int(roh) if roh else STANDARD_ANSCHLUSS
        except ValueError:
            raise Fehlt(f"»{ANSCHLUSS}={roh}« ist keine Portnummer.") from None
        if not 1 <= anschluss <= 65535:
            raise Fehlt(f"Der Port {anschluss} liegt außerhalb des Bereichs.")

        return cls(
            archiv=archiv,
            adresse=os.environ.get(ADRESSE, "").strip() or STANDARD_ADRESSE,
            anschluss=anschluss,
        )


def anschluss_frei(adresse: str, anschluss: int) -> bool:
    """Ob auf diesem Port noch nichts lauscht.

    **Warum MailBurg das selbst prüft.** uvicorn meldet sonst
    ``[Errno 98] error while attempting to bind on address`` – eine
    Zeile, die einem Menschen nicht sagt, was los ist und schon gar
    nicht, was zu tun wäre. Am 2026-08-31 ist Stephan genau darüber
    gestolpert: Zwei MailBurg-Server auf demselben Port, und die
    Meldung nannte weder den einen noch den anderen.

    Die Prüfung ist eine Auskunft, keine Reservierung: Zwischen ihr und
    dem Start kann sich jemand dazwischenschieben. Dann greift immer
    noch uvicorns Meldung – nur ist der häufige Fall dann schon
    abgefangen.
    """
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as buchse:
        buchse.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            buchse.bind((adresse, anschluss))
        except OSError:
            return False
    return True
