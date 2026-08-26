"""Der Dialog, mit dem eine Mail wieder in ein Postfach kommt.

Eine einzige Frage ist zu beantworten: in welches Postfach. Der Ordner
ist immer der Posteingang – dort schaut man hin, dort erwartet man neue
Post, und von dort verschiebt man sie im Mailprogramm mit einem
Handgriff dahin, wo man sie haben will. Eine Ordnerliste zu holen hieße
dagegen: warten, wählen, sich vertippen.

Wählbar ist das Postfach frei. Wer nach zehn Jahren eine Rechnung
zurückholt, hat das damalige Konto vielleicht gar nicht mehr.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from mailburg.core import accounts
from mailburg.core.accounts import Kontenliste
from mailburg.ui.arbeit import Auftrag, Läufer

#: Dorthin geht die Nachricht zurück. IMAP schreibt diesen Namen vor –
#: er ist auf jedem Server derselbe, auch auf deutschsprachigen, wo der
#: Anwender ihn als »Posteingang« sieht.
POSTEINGANG = "INBOX"


class Zurueckgeben(Auftrag):
    """Legt die Mail ins Postfach."""

    def __init__(self, konto, passwort: str, rohdaten: bytes,
                 ungelesen: bool = True) -> None:
        super().__init__()
        self.konto = konto
        self.passwort = passwort
        self.rohdaten = rohdaten
        self.ungelesen = ungelesen

    def ausfuehren(self) -> str:
        from mailburg.core import rueckgabe

        rueckgabe.ins_postfach(
            self.konto, self.passwort, POSTEINGANG, self.rohdaten,
            ungelesen=self.ungelesen,
        )
        return self.konto.benutzer or self.konto.name


class Zurueckdialog(QDialog):
    """Postfach wählen, dann wiederherstellen."""

    def __init__(self, rohdaten: bytes, betreff: str, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Nachricht wiederherstellen")
        self.setMinimumWidth(560)
        self.rohdaten = rohdaten
        self._laeufer = None

        erklaerung = QLabel(
            "<p>Die Nachricht kommt in den <b>Posteingang</b> des gewählten "
            "Postfachs – vollständig, mit allen Anhängen und mit ihrem "
            "ursprünglichen Datum. Damit steht sie im Mailprogramm an "
            "ihrem Platz in der Zeit und nicht ganz oben.</p>"
            "<p><b>Es muss nicht das Postfach sein, aus dem sie stammt.</b> "
            "Post überlebt Anbieter und Adressen; wählen Sie einfach das, "
            "in dem Sie sie jetzt haben wollen.</p>"
        )
        erklaerung.setWordWrap(True)
        erklaerung.setTextFormat(Qt.RichText)

        self.konten = QComboBox()
        for konto in Kontenliste().konten:
            if konto.aktiv:
                self.konten.addItem(konto.benutzer or konto.name, konto)

        # Voreingestellt an: Die Nachricht kommt mit ihrem alten Datum
        # zurück und steht damit mitten in der Post von damals. Ungelesen
        # erscheint sie hervorgehoben und im Zähler des Ordners - sonst
        # sucht man sie hinterher.
        self.ungelesen = QCheckBox(
            "Als ungelesen markieren, damit sie im Mailprogramm auffällt"
        )
        self.ungelesen.setChecked(True)

        self.stand = QLabel("")
        self.stand.setWordWrap(True)

        self.knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.knoepfe.button(QDialogButtonBox.Ok).setText("Wiederherstellen")
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        self.knoepfe.accepted.connect(self._zuruecklegen)
        self.knoepfe.rejected.connect(self.reject)

        felder = QFormLayout()
        felder.addRow("Nachricht:", QLabel(betreff or "(ohne Betreff)"))
        felder.addRow("Postfach:", self.konten)
        felder.addRow("Ziel:", QLabel("Posteingang"))
        felder.addRow("", self.ungelesen)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(erklaerung)
        aufbau.addLayout(felder)
        aufbau.addWidget(self.stand)
        aufbau.addWidget(self.knoepfe)

        if self.konten.count() == 0:
            self.stand.setText(
                "Es ist kein Postfach eingerichtet. Über »Post → Postfächer "
                "verwalten« lässt sich eines hinzufügen – oder speichern Sie "
                "die Nachricht als Datei."
            )
            self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)

    # -------------------------------------------------------- Zurücklegen

    def _zuruecklegen(self) -> None:
        konto = self.konten.currentData()
        if konto is None:
            return
        passwort = accounts.passwort_holen(konto)
        if not passwort:
            QMessageBox.warning(
                self, "Kein Passwort",
                "Für dieses Postfach liegt kein Passwort im Schlüsselbund.",
            )
            return

        self.knoepfe.setEnabled(False)
        self.stand.setText("Lege die Nachricht ab …")
        auftrag = Zurueckgeben(
            konto, passwort, self.rohdaten, self.ungelesen.isChecked()
        )
        auftrag.fertig.connect(self._geschafft)
        auftrag.gescheitert.connect(self._misslungen)
        self._laeufer = Läufer(auftrag)
        self._laeufer.starten()

    def _geschafft(self, postfach: str) -> None:
        QMessageBox.information(
            self, "Wiederhergestellt",
            f"Die Nachricht liegt jetzt im Posteingang von »{postfach}«.\n\n"
            f"Im Mailprogramm erscheint sie, sobald der Posteingang das "
            f"nächste Mal abgeglichen wird.",
        )
        self.accept()

    def _misslungen(self, text: str) -> None:
        self.knoepfe.setEnabled(True)
        self.stand.setText("")
        QMessageBox.warning(self, "Nicht wiederhergestellt", text)
