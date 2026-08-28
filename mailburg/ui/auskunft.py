"""Auskunft nach Art. 15 DSGVO – das Fenster dazu.

Wer fragt, was über ihn gespeichert ist, hat Anspruch auf eine Kopie.
Dieses Fenster sucht zusammen und packt auf Wunsch ein ZIP.

**Es gibt nichts heraus.** Das tut ein Mensch, und vorher muss er zwei
Dinge prüfen, die kein Programm entscheiden kann: ob in denselben
Nachrichten Daten Dritter stehen, die nach Art. 15 Abs. 4 DSGVO nicht
mitgehen dürfen, und ob die Person unter weiteren Adressen schreibt.
Beides steht im Fenster und noch einmal im Begleitblatt.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from mailburg.core import auskunft


class Auskunftsdialog(QDialog):
    """Fragt nach einer Adresse und stellt zusammen, was dazu vorliegt."""

    def __init__(self, archiv, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Auskunft nach DSGVO")
        self.archiv = archiv
        self.befund = None

        aufbau = QVBoxLayout(self)

        einleitung = QLabel(
            "Fragt jemand, was über ihn gespeichert ist, hat er nach "
            "<b>Artikel 15 DSGVO</b> Anspruch auf eine Kopie. MailBurg "
            "sucht alle Nachrichten, in denen die Person vorkommt, und "
            "packt sie auf Wunsch in eine Datei."
        )
        einleitung.setWordWrap(True)
        aufbau.addWidget(einleitung)

        aufbau.addSpacing(8)
        aufbau.addWidget(QLabel("<b>Mailadresse der betroffenen Person</b>"))
        self.adresse = QLineEdit()
        self.adresse.setPlaceholderText("post@example.org")
        self.adresse.returnPressed.connect(self._suchen)
        aufbau.addWidget(self.adresse)

        self.im_text = QCheckBox(
            "Auch Nachrichten, in denen die Adresse nur erwähnt wird"
        )
        self.im_text.setToolTip(
            "Trifft oft Weiterleitungen und Verteiler, in denen die Person "
            "selbst nicht Beteiligte ist. Und jede zusätzliche Nachricht "
            "ist eine, in der womöglich Daten Dritter stehen."
        )
        aufbau.addWidget(self.im_text)

        self.suchknopf = QPushButton("Zusammenstellen")
        self.suchknopf.clicked.connect(self._suchen)
        aufbau.addWidget(self.suchknopf)

        aufbau.addSpacing(8)
        self.ergebnis = QLabel("")
        self.ergebnis.setWordWrap(True)
        self.ergebnis.setTextFormat(Qt.RichText)
        aufbau.addWidget(self.ergebnis)

        self.vorbehalt = QLabel(
            "<b>Vor der Herausgabe zu prüfen.</b> In denselben Nachrichten "
            "stehen oft Daten Dritter – Adressen im Verteiler, Namen im "
            "Text, Unterschriften in Anhängen. Nach Artikel 15 Absatz 4 "
            "darf die Kopie deren Rechte nicht beeinträchtigen. Was davon "
            "zu schwärzen ist, kann kein Programm entscheiden.<br><br>"
            "Und: Gesucht wird nach genau dieser Adresse. Wer unter "
            "mehreren schreibt, taucht nur unter der gesuchten auf."
        )
        self.vorbehalt.setWordWrap(True)
        self.vorbehalt.setVisible(False)
        aufbau.addWidget(self.vorbehalt)

        self.knoepfe = QDialogButtonBox(self)
        self.packen = QPushButton("Als Datei speichern …")
        self.packen.setEnabled(False)
        self.packen.clicked.connect(self._packen)
        self.knoepfe.addButton(self.packen, QDialogButtonBox.AcceptRole)
        self.knoepfe.addButton("Schließen", QDialogButtonBox.RejectRole)
        self.knoepfe.rejected.connect(self.reject)
        aufbau.addWidget(self.knoepfe)

    def _suchen(self) -> None:
        adresse = self.adresse.text().strip()
        if not adresse:
            return

        self.setCursor(Qt.WaitCursor)
        try:
            self.befund = auskunft.zusammenstellen(
                self.archiv, adresse, im_text=self.im_text.isChecked()
            )
        except Exception as exc:  # noqa: BLE001
            self.unsetCursor()
            QMessageBox.warning(self, "Suche gescheitert", str(exc))
            return
        finally:
            self.unsetCursor()

        if not self.befund.anzahl:
            self.ergebnis.setText(
                f"<b>Nichts gefunden</b> zu {adresse}.<br>"
                f"Schreibt die Person unter einer anderen Adresse?"
            )
            self.vorbehalt.setVisible(False)
            self.packen.setEnabled(False)
            return

        von = (self.befund.treffer[0].date or "")[:10]
        bis = (self.befund.treffer[-1].date or "")[:10]
        zeilen = [
            f"<b>{self.befund.anzahl} Nachrichten</b> zu {adresse}",
            f"als Absender: {self.befund.als_absender} · "
            f"als Empfänger: {self.befund.als_empfaenger}"
            + (f" · im Text: {self.befund.im_text}" if self.befund.im_text else ""),
            f"Zeitraum: {von} bis {bis}",
        ]
        self.ergebnis.setText("<br>".join(zeilen))
        self.vorbehalt.setVisible(True)
        self.packen.setEnabled(True)

    def _packen(self) -> None:
        if self.befund is None or not self.befund.anzahl:
            return

        # Ein Name, der sagt, was drin ist - ohne die Adresse selbst im
        # Dateinamen: Solche Dateien liegen später in Ordnern, in die
        # auch andere sehen.
        vorschlag = str(
            Path.home() / f"Auskunft-{self.befund.adresse.split('@')[0]}.zip"
        )
        ziel, _ = QFileDialog.getSaveFileName(
            self, "Auskunft speichern", vorschlag, "ZIP-Datei (*.zip)"
        )
        if not ziel:
            return

        self.setCursor(Qt.WaitCursor)
        try:
            auskunft.packen(self.archiv, self.befund, Path(ziel))
        except Exception as exc:  # noqa: BLE001
            self.unsetCursor()
            QMessageBox.warning(self, "Speichern gescheitert", str(exc))
            return
        finally:
            self.unsetCursor()

        QMessageBox.information(
            self,
            "Auskunft gespeichert",
            f"{self.befund.anzahl} Nachrichten liegen in\n{self.befund.ziel}\n\n"
            f"Im Journal des Archivs vermerkt – Artikel 5 Absatz 2 DSGVO "
            f"verlangt, dass Sie die Einhaltung nachweisen können.\n\n"
            f"Das Begleitblatt im Paket nennt, was vor der Herausgabe noch "
            f"zu prüfen ist.",
        )
        self.accept()
