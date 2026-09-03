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
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from mailburg.ui.suchleiste import Suchleiste
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

        # **Suchen in der Nachricht.** Ein Anwender hat es am 2026-09-03
        # vermisst: MailBurg sucht hervorragend *über* Mails und hörte in
        # der einzelnen auf. Wer einen langen Newsletter öffnet, weil die
        # Volltextsuche ihn gefunden hat, stand dann davor.
        self.suchleiste = Suchleiste(self.vorschau.text)

        mitte = QWidget()
        aufbau = QVBoxLayout(mitte)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.setSpacing(0)
        aufbau.addWidget(self.vorschau, 1)
        aufbau.addWidget(self.suchleiste)
        self.setCentralWidget(mitte)

        # **Nur QKeySequence.Find, nichts daneben.** Das *ist* Strg+F.
        # Ein zweites, von Hand gesetztes Kürzel derselben Tastenfolge
        # macht Qt mehrdeutig, und dann löst es keines von beiden aus –
        # derselbe Fehler wie am 2026-08-31 bei Strg++.
        suchen = QAction(self)
        suchen.setShortcut(QKeySequence.Find)
        suchen.triggered.connect(self.suchleiste.oeffnen)
        self.addAction(suchen)

        for tasten, richtung in (
            (QKeySequence.FindNext, self.suchleiste.weiter),
            (QKeySequence.FindPrevious, self.suchleiste.zurueck),
        ):
            schritt = QAction(self)
            schritt.setShortcut(tasten)
            schritt.triggered.connect(richtung)
            self.addAction(schritt)

        # Fenster schließt man mit Strg+W – das gilt immer, auch bei
        # offener Suchleiste.
        zu = QAction(self)
        zu.setShortcut(QKeySequence.Close)
        zu.triggered.connect(self.close)
        self.addAction(zu)

        # Esc erwartet man bei etwas, das man nur angesehen hat – aber
        # erst, wenn die Suchleiste zu ist.
        abbrechen = QAction(self)
        abbrechen.setShortcut(QKeySequence("Esc"))
        abbrechen.triggered.connect(self._esc)
        self.addAction(abbrechen)

    def _esc(self) -> None:
        """Esc schließt erst die Suchleiste, dann das Fenster.

        Andersherum verlöre man mit einem Tastendruck die ganze
        Nachricht, obwohl man nur die Suche loswerden wollte.
        """
        if self.suchleiste.isVisible():
            self.suchleiste.schliessen()
            return
        self.close()

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
