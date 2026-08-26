"""Den regelmäßigen Abruf einstellen – am Ende der Einrichtung und später.

Zwei Fragen beantwortet diese Ansicht, und beide stellen sich Anwender
sofort: *Muss dafür etwas laufen?* und *Wie oft?* Die erste beantwortet
der Text, die zweite das Auswahlfeld.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from mailburg.core import zeitplan
from mailburg.ui import farben

#: Die angebotenen Abstände. Bewusst wenige: Wer zwischen siebzehn
#: Möglichkeiten wählen soll, wählt gar nicht.
TAKTE: list[tuple[str, int]] = [
    ("alle 15 Minuten", 15),
    ("alle 30 Minuten", 30),
    ("stündlich", 60),
    ("alle 4 Stunden", 240),
    ("einmal am Tag", 1440),
]


class Zeitplanwahl(QWidget):
    """Ankreuzfeld und Abstand – zum Einbauen in Seiten und Dialoge."""

    def __init__(self, eltern=None, archiv=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        stand = zeitplan.zustand()

        self.an = QCheckBox("Neue Post regelmäßig im Hintergrund holen")
        self.an.setChecked(stand.laeuft or stand.moeglich)
        self.an.toggled.connect(self._umschalten)

        self.takt = QComboBox()
        for beschriftung, minuten in TAKTE:
            self.takt.addItem(beschriftung, minuten)
        self.takt.setCurrentIndex(
            max(0, [m for _, m in TAKTE].index(stand.takt))
            if stand.takt in [m for _, m in TAKTE]
            else 1
        )
        self.takt.setAccessibleName("Abstand zwischen den Abrufen")

        reihe = QHBoxLayout()
        reihe.addSpacing(24)
        reihe.addWidget(QLabel("Abstand:"))
        reihe.addWidget(self.takt)
        reihe.addStretch()

        self.hinweis = QLabel()
        self.hinweis.setWordWrap(True)
        self.hinweis.setTextFormat(Qt.RichText)
        self.hinweis.setText(
            "<p style='margin-left:24px'>Dafür muss MailBurg <b>nicht</b> "
            "geöffnet bleiben und auch nicht in den Autostart – geholt wird "
            "im Hintergrund, ganz ohne Fenster.</p>"
            "<p style='margin-left:24px'>Nötig ist nur, dass Sie angemeldet "
            "sind: Die Passwörter liegen im Schlüsselbund, und der öffnet "
            "sich erst mit Ihrer Anmeldung. War der Rechner aus, wird der "
            "versäumte Abruf beim nächsten Anmelden nachgeholt.</p>"
        )

        aufbau = QVBoxLayout(self)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.addWidget(self.an)
        aufbau.addLayout(reihe)
        aufbau.addWidget(self.hinweis)

        if not stand.moeglich:
            self.an.setChecked(False)
            self.an.setEnabled(False)
            self.hinweis.setText(f"<p style='margin-left:24px'>{stand.grund}</p>")
        self._umschalten(self.an.isChecked())

    def _umschalten(self, an: bool) -> None:
        self.takt.setEnabled(an)

    def anwenden(self) -> tuple[bool, str]:
        """Richtet ein oder schaltet ab – je nach Häkchen."""
        if not self.an.isEnabled():
            return True, ""
        if not self.an.isChecked():
            return zeitplan.abschalten()
        archiv = self.archiv
        if archiv is None:
            from mailburg.ui.app import zuletzt_gemerkt

            archiv = zuletzt_gemerkt()
        if archiv is None:
            return False, "Es ist kein Archiv eingerichtet."
        return zeitplan.einrichten(archiv, self.takt.currentData())


class Zeitplandialog(QDialog):
    """Dieselbe Wahl, später aus dem Hauptfenster heraus."""

    def __init__(self, eltern=None, archiv=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Abruf im Hintergrund")
        self.setMinimumWidth(560)

        self.wahl = Zeitplanwahl(archiv=archiv)
        self.meldung = QLabel()
        self.meldung.setWordWrap(True)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        knoepfe.button(QDialogButtonBox.Save).setText("Übernehmen")
        knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self._übernehmen)
        knoepfe.rejected.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(self.wahl)
        aufbau.addWidget(self.meldung)
        aufbau.addWidget(knoepfe)

    def _übernehmen(self) -> None:
        geklappt, text = self.wahl.anwenden()
        if geklappt:
            self.accept()
            return
        # Nicht schließen, wenn es nicht geklappt hat: Sonst geht der
        # Anwender davon aus, es sei eingerichtet.
        self.meldung.setStyleSheet(farben.stil(False))
        self.meldung.setText(text)
