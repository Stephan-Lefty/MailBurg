"""Was zum Einrichten des Dienstes geprüft und getan werden muss.

**Ohne Qt und ohne Windows.** Jede Prüfung ist eine Funktion, die einen
:class:`Befund` zurückgibt; das Fenster in ``ui/servereinrichtung.py``
malt sie nur. Der Grund ist derselbe wie bei ``search/maske.py``: Läge
die Entscheidung im Fenster, wäre sie nur dort prüfbar – und auf einem
Linux-Rechner gar nicht.

**Warum es das gibt.** Am 2026-10-02 wurde der Windows-Dienst zum ersten
Mal eingerichtet. Von zehn Schritten verlangten acht einen abgetippten
PowerShell-Befehl, und als der Dienst nicht startete, stand der Grund in
einem Ereignisprotokoll, das man mit einem dritten Befehl durchsuchen
muss. Stephans Urteil: Das muss in ein Fenster.

**Die Reihenfolge ist Absicht.** Erst was ohne Rechte prüfbar ist
(Python, Pakete), dann das Archiv, dann der Dienst. Ein Fehler weit oben
macht alles darunter sinnlos – und eine Liste, die zehn rote Punkte
zeigt, obwohl nur der erste zählt, hilft niemandem.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from mailburg.server import einstellungen as lage
from mailburg.server.windows_dienst import NAME as DIENSTNAME

#: Die kleinste Python-Fassung, die MailBurg zusagt.
MINDESTENS = (3, 11)

#: Was der Dienst zwingend braucht, und was ihn nur besser macht.
PFLICHTPAKETE = ("starlette", "uvicorn")
KUERPAKETE = {
    "pywin32": "ohne es lässt sich kein Dienst einrichten",
    "keyring": "ohne es merkt sich MailBurg keine Postfach-Passwörter",
    "cryptography": "nötig für verschlüsselte Archive und den Tresor",
}


class Lage(Enum):
    """Wie ein Befund ausfällt."""

    GUT = "gut"
    FEHLT = "fehlt"
    ACHTUNG = "achtung"
    UNKLAR = "unklar"


@dataclass
class Befund:
    """Eine Zeile in der Prüfliste.

    ``abhilfe`` ist der Name einer Handlung, die das Fenster anbieten
    kann – oder nichts, wenn der Mensch selbst ran muss. **Der Text
    sagt, was los ist, nicht was zu tun wäre**; das steht am Knopf.
    """

    titel: str
    lage: Lage
    text: str
    abhilfe: str | None = None
    einzelheiten: str = ""


@dataclass
class Umgebung:
    """Was beim Einrichten gewählt wurde."""

    archiv: Path | None = None
    adresse: str = lage.STANDARD_ADRESSE
    anschluss: int = lage.STANDARD_ANSCHLUSS

    def als_variablen(self) -> dict[str, str]:
        return {
            lage.ARCHIV: str(self.archiv) if self.archiv else "",
            lage.ADRESSE: self.adresse,
            lage.ANSCHLUSS: str(self.anschluss),
        }


# ---------------------------------------------------------------- Prüfungen


def ist_windows() -> bool:
    return os.name == "nt"


def pruefe_system() -> Befund:
    if ist_windows():
        return Befund("Betriebssystem", Lage.GUT, "Windows.")
    return Befund(
        "Betriebssystem",
        Lage.ACHTUNG,
        f"Das hier ist kein Windows ({sys.platform}). Archiv und Zugänge "
        f"lassen sich einrichten, ein Windows-Dienst nicht.",
    )


def pruefe_python() -> Befund:
    hat = sys.version_info[:2]
    text = f"Python {hat[0]}.{hat[1]}"
    if hat >= MINDESTENS:
        return Befund("Python", Lage.GUT, f"{text} – ausreichend.")
    return Befund(
        "Python",
        Lage.FEHLT,
        f"{text}. MailBurg braucht mindestens "
        f"{MINDESTENS[0]}.{MINDESTENS[1]}.",
    )


def _vorhanden(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        # Ein kaputt installiertes Paket ist kein vorhandenes.
        return False


def pruefe_pakete() -> list[Befund]:
    """Je ein Befund für die Pflichtpakete und für jedes Kür-Paket."""
    fehlend = [n for n in PFLICHTPAKETE if not _vorhanden(n)]
    befunde = [
        Befund(
            "Pakete für den Dienst",
            Lage.FEHLT if fehlend else Lage.GUT,
            (
                f"Es fehlt: {', '.join(fehlend)}."
                if fehlend
                else "starlette und uvicorn sind da."
            ),
            abhilfe="pakete" if fehlend else None,
            einzelheiten=f"pip install {' '.join(fehlend)}" if fehlend else "",
        )
    ]

    for name, wozu in KUERPAKETE.items():
        if name == "pywin32" and not ist_windows():
            continue
        da = _vorhanden("win32serviceutil" if name == "pywin32" else name)
        befunde.append(
            Befund(
                name,
                Lage.GUT if da else Lage.ACHTUNG,
                "vorhanden." if da else f"fehlt – {wozu}.",
                abhilfe=None if da else "pakete",
                einzelheiten="" if da else f"pip install {name}",
            )
        )
    return befunde


def ist_administrator() -> bool:
    """Ob dieser Prozess erhöhte Rechte hat.

    Ohne sie lässt sich kein Dienst anlegen und keine systemweite
    Variable setzen. Unter Linux immer wahr – dort gibt es die Frage
    nicht, und der Dienstteil ist ohnehin abgeschaltet.
    """
    if not ist_windows():
        return True
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        # **Weit gefangen, mit Grund:** Diese Auskunft darf das Fenster
        # nicht umbringen. Wer sie nicht bekommt, sieht »unklar« und
        # kann es trotzdem versuchen – der Fehler käme dann vom Dienst,
        # und zwar mit einer Meldung, die mehr sagt als ein Traceback.
        return False


def pruefe_rechte() -> Befund:
    if not ist_windows():
        return Befund("Rechte", Lage.GUT, "Unter Linux nicht nötig.")
    if ist_administrator():
        return Befund("Rechte", Lage.GUT, "Als Administrator gestartet.")
    return Befund(
        "Rechte",
        Lage.FEHLT,
        "Nicht als Administrator gestartet. Dienst und systemweite "
        "Variablen bleiben gesperrt.",
        einzelheiten="Rechtsklick auf das Programm → »Als Administrator "
        "ausführen«.",
    )


def pruefe_archiv(wo: Path | None) -> Befund:
    if wo is None:
        return Befund(
            "Archiv", Lage.FEHLT, "Noch keines gewählt.", abhilfe="archiv"
        )
    if not (Path(wo) / "archive.json").is_file():
        return Befund(
            "Archiv",
            Lage.FEHLT,
            f"In »{wo}« liegt kein MailBurg-Archiv.",
            abhilfe="archiv",
            einzelheiten="Erwartet wird ein Ordner mit einer »archive.json«.",
        )
    return Befund("Archiv", Lage.GUT, str(wo))


def pruefe_zugaenge(wo: Path | None) -> Befund:
    """Ohne Zugang kommt niemand über die Anmeldeseite hinaus."""
    if wo is None or not (Path(wo) / "archive.json").is_file():
        return Befund("Zugänge", Lage.UNKLAR, "Erst ein Archiv wählen.")

    from mailburg.core.archive import Archive

    try:
        with Archive.open(wo) as archiv:
            leute = list(archiv.benutzer)
    except Exception as fehler:  # noqa: BLE001
        return Befund(
            "Zugänge", Lage.UNKLAR, f"Nicht lesbar: {fehler}"
        )

    mit_passwort = [b for b in leute if b.pruefwert]
    if not leute:
        return Befund(
            "Zugänge",
            Lage.FEHLT,
            "Keiner eingerichtet – niemand käme über die Anmeldeseite.",
            abhilfe="zugang",
        )
    if not mit_passwort:
        return Befund(
            "Zugänge",
            Lage.FEHLT,
            f"{len(leute)} angelegt, aber keiner hat ein Passwort.",
            abhilfe="zugang",
        )

    blind = [b for b in mit_passwort if not (b.alle_postfaecher or b.postfaecher)]
    if blind:
        return Befund(
            "Zugänge",
            Lage.ACHTUNG,
            f"{len(mit_passwort)} mit Passwort, davon {len(blind)} ohne "
            f"Postfächer – die sehen nichts.",
            abhilfe="zugang",
        )
    return Befund(
        "Zugänge", Lage.GUT, f"{len(mit_passwort)} mit Passwort."
    )


# ------------------------------------------------------------ Umgebung


def gesetzte_variablen() -> dict[str, str]:
    """Was systemweit hinterlegt ist – aus der Registry, nicht aus os.environ.

    **Der Unterschied ist der Kern des Problems.** ``os.environ`` zeigt,
    was *dieser* Prozess beim Start mitbekommen hat. Nach einem ``setx``
    steht der neue Wert in der Registry und in keinem laufenden Prozess.
    Wer die eigene Umgebung befragt, prüft seine Erinnerung.
    """
    if not ist_windows():
        return {k: os.environ.get(k, "") for k in
                (lage.ARCHIV, lage.ADRESSE, lage.ANSCHLUSS)}

    import winreg

    pfad = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    werte = {}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, pfad) as schluessel:
            for name in (lage.ARCHIV, lage.ADRESSE, lage.ANSCHLUSS):
                try:
                    werte[name] = winreg.QueryValueEx(schluessel, name)[0]
                except FileNotFoundError:
                    werte[name] = ""
    except OSError:
        return {}
    return werte


def variablen_setzen(umgebung: Umgebung) -> list[str]:
    """Schreibt die Einstellungen – systemweit **und** an den Dienst.

    **Zwei Orte, und beide haben einen Grund.** Systemweit, damit ein
    neu geöffnetes Fenster und ``mailburg server`` von Hand sie sehen.
    Am Dienstschlüssel, weil der Dienstmanager seine Umgebung beim
    Hochfahren einliest: Ein frisches ``setx`` erreicht einen Dienst
    sonst erst nach einem Neustart des Servers.

    **Der zweite Weg ist nicht erprobt** – er stammt aus der
    Windows-Dokumentation zum ``Environment``-Wert unter dem
    Dienstschlüssel, nicht aus einem Lauf. Deshalb beides: Greift er
    nicht, hilft spätestens der Neustart.

    Gibt zurück, was getan wurde – für das Protokollfenster.
    """
    getan = []
    if not ist_windows():
        for name, wert in umgebung.als_variablen().items():
            os.environ[name] = wert
            getan.append(f"{name}={wert} (nur in diesem Prozess)")
        return getan

    import winreg

    pfad = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE, pfad, 0, winreg.KEY_SET_VALUE
    ) as schluessel:
        for name, wert in umgebung.als_variablen().items():
            winreg.SetValueEx(schluessel, name, 0, winreg.REG_SZ, wert)
            os.environ[name] = wert
            getan.append(f"systemweit: {name}={wert}")

    try:
        dienst = rf"SYSTEM\CurrentControlSet\Services\{DIENSTNAME}"
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, dienst, 0, winreg.KEY_SET_VALUE
        ) as schluessel:
            zeilen = [f"{n}={w}" for n, w in umgebung.als_variablen().items()]
            winreg.SetValueEx(
                schluessel, "Environment", 0, winreg.REG_MULTI_SZ, zeilen
            )
            getan.append(f"am Dienst »{DIENSTNAME}«: {len(zeilen)} Werte")
    except OSError as fehler:
        # Der Dienst ist vielleicht noch gar nicht angelegt – kein Fehler,
        # sondern die normale Reihenfolge beim ersten Einrichten.
        getan.append(f"am Dienst noch nicht: {fehler}")

    return getan


# -------------------------------------------------------------- Dienst


def dienst_zustand() -> tuple[Lage, str]:
    """Läuft er, steht er, oder gibt es ihn gar nicht?"""
    if not ist_windows():
        return Lage.UNKLAR, "Windows-Dienste gibt es hier nicht."

    try:
        import win32service
        import win32serviceutil
    except ImportError:
        return Lage.UNKLAR, "Ohne pywin32 nicht feststellbar."

    try:
        stand = win32serviceutil.QueryServiceStatus(DIENSTNAME)[1]
    except Exception:  # noqa: BLE001
        return Lage.FEHLT, "Nicht eingerichtet."

    if stand == win32service.SERVICE_RUNNING:
        return Lage.GUT, "Läuft."
    if stand == win32service.SERVICE_START_PENDING:
        return Lage.ACHTUNG, "Startet gerade."
    return Lage.FEHLT, "Eingerichtet, läuft aber nicht."


def pruefe_dienst() -> Befund:
    zustand, text = dienst_zustand()
    abhilfe = None
    if zustand is Lage.FEHLT:
        abhilfe = "dienst_anlegen" if "Nicht eingerichtet" in text else "dienst_start"
    return Befund("Dienst", zustand, text, abhilfe=abhilfe)


def _dienst_befehl(was: str) -> tuple[bool, str]:
    """Ruft ``windows_dienst`` in einem eigenen Prozess auf.

    **Nicht im eigenen**: ``HandleCommandLine`` beendet den Prozess, in
    dem es läuft. Ein Fenster, das sich beim Starten des Dienstes selbst
    schließt, wäre eine denkwürdige Bedienung.
    """
    from mailburg.core import werkzeuge

    befehl = [sys.executable, "-m", "mailburg.server.windows_dienst", was]
    try:
        lauf = subprocess.run(
            befehl, capture_output=True, text=True, timeout=120,
            # **Kodierung und Fensterunterdrückung aus dem Kern.** Ohne
            # das Erste kommt »enth„lt« statt »enthält« an (2026-08-30,
            # schtasks.exe); ohne das Zweite blitzt bei jedem Knopfdruck
            # ein schwarzes Fenster auf.
            **werkzeuge.konsolenkodierung(),
            **werkzeuge.lautlos(),
        )
    except (OSError, subprocess.SubprocessError) as fehler:
        return False, str(fehler)
    ausgabe = (lauf.stdout + lauf.stderr).strip()
    return lauf.returncode == 0, ausgabe or f"Rückgabewert {lauf.returncode}"


def dienst_anlegen() -> tuple[bool, str]:
    return _dienst_befehl("install")


def dienst_starten() -> tuple[bool, str]:
    return _dienst_befehl("start")


def dienst_stoppen() -> tuple[bool, str]:
    return _dienst_befehl("stop")


def dienst_entfernen() -> tuple[bool, str]:
    return _dienst_befehl("remove")


# ------------------------------------------------------- Weboberfläche


def erreichbar(umgebung: Umgebung, zeit: float = 2.0) -> Befund:
    """Antwortet die Weboberfläche?

    Gefragt wird ``/lebt`` – die eine Route, die ohne Anmeldung
    antwortet. Über ``127.0.0.1``, auch wenn der Dienst im Netz lauscht:
    Von hier aus ist das der kürzeste Weg, und er sagt dasselbe.
    """
    import json
    import urllib.error
    import urllib.request

    ziel = f"http://127.0.0.1:{umgebung.anschluss}/lebt"
    try:
        with urllib.request.urlopen(ziel, timeout=zeit) as antwort:  # noqa: S310
            daten = json.loads(antwort.read().decode("utf-8"))
    except urllib.error.URLError as fehler:
        return Befund(
            "Weboberfläche",
            Lage.FEHLT,
            f"Antwortet nicht auf Port {umgebung.anschluss}.",
            einzelheiten=str(fehler.reason),
        )
    except (OSError, ValueError) as fehler:
        return Befund("Weboberfläche", Lage.FEHLT, str(fehler))

    if daten.get("lebt"):
        return Befund(
            "Weboberfläche",
            Lage.GUT,
            f"Antwortet auf http://127.0.0.1:{umgebung.anschluss}/",
        )
    return Befund("Weboberfläche", Lage.ACHTUNG, "Antwortet seltsam.")


# ------------------------------------------------- Ereignisprotokoll


def ereignisse(anzahl: int = 20) -> list[str]:
    """Die letzten Meldungen des Dienstes aus dem Ereignisprotokoll.

    **Das ist der eigentliche Gewinn dieses Fensters.** Bis hierher
    musste man wissen, dass es ein Ereignisprotokoll gibt, dass der
    Dienst dorthin schreibt und wie man es mit PowerShell durchsucht.
    Am 2026-10-02 lag genau dort die Ursache eines Fehlstarts – drei
    Befehle von dem entfernt, der ihn suchte.
    """
    if not ist_windows():
        return []

    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return ["PowerShell nicht gefunden."]

    skript = (
        f"Get-WinEvent -LogName Application -MaxEvents 200 "
        f"| Where-Object {{ $_.ProviderName -eq '{DIENSTNAME}' }} "
        f"| Select-Object -First {anzahl} "
        f"| ForEach-Object {{ \"$($_.TimeCreated)  $($_.Message)\" }}"
    )
    from mailburg.core import werkzeuge

    try:
        lauf = subprocess.run(
            [powershell, "-NoProfile", "-Command", skript],
            capture_output=True, text=True, timeout=60,
            **werkzeuge.konsolenkodierung(),
            **werkzeuge.lautlos(),
        )
    except (OSError, subprocess.SubprocessError) as fehler:
        return [f"Nicht lesbar: {fehler}"]

    zeilen = [z.rstrip() for z in lauf.stdout.splitlines() if z.strip()]
    return zeilen or ["Keine Einträge – der Dienst hat noch nichts gemeldet."]


# ----------------------------------------------------------- Zusammen


@dataclass
class Gesamtbild:
    """Alle Befunde auf einmal."""

    befunde: list[Befund] = field(default_factory=list)

    @property
    def bereit(self) -> bool:
        """Ob der Dienst laufen könnte – nichts Zwingendes fehlt."""
        return not any(b.lage is Lage.FEHLT for b in self.befunde)

    def mit_titel(self, titel: str) -> Befund | None:
        for b in self.befunde:
            if b.titel == titel:
                return b
        return None


def alles_pruefen(umgebung: Umgebung) -> Gesamtbild:
    """Die ganze Liste, in der Reihenfolge, in der sie abzuarbeiten ist."""
    befunde = [pruefe_system(), pruefe_python()]
    befunde.extend(pruefe_pakete())
    befunde.append(pruefe_rechte())
    befunde.append(pruefe_archiv(umgebung.archiv))
    befunde.append(pruefe_zugaenge(umgebung.archiv))
    if ist_windows():
        befunde.append(pruefe_dienst())
    befunde.append(erreichbar(umgebung))
    return Gesamtbild(befunde)
