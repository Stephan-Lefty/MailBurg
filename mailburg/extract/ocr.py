"""Texterkennung für eingescannte PDF.

Mehr als die Hälfte der PDF in einem gewachsenen Postfach sind Scans: die
Rechnung des Handwerkers, der Bescheid vom Amt, der unterschriebene Vertrag,
den jemand eingescannt zurückgeschickt hat. Ausgerechnet die Dokumente also,
die man später sucht. Ohne Texterkennung stehen sie im Archiv und sind doch
nicht zu finden.

**Der Weg:** ``pdftoppm`` macht aus jeder Seite ein Bild, ``tesseract`` liest
es. Beides sind eigenständige Programme; poppler ist ohnehin schon
Voraussetzung für ``pdftotext``, tesseract kommt hinzu. Ohne sie läuft
MailBurg weiter, nur bleiben Scans eben unauffindbar.

**Warum nicht ocrmypdf:** Das schreibt ein neues PDF mit eingebettetem Text.
Wir wollen aber nur den Text für den Suchindex – das Dokument im Archiv
bleibt unangetastet, sonst wäre die Unveränderbarkeit dahin und mit ihr der
Sinn der Hash-Kette.

**Warum das teuer ist:** Fünf bis dreißig Sekunden je Seite. Deshalb wird
hier nichts von allein gestartet; der Aufrufer bestimmt über ``abbruch``, wie
lange er bereit ist zu warten, und bekommt zurück, wie weit es gekommen ist.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

#: Auflösung für die Umwandlung in Bilder. 300 dpi ist der übliche Wert für
#: Texterkennung – darunter leidet die Trefferquote bei kleiner Schrift
#: spürbar, darüber steigt nur die Rechenzeit.
AUFLOESUNG = 300

#: Ab dieser Dateigröße wird gröber gerastert. Ein 23-MB-Scan ergibt bei
#: 300 dpi Bilder von dreißig Megabyte, und eine einzige Seite braucht
#: dann zwei Minuten – genau so lange, wie die Zeitgrenze erlaubt. Mit
#: 200 dpi liest tesseract solche Seiten immer noch zuverlässig; unter
#: 200 wird es unsicher, deshalb nicht weiter herunter.
GROSS_AB = 8 * 1024 * 1024
AUFLOESUNG_GROSS = 200

#: So viele Seiten je Dokument, mehr nicht. Ein zweihundertseitiges
#: eingescanntes Handbuch würde sonst eine Stunde binden – und wer danach
#: sucht, findet es über die ersten Seiten genauso.
MAX_SEITEN = 20

#: Zeitgrenze je Seite. Es gibt Bilder, an denen sich tesseract festbeißt.
ZEITGRENZE_SEITE = 120

#: Bevorzugte Sprachen. Deutsch zuerst, Englisch dazu – in deutscher
#: Geschäftspost stecken genug englische Rechnungen.
SPRACHEN = ("deu", "eng")


@dataclass
class Ergebnis:
    """Was bei der Erkennung eines Dokuments herauskam."""

    text: str = ""
    seiten: int = 0
    """Wie viele Seiten tatsächlich gelesen wurden."""

    seiten_gesamt: int = 0
    abgebrochen: bool = False
    """Ob wegen Zeitablauf aufgehört wurde – dann ist der Text unvollständig."""

    fehler: str = ""

    @property
    def geglueckt(self) -> bool:
        return bool(self.text.strip())


def verfuegbar() -> bool:
    """Sagt, ob Texterkennung überhaupt möglich ist."""
    return bool(shutil.which("tesseract") and shutil.which("pdftoppm"))


def sprachen_vorhanden() -> set[str]:
    """Welche Sprachdaten tesseract kennt.

    Ohne die passende Sprache ist die Erkennung fast wertlos: Ein deutscher
    Text, mit englischem Modell gelesen, wird zu Buchstabensalat mit
    zerstörten Umlauten. Lieber gar nicht erkennen als falsch.
    """
    if not shutil.which("tesseract"):
        return set()
    try:
        ergebnis = subprocess.run(
            ["tesseract", "--list-langs"], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    # Die erste Zeile ist eine Überschrift, danach eine Sprache je Zeile.
    zeilen = ergebnis.stdout.splitlines()[1:]
    return {z.strip() for z in zeilen if z.strip()}


def sprachwahl() -> str:
    """Baut den Sprachparameter aus dem, was vorhanden ist."""
    vorhanden = sprachen_vorhanden()
    gewaehlt = [s for s in SPRACHEN if s in vorhanden]
    return "+".join(gewaehlt)


def bereit() -> tuple[bool, str]:
    """Prüft die Voraussetzungen und erklärt, was gegebenenfalls fehlt."""
    if not shutil.which("pdftoppm"):
        return False, (
            "poppler fehlt (pdftoppm). Unter Debian: sudo apt install poppler-utils, "
            "unter Arch: sudo pacman -S poppler"
        )
    if not shutil.which("tesseract"):
        return False, (
            "tesseract fehlt. Unter Debian: sudo apt install tesseract-ocr "
            "tesseract-ocr-deu, unter Arch: sudo pacman -S tesseract tesseract-data-deu"
        )
    if not sprachwahl():
        return False, (
            f"tesseract ist da, aber ohne brauchbare Sprachdaten. Vorhanden: "
            f"{', '.join(sorted(sprachen_vorhanden())) or 'keine'}. Gebraucht wird "
            f"mindestens 'deu'. Unter Debian: sudo apt install tesseract-ocr-deu, "
            f"unter Arch: sudo pacman -S tesseract-data-deu"
        )
    return True, ""


def _seitenzahl(pdf: Path) -> int:
    try:
        ergebnis = subprocess.run(
            ["pdfinfo", str(pdf)], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0
    for zeile in ergebnis.stdout.splitlines():
        if zeile.startswith("Pages:"):
            try:
                return int(zeile.split(":", 1)[1].strip())
            except ValueError:
                return 0
    return 0


def text_aus_pdf(
    daten: bytes,
    *,
    abbruch: Callable[[], bool] | None = None,
    max_seiten: int = MAX_SEITEN,
    je_seite: Callable[[int, int], None] | None = None,
) -> Ergebnis:
    """Liest ein eingescanntes PDF Seite für Seite.

    ``je_seite`` bekommt nach jeder gelesenen Seite die Nummer und die
    Gesamtzahl. Ohne diese Rückmeldung steht eine Oberfläche bei einem
    zwanzigseitigen Dokument fast zwei Minuten auf demselben Wert – und
    wer nichts sieht, hält das Programm für abgestürzt.

    ``abbruch`` wird vor jeder Seite gefragt. Sagt es ja, wird der bis dahin
    gewonnene Text zurückgegeben und ``abgebrochen`` gesetzt – angefangene
    Arbeit soll nicht verfallen, nur weil das Zeitbudget aufgebraucht ist.
    """
    ergebnis = Ergebnis()
    if not daten.startswith(b"%PDF"):
        ergebnis.fehler = "keine PDF-Datei"
        return ergebnis

    sprachen = sprachwahl()
    if not sprachen:
        ergebnis.fehler = "keine Sprachdaten für tesseract"
        return ergebnis

    with tempfile.TemporaryDirectory(prefix="mailburg-ocr-") as verzeichnis:
        ordner = Path(verzeichnis)
        quelle = ordner / "dokument.pdf"
        quelle.write_bytes(daten)

        ergebnis.seiten_gesamt = _seitenzahl(quelle)
        letzte = min(max_seiten, ergebnis.seiten_gesamt or max_seiten)
        raster = AUFLOESUNG_GROSS if len(daten) >= GROSS_AB else AUFLOESUNG

        teile: list[str] = []
        for nummer in range(1, letzte + 1):
            if abbruch and abbruch():
                ergebnis.abgebrochen = True
                break

            bild = ordner / f"seite-{nummer}"
            try:
                # Seite für Seite umwandeln statt alles auf einmal: Ein
                # Dutzend Bilder zu 300 dpi wären über hundert Megabyte,
                # und beim Abbruch wäre die Arbeit dafür umsonst gewesen.
                subprocess.run(
                    ["pdftoppm", "-png", "-r", str(raster),
                     "-f", str(nummer), "-l", str(nummer),
                     "-singlefile", str(quelle), str(bild)],
                    capture_output=True,
                    timeout=ZEITGRENZE_SEITE,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue

            png = bild.with_suffix(".png")
            if not png.exists():
                # Über die letzte Seite hinaus - dann sind wir fertig.
                break

            try:
                gelesen = subprocess.run(
                    ["tesseract", str(png), "stdout", "-l", sprachen, "--psm", "3"],
                    capture_output=True,
                    timeout=ZEITGRENZE_SEITE,
                    check=False,
                )
                teile.append(gelesen.stdout.decode("utf-8", errors="replace"))
                ergebnis.seiten += 1
                if je_seite:
                    je_seite(nummer, letzte)
            except (OSError, subprocess.TimeoutExpired):
                pass
            finally:
                png.unlink(missing_ok=True)

    ergebnis.text = "\n".join(teile).strip()
    if not ergebnis.text and not ergebnis.fehler and not ergebnis.abgebrochen:
        # Kommt vor: eine leere Rückseite, ein völlig unleserlicher Scan.
        ergebnis.fehler = "kein Text erkannt"
    return ergebnis
