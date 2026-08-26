"""Eine einzelne Nachricht in einem eigenen Fenster.

Die Vorschau unten im Hauptfenster ist zum Überfliegen da – man sucht,
klickt sich durch die Treffer und liest jeweils die ersten Zeilen. Für
eine Mail, die man wirklich lesen will, ist sie zu klein, und größer
ziehen geht nur auf Kosten der Trefferliste.

Deshalb der Doppelklick: ein eigenes Fenster, so groß wie nötig, das
sich nebenherlegen lässt. Mehrere davon gleichzeitig sind ausdrücklich
erlaubt – wer zwei Rechnungen vergleicht, braucht beide nebeneinander.
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow

from mailburg.ui.vorschau import Mailvorschau

#: Alle offenen Lesefenster. Aus demselben Grund wie die Läuferliste in
#: ``ui/arbeit.py``: Ein Fenster, auf das niemand mehr zeigt, räumt
#: Python weg – und es verschwindet vor den Augen des Anwenders.
_OFFEN: set = set()


class Lesefenster(QMainWindow):
    """Eine Nachricht, groß und für sich."""

    def __init__(self, treffer, archiv, eltern=None) -> None:
        super().__init__(eltern)
        self.treffer = treffer
        self.setWindowTitle(treffer.subject or "(ohne Betreff)")
        self.resize(900, 700)

        self.vorschau = Mailvorschau()
        self.vorschau.zeigen(treffer, archiv)
        self.setCentralWidget(self.vorschau)

        # Fenster schließt man mit Strg+W, und Esc erwartet man bei
        # etwas, das man nur angesehen hat.
        for tasten in (QKeySequence.Close, QKeySequence("Esc")):
            schliessen = QAction(self)
            schliessen.setShortcut(tasten)
            schliessen.triggered.connect(self.close)
            self.addAction(schliessen)

    def closeEvent(self, ereignis) -> None:
        _OFFEN.discard(self)
        super().closeEvent(ereignis)


def oeffnen(treffer, archiv, eltern=None) -> Lesefenster:
    """Öffnet eine Nachricht in einem eigenen Fenster."""
    fenster = Lesefenster(treffer, archiv, eltern)
    _OFFEN.add(fenster)
    fenster.show()
    fenster.raise_()
    fenster.activateWindow()
    return fenster
