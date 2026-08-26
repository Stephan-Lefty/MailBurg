"""Eingescannte PDF durchsuchbar machen – aus der Oberfläche heraus.

Ein eingescanntes PDF ist für die Suche ein weißes Blatt. Der Anhang
heißt vielleicht ``Rechnung_2019.pdf``, aber was darin steht, findet
niemand – und das merkt man erst, wenn man danach sucht und nichts
bekommt. Das ist die unangenehmste Sorte Lücke: Sie meldet sich nicht,
sie schweigt.

Bisher gab es die Texterkennung nur auf der Kommandozeile. Wer die
Oberfläche benutzt, erfuhr also nie, dass ein Teil seines Archivs
unauffindbar ist.

**Es dauert.** Eine Seite braucht etwa fünf Sekunden; ein
Rechnungsstapel von hundert Seiten ist eine knappe Viertelstunde
Rechenzeit. Deshalb läuft das im Hintergrund, mit Fortschritt und
Abbruch – und abgebrochen wird nichts verworfen: Was erkannt ist, bleibt
erkannt.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from mailburg.ui.arbeit import Auftrag, Läufer


class Erkennungslauf(Auftrag):
    """Arbeitet die Warteschlange ab, bis nichts mehr da ist."""

    def __init__(self, archiv_pfad) -> None:
        super().__init__()
        self.archiv_pfad = archiv_pfad

    def ausfuehren(self):
        from mailburg.core import erkennung
        from mailburg.core.archive import Archive

        # Ein eigenes Handle: Der Lauf schreibt in den Index, und das
        # gehört nicht in den Faden der Oberfläche.
        with Archive.open(self.archiv_pfad, exclusive=False) as archiv:
            gesamt = erkennung.Warteschlange(archiv.index).anzahl()

            def melden(stat) -> None:
                fertig = stat.gelesen + stat.gescheitert
                self.fortschritt.emit(fertig, gesamt)
                self.meldung.emit(
                    f"{fertig} von {gesamt} gelesen"
                    + (f", {stat.gescheitert} ohne Ergebnis"
                       if stat.gescheitert else "")
                )

            return erkennung.durchlauf(
                archiv,
                budget_sekunden=0,
                budget_dokumente=0,
                fortschritt=melden,
                weiter=lambda: not self.abgebrochen,
            )


class Texterkennungsdialog(QDialog):
    """Zeigt, wie viel noch aussteht, und lässt es durchlaufen."""

    def __init__(self, archiv, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Eingescannte PDF durchsuchbar machen")
        self.setMinimumWidth(620)
        self.archiv_pfad = archiv.root
        self._laeufer = None

        from mailburg.core.erkennung import Warteschlange

        offen = Warteschlange(archiv.index).anzahl()

        self.erklaerung = QLabel()
        self.erklaerung.setWordWrap(True)
        self.erklaerung.setTextFormat(Qt.RichText)
        self.erklaerung.setText(self._einleitung(offen))

        self.balken = QProgressBar()
        self.balken.setRange(0, max(offen, 1))
        self.balken.setValue(0)
        self.balken.setVisible(False)

        self.stand = QLabel("")
        self.stand.setWordWrap(True)

        self.knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.knoepfe.button(QDialogButtonBox.Ok).setText("Jetzt lesen")
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Schließen")
        self.knoepfe.accepted.connect(self._starten)
        self.knoepfe.rejected.connect(self._abbrechen)
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(offen > 0)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(self.erklaerung)
        aufbau.addWidget(self.balken)
        aufbau.addWidget(self.stand)
        aufbau.addWidget(self.knoepfe)

    @staticmethod
    def _einleitung(offen: int) -> str:
        if not offen:
            return (
                "<p>Es warten keine eingescannten PDF. Alles, was sich lesen "
                "ließ, ist durchsuchbar.</p>"
            )
        # Fünf Sekunden je Seite, gemessen; ein PDF hat im Schnitt zwei bis
        # drei. Lieber großzügig schätzen als den Anwender überraschen.
        minuten = max(1, round(offen * 12 / 60))
        return (
            f"<p><b>{offen} eingescannte PDF warten.</b> Das sind Dokumente "
            f"ohne Textebene – ein Foto einer Seite. Für die Suche sind sie "
            f"bisher ein weißes Blatt: Der Dateiname ist zu finden, der "
            f"Inhalt nicht.</p>"
            f"<p>Die Texterkennung liest sie und legt das Ergebnis in den "
            f"Suchindex. <b>Das Archiv selbst bleibt unangetastet</b> – die "
            f"PDF werden nicht verändert.</p>"
            f"<p>Das dauert grob <b>{minuten} Minuten</b>. Sie können "
            f"jederzeit abbrechen; was gelesen ist, bleibt gelesen.</p>"
        )

    # ------------------------------------------------------------- Ablauf

    def _starten(self) -> None:
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
        self.balken.setVisible(True)
        self.stand.setText("Beginne …")

        auftrag = Erkennungslauf(self.archiv_pfad)
        auftrag.fortschritt.connect(self._schritt)
        auftrag.meldung.connect(self._welches)
        auftrag.fertig.connect(self._fertig)
        auftrag.gescheitert.connect(self._gescheitert)
        self._laeufer = Läufer(auftrag)
        self._laeufer.starten()

    def _schritt(self, erledigt: int, gesamt: int) -> None:
        if gesamt:
            self.balken.setRange(0, gesamt)
        self.balken.setValue(erledigt)

    def _welches(self, text: str) -> None:
        self.stand.setText(text)

    def _fertig(self, stat) -> None:
        self.balken.setVisible(False)
        zeilen = [f"<b>{stat.gelesen} Dokumente gelesen.</b>"]
        if getattr(stat, "offen_danach", 0):
            zeilen.append(f"{stat.offen_danach} warten noch.")
        if getattr(stat, "fehler", None):
            # Nicht verschweigen: Ein PDF, das sich nicht lesen ließ,
            # bleibt unauffindbar, und das soll man wissen.
            zeilen.append("<br>".join(str(f) for f in stat.fehler[:5]))
        self.stand.setText("<br>".join(zeilen))
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Fertig")

    def _gescheitert(self, text: str) -> None:
        self.balken.setVisible(False)
        self.stand.setText(f"Die Texterkennung ist gescheitert: {text}")
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(True)

    def _abbrechen(self) -> None:
        # Nicht warten, nur bitten – wie überall sonst. Der laufende Faden
        # räumt sich selbst weg, und was gelesen ist, steht schon im Index.
        if self._laeufer is not None:
            self._laeufer.auftrag.abbrechen()
        self.reject()
