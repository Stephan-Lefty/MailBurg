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
)

#: Wo eingehängte Laufwerke auftauchen. ``/mnt`` steht dabei für von Hand
#: eingehängte Datenträger, die übrigen für automatisch eingebundene.
EINHAENGEPUNKTE = ("/run/media", "/media", "/mnt", "/Volumes")

#: Verzeichnisname für das Archiv, wenn nur der Ort gewählt wurde.
VORGABENAME = "Mailarchiv"


@dataclass(frozen=True)
class Ort:
    """Ein möglicher Ablageort."""

    beschriftung: str
    pfad: Path
    art: str
    """``benutzer``, ``cloud``, ``laufwerk``."""

    frei: int = 0
    gesamt: int = 0

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


def _beschreibbar(pfad: Path) -> bool:
    """Ob dort tatsächlich etwas angelegt werden könnte.

    Nur zu prüfen, ob das Verzeichnis existiert, genügt nicht: Ein
    schreibgeschützt eingehängter Datenträger sähe genauso aus, und der
    Anwender erführe es erst, wenn das Anlegen fehlschlägt.
    """
    import os

    return pfad.is_dir() and os.access(pfad, os.W_OK)


def vorschlagen() -> list[Ort]:
    """Sammelt die Orte, die sich für ein Archiv anbieten."""
    gefunden: list[Ort] = []
    zuhause = Path.home()

    frei, gesamt = _platz(zuhause)
    gefunden.append(
        Ort("Im Benutzerordner", zuhause / VORGABENAME, "benutzer", frei, gesamt)
    )

    for name in CLOUD_ORDNER:
        ordner = zuhause / name
        if not _beschreibbar(ordner):
            continue
        frei, gesamt = _platz(ordner)
        gefunden.append(
            Ort(f"In der Cloud ({name})", ordner / VORGABENAME, "cloud", frei, gesamt)
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
                Ort(beschriftung, laufwerk / VORGABENAME, art, frei, gesamt)
            )

    return gefunden
