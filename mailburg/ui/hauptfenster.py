"""Das Hauptfenster: Ordner, Trefferliste, Vorschau.

Dreispaltig, wie man es von Mailprogrammen kennt – wer MailBurg zum ersten
Mal öffnet, soll sich nicht erst zurechtfinden müssen.

Die Suchleiste steht oben und ist der eigentliche Einstieg. Wer nur
``rechnung`` tippt, sucht überall; alles Weitere sind Einschränkungen, die
man dazunehmen kann, aber nicht muss.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mailburg import APP_NAME
from mailburg.core.accounts import Kontenliste
from mailburg.core.archive import Archive, ArchiveError, ArchiveLocked
from mailburg.search.query import QueryError, describe_syntax
from mailburg.ui.arbeit import Abruflauf, Läufer, alle_beenden
from mailburg.ui.modelle import Trefferliste
from mailburg.ui.vorschau import Mailvorschau

#: So lange wird nach dem letzten Tastendruck gewartet, bevor gesucht wird.
#: Ohne diese Pause liefe bei jedem Buchstaben eine Abfrage – bei einem
#: großen Archiv wäre das Tippen dann zäh.
TIPPAUSE = 250


class Hauptfenster(QMainWindow):
    """Das Fenster, in dem ein Archiv durchsucht und gefüllt wird."""

    def __init__(self, archiv_pfad: Path) -> None:
        super().__init__()
        self.archiv: Archive | None = None
        self.laeufer: Läufer | None = None

        self.setWindowTitle(APP_NAME)

        self._aufbauen()
        self._menue()
        # Erst nach dem Aufbau: Wiederhergestellt werden auch die
        # Aufteilungen, und die gibt es vorher noch nicht.
        self._groesse_herstellen()
        self._oeffnen(archiv_pfad)

    # ------------------------------------------------------------- Aufbau

    def _aufbauen(self) -> None:
        self.suchfeld = QLineEdit()
        self.suchfeld.setPlaceholderText(
            "Suchen … z. B. rechnung · von:müller · datei:*.pdf · jahr:2025"
        )
        self.suchfeld.setClearButtonEnabled(True)
        self.suchfeld.setAccessibleName("Suchausdruck")
        self.suchfeld.textChanged.connect(self._tippen)
        self.suchfeld.returnPressed.connect(self._suchen)

        self.tipp_uhr = QTimer(self)
        self.tipp_uhr.setSingleShot(True)
        self.tipp_uhr.timeout.connect(self._suchen)

        self.baum = QTreeWidget()
        self.baum.setHeaderLabels(["Postfach", "Mails"])
        self.baum.setAccessibleName("Postfächer und Ordner")
        self.baum.itemClicked.connect(self._ordner_gewaehlt)
        self.baum.setMinimumWidth(230)

        self.modell = Trefferliste()
        self.tabelle = QTableView()
        self.tabelle.setModel(self.modell)
        self.tabelle.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabelle.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabelle.setAlternatingRowColors(True)
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setAccessibleName("Trefferliste")
        self.tabelle.setSortingEnabled(False)

        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        kopf.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        kopf.setSectionResizeMode(2, QHeaderView.Interactive)
        kopf.setSectionResizeMode(3, QHeaderView.Stretch)
        kopf.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tabelle.setColumnWidth(2, 220)

        self.tabelle.selectionModel().selectionChanged.connect(self._treffer_gewaehlt)

        self.vorschau = Mailvorschau()

        rechts = QSplitter(Qt.Vertical)
        rechts.addWidget(self.tabelle)
        rechts.addWidget(self.vorschau)
        rechts.setSizes([320, 400])

        self.senkrecht = rechts
        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self.baum)
        teiler.addWidget(rechts)
        teiler.setSizes([250, 930])
        self.waagerecht = teiler

        mitte = QWidget()
        aufbau = QVBoxLayout(mitte)
        aufbau.setContentsMargins(8, 8, 8, 0)
        aufbau.addWidget(self.suchfeld)
        aufbau.addWidget(teiler, 1)
        self.setCentralWidget(mitte)

        self.stand = QLabel("")
        self.balken = QProgressBar()
        self.balken.setMaximumWidth(220)
        self.balken.hide()
        self.statusBar().addWidget(self.stand, 1)
        self.statusBar().addPermanentWidget(self.balken)

    def _menue(self) -> None:
        archiv = self.menuBar().addMenu("&Archiv")

        anlegen = QAction("Neues Archiv anlegen …", self)
        anlegen.setShortcut(QKeySequence.New)
        anlegen.triggered.connect(self._neues_archiv)
        archiv.addAction(anlegen)

        oeffnen = QAction("Archiv öffnen …", self)
        oeffnen.setShortcut(QKeySequence.Open)
        oeffnen.triggered.connect(self._archiv_waehlen)
        archiv.addAction(oeffnen)

        archiv.addSeparator()
        pruefen = QAction("Hash-Kette prüfen", self)
        pruefen.triggered.connect(self._pruefen)
        archiv.addAction(pruefen)

        archiv.addSeparator()
        schliessen = QAction("Beenden", self)
        schliessen.setShortcut(QKeySequence.Quit)
        schliessen.triggered.connect(self.close)
        archiv.addAction(schliessen)

        post = self.menuBar().addMenu("&Post")
        self.abrufen_aktion = QAction("Jetzt abrufen", self)
        self.abrufen_aktion.setShortcut("F5")
        self.abrufen_aktion.triggered.connect(self._abrufen)
        post.addAction(self.abrufen_aktion)

        post.addSeparator()
        postfaecher = QAction("Postfächer verwalten …", self)
        postfaecher.triggered.connect(self._postfaecher)
        post.addAction(postfaecher)

        hintergrund = QAction("Abruf im Hintergrund …", self)
        hintergrund.triggered.connect(self._zeitplan)
        post.addAction(hintergrund)

        suchen_menue = self.menuBar().addMenu("&Suchen")
        ausfuehrlich = QAction("Ausführlich suchen …", self)
        ausfuehrlich.setShortcut("Ctrl+F")
        ausfuehrlich.triggered.connect(self._suchmaske)
        suchen_menue.addAction(ausfuehrlich)

        hilfe = self.menuBar().addMenu("&Hilfe")
        suchhilfe = QAction("Suchsprache …", self)
        suchhilfe.setShortcut("F1")
        suchhilfe.triggered.connect(self._suchhilfe)
        hilfe.addAction(suchhilfe)

    # ------------------------------------------------------------- Archiv

    def _oeffnen(self, pfad: Path) -> None:
        if self.archiv is not None:
            self.archiv.close()
            self.archiv = None

        try:
            # Nur lesend: Ein laufender Abruf im Hintergrund soll das
            # Fenster nicht aussperren, und umgekehrt.
            self.archiv = Archive.open(Path(pfad), exclusive=False)
        except (ArchiveError, ArchiveLocked, OSError) as exc:
            QMessageBox.critical(self, "Archiv lässt sich nicht öffnen", str(exc))
            return

        self.modell.suchindex = self.archiv.index
        self.setWindowTitle(f"{APP_NAME} – {self.archiv.name}")
        self._baum_fuellen()
        self._suchen()

    def _neues_archiv(self) -> None:
        """Führt den Einrichtungsassistenten für ein weiteres Archiv.

        Ohne diesen Weg käme man an den Assistenten nur beim allerersten
        Start heran – wer ein zweites Archiv anlegen will, etwa auf einer
        externen Platte, stünde vor verschlossener Tür.
        """
        from mailburg.ui.assistent import Einrichtungsassistent

        assistent = Einrichtungsassistent(self)
        if not assistent.exec() or assistent.archiv_pfad is None:
            return

        self._oeffnen(assistent.archiv_pfad)
        if self.archiv is not None:
            from mailburg.ui.app import merken

            merken(assistent.archiv_pfad)
            if getattr(assistent, "soll_abrufen", False):
                self._abrufen()

    def _archiv_waehlen(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        gewaehlt = QFileDialog.getExistingDirectory(self, "Archiv öffnen")
        if gewaehlt:
            self._oeffnen(Path(gewaehlt))

    # ------------------------------------------------------- Fenstergröße

    def _groesse_herstellen(self) -> None:
        """Stellt die Ansicht her, die der Anwender zuletzt eingestellt hat.

        Beim allerersten Start gibt es nichts herzustellen. Dann ist eine
        großzügige Vorgabe richtig: Ein Archiv lebt von der Übersicht –
        Postfächer, Trefferliste und Vorschau nebeneinander. Ein knappes
        Fenster zwingt beim ersten Blick zum Ziehen an den Rändern, bevor
        man überhaupt etwas erkennt.
        """
        from mailburg.ui.app import gemerktes

        stand = gemerktes()
        wieder = stand.get("fenster")

        if wieder and self.restoreGeometry(QByteArray.fromBase64(wieder.encode())):
            if stand.get("maximiert"):
                self.showMaximized()
        else:
            flaeche = self.screen().availableGeometry()
            # Nicht ganz bis an den Rand: Ein Fenster, das den Bildschirm
            # ausfüllt, sieht aus wie ein Fehler, wenn es keiner ist.
            self.resize(
                min(1600, int(flaeche.width() * 0.9)),
                min(1000, int(flaeche.height() * 0.9)),
            )
            self.move(flaeche.center() - self.rect().center())

        for name, teiler in (("waagerecht", self.waagerecht),
                             ("senkrecht", self.senkrecht)):
            gespeichert = stand.get(name)
            if gespeichert:
                teiler.restoreState(QByteArray.fromBase64(gespeichert.encode()))

        kopf = stand.get("spalten")
        if kopf:
            self.tabelle.horizontalHeader().restoreState(
                QByteArray.fromBase64(kopf.encode())
            )

    def _groesse_merken(self) -> None:
        from mailburg.ui.app import merken_unter

        # Im maximierten Zustand liefert saveGeometry die Größe davor -
        # genau richtig, sonst käme das Fenster beim Wiederherstellen nie
        # aus der Vollbildgröße heraus.
        merken_unter("fenster", bytes(self.saveGeometry().toBase64()).decode())
        merken_unter("maximiert", self.isMaximized())
        merken_unter("waagerecht",
                     bytes(self.waagerecht.saveState().toBase64()).decode())
        merken_unter("senkrecht",
                     bytes(self.senkrecht.saveState().toBase64()).decode())
        merken_unter(
            "spalten",
            bytes(self.tabelle.horizontalHeader().saveState().toBase64()).decode(),
        )

    def _baum_fuellen(self) -> None:
        self.baum.clear()
        if self.archiv is None:
            return

        alle = QTreeWidgetItem(["Alle Postfächer", ""])
        alle.setData(0, Qt.UserRole, "")
        self.baum.addTopLevelItem(alle)

        # Angezeigt wird die Mailadresse, nicht der frei gewählte Name.
        # "Kontakt" sagt bei drei Postfächern auf demselben Server nichts;
        # kontakt@example.org lässt keinen Zweifel, welches gemeint ist.
        # Gesucht wird weiterhin über den Namen - der steht so im Archiv.
        adressen = {k.name: k.benutzer for k in Kontenliste().konten}

        konten: dict[str, QTreeWidgetItem] = {}
        for konto, ordner, anzahl in self.archiv.index.accounts():
            if konto not in konten:
                # Fällt ein Postfach später aus der Liste, bleiben seine
                # Mails im Archiv. Dann muss der Name genügen.
                eintrag = QTreeWidgetItem([adressen.get(konto, konto), ""])
                eintrag.setData(0, Qt.UserRole, f"konto:{_quoten(konto)}")
                self.baum.addTopLevelItem(eintrag)
                konten[konto] = eintrag
            unter = QTreeWidgetItem([ordner, f"{anzahl:,}".replace(",", ".")])
            unter.setData(
                0, Qt.UserRole, f"konto:{_quoten(konto)} ordner:{_quoten(ordner)}"
            )
            konten[konto].addChild(unter)

        alle.setSelected(True)
        self.baum.expandItem(alle)

    # -------------------------------------------------------------- Suchen

    def _tippen(self) -> None:
        self.tipp_uhr.start(TIPPAUSE)

    def _suchen(self) -> None:
        self.tipp_uhr.stop()
        if self.archiv is None:
            return

        ausdruck = self.suchfeld.text().strip()
        try:
            self.modell.suchen(ausdruck)
        except QueryError as exc:
            self.stand.setText(f"Suchausdruck: {exc}")
            return
        except Exception as exc:  # noqa: BLE001
            self.stand.setText(f"Suche gescheitert: {exc}")
            return

        self.vorschau.leeren()
        anzahl = f"{self.modell.gesamt:,}".replace(",", ".")
        if self.modell.gesamt:
            self.stand.setText(f"{anzahl} Treffer")
        else:
            self.stand.setText(
                "Keine Treffer. F1 erklärt die Suchsprache."
                if ausdruck
                else "Das Archiv ist noch leer."
            )

    def _ordner_gewaehlt(self, eintrag: QTreeWidgetItem) -> None:
        vorgabe = eintrag.data(0, Qt.UserRole) or ""
        self.suchfeld.setText(vorgabe)
        self._suchen()

    def _treffer_gewaehlt(self) -> None:
        stellen = self.tabelle.selectionModel().selectedRows()
        if not stellen or self.archiv is None:
            self.vorschau.leeren()
            return
        treffer = self.modell.treffer_bei(stellen[0].row())
        if treffer is not None:
            self.vorschau.zeigen(treffer, self.archiv)

    # -------------------------------------------------------------- Abrufen

    def _abrufen(self) -> None:
        if self.archiv is None or self.laeufer is not None:
            return

        konten = Kontenliste().aktive()
        if not konten:
            QMessageBox.information(
                self,
                "Kein Postfach eingerichtet",
                "Es ist noch kein Postfach eingerichtet, aus dem abgerufen "
                "werden könnte.",
            )
            return

        # Der Abruf braucht das Archiv schreibend; das Fenster hält es nur
        # lesend. Deshalb gibt der Auftrag es sich selbst - und wir
        # schließen unseren Index solange nicht, sondern lesen weiter.
        pfad = self.archiv.root
        self.abrufen_aktion.setEnabled(False)
        self.balken.setRange(0, 0)
        self.balken.show()
        self.stand.setText("Rufe ab …")

        auftrag = Abruflauf(pfad, konten)
        auftrag.meldung.connect(self.stand.setText)
        auftrag.fertig.connect(self._abruf_fertig)
        auftrag.gescheitert.connect(self._abruf_gescheitert)

        self.laeufer = Läufer(auftrag)
        self.laeufer.starten()

    def _abruf_fertig(self, ergebnisse: dict) -> None:
        self.laeufer = None
        self.balken.hide()
        self.abrufen_aktion.setEnabled(True)

        neu = sum(getattr(e, "neu", 0) for e in ergebnisse.values())
        fehler = [f"{k}: {v}" for k, v in ergebnisse.items() if isinstance(v, Exception)]

        self.stand.setText(
            f"{neu} neue Nachrichten" if neu else "Nichts Neues"
        )
        if fehler:
            QMessageBox.warning(
                self, "Nicht alle Postfächer erreichbar", "\n\n".join(fehler)
            )
        self._baum_fuellen()
        self._suchen()

    def _abruf_gescheitert(self, text: str) -> None:
        self.laeufer = None
        self.balken.hide()
        self.abrufen_aktion.setEnabled(True)
        self.stand.setText("Abruf gescheitert")
        QMessageBox.critical(self, "Abruf gescheitert", text)

    # --------------------------------------------------------------- Sonst

    def _pruefen(self) -> None:
        if self.archiv is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            bericht = self.archiv.verify()
        finally:
            QApplication.restoreOverrideCursor()

        zeilen = [
            "Hash-Kette: " + ("unversehrt" if bericht["chain_ok"] else "BESCHÄDIGT"),
            f"Laut Journal: {bericht['expected']} Mails",
            f"In der Ablage: {bericht['on_disk']} Dateien",
        ]
        if bericht["missing"]:
            zeilen.append(f"Fehlend: {len(bericht['missing'])}")
        if bericht["unexpected"]:
            zeilen.append(
                f"Ohne Journaleintrag: {len(bericht['unexpected'])} – diese Mails "
                f"wurden nicht über MailBurg aufgenommen."
            )

        art = QMessageBox.information if bericht["ok"] else QMessageBox.warning
        art(self, "Prüfung", "\n".join(zeilen))

    def _zeitplan(self) -> None:
        from mailburg.ui.zeitplan import Zeitplandialog

        pfad = self.archiv.root if self.archiv is not None else None
        Zeitplandialog(self, archiv=pfad).exec()

    def _postfaecher(self) -> None:
        """Postfächer hinzufügen, stilllegen oder entfernen."""
        from mailburg.ui.konten import Kontenverwaltung

        Kontenverwaltung(self).exec()

    def _suchmaske(self) -> None:
        """Öffnet die Maske und übernimmt, was sie zusammengestellt hat."""
        from mailburg.ui.suchmaske import Suchmaske

        maske = Suchmaske(self.archiv, self.suchfeld.text(), self)
        if maske.exec():
            # In die Suchleiste, nicht direkt in die Abfrage: So sieht der
            # Anwender, was aus seinen Angaben geworden ist, und kann es
            # von Hand weiterdrehen.
            self.suchfeld.setText(maske.ausdruck())
            self._suchen()

    def _suchhilfe(self) -> None:
        fenster = QMessageBox(self)
        fenster.setWindowTitle("Suchsprache")
        fenster.setTextFormat(Qt.PlainText)
        fenster.setText(describe_syntax())
        fenster.exec()

    def closeEvent(self, ereignis) -> None:
        # Zuerst merken, solange das Fenster noch steht.
        self._groesse_merken()
        # Nicht nur den eigenen Abruf: Auch Prüfungen aus Dialogen können
        # noch laufen, und ein Faden ohne Fenster beendet das Programm.
        alle_beenden(3000)
        if self.laeufer is not None:
            self.laeufer.warten(3000)
        if self.archiv is not None:
            self.archiv.close()
        super().closeEvent(ereignis)


def _quoten(wert: str) -> str:
    """Setzt einen Wert in Anführungszeichen, wenn er Leerzeichen enthält."""
    return f'"{wert}"' if " " in wert else wert
