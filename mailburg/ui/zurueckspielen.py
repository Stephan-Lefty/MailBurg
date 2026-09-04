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
    (
        "postfach",
        "In ein Postfach (IMAP)",
        "Legt die Nachrichten über IMAP in ein eingerichtetes Konto – "
        "auch in ein anderes als das, aus dem sie stammen. Vorhandene "
        "erkennt MailBurg an ihrer Message-ID und überspringt sie; ohne "
        "das legte der Server bei jedem Lauf neue Kopien an.",
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
        self.waehlen = QPushButton("Ordner auswählen …")
        self.waehlen.clicked.connect(self._waehlen)
        zeile = QHBoxLayout()
        zeile.addWidget(self.pfad, 1)
        zeile.addWidget(self.waehlen)

        # **Ein Postfach wählt man nicht als Pfad.** Deshalb steht an
        # derselben Stelle wahlweise eine Liste der eingerichteten
        # Konten – sichtbar nur, wenn sie gebraucht wird.
        self.postfach = QComboBox()
        for konto in self._konten():
            self.postfach.addItem(konto.beschreibung(), konto.name)
        self.postfach.currentIndexChanged.connect(self._pruefen)
        self.postfach.hide()
        zeile.addWidget(self.postfach, 1)

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
        self.wohin = QLabel("Wohin:")
        felder.addRow(self.wohin, zeile)
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

    @staticmethod
    def _konten() -> list:
        from mailburg.core.accounts import Kontenliste

        return list(Kontenliste().konten)

    def _ins_postfach(self) -> bool:
        return self._format() == "postfach"

    def _zielzeile_richten(self) -> None:
        """Zeigt das Pfadfeld oder die Kontenliste, je nach Format."""
        postfach = self._ins_postfach()
        self.pfad.setVisible(not postfach)
        self.waehlen.setVisible(not postfach)
        self.postfach.setVisible(postfach)
        self.wohin.setText("In welches Postfach:" if postfach else "Wohin:")

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

        self._zielzeile_richten()

        teile = []
        if self._ins_postfach():
            gut = self.postfach.count() > 0
            if not gut:
                teile.append(
                    "Dafür braucht es ein eingerichtetes Postfach – "
                    "<i>Einstellungen → Postfächer verwalten …</i>"
                )
        else:
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
            ziel = ("" if self._ins_postfach()
                    else Path(self.pfad.text().strip()))
            try:
                teile.append(kern.ziel_pruefen(ziel, self._format()))
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
        konto = passwort = None
        if self._ins_postfach():
            konto, passwort = self._konto_und_passwort()
            if konto is None:
                return

        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        self.balken.setRange(0, 0)
        self.balken.show()

        auftrag = Rueckspiellauf(
            self.archiv.root,
            "" if konto else Path(self.pfad.text().strip()),
            format=self._format(),
            suche=self.suche.text().strip(),
            struktur=self.struktur.isChecked(),
            konto=konto,
            passwort=passwort or "",
        )
        auftrag.meldung.connect(self.befund.setText)
        auftrag.fortschritt.connect(self._zaehlen)
        auftrag.fertig.connect(self._fertig)
        auftrag.gescheitert.connect(self._gescheitert)

        self.laeufer = Läufer(auftrag)
        self.laeufer.starten()

    def _konto_und_passwort(self):
        """Holt das gewählte Postfach samt Passwort – oder fragt danach.

        **Zurückspielen schreibt in ein fremdes Postfach.** Deshalb wird
        hier zuletzt bestätigt, wie viele Nachrichten wohin gehen: Auf
        der Platte ließe sich ein Fehlgriff wegwerfen, im Postfach eines
        Kollegen nicht.
        """
        from mailburg.core import accounts
        from mailburg.core.sprache import anzahl

        name = self.postfach.currentData()
        konto = next((k for k in self._konten() if k.name == name), None)
        if konto is None:
            return None, None

        treffer = self.archiv.index.count(self.suche.text().strip())
        antwort = QMessageBox.question(
            self,
            "Ins Postfach zurückspielen",
            f"{anzahl(treffer, 'Nachricht', 'Nachrichten')} gehen nach "
            f"»{konto.name}« ({konto.server}).\n\n"
            f"Dort wird geschrieben – gelöscht oder verändert wird nichts. "
            f"Was schon da ist, erkennt MailBurg an der Message-ID und "
            f"überspringt es.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Ok,
        )
        if antwort != QMessageBox.Ok:
            return None, None

        # **Hier wird nicht nach dem Passwort gefragt.** Ein Postfach,
        # aus dem MailBurg abruft, hat eines im Schlüsselbund; fehlt es,
        # ist etwas an der Einrichtung nicht in Ordnung, und das gehört
        # dorthin geklärt und nicht in einen Dialog, der gerade
        # zehntausend Nachrichten wegschreiben will. Genauso hält es die
        # Einzelrückgabe in ``ui/zurueck.py``.
        passwort = accounts.passwort_holen(konto)
        if not passwort:
            QMessageBox.warning(
                self, "Kein Passwort",
                f"Für »{konto.name}« liegt kein Passwort im Schlüsselbund. "
                f"Unter Einstellungen → Postfächer verwalten … lässt es "
                f"sich hinterlegen.",
            )
            return None, None
        return konto, passwort

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
