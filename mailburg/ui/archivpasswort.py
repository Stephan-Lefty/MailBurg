"""Die Fenster rund um das Passwort eines verschlüsselten Archivs.

Drei Momente, und jeder hat seine eigene Gefahr:

**Beim Öffnen** ist die Gefahr Ungeduld. Wer sein Archiv aufmachen will,
will nicht lesen, sondern hinein – hier steht deshalb so wenig wie
möglich.

**Beim Anlegen** ist die Gefahr das Gegenteil: Wer hier zu schnell
klickt, verschlüsselt zwanzig Jahre Post mit einem Passwort, das er sich
nicht gemerkt hat. Deshalb zweimal eingeben, und deshalb steht dort, was
auf dem Spiel steht.

**Beim Notschlüssel** ist die Gefahr, ihn wegzuklicken. Er ist genau
einmal zu sehen. Das Fenster lässt sich deshalb erst schließen, wenn
jemand ausdrücklich bestätigt, dass er ihn hat – nicht als Schikane,
sondern weil ein weggeklicktes Fenster hier ein verlorenes Archiv
bedeuten kann.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from mailburg.core import krypto


class PasswortFragen(QDialog):
    """Ein Feld, in das Passwort oder Notschlüssel darf."""

    def __init__(self, parent=None, *, archivname: str = "", nochmal: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Archiv öffnen")
        self.setMinimumWidth(440)

        aufbau = QVBoxLayout(self)

        titel = QLabel(
            f"<b>Das Archiv »{archivname}« ist verschlüsselt.</b>"
            if archivname
            else "<b>Dieses Archiv ist verschlüsselt.</b>"
        )
        titel.setTextFormat(Qt.RichText)
        aufbau.addWidget(titel)

        if nochmal:
            hinweis = QLabel(
                "Das war nicht das richtige Passwort. Der Notschlüssel "
                "geht hier ebenso – 32 Zeichen in acht Gruppen, "
                "Bindestriche und Groß- oder Kleinschreibung sind egal."
            )
        else:
            hinweis = QLabel(
                "Geben Sie das Passwort ein. Falls Sie es nicht mehr "
                "wissen, geht auch der Notschlüssel von damals."
            )
        hinweis.setWordWrap(True)
        aufbau.addWidget(hinweis)

        self.feld = QLineEdit()
        self.feld.setEchoMode(QLineEdit.Password)
        self.feld.setPlaceholderText("Passwort oder Notschlüssel")
        aufbau.addWidget(self.feld)

        self.zeigen = QCheckBox("Eingabe anzeigen")
        # Ein Notschlüssel wird von einem Zettel abgetippt; ihn dabei
        # nicht sehen zu können, ist die sichere Art, sich zu vertippen.
        self.zeigen.toggled.connect(self._sichtbarkeit)
        aufbau.addWidget(self.zeigen)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        aufbau.addWidget(knoepfe)

        self.feld.setFocus()

    def _sichtbarkeit(self, an: bool) -> None:
        self.feld.setEchoMode(QLineEdit.Normal if an else QLineEdit.Password)

    @property
    def geheimnis(self) -> str:
        return self.feld.text()


class NeuesPasswortFragen(QDialog):
    """Zweimal eingeben – hier gibt es keine Korrektur hinterher."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Archiv verschlüsseln")
        # **Breit genug für seine drei Absätze.** Bei 500 px brach der
        # Hinweis zum Suchindex unten ab - ausgerechnet der Satz, der
        # sagt, was die Verschlüsselung *nicht* schützt. Am 2026-08-31
        # mit werkzeuge/lesbarkeit.py nachgemessen.
        self.setMinimumWidth(600)

        aufbau = QVBoxLayout(self)

        titel = QLabel("<b>Ein Passwort für dieses Archiv</b>")
        titel.setTextFormat(Qt.RichText)
        aufbau.addWidget(titel)

        warnung = QLabel(
            "<p>Ohne dieses Passwort kommt niemand mehr an die Mails – "
            "auch nicht der Hersteller. Es gibt keine Hintertür; das "
            "ist der Sinn der Sache.</p>"
            "<p>Gleich danach bekommen Sie einen <b>Notschlüssel</b>, "
            "der das Archiv ebenfalls öffnet. Drucken Sie ihn aus.</p>"
            f"<p><b>{krypto.hinweis_neu()}</b></p>"
        )
        warnung.setTextFormat(Qt.RichText)
        warnung.setWordWrap(True)
        aufbau.addWidget(warnung)

        self.erstes = QLineEdit()
        self.erstes.setEchoMode(QLineEdit.Password)
        self.erstes.setPlaceholderText("Passwort")
        aufbau.addWidget(self.erstes)

        self.zweites = QLineEdit()
        self.zweites.setEchoMode(QLineEdit.Password)
        self.zweites.setPlaceholderText("Noch einmal zur Sicherheit")
        aufbau.addWidget(self.zweites)

        self.meldung = QLabel("")
        self.meldung.setWordWrap(True)
        aufbau.addWidget(self.meldung)

        hinweis = QLabel(krypto.hinweis_suchindex())
        hinweis.setWordWrap(True)
        hinweis.setStyleSheet("color: palette(mid);")
        aufbau.addWidget(hinweis)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        knoepfe.accepted.connect(self._pruefen)
        knoepfe.rejected.connect(self.reject)
        aufbau.addWidget(knoepfe)

        self.erstes.setFocus()
        # Die Höhe aus dem Inhalt, nicht aus einer Zahl: Der Text hängt
        # an der eingestellten Schriftgröße, und die kennt nur Qt.
        self.adjustSize()

    def _pruefen(self) -> None:
        if not self.erstes.text():
            self.meldung.setText("Ohne Passwort keine Verschlüsselung.")
            return
        if self.erstes.text() != self.zweites.text():
            self.meldung.setText(
                "Die beiden stimmen nicht überein. Bitte noch einmal – "
                "ein Tippfehler wäre hier nicht mehr zu beheben."
            )
            self.zweites.clear()
            self.zweites.setFocus()
            return
        self.accept()

    @property
    def passwort(self) -> str:
        return self.erstes.text()


class NotschluesselZeigen(QDialog):
    """Der einzige Moment, in dem der Notschlüssel zu sehen ist."""

    def __init__(self, wert: str, parent=None):
        super().__init__(parent)
        self.wert = wert
        self.setWindowTitle("Ihr Notschlüssel")
        self.setMinimumWidth(520)

        aufbau = QVBoxLayout(self)

        titel = QLabel("<b>Bewahren Sie diesen Schlüssel auf.</b>")
        titel.setTextFormat(Qt.RichText)
        aufbau.addWidget(titel)

        anzeige = QLabel(wert)
        anzeige.setTextInteractionFlags(Qt.TextSelectableByMouse)
        anzeige.setAlignment(Qt.AlignCenter)
        # Feste Schrittweite: Wer das abtippt, muss O von 0 unterscheiden
        # können. Genau deshalb kommen beide im Alphabet gar nicht vor -
        # aber lesbar soll es trotzdem sein.
        anzeige.setStyleSheet(
            "font-family: monospace; font-size: 14pt; padding: 12px;"
            "border: 1px solid palette(mid);"
        )
        aufbau.addWidget(anzeige)

        text = QLabel(
            "<p>Er öffnet das Archiv anstelle des Passworts. Legen Sie "
            "ihn dorthin, wo Sie auch wichtige Papiere aufbewahren.</p>"
            "<p><b>Er steht hier zum einzigen Mal.</b> MailBurg hat ihn "
            "nicht gespeichert und kann ihn nicht noch einmal ausgeben – "
            "läge er im Archiv, wäre er kein Schutz.</p>"
        )
        text.setTextFormat(Qt.RichText)
        text.setWordWrap(True)
        aufbau.addWidget(text)

        kopieren = QPushButton("In die Zwischenablage")
        kopieren.clicked.connect(self._kopieren)
        aufbau.addWidget(kopieren)

        speichern = QPushButton("Als Textdatei speichern …")
        speichern.clicked.connect(self._speichern)
        aufbau.addWidget(speichern)

        self.bestaetigt = QCheckBox("Ich habe den Notschlüssel gesichert")
        self.bestaetigt.toggled.connect(self._freigeben)
        aufbau.addWidget(self.bestaetigt)

        self.knoepfe = QDialogButtonBox(QDialogButtonBox.Ok, parent=self)
        self.knoepfe.accepted.connect(self.accept)
        # Kein Abbrechen: Das Archiv ist zu diesem Zeitpunkt schon
        # angelegt und verschlüsselt. Wegklicken änderte daran nichts,
        # nur wäre der Schlüssel dann weg.
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
        aufbau.addWidget(self.knoepfe)

    def _freigeben(self, an: bool) -> None:
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(an)

    def _kopieren(self) -> None:
        QApplication.clipboard().setText(self.wert)

    def _speichern(self) -> None:
        ziel, _ = QFileDialog.getSaveFileName(
            self, "Notschlüssel speichern", "mailburg-notschluessel.txt",
            "Textdateien (*.txt)",
        )
        if not ziel:
            return
        try:
            with open(ziel, "w", encoding="utf-8") as datei:
                datei.write(
                    "MailBurg – Notschlüssel für Ihr verschlüsseltes Archiv\n"
                    "=====================================================\n\n"
                    f"    {self.wert}\n\n"
                    "Er öffnet das Archiv anstelle des Passworts.\n\n"
                    "Diese Datei gehört nicht in dasselbe Verzeichnis wie\n"
                    "das Archiv und nicht auf dieselbe Platte. Ein Schlüssel,\n"
                    "der neben dem Schloss liegt, ist keiner.\n"
                )
        except OSError as fehler:
            QMessageBox.warning(self, "Nicht gespeichert", str(fehler))
            return
        self.bestaetigt.setChecked(True)

    def closeEvent(self, ereignis) -> None:
        """Das Fenster über das X zu schließen, wäre dasselbe wie Wegklicken."""
        if not self.bestaetigt.isChecked():
            ereignis.ignore()
            QMessageBox.information(
                self,
                "Erst sichern",
                "Der Notschlüssel ist danach nicht mehr abrufbar. "
                "Kopieren oder speichern Sie ihn und setzen Sie dann das "
                "Häkchen.",
            )
            return
        super().closeEvent(ereignis)
