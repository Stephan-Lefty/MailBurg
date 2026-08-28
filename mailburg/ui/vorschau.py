"""Die Anzeige einer einzelnen Mail samt ihrer Anhänge.

**HTML wird nicht dargestellt, und das ist Absicht.** Eine HTML-Mail lädt
beim Anzeigen Bilder von fremden Servern nach – und genau daran erkennt der
Absender, dass und wann sie gelesen wurde. In einem Archiv wäre das
besonders unangenehm: Wer eine zehn Jahre alte Werbemail heraussucht,
meldet damit dem Versender, dass er noch existiert und die Adresse noch
gültig ist. Angezeigt wird deshalb der ausgelesene Text.

Bilder aus der Mail selbst sind davon nicht betroffen – die liegen im
Archiv und werden von dort angezeigt, ohne dass ein Byte das Gerät
verlässt.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from mailburg.ui import datum
from mailburg.ui.modelle import menschenlesbar

#: Breite, auf die Bildvorschauen gebracht werden.
VORSCHAUBREITE = 320


class Anhangszeile(QFrame):
    """Ein Anhang mit Namen, Größe und – bei Bildern – einer Vorschau."""

    def __init__(self, anhang, eltern=None) -> None:
        super().__init__(eltern)
        self.anhang = anhang
        self.setFrameShape(QFrame.StyledPanel)

        beschriftung = QLabel(f"<b>{anhang.filename}</b>  ({menschenlesbar(anhang.size)})")
        beschriftung.setTextFormat(Qt.RichText)

        oeffnen = QPushButton("Öffnen")
        oeffnen.clicked.connect(self._oeffnen)
        speichern = QPushButton("Speichern unter …")
        speichern.clicked.connect(self._speichern)

        kopf = QHBoxLayout()
        kopf.addWidget(beschriftung, 1)
        kopf.addWidget(oeffnen)
        kopf.addWidget(speichern)

        aufbau = QVBoxLayout(self)
        aufbau.addLayout(kopf)

        bild = self._bild()
        if bild is not None:
            anzeige = QLabel()
            anzeige.setPixmap(bild)
            anzeige.setAlignment(Qt.AlignLeft)
            aufbau.addWidget(anzeige)

    def _bild(self) -> QPixmap | None:
        """Erzeugt eine Vorschau, wenn der Anhang ein anzeigbares Bild ist."""
        if not self.anhang.payload:
            return None
        pixmap = QPixmap()
        # Qt entscheidet selbst anhand des Inhalts, ob es damit umgehen
        # kann - verlässlicher als die Dateiendung, die in E-Mails
        # notorisch falsch ist.
        if not pixmap.loadFromData(self.anhang.payload):
            return None
        if pixmap.width() > VORSCHAUBREITE:
            pixmap = pixmap.scaledToWidth(
                VORSCHAUBREITE, Qt.SmoothTransformation
            )
        return pixmap

    def _ablegen(self) -> Path:
        """Schreibt den Anhang in eine Wegwerfdatei, um ihn zu öffnen."""
        ordner = Path(tempfile.mkdtemp(prefix="mailburg-"))
        # Der Name des Anhangs bleibt erhalten, aber ohne Pfadanteile: Ein
        # Anhang namens "../../.bashrc" darf nirgendwo landen außer hier.
        ziel = ordner / Path(self.anhang.filename).name
        ziel.write_bytes(self.anhang.payload)
        return ziel

    def _oeffnen(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._ablegen())))

    def _speichern(self) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        ziel, _ = QFileDialog.getSaveFileName(
            self, "Anhang speichern", self.anhang.filename
        )
        if not ziel:
            return
        try:
            Path(ziel).write_bytes(self.anhang.payload)
        except OSError as exc:
            QMessageBox.critical(self, "Speichern gescheitert", str(exc))


class Mailvorschau(QWidget):
    """Zeigt eine Mail mit Kopfzeilen, Text und Anhängen."""

    def __init__(self, eltern=None) -> None:
        super().__init__(eltern)
        self.archiv = None

        self.kopf = QLabel()
        self.kopf.setTextFormat(Qt.RichText)
        self.kopf.setWordWrap(True)
        self.kopf.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.kopf.setContentsMargins(8, 8, 8, 8)

        self.text = QTextBrowser()
        # Nur Klartext: siehe Modulbeschreibung. Externe Verweise werden
        # ohnehin nicht verfolgt.
        self.text.setOpenExternalLinks(False)
        self.text.setOpenLinks(False)

        self.anhangsbereich = QWidget()
        self.anhangsaufbau = QVBoxLayout(self.anhangsbereich)
        self.anhangsaufbau.setContentsMargins(8, 0, 8, 8)

        rollbar = QScrollArea()
        rollbar.setWidget(self.anhangsbereich)
        rollbar.setWidgetResizable(True)
        rollbar.setMaximumHeight(420)
        self.rollbar = rollbar
        rollbar.hide()

        aufbau = QVBoxLayout(self)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.addWidget(self.kopf)
        aufbau.addWidget(self.text, 1)
        aufbau.addWidget(rollbar)

        self.leeren()

    def _kopf_setzen(self, text: str) -> None:
        """Setzt die Kopfzeilen – und blendet sie aus, wenn keine da sind.

        Ein leeres Label verschwindet nicht von selbst: Es behält seine
        Zeilenhöhe und seine Ränder. Solange keine Nachricht gewählt ist,
        klaffte deshalb zwischen Trefferliste und Vorschau ein Streifen
        von gut fünfzig Pixeln, der aussah, als sei das Fenster falsch
        aufgeteilt. Am 2026-08-28 auf einem Windows-Screenshot
        aufgefallen – auf einem Bildschirm mit mehr Pixeldichte fällt er
        entsprechend breiter aus.
        """
        self.kopf.setText(text)
        self.kopf.setVisible(bool(text))

    def leeren(self) -> None:
        self._kopf_setzen("")
        self.text.setPlainText("Wählen Sie links eine Nachricht aus.")
        self._anhaenge_leeren()
        self.rollbar.hide()

    def _anhaenge_leeren(self) -> None:
        while self.anhangsaufbau.count():
            eintrag = self.anhangsaufbau.takeAt(0)
            if eintrag.widget():
                eintrag.widget().deleteLater()

    def zeigen(self, treffer, archiv) -> None:
        """Holt die Mail aus dem Archiv und stellt sie dar."""
        from mailburg.extract import message as message_modul

        self._anhaenge_leeren()
        try:
            roh = archiv.store.get(treffer.hash, treffer.bucket)
        except (FileNotFoundError, ValueError, OSError) as exc:
            self._kopf_setzen("")
            self.text.setPlainText(f"Diese Mail ist nicht lesbar: {exc}")
            self.rollbar.hide()
            return

        zerlegt = message_modul.parse(roh, with_payloads=True)

        empfaenger = ", ".join(zerlegt.to_addrs) or "—"
        zeilen = [
            f"<b style='font-size:14px'>{_sicher(zerlegt.subject) or '(kein Betreff)'}</b>",
            f"<b>Von:</b> {_sicher(zerlegt.from_name)} &lt;{_sicher(zerlegt.from_addr)}&gt;",
            f"<b>An:</b> {_sicher(empfaenger)}",
        ]
        if zerlegt.cc_addrs:
            zeilen.append(f"<b>Kopie:</b> {_sicher(', '.join(zerlegt.cc_addrs))}")
        if zerlegt.date:
            zeilen.append(f"<b>Datum:</b> {datum.tag_und_zeit(zerlegt.date)}")
        if getattr(zerlegt, "wichtigkeit", "normal") != "normal":
            zeilen.append(f"<b>Wichtigkeit:</b> {zerlegt.wichtigkeit}")
        self._kopf_setzen("<br>".join(zeilen))

        self.text.setPlainText(zerlegt.body or "(kein Text)")

        anhaenge = zerlegt.nutzanhaenge
        for anhang in anhaenge:
            self.anhangsaufbau.addWidget(Anhangszeile(anhang))
        self.anhangsaufbau.addStretch()
        self.rollbar.setVisible(bool(anhaenge))


def _sicher(text: str) -> str:
    """Entschärft Text, der in eine Beschriftung mit Auszeichnung geht.

    Ein Betreff wie ``<b>Angebot</b>`` soll als Text erscheinen und nicht
    als Formatierung – und ein Absender, der spitze Klammern in den Namen
    schreibt, darf die Anzeige nicht durcheinanderbringen.
    """
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
