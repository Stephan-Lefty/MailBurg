"""Text aus PDF-Dateien holen.

PDF ist der wichtigste Fall: Rechnungen, Verträge, Bescheide – alles, was
man später wiederfinden will, kommt als PDF. In einem Beispielarchiv machen
PDF zwar nur ein Fünftel der Anhänge aus, aber die Hälfte des Umfangs.

**Zwei Wege, in dieser Reihenfolge:**

1. ``pdftotext`` aus poppler, falls vorhanden. Deutlich schneller als alles
   in Python, weil in C geschrieben, und robuster gegenüber den vielen
   PDF-Dateien, die sich nicht an die Spezifikation halten.
2. ``pypdf``, falls installiert. Langsamer, aber ohne Fremdprogramm.

Ist keines von beidem da, bleibt der Text leer – die Mail wird trotzdem
archiviert, nur eben ohne durchsuchbaren Anhangsinhalt. Ein fehlendes
Hilfsprogramm darf niemals dazu führen, dass Post nicht gesichert wird.

**Nicht PyMuPDF**, obwohl es das schnellste wäre: Es steht unter der AGPL
und würde dieses MIT-Projekt anstecken, sobald es mitgeliefert wird.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from mailburg.core import werkzeuge

#: Mehr Text nehmen wir aus einem einzelnen Dokument nicht auf. Ein
#: tausendseitiges Handbuch macht die Suche nicht besser, den Index aber
#: deutlich größer.
MAX_ZEICHEN = 400_000

#: Nach dieser Zeit brechen wir ab. Es gibt PDF-Dateien, an denen sich jeder
#: Parser festbeißt – ein einziges davon darf keinen Archivlauf aufhalten.
ZEITGRENZE = 30


def verfuegbar() -> str | None:
    """Sagt, womit PDF gelesen werden können: ``poppler``, ``pypdf`` oder nichts."""
    if shutil.which("pdftotext"):
        return "poppler"
    try:
        import pypdf  # noqa: F401

        return "pypdf"
    except ImportError:
        return None


def _mit_poppler(daten: bytes) -> str:
    """Ruft ``pdftotext`` auf und liest das Ergebnis von der Standardausgabe."""
    # Über eine temporäre Datei, weil pdftotext auf der Standardeingabe
    # nicht springen kann - PDF wird aber von hinten nach vorn gelesen.
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(daten)
        tmp.flush()
        ergebnis = subprocess.run(
            ["pdftotext", "-q", "-enc", "UTF-8", "-nopgbrk", tmp.name, "-"],
            capture_output=True,
            timeout=ZEITGRENZE,
            **werkzeuge.lautlos(),
        )
    # Auch bei Rückgabewert ungleich null kann brauchbarer Text dabei sein:
    # poppler meldet Fehler für einzelne Seiten, liefert die übrigen aber.
    return ergebnis.stdout.decode("utf-8", errors="replace")


def _mit_pypdf(daten: bytes) -> str:
    import io

    from pypdf import PdfReader

    leser = PdfReader(io.BytesIO(daten))
    teile = []
    for seite in leser.pages:
        try:
            teile.append(seite.extract_text() or "")
        except Exception:  # noqa: BLE001 – eine kaputte Seite kostet nicht das Dokument
            continue
        if sum(len(t) for t in teile) > MAX_ZEICHEN:
            break
    return "\n".join(teile)


def text_aus_pdf(daten: bytes) -> str:
    """Holt den Text aus einer PDF-Datei. Gibt bei Misserfolg leeren Text zurück."""
    if not daten.startswith(b"%PDF"):
        return ""

    weg = verfuegbar()
    try:
        if weg == "poppler":
            text = _mit_poppler(daten)
        elif weg == "pypdf":
            text = _mit_pypdf(daten)
        else:
            return ""
    except (subprocess.TimeoutExpired, OSError, Exception):  # noqa: BLE001
        return ""

    return text[:MAX_ZEICHEN]


def ist_wohl_gescannt(daten: bytes, text: str) -> bool:
    """Schätzt, ob ein PDF nur eingescannte Seiten enthält.

    Ein umfangreiches Dokument, aus dem kaum Text herauskommt, besteht
    vermutlich aus Bildern. Solche Dateien bräuchten Texterkennung, um
    durchsuchbar zu werden – dafür ist noch nichts eingebaut, aber es lohnt,
    sie zu erkennen und zu zählen.
    """
    return len(daten) > 100_000 and len(text.strip()) < 200
