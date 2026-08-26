"""Das Hauptfenster: Ordner, Trefferliste, Vorschau.

Dreispaltig, wie man es von Mailprogrammen kennt – wer MailBurg zum ersten
Mal öffnet, soll sich nicht erst zurechtfinden müssen.

Die Suchleiste steht oben und ist der eigentliche Einstieg. Wer nur
``rechnung`` tippt, sucht überall; alles Weitere sind Einschränkungen, die
man dazunehmen kann, aber nicht muss.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer, Signal
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

#: Wie sich die Fläche in der Standardansicht verteilt. Abgenommen an
#: der Aufteilung, die sich im Betrieb als brauchbar erwiesen hat: Der
#: Postfachbaum braucht Platz für verschachtelte Ordnernamen, und die
#: Vorschau mehr als die Trefferliste – gelesen wird unten, gesucht oben.
BAUMANTEIL = 0.20
TREFFERANTEIL = 0.42
from mailburg.core.accounts import Kontenliste
from mailburg.core.archive import Archive, ArchiveError, ArchiveLocked
from mailburg.search.query import QueryError
from mailburg.ui import datum, farben
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

        self.baum = Postfachbaum()
        self.baum.setHeaderLabels(["Postfächer", "Mails"])
        self.baum.reihenfolge_geaendert.connect(self._reihenfolge_merken)
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
        # Klick auf den Spaltenkopf sortiert, nochmal klicken dreht um.
        self.tabelle.setSortingEnabled(True)
        self.tabelle.horizontalHeader().setSortIndicator(1, Qt.DescendingOrder)

        self._spalten_einrichten()
        self._baumspalten_einrichten()

        self.tabelle.selectionModel().selectionChanged.connect(self._treffer_gewaehlt)
        # Ein Archiv, aus dem nichts wieder herauskommt, ist ein Grab.
        self.tabelle.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabelle.customContextMenuRequested.connect(self._trefferminue)
        # Doppelklick öffnet die Nachricht zum Lesen. Das ist, was man
        # bei einer Liste erwartet - und die Vorschau unten ist zum
        # Überfliegen da, nicht zum Lesen.
        self.tabelle.doubleClicked.connect(self._oeffnen_zum_lesen)

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
        # Gleich unter dem Suchfeld, nicht unten in der Statuszeile: Bei
        # zweitausend Mails ist die Suche in Millisekunden durch. Wer
        # dabei auf das Suchfeld schaut - und das tut man beim Tippen -,
        # bemerkt eine Zahl am unteren Fensterrand überhaupt nicht.
        self.suchmeldung = QLabel("")
        self.suchmeldung.setTextFormat(Qt.RichText)
        self.suchmeldung.setAccessibleName("Suchergebnis")
        self.suchmeldung.setContentsMargins(2, 2, 2, 4)

        aufbau.addWidget(self.suchfeld)
        aufbau.addWidget(self.suchmeldung)
        aufbau.addWidget(teiler, 1)
        self.setCentralWidget(mitte)

        self.stand = QLabel("")
        self.balken = QProgressBar()
        self.balken.setMaximumWidth(220)
        self.balken.hide()
        # Dauerhaft rechts, nicht links bei den Meldungen: Der Bestand
        # soll immer dastehen. Links wechselt der Text mit jeder Suche,
        # jedem Abruf, jedem Fehler - und genau diese Angabe darf nicht
        # verschwinden, sobald jemand etwas sucht.
        self.bestand = QLabel("")
        self.bestand.setAccessibleName("Bestand und letzter Abruf")

        self.statusBar().addWidget(self.stand, 1)
        self.statusBar().addPermanentWidget(self.bestand)
        self.statusBar().addPermanentWidget(self.balken)

    def _menue(self) -> None:
        archiv = self.menuBar().addMenu("&Archiv")

        anlegen = QAction("Neues Archiv anlegen …", self)
        anlegen.setShortcut(QKeySequence.New)
        anlegen.triggered.connect(self._neues_archiv)
        archiv.addAction(anlegen)

        oeffnen = QAction("Archiv wechseln …", self)
        oeffnen.setShortcut(QKeySequence.Open)
        oeffnen.setStatusTip(
            "Zu einem anderen Archiv wechseln – etwa vom geschäftlichen "
            "zum privaten."
        )
        oeffnen.triggered.connect(self._archiv_waehlen)
        archiv.addAction(oeffnen)

        # Wer zwei Archive führt, wechselt ständig zwischen ihnen. Dafür
        # jedes Mal den Pfad zusammenzusuchen wäre Arbeit für nichts.
        self.zuletzt_menue = archiv.addMenu("Zuletzt benutzt")
        self._zuletzt_fuellen()

        archiv.addSeparator()
        # "Journal prüfen", nicht "Hash-Kette prüfen": Die Hash-Kette ist
        # das Mittel, das Journal die Sache. Wer den Menüpunkt sucht,
        # sucht nicht nach einem Verfahren, sondern nach der Antwort auf
        # die Frage, ob mit seinem Archiv alles in Ordnung ist.
        pruefen = QAction("Journal prüfen", self)
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

        post.addSeparator()
        # Mit der Zahl im Text: Ein eingescanntes PDF meldet sich nicht
        # von selbst. Wer nicht weiß, dass ein Teil seines Archivs
        # unauffindbar ist, sucht diesen Menüpunkt auch nicht.
        self.ocr_aktion = QAction("Eingescannte PDF lesen …", self)
        self.ocr_aktion.triggered.connect(self._texterkennung)
        post.addAction(self.ocr_aktion)

        ansicht = self.menuBar().addMenu("&Ansicht")
        zuruecksetzen = QAction("Fenster auf Standard zurücksetzen", self)
        zuruecksetzen.setStatusTip(
            "Größe und Aufteilung so, wie MailBurg das erste Mal aufging."
        )
        zuruecksetzen.triggered.connect(self._standardansicht)
        ansicht.addAction(zuruecksetzen)

        ansicht.addSeparator()
        hoch = QAction("Postfach nach oben", self)
        hoch.setShortcut("Ctrl+Up")
        hoch.triggered.connect(lambda: self.baum.verschieben(-1))
        ansicht.addAction(hoch)

        runter = QAction("Postfach nach unten", self)
        runter.setShortcut("Ctrl+Down")
        runter.triggered.connect(lambda: self.baum.verschieben(1))
        ansicht.addAction(runter)

        ansicht.addSeparator()
        merken = QAction("Eigene Ansicht speichern", self)
        merken.setStatusTip(
            "Die jetzige Größe und Aufteilung als eigene Ansicht ablegen."
        )
        merken.triggered.connect(self._ansicht_speichern)
        ansicht.addAction(merken)

        laden = QAction("Eigene Ansicht laden", self)
        laden.setStatusTip("Zur gespeicherten eigenen Ansicht zurückkehren.")
        laden.triggered.connect(self._ansicht_laden)
        ansicht.addAction(laden)

        suchen_menue = self.menuBar().addMenu("&Suchen")
        ausfuehrlich = QAction("Ausführlich suchen …", self)
        ausfuehrlich.setShortcut("Ctrl+F")
        ausfuehrlich.triggered.connect(self._suchmaske)
        suchen_menue.addAction(ausfuehrlich)

        hilfe = self.menuBar().addMenu("&Hilfe")
        handbuch = QAction("Handbuch …", self)
        handbuch.setShortcut("F1")
        handbuch.triggered.connect(lambda: self._handbuch())
        hilfe.addAction(handbuch)

        hilfe.addSeparator()
        # Die beiden häufigsten Fragen bekommen einen eigenen Weg, statt
        # den Anwender im Inhaltsverzeichnis suchen zu lassen. Sie führen
        # ins selbe Handbuch, nur gleich ans richtige Kapitel.
        suchhilfe = QAction("Suchsprache …", self)
        suchhilfe.triggered.connect(lambda: self._handbuch("suchen"))
        hilfe.addAction(suchhilfe)

        journalhilfe = QAction("Was das Journal ist …", self)
        journalhilfe.triggered.connect(lambda: self._handbuch("journal"))
        hilfe.addAction(journalhilfe)

        aufraeumen = QAction("Postfach aufräumen …", self)
        aufraeumen.triggered.connect(lambda: self._handbuch("aufraeumen"))
        hilfe.addAction(aufraeumen)

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
        self._bestand_zeigen()
        self._offene_pdf_zeigen()
        self._suchen()
        if hasattr(self, "zuletzt_menue"):
            # Das gerade geöffnete Archiv gehört nicht in die Liste der
            # anderen - man wechselt nicht dorthin, wo man schon ist.
            self._zuletzt_fuellen()

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

    def _zuletzt_fuellen(self) -> None:
        from mailburg.ui.app import zuletzt_benutzte

        self.zuletzt_menue.clear()
        andere = [
            p for p in zuletzt_benutzte()
            if self.archiv is None or p.resolve() != self.archiv.root.resolve()
        ]
        if not andere:
            leer = self.zuletzt_menue.addAction("(noch keine weiteren)")
            leer.setEnabled(False)
            return
        for pfad in andere:
            # Der Name des Archivs, nicht der Pfad: "Privatarchiv Familie"
            # sagt mehr als /mnt/usb-Hersteller_Portable_XXXXXXXX-0:0-part2.
            eintrag = self.zuletzt_menue.addAction(_archivname(pfad))
            eintrag.setStatusTip(str(pfad))
            eintrag.triggered.connect(
                lambda _geklickt=False, p=pfad: self._wechseln(p)
            )

    def _wechseln(self, pfad) -> None:
        from mailburg.ui.app import merken

        self._oeffnen(pfad)
        if self.archiv is not None:
            merken(pfad)
            self._zuletzt_fuellen()

    def _archiv_waehlen(self) -> None:
        gewaehlt = self._verzeichnis_waehlen("Archiv wechseln")
        if gewaehlt:
            self._wechseln(gewaehlt)

    def _verzeichnis_waehlen(self, titel: str, vorgabe=None):
        """Ein Verzeichnisdialog, der die angeschlossenen Platten kennt.

        Der Standarddialog startet im Benutzerverzeichnis und zeigt in der
        Seitenleiste nur die Lesezeichen des Dateimanagers. Ein Archiv
        liegt aber typischerweise gerade *nicht* dort, sondern auf einer
        externen Platte – die dann jedes Mal von Hand zusammengeklickt
        werden muss. Die Einrichtung bietet diese Orte längst an; hier
        fehlten sie.
        """
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QFileDialog

        from mailburg.core import orte

        dialog = QFileDialog(self, titel)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        # Nicht der Dialog des Systems: Nur den eigenen lässt Qt um
        # weitere Orte ergänzen.
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)

        seitenleiste = list(dialog.sidebarUrls())
        for ort in orte.vorschlagen():
            # Der Datenträger selbst, nicht der Vorschlagspfad darauf:
            # orte.vorschlagen() liefert, wo ein *neues* Archiv angelegt
            # würde. Diesen Ordner gibt es meist noch gar nicht, und ein
            # Lesezeichen ins Leere hilft niemandem.
            traeger = ort.pfad.parent
            if not traeger.is_dir():
                continue
            url = QUrl.fromLocalFile(str(traeger))
            if url not in seitenleiste:
                seitenleiste.append(url)
        dialog.setSidebarUrls(seitenleiste)

        # Dort anfangen, wo das jetzige Archiv liegt: Das zweite Archiv
        # steht meist daneben.
        start = vorgabe or (self.archiv.root.parent if self.archiv else None)
        if start is not None and Path(start).is_dir():
            dialog.setDirectory(str(start))

        if dialog.exec() and dialog.selectedFiles():
            return Path(dialog.selectedFiles()[0])
        return None

    # ------------------------------------------------------- Fenstergröße

    def _groesse_herstellen(self) -> None:
        """Stellt die Ansicht her, die der Anwender zuletzt eingestellt hat.

        Beim allerersten Start gibt es nichts herzustellen – dann gilt die
        Standardansicht.
        """
        from mailburg.ui.app import gemerktes

        stand = gemerktes()
        breite, hoehe = stand.get("breite"), stand.get("hoehe")

        if not (isinstance(breite, int) and isinstance(hoehe, int)):
            self._standardansicht(nur_aufbauen=True)
            return

        self.resize(breite, hoehe)
        if stand.get("maximiert"):
            self.showMaximized()

        for name, teiler in (("waagerecht", self.waagerecht),
                             ("senkrecht", self.senkrecht)):
            gespeichert = stand.get(name)
            if gespeichert:
                teiler.restoreState(QByteArray.fromBase64(gespeichert.encode()))

        kopf = stand.get("spalten")
        if kopf:
            # Erst wenn das Fenster seine Größe hat. Sonst rechnet der
            # Kopf mit der Anfangsbreite der Tabelle, und die Spalten
            # stehen zusammengedrängt, bis jemand am Fensterrand zieht.
            QTimer.singleShot(
                0,
                lambda: self.tabelle.horizontalHeader().restoreState(
                    QByteArray.fromBase64(kopf.encode())
                ),
            )

    def _ansicht_speichern(self) -> None:
        """Legt die jetzige Ansicht ausdrücklich ab.

        Gemerkt wird zwar ohnehin beim Schließen. Aber wer das Fenster
        gerade so hat, wie er es haben will, soll das festhalten können,
        ohne es dafür zu schließen – und ohne darauf zu vertrauen, dass
        beim Beenden schon alles gutgeht.
        """
        self._groesse_merken()
        self.stand.setText("Eigene Ansicht gespeichert.")

    def _ansicht_laden(self) -> None:
        """Kehrt zur gespeicherten eigenen Ansicht zurück."""
        from mailburg.ui.app import gemerktes

        if "breite" not in gemerktes():
            QMessageBox.information(
                self,
                "Noch keine eigene Ansicht",
                "Es ist noch keine eigene Ansicht gespeichert. Stellen Sie "
                "das Fenster so ein, wie Sie es möchten, und wählen Sie "
                "dann »Eigene Ansicht speichern«.",
            )
            return
        if self.isMaximized():
            self.showNormal()
        self._groesse_herstellen()
        self.stand.setText("Eigene Ansicht geladen.")

    def _standardansicht(self, nur_aufbauen: bool = False) -> None:  # noqa: ARG002
        """Die Ansicht, mit der MailBurg das erste Mal aufgeht.

        Ein Archiv lebt von der Übersicht: Postfächer links, Trefferliste
        und Vorschau rechts übereinander. Deshalb großzügig – ein knappes
        Fenster zwingt beim ersten Blick zum Ziehen an den Rändern, bevor
        man überhaupt etwas erkennt.

        Die Verhältnisse sind Anteile, keine festen Pixel: Auf einem
        kleinen Bildschirm wäre eine feste Baumbreite die halbe Ansicht,
        auf einem großen ein Streifen.
        """
        if self.isMaximized():
            self.showNormal()

        flaeche = self.screen().availableGeometry()
        # Nicht ganz bis an den Rand: Ein Fenster, das den Bildschirm
        # ausfüllt, sieht aus wie ein Fehler, wenn es keiner ist.
        self.resize(
            min(1600, int(flaeche.width() * 0.9)),
            min(1000, int(flaeche.height() * 0.9)),
        )
        self.move(flaeche.center() - self.rect().center())

        # Verhältniszahlen, nicht Pixel: ``resize`` wirkt nicht sofort -
        # unter Wayland muss der Compositor die neue Größe erst
        # bestätigen. Wer hier ``self.width()`` liest, rechnet mit der
        # alten Breite, und die Aufteilung bleibt sichtbar falsch. Ein
        # QSplitter verteilt die Zahlen ohnehin nur nach ihrem Verhältnis
        # zueinander, die Summe muss nichts bedeuten.
        self.waagerecht.setSizes([
            round(BAUMANTEIL * 1000), round((1 - BAUMANTEIL) * 1000),
        ])
        self.senkrecht.setSizes([
            round(TREFFERANTEIL * 1000), round((1 - TREFFERANTEIL) * 1000),
        ])
        self._spalten_einrichten()
        self._baumspalten_einrichten()

    def _groesse_merken(self) -> None:
        from mailburg.ui.app import merken_unter

        # Breite und Höhe als schlichte Zahlen, nicht als saveGeometry().
        # Unter Wayland darf ein Fenster seine Position nicht kennen; Qt
        # schreibt dort Platzhalter, und restoreGeometry() stellt sie
        # anschließend gehorsam wieder her. Herauskam immer dasselbe
        # 720x720 an Position 40,40 - die eingestellte Größe war nie
        # gespeichert. Die Position überlassen wir dem Fenstermanager;
        # unter Wayland ist das ohnehin dessen Sache.
        gemessen = self.normalGeometry().size()
        merken_unter("breite", gemessen.width())
        merken_unter("hoehe", gemessen.height())
        merken_unter("maximiert", self.isMaximized())
        merken_unter("waagerecht",
                     bytes(self.waagerecht.saveState().toBase64()).decode())
        merken_unter("senkrecht",
                     bytes(self.senkrecht.saveState().toBase64()).decode())
        merken_unter(
            "spalten",
            bytes(self.tabelle.horizontalHeader().saveState().toBase64()).decode(),
        )

    def _baumspalten_einrichten(self) -> None:
        """Drei Viertel für die Namen, ein Viertel für die Zahlen.

        Die Namen sind das Lange: Mailadressen und verschachtelte
        Ordnerpfade wie ``Folders/Max.Muster/Entwicklung``. Die
        Zahlen brauchen kaum Platz, und eine hälftige Teilung schnitte
        genau das ab, wonach man sucht.
        """
        kopf = self.baum.header()
        kopf.setSectionResizeMode(0, QHeaderView.Interactive)
        kopf.setSectionResizeMode(1, QHeaderView.Interactive)
        breite = max(self.baum.width(), self.baum.minimumWidth())
        self.baum.setColumnWidth(0, int(breite * 0.75))
        self.baum.setColumnWidth(1, breite - int(breite * 0.75))

    def _spalten_einrichten(self) -> None:
        """Legt fest, welche Spalte sich wie verhält.

        Ausdrücklich über die Verhaltensregeln und nicht über einen
        gespeicherten Zustand: ``saveState`` hält auch die damalige Breite
        der Tabelle fest. Wird so ein Zustand wiederhergestellt, während
        das Fenster noch seine Anfangsgröße hat, bekommen alle Spalten die
        Breiten von damals – und der Betreff dehnt sich erst beim nächsten
        Ziehen am Fensterrand wieder aus. Genau so sah es aus: schmale
        Spalten, abgeschnittene Betreffs, rechts daneben freie Fläche.
        """
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        kopf.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        kopf.setSectionResizeMode(2, QHeaderView.Interactive)
        # Der Betreff bekommt, was übrig bleibt. Er ist die einzige Spalte,
        # bei der jedes zusätzliche Zeichen zählt.
        kopf.setSectionResizeMode(3, QHeaderView.Stretch)
        kopf.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tabelle.setColumnWidth(2, 220)

    def _bestand_zeigen(self) -> None:
        """Wie viel im Archiv liegt und wann zuletzt geholt wurde.

        Zusammen beantwortet das die Frage, die sich vor jedem Aufräumen
        im Mailprogramm stellt: *Ist mein Archiv auf dem Stand?* Ein
        Archiv, dem man das nicht ansieht, muss man glauben.
        """
        if self.archiv is None:
            self.bestand.setText("")
            return

        from mailburg.core.sync import Abrufzustand

        anzahl = f"{self.archiv.index.count():,}".replace(",", ".")
        wann = _abrufzeit(Abrufzustand(self.archiv.uuid).zuletzt)
        self.bestand.setText(f"{anzahl} Mails im Archiv · {wann}")

    def _reihenfolge_merken(self) -> None:
        from mailburg.ui.app import merken_unter

        merken_unter("postfachreihenfolge", self.baum.reihenfolge())

    def _baum_fuellen(self) -> None:
        self.baum.clear()
        if self.archiv is None:
            return

        from mailburg.ui.app import gemerktes

        alle = QTreeWidgetItem(["Alle Postfächer", ""])
        alle.setData(0, Qt.UserRole, "")
        self.baum.addTopLevelItem(alle)

        # Angezeigt wird die Mailadresse, nicht der frei gewählte Name.
        # "Kontakt" sagt bei drei Postfächern auf demselben Server nichts;
        # kontakt@example.org lässt keinen Zweifel, welches gemeint ist.
        # Gesucht wird weiterhin über den Namen - der steht so im Archiv.
        adressen = {k.name: k.benutzer for k in Kontenliste().konten}

        # Die selbst gewählte Reihenfolge zuerst, alles Übrige dahinter -
        # ein neu eingerichtetes Postfach soll auftauchen und nicht
        # verschwinden, nur weil es beim Sortieren noch nicht dabei war.
        gewuenscht = gemerktes().get("postfachreihenfolge", [])
        eintraege = sorted(
            self.archiv.index.accounts(),
            key=lambda z: (
                gewuenscht.index(z[0]) if z[0] in gewuenscht else len(gewuenscht),
                z[0],
                z[1],
            ),
        )

        konten: dict[str, QTreeWidgetItem] = {}
        for konto, ordner, anzahl in eintraege:
            if konto not in konten:
                # Fällt ein Postfach später aus der Liste, bleiben seine
                # Mails im Archiv. Dann muss der Name genügen.
                eintrag = QTreeWidgetItem([adressen.get(konto, konto), ""])
                # Der Kontoname, nicht die Anzeige: Die Reihenfolge soll
                # halten, auch wenn sich die Mailadresse einmal ändert.
                eintrag.setData(0, Qt.UserRole + 1, konto)
                eintrag.setData(0, Qt.UserRole, f"konto:{_quoten(konto)}")
                self.baum.addTopLevelItem(eintrag)
                konten[konto] = eintrag
            unter = QTreeWidgetItem([ordner, f"{anzahl:,}".replace(",", ".")])
            unter.setData(1, Qt.UserRole, anzahl)
            unter.setData(
                0, Qt.UserRole, f"konto:{_quoten(konto)} ordner:{_quoten(ordner)}"
            )
            konten[konto].addChild(unter)

        # Gezählt werden Mails, nicht Fundorte. Die Ordnerzahlen darüber
        # zu addieren wäre falsch: Bei Proton trägt jede Mail neben ihrem
        # Ordner noch Etiketten, und jedes Etikett ist ein weiterer
        # Fundort. Die Summe ergäbe eine Zahl, die es nicht gibt - und
        # sie widerspräche der Gesamtzahl in der Statuszeile.
        summen = self.archiv.index.account_totals()
        for konto, eintrag in konten.items():
            anzahl = summen.get(konto, 0)
            eintrag.setText(1, f"{anzahl:,}".replace(",", "."))
            if anzahl != sum(
                eintrag.child(i).data(1, Qt.UserRole) or 0
                for i in range(eintrag.childCount())
            ):
                eintrag.setToolTip(
                    1,
                    "Mails, nicht Fundorte: Dieselbe Mail kann in mehreren "
                    "Ordnern liegen – bei Proton etwa im Ordner und unter "
                    "jedem ihrer Etiketten.",
                )
        alle.setText(1, f"{self.archiv.index.count():,}".replace(",", "."))

        alle.setSelected(True)
        self.baum.expandItem(alle)

    # -------------------------------------------------------------- Suchen

    def _tippen(self) -> None:
        if self.suchfeld.text().strip():
            self.suchmeldung.setText("MailBurg sucht …")
        self.tipp_uhr.start(TIPPAUSE)

    def _suchen(self) -> None:
        self.tipp_uhr.stop()
        if self.archiv is None:
            return

        ausdruck = self.suchfeld.text().strip()
        try:
            self.modell.suchen(ausdruck)
        except QueryError as exc:
            self._suchmeldung_setzen(f"Der Suchausdruck stimmt nicht: {exc}", False)
            return
        except Exception as exc:  # noqa: BLE001
            self._suchmeldung_setzen(f"Die Suche ist gescheitert: {exc}", False)
            return

        self.vorschau.leeren()
        anzahl = f"{self.modell.gesamt:,}".replace(",", ".")

        if not ausdruck:
            # Ohne Suchausdruck ist nichts gesucht worden; dann steht dort
            # auch kein Ergebnis, sondern gar nichts.
            self.suchmeldung.setText("")
            self.stand.setText(
                f"{anzahl} Mails" if self.modell.gesamt
                else "Das Archiv ist noch leer."
            )
            return

        if self.modell.gesamt:
            wort = "Treffer" if self.modell.gesamt > 1 else "Treffer"
            self._suchmeldung_setzen(f"MailBurg hat {anzahl} {wort}.", True)
        else:
            self._suchmeldung_setzen(
                "MailBurg hat nichts gefunden. F1 erklärt die Suchsprache.",
                False,
            )
        self.stand.setText(f"{anzahl} Treffer")

    def _suchmeldung_setzen(self, text: str, fuendig: bool) -> None:
        """Schreibt das Suchergebnis hin – deutlich genug, um es zu sehen.

        Fett, weil es sonst zwischen Suchfeld und Trefferliste untergeht.
        Farbe nur, wenn nichts gefunden wurde: Ein Treffer ist der
        Normalfall und braucht kein Signal, ein Fehlschlag dagegen schon –
        sonst sucht jemand weiter in einer Liste, die von der vorigen
        Suche stammt.
        """
        farbe = "" if fuendig else f"color: {farben.schlecht()};"
        self.suchmeldung.setText(f"<span style='{farbe}'><b>{text}</b></span>")

    def _ordner_gewaehlt(self, eintrag: QTreeWidgetItem) -> None:
        vorgabe = eintrag.data(0, Qt.UserRole) or ""
        self.suchfeld.setText(vorgabe)
        self._suchen()

    def _trefferminue(self, stelle) -> None:
        from PySide6.QtWidgets import QMenu

        treffer = self._gewaehlter_treffer()
        if treffer is None:
            return

        menue = QMenu(self)
        lesen = menue.addAction("Öffnen")
        lesen.triggered.connect(self._oeffnen_zum_lesen)
        menue.addSeparator()
        zurueck = menue.addAction("Im Postfach wiederherstellen …")
        zurueck.triggered.connect(self._zuruecklegen)
        speichern = menue.addAction("Als Datei speichern …")
        speichern.triggered.connect(self._als_datei)
        menue.exec(self.tabelle.viewport().mapToGlobal(stelle))

    def _oeffnen_zum_lesen(self) -> None:
        from mailburg.ui.lesefenster import oeffnen

        treffer = self._gewaehlter_treffer()
        if treffer is not None:
            oeffnen(treffer, self.archiv, self)

    def _gewaehlter_treffer(self):
        stellen = self.tabelle.selectionModel().selectedRows()
        if not stellen or self.archiv is None:
            return None
        return self.modell.treffer_bei(stellen[0].row())

    def _rohdaten(self, treffer) -> bytes | None:
        """Die Nachricht, so wie sie archiviert wurde – Byte für Byte."""
        try:
            return self.archiv.store.get(treffer.hash, treffer.bucket)
        except OSError as exc:
            QMessageBox.warning(
                self, "Nachricht nicht lesbar",
                f"Die Datei zu dieser Nachricht ließ sich nicht lesen.\n\n"
                f"{exc}\n\nLiegt das Archiv auf einer externen Platte, ist "
                f"sie vielleicht abgezogen. »Archiv → Journal prüfen« sagt, "
                f"ob mehr fehlt.",
            )
            return None

    def _zuruecklegen(self) -> None:
        from mailburg.ui.zurueck import Zurueckdialog

        treffer = self._gewaehlter_treffer()
        if treffer is None:
            return
        roh = self._rohdaten(treffer)
        if roh is not None:
            Zurueckdialog(roh, treffer.subject, self).exec()

    def _als_datei(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        from mailburg.core import rueckgabe

        treffer = self._gewaehlter_treffer()
        if treffer is None:
            return
        roh = self._rohdaten(treffer)
        if roh is None:
            return

        vorschlag = _dateiname(treffer.subject)
        ziel, _ = QFileDialog.getSaveFileName(
            self, "Nachricht speichern",
            str(Path.home() / vorschlag),
            "E-Mail-Datei (*.eml)",
        )
        if not ziel:
            return
        try:
            abgelegt = rueckgabe.als_datei(roh, Path(ziel))
        except OSError as exc:
            QMessageBox.warning(self, "Nicht gespeichert", str(exc))
            return
        self.stand.setText(f"Gespeichert: {abgelegt}")

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
        self._baum_fuellen()
        self._bestand_zeigen()
        self._suchen()

        # Wer selbst auf "Jetzt abrufen" geklickt hat, wartet auf eine
        # Antwort. Der Abruf im Hintergrund meldet sich dagegen nie - er
        # hat kein Fenster und soll auch keines aufmachen.
        if fehler:
            # Dann eben *nicht* "alle Mails sind im Archiv". In einem
            # Archivprogramm ist die falsche Entwarnung der teuerste
            # Fehler: Wer sie glaubt, räumt sein Postfach auf.
            QMessageBox.warning(
                self,
                "Nicht alle Postfächer erreichbar",
                "Diese Postfächer konnten nicht abgerufen werden – ihre "
                "Mails fehlen also noch:\n\n" + "\n\n".join(fehler)
                + "\n\nBitte räumen Sie diese Postfächer im Mailprogramm "
                "noch nicht auf.",
            )
            return

        QMessageBox.information(
            self,
            "Abruf abgeschlossen",
            "Alle Mails sind im Archiv."
            + (f"\n\n{neu} neu hinzugekommen." if neu else
               "\n\nEs war nichts Neues da."),
        )

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
            "Protokollkette: "
            + ("unversehrt" if bericht["chain_ok"] else "BESCHÄDIGT"),
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

    def _texterkennung(self) -> None:
        from mailburg.ui.texterkennung import Texterkennungsdialog

        if self.archiv is None:
            return
        Texterkennungsdialog(self.archiv, self).exec()
        self._offene_pdf_zeigen()
        self._suchen()

    def _offene_pdf_zeigen(self) -> None:
        """Schreibt die Zahl wartender PDF in den Menüeintrag."""
        if self.archiv is None or not hasattr(self, "ocr_aktion"):
            return
        from mailburg.core.erkennung import Warteschlange

        try:
            offen = Warteschlange(self.archiv.index).anzahl()
        except Exception:  # noqa: BLE001 – eine Zahl im Menü ist kein Grund zu scheitern
            return
        self.ocr_aktion.setText(
            f"Eingescannte PDF lesen … ({offen})" if offen
            else "Eingescannte PDF lesen …"
        )
        self.ocr_aktion.setEnabled(offen > 0)
        self.ocr_aktion.setStatusTip(
            f"{offen} eingescannte PDF sind noch nicht durchsuchbar."
            if offen else "Alle lesbaren PDF sind durchsuchbar."
        )

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

    def _handbuch(self, kapitel: str = "ueberblick") -> None:
        from mailburg.ui.hilfe import oeffnen

        oeffnen(self, kapitel)

    def closeEvent(self, ereignis) -> None:
        # Hier wird ausdrücklich *nichts* gemerkt. Die eigene Ansicht legt
        # ab, wer sie ablegen will - über "Ansicht > Eigene Ansicht
        # speichern". Würde das Schließen automatisch mitschreiben,
        # überschriebe jedes versehentliche Verziehen kurz vor Feierabend
        # die Ansicht, die jemand sich eingerichtet hat. Und "auf Standard
        # zurücksetzen" hätte sie gleich mit gelöscht.
        # Nicht nur den eigenen Abruf: Auch Prüfungen aus Dialogen können
        # noch laufen, und ein Faden ohne Fenster beendet das Programm.
        alle_beenden(3000)
        if self.laeufer is not None:
            self.laeufer.warten(3000)
        if self.archiv is not None:
            self.archiv.close()
        super().closeEvent(ereignis)


class Postfachbaum(QTreeWidget):
    """Der Baum links – mit frei verschiebbaren Postfächern.

    Verschoben werden dürfen nur die Postfächer, nicht ihre Ordner. Die
    Ordner stehen alphabetisch, und das ist auch richtig so: Ihre
    Reihenfolge kommt vom Mailserver und sagt nichts. Welches Postfach
    einem am wichtigsten ist, weiß dagegen nur der Anwender.
    """

    reihenfolge_geaendert = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dragMoveEvent(self, ereignis) -> None:
        if not self._erlaubt(ereignis):
            ereignis.ignore()
            return
        super().dragMoveEvent(ereignis)

    def dropEvent(self, ereignis) -> None:
        if not self._erlaubt(ereignis):
            ereignis.ignore()
            return
        super().dropEvent(ereignis)
        self.reihenfolge_geaendert.emit()

    def _erlaubt(self, ereignis) -> bool:
        """Nur ein Postfach, nur zwischen zwei andere.

        Ohne diese Prüfung ließe sich ein Postfach in ein anderes
        hineinziehen oder ein Ordner aus seinem Postfach heraus. Beides
        ergäbe einen Baum, der etwas behauptet, was im Archiv nicht steht.
        """
        gezogen = self.currentItem()
        if gezogen is None or gezogen.parent() is not None:
            return False
        # Auf einem Element abzulegen hieße "hineinlegen"; erlaubt ist nur
        # davor und dahinter.
        if self.dropIndicatorPosition() not in (
            QAbstractItemView.AboveItem, QAbstractItemView.BelowItem
        ):
            return False
        ziel = self.itemAt(ereignis.position().toPoint())
        return ziel is None or ziel.parent() is None

    def verschieben(self, richtung: int) -> None:
        """Rückt das gewählte Postfach eine Stelle – für die Tastatur.

        Ziehen mit der Maus ist für viele keine Option: Wer mit der
        Tastatur arbeitet oder eine Sprachsteuerung nutzt, kommt daran
        nicht heran. Eine Anordnung, die sich nur ziehen lässt, ist
        deshalb keine.
        """
        eintrag = self.currentItem()
        if eintrag is None or eintrag.parent() is not None:
            return
        stelle = self.indexOfTopLevelItem(eintrag)
        # Stelle 0 ist "Alle Postfächer" und bleibt oben.
        neu = stelle + richtung
        if stelle < 1 or not 1 <= neu < self.topLevelItemCount():
            return
        ausgeklappt = eintrag.isExpanded()
        self.takeTopLevelItem(stelle)
        self.insertTopLevelItem(neu, eintrag)
        eintrag.setExpanded(ausgeklappt)
        self.setCurrentItem(eintrag)
        self.reihenfolge_geaendert.emit()

    def reihenfolge(self) -> list[str]:
        """Die Postfächer in ihrer jetzigen Reihenfolge."""
        return [
            self.topLevelItem(i).data(0, Qt.UserRole + 1)
            for i in range(1, self.topLevelItemCount())
            if self.topLevelItem(i).data(0, Qt.UserRole + 1)
        ]


def _dateiname(betreff: str) -> str:
    """Ein Dateiname aus dem Betreff, der auf jedem System zulässig ist.

    Windows verbietet ``\\ / : * ? " < > |``, und ein Doppelpunkt steht in
    fast jedem Betreff mit "Re:" oder "AW:". Wer das nicht ersetzt,
    bekommt beim Speichern eine Fehlermeldung statt einer Datei.
    """
    sauber = "".join(
        "-" if z in '\\/:*?"<>|' else z for z in (betreff or "Nachricht")
    ).strip()
    return (sauber[:80] or "Nachricht") + ".eml"


def _archivname(pfad) -> str:
    """Der Anzeigename eines Archivs, ohne es dafür zu öffnen."""
    import json

    try:
        meta = json.loads((pfad / "archive.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return pfad.name
    return meta.get("name") or pfad.name


def _abrufzeit(iso: str) -> str:
    """Formt den Zeitpunkt des letzten Abrufs in etwas Lesbares um.

    »heute 21:14« sagt mehr als »2026-08-26T21:14:03+02:00« – und der
    Anwender soll auf einen Blick sehen, ob das lange her ist.
    """
    if not iso:
        return "noch nicht abgerufen"
    try:
        wann = datetime.fromisoformat(iso)
    except ValueError:
        return "letzter Abruf unbekannt"

    heute = datetime.now(wann.tzinfo).date()
    tag = wann.date()
    if tag == heute:
        wortlaut = "heute"
    elif (heute - tag).days == 1:
        wortlaut = "gestern"
    else:
        wortlaut = datum.tag(wann)
    return f"zuletzt abgerufen: {wortlaut} {wann:%H:%M}"


def _quoten(wert: str) -> str:
    """Setzt einen Wert in Anführungszeichen, wenn er Leerzeichen enthält."""
    return f'"{wert}"' if " " in wert else wert
