"""Das Archiv in eine Datei packen – für die Ablage anderswo.

Der Dialog sagt vorher, was zu erwarten ist, und hinterher, was
herauskam. Beides mit ehrlichen Zahlen: Kleiner wird ein Archiv beim
Packen kaum, weil die Mails schon komprimiert liegen. Wer eine große
Ersparnis erwartet und zwei Prozent bekommt, hält das Programm für
kaputt – dabei ist es die Ablage, die ihre Arbeit schon getan hat.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QLayout,
    QProgressBar,
    QVBoxLayout,
)

from mailburg.core import sprache
from mailburg.ui.arbeit import Auftrag, Läufer
from mailburg.ui.fliesstext import Fliesstext


class Packlauf(Auftrag):
    """Packt im Hintergrund – bei einem großen Archiv dauert es."""

    def __init__(self, archiv_pfad: Path, ziel: Path) -> None:
        super().__init__()
        self.archiv_pfad = archiv_pfad
        self.ziel = ziel

    def ausfuehren(self):
        from mailburg.core import sicherung

        return sicherung.packen(
            self.archiv_pfad,
            self.ziel,
            fortschritt=lambda n, von: self.fortschritt.emit(n, von),
            abbruch=lambda: self.abgebrochen,
        )


class Sicherungsdialog(QDialog):
    """Zielort wählen, packen, Ergebnis zeigen."""

    def __init__(self, archiv, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Archiv sichern")
        self.setMinimumWidth(640)
        self.archiv_pfad = archiv.root
        self.archiv_name = archiv.name
        self._laeufer = None

        self.erklaerung = Fliesstext()
        self.erklaerung.setText(
            "<p>MailBurg packt das ganze Archiv in <b>eine einzige "
            "Datei</b>. Die lässt sich in die Cloud legen, auf eine "
            "andere Platte kopieren oder wegtragen.</p>"
            "<p><b>Viel kleiner wird sie nicht.</b> Ihre Mails liegen "
            "bereits komprimiert im Archiv – da ist nichts mehr zu holen. "
            "Der Gewinn ist ein anderer: Statt tausender einzelner "
            "Dateien haben Sie eine, und Cloud-Programme kommen damit um "
            "ein Vielfaches schneller zurecht.</p>"
            "<p>Der Suchindex kommt nicht mit. Er liegt außerhalb des "
            "Archivs und lässt sich jederzeit neu aufbauen.</p>"
        )

        self.balken = QProgressBar()
        self.balken.setFormat("%v von %m Dateien")
        self.balken.setVisible(False)

        self.stand = Fliesstext("")

        self.knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.knoepfe.button(QDialogButtonBox.Ok).setText("Speichern unter …")
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        self.knoepfe.accepted.connect(self._waehlen)
        self.knoepfe.rejected.connect(self._abbrechen)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(self.erklaerung)
        aufbau.addWidget(self.balken)
        aufbau.addWidget(self.stand)
        aufbau.addWidget(self.knoepfe)
        aufbau.setSizeConstraint(QLayout.SetMinimumSize)

    # -------------------------------------------------------------- Ablauf

    def _waehlen(self) -> None:
        from mailburg.core import orte, sicherung

        dialog = QFileDialog(self, "Sicherung speichern")
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.selectFile(sicherung.vorschlag(self.archiv_pfad, self.archiv_name))

        # Dieselben Orte wie überall sonst: Eine Sicherung gehört gerade
        # nicht auf die Platte, auf der das Archiv liegt.
        from PySide6.QtCore import QUrl

        seitenleiste = list(dialog.sidebarUrls())
        for ort in orte.vorschlagen():
            traeger = ort.pfad.parent
            if traeger.is_dir():
                url = QUrl.fromLocalFile(str(traeger))
                if url not in seitenleiste:
                    seitenleiste.append(url)
        dialog.setSidebarUrls(seitenleiste)

        if not dialog.exec() or not dialog.selectedFiles():
            return
        ziel = Path(dialog.selectedFiles()[0])

        if ziel.is_relative_to(self.archiv_pfad):
            self.stand.setText(
                "<b>Nicht ins Archiv selbst.</b> Eine Sicherung, die neben "
                "dem Original liegt, geht mit ihm zusammen verloren."
            )
            return

        self._packen(ziel)

    def _packen(self, ziel: Path) -> None:
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
        self.balken.setVisible(True)
        self.stand.setText(f"Packe nach {ziel} …")

        auftrag = Packlauf(self.archiv_pfad, ziel)
        auftrag.fortschritt.connect(self._schritt)
        auftrag.fertig.connect(self._fertig)
        auftrag.gescheitert.connect(self._gescheitert)
        self._laeufer = Läufer(auftrag)
        self._laeufer.starten()

    def _schritt(self, erledigt: int, gesamt: int) -> None:
        if gesamt:
            self.balken.setRange(0, gesamt)
        self.balken.setValue(erledigt)

    def _fertig(self, befund) -> None:
        self.balken.setVisible(False)
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(True)
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Schließen")
        self.stand.setText(
            f"<p><b>Fertig.</b> {sprache.dateien(befund.dateien)} "
            f"in einer.</p>"
            f"<p>{befund.ziel_bytes / 1024 / 1024:.0f} MB · "
            f"{befund.ziel}</p>".replace(",", ".")
        )

    def _gescheitert(self, text: str) -> None:
        self.balken.setVisible(False)
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(True)
        self.stand.setText(f"<b>Nicht gesichert:</b> {text}")

    def _abbrechen(self) -> None:
        if self._laeufer is not None:
            self._laeufer.auftrag.abbrechen()
        self.reject()


class Entpacklauf(Auftrag):
    """Holt eine Sicherung heraus und baut den Suchindex neu."""

    def __init__(self, datei: Path, ziel: Path) -> None:
        super().__init__()
        self.datei = datei
        self.ziel = ziel

    def ausfuehren(self):
        from mailburg.core import sicherung
        from mailburg.core.archive import Archive

        self.meldung.emit("Entpacke …")
        befund = sicherung.entpacken(
            self.datei, self.ziel,
            fortschritt=lambda n, _von: self.fortschritt.emit(n, 0),
        )

        # Der Index wurde nicht mitgesichert - ohne ihn findet die Suche
        # nichts, obwohl alles da ist. Das gleich hier zu erledigen
        # erspart dem Anwender die Frage, warum sein Archiv leer wirkt.
        self.meldung.emit("Baue den Suchindex neu …")
        with Archive.open(self.ziel) as archiv:
            archiv.rebuild_index()
        return befund


class Rueckholdialog(QDialog):
    """Eine Sicherung wieder zu einem eigenen Archiv machen."""

    def __init__(self, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Sicherung in neues Archiv")
        self.setMinimumWidth(640)
        self.ziel: Path | None = None
        self._laeufer = None

        erklaerung = Fliesstext(
            "<p>Aus einer gesicherten Datei wird wieder ein Archiv.</p>"
            "<p><b>Das Zielverzeichnis muss leer sein.</b> In ein "
            "vorhandenes Archiv hinein zu entpacken hieße, zwei "
            "Protokolle zu vermischen – hinterher wäre keines von beiden "
            "prüfbar.</p>"
            "<p>Der Suchindex wird anschließend neu aufgebaut; er wird "
            "nicht mitgesichert, weil er sich aus dem Protokoll ergibt.</p>"
        )

        self.balken = QProgressBar()
        self.balken.setRange(0, 0)
        self.balken.setVisible(False)

        self.stand = Fliesstext("")

        self.knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.knoepfe.button(QDialogButtonBox.Ok).setText("Datei wählen …")
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        self.knoepfe.accepted.connect(self._waehlen)
        self.knoepfe.rejected.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(erklaerung)
        aufbau.addWidget(self.balken)
        aufbau.addWidget(self.stand)
        aufbau.addWidget(self.knoepfe)
        aufbau.setSizeConstraint(QLayout.SetMinimumSize)

    def _waehlen(self) -> None:
        datei, _ = QFileDialog.getOpenFileName(
            self, "Sicherung öffnen", str(Path.home()),
            "Gesicherte Archive (*.tar.zst *.tar.xz);;Alle Dateien (*)",
        )
        if not datei:
            return
        ordner = QFileDialog.getExistingDirectory(
            self, "Leeren Ordner für das Archiv wählen", str(Path.home())
        )
        if not ordner:
            return

        self.ziel = Path(ordner)
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
        self.balken.setVisible(True)
        self.stand.setText("Entpacke …")

        auftrag = Entpacklauf(Path(datei), self.ziel)
        auftrag.meldung.connect(self.stand.setText)
        auftrag.fertig.connect(self._fertig)
        auftrag.gescheitert.connect(self._gescheitert)
        self._laeufer = Läufer(auftrag)
        self._laeufer.starten()

    def _fertig(self, befund) -> None:
        self.balken.setVisible(False)
        self.stand.setText(
            f"<p><b>Zurückgeholt.</b> {befund.dateien} Dateien.</p>"
            f"<p>Bitte prüfen Sie das Ergebnis mit "
            f"<i>Archiv → Journal prüfen</i> – eine Übertragung lässt "
            f"schon einmal etwas aus.</p>"
        )
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Schließen")

    def _gescheitert(self, text: str) -> None:
        self.balken.setVisible(False)
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(True)
        self.stand.setText(f"<b>Nicht zurückgeholt:</b> {text}")


class Uebernahmelauf(Auftrag):
    """Nimmt die Mails einer Sicherung ins offene Archiv auf."""

    def __init__(self, archiv, datei: Path) -> None:
        super().__init__()
        self.archiv = archiv
        self.datei = datei

    def ausfuehren(self):
        from mailburg.core import sicherung

        self.meldung.emit("Entpacke die Sicherung …")
        return sicherung.uebernehmen(
            self.archiv,
            self.datei,
            fortschritt=lambda n, von: self.fortschritt.emit(n, von),
            abbruch=lambda: self.abgebrochen,
        )


class Uebernahmedialog(QDialog):
    """Mails aus einer Sicherung in das geöffnete Archiv holen."""

    def __init__(self, archiv, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Sicherung importieren")
        self.setMinimumWidth(640)
        self.archiv = archiv
        self._laeufer = None

        erklaerung = Fliesstext(
            f"<p>Die Mails aus einer gesicherten Datei kommen in Ihr "
            f"<b>geöffnetes Archiv</b> – {archiv.name}. Sie behalten "
            f"dabei ihr Postfach und ihren Ordner, denn das steht im "
            f"Protokoll der Sicherung.</p>"
            f"<p><b>Doppelte müssen Sie nicht fürchten.</b> Eine Mail, "
            f"die schon da ist, wird nicht zweimal abgelegt. Sie können "
            f"dieselbe Sicherung gefahrlos zweimal einlesen.</p>"
            f"<p>Soll aus der Datei stattdessen ein eigenes, neues Archiv "
            f"werden, nehmen Sie <i>Sicherung in neues Archiv …</i></p>"
        )

        self.balken = QProgressBar()
        self.balken.setFormat("%v von %m Mails")
        self.balken.setVisible(False)

        self.stand = Fliesstext("")

        self.knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.knoepfe.button(QDialogButtonBox.Ok).setText("Datei wählen …")
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        self.knoepfe.accepted.connect(self._waehlen)
        self.knoepfe.rejected.connect(self._abbrechen)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(erklaerung)
        aufbau.addWidget(self.balken)
        aufbau.addWidget(self.stand)
        aufbau.addWidget(self.knoepfe)
        aufbau.setSizeConstraint(QLayout.SetMinimumSize)

    def _waehlen(self) -> None:
        datei, _ = QFileDialog.getOpenFileName(
            self, "Sicherung öffnen", str(Path.home()),
            "Gesicherte Archive (*.tar.zst *.tar.xz);;Alle Dateien (*)",
        )
        if not datei:
            return

        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
        self.balken.setVisible(True)
        auftrag = Uebernahmelauf(self.archiv, Path(datei))
        auftrag.meldung.connect(self.stand.setText)
        auftrag.fortschritt.connect(self._schritt)
        auftrag.fertig.connect(self._fertig)
        auftrag.gescheitert.connect(self._gescheitert)
        self._laeufer = Läufer(auftrag)
        self._laeufer.starten()

    def _schritt(self, erledigt: int, gesamt: int) -> None:
        if gesamt:
            self.balken.setRange(0, gesamt)
        self.balken.setValue(erledigt)
        self.stand.setText("")

    def _fertig(self, befund) -> None:
        self.balken.setVisible(False)
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Schließen")
        zeilen = [f"<b>{sprache.mails(befund.dateien)} eingelesen.</b>"]
        if befund.warnungen:
            # Nicht verschweigen: Was nicht gelesen werden konnte, fehlt.
            zeilen.append("Nicht lesbar waren:")
            zeilen.extend(befund.warnungen[:5])
        self.stand.setText("<br>".join(zeilen))

    def _gescheitert(self, text: str) -> None:
        self.balken.setVisible(False)
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(True)
        self.stand.setText(f"<b>Nicht eingelesen:</b> {text}")

    def _abbrechen(self) -> None:
        if self._laeufer is not None:
            self._laeufer.auftrag.abbrechen()
        self.reject()
