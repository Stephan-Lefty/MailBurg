#!/usr/bin/env python3
"""Baut aus dem PyInstaller-Ergebnis ein AppImage.

**Warum es das gibt.** Am 2026-09-14 meldete ein Anwender auf Linux
Mint: »Wenn ich das Tool starte, passiert gar nichts.« Ursache war das
Debian-Paket, das die Oberfläche aus der Distribution nachzieht – und
Ubuntu, Mint, Pop!_OS und Zorin führen PySide6 nicht in ihren
Paketquellen. Der Weg dorthin war ein `git clone` und fünfzehn Minuten
Übersetzen.

Ein AppImage ist die Antwort darauf: **eine Datei, ausführbar machen,
starten.** Ohne Paketverwaltung, ohne Python auf dem Zielrechner, ohne
Rücksicht auf die Distribution.

Der Preis ist derselbe wie bei der ``MailBurg.exe``: Qt steckt mit drin
und bekommt damit keine Sicherheitsupdates der Distribution. Wer ein
Debian 13 oder GuideOS betreibt, ist mit dem ``.deb`` besser bedient –
das steht auch so in der Anleitung. Das AppImage ist für alle anderen.

**Keine Fassungsnummer im Dateinamen**, und das ist Absicht: Der Pfad
zur Datei wandert in den Zeitplan für den regelmäßigen Abruf. Hieße sie
``MailBurg-1.4.6-x86_64.AppImage``, zeigte der Zeitplan nach jedem
Update ins Leere, und der Abruf hörte stillschweigend auf – genau der
Fehler, der am 2026-09-12 in der 1.4.4 behoben wurde. Dieselbe
Überlegung wie bei der ``.exe``.

Aufruf::

    python3 werkzeuge/appimage_bauen.py [zielordner]

Voraussetzung ist ein fertiger PyInstaller-Lauf (``dist/MailBurg``) und
``appimagetool`` im Suchpfad oder unter ``werkzeuge/appimagetool``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mailburg import __version__  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent

#: Der Name ohne Fassungsnummer – siehe Modulkopf.
DATEINAME = "MailBurg-x86_64.AppImage"

#: **Der Starter im AppImage.** Er richtet die Umgebung ein und ruft das
#: gepackte Programm.
#:
#: ``APPDIR`` setzt AppImage selbst; darunter liegt alles. Der Rest sind
#: zwei Dinge, die MailBurg braucht und die sonst fehlen:
#:
#: * ``PATH`` um ``/usr/bin`` des Wirtssystems ergänzt zu lassen ist
#:   wichtig, weil die Texterkennung ``pdftotext`` und ``tesseract``
#:   dort sucht. Ein AppImage, das den Suchpfad überschreibt, findet sie
#:   nicht mehr – und meldet dann, sie seien nicht installiert, obwohl
#:   sie es sind.
#: * ``QT_QPA_PLATFORM`` bleibt **ungesetzt**. Qt entscheidet dann
#:   selbst zwischen Wayland und X11. Wer hier etwas festschreibt,
#:   bricht die jeweils andere Sitzung.
APPRUN = """\
#!/bin/sh
# Von werkzeuge/appimage_bauen.py erzeugt - nicht von Hand aendern.
HIER="$(dirname "$(readlink -f "$0")")"

# Der Suchpfad des Wirtssystems bleibt erhalten: Die Texterkennung
# braucht pdftotext und tesseract von dort.
export PATH="$HIER/usr/bin:$PATH"

exec "$HIER/usr/bin/MailBurg" "$@"
"""

#: Der Eintrag im Anwendungsmenü. ``Terminal=false`` wie beim
#: Debian-Paket – und aus demselben Grund gibt MailBurg seine Meldungen
#: seit der 1.4.6 auch als Fenster aus, nicht nur auf die Fehlerausgabe.
DESKTOP = """\
[Desktop Entry]
Type=Application
Name=MailBurg
GenericName=E-Mail-Archiv
Comment=Archiv fuer E-Mail, an einem Ort Ihrer Wahl
Exec=MailBurg %f
Icon=mailburg
Terminal=false
Categories=Office;Email;
Keywords=Mail;Archiv;E-Mail;Backup;IMAP;
StartupNotify=true
"""


def _appimagetool() -> str:
    """Wo ``appimagetool`` liegt – im Suchpfad oder daneben."""
    gefunden = shutil.which("appimagetool")
    if gefunden:
        return gefunden
    daneben = WURZEL / "werkzeuge" / "appimagetool"
    if daneben.is_file():
        return str(daneben)
    raise SystemExit(
        "appimagetool nicht gefunden. Es gehört in den Suchpfad oder nach "
        "werkzeuge/appimagetool.\n"
        "Zu holen unter https://github.com/AppImage/appimagetool/releases"
    )


def _symbol(ziel: Path) -> None:
    """Legt das Anwendungssymbol ab, wo AppImage es erwartet.

    **Ein AppImage ohne Symbol ist kein kaputtes, aber ein namenloses.**
    In der Menüleiste steht dann ein grauer Platzhalter, und wer drei
    Programme offen hat, findet seines nicht wieder.
    """
    quelle = WURZEL / "assets" / "icon.svg"
    if not quelle.is_file():
        raise SystemExit(f"Das Symbol fehlt: {quelle}")

    # Zweimal: einmal als Datei neben AppRun – dort sucht AppImage sie –
    # und einmal am ordentlichen Platz nach Freedesktop-Standard, damit
    # die Menüs des Systems sie nach dem Einhängen auch finden.
    shutil.copy2(quelle, ziel / "mailburg.svg")
    ordner = ziel / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    ordner.mkdir(parents=True, exist_ok=True)
    shutil.copy2(quelle, ordner / "mailburg.svg")


def appdir_bauen(dist: Path, ziel: Path) -> Path:
    """Baut den Verzeichnisbaum, aus dem das AppImage entsteht."""
    if not (dist / "MailBurg").exists():
        raise SystemExit(
            f"In {dist} liegt kein fertiges Programm.\n"
            f"Vorher laufen lassen:  pyinstaller werkzeuge/mailburg.spec"
        )

    appdir = ziel / "MailBurg.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    (appdir / "usr" / "bin").mkdir(parents=True)

    # PyInstaller liefert je nach Bauart eine einzelne Datei oder einen
    # Ordner. Beides wird gleich behandelt: Was da ist, kommt nach
    # usr/bin, und AppRun ruft MailBurg darin.
    quelle = dist / "MailBurg"
    if quelle.is_dir():
        shutil.copytree(quelle, appdir / "usr" / "bin", dirs_exist_ok=True)
    else:
        shutil.copy2(quelle, appdir / "usr" / "bin" / "MailBurg")
    (appdir / "usr" / "bin" / "MailBurg").chmod(0o755)

    starter = appdir / "AppRun"
    starter.write_text(APPRUN, encoding="utf-8")
    starter.chmod(0o755)

    # **Ein Skript, das nicht ausführbar ist, ist keines.** Am
    # 2026-09-14 hat dpkg-deb denselben Fehler im postinst gemeldet und
    # den Bau verweigert; AppImage merkt es nicht und baut ein Paket,
    # das sich nicht starten lässt.
    if not os.access(starter, os.X_OK):
        raise SystemExit("AppRun ist nicht ausführbar geworden.")

    eintrag = appdir / "mailburg.desktop"
    eintrag.write_text(DESKTOP, encoding="utf-8")
    ordner = appdir / "usr" / "share" / "applications"
    ordner.mkdir(parents=True, exist_ok=True)
    shutil.copy2(eintrag, ordner / "mailburg.desktop")

    _symbol(appdir)
    return appdir


def bauen(ziel: Path, dist: Path | None = None) -> Path:
    """Packt das AppImage und gibt seinen Pfad zurück."""
    ziel.mkdir(parents=True, exist_ok=True)
    appdir = appdir_bauen(dist or WURZEL / "dist", ziel)

    paket = ziel / DATEINAME
    if paket.exists():
        paket.unlink()

    umgebung = dict(os.environ)
    # Reproduzierbar: ohne diese Angabe steckt in jedem Lauf ein anderer
    # Zeitstempel, und zwei Bauten derselben Fassung wären verschieden.
    # Dieselbe Überlegung wie beim Debian-Paket.
    umgebung.setdefault("SOURCE_DATE_EPOCH", str(_bauzeit()))
    # Keine Zufallssignatur und keine Aktualisierungsangabe: Beides
    # verlangt Schlüssel und einen festen Ablageort, die es hier nicht
    # gibt. Ein AppImage, das nach einem Update-Kanal sucht, den niemand
    # betreibt, meldet dem Anwender nur Fehler.
    subprocess.run(
        [_appimagetool(), "--no-appstream", str(appdir), str(paket)],
        check=True, env=umgebung,
    )

    groesse = paket.stat().st_size / 1_048_576
    print(f"{paket}  ({groesse:.0f} MB)")
    return paket


def _bauzeit() -> int:
    """Der Zeitpunkt des letzten Commits, nicht der des Bauens."""
    try:
        ergebnis = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            cwd=WURZEL, capture_output=True, text=True, check=True,
        )
        return int(ergebnis.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        # Kein Git-Klon zur Hand – dann eben ein fester Wert. Er ist
        # willkürlich, aber gleichbleibend, und darum geht es hier.
        return 1_700_000_000


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ziel = Path(argv[0]) if argv else WURZEL / "dist"
    print(f"MailBurg {__version__} als AppImage")
    bauen(ziel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
