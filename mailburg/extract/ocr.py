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
import os
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mailburg.core import werkzeuge

# **Beim Import, nicht erst beim ersten Auftrag.** Alles hier fragt über
# ``shutil.which`` nach den Programmen; steht der mitgelieferte Ordner
# dann noch nicht im Suchpfad, meldet MailBurg »tesseract fehlt« und
# schaltet die Texterkennung ab, obwohl sie eingepackt danebenliegt.
# Unter Linux findet das nichts und ändert nichts.
werkzeuge.bereitstellen()

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

#: Wie viele Bildpunkte die längere Seitenkante höchstens bekommt.
#:
#: **Die Auflösung allein genügt nicht.** 300 dpi sind eine Angabe je
#: Zoll – wie groß das Bild wird, hängt daran, wie groß die Seite ist.
#: Ein A4-Blatt ergibt 2480 × 3508 Punkte, also knapp neun Megapixel.
#: Ein Scan aus der iPhone-Kamera-App misst dagegen 4507 × 6681 Punkte
#: statt 595 × 842 – bei 300 dpi wären das **523 Megapixel**. Daran
#: erstickt tesseract; es liefert keinen Fehler, sondern nichts.
#:
#: Am 2026-08-26 an einem echten Archiv gefunden: Von sechs Dokumenten,
#: die als »kein Text erkannt« liegengeblieben waren, gingen zwei
#: hierauf zurück – ein Wohnungsgrundriss und eine Zeugnismappe. Mit
#: passender Auflösung liest tesseract beide einwandfrei.
#:
#: 5000 ist gemessen, nicht geschätzt. Am selben Wohnungsgrundriss
#: durchprobiert: bei 8 Megapixeln kommt der Text, bei 16 derselbe, bei
#: 33 sogar etwas mehr. Die Grenze liegt also weit über dem, was nötig
#: ist – und deutlich unter dem, was den Rechner lahmlegt, wenn sechs
#: Dokumente nebeneinander gelesen werden.
#:
#: Der Wert ist zugleich so hoch, dass für alle üblichen Papierformate
#: gar nichts eingegriffen wird: A4 braucht bei 300 dpi 3508 Punkte,
#: A3 deren 4961. Erst darüber greift die Begrenzung.
MAX_KANTE = 5000
MAX_KANTE_GROSS = 3400

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


def _windows() -> bool:
    return os.name == "nt"


def bereit() -> tuple[bool, str]:
    """Prüft die Voraussetzungen und erklärt, was gegebenenfalls fehlt.

    **Der Rat muss zum System passen.** »sudo apt install« hilft niemandem
    unter Windows weiter; es sagt ihm nur, dass er hier falsch ist. Und
    wer dort die gepackte Fassung benutzt, soll überhaupt nichts
    nachinstallieren müssen - kommt diese Meldung trotzdem, ist etwas mit
    der Datei nicht in Ordnung, und genau das gehört dann dagestanden.
    """
    if not shutil.which("pdftoppm"):
        if _windows():
            return False, (
                "Die Texterkennung fehlt (pdftoppm aus poppler). In der "
                "fertigen MailBurg.exe ist sie enthalten - fehlt sie dort, "
                "ist die Datei unvollständig heruntergeladen worden. Wer "
                "MailBurg aus den Quellen betreibt, installiert poppler "
                "mit: winget install oschwartz10612.Poppler"
            )
        return False, (
            "poppler fehlt (pdftoppm). Unter Debian: sudo apt install poppler-utils, "
            "unter Arch: sudo pacman -S poppler"
        )
    if not shutil.which("tesseract"):
        if _windows():
            return False, (
                "Die Texterkennung fehlt (tesseract). In der fertigen "
                "MailBurg.exe ist sie enthalten - fehlt sie dort, ist die "
                "Datei unvollständig heruntergeladen worden. Wer MailBurg "
                "aus den Quellen betreibt, installiert sie mit: "
                "winget install UB-Mannheim.TesseractOCR"
            )
        return False, (
            "tesseract fehlt. Unter Debian: sudo apt install tesseract-ocr "
            "tesseract-ocr-deu, unter Arch: sudo pacman -S tesseract tesseract-data-deu"
        )
    if not sprachwahl():
        vorhanden = ", ".join(sorted(sprachen_vorhanden())) or "keine"
        if _windows():
            return False, (
                f"tesseract ist da, aber ohne deutsche Sprachdaten. "
                f"Vorhanden: {vorhanden}. Ein deutscher Text mit englischem "
                f"Modell gelesen wird zu Buchstabensalat mit zerstörten "
                f"Umlauten - lieber gar nicht erkennen als falsch. Bei "
                f"eigener Installation fehlt meist das Häkchen bei "
                f"»German« im tesseract-Setup."
            )
        return False, (
            f"tesseract ist da, aber ohne brauchbare Sprachdaten. Vorhanden: "
            f"{vorhanden}. Gebraucht wird "
            f"mindestens 'deu'. Unter Debian: sudo apt install tesseract-ocr-deu, "
            f"unter Arch: sudo pacman -S tesseract-data-deu"
        )
    return True, ""


@dataclass
class Seitenmasse:
    """Was ``pdfinfo`` über ein Dokument sagt."""

    seiten: int = 0
    breite: float = 0.0
    """Breite der ersten Seite in Punkten. 595 wäre A4 hochkant."""

    hoehe: float = 0.0
    verschluesselt: bool = False
    """Ob ein Passwort verlangt wird – dann geht gar nichts."""


def _pdfinfo(pdf: Path) -> Seitenmasse:
    """Seitenzahl, Seitengröße und Verschlüsselung in einem Aufruf.

    Alles drei kommt aus demselben ``pdfinfo``. Die Seitengröße wird
    gebraucht, um die Auflösung zu wählen (siehe :data:`MAX_KANTE`); die
    Verschlüsselung, um dem Anwender etwas anderes sagen zu können als
    »kein Text erkannt«. Ein Dokument, das nach einem Passwort verlangt,
    ist nicht kaputt – es ist zu.
    """
    masse = Seitenmasse()
    try:
        ergebnis = subprocess.run(
            ["pdfinfo", str(pdf)], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return masse

    if "Incorrect password" in (ergebnis.stderr or ""):
        masse.verschluesselt = True
        return masse

    for zeile in ergebnis.stdout.splitlines():
        if zeile.startswith("Pages:"):
            try:
                masse.seiten = int(zeile.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif zeile.startswith("Page size:"):
            # "Page size:  595.276 x 841.89 pts (A4)"
            teile = zeile.split(":", 1)[1].split()
            try:
                masse.breite = float(teile[0])
                masse.hoehe = float(teile[2])
            except (IndexError, ValueError):
                pass
        elif zeile.startswith("Encrypted:") and "yes" in zeile:
            # Verschlüsselt heißt nicht immer gesperrt: Viele PDF sind
            # nur gegen Drucken geschützt und lassen sich lesen. Erst
            # wenn pdfinfo gar nichts herausrückt, ist wirklich zu.
            masse.verschluesselt = not masse.seiten
    return masse


def _aufloesung(masse: Seitenmasse, gross: bool) -> int:
    """Die Auflösung, bei der das Seitenbild handhabbar bleibt.

    Für alles in üblichen Papierformaten kommt hier der gewohnte Wert
    heraus. Erst bei Seiten, die um ein Vielfaches größer sind, greift
    die Begrenzung – und zwar so, dass die längere Kante ungefähr so
    viele Bildpunkte bekommt wie ein A4-Blatt bei 300 dpi.
    """
    standard = AUFLOESUNG_GROSS if gross else AUFLOESUNG
    kante_pt = max(masse.breite, masse.hoehe)
    if kante_pt <= 0:
        return standard
    grenze = MAX_KANTE_GROSS if gross else MAX_KANTE
    passend = int(grenze / (kante_pt / 72))
    # Unter 30 dpi wird auch großer Text unleserlich. Lieber ein Bild,
    # das tesseract vielleicht noch schafft, als sicher nichts.
    return max(30, min(standard, passend))


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

        masse = _pdfinfo(quelle)
        if masse.verschluesselt:
            # Nicht als Fehlschlag verbuchen wie ein unlesbares Bild:
            # Hier ist nichts kaputt, hier fehlt ein Passwort. Wer die
            # Meldung liest, soll wissen, ob es sich lohnt nachzusehen.
            ergebnis.fehler = "passwortgeschützt – ohne Kennwort nicht lesbar"
            return ergebnis

        ergebnis.seiten_gesamt = masse.seiten
        letzte = min(max_seiten, ergebnis.seiten_gesamt or max_seiten)
        raster = _aufloesung(masse, gross=len(daten) >= GROSS_AB)

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
                    # Ein Faden je Aufruf. Tesseract nimmt sich sonst
                    # alle Kerne - was allein schneller ist, sich aber
                    # selbst im Weg steht, sobald mehrere Dokumente
                    # gleichzeitig gelesen werden.
                    env={**os.environ, "OMP_THREAD_LIMIT": "1"},
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
