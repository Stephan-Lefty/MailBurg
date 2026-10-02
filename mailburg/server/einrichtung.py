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

from mailburg.core import paths, tresor
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


#: Wie die Umgebungsvariablen in einer Meldung heißen.
#:
#: **Dieselben Wörter wie im Fenster.** ``MAILBURG_ADRESSE`` sagt einem
#: Menschen nichts; »Erreichbar« steht als Beschriftung über dem Feld, in
#: dem er es ändert. Wer eine Meldung liest, soll wissen, wohin er
#: greifen muss.
WORTE = {
    lage.ARCHIV: "Archiv",
    lage.ADRESSE: "Erreichbar",
    lage.ANSCHLUSS: "Port",
    paths.EINSTELLUNGEN: "Gemeinsamer Ordner",
    paths.DATEN: "Gemeinsamer Ordner (Index)",
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

    #: Wo Kontenliste, Tresor und Suchindex liegen – für Mensch und
    #: Dienst gemeinsam. Leer heißt: jeder dort, wo sein Profil liegt,
    #: und das ist auf einem Server der Fehler.
    einstellungen: Path | None = None
    daten: Path | None = None

    #: Wie oft Post geholt wird, in Minuten. 0 heißt: gar nicht.
    abruf: int = 0

    #: Wann nicht geholt wird, als »HH:MM-HH:MM« – für die nächtliche
    #: Sicherung.
    abrufpause: str = ""

    def als_variablen(self) -> dict[str, str]:
        werte = {
            lage.ARCHIV: str(self.archiv) if self.archiv else "",
            lage.ADRESSE: self.adresse,
            lage.ANSCHLUSS: str(self.anschluss),
        }
        # Nur was gesetzt ist: Eine leere Variable am Dienstschlüssel
        # überschriebe die Vorgabe mit nichts, und der Dienst suchte
        # dann in einem Verzeichnis ohne Namen.
        if self.einstellungen:
            werte[paths.EINSTELLUNGEN] = str(self.einstellungen)
        if self.daten:
            werte[paths.DATEN] = str(self.daten)
        if self.abruf:
            from mailburg.server import abruf as abrufmodul

            werte[abrufmodul.TAKT] = str(self.abruf)
            if self.abrufpause:
                werte[abrufmodul.PAUSE] = self.abrufpause
        return werte


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


def pruefe_fassung(stand=None) -> Befund:
    """Ob eine neuere Fassung veröffentlicht ist.

    **Der Stand wird übergeben, nicht hier geholt.** Ein Netzaufruf in
    der Prüfliste hinge bei jedem »Neu prüfen« an der Geduld des
    Netzwerks – und auf einem Server ohne Außenverbindung jedes Mal bis
    zum Zeitablauf. Das Fenster fragt einmal und reicht das Ergebnis
    weiter.
    """
    from mailburg import __version__

    if stand is None:
        return Befund(
            "Fassung", Lage.UNKLAR, f"{__version__} – noch nicht nachgesehen.",
            abhilfe="nachsehen",
        )

    if stand.fehler:
        # **Kein Fehler, sondern eine Lage.** Ein Archivserver ohne
        # Außenverbindung ist der Normalfall, nicht die Störung.
        return Befund(
            "Fassung", Lage.UNKLAR,
            f"{stand.hier} – GitHub {stand.fehler}.",
            einzelheiten="Ohne Internet lässt sich das nicht feststellen. "
                         "Alles andere läuft davon unberührt weiter.",
        )

    if stand.neuer:
        return Befund(
            "Fassung", Lage.ACHTUNG,
            f"{stand.hier} läuft, {stand.draussen} ist veröffentlicht.",
            abhilfe="aktualisieren",
            einzelheiten=stand.seite,
        )

    return Befund("Fassung", Lage.GUT, f"{stand.hier} – das ist die neueste.")


def pruefe_abruf(umgebung: Umgebung) -> Befund:
    """Ob und wie oft der Dienst Post holt.

    **Ein Archiv, das nichts mehr dazubekommt, sieht aus wie eines, in
    dem gerade nichts ankam.** Der Unterschied zeigt sich erst nach
    Wochen – und dann fehlen sie.

    Geprüft wird, was beim *Dienst* steht, nicht was im Fenster gewählt
    ist: Der Dienst holt die Post, nicht das Fenster.
    """
    from mailburg.server import abruf as abrufmodul

    gesetzt = gesetzte_variablen().get(abrufmodul.TAKT, "").strip()
    try:
        takt = int(gesetzt) if gesetzt else 0
    except ValueError:
        takt = 0

    if takt <= 0:
        return Befund(
            "Abruf",
            Lage.ACHTUNG,
            "Es wird keine Post geholt. Der Dienst stellt das Archiv "
            "bereit, aber es wächst nicht mehr.",
            abhilfe="abruf",
            einzelheiten="Nötig, sobald der Server selbst abrufen soll. "
                         "Vorher muss der Tresor stehen.",
        )

    pause = gesetzte_variablen().get(abrufmodul.PAUSE, "").strip()
    text = f"Alle {takt} Minuten."
    if pause:
        text += f" Ruhe von {pause}."
    return Befund("Abruf", Lage.GUT, text)


def pruefe_tresor(umgebung: Umgebung) -> Befund:
    """Kommt der Dienst an die Postfach-Passwörter?

    **Ohne ihn läuft der Dienst und holt keine Post.** Das ist die
    teuerste Fehlerart in diesem Programm: Es sieht funktionierend aus,
    und auffallen wird es dem, der in einem Jahr eine Mail aus diesem
    Monat sucht.

    Der Tresor hat zwei Hälften, die getrennt liegen müssen und beide da
    sein müssen:

    * die **Datei** mit den verschlüsselten Passwörtern, in den
      Einstellungen – und die liegen unter Windows im Benutzerprofil,
      das ``LocalSystem`` nicht hat;
    * der **Hauptschlüssel**, über ``MAILBURG_SCHLUESSELDATEI`` oder
      ``MAILBURG_SCHLUESSEL``.

    Geprüft wird hier die Lage für den *Dienst*, nicht für den Menschen,
    der gerade davorsitzt. Deshalb zählt, ob ein gemeinsamer
    Einstellungsort gewählt ist – ohne ihn sucht der Dienst woanders als
    der Mensch, und beide finden jeweils ihre eigene Leere.
    """
    hat_schluessel = tresor.verfuegbar()
    datei = paths.config_dir() / tresor.DATEI
    eintraege = tresor.eintraege() if datei.is_file() else []

    if not hat_schluessel and not eintraege:
        return Befund(
            "Tresor",
            Lage.ACHTUNG,
            "Nicht eingerichtet. Der Dienst stellt das Archiv bereit, "
            "holt aber keine neue Post.",
            abhilfe="tresor",
            einzelheiten="Nötig, sobald Postfächer abgerufen werden sollen.",
        )

    if not hat_schluessel:
        return Befund(
            "Tresor",
            Lage.FEHLT,
            f"{len(eintraege)} Passwörter liegen da, aber es ist kein "
            f"Hauptschlüssel eingerichtet – ohne ihn sind sie nicht zu "
            f"öffnen.",
            abhilfe="tresor",
        )

    if not eintraege:
        return Befund(
            "Tresor",
            Lage.ACHTUNG,
            "Hauptschlüssel ist da, aber es liegt kein Passwort darin.",
            abhilfe="tresor",
            einzelheiten=f"Die Datei läge unter »{datei}«.",
        )

    if ist_windows() and not umgebung.einstellungen:
        # **Der Fall, der still schiefgeht.** Der Mensch hat alles
        # eingerichtet, der Dienst sucht nur woanders.
        return Befund(
            "Tresor",
            Lage.FEHLT,
            f"{len(eintraege)} Passwörter liegen in Ihrem Benutzerprofil. "
            f"Der Dienst läuft als Systemkonto und sucht sie dort nicht – "
            f"er holt dann keine Post, ohne dass etwas fehlschlägt.",
            abhilfe="tresor",
            einzelheiten=f"Jetzt unter »{datei}«.",
        )

    return Befund(
        "Tresor", Lage.GUT,
        f"{len(eintraege)} Passwörter hinterlegt, Hauptschlüssel ist da.",
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
            winreg.HKEY_LOCAL_MACHINE, dienst, 0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
        ) as schluessel:
            # **Dazu, nicht statt.** Die erste Fassung überschrieb den
            # ganzen Wert – und warf dabei am 2026-10-02 Stephans
            # ``LOCALAPPDATA`` weg, mit dem der Dienst seinen Suchindex
            # fand. Danach suchte er wieder im Systemprofil, die Suche
            # blieb leer, und niemand hätte den Zusammenhang zum Klick
            # auf »Übernehmen« hergestellt.
            #
            # Beim Tresor stand es von Anfang an richtig; hier nicht.
            # Zwei Stellen, eine nachgezogen, die andere nicht – dieselbe
            # Klasse wie so oft in diesem Projekt.
            try:
                vorhanden = list(
                    winreg.QueryValueEx(schluessel, "Environment")[0]
                )
            except FileNotFoundError:
                vorhanden = []

            neue = umgebung.als_variablen()
            behalten = [
                zeile for zeile in vorhanden
                if zeile.split("=", 1)[0] not in neue
            ]
            zeilen = behalten + [f"{n}={w}" for n, w in neue.items()]
            winreg.SetValueEx(
                schluessel, "Environment", 0, winreg.REG_MULTI_SZ, zeilen
            )
            getan.append(
                f"am Dienst »{DIENSTNAME}«: {len(neue)} Werte gesetzt, "
                f"{len(behalten)} unberührt"
            )
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


def pruefe_einstellungen(umgebung: Umgebung) -> Befund:
    """Ob das, was im Fenster steht, auch dort steht, wo der Dienst liest.

    **Der Fehler, der am 2026-10-02 eine halbe Stunde gekostet hat.** Man
    konnte im Fenster ein Archiv wählen, den Dienst einrichten und
    starten – ohne »Übernehmen« dazwischen. Der Dienst nahm dann den
    Wert, der seit vorgestern in der Registry stand, fand dort kein
    Archiv und starb. Im Ereignisprotokoll stand ein Pfad, den im Fenster
    niemand mehr sah.

    Zwei Dinge sind hier verschieden und sehen gleich aus: was *gewählt*
    ist und was *gilt*. Diese Zeile hält sie auseinander.
    """
    gesetzt = gesetzte_variablen()
    soll = umgebung.als_variablen()

    if not gesetzt.get(lage.ARCHIV, "").strip():
        return Befund(
            "Einstellungen",
            Lage.FEHLT,
            "Noch nichts übernommen – der Dienst weiß nicht, welches "
            "Archiv er ausliefern soll.",
            abhilfe="uebernehmen",
        )

    anders = [
        name for name, wert in soll.items()
        if wert and gesetzt.get(name, "").strip() != wert
    ]
    if anders:
        # **Nennen, was abweicht – nicht irgendetwas.** Die erste Fassung
        # schrieb immer den Archivpfad in die Meldung, auch wenn der
        # stimmte und nur die Adresse abwich. Auf Stephans Bildschirm
        # stand dann »Hier steht etwas anderes (Archiv: C:\MailBurg-
        # Archiv)« – über einem Feld, in dem genau dieser Pfad stand.
        # Eine Meldung, die auf etwas zeigt, das in Ordnung ist, schickt
        # die Suche in die falsche Richtung.
        teile = [
            f"{WORTE.get(name, name)}: »{gesetzt.get(name, '')}« statt "
            f"»{soll[name]}«"
            for name in anders
        ]
        return Befund(
            "Einstellungen",
            Lage.FEHLT,
            f"Beim Dienst steht etwas anderes – {'; '.join(teile)}. "
            f"Ohne Übernehmen startet er mit dem alten Wert.",
            abhilfe="uebernehmen",
        )

    return Befund("Einstellungen", Lage.GUT, "Übernommen.")


#: Was in der Registry unter ``Start`` steht. Aus der Windows-Doku zum
#: Dienstschlüssel; ``sc qc`` zeigt dieselben Werte in Worten.
STARTARTEN = {
    0: ("Treiber (Systemstart)", True),
    1: ("Treiber (System)", True),
    2: ("Automatisch", True),
    3: ("Manuell", False),
    4: ("Deaktiviert", False),
}


def pruefe_starttyp() -> Befund:
    """Ob der Dienst einen Neustart des Servers übersteht.

    **Die teuerste Vorgabe in diesem ganzen Aufbau.** pywin32 legt
    Dienste ohne Angabe als ``manual`` an. Der Dienst läuft dann, solange
    niemand den Server neu startet – und danach nie wieder, ohne dass
    irgendwo ein Fehler steht. Ein Archiv, das montags nicht mehr
    erreichbar ist, sucht niemand beim Starttyp.

    Gelesen wird die Registry, nicht die eigene Erinnerung: Wer die
    eigene Kopie liest, prüft, was er gemeint hat – nicht, was gilt.
    """
    if not ist_windows():
        return Befund("Start beim Hochfahren", Lage.UNKLAR, "Nur unter Windows.")

    import winreg

    pfad = rf"SYSTEM\CurrentControlSet\Services\{DIENSTNAME}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, pfad) as schluessel:
            wert = winreg.QueryValueEx(schluessel, "Start")[0]
            try:
                verzoegert = winreg.QueryValueEx(
                    schluessel, "DelayedAutostart"
                )[0]
            except FileNotFoundError:
                verzoegert = 0
    except OSError:
        return Befund(
            "Start beim Hochfahren", Lage.UNKLAR, "Der Dienst ist nicht da."
        )

    name, kommt_wieder = STARTARTEN.get(wert, (f"unbekannt ({wert})", False))
    if kommt_wieder:
        if verzoegert:
            name += " (verzögert)"
        return Befund(
            "Start beim Hochfahren", Lage.GUT,
            f"{name} – er kommt nach einem Neustart von selbst wieder.",
        )
    return Befund(
        "Start beim Hochfahren",
        Lage.FEHLT,
        f"{name}. Nach einem Neustart des Servers bleibt der Dienst unten, "
        f"und niemand bekommt eine Meldung darüber.",
        abhilfe="starttyp",
        einzelheiten="Abhilfe: Dienst entfernen und neu einrichten.",
    )


def _dienst_befehl(was: str, *zusatz: str) -> tuple[bool, str]:
    """Ruft ``windows_dienst`` in einem eigenen Prozess auf.

    **Nicht im eigenen**: ``HandleCommandLine`` beendet den Prozess, in
    dem es läuft. Ein Fenster, das sich beim Starten des Dienstes selbst
    schließt, wäre eine denkwürdige Bedienung.

    ``zusatz`` steht **vor** dem Befehl – so will es pywin32: Optionen
    wie ``--startup`` sind Vorsatz, nicht Nachsatz.
    """
    from mailburg.core import werkzeuge

    befehl = [
        sys.executable, "-m", "mailburg.server.windows_dienst", *zusatz, was,
    ]
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
    """Legt den Dienst an – **und zwar automatisch startend.**

    pywin32 setzt ohne Angabe ``manual``; das steht in seiner eigenen
    Hilfe (``--startup [manual|auto|disabled|delayed] … default =
    manual``). Ein Archivdienst, der nach jedem Neustart des Servers
    unten bleibt, ist genau die Sorte Fehler, die dieses Projekt sonst
    bei anderen findet: Nichts ist kaputt, es läuft nur nichts mehr, und
    auffallen wird es dem, der montags vergeblich sucht.

    ``delayed`` statt ``auto``: Windows startet verzögerte Dienste, wenn
    das System oben ist. Liegt das Archiv auf einer zweiten Platte oder
    einer Freigabe, ist die zu Beginn des Hochfahrens noch nicht da – und
    der Dienst stirbt daran, bevor jemand ihn gebraucht hätte. Die
    Verzögerung kostet eine knappe Minute nach dem Hochfahren; dafür
    läuft er dann auch.
    """
    return _dienst_befehl("install", "--startup", "delayed")


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

    # **``Format-List``, nicht selbst zusammengebaut.** Die erste Fassung
    # setzte die Zeile als "$($_.TimeCreated)  $($_.Message)" zusammen –
    # und lieferte am 2026-10-02 auf dem echten Server nur Zeitstempel,
    # die Texte blieben leer. Derselbe Filter von Hand in einer
    # PowerShell zeigte sie vollständig.
    #
    # Woran es lag, ist nicht geklärt; naheliegend ist die Auflösung der
    # Meldungstexte, die in einem nicht-interaktiven Unterprozess anders
    # ausgehen kann. Geklärt ist nur, welcher Weg nachweislich geht –
    # und den nehmen wir. Ein Protokollknopf, der Zeitstempel ohne Text
    # zeigt, ist schlimmer als keiner: Er sieht aus, als hätte er
    # nachgesehen.
    skript = (
        f"Get-WinEvent -LogName Application -MaxEvents 200 "
        f"| Where-Object {{ $_.ProviderName -eq '{DIENSTNAME}' }} "
        f"| Select-Object -First {anzahl} "
        f"| Format-List TimeCreated, Id, Message"
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

    # Leerzeilen bleiben weg, Einrückungen nicht: ``Format-List`` bricht
    # einen Traceback über viele Zeilen um, und der ist der Grund, warum
    # jemand hier nachsieht.
    zeilen = [z.rstrip() for z in lauf.stdout.splitlines() if z.strip()]
    return zeilen or ["Keine Einträge – der Dienst hat noch nichts gemeldet."]


# ------------------------------------------------------------- Tresor

#: Wie die Datei mit dem Hauptschlüssel heißt.
SCHLUESSELDATEI = "tresor-schluessel.txt"


def tresor_einrichten(umgebung: Umgebung) -> list[str]:
    """Hauptschlüssel erzeugen und dem Dienst beibringen, wo er liegt.

    **Was hier passiert und was nicht.** Erzeugt wird ein Schlüssel und
    eine Datei, die ihn enthält; eingetragen werden die Pfade am
    Dienstschlüssel. **Die Passwörter selbst kommen nicht von hier** –
    die trägt ``mailburg tresor uebernehmen`` aus dem Schlüsselbund ein
    oder ``mailburg konten passwort`` von Hand. Ein Fenster, das
    Passwörter aus einem fremden Schlüsselbund holt, wäre ein Werkzeug,
    das man nicht bauen sollte.

    **Ein vorhandener Schlüssel wird nie überschrieben.** Er ist das
    Einzige, was die hinterlegten Passwörter noch öffnet; ihn zu
    ersetzen hieße, sie alle zu verlieren – und zwar stumm, denn die
    Datei bliebe ja lesbar.
    """
    getan: list[str] = []

    if not umgebung.einstellungen:
        return [
            "Erst einen gemeinsamen Ort für die Einstellungen wählen – "
            "sonst legt der Dienst den Tresor woanders ab als Sie."
        ]

    ordner = Path(umgebung.einstellungen)
    try:
        ordner.mkdir(parents=True, exist_ok=True)
    except OSError as fehler:
        return [f"»{ordner}« ließ sich nicht anlegen: {fehler}"]

    schluesseldatei = ordner / SCHLUESSELDATEI
    if schluesseldatei.is_file():
        getan.append(f"Hauptschlüssel liegt schon: {schluesseldatei}")
    else:
        try:
            schluessel = tresor.schluessel_erzeugen()
        except Exception as fehler:  # noqa: BLE001
            return [f"Kein Schlüssel zu erzeugen: {fehler}"]

        schluesseldatei.write_text(schluessel, encoding="utf-8")
        if os.name != "nt":
            schluesseldatei.chmod(0o600)
        getan.append(f"Hauptschlüssel erzeugt: {schluesseldatei}")

    # Für diesen Prozess sofort, damit die Prüfung danach etwas sieht.
    os.environ[tresor.UMGEBUNG_DATEI] = str(schluesseldatei)
    os.environ[paths.EINSTELLUNGEN] = str(ordner)

    if ist_windows():
        import winreg

        try:
            pfad = rf"SYSTEM\CurrentControlSet\Services\{DIENSTNAME}"
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, pfad, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
            ) as schluessel_ort:
                # **Dazu, nicht statt.** Der Wert trägt auch Archivpfad,
                # Adresse und Port; ihn zu überschreiben nähme dem Dienst
                # alles andere weg.
                try:
                    vorhanden = list(
                        winreg.QueryValueEx(schluessel_ort, "Environment")[0]
                    )
                except FileNotFoundError:
                    vorhanden = []

                neu = {tresor.UMGEBUNG_DATEI: str(schluesseldatei)}
                behalten = [
                    zeile for zeile in vorhanden
                    if zeile.split("=", 1)[0] not in neu
                ]
                winreg.SetValueEx(
                    schluessel_ort, "Environment", 0, winreg.REG_MULTI_SZ,
                    behalten + [f"{n}={w}" for n, w in neu.items()],
                )
            getan.append(f"Am Dienst eingetragen: {tresor.UMGEBUNG_DATEI}")
        except OSError as fehler:
            getan.append(f"Am Dienst noch nicht: {fehler}")

    getan.append(
        "Noch keine Passwörter darin. Auf dem Rechner, der die Postfächer "
        "kennt:  mailburg tresor uebernehmen"
    )
    getan.append(
        "WICHTIG: Schlüsseldatei und Tresordatei nie zusammen weitergeben "
        "und nie zusammen sichern – wer beides hat, hat die Postfächer."
    )
    return getan


# -------------------------------------------------- Verknüpfungen


#: Wie die Verknüpfungen heißen. Als Tabelle, damit ein Aufräumen
#: dieselben Namen findet wie das Anlegen.
VERKNUEPFUNGEN = {
    "MailBurg starten": "prüft den Dienst und öffnet den Browser",
    "MailBurg im Browser": "die Weboberfläche im Standardbrowser",
    "MailBurg einrichten": "dieses Fenster",
}


def verknuepfungen_anlegen(umgebung: Umgebung) -> list[str]:
    """Zwei Symbole auf dem Schreibtisch aller Benutzer.

    **Warum auf den öffentlichen Schreibtisch.** Auf einem Server
    wechseln die Menschen, die sich anmelden; eine Verknüpfung im Profil
    des Administrators sieht der nächste nicht. ``%PUBLIC%\\Desktop``
    gilt für alle.

    **Und warum zwei.** Das Einrichtungsfenster braucht man einmal, die
    Weboberfläche täglich. Beides hinter ein Symbol zu legen hieße, dass
    einer von beiden Wegen der falsche ist.

    Der Dienst selbst braucht kein Symbol – er läuft. Wäre er nur über
    ein Symbol zu starten, wäre er kein Dienst.
    """
    if not ist_windows():
        return ["Verknüpfungen gibt es nur unter Windows."]

    import os.path

    oeffentlich = os.environ.get("PUBLIC", r"C:\Users\Public")
    schreibtisch = Path(oeffentlich) / "Desktop"
    if not schreibtisch.is_dir():
        return [f"»{schreibtisch}« gibt es nicht."]

    adresse = (
        "127.0.0.1" if umgebung.adresse in ("0.0.0.0", "::")  # noqa: S104
        else umgebung.adresse
    )
    ziel_browser = f"http://{adresse}:{umgebung.anschluss}/"

    # **Das rote Wappen als Symbol.** Ohne ``IconLocation`` nimmt Windows
    # das Symbol des Zielprogramms – bei einer Adresse ein weißes Blatt,
    # bei einem Python-Aufruf die Python-Schlange. Beides sagt nichts
    # über MailBurg, und auf einem Schreibtisch mit zwanzig Symbolen
    # findet man ein Programm am Bild, nicht am Namen.
    from mailburg import bilder

    wappen = bilder.finden("server/mailburg-server.ico")
    symbolzeile = f'$X.IconLocation = "{wappen}"' if wappen else ""

    # PowerShell statt pywin32-COM: Dieselbe Sprache wie der Rest der
    # Windows-Arbeit hier, und sie läuft auch, wenn pywin32 klemmt – was
    # ausgerechnet der Fall ist, in dem jemand ein Symbol sucht.
    # **Ein Startsymbol, zwei Nachschlagewerke.** Das erste ist das, was
    # Stephan am 02.10. verlangt hat: ein Doppelklick, nach dem MailBurg
    # offen ist – auch wenn der Dienst gerade erst anläuft. Die beiden
    # anderen führen direkt zum Ziel, für den, der weiß, was er will.
    #
    # ``pythonw.exe`` beim Starter, nicht ``python.exe``: Sonst blitzt
    # bei jedem Doppelklick ein schwarzes Fenster auf.
    ohne_fenster = Path(sys.executable).with_name("pythonw.exe")
    starter = ohne_fenster if ohne_fenster.exists() else Path(sys.executable)

    skript = f"""
$w = New-Object -ComObject WScript.Shell

$X = $w.CreateShortcut("{schreibtisch}\\MailBurg starten.lnk")
$X.TargetPath = "{starter}"
$X.Arguments = "-m mailburg.anlauf"
$X.WorkingDirectory = "{Path(sys.executable).parent}"
$X.Description = "MailBurg prüfen, notfalls starten und im Browser öffnen"
{symbolzeile}
$X.Save()

$X = $w.CreateShortcut("{schreibtisch}\\MailBurg im Browser.lnk")
$X.TargetPath = "{ziel_browser}"
$X.Description = "Das Archiv im Browser"
{symbolzeile}
$X.Save()

$X = $w.CreateShortcut("{schreibtisch}\\MailBurg einrichten.lnk")
$X.TargetPath = "{sys.executable}"
$X.Arguments = "-m mailburg.ui.servereinrichtung"
$X.WorkingDirectory = "{Path(sys.executable).parent}"
$X.Description = "Den Serverdienst einrichten und nachsehen"
{symbolzeile}
$X.Save()
"""

    from mailburg.core import werkzeuge

    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return ["PowerShell nicht gefunden."]
    try:
        lauf = subprocess.run(
            [powershell, "-NoProfile", "-Command", skript],
            capture_output=True, text=True, timeout=60,
            **werkzeuge.konsolenkodierung(),
            **werkzeuge.lautlos(),
        )
    except (OSError, subprocess.SubprocessError) as fehler:
        return [f"Ging nicht: {fehler}"]

    if lauf.returncode:
        return [(lauf.stderr or lauf.stdout).strip() or "Ging nicht."]

    getan = [f"Auf {schreibtisch}:"]
    getan += [f"  {name} – {wozu}" for name, wozu in VERKNUEPFUNGEN.items()]
    getan.append(
        "Das Symbol für den Browser zeigt auf 127.0.0.1 – es gilt auf dem "
        "Server selbst. Von einem Arbeitsplatz aus gehört der Servername "
        "in die Adresse."
    )
    return getan


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


def alles_pruefen(umgebung: Umgebung, stand=None) -> Gesamtbild:
    """Die ganze Liste, in der Reihenfolge, in der sie abzuarbeiten ist.

    ``stand`` ist das Ergebnis von :func:`aktualisierung.nachsehen` –
    übergeben statt hier geholt, damit kein »Neu prüfen« am Netz hängt.
    """
    befunde = [pruefe_system(), pruefe_python(), pruefe_fassung(stand)]
    befunde.extend(pruefe_pakete())
    befunde.append(pruefe_rechte())
    befunde.append(pruefe_archiv(umgebung.archiv))
    befunde.append(pruefe_zugaenge(umgebung.archiv))
    if ist_windows():
        # **Vor dem Dienst, nicht danach.** Was der Dienst liest, steht
        # fest, bevor er startet; ein Fehler hier macht jede Meldung
        # darunter zu einer Folgeerscheinung.
        befunde.append(pruefe_einstellungen(umgebung))
        befunde.append(pruefe_dienst())
        befunde.append(pruefe_starttyp())
    befunde.append(pruefe_tresor(umgebung))
    befunde.append(pruefe_abruf(umgebung))
    befunde.append(erreichbar(umgebung))
    return Gesamtbild(befunde)
