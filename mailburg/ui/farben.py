"""Die wenigen Farben, die MailBurg selbst festlegt.

Fast alles überlässt die Oberfläche dem System: Auswahl, Hintergrund,
Schrift, Akzent. Wer die Systemfarben überschreibt, sieht auf jedem
fremden Desktop falsch aus und bricht Hochkontrast-Themen.

Zwei Farben lassen sich aber nicht ableiten, weil sie eine *Bedeutung*
tragen und keine Rolle: »hat geklappt« und »ist schiefgegangen«. Dafür
gibt es in keiner Qt-Palette einen Eintrag.

Und genau die müssen zum Thema passen. Ein festes ``#c62828`` erreicht
auf weißem Grund ein Kontrastverhältnis von 5,6 – auf dunklem nur 2,7.
Verlangt sind 4,5 (WCAG AA). Ausgerechnet »Anmeldung gescheitert« wäre
im dunklen Thema also die am schlechtesten lesbare Zeile im Fenster.
"""

from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

#: Für helle Themen. Nachgerechnet auf Weiß: 5,1 und 5,6.
_HELL = {"gut": "#2e7d32", "schlecht": "#c62828"}

#: Für dunkle. Nachgerechnet auf dem üblichen Breeze-Dunkel (#232629):
#: 8,0 und 7,3. Dieselben Farbtöne, nur aufgehellt – Grün bleibt Grün.
_DUNKEL = {"gut": "#81c784", "schlecht": "#ef9a9a"}

#: Verweise. Qts Standardblau (#0000ff) hat auf dunklem Grund ein
#: Kontrastverhältnis von 2,4 – ein Link, den man nur findet, wenn man
#: weiß, dass er da ist. Auf hellem Grund ist dasselbe Blau in Ordnung.
_LINK_HELL = "#0645ad"
_LINK_DUNKEL = "#6cb6ff"


def link() -> str:
    """Farbe für Verweise, passend zum Thema."""
    return _LINK_DUNKEL if dunkles_thema() else _LINK_HELL


def verweis(adresse: str, beschriftung: str) -> str:
    """Ein Verweis, der auf hellem wie dunklem Grund lesbar ist."""
    return f"<a href='{adresse}' style='color: {link()}'>{beschriftung}</a>"


def dunkles_thema() -> bool:
    """Ob die Oberfläche gerade dunkel eingestellt ist.

    Gefragt wird die Palette, nicht die Arbeitsumgebung: Das Thema kann
    zur Laufzeit wechseln, und es gibt mehr Arbeitsumgebungen, als man
    einzeln abfragen möchte.
    """
    anwendung = QApplication.instance()
    if anwendung is None:
        return False
    grund = anwendung.palette().color(QPalette.Window)
    # value() ist der Helligkeitsanteil in HSV, von 0 bis 255.
    return grund.value() < 128


def kante() -> str:
    """Die Farbe für Trennlinien zwischen den Bereichen.

    **Das dunkle Thema hat kein Farbproblem, es hat ein Kantenproblem.**
    Nachgemessen am 2026-08-27: Zwischen ``Window`` und ``Base`` – also
    zwischen Fensterhintergrund und Inhaltsbereich – liegt ein
    Kontrastverhältnis von **1,15**. Das liest kein Auge als Grenze, und
    zwar in keinem Thema. Im hellen fällt es nicht auf, weil Gewohnheit
    und Bildschirmrand helfen; auf einem 14-Zoll-Gerät im Dunkeln fehlt
    beides, und Baum, Trefferliste und Vorschau verschwimmen zu einer
    Fläche.

    Die Lösung ist deshalb nicht, eigene Farben zu setzen – das bräche
    Hochkontrast-Themen und träfe ausgerechnet die Anwender, für die
    solche Themen gemacht sind. Die Lösung ist, die Linie zu zeichnen,
    die es ohnehin geben sollte. ``Mid`` ist genau dafür da: eine Farbe
    zwischen Hintergrund und Rahmen, die jedes Thema mitliefert und
    jedes Hochkontrast-Thema kräftig setzt.
    """
    anwendung = QApplication.instance()
    if anwendung is None:
        return "#808080"
    return anwendung.palette().color(QPalette.Mid).name()


def bereichsrahmen() -> str:
    """Stylesheet, das die Bereiche voneinander abgrenzt.

    Bewusst knapp: nur der Rahmen, keine Hintergründe, keine Schrift.
    Alles andere bleibt beim Thema des Systems.
    """
    return (
        f"QTreeView, QTableView, QTextBrowser, QTextEdit "
        f"{{ border: 1px solid {kante()}; }}"
    )


def _waehlen(rolle: str) -> str:
    return (_DUNKEL if dunkles_thema() else _HELL)[rolle]


def gut() -> str:
    """Farbe für »hat geklappt«."""
    return _waehlen("gut")


def schlecht() -> str:
    """Farbe für »ist schiefgegangen«."""
    return _waehlen("schlecht")


def stil(gelungen: bool | None) -> str:
    """Fertiges Stylesheet für eine Zustandsanzeige.

    ``None`` heißt »noch nichts zu sagen« und gibt die Schrift wieder
    frei – dann gilt wieder die Farbe des Themas.
    """
    if gelungen is None:
        return ""
    return f"color: {gut() if gelungen else schlecht()}"
