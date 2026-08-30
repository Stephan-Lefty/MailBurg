"""Wo ein Archiv liegen könnte – Vorschläge für die Einrichtung.

Dass der Ablageort frei wählbar ist, ist eine Kernzusage des Programms.
Ein einzelnes Eingabefeld mit einem vorgeschlagenen Pfad zeigt davon
nichts: Wer nicht weiß, dass hinter »Auswählen…« auch die externe Platte
und der Cloud-Ordner stecken, nimmt eben den Vorschlag.

Deshalb wird nachgesehen, was tatsächlich da ist – Benutzerverzeichnis,
Cloud-Ordner, eingehängte Laufwerke – und alles zur Auswahl gestellt,
samt freiem Platz. Ein Archiv wächst über Jahre; wie viel Raum bleibt,
gehört zur Entscheidung.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

#: Verzeichnisnamen, unter denen Abgleichprogramme ihre Ordner anlegen.
CLOUD_ORDNER = (
    "Nextcloud", "nextcloud", "ownCloud", "owncloud",
    "Seafile", "Syncthing", "Dropbox", "Cloud",
    # **OneDrive fehlte hier bis zum 2026-08-30.** Ausgerechnet der
    # Ordner, den ein Windows-Rechner meistens schon mitbringt – und
    # damit fand der Sicherungsvorschlag auf einem gewöhnlichen Windows
    # gar nichts und ließ das Feld leer. Die Liste war an einem
    # Linux-Rechner entstanden, und dort kommt OneDrive nicht vor.
    "OneDrive", "OneDrive - Persönlich", "iCloudDrive", "pCloudDrive",
    "MagentaCLOUD", "GMX Cloud", "WEB.DE Cloud",
)

#: Wo eingehängte Laufwerke auftauchen. ``/mnt`` steht dabei für von Hand
#: eingehängte Datenträger, die übrigen für automatisch eingebundene.
EINHAENGEPUNKTE = ("/run/media", "/media", "/mnt", "/Volumes")

#: Verzeichnisname für das Archiv, wenn nur der Ort gewählt wurde.
VORGABENAME = "Mailarchiv"

#: Dasselbe für die Sicherungen. Ein eigener Name, damit niemand die
#: gepackten Stände für das Archiv selbst hält.
SICHERUNGSNAME = "MailBurg-Sicherung"


@dataclass(frozen=True)
class Ort:
    """Ein möglicher Ablageort."""

    beschriftung: str
    pfad: Path
    art: str
    """``benutzer``, ``cloud``, ``laufwerk``."""

    frei: int = 0
    gesamt: int = 0

    auf_systemplatte: bool = False
    """Ob dieser Ort auf demselben Datenträger liegt wie das System.

    Dann trifft ein Plattendefekt beides auf einmal: den Rechner und das
    Archiv. Das ist nicht verboten – aber es ist der Fall, in dem eine
    Sicherung am dringendsten gebraucht wird.
    """

    @property
    def freier_platz(self) -> str:
        if not self.gesamt:
            return ""
        return f"{_lesbar(self.frei)} von {_lesbar(self.gesamt)} frei"

    @property
    def eng(self) -> bool:
        """Ob der Platz für ein wachsendes Archiv knapp werden dürfte."""
        return bool(self.gesamt) and self.frei < 2 * 1024**3


def _lesbar(bytes_zahl: int) -> str:
    wert = float(bytes_zahl)
    for einheit in ("B", "KB", "MB", "GB", "TB"):
        if wert < 1024 or einheit == "TB":
            return f"{wert:.0f} {einheit}" if einheit in ("B", "KB") else f"{wert:.1f} {einheit}"
        wert /= 1024
    return f"{wert:.1f} TB"


def _platz(pfad: Path) -> tuple[int, int]:
    try:
        belegung = shutil.disk_usage(pfad)
    except OSError:
        return 0, 0
    return belegung.free, belegung.total


def _geraet_von(einhaengepunkt: Path) -> str:
    """Welches Gerät an dieser Stelle eingehängt ist."""
    try:
        zeilen = Path("/proc/mounts").read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    gesucht = str(einhaengepunkt)
    for zeile in zeilen:
        teile = zeile.split()
        if len(teile) < 2:
            continue
        # Leerzeichen und Sonderzeichen stehen dort als Oktalfolgen.
        ort = teile[1].encode().decode("unicode_escape")
        if ort == gesucht:
            return teile[0]
    return ""


def datentraegername(einhaengepunkt: Path) -> str:
    """Der Name, den der Datenträger trägt – nicht der des Einhängepunkts.

    Von Hand eingehängte Platten liegen oft unter Pfaden wie
    ``/mnt/usb-Hersteller_Portable_XXXXXXXX-0:0-part1``. Das ist eine
    Gerätekennung, kein Name; den kennt nur das Dateisystem selbst, und er
    steht in ``/dev/disk/by-label``.
    """
    geraet = _geraet_von(einhaengepunkt)
    if not geraet:
        return ""
    verzeichnis = Path("/dev/disk/by-label")
    if not verzeichnis.is_dir():
        return ""
    try:
        ziel = Path(geraet).resolve()
        for eintrag in verzeichnis.iterdir():
            if eintrag.resolve() == ziel:
                # Labels stehen dort mit Oktalfolgen für Sonderzeichen.
                return eintrag.name.encode().decode("unicode_escape")
    except OSError:
        pass
    return ""


def ist_wechseldatentraeger(einhaengepunkt: Path) -> bool:
    """Ob dahinter eine Platte steckt, die man abziehen kann.

    Wichtig für die Beschriftung: Eine externe Platte darf man ruhig als
    solche benennen – sie ist eben nicht immer da, und ein Archiv darauf
    ist nur erreichbar, solange sie angesteckt ist.

    Die Angabe ``removable`` allein taugt dafür nicht: Sie steht bei
    USB-Festplatten auf 0, weil sich ihr *Medium* nicht wechseln lässt –
    anders als bei einer CD oder einem Kartenleser. Verlässlicher ist der
    Anschluss: Was am USB- oder Firewire-Bus hängt, kann jederzeit weg
    sein.
    """
    geraet = _geraet_von(einhaengepunkt)
    if not geraet.startswith("/dev/"):
        return False

    name = Path(geraet).name.rstrip("0123456789")
    geraetepfad = Path("/sys/block") / name
    try:
        # Der aufgelöste Pfad führt durch die Anschlusskette hindurch:
        # .../pci0000:00/.../usb2/2-1/2-1:1.0/host6/.../block/sdd
        kette = str(geraetepfad.resolve())
    except OSError:
        return False

    if "/usb" in kette or "firewire" in kette:
        return True

    try:
        return (geraetepfad / "removable").read_text().strip() == "1"
    except OSError:
        return False


def _geraetenummer(pfad: Path) -> int:
    """Auf welchem Datenträger ein Pfad liegt.

    Nicht der Pfad entscheidet, sondern das Gerät dahinter: ``/home`` kann
    auf derselben Platte liegen wie ``/`` oder auf einer eigenen. Nur die
    Gerätenummer sagt es sicher.
    """
    try:
        return pfad.stat().st_dev
    except OSError:
        return -1


def _beschreibbar(pfad: Path) -> bool:
    """Ob dort tatsächlich etwas angelegt werden könnte.

    Nur zu prüfen, ob das Verzeichnis existiert, genügt nicht: Ein
    schreibgeschützt eingehängter Datenträger sähe genauso aus, und der
    Anwender erführe es erst, wenn das Anlegen fehlschlägt.
    """
    import os

    return pfad.is_dir() and os.access(pfad, os.W_OK)


def _cloudordner_im(zuhause: Path) -> list[str]:
    """Die Cloud-Ordner, die es hier wirklich gibt.

    Feste Namen reichen nicht: OneDrive heißt im Geschäftsumfeld
    »OneDrive - Firmenname«, und der Zusatz steht nirgends fest. Deshalb
    zusätzlich alles, was mit einem bekannten Namen *beginnt*.

    Die Reihenfolge folgt ``CLOUD_ORDNER``, damit der Vorschlag
    berechenbar bleibt und nicht davon abhängt, wie das Dateisystem
    gerade sortiert.
    """
    gefunden: list[str] = []
    try:
        vorhanden = sorted(p.name for p in zuhause.iterdir() if p.is_dir())
    except OSError:
        vorhanden = []

    for name in CLOUD_ORDNER:
        if name in vorhanden:
            gefunden.append(name)
        for da in vorhanden:
            if da not in gefunden and da.startswith(name + " -"):
                gefunden.append(da)
    return gefunden


def vorschlagen() -> list[Ort]:
    """Sammelt die Orte, die sich für ein Archiv anbieten."""
    gefunden: list[Ort] = []
    zuhause = Path.home()

    system = _geraetenummer(zuhause)

    frei, gesamt = _platz(zuhause)
    gefunden.append(
        Ort("Im Benutzerordner", zuhause / VORGABENAME, "benutzer", frei, gesamt,
            auf_systemplatte=True)
    )

    for name in _cloudordner_im(zuhause):
        ordner = zuhause / name
        if not _beschreibbar(ordner):
            continue
        frei, gesamt = _platz(ordner)
        gefunden.append(
            Ort(f"In der Cloud ({name})", ordner / VORGABENAME, "cloud", frei, gesamt,
                auf_systemplatte=_geraetenummer(ordner) == system)
        )

    for wurzel in EINHAENGEPUNKTE:
        basis = Path(wurzel)
        if not basis.is_dir():
            continue
        # Unter /run/media und /media liegt eine Ebene je Benutzer.
        kandidaten = list(basis.glob(f"{zuhause.name}/*")) + list(basis.glob("*"))
        for laufwerk in sorted(set(kandidaten)):
            if not _beschreibbar(laufwerk) or laufwerk == zuhause:
                continue
            # Nicht dasselbe Gerät zweimal anbieten, nur weil es unter zwei
            # Pfaden erreichbar ist.
            if any(o.pfad.parent == laufwerk for o in gefunden):
                continue
            frei, gesamt = _platz(laufwerk)
            if not gesamt:
                continue

            name = datentraegername(laufwerk) or laufwerk.name
            if ist_wechseldatentraeger(laufwerk):
                beschriftung = f"Externe Platte »{name}«"
                art = "extern"
            else:
                beschriftung = f"Laufwerk »{name}«"
                art = "laufwerk"

            gefunden.append(
                Ort(beschriftung, laufwerk / VORGABENAME, art, frei, gesamt,
                    auf_systemplatte=_geraetenummer(laufwerk) == system)
            )

    return gefunden


#: In welcher Reihenfolge sich ein Ort für Sicherungen eignet. Die Cloud
#: zuerst, weil sie den Rechner überlebt und weil sie den Zweck einer
#: Sicherung – woanders zu liegen – ohne Zutun erfüllt. Dann eine externe
#: Platte, dann ein anderes eingebautes Laufwerk.
#:
#: Der Benutzerordner steht bewusst **nicht** in der Liste: Er liegt auf
#: derselben Platte wie in aller Regel das Archiv, und eine Sicherung
#: neben dem Original geht mit ihm zusammen verloren.
SICHERUNGSRANG = ("cloud", "extern", "laufwerk")


def sicherungsort_vorschlagen(archiv: Path | str | None = None) -> Path | None:
    """Wohin die Sicherungen am ehesten gehören – oder ``None``.

    Der Dialog verlangte einen Ordner, schlug aber keinen vor: Wer das
    Häkchen setzte und auf »Übernehmen« ging, bekam erst einmal eine
    Fehlermeldung für einen Zustand, den der Dialog selbst hergestellt
    hatte.

    **Lieber nichts als etwas Falsches.** Findet sich kein Ort, der auf
    einer anderen Platte liegt als das Archiv, wird nichts vorgeschlagen.
    Ein Vorschlag, der dem fettgedruckten Rat direkt darunter
    widerspricht, wäre schlimmer als ein leeres Feld.
    """
    if archiv is not None:
        archivgeraet = _geraetenummer(Path(archiv).expanduser())
    else:
        archivgeraet = _geraetenummer(Path.home())

    orte = vorschlagen()
    for art in SICHERUNGSRANG:
        for ort in orte:
            if ort.art != art:
                continue
            ordner = ort.pfad.parent
            if _geraetenummer(ordner) == archivgeraet:
                continue
            return ordner / SICHERUNGSNAME
    return None
