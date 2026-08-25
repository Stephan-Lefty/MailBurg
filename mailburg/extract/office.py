"""Text aus Büroformaten holen – ohne eine einzige Fremdbibliothek.

DOCX, XLSX, PPTX und die OpenDocument-Formate sind allesamt ZIP-Archive mit
XML darin. Das ist der ganze Trick: ``zipfile`` und ``xml`` stecken in der
Standardbibliothek, damit kommt man an den Text heran, ohne ``python-docx``,
``openpyxl`` und ``python-pptx`` mitzuschleppen.

Für ein Archivprogramm ist das mehr als Bequemlichkeit. Jede Abhängigkeit
ist etwas, das in zehn Jahren nicht mehr installierbar sein kann – und ein
Archiv soll dann noch durchsuchbar sein.

**Wir lesen absichtlich grob.** Es wird nicht versucht, das Dokument
originalgetreu nachzubilden; es interessiert nur, welche Wörter darin
vorkommen. Deshalb werden schlicht alle Textknoten eingesammelt, ohne auf
Namensräume zu achten. Das ist unempfindlich gegen Formatversionen: Ein
Word-Dokument von 2007 wird genauso behandelt wie eines von heute.
"""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

#: Höchstmenge Text je Dokument.
MAX_ZEICHEN = 400_000

#: Wo in den einzelnen Formaten der Text steckt. Reihenfolge zählt: Bei
#: Tabellen liefern die gemeinsamen Zeichenketten den meisten Inhalt.
QUELLEN: dict[str, tuple[str, ...]] = {
    # Word
    "docx": ("word/document.xml", "word/header*.xml", "word/footer*.xml"),
    # Excel: sharedStrings hält alle Texte der Mappe an einer Stelle
    "xlsx": ("xl/sharedStrings.xml", "xl/worksheets/sheet*.xml"),
    # PowerPoint: eine Datei je Folie
    "pptx": ("ppt/slides/slide*.xml", "ppt/notesSlides/notesSlide*.xml"),
    # OpenDocument: Text, Tabelle, Präsentation - immer dieselbe Datei
    "odt": ("content.xml",),
    "ods": ("content.xml",),
    "odp": ("content.xml",),
    "odg": ("content.xml",),
}

#: Endungen, die dieses Modul bedienen kann.
ENDUNGEN = frozenset(QUELLEN) | {"docm", "xlsm", "pptm"}

_LEERRAUM = re.compile(r"\s+")


def _passende_eintraege(archiv: zipfile.ZipFile, muster: str) -> list[str]:
    """Löst ein Muster wie ``ppt/slides/slide*.xml`` gegen den Archivinhalt auf."""
    if "*" not in muster:
        return [muster] if muster in archiv.namelist() else []
    regex = re.compile(re.escape(muster).replace(r"\*", r"[^/]*") + r"$")
    return sorted(n for n in archiv.namelist() if regex.match(n))


def _text_aus_xml(daten: bytes) -> str:
    """Sammelt allen Textinhalt aus einem XML-Baum ein.

    Ohne Rücksicht auf Namensräume oder Elementnamen: Was Text ist, wird
    genommen. Bei Fließtext liefert das genau die Wörter, auf die es bei der
    Suche ankommt.
    """
    try:
        wurzel = ElementTree.fromstring(daten)
    except ElementTree.ParseError:
        return ""

    teile: list[str] = []
    for element in wurzel.iter():
        if element.text and element.text.strip():
            teile.append(element.text)
        # Absatzenden gehen sonst verloren und Wörter kleben aneinander.
        if element.tail and element.tail.strip():
            teile.append(element.tail)
    return " ".join(teile)


def text_aus_zip_dokument(daten: bytes, endung: str) -> str:
    """Holt den Text aus einem ZIP-basierten Bürodokument."""
    endung = endung.lower().lstrip(".")
    # Die Makro-Varianten sind aufbaugleich mit ihren normalen Geschwistern.
    endung = {"docm": "docx", "xlsm": "xlsx", "pptm": "pptx"}.get(endung, endung)

    muster = QUELLEN.get(endung)
    if muster is None:
        return ""

    try:
        archiv = zipfile.ZipFile(io.BytesIO(daten))
    except (zipfile.BadZipFile, OSError):
        return ""

    teile: list[str] = []
    laenge = 0
    with archiv:
        for eines in muster:
            for name in _passende_eintraege(archiv, eines):
                try:
                    roh = archiv.read(name)
                except (KeyError, zipfile.BadZipFile, OSError, RuntimeError):
                    continue
                stueck = _text_aus_xml(roh)
                if stueck:
                    teile.append(stueck)
                    laenge += len(stueck)
                    if laenge > MAX_ZEICHEN:
                        break
            if laenge > MAX_ZEICHEN:
                break

    return _LEERRAUM.sub(" ", " ".join(teile)).strip()[:MAX_ZEICHEN]


def text_aus_rtf(daten: bytes) -> str:
    """Holt den Text aus einer RTF-Datei.

    RTF ist eine Auszeichnungssprache mit Steuerwörtern, die mit einem
    Rückstrich beginnen. Für die Suche genügt es, diese samt geschweifter
    Klammern zu entfernen – ein vollständiger Parser wäre für den Zweck
    weit übertrieben.
    """
    if not daten.startswith(b"{\\rt"):
        return ""
    text = daten.decode("cp1252", errors="replace")

    # Umlaute stehen als \'e4 und ähnlich.
    text = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), text)
    # Gruppen, die nur Verwaltungsangaben enthalten, ganz weg.
    text = re.sub(r"\{\\\*[^{}]*\}", " ", text)
    # Übrige Steuerwörter entfernen.
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
    text = text.replace("{", " ").replace("}", " ").replace("\\", " ")
    return _LEERRAUM.sub(" ", text).strip()[:MAX_ZEICHEN]
