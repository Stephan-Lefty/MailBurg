"""Postfächer verwalten, nachdem die Einrichtung durch ist.

Der Assistent läuft einmal. Danach kommt trotzdem ein Konto hinzu, ein
altes wird stillgelegt, ein Passwort ändert sich – und für all das gab es
bisher nur die Kommandozeile.

**Konten gelten programmweit, nicht je Archiv.** Wer zwei Archive führt,
etwa ein privates und ein geschäftliches, ruft dieselben Postfächer ab und
entscheidet beim Abruf, wohin. Das ist die einfachere Ordnung: Ein Postfach
zweimal einzurichten hieße, es zweimal abzurufen.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from mailburg.core import accounts
from mailburg.core.accounts import Kontenliste


class Kontenverwaltung(QDialog):
    """Zeigt die eingerichteten Postfächer und lässt sie ändern."""

    def __init__(self, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Postfächer")
        self.setMinimumSize(720, 420)
        self.liste = Kontenliste()

        self.baum = QTreeWidget()
        # Die Mailadresse gehört sichtbar dazu: Der Name ist frei gewählt
        # und sagt bei mehreren Postfächern desselben Anbieters nichts.
        self.baum.setHeaderLabels(
            ["Postfach", "Mailadresse", "Server", "Passwort", "Zustand"]
        )
        self.baum.setRootIsDecorated(False)
        self.baum.setAccessibleName("Eingerichtete Postfächer")
        self.baum.itemSelectionChanged.connect(self._auswahl_geaendert)

        self.hinzu = QPushButton("Hinzufügen …")
        self.hinzu.clicked.connect(self._hinzufuegen)
        self.uebernehmen = QPushButton("Aus Thunderbird übernehmen …")
        self.uebernehmen.clicked.connect(self._uebernehmen)
        self.passwort_neu = QPushButton("Passwort ändern …")
        self.passwort_neu.clicked.connect(self._passwort_aendern)
        self.stilllegen = QPushButton("Stilllegen")
        self.stilllegen.clicked.connect(self._stilllegen)
        self.entfernen = QPushButton("Entfernen")
        self.entfernen.clicked.connect(self._entfernen)

        knopfreihe = QHBoxLayout()
        for knopf in (self.hinzu, self.uebernehmen):
            knopfreihe.addWidget(knopf)
        knopfreihe.addStretch()
        for knopf in (self.passwort_neu, self.stilllegen, self.entfernen):
            knopfreihe.addWidget(knopf)

        hinweis = QLabel(
            "Ein stillgelegtes Postfach bleibt eingerichtet, wird beim Abruf "
            "aber übergangen – nützlich für ein Konto, das es nicht mehr "
            "gibt. <b>Entfernen</b> nimmt es samt Passwort aus der Liste; die "
            "bereits archivierten Mails bleiben in jedem Fall erhalten."
        )
        hinweis.setWordWrap(True)
        hinweis.setTextFormat(Qt.RichText)

        schliessen = QDialogButtonBox(QDialogButtonBox.Close)
        schliessen.rejected.connect(self.accept)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(self.baum, 1)
        aufbau.addLayout(knopfreihe)
        aufbau.addWidget(hinweis)
        aufbau.addWidget(schliessen)

        self._fuellen()

    # ------------------------------------------------------------- Anzeigen

    def _fuellen(self) -> None:
        self.baum.clear()
        for konto in self.liste.konten:
            gemerkt = "im Schlüsselbund" if accounts.passwort_holen(konto) else "fehlt"
            eintrag = QTreeWidgetItem([
                konto.name,
                konto.benutzer,
                f"{konto.server}:{konto.port}",
                gemerkt,
                "aktiv" if konto.aktiv else "stillgelegt",
            ])
            eintrag.setData(0, Qt.UserRole, konto.name)
            if not konto.aktiv:
                eintrag.setForeground(0, self.palette().placeholderText())
            self.baum.addTopLevelItem(eintrag)

        for spalte in range(5):
            self.baum.resizeColumnToContents(spalte)
        self._auswahl_geaendert()

    def _gewaehltes_konto(self):
        stellen = self.baum.selectedItems()
        if not stellen:
            return None
        return self.liste.finden(stellen[0].data(0, Qt.UserRole))

    def _auswahl_geaendert(self) -> None:
        konto = self._gewaehltes_konto()
        for knopf in (self.passwort_neu, self.stilllegen, self.entfernen):
            knopf.setEnabled(konto is not None)
        if konto is not None:
            self.stilllegen.setText("Wieder aufnehmen" if not konto.aktiv else "Stilllegen")

    # -------------------------------------------------------------- Ändern

    def _hinzufuegen(self) -> None:
        from mailburg.ui.assistent import KontoDialog

        dialog = KontoDialog(self)
        if not dialog.exec():
            return
        konto = dialog.konto()

        if self.liste.finden(konto.name):
            QMessageBox.warning(
                self, "Name vergeben",
                f"Ein Postfach namens »{konto.name}« gibt es schon.",
            )
            return
        schon_da = self.liste.finden_nach_postfach(konto.benutzer, konto.server)
        if schon_da is not None:
            antwort = QMessageBox.question(
                self, "Postfach bereits eingerichtet",
                f"Dieses Postfach ist bereits als »{schon_da.name}« "
                f"eingerichtet. Trotzdem ein zweites Mal hinzufügen?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if antwort != QMessageBox.Yes:
                return

        if not self._passwort_erfragen(konto, "Passwort für das neue Postfach"):
            return
        self.liste.hinzufuegen(konto)
        self._fuellen()

    def _uebernehmen(self) -> None:
        """Öffnet den Kontenschritt des Assistenten für weitere Postfächer."""
        from mailburg.ui.assistent import Einrichtungsassistent

        assistent = Einrichtungsassistent(self)
        # Direkt auf die Kontenseite: Archiv und Willkommen sind erledigt.
        assistent.setStartId(assistent.pageIds()[2])
        assistent.exec()
        self.liste = Kontenliste()
        self._fuellen()

    def _passwort_aendern(self) -> None:
        konto = self._gewaehltes_konto()
        if konto is None:
            return
        self._passwort_erfragen(konto, f"Neues Passwort für {konto.name}")
        self._fuellen()

    def _passwort_erfragen(self, konto, titel: str) -> bool:
        """Fragt ein Passwort ab und prüft es gleich am Server."""
        from mailburg.ui.assistent import PasswortNachfrage
        from mailburg.sources.imap import ImapFehler, ImapSource

        dialog = PasswortNachfrage(konto, titel, self)
        if not dialog.exec() or not dialog.passwort.text():
            return False

        passwort = dialog.passwort.text()
        try:
            quelle = ImapSource(konto, passwort)
        except ImapFehler as exc:
            antwort = QMessageBox.question(
                self, "Anmeldung nicht möglich",
                f"{exc}\n\nTrotzdem speichern?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if antwort != QMessageBox.Yes:
                return False
        else:
            quelle.close()

        if not accounts.passwort_setzen(konto, passwort):
            QMessageBox.information(
                self, "Kein Schlüsselbund",
                "Das Passwort ließ sich nicht ablegen – es wird bei jedem "
                "Abruf neu erfragt.",
            )
        return True

    def _stilllegen(self) -> None:
        konto = self._gewaehltes_konto()
        if konto is None:
            return
        konto.aktiv = not konto.aktiv
        self.liste.speichern()
        self._fuellen()

    def _entfernen(self) -> None:
        konto = self._gewaehltes_konto()
        if konto is None:
            return

        antwort = QMessageBox.question(
            self, "Postfach entfernen",
            f"»{konto.name}« aus der Liste nehmen?\n\n"
            f"Das Passwort wird aus dem Schlüsselbund gelöscht. Die bereits "
            f"archivierten Mails bleiben erhalten – entfernt wird nur der "
            f"Zugang zum Abrufen.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return

        accounts.passwort_loeschen(konto)
        self.liste.entfernen(konto.name)
        self._fuellen()
