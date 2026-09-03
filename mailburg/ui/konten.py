"""Postfächer verwalten, nachdem die Einrichtung durch ist.

Der Assistent läuft einmal. Danach kommt trotzdem ein Konto hinzu, ein
altes wird stillgelegt, ein Passwort ändert sich – und für all das gab es
bisher nur die Kommandozeile.

**Jedes Postfach gehört ausdrücklich in ein Archiv.** Das war einmal
anders gedacht – die Liste galt programmweit, und beim Abruf sollte sich
entscheiden, wohin. Diese Ordnung ist am 2026-08-26 im Echtbetrieb
gescheitert: Von 9.866 Mails in einem Geschäftsarchiv gehörten 176
dorthin, der Rest war private Post und lag damit unter zehnjährigen
Aufbewahrungsfristen.

Ein Postfach kann in mehreren Archiven stehen – selten, aber es gibt
Gründe. Ohne Zuordnung wird es beim Abruf übergangen; das ist die
unbequemere Voreinstellung und die einzige vertretbare.
"""

from __future__ import annotations

import pathlib

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
            ["Postfach", "Mailadresse", "Server", "Passwort", "Zustand",
             "Archive"]
        )
        self.baum.setRootIsDecorated(False)
        self.baum.setAccessibleName("Eingerichtete Postfächer")
        self.baum.itemSelectionChanged.connect(self._auswahl_geaendert)

        self.hinzu = QPushButton("Hinzufügen …")
        self.hinzu.clicked.connect(self._hinzufuegen)
        self.uebernehmen = QPushButton("Aus dem Mailprogramm übernehmen …")
        self.uebernehmen.clicked.connect(self._uebernehmen)
        self.zuordnen = QPushButton("Archiv zuordnen …")
        self.zuordnen.setToolTip(
            "In welche Archive dieses Postfach abgerufen wird. Ohne "
            "Zuordnung bleibt es beim Abruf außen vor."
        )
        self.zuordnen.clicked.connect(self._zuordnen)
        self.passwort_neu = QPushButton("Passwort ändern …")
        self.passwort_neu.clicked.connect(self._passwort_aendern)
        self.anmelden = QPushButton("Anmelden …")
        self.anmelden.setToolTip(
            "Anmeldung per OAuth2 – nötig bei Microsoft, das kein Passwort "
            "mehr annimmt. Sie brauchen dafür die Kennung einer selbst "
            "registrierten Anwendung; siehe docs/oauth2.md."
        )
        self.anmelden.clicked.connect(self._anmelden)
        self.stilllegen = QPushButton("Stilllegen")
        self.stilllegen.clicked.connect(self._stilllegen)
        self.entfernen = QPushButton("Entfernen")
        self.entfernen.clicked.connect(self._entfernen)

        knopfreihe = QHBoxLayout()
        for knopf in (self.hinzu, self.uebernehmen):
            knopfreihe.addWidget(knopf)
        knopfreihe.addStretch()
        for knopf in (self.zuordnen, self.passwort_neu, self.anmelden,
                      self.stilllegen, self.entfernen):
            knopfreihe.addWidget(knopf)

        hinweis = QLabel(
            "Ein stillgelegtes Postfach bleibt eingerichtet, wird beim Abruf "
            "aber übergangen – nützlich für ein Konto, das es nicht mehr "
            "gibt. <b>Entfernen</b> nimmt es samt Passwort aus der Liste; die "
            "bereits archivierten Mails bleiben in jedem Fall erhalten.<br>"
            "<b>Ohne Archiv wird ein Postfach beim Abruf übergangen</b> – "
            "sonst landete geschäftliche Post im Privatarchiv."
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
        # Beim Neuaufbau frisch nachsehen: Zwischen zwei Durchläufen kann
        # ein Archiv angelegt, umbenannt oder abgezogen worden sein.
        self._namen = None
        self.baum.clear()
        for konto in self.liste.konten:
            gemerkt = "im Schlüsselbund" if accounts.passwort_holen(konto) else "fehlt"
            eintrag = QTreeWidgetItem([
                konto.name,
                konto.benutzer,
                f"{konto.server}:{konto.port}",
                gemerkt,
                "aktiv" if konto.aktiv else "stillgelegt",
                self._archivnamen(konto),
            ])
            eintrag.setData(0, Qt.UserRole, konto.name)
            if not konto.aktiv:
                eintrag.setForeground(0, self.palette().placeholderText())
            self.baum.addTopLevelItem(eintrag)

        for spalte in range(6):
            self.baum.resizeColumnToContents(spalte)
        self._auswahl_geaendert()

    def _archivnamen(self, konto) -> str:
        """Wohin dieses Postfach abgerufen wird – in Klarnamen.

        Gespeichert ist die Archivkennung, weil ein Archiv auf einer
        externen Platte morgen woanders liegt. Angezeigt gehört der
        Name: Mit »220b2cd0-f3b1-…« kann niemand etwas anfangen.
        """
        from mailburg.core.archive import archivnamen

        if not konto.archive:
            return "keinem – wird übergangen"

        # Einmal lesen, nicht je Kennung: Bei acht Postfächern und zwei
        # Archiven waren das vorher sechzehn Durchläufe durch dieselben
        # Dateien.
        if self._namen is None:
            self._namen = archivnamen()

        # Was sich nicht auflösen lässt, bleibt als gekürzte Kennung
        # stehen. Ein Archiv auf einer abgezogenen Platte hat trotzdem
        # Postfächer, und die zu verschweigen wäre schlimmer.
        return ", ".join(
            self._namen.get(k, k[:8] + "…") for k in konto.archive
        )

    def _zuordnen(self) -> None:
        """Fragt, in welche Archive dieses Postfach abgerufen wird."""
        konto = self._gewaehltes_konto()
        if konto is None:
            return
        gewaehlt = ArchivZuordnung.fragen(konto, self)
        if gewaehlt is None:
            return

        for kennung in list(konto.archive):
            if kennung not in gewaehlt:
                self.liste.loesen(konto.name, kennung)
        for kennung in gewaehlt:
            self.liste.zuordnen(konto.name, kennung)
        self._fuellen()

    def _gewaehltes_konto(self):
        stellen = self.baum.selectedItems()
        if not stellen:
            return None
        return self.liste.finden(stellen[0].data(0, Qt.UserRole))

    def _auswahl_geaendert(self) -> None:
        konto = self._gewaehltes_konto()
        for knopf in (self.passwort_neu, self.anmelden, self.stilllegen,
                      self.entfernen):
            knopf.setEnabled(konto is not None)
        if konto is None:
            return

        self.stilllegen.setText(
            "Wieder aufnehmen" if not konto.aktiv else "Stilllegen"
        )
        # **Beides zugleich ergibt keinen Sinn.** Ein Postfach meldet
        # sich entweder mit Passwort an oder per OAuth2; die Knöpfe
        # sollen zeigen, was gerade gilt, statt beide gleich aussehen
        # zu lassen.
        self.anmelden.setText(
            "Neu anmelden …" if konto.per_oauth2 else "Anmelden …"
        )
        self.passwort_neu.setEnabled(not konto.per_oauth2)
        if konto.per_oauth2:
            self.passwort_neu.setToolTip(
                "Dieses Postfach meldet sich per OAuth2 an – ein Passwort "
                "wird dafür nicht gebraucht."
            )
        else:
            self.passwort_neu.setToolTip("")

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

    def _anmelden(self) -> None:
        """Meldet das gewählte Postfach per OAuth2 an."""
        from mailburg.ui.anmelden import Anmeldedialog

        konto = self._gewaehltes_konto()
        if konto is None:
            return

        dialog = Anmeldedialog(konto, self)
        if not dialog.exec():
            return

        self.liste.speichern()
        self._fuellen()
        QMessageBox.information(
            self,
            "Angemeldet",
            f"»{konto.name}« ist angemeldet.\n\n"
            f"Die Anmeldung liegt im Schlüsselbund Ihres Systems. MailBurg "
            f"erneuert sie bei jedem Abruf von selbst – nur wenn Sie das "
            f"Kontopasswort ändern oder den Zugriff beim Anbieter "
            f"entziehen, ist eine neue Anmeldung nötig.",
        )

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


class ArchivZuordnung(QDialog):
    """In welche Archive ein Postfach abgerufen wird.

    Angeboten werden die zuletzt geöffneten Archive – mehr kennt das
    Programm nicht, und mehr braucht es auch nicht: Wer ein Archiv
    zuordnen will, hat es zuvor einmal geöffnet.
    """

    def __init__(self, konto, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle(f"Archive für »{konto.name}«")
        self.setMinimumWidth(520)

        from PySide6.QtWidgets import QCheckBox

        self.kaestchen: list[tuple[QCheckBox, str]] = []
        aufbau = QVBoxLayout(self)

        erklaerung = QLabel(
            f"In welche Archive soll <b>{konto.name}</b> abgerufen werden?<br>"
            f"Ohne Zuordnung bleibt das Postfach beim Abruf außen vor – "
            f"sonst landete geschäftliche Post im Privatarchiv und private "
            f"unter den Aufbewahrungsfristen eines Geschäftsarchivs."
        )
        erklaerung.setWordWrap(True)
        erklaerung.setTextFormat(Qt.RichText)
        aufbau.addWidget(erklaerung)

        for kennung, name in self._bekannte_archive():
            kaestchen = QCheckBox(name)
            kaestchen.setChecked(kennung in konto.archive)
            aufbau.addWidget(kaestchen)
            self.kaestchen.append((kaestchen, kennung))

        if not self.kaestchen:
            leer = QLabel(
                "Es ist noch kein Archiv bekannt. Öffnen Sie zuerst eines "
                "über <i>Archiv → Öffnen</i>."
            )
            leer.setWordWrap(True)
            leer.setTextFormat(Qt.RichText)
            aufbau.addWidget(leer)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        aufbau.addStretch()
        aufbau.addWidget(knoepfe)

    @staticmethod
    def _bekannte_archive() -> list[tuple[str, str]]:
        """Kennung und Name der zuletzt geöffneten Archive."""
        import json

        from mailburg.core.einstellungen import zuletzt_benutzte_pfade

        gefunden = []
        for pfad in zuletzt_benutzte_pfade():
            datei = pathlib.Path(pfad) / "archive.json"
            try:
                daten = json.loads(datei.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            kennung = daten.get("uuid")
            if kennung and kennung not in [k for k, _ in gefunden]:
                name = daten.get("name") or pathlib.Path(pfad).name
                art = daten.get("mode", "")
                zusatz = " (geschäftlich)" if art.startswith("gesch") else ""
                gefunden.append((kennung, f"{name}{zusatz}"))
        return gefunden

    @classmethod
    def fragen(cls, konto, eltern=None) -> list[str] | None:
        """Zeigt den Dialog. Gibt die gewählten Kennungen zurück, sonst None."""
        dialog = cls(konto, eltern)
        if dialog.exec() != QDialog.Accepted:
            return None
        return [k for kaestchen, k in dialog.kaestchen if kaestchen.isChecked()]
