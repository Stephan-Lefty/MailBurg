"""Einstufungsregeln verwalten – die Oberfläche zu ``core.regeln``.

Was die Regeln tun und warum es sie gibt, steht dort. Hier geht es nur
darum, sie sichtbar und änderbar zu machen.

**Die Reihenfolge ist der Kern dieser Ansicht.** Es gilt die erste
passende Regel, und wer das nicht sieht, legt eine Ausnahme an, die nie
greift. Deshalb sind die Regeln nummeriert, deshalb lassen sie sich
verschieben, und deshalb steht der Satz »Die erste passende Regel gilt«
unter der Liste statt in einem Hilfetext, den niemand aufschlägt.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from mailburg.core import sprache
from mailburg.core.regeln import BESCHRIFTUNG, FELDER, Regel, Regelwerk
from mailburg.core.retention import Category

#: Die Einstufungen zur Auswahl. »Unbestimmt« fehlt bewusst: Eine Regel,
#: die etwas für unbestimmt erklärt, tut nichts – das ist der Zustand
#: ohne Regel.
STUFEN = (
    (Category.PRIVAT, "privat"),
    (Category.HANDELSBRIEF, "Handelsbrief"),
    (Category.BUCHUNGSBELEG, "Buchungsbeleg"),
)


class Regeldialog(QDialog):
    """Die Regeln eines Archivs ansehen, anlegen, sortieren, löschen."""

    def __init__(self, eltern=None, archiv=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        self.setWindowTitle("Post beim Aufnehmen einstufen")
        self.werk = archiv.regeln if archiv is not None else Regelwerk()

        einleitung = QLabel(
            "<p>In einem Geschäftsarchiv landet private Post – der Verein, "
            "die Familie, der Handwerker für die eigene Wohnung. Sie "
            "unterliegt dort Aufbewahrungsfristen, die für sie gar nicht "
            "gelten.</p>"
            "<p>Eine Regel nimmt das vorweg: Was aus dem Vereinsordner "
            "kommt, ist privat. <b>Geholt wird trotzdem alles</b> – die "
            "Regel bestimmt nur die Einstufung, und die lässt sich "
            "zurücknehmen.</p>"
        )
        einleitung.setWordWrap(True)
        einleitung.setTextFormat(Qt.RichText)

        self.tabelle = QTableWidget(0, 3)
        self.tabelle.setHorizontalHeaderLabels(["Wenn", "passt auf", "dann"])
        self.tabelle.verticalHeader().setVisible(True)
        self.tabelle.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabelle.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabelle.setEditTriggers(QAbstractItemView.NoEditTriggers)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        kopf.setSectionResizeMode(1, QHeaderView.Stretch)
        kopf.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tabelle.setAccessibleName("Die eingerichteten Regeln")

        self.reihenfolge = QLabel(
            "<b>Die erste passende Regel gilt.</b> Eine Ausnahme gehört "
            "deshalb nach oben – sonst greift sie nie."
        )
        self.reihenfolge.setWordWrap(True)
        self.reihenfolge.setTextFormat(Qt.RichText)

        # --- Neue Regel
        self.feld = QComboBox()
        for kennung in FELDER:
            self.feld.addItem(BESCHRIFTUNG[kennung], kennung)
        self.feld.setAccessibleName("Worauf die Regel schaut")

        self.muster = QLineEdit()
        self.muster.setPlaceholderText("z. B. *@verein.example oder INBOX/Privat*")
        self.muster.setAccessibleName("Das Suchmuster")
        self.muster.setToolTip(
            "Platzhalter: * steht für beliebig viele Zeichen, ? für "
            "genau eines. Groß- und Kleinschreibung spielt keine Rolle."
        )
        self.muster.returnPressed.connect(self._anlegen)

        self.stufe = QComboBox()
        for kategorie, beschriftung in STUFEN:
            self.stufe.addItem(beschriftung, kategorie)
        self.stufe.setAccessibleName("Als was eingestuft wird")

        self.anlegen_knopf = QPushButton("Hinzufügen")
        self.anlegen_knopf.clicked.connect(self._anlegen)

        neue = QHBoxLayout()
        neue.addWidget(QLabel("Wenn"))
        neue.addWidget(self.feld)
        neue.addWidget(QLabel("passt auf"))
        neue.addWidget(self.muster, 1)
        neue.addWidget(QLabel("→"))
        neue.addWidget(self.stufe)
        neue.addWidget(self.anlegen_knopf)

        # --- Reihenfolge und Löschen
        self.hoch = QPushButton("▲ Nach oben")
        self.hoch.clicked.connect(lambda: self._schieben(-1))
        self.runter = QPushButton("▼ Nach unten")
        self.runter.clicked.connect(lambda: self._schieben(1))
        self.weg = QPushButton("Entfernen")
        self.weg.clicked.connect(self._entfernen)
        self.anwenden_knopf = QPushButton("Auf bestehende Post anwenden …")
        self.anwenden_knopf.setToolTip(
            "Beim Aufnehmen greifen die Regeln von selbst. Bereits "
            "archivierte Post rühren sie nicht an – das geschieht nur "
            "hier, und nur nach einer Rückfrage."
        )
        self.anwenden_knopf.clicked.connect(self._anwenden)

        werkzeuge = QHBoxLayout()
        werkzeuge.addWidget(self.hoch)
        werkzeuge.addWidget(self.runter)
        werkzeuge.addWidget(self.weg)
        werkzeuge.addStretch()
        werkzeuge.addWidget(self.anwenden_knopf)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        knoepfe.button(QDialogButtonBox.Save).setText("Übernehmen")
        knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self._speichern)
        knoepfe.rejected.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(einleitung)
        aufbau.addWidget(self.tabelle, 1)
        aufbau.addWidget(self.reihenfolge)
        aufbau.addLayout(werkzeuge)
        aufbau.addSpacing(8)
        aufbau.addWidget(QLabel("<b>Neue Regel</b>"))
        aufbau.addLayout(neue)
        aufbau.addWidget(knoepfe)

        self.tabelle.itemSelectionChanged.connect(self._knoepfe_richten)
        self._fuellen()

    # ------------------------------------------------------------ Anzeige

    def _fuellen(self) -> None:
        self.tabelle.setRowCount(len(self.werk))
        for zeile, regel in enumerate(self.werk):
            self.tabelle.setItem(
                zeile, 0, QTableWidgetItem(BESCHRIFTUNG[regel.feld])
            )
            self.tabelle.setItem(zeile, 1, QTableWidgetItem(regel.muster))
            self.tabelle.setItem(
                zeile, 2, QTableWidgetItem(regel.kategorie.value)
            )
        self._knoepfe_richten()

    def _knoepfe_richten(self) -> None:
        zeile = self.tabelle.currentRow()
        gewaehlt = 0 <= zeile < len(self.werk)
        self.hoch.setEnabled(gewaehlt and zeile > 0)
        self.runter.setEnabled(gewaehlt and zeile < len(self.werk) - 1)
        self.weg.setEnabled(gewaehlt)
        self.anwenden_knopf.setEnabled(bool(len(self.werk)))

    # ------------------------------------------------------------ Ändern

    def _anlegen(self) -> None:
        muster = self.muster.text().strip()
        if not muster:
            QMessageBox.information(
                self, "Kein Muster",
                "Ohne Muster wüsste die Regel nicht, worauf sie schauen "
                "soll. Ein Beispiel: *@verein.example",
            )
            self.muster.setFocus()
            return

        try:
            neu = Regel(
                feld=self.feld.currentData(),
                muster=muster,
                kategorie=self.stufe.currentData(),
            )
        except ValueError as fehler:
            QMessageBox.warning(self, "Das geht so nicht", str(fehler))
            return

        self.werk.regeln.append(neu)
        self.muster.clear()
        self._fuellen()
        self.tabelle.setCurrentCell(len(self.werk) - 1, 0)
        self.muster.setFocus()

    def _schieben(self, richtung: int) -> None:
        zeile = self.tabelle.currentRow()
        ziel = zeile + richtung
        if not (0 <= zeile < len(self.werk) and 0 <= ziel < len(self.werk)):
            return
        regeln = self.werk.regeln
        regeln[zeile], regeln[ziel] = regeln[ziel], regeln[zeile]
        self._fuellen()
        self.tabelle.setCurrentCell(ziel, 0)

    def _entfernen(self) -> None:
        zeile = self.tabelle.currentRow()
        if not 0 <= zeile < len(self.werk):
            return
        regel = self.werk.regeln[zeile]
        antwort = QMessageBox.question(
            self, "Regel entfernen",
            f"{regel.beschreibung()}\n\n"
            f"Bereits eingestufte Post bleibt, wie sie ist – "
            f"nur künftige wird nicht mehr von dieser Regel erfasst.\n\n"
            f"Entfernen?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return
        del self.werk.regeln[zeile]
        self._fuellen()

    # ------------------------------------------------------------ Wirkung

    def _speichern(self) -> None:
        if self.archiv is None:
            self.accept()
            return
        try:
            self.archiv.regeln_setzen(self.werk)
        except Exception as fehler:  # noqa: BLE001
            QMessageBox.critical(
                self, "Nicht gespeichert",
                f"Die Regeln ließen sich nicht sichern:\n\n{fehler}",
            )
            return
        self.accept()

    def _anwenden(self) -> None:
        """Stuft bestehende Post nach – nach einer Rückfrage mit Zahlen.

        **Erst speichern.** Wer Regeln anlegt und gleich anwendet, meint
        die eben angelegten. Ohne das Sichern liefe der Lauf gegen den
        Stand von vorhin, und das Ergebnis wäre nicht das, was auf dem
        Bildschirm steht.
        """
        if self.archiv is None:
            return
        try:
            self.archiv.regeln_setzen(self.werk)
        except Exception as fehler:  # noqa: BLE001
            QMessageBox.critical(
                self, "Nicht gespeichert",
                f"Die Regeln ließen sich nicht sichern:\n\n{fehler}",
            )
            return

        betroffen = self._vorschau()
        if not betroffen:
            QMessageBox.information(
                self, "Nichts zu tun",
                "Keine der bereits archivierten Mails müsste umgestuft "
                "werden.",
            )
            return

        antwort = QMessageBox.question(
            self, "Auf bestehende Post anwenden",
            f"{sprache.mails(len(betroffen))} "
            + ("würde" if len(betroffen) == 1 else "würden")
            + " umgestuft.\n\n"
            "Von Hand vorgenommene Einstufungen werden dabei "
            "überschrieben. Jeder Vorgang steht im Journal und lässt "
            "sich einzeln zurücknehmen.\n\n"
            "Jetzt anwenden?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return

        for digest, kategorie, begruendung in betroffen:
            self.archiv.classify(
                digest, kategorie, actor="Regel", note=begruendung
            )
        QMessageBox.information(
            self, "Fertig",
            f"Umgestuft: {sprache.mails(len(betroffen))}. Im Journal "
            f"vermerkt.",
        )

    def _vorschau(self) -> list[tuple[str, Category, str]]:
        """Was eine Anwendung ändern würde – ohne etwas zu ändern."""
        gefunden: list[tuple[str, Category, str]] = []
        for eintrag in self.archiv.index.search("", limit=1_000_000):
            ordner = [
                z["folder"] for z in self.archiv.index.db.execute(
                    """SELECT l.folder FROM locations l
                       JOIN messages m ON m.id = l.msg_id
                       WHERE m.hash = ?""",
                    (eintrag.hash,),
                )
            ] or [""]

            for einer in ordner:
                befund = self.werk.einstufung(
                    ordner=einer, von=eintrag.from_addr or "", an=""
                )
                if befund is None:
                    continue
                kategorie, begruendung = befund
                if eintrag.category != kategorie.value:
                    gefunden.append((eintrag.hash, kategorie, begruendung))
                break
        return gefunden
