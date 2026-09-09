"""Baut ein Debian-Paket aus dem Quellbaum.

**Warum ein natives Paket und keine gepackte Datei.** Unter Windows
liefert MailBurg eine einzelne ``.exe`` mit allem darin – dort gibt es
keine Paketverwaltung, die Qt oder poppler beistellen könnte. Unter
Debian gibt es sie, und ein Paket, das sein eigenes Qt mitbringt,
bekommt dessen Sicherheitsupdates nie. Deshalb stehen die Abhängigkeiten
hier als ``Depends`` und kommen aus der Distribution.

Der Preis dafür: Die Paketnamen müssen stimmen, und das lässt sich nur
auf einem Debian-System prüfen. Genau das tut ``.github/workflows/deb.yml``
– es installiert das gebaute Paket wirklich und startet MailBurg danach.
Ein Paket, das sich bauen, aber nicht installieren lässt, wäre schlimmer
als keines.

**Ohne Fremdwerkzeuge.** Gebraucht wird allein ``dpkg-deb``, das auf
jedem Debian-System liegt. Kein ``fpm``, kein ``debhelper``, keine
Bauabhängigkeit, die in zwei Jahren anders heißt.
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from mailburg import __version__  # noqa: E402

#: Was ohne MailBurg selbst nicht läuft. Bewusst kurz gehalten: Der Kern
#: kommt ohne jedes Fremdpaket aus, und wer nur die Kommandozeile
#: braucht, soll sich kein Qt installieren müssen.
#:
#: ``python3`` deckt die Kommandozeile ab. Alles andere steht unter
#: *Recommends* – apt installiert es von Haus aus mit, wer es nicht
#: will, kann es abwählen.
DEPENDS = "python3 (>= 3.11)"

#: Die übliche Ausstattung eines Arbeitsplatzes. **Recommends und nicht
#: Depends**, damit MailBurg auch auf einen Server passt, auf dem es
#: kein Qt gibt – die Server-Variante braucht keine Oberfläche.
RECOMMENDS = ", ".join((
    "python3-pyside6.qtwidgets",   # die Oberfläche
    "python3-keyring",             # Passwörter, sonst jedes Mal neu
    "python3-cryptography",        # verschlüsselte Archive und Tresor
    "python3-pypdf",               # PDF-Anhänge durchsuchbar
    "poppler-utils",               # pdftotext, der schnellere Weg
))

#: Was den Funktionsumfang abrundet, aber selten gebraucht wird.
SUGGESTS = ", ".join((
    "tesseract-ocr",               # eingescannte PDF lesen
    "tesseract-ocr-deu",
    "python3-zstandard",           # bessere Packung; ab 3.14 eingebaut
    "python3-starlette",           # Das Archiv im Browser
    "python3-uvicorn",
))

BESCHREIBUNG = """\
 MailBurg holt E-Mail aus beliebig vielen Postfaechern zusammen, legt sie
 an einem frei gewaehlten Ort ab und macht sie durchsuchbar - Mailtexte,
 Kopfzeilen und den Inhalt der Anhaenge.
 .
 Jede Nachricht liegt bytegenau als einzelne .eml-Datei; der Dateiname
 ist der SHA-256 ihres Inhalts. Das Archiv laesst sich damit auch ohne
 MailBurg lesen, und eine beschaedigte Datei faellt beim Lesen von selbst
 auf. Ein Protokoll mit Hash-Kette haelt jeden Vorgang fest.
 .
 Fuer geschaeftliche Post gibt es Aufbewahrungsfristen (DE, AT, CH),
 Einstufung nach Belegart und einen Auskunftsexport nach Art. 15 DSGVO.
 MailBurg unterstuetzt revisionssicheren Betrieb, es stellt ihn nicht
 her - dazu gehoeren Verfahrensdokumentation und geregelte Ablaeufe.
"""


def _starter(modul: str, funktion: str) -> str:
    """Ein Startskript, das ohne installiertes pip auskommt.

    Die Einstiegspunkte aus ``pyproject.toml`` erzeugt ``pip``; in einem
    Debian-Paket gibt es kein pip, das sie schreiben könnte. Drei Zeilen
    Python tun dasselbe und hängen an nichts.
    """
    return (
        "#!/usr/bin/python3\n"
        "import sys\n"
        f"from {modul} import {funktion}\n"
        f"sys.exit({funktion}())\n"
    )


DESKTOP = """\
[Desktop Entry]
Type=Application
Name=MailBurg
GenericName=E-Mail-Archiv
Comment=E-Mails sammeln, aufbewahren und durchsuchen
Exec=mailburg-gui %f
Icon=mailburg
Terminal=false
Categories=Office;Email;
Keywords=Mail;E-Mail;Archiv;Suche;IMAP;
StartupNotify=true
"""


def _saeubern(ordner: Path) -> None:
    """Wirft weg, was in ein Paket nicht gehört."""
    for pfad in list(ordner.rglob("__pycache__")):
        shutil.rmtree(pfad, ignore_errors=True)
    for muster in ("*.pyc", "*.pyo"):
        for pfad in list(ordner.rglob(muster)):
            pfad.unlink(missing_ok=True)


def _bauzeit() -> str:
    """Ein Zeitstempel, der zum Quellstand gehört – nicht zur Bauzeit.

    **Damit zwei Bauläufe dasselbe Paket ergeben.** Sonst unterscheiden
    sich zwei Pakete aus demselben Stand, und niemand kann belegen, dass
    ein heruntergeladenes ``.deb`` wirklich aus dem Commit stammt, der
    dabeisteht. ``dpkg-deb`` liest dafür ``SOURCE_DATE_EPOCH``.

    Genommen wird das Datum des letzten Commits; ohne Git-Auskunft das
    des Änderungsprotokolls, das sich mit jeder Fassung ändert.
    """
    try:
        ergebnis = subprocess.run(
            ["git", "-C", str(WURZEL), "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        stempel = ergebnis.stdout.strip()
        if stempel.isdigit():
            return stempel
    except (OSError, subprocess.SubprocessError):
        pass
    return str(int((WURZEL / "CHANGELOG.md").stat().st_mtime))


def bauen(ziel: Path) -> Path:
    """Legt den Paketbaum an und ruft ``dpkg-deb``."""
    bau = ziel / "bau"
    if bau.exists():
        shutil.rmtree(bau)

    # --- Das Programm selbst ------------------------------------------
    dist = bau / "usr/lib/python3/dist-packages/mailburg"
    shutil.copytree(WURZEL / "mailburg", dist)
    _saeubern(dist)

    # **Die Bilder gehören mit.** Sie liegen im Quellbaum unter
    # ``assets/`` und werden über ``mailburg/bilder.py`` gesucht; ohne
    # sie hat die Weboberfläche kein Wappen und das Fenster kein Banner.
    shutil.copytree(WURZEL / "assets", dist / "assets")
    _saeubern(dist / "assets")

    # --- Startbefehle --------------------------------------------------
    binaer = bau / "usr/bin"
    binaer.mkdir(parents=True)
    for name, modul, funktion in (
        ("mailburg", "mailburg.__main__", "main"),
        ("mailburg-gui", "mailburg.ui.app", "main"),
    ):
        datei = binaer / name
        datei.write_text(_starter(modul, funktion), encoding="utf-8")
        datei.chmod(0o755)

    # --- Menüeintrag und Symbole ---------------------------------------
    anwendungen = bau / "usr/share/applications"
    anwendungen.mkdir(parents=True)
    (anwendungen / "de.stephanlefty.MailBurg.desktop").write_text(
        DESKTOP, encoding="utf-8"
    )

    for groesse in (16, 32, 48, 64, 128, 256):
        quelle = WURZEL / "assets" / f"icon-{groesse}.png"
        if not quelle.exists():
            continue
        ort = bau / f"usr/share/icons/hicolor/{groesse}x{groesse}/apps"
        ort.mkdir(parents=True, exist_ok=True)
        shutil.copy2(quelle, ort / "mailburg.png")

    svg = WURZEL / "assets" / "icon.svg"
    if svg.exists():
        ort = bau / "usr/share/icons/hicolor/scalable/apps"
        ort.mkdir(parents=True, exist_ok=True)
        shutil.copy2(svg, ort / "mailburg.svg")

    # --- Papiere -------------------------------------------------------
    doku = bau / "usr/share/doc/mailburg"
    doku.mkdir(parents=True)
    (doku / "copyright").write_text(
        "Format: https://www.debian.org/doc/packaging-manuals/"
        "copyright-format/1.0/\n"
        "Upstream-Name: MailBurg\n"
        "Source: https://github.com/Stephan-Lefty/MailBurg\n"
        "\n"
        "Files: *\n"
        "Copyright: Stephan Roesner\n"
        "License: MIT\n"
        + "".join(
            " " + zeile if zeile.strip() else " .\n"
            for zeile in (WURZEL / "LICENSE").read_text(
                encoding="utf-8"
            ).splitlines(keepends=True)
        ),
        encoding="utf-8",
    )
    # Ein Änderungsprotokoll gehört ins Paket, gepackt – lintian besteht
    # darauf, und wer wissen will, was sich geändert hat, sucht es dort.
    #
    # ``mtime=0``, damit zwei Bauläufe aus demselben Stand dieselbe Datei
    # ergeben. ``gzip.open`` kennt den Parameter nicht, ``GzipFile`` schon.
    with (doku / "changelog.gz").open("wb") as roh:
        with gzip.GzipFile(
            filename="changelog", mode="wb", fileobj=roh, mtime=0
        ) as f:
            f.write((WURZEL / "CHANGELOG.md").read_bytes())

    # --- Steuerdatei ---------------------------------------------------
    steuer = bau / "DEBIAN"
    steuer.mkdir()
    groesse_kb = sum(
        p.stat().st_size for p in bau.rglob("*") if p.is_file()
    ) // 1024
    (steuer / "control").write_text(
        f"Package: mailburg\n"
        f"Version: {__version__}\n"
        f"Section: mail\n"
        f"Priority: optional\n"
        f"Architecture: all\n"
        f"Depends: {DEPENDS}\n"
        f"Recommends: {RECOMMENDS}\n"
        f"Suggests: {SUGGESTS}\n"
        f"Installed-Size: {groesse_kb}\n"
        f"Maintainer: Stephan Roesner <noreply@github.com>\n"
        f"Homepage: https://github.com/Stephan-Lefty/MailBurg\n"
        f"Description: Archiv fuer E-Mail, an einem Ort Ihrer Wahl\n"
        f"{BESCHREIBUNG}",
        encoding="utf-8",
    )

    # --- Packen --------------------------------------------------------
    paket = ziel / f"mailburg_{__version__}_all.deb"
    if paket.exists():
        paket.unlink()
    # **Rechte setzen, bevor gepackt wird.** dpkg-deb übernimmt sie, wie
    # sie sind; kommt der Baum aus einem Git-Klon mit umask 002, hätte
    # das fertige Paket gruppenschreibbare Verzeichnisse.
    for pfad in bau.rglob("*"):
        if pfad.is_dir():
            pfad.chmod(0o755)
        elif pfad.parent.name == "bin":
            pfad.chmod(0o755)
        else:
            pfad.chmod(0o644)
    bau.chmod(0o755)

    # Auch die Zeitstempel der Dateien selbst, sonst steckt in jedem
    # Paket der Augenblick des Kopierens.
    zeit = int(_bauzeit())
    for pfad in sorted(bau.rglob("*")) + [bau]:
        os.utime(pfad, (zeit, zeit))

    subprocess.run(
        ["dpkg-deb", "--root-owner-group", "--build", str(bau), str(paket)],
        check=True,
        env={**os.environ, "SOURCE_DATE_EPOCH": str(zeit)},
    )
    return paket


def main(argv: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    zerleger.add_argument(
        "ziel", nargs="?", default="dist",
        help="wohin das Paket soll (Vorgabe: dist/)",
    )
    args = zerleger.parse_args(argv)

    if shutil.which("dpkg-deb") is None:
        print(
            "dpkg-deb fehlt. Es liegt auf jedem Debian-System im Paket "
            "»dpkg«;\nunter Arch und Manjaro heißt es »dpkg«.",
            file=sys.stderr,
        )
        return 2

    ziel = Path(args.ziel)
    ziel.mkdir(parents=True, exist_ok=True)
    paket = bauen(ziel)
    print(f"{paket}  ({paket.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
