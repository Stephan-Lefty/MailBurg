"""Das Hauptfenster: Ordner, Trefferliste, Vorschau.

Dreispaltig, wie man es von Mailprogrammen kennt – wer MailBurg zum ersten
Mal öffnet, soll sich nicht erst zurechtfinden müssen.

Die Suchleiste steht oben und ist der eigentliche Einstieg. Wer nur
``rechnung`` tippt, sucht überall; alles Weitere sind Einschränkungen, die
man dazunehmen kann, aber nicht muss.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
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
#: Die Spalte mit dem Datum der Nachricht. Nach ihr wird beim Öffnen
#: sortiert – siehe :meth:`Hauptfenster._neueste_zuerst`.
SPALTE_DATUM = 1

BAUMANTEIL = 0.20
TREFFERANTEIL = 0.42
from mailburg.core.accounts import Kontenliste
from mailburg.core.archive import Archive, ArchiveError, ArchiveLocked
from mailburg.core.index import IndexOutdated
from mailburg.core.journal import JournalBeschaedigt
from mailburg.core.krypto import KryptoFehler
from mailburg.search.query import QueryError
from mailburg.ui import datum, farben
from mailburg.ui import farben
from mailburg.ui.arbeit import Abruflauf, Läufer, alle_beenden
from mailburg.ui.modelle import Trefferliste
from mailburg.ui.vorschau import Mailvorschau

#: So lange wird nach dem letzten Tastendruck gewartet, bevor gesucht wird.
#: Ohne diese Pause liefe bei jedem Buchstaben eine Abfrage – bei einem
#: großen Archiv wäre das Tippen dann zäh.
TIPPAUSE = 250

#: So oft frischt der Postfachbaum auf, während ein Abruf läuft.
#:
#: **Warum es das überhaupt gibt.** Der Baum wurde bis dahin erst
#: aufgebaut, wenn der Abruf *fertig* war. Bei sechstausend Mails hieß
#: das: eine Viertelstunde lang ein leerer Baum und »0 Mails im Archiv ·
#: noch nicht abgerufen« – während unten links längst »2800 geholt«
#: stand. Zwei Anzeigen im selben Fenster, die einander widersprachen.
#: Ein Anwender hat genau das gemeldet: Er war sich nicht sicher, ob das
#: Programm etwas Sinnvolles tut.
#:
#: Drei Sekunden, nicht bei jeder Mail: Der Baum wird dabei vollständig
#: neu aufgebaut, und das kostet bei vielen Ordnern spürbar.
MITWACHSEN = 3000


class Hauptfenster(QMainWindow):
    """Das Fenster, in dem ein Archiv durchsucht und gefüllt wird."""

    def __init__(self, archiv_pfad: Path) -> None:
        super().__init__()
        self.archiv: Archive | None = None
        #: Das Passwort des offenen Archivs, solange es offen ist.
        #: Gebraucht fuer Arbeitsgaenge, die es selbst noch einmal
        #: oeffnen - der Neuaufbau etwa laeuft in einem eigenen Faden.
        self._geheimnis = ""
        self._geheimnis_fuer: Path | None = None
        self.laeufer: Läufer | None = None
        self.ocr_laeufer: Läufer | None = None
        #: Ob gerade ein Suchindex neu gebaut wird. ``ui/app.py`` fragt
        #: danach: Waehrend des Aufbaus ist ``archiv`` None, und das sah
        #: dort bis zum 2026-08-31 aus wie "Archiv nicht zu oeffnen" -
        #: das Programm beendete sich, kaum dass jemand "Ja" geklickt
        #: hatte. Das Fenster ging einfach zu.
        self.baut_auf = False

        from PySide6.QtWidgets import QApplication

        self._grundgroesse = QApplication.font().pointSizeF()
        # **Menüs haben ihre eigene Schriftgröße.** Qt führt neben der
        # Anwendungsschrift eine je Widgetklasse, und der Stil setzt sie
        # unabhängig: Unter Breeze steht die Anwendung auf 9 pt und ein
        # Menü auf 14. Wer beide auf denselben Wert zöge, machte die
        # Menüs beim Vergrößern erst einmal kleiner.
        #
        # Deshalb hier die Ausgangsgrößen merken und später *relativ*
        # verschieben - jede Klasse um dieselbe Zahl Punkte.
        self._grundgroessen = {
            klasse: QApplication.font(klasse).pointSizeF()
            for klasse in ("QMenu", "QMenuBar", "QToolTip")
        }
        self.schriftstufe = 0

        self.setWindowTitle(APP_NAME)

        self._aufbauen()
        self._menue()
        # Erst nach dem Aufbau: Wiederhergestellt werden auch die
        # Aufteilungen, und die gibt es vorher noch nicht.
        self._groesse_herstellen()

        from mailburg.core.einstellungen import gemerktes

        stufe = gemerktes().get("schriftstufe", 0)
        if isinstance(stufe, int) and stufe:
            self._schrift_setzen(stufe)

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

        # Läuft nur während eines Abrufs. Lesen und Schreiben zugleich
        # ist zulässig, weil der Index im WAL-Modus liegt – der Kommentar
        # in core/index.py sagt das seit jeher, abgeholt hat es niemand.
        self.mitwachsen = QTimer(self)
        self.mitwachsen.timeout.connect(self._mitwachsen)

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
        self.tabelle.horizontalHeader().setSortIndicator(
            SPALTE_DATUM, Qt.DescendingOrder
        )

        self._spalten_einrichten()
        self._baumspalten_einrichten()
        self._kanten_setzen()

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

        # Rechts daneben, auf derselben Höhe: Was im Hintergrund läuft,
        # gehört dorthin, wo der Anwender ohnehin hinschaut - und nicht
        # in die Statuszeile am unteren Rand, die beim Suchen niemand
        # ansieht.
        self.ocr_hinweis = QLabel("")
        self.ocr_hinweis.setTextFormat(Qt.RichText)
        self.ocr_hinweis.setAccessibleName("Läuft im Hintergrund")
        self.ocr_hinweis.setContentsMargins(2, 2, 2, 4)

        meldungszeile = QHBoxLayout()
        meldungszeile.addWidget(self.suchmeldung, 1)
        meldungszeile.addWidget(self.ocr_hinweis)

        # **Suchfeld und Trefferzeile sind ein Bereich, nicht zwei.**
        # Sie gehören zusammen: oben die Frage, darunter die Antwort.
        # Bisher standen beide auf derselben Fläche wie der Inhalt
        # darunter, und der Blick fand keinen Anfang.
        #
        # Der Name hängt an der Regel in ``farben.bereichsrahmen()``.
        self.suchbereich = QWidget()
        self.suchbereich.setObjectName("suchbereich")
        suchaufbau = QVBoxLayout(self.suchbereich)
        suchaufbau.setContentsMargins(6, 6, 6, 2)
        suchaufbau.setSpacing(2)
        suchaufbau.addWidget(self.suchfeld)
        suchaufbau.addLayout(meldungszeile)

        aufbau.addWidget(self.suchbereich)
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
        sichern = QAction("Archiv sichern …", self)
        sichern.setStatusTip(
            "Das ganze Archiv in eine Datei packen – für die Cloud oder "
            "eine zweite Platte."
        )
        sichern.triggered.connect(self._sichern)
        archiv.addAction(sichern)

        uebernehmen = QAction("Sicherung importieren …", self)
        uebernehmen.setStatusTip(
            "Die Mails einer Sicherung in das geöffnete Archiv aufnehmen."
        )
        uebernehmen.triggered.connect(self._sicherung_uebernehmen)
        archiv.addAction(uebernehmen)

        zurueckholen = QAction("Sicherung in neues Archiv …", self)
        zurueckholen.setStatusTip(
            "Aus einer Sicherung ein eigenes, neues Archiv machen."
        )
        zurueckholen.triggered.connect(self._zurueckholen)
        archiv.addAction(zurueckholen)

        archiv.addSeparator()
        # "Journal prüfen", nicht "Hash-Kette prüfen": Die Hash-Kette ist
        # das Mittel, das Journal die Sache. Wer den Menüpunkt sucht,
        # sucht nicht nach einem Verfahren, sondern nach der Antwort auf
        # die Frage, ob mit seinem Archiv alles in Ordnung ist.
        self.doku_aktion = QAction("Verfahrensdokumentation …", self)
        self.doku_aktion.setStatusTip(
            "Einen Entwurf nach GoBD erzeugen – den technischen Teil füllt "
            "MailBurg aus, den organisatorischen Sie."
        )
        self.doku_aktion.triggered.connect(self._verfahrensdoku)
        archiv.addAction(self.doku_aktion)

        self.auskunft_aktion = QAction("Auskunft nach DSGVO …", self)
        self.auskunft_aktion.setStatusTip(
            "Alles zusammenstellen, was zu einer Person im Archiv liegt – "
            "wenn jemand nach Artikel 15 DSGVO fragt."
        )
        self.auskunft_aktion.triggered.connect(self._auskunft)
        archiv.addAction(self.auskunft_aktion)

        archiv.addSeparator()

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
        # **Gleich unter »Jetzt abrufen«, nicht weiter unten.** Beides
        # bringt Post ins Archiv; der eine Weg über den Server, der
        # andere von der Platte. Bis zum 2026-09-03 gab es diesen Punkt
        # gar nicht – die Quellen konnte MailBurg von Anfang an, aber nur
        # über die Kommandozeile. Ein Anwender hat sich gewünscht, was
        # längst da war: Er hat es nicht gefunden.
        self.einlesen_aktion = QAction("Lokale Mailordner einlesen …", self)
        self.einlesen_aktion.setStatusTip(
            "Post aus Dateien auf dieser Platte übernehmen – "
            "Thunderbird-Profile, Maildir-Ordner (auch von Evolution), "
            "MBOX-Dateien."
        )
        self.einlesen_aktion.triggered.connect(self._einlesen)
        post.addAction(self.einlesen_aktion)

        # **Und gleich darunter der Weg hinaus.** Hinein und hinaus
        # gehören nebeneinander; wer das eine findet, findet das andere.
        # Gewünscht am 2026-09-03: »Ich würde mir ein Restore wünschen,
        # wie in MailStore Home.«
        self.rueckspielen_aktion = QAction("Ins Dateisystem zurückspielen …", self)
        self.rueckspielen_aktion.setStatusTip(
            "Viele Nachrichten auf einmal als Dateien wegschreiben – als "
            "Maildir, MBOX oder einzelne .eml. Das Archiv bleibt "
            "unverändert."
        )
        self.rueckspielen_aktion.triggered.connect(self._zurueckspielen)
        post.addAction(self.rueckspielen_aktion)

        post.addSeparator()
        # Mit der Zahl im Text: Ein eingescanntes PDF meldet sich nicht
        # von selbst. Wer nicht weiß, dass ein Teil seines Archivs
        # unauffindbar ist, sucht diesen Menüpunkt auch nicht.
        self.ocr_aktion = QAction("Eingescannte PDF lesen …", self)
        self.ocr_aktion.triggered.connect(self._texterkennung)
        post.addAction(self.ocr_aktion)

        post.addSeparator()
        # **Nur im Geschäftsarchiv.** In einem Privatarchiv gibt es keine
        # Aufbewahrungsfristen; ein Menüpunkt, der dort nichts bewirkt,
        # wäre eine Einladung, sich über etwas Gedanken zu machen, das
        # keine Rolle spielt.
        self.einstufen_aktion = QAction("Aufbewahrung festlegen …", self)
        self.einstufen_aktion.setStatusTip(
            "Die gefundenen Mails als Buchungsbeleg, Handelsbrief oder "
            "privat einordnen – davon hängt ab, wie lange sie vor dem "
            "Löschen geschützt sind."
        )
        self.einstufen_aktion.triggered.connect(self._einstufen)
        post.addAction(self.einstufen_aktion)

        # **Neben dem Einstufen von Hand, nicht darunter.** Beides
        # beantwortet dieselbe Frage – wozu zählt diese Post –, nur das
        # eine rückblickend und das andere im Voraus.
        self.regeln_aktion = QAction("Beim Aufnehmen einstufen …", self)
        self.regeln_aktion.setStatusTip(
            "Regeln, die eingehende Post von selbst einordnen – etwa "
            "alles aus dem Vereinsordner als privat, damit es nicht "
            "unter Aufbewahrungsfristen fällt, die dafür nicht gelten."
        )
        self.regeln_aktion.triggered.connect(self._regeln)
        post.addAction(self.regeln_aktion)

        # Einstellungen sind kein Handeln: Was hier steht, gilt fort,
        # bis es jemand ändert. Deshalb ein eigenes Menü - und deshalb
        # weit rechts, kurz vor der Hilfe: Was man täglich braucht,
        # steht links, was man einmal einstellt, rechts.
        suchen_menue = self.menuBar().addMenu("&Suchen")
        ausfuehrlich = QAction("Ausführlich suchen …", self)
        ausfuehrlich.setShortcut("Ctrl+F")
        ausfuehrlich.triggered.connect(self._suchmaske)
        suchen_menue.addAction(ausfuehrlich)

        ansicht = self.menuBar().addMenu("&Ansicht")
        zuruecksetzen = QAction("Fenster auf Standard zurücksetzen", self)
        zuruecksetzen.setStatusTip(
            "Größe und Aufteilung so, wie MailBurg das erste Mal aufging."
        )
        zuruecksetzen.triggered.connect(self._standardansicht)
        ansicht.addAction(zuruecksetzen)

        ansicht.addSeparator()
        groesser = QAction("Schrift größer", self)
        # **Keine Doppelung.** ``ZoomIn`` ist auf dieser Plattform
        # bereits Strg++; wer es zusätzlich von Hand einträgt, gibt
        # derselben Aktion dasselbe Kürzel zweimal. Qt hält das für
        # mehrdeutig und führt dann *keines* von beiden aus – die
        # Schrift ließ sich per Tastatur überhaupt nicht mehr ändern.
        #
        # Am 2026-08-31 von Stephan gemeldet: »STRG ++ vergrößert nix.«
        # Der Menüeintrag zeigte das Kürzel brav an, und genau deshalb
        # sucht man den Fehler zuletzt dort.
        #
        # Strg+= kommt dazu, weil das Pluszeichen auf vielen Belegungen
        # nur mit Umschalt zu erreichen ist.
        groesser.setShortcuts(_ohne_doppelte([
            QKeySequence.ZoomIn, QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")
        ]))
        groesser.triggered.connect(lambda: self._schrift_aendern(+1))
        ansicht.addAction(groesser)

        kleiner = QAction("Schrift kleiner", self)
        kleiner.setShortcuts(_ohne_doppelte([
            QKeySequence.ZoomOut, QKeySequence("Ctrl+-")
        ]))
        kleiner.triggered.connect(lambda: self._schrift_aendern(-1))
        ansicht.addAction(kleiner)

        normal = QAction("Schrift zurücksetzen", self)
        normal.setShortcut(QKeySequence("Ctrl+0"))
        normal.triggered.connect(lambda: self._schrift_setzen(0))
        ansicht.addAction(normal)

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

        einstellungen = self.menuBar().addMenu("&Einstellungen")

        postfaecher = QAction("Postfächer verwalten …", self)
        postfaecher.setStatusTip(
            "Postfächer hinzufügen, Passwörter ändern, stilllegen oder "
            "entfernen."
        )
        postfaecher.triggered.connect(self._postfaecher)
        einstellungen.addAction(postfaecher)

        # Der Klammerzusatz ist keine Doppelung: "Was von selbst laufen
        # soll" sagt, was gemeint ist, und "Automatisierung" ist das
        # Wort, unter dem viele danach suchen.
        hintergrund = QAction("Was von selbst laufen soll (Automatisierung) …", self)
        hintergrund.setStatusTip(
            "Regelmäßiger Abruf und regelmäßige Sicherung des Archivs."
        )
        hintergrund.triggered.connect(self._zeitplan)
        einstellungen.addAction(hintergrund)

        # Nur im Geschäftsarchiv: Ein Privatarchiv gehört einem
        # Menschen, und der sitzt davor. Zugänge zu verwalten, die
        # nur für sich selbst gelten, wäre Ballast.
        self.zugaenge_aktion = QAction("Zugänge verwalten …", self)
        self.zugaenge_aktion.setStatusTip(
            "Wer sich anmelden darf und welche Postfächer er sieht - für den Betrieb über einen Server."
        )
        self.zugaenge_aktion.triggered.connect(self._zugaenge)
        einstellungen.addAction(self.zugaenge_aktion)

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

        tipps = QAction("Tipps …", self)
        tipps.setStatusTip("Was sich im Alltag als nützlich erwiesen hat.")
        tipps.triggered.connect(lambda: self._handbuch("tipps"))
        hilfe.addAction(tipps)

        hilfe.addSeparator()
        info = QAction("Info …", self)
        info.setStatusTip("Wer das Programm gemacht hat, und wohin mit Fehlern.")
        info.triggered.connect(self._info)
        hilfe.addAction(info)

    # ------------------------------------------------------------- Archiv

    def _oeffnen(self, pfad: Path, geheimnis: str | None = None) -> None:
        """Öffnet ein Archiv im Fenster.

        ``geheimnis`` überspringt die Passwortabfrage. Das braucht, wer
        es ohnehin gerade hat: der Assistent direkt nach dem Anlegen und
        der Neuaufbau, der dasselbe Archiv wieder aufmacht. **Als
        Parameter und nicht als gemerkter Zustand**, denn beim Wechsel
        von einem verschlüsselten Archiv zum nächsten wäre ein
        gemerktes Passwort das falsche - und der Anwender bekäme »geht
        nicht« statt einer Frage.
        """
        if self.archiv is not None:
            self.archiv.close()
            self.archiv = None

        if geheimnis is None:
            geheimnis = self._geheimnis_besorgen(Path(pfad))
        if geheimnis is None:
            return

        try:
            # Nur lesend: Ein laufender Abruf im Hintergrund soll das
            # Fenster nicht aussperren, und umgekehrt.
            self.archiv = Archive.open(
                Path(pfad), exclusive=False, passwort=geheimnis
            )
        except IndexOutdated:
            self._index_veraltet(Path(pfad))
            return
        except JournalBeschaedigt as exc:
            QMessageBox.critical(self, "Das Protokoll ist beschädigt", str(exc))
            return
        except KryptoFehler as exc:
            QMessageBox.critical(self, "Archiv lässt sich nicht öffnen", str(exc))
            return
        except (ArchiveError, ArchiveLocked, OSError) as exc:
            QMessageBox.critical(self, "Archiv lässt sich nicht öffnen", str(exc))
            return
        self._geheimnis = geheimnis
        self._geheimnis_fuer = Path(pfad)

        self.modell.suchindex = self.archiv.index
        self.setWindowTitle(f"{APP_NAME} – {self.archiv.name}")
        self._betriebsart_anwenden()
        self._index_pruefen()
        self._baum_fuellen()
        self._bestand_zeigen()
        self._offene_pdf_zeigen()
        self._suchen()
        # Zuletzt: erst soll das Fenster stehen, dann die Frage kommen.
        QTimer.singleShot(0, self._fristen_pruefen)
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

        # Wurde gerade ein verschlüsseltes Archiv angelegt, ist das
        # Passwort noch warm. Gleich wieder danach zu fragen wäre eine
        # Zumutung - der Anwender hat es eben zweimal eingetippt.
        self._oeffnen(
            assistent.archiv_pfad,
            geheimnis=getattr(assistent, "archiv_passwort", "") or None,
        )
        if self.archiv is not None:
            from mailburg.core.einstellungen import merken

            merken(assistent.archiv_pfad)
            if getattr(assistent, "soll_abrufen", False):
                self._abrufen()

    def _zuletzt_fuellen(self) -> None:
        from mailburg.core.einstellungen import zuletzt_benutzte

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
            name = _archivname(pfad)
            da = (pfad / "archive.json").is_file()

            # **Nicht erreichbar heißt nicht weg.** Der häufigste Grund
            # ist eine abgezogene Platte – und für ein Archivprogramm ist
            # das der Normalfall, nicht die Ausnahme. Ein Eintrag, der
            # dann aus der Liste verschwände, sähe aus, als hätte
            # MailBurg das Archiv vergessen.
            #
            # Also bleibt er stehen und sagt, was los ist. Am 2026-08-31
            # aufgefallen: Zwei längst gelöschte Archive standen im Menü
            # und meldeten beim Anklicken nur »liegt kein MailBurg-Archiv«.
            eintrag = self.zuletzt_menue.addAction(
                name if da else f"{name}  (nicht erreichbar)"
            )
            eintrag.setStatusTip(
                str(pfad) if da
                else f"{pfad} – Platte angeschlossen? Ordner verschoben?"
            )
            eintrag.setEnabled(da)
            if da:
                eintrag.triggered.connect(
                    lambda _geklickt=False, p=pfad: self._wechseln(p)
                )

    def _wechseln(self, pfad) -> None:
        from mailburg.core.einstellungen import merken

        self._oeffnen(pfad)
        if self.archiv is not None:
            merken(pfad)
            self._zuletzt_fuellen()
            self._neueste_zuerst()

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
        from mailburg.core.einstellungen import gemerktes

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
                lambda: self._kopf_wiederherstellen(kopf),
            )

    def _kopf_wiederherstellen(self, kopf: str) -> None:
        """Stellt Spaltenbreiten wieder her – aber nicht die Sortierung."""
        self.tabelle.horizontalHeader().restoreState(
            QByteArray.fromBase64(kopf.encode())
        )
        self._neueste_zuerst()

    def _kanten_setzen(self) -> None:
        """Grenzt die drei Bereiche sichtbar voneinander ab.

        Ohne das verschwimmen Baum, Trefferliste und Vorschau zu einer
        Fläche – siehe :func:`farben.kante` für die Messung dahinter.
        Auch die Griffe der Teiler bekommen Breite: Ein Teiler, den man
        nicht sieht, wird nicht gezogen.
        """
        # Das Stylesheet setzt die Anwendung beim Start für alle
        # Fenster; hier bleiben nur die Teiler.
        for teiler in self.findChildren(QSplitter):
            teiler.setHandleWidth(4)

    def _neueste_zuerst(self) -> None:
        """Die jüngste Nachricht steht oben. Immer.

        Breiten und Reihenfolge der Spalten sind Geschmackssache und
        werden gemerkt – die Sortierung nicht. Wer einmal nach Absender
        sortiert hat, um etwas zu suchen, findet sonst Wochen später
        immer noch diese Ordnung vor und übersieht, dass neue Post
        angekommen ist. Beim Öffnen eines Archivs will man wissen, was
        zuletzt hereinkam; alles andere stellt man sich für den Moment
        ein, nicht auf Dauer.

        Das gilt für jedes Archiv gleich: Wer zwischen geschäftlich und
        privat wechselt, soll nicht die Sortierung des anderen erben.
        """
        kopf = self.tabelle.horizontalHeader()
        kopf.setSortIndicator(SPALTE_DATUM, Qt.DescendingOrder)
        # Und das Modell ausdrücklich dazu. ``setSortIndicator`` löst
        # eine Sortierung nur aus, wenn sich der Pfeil *ändert* – steht
        # er schon richtig, während die Liste anders geordnet ist, bliebe
        # es beim falschen Zustand. Zweimal zu sortieren kostet nichts,
        # einmal zu wenig kostet das Vertrauen in die Anzeige.
        self.tabelle.model().sort(SPALTE_DATUM, Qt.DescendingOrder)

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
        from mailburg.core.einstellungen import gemerktes

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

    def _schrift_aendern(self, schritte: int) -> None:
        self._schrift_setzen(self.schriftstufe + schritte)

    def _schrift_setzen(self, stufe: int) -> None:
        """Vergrößert oder verkleinert die Schrift im ganzen Fenster.

        Auf einem 14-Zoll-Bildschirm ist die Vorgabe vieler
        Arbeitsumgebungen schlicht zu klein, und ein Archiv liest man
        nicht im Vorbeigehen – man sucht darin nach einer Zahl in einer
        Rechnung. Wer schlecht sieht, stellt die Schrift des ganzen
        Systems groß; wer nur hier mehr braucht, soll es hier bekommen.
        """
        from PySide6.QtWidgets import QApplication

        self.schriftstufe = max(-3, min(8, stufe))
        schrift = QApplication.font()
        # Von der Systemgröße aus rechnen, nicht von der zuletzt
        # gesetzten: Sonst wächst die Schrift bei jedem Aufruf weiter,
        # auch wenn der Anwender zurückstellen wollte.
        schrift.setPointSizeF(max(6.0, self._grundgroesse + self.schriftstufe))

        # **An der Anwendung, nicht am Fenster.** Bis zum 2026-08-31
        # ging die Schrift ans Hauptfenster und an dessen Kinder – und
        # damit nicht dorthin, wo man sie am ehesten braucht:
        #
        # Ein aufgeklapptes Menü ist in Qt kein Kind des Fensters,
        # sondern ein eigenes Fenster. Dasselbe gilt für jeden Dialog,
        # der später aufgeht, und für die Meldungsfenster. Stephan hat
        # es so gemeldet: »Wenn ich die Schrift vergrößere, sieht es im
        # Menü immer gleich aus.«
        #
        # ``QApplication.setFont`` erreicht alle drei – auch die
        # Fenster, die es noch gar nicht gibt.
        anwendung = QApplication.instance()
        if anwendung is not None:
            anwendung.setFont(schrift)
            for klasse, ausgangswert in self._grundgroessen.items():
                eigene = QApplication.font(klasse)
                eigene.setPointSizeF(
                    max(6.0, ausgangswert + self.schriftstufe)
                )
                anwendung.setFont(eigene, klasse)
        self.setFont(schrift)
        for teil in self.findChildren(QWidget):
            teil.setFont(schrift)
        self.menuBar().setFont(schrift)

        from mailburg.core.einstellungen import merken_unter

        merken_unter("schriftstufe", self.schriftstufe)
        self.stand.setText(
            "Schriftgröße zurückgesetzt." if not self.schriftstufe
            else f"Schrift {self.schriftstufe:+d} Punkte."
        )

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
        from mailburg.core.einstellungen import merken_unter

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

    def _index_pruefen(self) -> None:
        """Merkt, wenn der Suchindex fehlt, obwohl Mails da sind.

        Ein leerer Index sieht aus wie ein leeres Archiv – dieselbe
        Anzeige, dieselbe Null. Für den Anwender ist das der Anblick
        eines Datenverlusts, dabei liegen seine Mails unversehrt
        daneben; nur das Verzeichnis dazu fehlt.

        Genau das ist passiert: Ein gelöschtes Indexverzeichnis, und
        MailBurg meldete stumm »0 Mails im Archiv«. Wer das sieht,
        denkt nicht an einen Neuaufbau, sondern an das Schlimmste.
        """
        if self.archiv is None:
            return
        try:
            im_index = self.archiv.index.count()
            if im_index:
                return
            # Nicht das Protokoll zählen, sondern die Dateien: Ein frisch
            # angelegtes Archiv hat einen create-Eintrag im Journal und
            # trotzdem keine einzige Mail. Wer danach ginge, fragte bei
            # jedem neuen Archiv, ob der Index aufgebaut werden soll.
            auf_der_platte = sum(1 for _ in self.archiv.store.iter_all())
        except Exception:  # noqa: BLE001 – eine Warnung darf nie selbst scheitern
            return
        if not auf_der_platte:
            return

        antwort = QMessageBox.question(
            self,
            "Der Suchindex fehlt",
            f"<p><b>Ihre Mails sind da – nur das Verzeichnis dazu fehlt.</b></p>"
            f"<p>In diesem Archiv liegen {auf_der_platte:,} Nachrichten, "
            f"aber der Suchindex ist leer. Das passiert, wenn er gelöscht "
            f"wurde oder das Archiv von einem anderen Rechner kommt.</p>"
            f"<p>Der Index lässt sich aus dem Protokoll neu aufbauen. Das "
            f"dauert bei diesem Bestand einige Minuten – gerechnet mit "
            f"etwa vier Minuten je zehntausend Nachrichten.</p>"
            f"<p>Jetzt aufbauen?</p>".replace(",", "."),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if antwort == QMessageBox.Yes:
            self._neuaufbau()

    def _geheimnis_besorgen(self, pfad: Path) -> str | None:
        """Fragt nach dem Passwort, wenn das Archiv verschlüsselt ist.

        Gibt ``""`` zurück, wenn keines nötig ist, und ``None``, wenn
        jemand abgebrochen hat – dann bleibt das Fenster, wie es war.

        Gefragt wird nur, wenn es nicht hinterlegt ist. Wer das Passwort
        im Tresor abgelegt hat, um den Zeitplan laufen zu lassen, will
        es nicht bei jedem Öffnen wieder eintippen; er hat sich für
        Bequemlichkeit entschieden, und das gilt dann überall.
        """
        if not Archive.ist_verschluesselt(pfad):
            return ""

        from mailburg.core import passwort as passwort_modul

        hinterlegt = passwort_modul.hinterlegt(pfad)
        if hinterlegt:
            return hinterlegt

        from mailburg.core import krypto
        from mailburg.ui.archivpasswort import PasswortFragen

        name = _archivname(pfad)
        huelle = None
        try:
            meta = json.loads((pfad / "archive.json").read_text(encoding="utf-8"))
            huelle = krypto.Huelle.aus_json(meta["encryption"])
        except (OSError, ValueError, KeyError, krypto.KryptoFehler):
            # Dann scheitert gleich das Öffnen mit einer eigenen Meldung.
            return ""

        nochmal = False
        while True:
            dialog = PasswortFragen(self, archivname=name, nochmal=nochmal)
            if not dialog.exec():
                return None
            try:
                huelle.oeffnen(dialog.geheimnis)
            except krypto.KryptoFehler:
                # **Hier prüfen, nicht erst beim Öffnen.** Sonst müsste
                # nach jedem Vertipper das halbe Fenster neu aufgebaut
                # werden, nur um wieder zu fragen.
                nochmal = True
                continue
            return dialog.geheimnis

    def _index_veraltet(self, pfad: Path) -> None:
        """Der Index stammt aus einer älteren Fassung – anbieten, ihn zu bauen.

        Das Archiv ließ sich gar nicht erst öffnen; ``self.archiv`` ist
        hier also ``None``. Eine reine Fehlermeldung wäre an dieser
        Stelle das Schlimmste: Wer nach einer Aktualisierung sein Archiv
        nicht mehr aufbekommt, rechnet mit dem Verlust von zwanzig
        Jahren Post. Es geht aber nur das Verzeichnis neu.
        """
        antwort = QMessageBox.question(
            self,
            "Der Suchindex gehört zu einer älteren Fassung",
            "<p><b>Ihre Mails sind unversehrt.</b> Nur das Verzeichnis "
            "dazu passt nicht mehr zu dieser Programmfassung.</p>"
            "<p>Diese Fassung merkt sich zu jeder Nachricht, zu welchem "
            "Gespräch sie gehört. Das steht in jeder Mail, wurde bisher "
            "aber nicht mitgeführt – der Index muss dafür einmal neu "
            "gebaut werden.</p>"
            "<p>Das dauert; gerechnet mit etwa vier Minuten je "
            "zehntausend Nachrichten. Solange läuft das Archiv nicht.</p>"
            "<p>Jetzt aufbauen?</p>",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if antwort == QMessageBox.Yes:
            self._neuaufbau(pfad)

    def _neuaufbau(self, pfad: Path | None = None) -> None:
        """Baut den Suchindex neu – mit Fortschritt, denn es dauert.

        Ohne ``pfad`` wird das geöffnete Archiv genommen. Mit einem
        kommt der Aufruf von :meth:`_index_veraltet`, wo gar nichts
        offen ist – der alte Index verhinderte ja das Öffnen.
        """
        from mailburg.ui.arbeit import Auftrag, Läufer

        class Aufbau(Auftrag):
            def __init__(self, pfad, geheimnis):
                super().__init__()
                self.pfad = pfad
                self.geheimnis = geheimnis

            def ausfuehren(self):
                from mailburg.core.archive import Archive

                # ``index_verwerfen``, weil der vorhandene Index aus
                # einer älteren Fassung stammen kann und sich dann nicht
                # öffnen lässt. Für den Neuaufbau ist er ohnehin
                # wertlos - die nächste Zeile schreibt ihn komplett neu.
                with Archive.open(
                    self.pfad, index_verwerfen=True, passwort=self.geheimnis
                ) as archiv:
                    return archiv.rebuild_index(progress=self._melden)

            def _melden(self, erledigt, gesamt):
                self.fortschritt.emit(erledigt, gesamt)

        if not isinstance(pfad, Path):
            # Kommt der Aufruf von einem Menüpunkt, steht hier Qts
            # »checked«-Kennzeichen statt eines Pfads.
            pfad = self.archiv.root

        # Der Aufbau öffnet das Archiv im Arbeitsfaden selbst und
        # braucht dafür das Passwort. Kommt der Aufruf von
        # _index_veraltet, ist noch keines abgefragt worden - dort hat
        # das Öffnen ja nie stattgefunden.
        geheimnis = self._geheimnis
        if not geheimnis or pfad != getattr(self, "_geheimnis_fuer", None):
            geheimnis = self._geheimnis_besorgen(pfad)
            if geheimnis is None:
                return

        # Ein eigenes Handle muss weg: Der Aufbau schreibt in den Index.
        if self.archiv is not None:
            self.archiv.close()
            self.archiv = None
        self.modell.suchindex = None

        self.stand.setText("Baue den Suchindex neu …")
        self.balken.setFormat("%v von %m Mails")
        self.balken.show()

        auftrag = Aufbau(pfad, geheimnis)
        # Gebundene Methoden, keine Lambdas - siehe die Regel in
        # ui/arbeit.py. Welches Archiv gemeint ist, steht am Fenster.
        self._aufbau_pfad = pfad
        self._geheimnis = geheimnis
        self._geheimnis_fuer = pfad
        self.baut_auf = True
        auftrag.fortschritt.connect(self._erkennung_schritt)
        auftrag.fertig.connect(self._nach_neuaufbau)
        auftrag.gescheitert.connect(self._aufbau_gescheitert)
        self.aufbau_laeufer = Läufer(auftrag)

        # **Erst wenn die Ereignisschleife laeuft.** Beim Start kommt
        # dieser Weg aus dem Konstruktor, und dort gibt es noch keine:
        # QApplication.exec() wird erst danach aufgerufen. Ein QThread,
        # der ohne sie startet, liefert seine Signale an niemanden.
        # Derselbe Fehler wie beim ersten Abruf am 2026-08-28, an
        # derselben Stelle nachzulesen in ui/app.py.
        QTimer.singleShot(0, self._aufbau_starten)

    def _aufbau_starten(self) -> None:
        """Startet den Aufbau – falls er dann noch gewollt ist.

        **Zwischen dem Stellen des Zeitgebers und seinem Auslösen kann
        das Fenster zugegangen sein.** Ein ``singleShot`` auf die
        Startmethode des Läufers ließe ihn auch dann loslaufen: auf ein
        Archiv, das niemand mehr offen hat. Im Testlauf hat genau das
        einen späteren, unbeteiligten Test mitgerissen.
        """
        if self.baut_auf and self.aufbau_laeufer is not None:
            self.aufbau_laeufer.starten()

    def _nach_neuaufbau(self, _anzahl=None) -> None:
        self.baut_auf = False
        self.balken.hide()
        self.balken.setFormat("%p%")
        # Das Passwort liegt vom Aufbau noch vor; danach noch einmal zu
        # fragen wäre unverständlich - es hat sich ja nichts geändert.
        self._oeffnen(self._aufbau_pfad, geheimnis=self._geheimnis or None)
        self.stand.setText("Der Suchindex ist wieder aufgebaut.")

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

        from mailburg.core.sprache import mails

        # **Während eines Abrufs nicht »zuletzt abgerufen«.** Der Stand
        # wird erst am Ende geschrieben; bis dahin stünde dort »noch nicht
        # abgerufen«, während daneben die geholten Mails hochzählen. Das
        # hat ein Anwender gemeldet, und er hatte recht: Zwei Anzeigen im
        # selben Fenster dürfen sich nicht widersprechen.
        if self.mitwachsen.isActive():
            wann = "wird gerade abgerufen …"
        else:
            wann = _abrufzeit(Abrufzustand(self.archiv.uuid).zuletzt)
        self.bestand.setText(
            f"{mails(self.archiv.index.count())} im Archiv · {wann}"
        )

    def _reihenfolge_merken(self) -> None:
        from mailburg.core.einstellungen import merken_unter

        merken_unter("postfachreihenfolge", self.baum.reihenfolge())

    def _baum_fuellen(self, auswahl_halten: bool = False) -> None:
        """Baut den Postfachbaum neu auf.

        Mit ``auswahl_halten`` überlebt, was der Anwender ausgewählt und
        aufgeklappt hatte. Das ist nötig, seit der Baum **während** eines
        laufenden Abrufs mitwächst: Wer alle paar Sekunden auf »Alle
        Postfächer« zurückgeworfen wird, kann nicht nebenher arbeiten.
        """
        vorher = self._baumstand() if auswahl_halten else None
        self.baum.clear()
        if self.archiv is None:
            return

        from mailburg.core.einstellungen import gemerktes

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

        if vorher is not None and self._baumstand_herstellen(*vorher):
            return

        alle.setSelected(True)
        self.baum.expandItem(alle)

    def _baumeintraege(self):
        """Alle Einträge des Baums, Konten und Ordner."""
        for i in range(self.baum.topLevelItemCount()):
            oben = self.baum.topLevelItem(i)
            yield oben
            for j in range(oben.childCount()):
                yield oben.child(j)

    def _baumstand(self) -> tuple[str | None, set[str]]:
        """Merkt, was ausgewählt und was aufgeklappt ist.

        Festgehalten wird der Suchausdruck des Eintrags, nicht seine
        Zeilennummer: Kommt während des Abrufs ein Ordner dazu, rutscht
        alles darunter eine Zeile weiter.
        """
        aktuell = self.baum.currentItem()
        gewaehlt = aktuell.data(0, Qt.UserRole) if aktuell is not None else None
        offen = {
            eintrag.data(0, Qt.UserRole)
            for eintrag in self._baumeintraege()
            if eintrag.isExpanded() and eintrag.data(0, Qt.UserRole) is not None
        }
        return gewaehlt, offen

    def _baumstand_herstellen(self, gewaehlt: str | None, offen: set[str]) -> bool:
        """Stellt Auswahl und aufgeklappte Zweige wieder her.

        Gibt zurück, ob die Auswahl wiedergefunden wurde. Wurde sie es
        nicht – das Postfach ist weg, der Ordner umbenannt –, fällt der
        Aufrufer auf »Alle Postfächer« zurück, statt den Baum ohne jede
        Auswahl stehen zu lassen.
        """
        getroffen = False
        for eintrag in self._baumeintraege():
            kennung = eintrag.data(0, Qt.UserRole)
            if kennung in offen:
                eintrag.setExpanded(True)
            if not getroffen and gewaehlt is not None and kennung == gewaehlt:
                eintrag.setSelected(True)
                self.baum.setCurrentItem(eintrag)
                getroffen = True
        return getroffen

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
            from mailburg.core.sprache import mails

            self.stand.setText(
                mails(self.modell.gesamt) if self.modell.gesamt
                else "Das Archiv ist noch leer."
            )
            return

        if self.modell.gesamt:
            # »Treffer« ist in Ein- und Mehrzahl gleich – hier stand
            # einmal eine Fallunterscheidung mit zwei gleichen Zweigen.
            self._suchmeldung_setzen(f"MailBurg hat {anzahl} Treffer.", True)
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
        im_programm = menue.addAction("In Mailprogramm öffnen")
        im_programm.triggered.connect(self._im_mailprogramm)
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

    def _im_mailprogramm(self) -> None:
        """Die Nachricht im gewohnten Mailprogramm öffnen.

        Ohne Rückfrage und ohne Dialog: Der Weg ist ungefährlich, weil
        er nichts verändert – weder im Archiv noch in einem Postfach.
        Wer ihn wählt, will die Mail *jetzt* sehen.
        """
        from mailburg.core import rueckgabe

        treffer = self._gewaehlter_treffer()
        if treffer is None:
            return
        roh = self._rohdaten(treffer)
        if roh is None:
            return

        try:
            rueckgabe.im_mailprogramm_oeffnen(roh, treffer.subject)
        except rueckgabe.RueckgabeFehler as exc:
            QMessageBox.warning(self, "Kein Mailprogramm gefunden", str(exc))
        except OSError as exc:
            QMessageBox.warning(
                self, "Öffnen nicht möglich",
                f"Die Nachricht ließ sich nicht ablegen.\n\n{exc}",
            )

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

        # **Nur die Postfächer dieses Archivs.** Hier lag der Fehler: Die
        # Kontenliste gilt für das ganze Programm, das Archiv aber nicht.
        # Wer geschäftlich und privat trennt, bekam mit jedem Abruf in
        # beiden Archiven denselben Bestand - am 2026-08-26 aufgefallen,
        # als von 9.866 Mails im Geschäftsarchiv 176 dorthin gehörten.
        liste = Kontenliste()
        konten = liste.fuer_archiv(self.archiv.uuid)
        offen = liste.ohne_archiv()
        if not konten:
            if offen:
                QMessageBox.information(
                    self,
                    "Kein Postfach für dieses Archiv",
                    f"Diesem Archiv ist kein Postfach zugeordnet.\n\n"
                    f"Nicht zugeordnet sind: "
                    f"{', '.join(k.name for k in offen)}\n\n"
                    f"Ein Postfach gehört ausdrücklich in ein Archiv – sonst "
                    f"landet geschäftliche Post im Privatarchiv und private "
                    f"Post unter den Aufbewahrungsfristen eines "
                    f"Geschäftsarchivs. Zuordnen unter "
                    f"Einstellungen → Postfächer.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Kein Postfach eingerichtet",
                    "Es ist noch kein Postfach eingerichtet, aus dem "
                    "abgerufen werden könnte.",
                )
            return
        if offen:
            # Kein Abbruch, aber eine Ansage: Wer nach einem Update
            # feststellt, dass weniger ankommt, soll den Grund kennen.
            self.stand.setText(
                f"{len(offen)} Postfächer sind keinem Archiv zugeordnet und "
                f"werden übergangen."
            )

        # Der Abruf braucht das Archiv schreibend; das Fenster hält es nur
        # lesend. Deshalb gibt der Auftrag es sich selbst - und wir
        # schließen unseren Index solange nicht, sondern lesen weiter.
        pfad = self.archiv.root

        uebergehen = self._sperre_klaeren(pfad)
        if uebergehen is None:
            return

        self.abrufen_aktion.setEnabled(False)
        self.balken.setRange(0, 0)
        self.balken.show()
        self.stand.setText("Rufe ab …")

        auftrag = Abruflauf(pfad, konten, sperre_uebergehen=uebergehen)
        auftrag.meldung.connect(self.stand.setText)
        auftrag.fertig.connect(self._abruf_fertig)
        auftrag.gescheitert.connect(self._abruf_gescheitert)

        self.laeufer = Läufer(auftrag)
        self.laeufer.starten()
        self.mitwachsen.start(MITWACHSEN)

    def _mitwachsen(self) -> None:
        """Zeigt während des Abrufs, was schon im Archiv liegt.

        **Darf nie selbst scheitern.** Das hier ist eine Nebensache, die
        alle drei Sekunden läuft, während im Hintergrund geschrieben
        wird. Ein Lesefehler – eine Sperre, ein halb geschriebener Stand –
        darf den Abruf nicht mit einem Traceback beenden; beim nächsten
        Schlag steht es ohnehin wieder richtig da.
        """
        if self.archiv is None:
            return
        try:
            self._baum_fuellen(auswahl_halten=True)
            self._bestand_zeigen()
        except Exception:  # noqa: BLE001 – siehe Docstring
            pass

    def _abruf_fertig(self, ergebnisse: dict) -> None:
        self.laeufer = None
        self.mitwachsen.stop()
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

    def _sperre_klaeren(self, pfad) -> bool | None:
        """Klärt vor dem Abruf, ob eine Sperre im Weg liegt.

        Gibt ``True`` zurück, wenn der Anwender sie ausdrücklich
        übergehen will, ``False``, wenn nichts im Weg ist, und ``None``,
        wenn abgebrochen wurde.

        **Warum die Frage hierhin gehört und nicht in eine
        Fehlermeldung.** Bis zum 2026-09-01 lief der Abruf einfach los,
        scheiterte an der Sperre und meldete: »der Vorgang, der es hielt,
        läuft nicht mehr … die Datei kann gelöscht werden«. Wer das las,
        musste ins Terminal, um eine versteckte Datei auf einer externen
        Platte zu entfernen – und stand sonst vor einer Sackgasse.

        Eine nachweislich verwaiste Sperre räumt der Kern inzwischen
        selbst weg. Übrig bleiben die Fälle, in denen er es *nicht*
        wissen kann: Die Sperre stammt von einem anderen Rechner oder
        führt keine Prozessnummer. Genau dort weiß der Anwender mehr als
        das Programm – dass der zweite Rechner aus ist, dass die Platte
        gerade erst angesteckt wurde.
        """
        liegt, erklaerung = Archive.sperre_pruefen(pfad)
        if not liegt:
            return False

        laeuft = Archive.sperre_laeuft_noch(pfad)
        if laeuft is True:
            # Der häufigste Fall: der Abruf im Hintergrund. Kein Wort
            # über Sperrdateien - das ist kein Fehler, sondern Betrieb.
            QMessageBox.information(self, "Bitte einen Augenblick", erklaerung)
            return None
        if laeuft is False:
            # Verwaist und auf diesem Rechner: Der Kern räumt selbst auf.
            return False

        antwort = QMessageBox.question(
            self,
            "Das Archiv ist als geöffnet vermerkt",
            f"<p>{erklaerung.replace(chr(10), '<br>')}</p>"
            f"<p><b>Läuft dort wirklich noch MailBurg?</b> Ob auf einem "
            f"anderen Rechner noch etwas läuft, kann MailBurg von hier "
            f"aus nicht feststellen – Sie schon.</p>"
            f"<p>Ist der andere Rechner aus oder das Programm dort "
            f"längst beendet, können Sie den Vermerk entfernen lassen "
            f"und jetzt abrufen.</p>"
            f"<p><i>Läuft dort noch etwas, schreiben hinterher zwei "
            f"Vorgänge gleichzeitig ins Protokoll – und das lässt sich "
            f"nicht wieder auflösen.</i></p>",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if antwort != QMessageBox.Yes:
            self.stand.setText("Abruf abgebrochen – der Vermerk bleibt.")
            return None

        self.stand.setText("Vermerk entfernt, rufe ab …")
        return True

    def _abruf_gescheitert(self, text: str) -> None:
        self.laeufer = None
        self.mitwachsen.stop()
        self.balken.hide()
        self.abrufen_aktion.setEnabled(True)
        # Auch hier auffrischen: Ein Abruf, der nach der Hälfte
        # abbricht, hat die erste Hälfte trotzdem archiviert. Der Baum
        # dürfte sie nicht verschweigen.
        self._baum_fuellen(auswahl_halten=True)
        self._bestand_zeigen()
        self.stand.setText("Abruf gescheitert")
        QMessageBox.critical(self, "Abruf gescheitert", text)

    def _aufbau_gescheitert(self, text: str) -> None:
        """Eigener Weg, weil hier womöglich kein Archiv offen ist.

        Beim Start kommt der Aufbau aus :meth:`_index_veraltet`;
        scheitert er, sitzt der Anwender vor einem leeren Fenster ohne
        Archiv. ``_abruf_gescheitert`` schaltete stattdessen den
        Abrufknopf wieder ein und meldete »Abruf gescheitert« – beides
        falsch, und das Zweite auch noch irreführend.
        """
        self.baut_auf = False
        self.aufbau_laeufer = None
        self.balken.hide()
        self.balken.setFormat("%p%")
        self.stand.setText("Der Suchindex konnte nicht aufgebaut werden.")
        QMessageBox.critical(
            self,
            "Suchindex nicht aufgebaut",
            f"{text}\n\n"
            f"Ihre Mails sind davon nicht betroffen – der Index liegt "
            f"außerhalb des Archivs. Versuchen Sie es beim nächsten Start "
            f"erneut oder auf der Kommandozeile mit »mailburg neuaufbau«.",
        )

    # --------------------------------------------------------------- Sonst

    def _sichern(self) -> None:
        from mailburg.ui.sichern import Sicherungsdialog

        if self.archiv is None:
            return
        Sicherungsdialog(self.archiv, self).exec()

    def _sicherung_uebernehmen(self) -> None:
        from mailburg.ui.sichern import Uebernahmedialog

        if self.archiv is None:
            return
        Uebernahmedialog(self.archiv, self).exec()
        self._baum_fuellen()
        self._bestand_zeigen()
        self._offene_pdf_zeigen()
        self._suchen()

    def _zurueckholen(self) -> None:
        from mailburg.ui.sichern import Rueckholdialog

        dialog = Rueckholdialog(self)
        if dialog.exec() and dialog.ziel is not None:
            antwort = QMessageBox.question(
                self, "Zurückgeholtes Archiv öffnen?",
                f"Soll MailBurg jetzt zu {dialog.ziel} wechseln?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if antwort == QMessageBox.Yes:
                self._wechseln(dialog.ziel)

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

    #: Was nur in einer der beiden Betriebsarten sinnvoll ist.
    #:
    #: Die Zuordnung steht an *einer* Stelle. Verteilt über die
    #: Menüaufbau-Methode wäre beim nächsten Punkt die Hälfte vergessen,
    #: und der Anwender stünde vor einem Eintrag, der nichts tut.
    NUR_GESCHAEFTLICH = (
        ("einstufen_aktion", "Aufbewahrungsfristen gibt es nur im "
                             "Geschäftsarchiv – ein Privatarchiv kennt "
                             "keine."),
        ("regeln_aktion", "Einstufungsregeln sind für das "
                          "Geschäftsarchiv gedacht: Sie halten private "
                          "Post aus den Aufbewahrungsfristen heraus. Im "
                          "Privatarchiv gibt es keine."),
        ("doku_aktion", "Eine Verfahrensdokumentation nach GoBD "
                        "verlangt nur, wer geschäftlich archiviert."),
        ("auskunft_aktion", "Ein Privatarchiv fällt unter die "
                            "Haushaltsausnahme der DSGVO; ein "
                            "Auskunftsrecht nach Artikel 15 besteht "
                            "dort nicht."),
        ("zugaenge_aktion", "Zugänge trennen, was mehrere Menschen "
                            "sehen dürfen. Ein Privatarchiv gehört "
                            "einem – und der sitzt davor."),
    )

    def _betriebsart_anwenden(self) -> None:
        """Schaltet die Menüpunkte, die nur zu einer Archivart passen.

        **Ausgegraut, nicht ausgeblendet.** Ein verschwundener Eintrag
        lässt niemanden wissen, dass es die Funktion gibt – wer sie
        einmal braucht, sucht sie im falschen Programm. Ein grauer
        Eintrag zeigt sie und sagt im Statustext, warum er hier nicht
        gilt. So lernt man das Programm nebenbei kennen, statt vor einer
        Lücke zu stehen.
        """
        geschaeftlich = (
            self.archiv is not None and self.archiv.mode.is_business
        )
        for name, grund in self.NUR_GESCHAEFTLICH:
            aktion = getattr(self, name, None)
            if aktion is None:
                continue
            aktion.setEnabled(geschaeftlich)
            if not geschaeftlich:
                aktion.setStatusTip(grund)
                aktion.setToolTip(grund)

    def _verfahrensdoku(self) -> None:
        """Schreibt einen Entwurf nach GoBD in eine Datei."""
        from PySide6.QtWidgets import QFileDialog

        from mailburg.core import verfahrensdoku

        if self.archiv is None:
            return

        ziel, _ = QFileDialog.getSaveFileName(
            self,
            "Verfahrensdokumentation speichern",
            str(Path.home() / f"Verfahrensdokumentation-{self.archiv.name}.md"),
            "Markdown (*.md)",
        )
        if not ziel:
            return

        from mailburg.core.accounts import Kontenliste

        try:
            text = verfahrensdoku.erzeugen(self.archiv, Kontenliste())
            Path(ziel).write_text(text, encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Speichern gescheitert", str(exc))
            return

        luecken = text.count(verfahrensdoku.LUECKE)
        QMessageBox.information(
            self,
            "Entwurf gespeichert",
            f"Geschrieben nach\n{ziel}\n\n"
            f"{luecken} Stellen sind noch auszufüllen – suchen Sie in der "
            f"Datei nach »BITTE ERGÄNZEN«.\n\n"
            f"Was dort steht, kann kein Programm wissen: wer zuständig "
            f"ist, wer vertreten darf, wie oft geprüft wird. "
            f"Verantwortlich für die Verfahrensdokumentation ist "
            f"ausschließlich der Steuerpflichtige.",
        )

    def _auskunft(self) -> None:
        """Stellt zusammen, was zu einer Person im Archiv liegt."""
        from mailburg.ui.auskunft import Auskunftsdialog

        if self.archiv is None:
            return
        Auskunftsdialog(self.archiv, self).exec()

    def _fristen_pruefen(self) -> None:
        """Fragt einmal im Jahr, was seine Frist hinter sich hat.

        **Einmal, nicht bei jedem Start.** Eine Meldung, die ab dem
        1. Januar bei jedem Öffnen erscheint, wird nach der dritten
        Wiederholung weggeklickt, ohne gelesen zu werden – und dann auch
        beim vierten Mal, wenn es darauf ankäme.
        """
        from mailburg.core import nachfrage

        if self.archiv is None or not nachfrage.steht_an(self.archiv):
            return

        try:
            treffer = (
                self.archiv.faellige() if self.archiv.mode.is_business
                else self.archiv.alte()
            )
        except Exception:  # noqa: BLE001
            # Eine Nachfrage darf das Öffnen eines Archivs nie verhindern.
            return

        # **Auch ein leerer Befund wird vermerkt.** Sonst rechnet MailBurg
        # bei jedem Start des Jahres von neuem durch das ganze Archiv,
        # ohne dass jemals etwas dabei herauskäme.
        nachfrage.gefragt_vermerken(str(self.archiv.uuid))
        if not treffer:
            return

        from mailburg.ui.fristen import Fristendialog

        dialog = Fristendialog(self.archiv, treffer, self)
        dialog.exec()
        if not dialog.ansehen:
            return

        # Die Treffer in die Suche legen, statt sie im Dialog zu zeigen:
        # Dort stehen sie in der gewohnten Liste, mit Vorschau, Sortierung
        # und allem, was man zum Beurteilen braucht.
        jahre = sorted({(t.date or "?")[:4] for t in treffer if t.date})
        if jahre:
            self.suchfeld.setText(f"jahr:1900-{jahre[-1]}")
            self._suchen()

    def _zugaenge(self) -> None:
        """Öffnet die Verwaltung der Zugänge."""
        from mailburg.ui.zugaenge import Zugangsdialog

        if self.archiv is None:
            return
        Zugangsdialog(self, archiv=self.archiv).exec()

    def _regeln(self) -> None:
        """Öffnet die Verwaltung der Einstufungsregeln."""
        from mailburg.ui.regeln import Regeldialog

        if self.archiv is None:
            return
        dialog = Regeldialog(self, archiv=self.archiv)
        dialog.resize(760, 560)
        if dialog.exec():
            # Die Statuszeile kann sich geändert haben, wenn beim
            # Anwenden Mails umgestuft wurden.
            self._bestand_zeigen()

    def _einstufen(self) -> None:
        """Ordnet die gerade gefundenen Mails aufbewahrungsrechtlich ein."""
        from mailburg.ui.einstufen import Einstufungsdialog

        if self.archiv is None:
            return

        ausdruck = self.suchfeld.text().strip()
        treffer = self.archiv.index.search(ausdruck, limit=1_000_000)
        if not treffer:
            QMessageBox.information(
                self,
                "Nichts gefunden",
                "Eingestuft wird, was gerade gefunden ist. Suchen Sie "
                "zuerst – etwa nach »von:steuerkanzlei« oder »rechnung«.",
            )
            return

        dialog = Einstufungsdialog(self.archiv, ausdruck, treffer, self)
        if not dialog.exec():
            return

        stufe = dialog.gewaehlt()
        offen = [t for t in treffer if t.category != stufe.value]
        if not offen:
            return

        # Ohne Warteanzeige: Bei mehreren tausend Mails schreibt das
        # Journal für jede einen Eintrag, und das dauert spürbar.
        self.setCursor(Qt.WaitCursor)
        try:
            for eintrag in offen:
                self.archiv.classify(
                    eintrag.hash, stufe,
                    note=f"Suche: {ausdruck}" if ausdruck else "gesamtes Archiv",
                )
        except Exception as exc:  # noqa: BLE001
            self.unsetCursor()
            QMessageBox.warning(
                self, "Einstufen abgebrochen",
                f"Nicht alle Mails konnten eingestuft werden: {exc}\n\n"
                f"Was bis dahin geändert wurde, steht im Journal.",
            )
            return
        finally:
            self.unsetCursor()

        wort = "Mail" if len(offen) == 1 else "Mails"
        self.stand.setText(
            f"{len(offen)} {wort} als »{stufe.value}« eingestuft – "
            f"im Journal vermerkt."
        )
        self._suchen()

    def _einlesen(self) -> None:
        """Liest lokale Mailordner ein – Thunderbird, Maildir, MBOX.

        Der Dialog öffnet das Archiv selbst schreibend; unser Handle
        hält es nur lesend. Deshalb wird danach neu aufgebaut, statt
        darauf zu hoffen, dass die Anzeige von allein stimmt.
        """
        from mailburg.ui.einlesen import Einlesedialog

        if self.archiv is None:
            return
        uebergehen = self._sperre_klaeren(self.archiv.root)
        if uebergehen is None:
            return

        dialog = Einlesedialog(self.archiv, self)
        dialog.exec()
        self._baum_fuellen(auswahl_halten=True)
        self._bestand_zeigen()
        self._suchen()

    def _zurueckspielen(self) -> None:
        """Schreibt viele Mails auf einmal auf die Platte.

        **Der Suchausdruck aus dem Fenster kommt mit.** Wer erst sucht
        und dann zurückspielt, meint in aller Regel genau das, was er
        vor sich sieht – ihn den Ausdruck ein zweites Mal tippen zu
        lassen wäre eine Gelegenheit, ihn anders zu tippen.

        Anders als beim Einlesen wird die Anzeige danach nicht neu
        aufgebaut: Am Archiv ändert sich nichts.
        """
        from mailburg.ui.zurueckspielen import Rueckspieldialog

        if self.archiv is None:
            return
        Rueckspieldialog(self.archiv, self.suchfeld.text().strip(), self).exec()

    def _texterkennung(self) -> None:
        from mailburg.ui.texterkennung import Texterkennungsdialog

        if self.archiv is None:
            return
        dialog = Texterkennungsdialog(self.archiv, self)
        dialog.weiterlaufen.connect(self._erkennung_uebernehmen)
        dialog.exec()
        self._offene_pdf_zeigen()
        self._suchen()

    def _erkennung_uebernehmen(self, laeufer) -> None:
        """Beobachtet einen Erkennungslauf weiter, dessen Fenster zu ist.

        Der Läufer wandert hierher, weil das Hauptfenster länger lebt als
        der Dialog. Angezeigt wird nur noch in der Statuszeile – man soll
        weitersuchen können, ohne dass etwas dazwischenfunkt.
        """
        self.ocr_laeufer = laeufer
        laeufer.auftrag.fortschritt.connect(self._erkennung_schritt)
        laeufer.auftrag.fertig.connect(self._erkennung_fertig)
        laeufer.auftrag.gescheitert.connect(self._erkennung_fertig)
        self.balken.setFormat("%v von %m")
        self.balken.show()
        self._ocr_hinweis_setzen(0, 0)

    def _erkennung_schritt(self, erledigt: int, gesamt: int) -> None:
        if gesamt:
            self.balken.setRange(0, gesamt)
        self.balken.setValue(erledigt)
        self._ocr_hinweis_setzen(erledigt, gesamt)

    def _ocr_hinweis_setzen(self, erledigt: int, gesamt: int) -> None:
        stand = f" {erledigt} von {gesamt}" if gesamt else " …"
        self.ocr_hinweis.setText(
            f"<span style='color: {farben.schlecht()}'><b>"
            f"PDF-Erkennung läuft im Hintergrund:{stand}</b></span>"
        )

    def _erkennung_fertig(self, _ergebnis=None) -> None:
        self.ocr_laeufer = None
        self.ocr_hinweis.setText("")
        self.balken.hide()
        self.balken.setFormat("%p%")
        self._offene_pdf_zeigen()
        # Frisch suchen: Was gerade gelesen wurde, ist ab jetzt zu finden.
        self._suchen()
        self.stand.setText("Die eingescannten PDF sind gelesen.")

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

    def _info(self) -> None:
        """Wer das Programm gemacht hat – und wohin mit Fehlern und Ideen.

        Eine gebundene Methode, kein Lambda: An dieser Stelle ist es
        gleichgültig, aber die Regel gilt im ganzen Fenster, und eine
        Ausnahme lädt zur nächsten ein.
        """
        from mailburg.ui import info

        info.oeffnen(self)

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


# Die Leseroutine steht in core.archive - sie gehört zum Archivformat,
# nicht zur Darstellung. Hier nur weitergereicht, damit die Aufrufer im
# Modul nicht zwei Herkünfte kennen müssen.
def _ohne_doppelte(kuerzel):
    """Entfernt Kürzel, die schon in der Liste stehen.

    **Zwei gleiche Kürzel an einer Aktion sind keines.** Qt meldet dann
    ``AmbiguousShortcutOverload`` und löst nichts aus. Die Liste kommt
    aber oft aus zwei Quellen – einem Standardwert der Plattform und
    einer eigenen Ergänzung –, und ob die zusammenfallen, weiß man erst
    zur Laufzeit: ``QKeySequence.ZoomIn`` ist unter Linux Strg++, unter
    macOS aber nicht.

    Deshalb hier aussortieren statt raten.
    """
    gesehen = []
    for eines in kuerzel:
        from PySide6.QtGui import QKeySequence

        folge = QKeySequence(eines)
        if folge.isEmpty():
            continue
        if any(folge == schon for schon in gesehen):
            continue
        gesehen.append(folge)
    return gesehen


from mailburg.core.archive import archivname as _archivname  # noqa: E402


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
