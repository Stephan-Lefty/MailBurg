"""Ein umbrechender Absatz, der die Höhe bekommt, die er braucht.

Qt kann das von Haus aus nicht zuverlässig. Ein ``QLabel`` mit
``setWordWrap(True)`` braucht umso mehr Höhe, je schmaler es ist – die
Höhe hängt an der Breite. Genau diesen Zusammenhang meldet es dem
Layout aber nicht: ``minimumSizeHint()`` gibt eine Höhe zurück, die für
irgendeine angenommene Breite gilt, nicht für die tatsächliche.

Solange nichts anderes im Fenster steht, fällt das nicht auf. Sobald
aber ein Fortschrittsbalken dazukommt und Platz verlangt, nimmt das
Layout ihn sich beim Absatz darüber – und dort steht dann eine Zeile
weniger, als geschrieben wurde. Der Text ist nicht abgeschnitten mit
Auslassungspunkten, er ist einfach weg. Wer das Fenster zum ersten Mal
sieht, hält den verstümmelten Rest für den ganzen Text.

``QLayout.SetMinimumSize`` am Layout allein reicht nicht: Es zwingt das
Fenster auf die gemeldete Mindestgröße, und die ist ja gerade die
falsche Zahl.

Deshalb dieses Etikett. Es rechnet die Höhe für die Breite aus, die es
gerade tatsächlich hat, und meldet sich beim Layout neu, sobald sich
diese Breite ändert.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


class Fliesstext(QLabel):
    """Ein Absatz, der lieber wächst als Zeilen zu verschlucken."""

    def __init__(self, text: str = "", eltern=None) -> None:
        super().__init__(text, eltern)
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        # Auswählbar: In diesen Absätzen stehen Pfade und Zahlen, die
        # man gelegentlich kopieren möchte.
        self.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        regel = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        regel.setHeightForWidth(True)
        self.setSizePolicy(regel)

    def minimumSizeHint(self) -> QSize:
        """So hoch, wie der Text bei der aktuellen Breite wirklich ist.

        Vor dem ersten Anzeigen gibt es noch keine Breite. Dann gilt die
        Mindestbreite des Fensters, ersatzweise ein vernünftiger Wert –
        besser eine Zeile zu viel als eine zu wenig.
        """
        breite = self.width()
        if breite <= 20:
            breite = self.minimumWidth() or 400
        return QSize(0, self.heightForWidth(breite))

    def sizeHint(self) -> QSize:
        return self.minimumSizeHint()

    def resizeEvent(self, ereignis) -> None:
        """Wird das Etikett schmaler, braucht es mehr Höhe.

        Ohne diese Meldung rechnet das Layout weiter mit der Höhe von
        vorhin – und beim Schmalerziehen des Fensters verschwindet die
        letzte Zeile.
        """
        super().resizeEvent(ereignis)
        self.updateGeometry()
