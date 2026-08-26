"""Den regelmäßigen Abruf einstellen – am Ende der Einrichtung und später.

Zwei Fragen beantwortet diese Ansicht, und beide stellen sich Anwender
sofort: *Muss dafür etwas laufen?* und *Wie oft?* Die erste beantwortet
der Text, die zweite das Auswahlfeld.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
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


class Sicherungswahl(QWidget):
    """Wie oft das Archiv weggepackt wird – und wohin."""

    def __init__(self, eltern=None, archiv=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        stand = zeitplan.sicherung_zustand()

        self.an = QCheckBox("Das Archiv regelmäßig in eine Datei sichern")
        self.an.setChecked(stand.laeuft)
        self.an.toggled.connect(self._umschalten)

        self.takt = QComboBox()
        for bezeichnung in zeitplan.TAKTE_SICHERUNG:
            self.takt.addItem(bezeichnung, bezeichnung)
        self.takt.setAccessibleName("Wie oft gesichert wird")

        self.ziel = QLineEdit(stand.archiv or "")
        self.ziel.setPlaceholderText(
            "Ordner für die Sicherungen – am besten in der Cloud"
        )
        self.suchen = QPushButton("Auswählen …")
        self.suchen.clicked.connect(self._ordner_waehlen)

        self.behalten = QSpinBox()
        self.behalten.setRange(0, 99)
        self.behalten.setValue(0)
        self.behalten.setSpecialValueText("immer dieselbe Datei ersetzen")
        self.behalten.setSuffix(" Stände")
        self.behalten.setToolTip(
            "»Immer dieselbe Datei ersetzen« hält den Platzbedarf "
            "gleich – bei Nextcloud sinnvoll, weil der Server die "
            "Versionen ohnehin führt. Andernfalls wird je Lauf eine "
            "Datei mit Datum angelegt und nur die eingestellte Zahl "
            "behalten; ohne Grenze läuft die Platte irgendwann voll, "
            "und dann scheitert ausgerechnet die Sicherung, auf die es "
            "ankäme."
        )

        reihe = QHBoxLayout()
        reihe.addSpacing(24)
        reihe.addWidget(QLabel("Wie oft:"))
        reihe.addWidget(self.takt)
        reihe.addWidget(QLabel("behalten:"))
        reihe.addWidget(self.behalten)
        reihe.addStretch()

        zielreihe = QHBoxLayout()
        zielreihe.addSpacing(24)
        zielreihe.addWidget(QLabel("Ordner:"))
        zielreihe.addWidget(self.ziel, 1)
        zielreihe.addWidget(self.suchen)

        hinweis = QLabel(
            "<p style='margin-left:24px'>Gepackt wird das ganze Archiv in "
            "<b>eine Datei</b> mit Datum im Namen. Viel kleiner wird sie "
            "nicht – Ihre Mails liegen schon komprimiert –, aber ein "
            "Cloud-Programm kommt mit einer Datei um ein Vielfaches "
            "schneller zurecht als mit zehntausend.</p>"
            "<p style='margin-left:24px'><b>Nicht auf dieselbe Platte wie "
            "das Archiv.</b> Eine Sicherung, die neben dem Original liegt, "
            "geht mit ihm zusammen verloren.</p>"
        )
        hinweis.setWordWrap(True)
        hinweis.setTextFormat(Qt.RichText)

        aufbau = QVBoxLayout(self)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.addWidget(self.an)
        aufbau.addLayout(reihe)
        aufbau.addLayout(zielreihe)
        aufbau.addWidget(hinweis)

        if not stand.moeglich:
            self.an.setChecked(False)
            self.an.setEnabled(False)
        self._umschalten(self.an.isChecked())

    def _umschalten(self, an: bool) -> None:
        for teil in (self.takt, self.behalten, self.ziel, self.suchen):
            teil.setEnabled(an)

    def _ordner_waehlen(self) -> None:
        gewaehlt = QFileDialog.getExistingDirectory(
            self, "Ordner für die Sicherungen", self.ziel.text() or str(Path.home())
        )
        if gewaehlt:
            self.ziel.setText(gewaehlt)

    def anwenden(self) -> tuple[bool, str]:
        if not self.an.isEnabled():
            return True, ""
        if not self.an.isChecked():
            return zeitplan.sicherung_abschalten()

        archiv = self.archiv
        if archiv is None:
            from mailburg.ui.app import zuletzt_gemerkt

            archiv = zuletzt_gemerkt()
        if archiv is None:
            return False, "Es ist kein Archiv eingerichtet."
        if not self.ziel.text().strip():
            return False, "Bitte einen Ordner für die Sicherungen wählen."
        return zeitplan.sicherung_einrichten(
            archiv, self.ziel.text().strip(),
            self.takt.currentData(), self.behalten.value(),
        )


class Zeitplandialog(QDialog):
    """Abruf und Sicherung – beides, was von selbst laufen soll."""

    def __init__(self, eltern=None, archiv=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Was von selbst laufen soll")
        self.setMinimumWidth(620)

        self.wahl = Zeitplanwahl(archiv=archiv)
        self.sicherung = Sicherungswahl(archiv=archiv)
        self.meldung = QLabel()
        self.meldung.setWordWrap(True)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        knoepfe.button(QDialogButtonBox.Save).setText("Übernehmen")
        knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self._übernehmen)
        knoepfe.rejected.connect(self.reject)

        trenner = QFrame()
        trenner.setFrameShape(QFrame.HLine)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(self.wahl)
        aufbau.addWidget(trenner)
        aufbau.addWidget(self.sicherung)
        aufbau.addWidget(self.meldung)
        aufbau.addWidget(knoepfe)
        aufbau.setSizeConstraint(QLayout.SetMinimumSize)

    def _übernehmen(self) -> None:
        geklappt, text = self.wahl.anwenden()
        if geklappt:
            geklappt, text = self.sicherung.anwenden()
        if geklappt:
            self.accept()
            return
        # Nicht schließen, wenn es nicht geklappt hat: Sonst geht der
        # Anwender davon aus, es sei eingerichtet.
        self.meldung.setStyleSheet(farben.stil(False))
        self.meldung.setText(text)
