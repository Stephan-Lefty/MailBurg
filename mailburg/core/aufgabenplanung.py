"""Der regelmäßige Abruf unter Windows – über die Aufgabenplanung.

Das Gegenstück zu den systemd-Timern in :mod:`mailburg.core.zeitplan`.
Bis zum 2026-08-28 stand an dieser Stelle ein grauer Kasten mit dem Satz
»Unter Windows richtet MailBurg den regelmäßigen Abruf noch nicht selbst
ein«. Stephan hat ihn zwei Tage hintereinander gesehen und beim zweiten
Mal gesagt, was zu sagen war: »Und ich konnte die Abrufzeit nicht
einstellen!«

Ein Archivprogramm, das man täglich von Hand anstoßen muss, wird nach
zwei Wochen nicht mehr angestoßen. Dann fehlt Post, und gemerkt hat es
niemand.

**Wie es gemacht wird.** Angelegt wird eine gewöhnliche Aufgabe im
Ordner ``MailBurg`` der Windows-Aufgabenplanung, sichtbar und löschbar
wie jede andere. Der Umweg über eine XML-Datei statt über die Schalter
von ``schtasks`` hat einen Grund: Nur so lässt sich
``StartWhenAvailable`` setzen – das Windows-Gegenstück zu systemds
``Persistent=true``. Ohne das fällt eine tägliche Sicherung schlicht
aus, wenn der Rechner zur fraglichen Zeit ausgeschaltet war, und zwar
stillschweigend.

**Ohne Verwaltungsrechte.** Die Aufgabe läuft als der angemeldete
Benutzer und nur, während er angemeldet ist (``InteractiveToken``). Das
ist keine Bequemlichkeit, sondern Notwendigkeit: Die Passwörter liegen
in der Anmeldeinformationsverwaltung, und die öffnet sich erst mit der
Anmeldung. Eine Aufgabe, die nachts im Dienstkontext läuft, käme an
kein einziges Postfach heran.
"""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from mailburg.core import werkzeuge

#: Der Ordner, in dem die Aufgaben in der Aufgabenplanung erscheinen.
#: Ein eigener Ordner, damit man sie beisammen findet – und damit
#: erkennbar bleibt, was MailBurg angelegt hat und was nicht.
ORDNER = "MailBurg"

#: Wohin die XML-Vorlagen geschrieben werden. Sie sind nicht bloß
#: Zwischenschritt: MailBurg liest später aus ihnen zurück, was
#: eingerichtet ist – genauso, wie die Linux-Fassung ihre
#: ``.timer``-Dateien liest.
def _ablage() -> Path:
    wurzel = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(wurzel) / "MailBurg" / "aufgaben"


#: Was die Aufgabenplanung unter den Bezeichnungen versteht.
TAKTE_SICHERUNG = {
    "täglich": ("DAYS", 1),
    "wöchentlich": ("DAYS", 7),
    "monatlich": ("DAYS", 30),
}


def moeglich() -> tuple[bool, str]:
    """Ob sich auf diesem Windows eine Aufgabe anlegen lässt."""
    if os.name != "nt":
        return False, "Die Aufgabenplanung gibt es nur unter Windows."
    if _schtasks_pfad() is None:
        return False, (
            "Die Windows-Aufgabenplanung (schtasks.exe) ließ sich nicht "
            "finden. Der Abruf lässt sich weiterhin von Hand starten."
        )
    return True, ""


def _schtasks_pfad() -> str | None:
    """``schtasks.exe`` – bevorzugt mit vollem Pfad.

    ``shutil.which`` allein genügt nicht: In einer gepackten Anwendung
    kann ``PATH`` beschnitten sein. Der feste Pfad unter ``System32``
    steht auf jedem Windows.
    """
    gefunden = shutil.which("schtasks")
    if gefunden:
        return gefunden
    fest = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "schtasks.exe"
    return str(fest) if fest.is_file() else None


def _schtasks(*argumente: str) -> subprocess.CompletedProcess:
    """Ruft ``schtasks`` auf, ohne ein Fenster aufblitzen zu lassen.

    Ohne ``CREATE_NO_WINDOW`` erscheint bei jedem Aufruf für einen
    Sekundenbruchteil eine schwarze Konsole. In einem Programm mit
    Oberfläche sieht das nach Fehlfunktion aus.
    """
    pfad = _schtasks_pfad() or "schtasks"
    return subprocess.run(
        [pfad, *argumente],
        capture_output=True, text=True, check=False, timeout=30,
        errors="replace",
        **werkzeuge.lautlos(),
    )


def _befehl() -> tuple[str, str]:
    """Was aufgerufen wird: Programm und Anfang der Argumente.

    Drei Fälle, und beim mittleren steckt der Unterschied zwischen
    »läuft unbemerkt« und »blitzt alle 30 Minuten schwarz auf«:

    * **Gepackte Fassung** – ``MailBurg.exe`` selbst. Sie ist ohne
      Konsole gebaut, also bleibt der Abruf unsichtbar.
    * **Über pip installiert** – dann gäbe es ``mailburg.exe``, aber das
      ist ein Konsolenprogramm. Alle halbe Stunde ein aufpoppendes
      schwarzes Fenster ist keine Lösung; deshalb lieber
      ``pythonw.exe -m mailburg``, das schweigt.
    * **Aus dem Quellverzeichnis** – derselbe Weg, notfalls mit
      ``python.exe``.
    """
    if getattr(sys, "frozen", False):
        return sys.executable, ""

    lautlos = Path(sys.executable).with_name("pythonw.exe")
    deuter = str(lautlos) if lautlos.is_file() else sys.executable
    return deuter, "-m mailburg"


def _aufgabenname(art: str, archiv: Path) -> str:
    """Ein eigener Name je Archiv – aus demselben Grund wie unter Linux.

    Wer geschäftlich und privat trennt, führt zwei Archive und braucht
    zwei Zeitpläne. Mit einem festen Namen überschriebe das Einrichten
    des zweiten den ersten, und nur eines der beiden würde noch
    beliefert. Auffallen würde das erst, wenn dort etwas fehlt.
    """
    kurz = "".join(z if z.isalnum() or z in " -_" else "-" for z in archiv.name)
    return f"{ORDNER}\\{art} - {kurz.strip() or 'Archiv'}"


def _xml(beschreibung: str, programm: str, argumente: str,
         wiederholung: str = "", taeglich: int = 0,
         uhrzeit: str = "03:00") -> str:
    """Baut die Aufgabenbeschreibung.

    ``wiederholung`` ist eine ISO-8601-Dauer (``PT30M``) für den Abruf,
    ``taeglich`` ein Abstand in Tagen für die Sicherung.
    """
    # Ein fester, längst vergangener Beginn. Die Aufgabenplanung rechnet
    # von dort aus weiter; ein Datum in der Zukunft ließe die Aufgabe
    # bis dahin schlafen.
    beginn = f"2020-01-01T{uhrzeit}:00"

    if wiederholung:
        ausloeser = f"""    <TimeTrigger>
      <StartBoundary>2020-01-01T00:00:00</StartBoundary>
      <Repetition>
        <Interval>{wiederholung}</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <Enabled>true</Enabled>
    </TimeTrigger>"""
    else:
        ausloeser = f"""    <CalendarTrigger>
      <StartBoundary>{beginn}</StartBoundary>
      <ScheduleByDay>
        <DaysInterval>{taeglich or 1}</DaysInterval>
      </ScheduleByDay>
      <Enabled>true</Enabled>
    </CalendarTrigger>"""

    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>MailBurg</Author>
    <Description>{escape(beschreibung)}</Description>
  </RegistrationInfo>
  <Triggers>
{ausloeser}
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(_benutzer())}</UserId>
      <!-- Nur bei angemeldetem Benutzer: Die Passwoerter liegen in der
           Anmeldeinformationsverwaltung, und die oeffnet sich erst mit
           der Anmeldung. -->
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <!-- Ueberholt sich nie selbst, auch wenn ein Durchgang laenger
         dauert als der Abstand. -->
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <!-- Ein Notebook im Akkubetrieb soll seine Post trotzdem holen. -->
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <!-- Das Gegenstueck zu systemds Persistent=true: holt nach, was
         waehrend ausgeschaltetem Rechner ausfiel. -->
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <!-- Damit ein haengender Server die Aufgabe nicht ewig blockiert. -->
    <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
    <!-- Damit nicht alle Rechner auf die Sekunde genau anfragen. -->
    <RandomDelay>PT2M</RandomDelay>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(programm)}</Command>
      <Arguments>{escape(argumente)}</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def _benutzer() -> str:
    """Wer die Aufgabe ausführt – mit Domäne, wenn es eine gibt."""
    name = os.environ.get("USERNAME") or getpass.getuser()
    domaene = os.environ.get("USERDOMAIN", "")
    return f"{domaene}\\{name}" if domaene else name


def _anlegen(name: str, xml: str) -> tuple[bool, str]:
    """Schreibt die Beschreibung weg und meldet sie an."""
    ablage = _ablage()
    ablage.mkdir(parents=True, exist_ok=True)
    # Der Dateiname darf den Ordnertrenner der Aufgabenplanung nicht
    # enthalten - sonst landete die Datei in einem Unterverzeichnis, das
    # es nicht gibt.
    datei = ablage / f"{name.replace(chr(92), '_')}.xml"

    # **UTF-16 mit Vorzeichen.** Die Aufgabenplanung liest die Datei
    # sonst als Zeichensalat ein und lehnt sie mit einer Fehlermeldung
    # ab, die den Grund nicht nennt.
    datei.write_text(xml, encoding="utf-16")

    ergebnis = _schtasks("/Create", "/TN", name, "/XML", str(datei), "/F")
    if ergebnis.returncode != 0:
        meldung = (ergebnis.stderr or ergebnis.stdout or "").strip()
        return False, meldung or "Die Aufgabe ließ sich nicht anlegen."
    return True, ""


def _entfernen(name: str) -> None:
    _schtasks("/Delete", "/TN", name, "/F")
    datei = _ablage() / f"{name.replace(chr(92), '_')}.xml"
    datei.unlink(missing_ok=True)


def _laeuft(name: str) -> bool:
    return _schtasks("/Query", "/TN", name).returncode == 0


def _gelesen(name: str) -> str:
    """Die weggeschriebene Beschreibung, sofern noch vorhanden."""
    datei = _ablage() / f"{name.replace(chr(92), '_')}.xml"
    if not datei.is_file():
        return ""
    try:
        return datei.read_text(encoding="utf-16")
    except (OSError, UnicodeError):
        return ""


# --------------------------------------------------------------- Abruf

def einrichten(archiv: Path, takt: int) -> tuple[bool, str]:
    """Legt den regelmäßigen Abruf an."""
    geht, grund = moeglich()
    if not geht:
        return False, grund

    programm, vorspann = _befehl()
    argumente = f'{vorspann} abrufen --leise "{archiv}"'.strip()
    erfolg, fehler = _anlegen(
        _aufgabenname("Abruf", archiv),
        _xml(
            f"MailBurg holt alle {takt} Minuten neue Post nach {archiv.name}.",
            programm, argumente, wiederholung=f"PT{takt}M",
        ),
    )
    if not erfolg:
        return False, fehler
    return True, (
        f"Abruf eingerichtet: alle {takt} Minuten, solange Sie angemeldet "
        f"sind. Nachzusehen in der Windows-Aufgabenplanung unter "
        f"»{ORDNER}«."
    )


def abschalten(archiv: Path) -> tuple[bool, str]:
    geht, grund = moeglich()
    if not geht:
        return False, grund
    _entfernen(_aufgabenname("Abruf", archiv))
    return True, "Der regelmäßige Abruf ist abgeschaltet."


def zustand(archiv: Path | None) -> tuple[bool, int, str]:
    """Läuft der Abruf, in welchem Takt, für welches Archiv."""
    if archiv is None:
        return False, 0, ""
    name = _aufgabenname("Abruf", archiv)
    if not _laeuft(name):
        return False, 0, ""

    takt, ziel = 0, ""
    for zeile in _gelesen(name).splitlines():
        if "<Interval>" in zeile:
            roh = zeile.split("<Interval>")[1].split("<")[0]
            if roh.startswith("PT") and roh.endswith("M"):
                takt = int(roh[2:-1] or 0)
        if "<Arguments>" in zeile and '"' in zeile:
            ziel = zeile.split('"')[1]
    return True, takt, ziel


# ----------------------------------------------------------- Sicherung

def sicherung_einrichten(archiv: Path, ziel: Path, takt: str,
                         haltung: str, name: str = "") -> tuple[bool, str]:
    """Legt die regelmäßige Sicherung an.

    ``haltung`` kommt fertig aus :mod:`mailburg.core.zeitplan` – dort
    steht die Regel, ob ersetzt oder gesammelt wird, und sie soll nur an
    einer Stelle stehen.
    """
    geht, grund = moeglich()
    if not geht:
        return False, grund

    _einheit, tage = TAKTE_SICHERUNG.get(takt, ("DAYS", 1))
    programm, vorspann = _befehl()
    benennung = f' --name "{name}"' if name else ""
    argumente = (
        f'{vorspann} sichern --leise {haltung}{benennung} '
        f'"{archiv}" "{ziel}"'
    ).strip()

    erfolg, fehler = _anlegen(
        _aufgabenname("Sicherung", archiv),
        _xml(
            f"MailBurg sichert {archiv.name} nach {ziel} ({takt}).",
            programm, argumente, taeglich=tage,
        ),
    )
    if not erfolg:
        return False, fehler
    return True, f"Sicherung eingerichtet: {takt} nach {ziel}"


def sicherung_abschalten(archiv: Path) -> tuple[bool, str]:
    geht, grund = moeglich()
    if not geht:
        return False, grund
    _entfernen(_aufgabenname("Sicherung", archiv))
    return True, "Die regelmäßige Sicherung ist abgeschaltet."


def sicherung_zustand(archiv: Path | None) -> tuple[bool, str]:
    """Läuft die Sicherung, und für welches Archiv."""
    if archiv is None:
        return False, ""
    name = _aufgabenname("Sicherung", archiv)
    if not _laeuft(name):
        return False, ""

    for zeile in _gelesen(name).splitlines():
        if "<Arguments>" in zeile and '"' in zeile:
            teile = zeile.split('"')
            # Vorletztes Anführungspaar ist das Archiv, letztes das Ziel.
            if len(teile) >= 4:
                return True, teile[-4]
    return True, ""
