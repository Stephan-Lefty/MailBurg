"""Viele Mails auf einmal aus dem Archiv auf die Platte zurück.

**Der Anlass ist eine Rückmeldung vom 2026-09-03**, von demselben
Anwender, der JMAP angestoßen hat: »Ich würde mir ein Restore wünschen,
wie in MailStore Home. […] Also unabhängige Backups und Restores.«

Einzeln ging das längst – rechte Maustaste auf eine Nachricht, und sie
geht zurück ins Postfach oder als Datei auf die Platte. Was fehlte, war
die Menge.

**Der Dialog sagt vor dem Start, was passieren wird.** Wie viele
Nachrichten es sind, wohin sie gehen und was das gewählte Format mit
ihnen macht. Bei zehntausend Mails ist das keine Höflichkeit: Ein falsch
gesetzter Suchausdruck kostet sonst Gigabyte und eine halbe Stunde.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from mailburg.ui.arbeit import Läufer, Rueckspiellauf

#: Was in der Auswahlliste steht: Kennung, Beschriftung, Erklärung.
FORMATE = (
    (
        "maildir",
        "Maildir – eine Datei je Nachricht",
        "Bytegenau, mit Lesezustand, beliebig groß. Das Format für alles, "
        "was wieder ein Postfach werden soll. Evolution und moderne "
        "Thunderbird-Profile lesen es unmittelbar.",
    ),
    (
        "mbox",
        "MBOX – eine Datei je Ordner",
        "So sind Thunderbirds lokale Ordner aufgebaut. <b>Nicht "
        "bytegenau:</b> Zeilen, die mit »From « beginnen, bekommen ein "
        "»&gt;« davor – das verlangt das Format, sonst gälten sie als "
        "Anfang der nächsten Nachricht.",
    ),
    (
        "eml",
        "Einzelne .eml-Dateien",
        "Eine Datei je Nachricht, ohne Maildir-Gerüst. Zum Hineinziehen "
        "in ein beliebiges Mailprogramm.",
    ),
)


class Rueckspieldialog(QDialog):
    """Fragt nach Ziel, Format und Auswahl – und schreibt dann."""

    def __init__(self, archiv, suche: str = "", eltern=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        self.laeufer = None
        self.setWindowTitle("Ins Dateisystem zurückspielen")

        erklaerung = QLabel(
            "<p>Schreibt Nachrichten aus dem Archiv als Dateien auf die "
            "Platte – zum Zurückholen in ein Mailprogramm, für eine "
            "Übergabe oder als zweites Standbein neben der Sicherung.</p>"
            "<p><b>Das Archiv bleibt unverändert.</b> Es entsteht eine "
            "Kopie; gelöscht wird nichts. Und derselbe Lauf zweimal ändert "
            "nichts: Was schon dort liegt, erkennt MailBurg wieder.</p>"
        )
        erklaerung.setWordWrap(True)

        self.pfad = QLineEdit()
        self.pfad.setPlaceholderText("Noch kein Ordner gewählt")
        self.pfad.textChanged.connect(self._pruefen)
        waehlen = QPushButton("Ordner auswählen …")
        waehlen.clicked.connect(self._waehlen)
        zeile = QHBoxLayout()
        zeile.addWidget(self.pfad, 1)
        zeile.addWidget(waehlen)

        self.format = QComboBox()
        for kennung, beschriftung, _ in FORMATE:
            self.format.addItem(beschriftung, kennung)
        self.format.currentIndexChanged.connect(self._pruefen)

        self.suche = QLineEdit(suche)
        self.suche.setPlaceholderText("leer = alle Nachrichten")
        self.suche.setToolTip(
            "Dieselbe Suchsprache wie im Hauptfenster – etwa "
            "»von:firma.example seit:01.01.2024«."
        )
        self.suche.textChanged.connect(self._pruefen)

        self.struktur = QCheckBox("Postfächer und Ordner nachbauen")
        self.struktur.setChecked(True)
        self.struktur.setToolTip(
            "Ohne Haken landet alles in einem Topf. Mit Haken entsteht je "
            "Postfach und Ordner ein eigener Zielordner."
        )

        felder = QFormLayout()
        felder.addRow("Wohin:", zeile)
        felder.addRow("Format:", self.format)
        felder.addRow("Auswahl:", self.suche)

        self.befund = QLabel()
        self.befund.setWordWrap(True)
        self.befund.setTextFormat(Qt.RichText)

        self.balken = QProgressBar()
        self.balken.hide()

        self.knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.knoepfe.button(QDialogButtonBox.Ok).setText("Zurückspielen")
        self.knoepfe.accepted.connect(self._starten)
        self.knoepfe.rejected.connect(self._abbrechen_oder_schliessen)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(erklaerung)
        aufbau.addLayout(felder)
        aufbau.addWidget(self.struktur)
        aufbau.addWidget(self.befund)
        aufbau.addWidget(self.balken)
        aufbau.addStretch(1)
        aufbau.addWidget(self.knoepfe)

        self._pruefen()

    # ------------------------------------------------------------ Wählen

    def _waehlen(self) -> None:
        ort = QFileDialog.getExistingDirectory(
            self, "Zielordner auswählen",
            self.pfad.text() or str(Path.home()),
        )
        if ort:
            self.pfad.setText(ort)

    # ------------------------------------------------------------ Prüfen

    def _pruefen(self) -> None:
        """Sagt vor dem Start, wie viele Mails wohin gehen.

        **Die Zahl ist der Punkt.** Ein Suchausdruck, der versehentlich
        auf alles passt, sieht genauso aus wie einer, der auf drei Mails
        passt – bis hier die Zahl steht.
        """
        from mailburg.core import zurueckspielen as kern
        from mailburg.core.sprache import anzahl

        teile = []
        gut = bool(self.pfad.text().strip())

        try:
            treffer = self.archiv.index.count(self.suche.text().strip())
        except Exception:  # noqa: BLE001 – ein halb getippter Ausdruck
            self.befund.setText(
                "<span style='color:palette(mid);'>Der Suchausdruck ist "
                "noch nicht vollständig.</span>"
            )
            self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
            return

        teile.append(f"<b>{anzahl(treffer, 'Nachricht', 'Nachrichten')}</b>")
        if not treffer:
            gut = False

        if gut:
            try:
                teile.append(kern.ziel_pruefen(
                    Path(self.pfad.text().strip()), self._format()
                ))
            except kern.ZielFehler as fehler:
                teile.append(str(fehler))
                gut = False

        teile.append(dict((k, e) for k, _, e in FORMATE)[self._format()])
        self.befund.setText("<br>".join(teile))
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(gut)

    def _format(self) -> str:
        return self.format.currentData()

    # ------------------------------------------------------------ Laufen

    def _starten(self) -> None:
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        self.balken.setRange(0, 0)
        self.balken.show()

        auftrag = Rueckspiellauf(
            self.archiv.root,
            Path(self.pfad.text().strip()),
            format=self._format(),
            suche=self.suche.text().strip(),
            struktur=self.struktur.isChecked(),
        )
        auftrag.meldung.connect(self.befund.setText)
        auftrag.fortschritt.connect(self._zaehlen)
        auftrag.fertig.connect(self._fertig)
        auftrag.gescheitert.connect(self._gescheitert)

        self.laeufer = Läufer(auftrag)
        self.laeufer.starten()

    def _zaehlen(self, getan: int, gesamt: int) -> None:
        if gesamt:
            self.balken.setRange(0, gesamt)
            self.balken.setValue(getan)

    def _abbrechen_oder_schliessen(self) -> None:
        if self.laeufer is not None:
            self.laeufer.auftrag.abbrechen()
            self.befund.setText("Wird abgebrochen …")
            return
        self.reject()

    def _fertig(self, bericht) -> None:
        self.laeufer = None
        self.balken.hide()

        zeilen = [bericht.zusammenfassung(), "", f"Ziel: {bericht.ziel}"]
        if bericht.mehrfach:
            zeilen.append(
                f"\n{bericht.mehrfach} Nachrichten lagen an mehreren "
                f"Stellen. Geschrieben wurde jede einmal – sonst stünde "
                f"dieselbe Mail hinterher mehrfach da."
            )
        if bericht.abgebrochen:
            zeilen.append(
                "\nAbgebrochen. Was geschrieben ist, ist vollständig; "
                "ein späterer Lauf setzt dort an."
            )
        if bericht.fehler:
            zeilen.append(
                f"\n{len(bericht.fehler)} Nachrichten ließen sich nicht "
                f"schreiben. Die erste: {bericht.fehler[0][1]}"
            )
        if bericht.format == "mbox":
            zeilen.append(
                "\nHinweis zum MBOX-Format: Zeilen, die mit »From « "
                "beginnen, tragen jetzt ein »>« davor. Wer es bytegenau "
                "braucht, nimmt Maildir."
            )

        QMessageBox.information(self, "Zurückgespielt", "\n".join(zeilen))
        self.accept()

    def _gescheitert(self, text: str) -> None:
        self.laeufer = None
        self.balken.hide()
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(True)
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Schließen")
        QMessageBox.critical(self, "Zurückspielen gescheitert", text)
