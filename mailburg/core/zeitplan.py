"""Den regelmäßigen Abruf einrichten – ohne Umweg über das Terminal.

Bisher stand am Ende der grafischen Einrichtung der Rat, den Hintergrund-
abruf mit ``./install.sh --zeitsteuerung`` anzuschalten. Das setzt voraus,
dass jemand das Quellverzeichnis zur Hand hat – wer MailBurg installiert
hat, hat es gerade nicht. Ein Programm, das den Anwender für einen
Handgriff ins Terminal schickt, den es selbst tun kann, schiebt ihm seine
eigene Arbeit zu.

Angelegt werden zwei gewöhnliche Textdateien unter
``~/.config/systemd/user``. Nichts davon braucht Verwaltungsrechte, und
alles lässt sich mit einem Texteditor nachlesen – wer wissen will, was da
regelmäßig läuft, soll es sehen können.

**Der Abruf hängt an der angemeldeten Sitzung.** Die Passwörter liegen im
Schlüsselbund, und der öffnet sich erst mit der Anmeldung. Ein Zeitplan,
der nachts bei ausgeschaltetem Rechner laufen soll, läuft nicht. Deshalb
holt ``Persistent=true`` versäumte Läufe nach, sobald sich jemand anmeldet.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: Wie oft abgerufen wird, wenn niemand etwas anderes sagt. Halbstündlich
#: ist bei Mail ein vernünftiger Kompromiss: neu genug, um nichts zu
#: verpassen, selten genug, um den Server nicht zu belästigen.
STANDARDTAKT = 30

DIENSTE = Path.home() / ".config" / "systemd" / "user"
EINHEIT = "mailburg-abruf"


@dataclass
class Zustand:
    """Was gerade eingerichtet ist."""

    moeglich: bool = False
    """Ob sich auf diesem System überhaupt ein Zeitplan anlegen lässt."""

    laeuft: bool = False
    archiv: str = ""
    takt: int = STANDARDTAKT
    grund: str = ""
    """Warum es nicht geht – für die Oberfläche, in ganzen Sätzen."""


def _systemctl(*argumente: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *argumente],
        capture_output=True, text=True, check=False, timeout=20,
    )


def moeglich() -> tuple[bool, str]:
    """Sagt, ob ein Zeitplan angelegt werden kann – und sonst warum nicht."""
    if os.name == "nt":
        return False, (
            "Unter Windows richtet MailBurg den regelmäßigen Abruf noch "
            "nicht selbst ein. Bis dahin geht es über die Aufgabenplanung; "
            "die Anleitung liegt bei der Doku."
        )
    if shutil.which("systemctl") is None:
        return False, (
            "Auf diesem System gibt es kein systemd. Der Abruf lässt sich "
            "dann über die Zeitsteuerung Ihrer Arbeitsumgebung starten – "
            "der Befehl dafür ist »mailburg abrufen«."
        )
    if _systemctl("--version").returncode != 0:
        return False, (
            "Die Benutzerdienste von systemd antworten nicht. Der Abruf "
            "lässt sich weiterhin von Hand starten."
        )
    return True, ""


def _mailburg_befehl() -> str:
    """Der Pfad zum Programm, so wie systemd ihn später braucht.

    ``mailburg`` allein genügt nicht: Ein Dienst startet ohne die
    ``PATH``-Ergänzungen einer Anmeldesitzung. Steht dort nur der Name,
    läuft der Abruf monatelang gar nicht, und niemand merkt es.
    """
    gefunden = shutil.which("mailburg")
    if gefunden:
        return gefunden
    return str(Path.home() / ".local" / "bin" / "mailburg")


def einrichten(archiv: Path | str, takt: int = STANDARDTAKT) -> tuple[bool, str]:
    """Legt den Zeitplan an und schaltet ihn ein."""
    geht, grund = moeglich()
    if not geht:
        return False, grund

    archiv = Path(archiv).expanduser().resolve()
    if not (archiv / "archive.json").is_file():
        return False, f"In {archiv} liegt kein Archiv."
    takt = max(5, int(takt))

    DIENSTE.mkdir(parents=True, exist_ok=True)
    (DIENSTE / f"{EINHEIT}.service").write_text(
        f"""[Unit]
Description=MailBurg: neue Mails ins Archiv holen
# Ohne Netz braucht der Abruf gar nicht erst anzulaufen.
After=network-online.target

[Service]
Type=oneshot
ExecStart={_mailburg_befehl()} abrufen --leise "{archiv}"
Environment=PYTHONUNBUFFERED=1
""",
        encoding="utf-8",
    )
    (DIENSTE / f"{EINHEIT}.timer").write_text(
        f"""[Unit]
Description=MailBurg alle {takt} Minuten abrufen

[Timer]
# Nicht sofort beim Anmelden: Erst soll der Rechner hochkommen.
OnBootSec=5min
# Gerechnet ab dem Ende des letzten Laufs. Damit überholt sich der Abruf
# nie selbst, auch wenn ein Durchgang länger dauert als das Intervall.
OnUnitActiveSec={takt}min
# Damit nicht alle Postfächer auf die Sekunde genau angefragt werden.
RandomizedDelaySec=2m
# Holt nach, was verpasst wurde, während der Rechner aus war.
Persistent=true

[Install]
WantedBy=timers.target
""",
        encoding="utf-8",
    )

    _systemctl("daemon-reload")
    ergebnis = _systemctl("enable", "--now", f"{EINHEIT}.timer")
    if ergebnis.returncode != 0:
        return False, (ergebnis.stderr or "").strip() or "Der Zeitplan ließ sich nicht einschalten."
    return True, f"Abruf eingerichtet: alle {takt} Minuten, solange Sie angemeldet sind."


def abschalten() -> tuple[bool, str]:
    """Nimmt den Zeitplan zurück. Das Archiv bleibt selbstverständlich."""
    geht, grund = moeglich()
    if not geht:
        return False, grund
    _systemctl("disable", "--now", f"{EINHEIT}.timer")
    for datei in (f"{EINHEIT}.timer", f"{EINHEIT}.service"):
        (DIENSTE / datei).unlink(missing_ok=True)
    _systemctl("daemon-reload")
    return True, "Der regelmäßige Abruf ist abgeschaltet."


def zustand() -> Zustand:
    """Was gerade eingerichtet ist – für die Anzeige in den Einstellungen."""
    geht, grund = moeglich()
    stand = Zustand(moeglich=geht, grund=grund)
    if not geht:
        return stand

    stand.laeuft = _systemctl("is-enabled", f"{EINHEIT}.timer").stdout.strip() == "enabled"

    dienst = DIENSTE / f"{EINHEIT}.service"
    if dienst.is_file():
        for zeile in dienst.read_text(encoding="utf-8").splitlines():
            if zeile.startswith("ExecStart=") and '"' in zeile:
                stand.archiv = zeile.split('"')[1]

    uhr = DIENSTE / f"{EINHEIT}.timer"
    if uhr.is_file():
        for zeile in uhr.read_text(encoding="utf-8").splitlines():
            if zeile.startswith("OnUnitActiveSec="):
                stand.takt = int(zeile.split("=")[1].rstrip("min") or STANDARDTAKT)
    return stand
