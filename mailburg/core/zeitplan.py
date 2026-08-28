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

from mailburg.core import werkzeuge

#: Wie oft abgerufen wird, wenn niemand etwas anderes sagt. Halbstündlich
#: ist bei Mail ein vernünftiger Kompromiss: neu genug, um nichts zu
#: verpassen, selten genug, um den Server nicht zu belästigen.
STANDARDTAKT = 30

DIENSTE = Path.home() / ".config" / "systemd" / "user"
EINHEIT = "mailburg-abruf"
EINHEIT_SICHERUNG = "mailburg-sicherung"

#: Wie oft gesichert wird, wenn niemand etwas anderes sagt. Täglich ist
#: bei Mail angemessen: Mehr bringt wenig, weniger lässt im Ernstfall
#: mehrere Tage Arbeit im Nichts verschwinden.
STANDARDTAKT_SICHERUNG = "täglich"

#: Was systemd unter den Bezeichnungen versteht.
TAKTE_SICHERUNG = {
    "täglich": "daily",
    "wöchentlich": "weekly",
    "monatlich": "monthly",
}


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


def _windows() -> bool:
    """Ob der Zeitplan über die Windows-Aufgabenplanung läuft.

    Als eigene Funktion, nicht als ``os.name``-Abfrage an sieben
    Stellen: So lässt sie sich in den Tests umlegen. ``os.name`` selbst
    zu verbiegen zieht pathlib mit – jeder Pfad wäre dann plötzlich ein
    ``WindowsPath``, und der lässt sich unter Linux nicht einmal
    anlegen.
    """
    return os.name == "nt"


def _systemctl(*argumente: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *argumente],
        capture_output=True, text=True, check=False, timeout=20,
        **werkzeuge.lautlos(),
    )


def moeglich() -> tuple[bool, str]:
    """Sagt, ob ein Zeitplan angelegt werden kann – und sonst warum nicht."""
    if _windows():
        from mailburg.core import aufgabenplanung

        return aufgabenplanung.moeglich()
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


def _abrufeinheit(archiv: Path) -> str:
    """Eine eigene Abrufeinheit je Archiv.

    Dieselbe Überlegung wie bei :func:`_einheitsname` für die Sicherung –
    und dieselbe Lücke, die dort schon geschlossen war und hier nicht.
    Mit einer festen Einheit überschrieb das Einrichten des zweiten
    Zeitplans den ersten: Nur ein Archiv wurde noch beliefert, und
    bemerkt hätte man es erst, wenn dort etwas fehlt.
    """
    kurz = "".join(z if z.isalnum() else "-" for z in archiv.name).strip("-")
    return f"{EINHEIT}-{kurz.lower() or 'archiv'}"


def einrichten(archiv: Path | str, takt: int = STANDARDTAKT) -> tuple[bool, str]:
    """Legt den Zeitplan an und schaltet ihn ein."""
    geht, grund = moeglich()
    if not geht:
        return False, grund

    archiv = Path(archiv).expanduser().resolve()
    if not (archiv / "archive.json").is_file():
        return False, f"In {archiv} liegt kein Archiv."
    takt = max(5, int(takt))

    if _windows():
        from mailburg.core import aufgabenplanung

        return aufgabenplanung.einrichten(archiv, takt)

    einheit = _abrufeinheit(archiv)

    DIENSTE.mkdir(parents=True, exist_ok=True)
    (DIENSTE / f"{einheit}.service").write_text(
        f"""[Unit]
Description=MailBurg: neue Mails nach {archiv.name} holen
# Ohne Netz braucht der Abruf gar nicht erst anzulaufen.
After=network-online.target

[Service]
Type=oneshot
ExecStart={_mailburg_befehl()} abrufen --leise "{archiv}"
Environment=PYTHONUNBUFFERED=1
""",
        encoding="utf-8",
    )
    (DIENSTE / f"{einheit}.timer").write_text(
        f"""[Unit]
Description=MailBurg alle {takt} Minuten nach {archiv.name} abrufen

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
    ergebnis = _systemctl("enable", "--now", f"{einheit}.timer")
    if ergebnis.returncode != 0:
        return False, (ergebnis.stderr or "").strip() or "Der Zeitplan ließ sich nicht einschalten."
    return True, f"Abruf eingerichtet: alle {takt} Minuten, solange Sie angemeldet sind."


def abschalten(archiv: Path | str | None = None) -> tuple[bool, str]:
    """Nimmt den Zeitplan zurück. Das Archiv bleibt selbstverständlich.

    Ohne Archiv wird die alte, archivlose Einheit entfernt – die aus der
    Zeit, als es nur einen Zeitplan für alles gab.
    """
    geht, grund = moeglich()
    if not geht:
        return False, grund

    if _windows():
        from mailburg.core import aufgabenplanung

        if archiv is None:
            return True, "Der regelmäßige Abruf ist abgeschaltet."
        return aufgabenplanung.abschalten(Path(archiv).expanduser().resolve())

    einheit = _abrufeinheit(Path(archiv).expanduser().resolve()) if archiv else EINHEIT
    _systemctl("disable", "--now", f"{einheit}.timer")
    for datei in (f"{einheit}.timer", f"{einheit}.service"):
        (DIENSTE / datei).unlink(missing_ok=True)
    _systemctl("daemon-reload")
    return True, "Der regelmäßige Abruf ist abgeschaltet."


def _einheitsname(archiv: Path) -> str:
    """Eine eigene Einheit je Archiv.

    Wer zwei Archive führt – ein geschäftliches und ein privates –,
    braucht zwei Zeitpläne. Mit einer festen Einheit überschriebe das
    Einrichten des zweiten den ersten, und nur eines der beiden Archive
    würde je gesichert. Bemerkt hätte das niemand: Es liegt ja eine
    Sicherung da.
    """
    kurz = "".join(z if z.isalnum() else "-" for z in archiv.name).strip("-")
    return f"{EINHEIT_SICHERUNG}-{kurz.lower() or 'archiv'}"


def sicherung_einrichten(archiv: Path | str, ziel: Path | str,
                         takt: str = STANDARDTAKT_SICHERUNG,
                         behalten: int = 7, name: str = "") -> tuple[bool, str]:
    """Legt einen Zeitplan an, der das Archiv regelmäßig wegpackt.

    Ein Backup, an das jemand denken muss, ist irgendwann keines mehr.

    ``name`` bestimmt den Dateinamen der Sicherung; ohne Angabe nimmt
    MailBurg den Namen des Archivs.
    """
    geht, grund = moeglich()
    if not geht:
        return False, grund

    archiv = Path(archiv).expanduser().resolve()
    ziel = Path(ziel).expanduser().resolve()
    if not (archiv / "archive.json").is_file():
        return False, f"In {archiv} liegt kein Archiv."
    if ziel.is_relative_to(archiv):
        # Eine Sicherung neben dem Original geht mit ihm zusammen
        # verloren - dann ist sie keine.
        return False, "Das Ziel darf nicht im Archiv selbst liegen."

    # **Den Ordner gleich auszeichnen.** Der Zeitplan prüft später, ob
    # die Marke noch da ist - fehlt sie, geht MailBurg davon aus, dass
    # der Datenträger nicht eingehängt ist, und sichert lieber gar
    # nicht. Ohne dieses Setzen hier schlüge ausgerechnet der erste Lauf
    # fehl, unmittelbar nach dem Einrichten.
    from mailburg.core import sicherung

    sicherung.marke_setzen(ziel)

    if _windows():
        from mailburg.core import aufgabenplanung

        return aufgabenplanung.sicherung_einrichten(
            archiv, ziel, takt, _haltung(behalten), name
        )

    DIENSTE.mkdir(parents=True, exist_ok=True)
    einheit = _einheitsname(archiv)
    benennung = f' --name "{name}"' if name else ""
    (DIENSTE / f"{einheit}.service").write_text(
        f"""[Unit]
Description=MailBurg: {archiv.name} sichern

[Service]
Type=oneshot
ExecStart={_mailburg_befehl()} sichern --leise {_haltung(behalten)}{benennung} "{archiv}" "{ziel}"
""",
        encoding="utf-8",
    )
    (DIENSTE / f"{einheit}.timer").write_text(
        f"""[Unit]
Description=MailBurg-Sicherung {archiv.name} ({takt})

[Timer]
OnCalendar={TAKTE_SICHERUNG.get(takt, "daily")}
# Nicht Schlag Mitternacht: Wenn alle Zeitpläne zugleich anlaufen,
# steht der Rechner. Eine halbe Stunde Streuung genügt.
RandomizedDelaySec=30m
# Holt nach, was verpasst wurde, während der Rechner aus war.
Persistent=true

[Install]
WantedBy=timers.target
""",
        encoding="utf-8",
    )

    _systemctl("daemon-reload")
    # Die *archiveigene* Einheit, nicht die Sammelbezeichnung. Geschrieben
    # wurde sie schon immer unter dem eigenen Namen; eingeschaltet wurde
    # der feste - und systemd meldete zu Recht, dass es die nicht gibt.
    ergebnis = _systemctl("enable", "--now", f"{einheit}.timer")
    if ergebnis.returncode != 0:
        return False, (ergebnis.stderr or "").strip() or "Ließ sich nicht einschalten."
    return True, f"Sicherung eingerichtet: {takt} nach {ziel}"


def _haltung(behalten: int) -> str:
    """Ersetzen oder sammeln – als Schalter für die Befehlszeile."""
    return "--ersetzen" if behalten <= 0 else f"--behalten {behalten}"


def sicherung_abschalten(archiv: Path | str) -> tuple[bool, str]:
    """Nimmt den Sicherungsplan dieses Archivs zurück."""
    geht, grund = moeglich()
    if not geht:
        return False, grund

    if _windows():
        from mailburg.core import aufgabenplanung

        return aufgabenplanung.sicherung_abschalten(
            Path(archiv).expanduser().resolve()
        )

    einheit = _einheitsname(Path(archiv).expanduser().resolve())
    _systemctl("disable", "--now", f"{einheit}.timer")
    for datei in (f"{einheit}.timer", f"{einheit}.service"):
        (DIENSTE / datei).unlink(missing_ok=True)
    _systemctl("daemon-reload")
    return True, "Die regelmäßige Sicherung ist abgeschaltet."


def sicherung_zustand(archiv: Path | str | None = None) -> Zustand:
    """Was für die Sicherung dieses Archivs eingerichtet ist."""
    geht, grund = moeglich()
    stand = Zustand(moeglich=geht, grund=grund)
    if not geht or archiv is None:
        return stand

    if _windows():
        from mailburg.core import aufgabenplanung

        stand.laeuft, stand.archiv = aufgabenplanung.sicherung_zustand(
            Path(archiv).expanduser().resolve()
        )
        return stand

    einheit = _einheitsname(Path(archiv).expanduser().resolve())
    stand.laeuft = _systemctl(
        "is-enabled", f"{einheit}.timer"
    ).stdout.strip() == "enabled"

    dienst = DIENSTE / f"{einheit}.service"
    if dienst.is_file():
        teile = [
            t for t in dienst.read_text(encoding="utf-8").split('"') if t.strip()
        ]
        if len(teile) >= 2:
            stand.archiv = teile[-1].strip()
    return stand


def zustand(archiv: Path | str | None = None) -> Zustand:
    """Was gerade eingerichtet ist – für die Anzeige in den Einstellungen."""
    geht, grund = moeglich()
    stand = Zustand(moeglich=geht, grund=grund)
    if not geht:
        return stand

    if _windows():
        from mailburg.core import aufgabenplanung

        ziel = Path(archiv).expanduser().resolve() if archiv else None
        stand.laeuft, takt, stand.archiv = aufgabenplanung.zustand(ziel)
        stand.takt = takt or STANDARDTAKT
        return stand

    einheit = _abrufeinheit(Path(archiv).expanduser().resolve()) if archiv else EINHEIT
    stand.laeuft = _systemctl(
        "is-enabled", f"{einheit}.timer"
    ).stdout.strip() == "enabled"

    dienst = DIENSTE / f"{einheit}.service"
    if dienst.is_file():
        for zeile in dienst.read_text(encoding="utf-8").splitlines():
            if zeile.startswith("ExecStart=") and '"' in zeile:
                stand.archiv = zeile.split('"')[1]

    uhr = DIENSTE / f"{einheit}.timer"
    if uhr.is_file():
        for zeile in uhr.read_text(encoding="utf-8").splitlines():
            if zeile.startswith("OnUnitActiveSec="):
                stand.takt = int(zeile.split("=")[1].rstrip("min") or STANDARDTAKT)
    return stand
