"""Suchen innerhalb einer geöffneten Nachricht.

**Der Anlass ist eine Rückmeldung vom 2026-09-03.** Ein Anwender öffnete
eine Mail per Doppelklick und suchte darin ein Stichwort: »Leider wird
innerhalb des Fensters keine Suchfunktion angeboten, so dass die Suche
innerhalb einer einzelnen langen Mail nach einem Stichwort innerhalb des
Tools nicht möglich ist.«

Das trifft einen blinden Fleck. MailBurg sucht sehr gut *über* Mails –
Volltext, zwei Indizes, Anhänge bis in eingescannte PDF hinein. In der
einzelnen Mail hörte es auf. Wer einen Newsletter mit zweihundert Zeilen
öffnet, weil die Volltextsuche ihn gefunden hat, steht dann davor und
sucht mit den Augen.

**Bewusst keine zweite Suchsprache.** Hier wird schlicht nach Zeichen
gesucht, wie in jedem Textprogramm – kein ``von:``, kein ``jahr:``. Wer
Felder braucht, sucht im Hauptfenster; wer eine Stelle in einem Text
sucht, erwartet Strg+F und nichts weiter.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QWidget,
)


class Suchleiste(QWidget):
    """Eine Leiste zum Suchen in einem Textfeld – wie überall sonst auch."""

    geschlossen = Signal()

    def __init__(self, ziel, eltern=None) -> None:
        super().__init__(eltern)
        self.ziel = ziel

        self.feld = QLineEdit()
        self.feld.setPlaceholderText("In dieser Nachricht suchen …")
        self.feld.setClearButtonEnabled(True)
        self.feld.textChanged.connect(self._von_vorn)
        self.feld.returnPressed.connect(self.weiter)
        self.feld.setAccessibleName("Suchbegriff in dieser Nachricht")

        self.zurueck_knopf = QToolButton()
        self.zurueck_knopf.setText("▲")
        self.zurueck_knopf.setToolTip("Vorheriger Treffer (Umschalt+F3)")
        self.zurueck_knopf.clicked.connect(self.zurueck)

        self.weiter_knopf = QToolButton()
        self.weiter_knopf.setText("▼")
        self.weiter_knopf.setToolTip("Nächster Treffer (F3)")
        self.weiter_knopf.clicked.connect(self.weiter)

        self.gross_klein = QCheckBox("Groß-/Kleinschreibung")
        self.gross_klein.setToolTip(
            "Standardmäßig aus – wer eine Stelle sucht, weiß meist nicht "
            "mehr, wie sie geschrieben war."
        )
        self.gross_klein.stateChanged.connect(self._von_vorn)

        self.stand = QLabel()
        self.stand.setAccessibleName("Suchergebnis")

        zu = QToolButton()
        zu.setText("✕")
        zu.setToolTip("Suche schließen (Esc)")
        zu.clicked.connect(self.schliessen)

        aufbau = QHBoxLayout(self)
        aufbau.setContentsMargins(6, 3, 6, 3)
        aufbau.addWidget(QLabel("Suchen:"))
        aufbau.addWidget(self.feld, 1)
        aufbau.addWidget(self.zurueck_knopf)
        aufbau.addWidget(self.weiter_knopf)
        aufbau.addWidget(self.gross_klein)
        aufbau.addWidget(self.stand)
        aufbau.addWidget(zu)

        self.hide()

    # ----------------------------------------------------------- Öffnen

    def oeffnen(self) -> None:
        """Zeigt die Leiste und übernimmt eine markierte Stelle.

        Wer etwas markiert hat und dann Strg+F drückt, meint fast immer
        genau das – so hält es jedes andere Programm auch.
        """
        markiert = self.ziel.textCursor().selectedText().strip()
        if markiert and " " not in markiert:
            self.feld.setText(markiert)
        self.show()
        self.feld.setFocus()
        self.feld.selectAll()
        self._von_vorn()

    def schliessen(self) -> None:
        self.hide()
        self.stand.setText("")
        # Die Markierung aufheben, sonst bleibt der letzte Treffer
        # farbig stehen und sieht aus, als sei noch etwas ausgewählt.
        strich = self.ziel.textCursor()
        strich.clearSelection()
        self.ziel.setTextCursor(strich)
        self.ziel.setFocus()
        self.geschlossen.emit()

    # ----------------------------------------------------------- Suchen

    @property
    def _flaggen(self) -> QTextDocument.FindFlag:
        if self.gross_klein.isChecked():
            return QTextDocument.FindCaseSensitively
        return QTextDocument.FindFlag(0)

    def _von_vorn(self) -> None:
        """Sucht ab dem Anfang – für jeden neuen Buchstaben.

        Ohne das liefe die Suche vom letzten Treffer aus weiter, und wer
        einen Buchstaben löscht, landete unversehens weit hinten im Text.
        """
        strich = self.ziel.textCursor()
        strich.setPosition(0)
        self.ziel.setTextCursor(strich)
        self.weiter(vom_anfang=True)

    def weiter(self, vom_anfang: bool = False) -> bool:
        return self._suchen(self._flaggen, vom_anfang)

    def zurueck(self) -> bool:
        return self._suchen(self._flaggen | QTextDocument.FindBackward, False)

    def _suchen(self, flaggen, vom_anfang: bool) -> bool:
        was = self.feld.text()
        if not was:
            self.stand.setText("")
            return False

        gefunden = self.ziel.find(was, flaggen)
        if not gefunden and not vom_anfang:
            # **Am Ende von vorn.** Sonst hört die Suche beim letzten
            # Treffer auf, ohne zu sagen, dass es weiter oben noch
            # welche gibt.
            strich = self.ziel.textCursor()
            strich.movePosition(
                QTextCursor.End
                if flaggen & QTextDocument.FindBackward
                else QTextCursor.Start
            )
            self.ziel.setTextCursor(strich)
            gefunden = self.ziel.find(was, flaggen)

        self._stand_setzen(was, gefunden)
        return gefunden

    def _stand_setzen(self, was: str, gefunden: bool) -> None:
        if not gefunden:
            self.stand.setText("nicht gefunden")
            return
        anzahl = self._zaehlen(was)
        self.stand.setText(
            f"{anzahl} Treffer" if anzahl != 1 else "1 Treffer"
        )

    def _zaehlen(self, was: str) -> int:
        """Zählt die Vorkommen im ganzen Text.

        Über den reinen Text, nicht über wiederholtes ``find`` – das
        würde den Cursor bewegen und die gerade gefundene Stelle wieder
        verlieren.
        """
        text = self.ziel.toPlainText()
        if not self.gross_klein.isChecked():
            text, was = text.lower(), was.lower()
        return text.count(was)

    # ------------------------------------------------------------ Tasten

    def keyPressEvent(self, ereignis) -> None:
        # Esc schließt die Leiste, nicht das Fenster. Erst wenn sie zu
        # ist, darf Esc das Fenster schließen – sonst verliert man mit
        # einem Tastendruck die ganze Nachricht, obwohl man nur die
        # Suche loswerden wollte.
        if ereignis.key() == Qt.Key_Escape:
            self.schliessen()
            ereignis.accept()
            return
        super().keyPressEvent(ereignis)
