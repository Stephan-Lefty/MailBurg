"""Den Serverdienst einrichten – ohne einen einzigen abgetippten Befehl.

**Woher das kommt.** Am 2026-10-02 wurde der Windows-Dienst zum ersten
Mal aufgesetzt. Von zehn Schritten verlangten acht einen PowerShell-
Befehl aus einer PDF, und als der Dienst nicht startete, stand der Grund
in einem Ereignisprotokoll, das man mit einem weiteren Befehl durchsucht
– ``Unable to configure formatter 'default'``, drei Befehle entfernt von
dem, der danach suchte.

**Der Aufbau ist eine Prüfliste, kein Assistent.** Ein Assistent führt
einmal durch und ist dann fertig; hier kommt man wieder, weil etwas
klemmt. Jede Zeile sagt, wie sie steht, und wo es hakt, steht der Knopf
daneben, der es behebt.

**Die Prüfungen selbst stehen in ``server/einrichtung.py``.** Dieses
Fenster malt sie nur. Läge die Entscheidung hier, wäre sie auf einem
Linux-Rechner nicht prüfbar – und ausgerechnet dieses Fenster handelt
von Dingen, die nur unter Windows passieren.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mailburg.core.bericht import pruefbericht, tresorbericht
from mailburg.server import einrichtung
from mailburg.server.einrichtung import Befund, Lage, Umgebung
from mailburg.ui.fliesstext import Fliesstext

#: Was vor einer Zeile steht. Zeichen statt Farbe allein – wer Rot und
#: Grün nicht unterscheidet, sieht sonst eine Liste gleicher Punkte.
ZEICHEN = {
    Lage.GUT: "✓",
    Lage.FEHLT: "✗",
    Lage.ACHTUNG: "!",
    Lage.UNKLAR: "?",
}

#: Die Farben kommen **nicht** aus der Systempalette, sondern sind die
#: drei Ampelfarben – sie bedeuten etwas, statt zum Thema zu passen.
#: Dunkel genug für helle und kräftig genug für dunkle Themen.
FARBEN = {
    Lage.GUT: "#1E7B34",
    Lage.FEHLT: "#B3261E",
    Lage.ACHTUNG: "#9A6700",
    Lage.UNKLAR: "#5F6368",
}

#: Beschriftung und Erklärung je Abhilfe-Knopf.
KNOEPFE = {
    "pakete": ("Pakete nachrüsten …", "Zeigt den Befehl zum Kopieren."),
    "archiv": ("Archiv wählen …", "Einen vorhandenen Archivordner suchen."),
    "zugang": ("Zugänge …", "Wer sich anmelden darf."),
    "uebernehmen": ("Übernehmen", "Schreibt die Einstellungen für den Dienst."),
    "dienst_anlegen": ("Dienst einrichten", "Meldet ihn bei Windows an."),
    "dienst_start": ("Dienst starten", "Startet den eingerichteten Dienst."),
    "starttyp": (
        "Automatisch starten",
        "Baut den Dienst ab und richtet ihn so ein, dass er nach einem "
        "Neustart von selbst wiederkommt.",
    ),
    "tresor": (
        "Tresor einrichten …",
        "Erzeugt den Hauptschlüssel, mit dem der Dienst an die "
        "Postfach-Passwörter kommt.",
    ),
    "abruf": (
        "Abruf einrichten …",
        "Wie oft der Dienst Post holt – und wann er dabei Ruhe gibt.",
    ),
    "nachsehen": (
        "Nach Updates sehen",
        "Fragt GitHub, ob eine neuere Fassung veröffentlicht ist.",
    ),
    "aktualisieren": (
        "Update installieren",
        "Lädt die neue Fassung und spielt sie ein. Der Dienst wird dabei "
        "einmal angehalten.",
    ),
}


class Zeile(QWidget):
    """Ein Befund: Zeichen, Titel, Text – und vielleicht ein Knopf."""

    def __init__(self, befund: Befund, handeln) -> None:
        super().__init__()
        reihe = QHBoxLayout(self)
        reihe.setContentsMargins(0, 2, 0, 2)

        marke = QLabel(ZEICHEN[befund.lage])
        marke.setStyleSheet(
            f"color: {FARBEN[befund.lage]}; font-weight: bold;"
        )
        # **Aus der Schrift gerechnet, nicht geraten.** Eine feste
        # Pixelzahl sitzt falsch, sobald jemand die Schrift vergrößert –
        # und in MailBurg lässt sie sich einstellen.
        marke.setMinimumWidth(self.fontMetrics().horizontalAdvance("M") * 2)
        reihe.addWidget(marke)

        titel = QLabel(f"<b>{befund.titel}</b>")
        titel.setMinimumWidth(
            self.fontMetrics().horizontalAdvance("Pakete für den Dienst") + 8
        )
        reihe.addWidget(titel)

        # **Kein nacktes QLabel mit setWordWrap.** Qt meldet dem Layout
        # dann eine Höhe, die für irgendeine angenommene Breite gilt,
        # nicht für die tatsächliche – und verschluckt die zweite Zeile.
        # Genau das hat ``lesbarkeit.py`` hier bei allen fünf
        # Schriftgrößen gefunden, bevor dieser Absatz ein Fliesstext war.
        text = Fliesstext(befund.text)
        reihe.addWidget(text, 1)

        if befund.abhilfe and befund.abhilfe in KNOEPFE:
            beschriftung, erklaerung = KNOEPFE[befund.abhilfe]
            knopf = QPushButton(beschriftung)
            knopf.setToolTip(erklaerung)
            knopf.clicked.connect(lambda: handeln(befund.abhilfe))
            reihe.addWidget(knopf)

        if befund.einzelheiten:
            self.setToolTip(befund.einzelheiten)


class Einrichtungsfenster(QMainWindow):
    """Die Prüfliste und alles, was man daraus tun kann."""

    def __init__(self) -> None:
        super().__init__()
        # **»und Wartung«, seit dem 2026-10-06.** Das Fenster war als
        # Einrichtungshilfe gedacht – etwas, das man einmal braucht.
        # Nach dem ersten echten Serverumzug ist klar, dass es der Ort
        # ist, an dem ein Verwalter *im Betrieb* nachsieht: Läuft es
        # sauber, und wenn nicht, was ist zu tun?
        self.setWindowTitle("MailBurg im Browser – einrichten und warten")
        self._wappen_setzen()
        self.umgebung = self._umgebung_laden()

        #: Was GitHub zuletzt gesagt hat. **Gemerkt, nicht bei jedem
        #: »Neu prüfen« neu geholt**: Auf einem Server ohne
        #: Außenverbindung hinge die Liste sonst jedes Mal bis zum
        #: Zeitablauf, bevor überhaupt etwas erscheint.
        self.stand = None

        # **Ein Rollbereich, und zwar als Rückfalllinie.** In der
        # Vorgabegröße soll nichts gerollt werden – das ist Stephans
        # Regel vom 2026-08-31, und sie gilt. Aber dieses Fenster hat
        # siebzehn Prüfzeilen, einen Wartungskasten und ein Protokoll;
        # auf einem Server, der oft an einem kleinen oder entfernten
        # Bildschirm hängt, kam man an die unteren Zeilen gar nicht
        # heran (2026-10-06 gemeldet: »im Menü kann ich nicht
        # scrollen«).
        mitte = QWidget()
        rollen = QScrollArea()
        rollen.setWidget(mitte)
        rollen.setWidgetResizable(True)
        # Waagerecht wird nie gerollt: Was zu breit ist, ist ein Fehler
        # im Layout und soll als solcher auffallen.
        rollen.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rollen.setFrameShape(QFrame.NoFrame)
        self.setCentralWidget(rollen)
        senkrecht = QVBoxLayout(mitte)

        # -- Die Ampel ------------------------------------------------------
        # **Ganz oben und vor allem anderen.** Siebzehn Zeilen
        # beantworten nicht die Frage, mit der ein Verwalter dieses
        # Fenster öffnet: Muss ich etwas tun? Erst danach interessiert
        # ihn, was.
        ampelzeile = QHBoxLayout()
        self.ampel = QLabel()
        self.ampel.setToolTip(
            "Rot: etwas Zwingendes fehlt – der Dienst läuft nicht oder "
            "liefert nichts aus.\n"
            "Gelb: es läuft, aber etwas gehört nachgezogen.\n"
            "Grün: alles in Ordnung."
        )
        ampelzeile.addWidget(self.ampel)
        self.ampeltext = Fliesstext("")
        ampelzeile.addWidget(self.ampeltext, 1)
        self.ampelknopf = QPushButton()
        self.ampelknopf.clicked.connect(self._ampel_handeln)
        ampelzeile.addWidget(self.ampelknopf)
        senkrecht.addLayout(ampelzeile)

        #: Woran der Ampelknopf gerade hängt – die erste offene Sache.
        self._ampel_abhilfe = ""

        senkrecht.addWidget(Fliesstext(
            "<p>Hier wird eingerichtet und nachgesehen, was nötig ist, "
            "damit das Archiv im Browser erreichbar ist – auf diesem "
            "Rechner und, wenn Sie es wollen, im Netz.</p>"
            "<p>Die Liste prüft sich selbst. Wo etwas fehlt, steht der "
            "Knopf daneben; die Werkzeuge darunter sagen Ihnen, ob das "
            "Archiv in Ordnung ist.</p>"
        ))

        # -- Einstellungen -------------------------------------------------
        kasten = QGroupBox("Was ausgeliefert wird")
        oben = QVBoxLayout(kasten)

        archivzeile = QHBoxLayout()
        archivzeile.addWidget(QLabel("Archiv:"))
        self.archivfeld = QLineEdit(
            str(self.umgebung.archiv) if self.umgebung.archiv else ""
        )
        self.archivfeld.setPlaceholderText("noch keines gewählt")
        # Ein Pfad braucht Platz; 108 px wie am 2026-09-07 im
        # Einlesedialog zeigen »erbird« statt des Verzeichnisses.
        self.archivfeld.setMinimumWidth(
            self.fontMetrics().horizontalAdvance("W") * 40
        )
        archivzeile.addWidget(self.archivfeld, 1)
        suchen = QPushButton("Suchen …")
        suchen.clicked.connect(self._archiv_waehlen)
        archivzeile.addWidget(suchen)
        neu = QPushButton("Vorführarchiv anlegen …")
        neu.setToolTip(
            "27 erfundene Mails zum Ausprobieren. Alle Adressen enden "
            "auf .example – es steht keine echte Post darin."
        )
        neu.clicked.connect(self._vorfuehrarchiv)
        archivzeile.addWidget(neu)
        oben.addLayout(archivzeile)

        netzzeile = QHBoxLayout()
        netzzeile.addWidget(QLabel("Erreichbar:"))
        from PySide6.QtWidgets import QComboBox

        self.netz = QComboBox()
        self.netz.addItem("nur auf diesem Rechner", "127.0.0.1")
        self.netz.addItem("auch im Netz (ohne TLS!)", "0.0.0.0")  # noqa: S104
        self.netz.setCurrentIndex(
            1 if self.umgebung.adresse not in ("127.0.0.1", "::1") else 0
        )
        # Ein Auswahlfeld so breit wie sein längster Eintrag, nicht wie
        # das Layout es zuteilt.
        self.netz.setMinimumWidth(
            self.fontMetrics().horizontalAdvance(
                "auch im Netz (ohne TLS!)"
            ) + 40
        )
        netzzeile.addWidget(self.netz)

        netzzeile.addWidget(QLabel("Port:"))
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(self.umgebung.anschluss)
        netzzeile.addWidget(self.port)

        uebernehmen = QPushButton("Übernehmen")
        uebernehmen.setToolTip(
            "Schreibt die Einstellungen dorthin, wo der Dienst sie findet."
        )
        uebernehmen.clicked.connect(self._uebernehmen)
        netzzeile.addWidget(uebernehmen)
        netzzeile.addStretch(1)
        oben.addLayout(netzzeile)

        # -- der gemeinsame Ordner ----------------------------------------
        gemeinsam = QHBoxLayout()
        gemeinsam.addWidget(QLabel("Gemeinsamer Ordner:"))
        self.gemeinsamfeld = QLineEdit(
            str(self.umgebung.einstellungen)
            if self.umgebung.einstellungen else ""
        )
        self.gemeinsamfeld.setPlaceholderText("z. B. C:\\MailBurg-Daten")
        self.gemeinsamfeld.setToolTip(
            "Hier liegen Kontenliste, Tresor und Suchindex – an einem Ort, "
            "den der Dienst und Sie beide erreichen.\n\n"
            "Ohne ihn sucht der Dienst in einem Systemprofil, in das Sie "
            "nie etwas gelegt haben: Die Suche bliebe leer und es käme "
            "keine Post nach, ohne dass irgendwo ein Fehler steht."
        )
        self.gemeinsamfeld.setMinimumWidth(
            self.fontMetrics().horizontalAdvance("W") * 40
        )
        gemeinsam.addWidget(self.gemeinsamfeld, 1)
        waehlen = QPushButton("Suchen …")
        waehlen.clicked.connect(self._gemeinsam_waehlen)
        gemeinsam.addWidget(waehlen)
        oben.addLayout(gemeinsam)

        self.warnung = QLabel()
        self.warnung.setWordWrap(True)
        self.warnung.setStyleSheet(f"color: {FARBEN[Lage.ACHTUNG]};")
        oben.addWidget(self.warnung)
        self.netz.currentIndexChanged.connect(self._warnung_pflegen)
        self._warnung_pflegen()

        senkrecht.addWidget(kasten)

        # -- die Prüfliste --------------------------------------------------
        self.liste = QGroupBox("Was geprüft wird")
        self.listenlayout = QVBoxLayout(self.liste)
        senkrecht.addWidget(self.liste)

        # -- Dienst ---------------------------------------------------------
        dienstzeile = QHBoxLayout()
        for beschriftung, was in (
            ("Dienst einrichten", "anlegen"),
            ("Starten", "starten"),
            ("Anhalten", "stoppen"),
            ("Entfernen", "entfernen"),
        ):
            knopf = QPushButton(beschriftung)
            knopf.clicked.connect(
                lambda _=False, w=was: self._dienst(w)
            )
            dienstzeile.addWidget(knopf)
        dienstzeile.addStretch(1)
        symbole = QPushButton("Symbole anlegen")
        symbole.setToolTip(
            "Zwei Verknüpfungen auf dem Schreibtisch aller Benutzer: "
            "die Weboberfläche und dieses Fenster."
        )
        symbole.clicked.connect(self._verknuepfungen)
        dienstzeile.addWidget(symbole)
        nachsehen = QPushButton("Neu prüfen")
        nachsehen.clicked.connect(self.auffrischen)
        dienstzeile.addWidget(nachsehen)
        senkrecht.addLayout(dienstzeile)

        # -- Wartung --------------------------------------------------------
        # **Eigener Kasten, seit dem 2026-10-06.** Die Prüfliste darüber
        # beantwortet »ist es eingerichtet«. Ein Verwalter im Betrieb
        # fragt etwas anderes: »Ist mein Archiv in Ordnung, und wenn
        # nicht, was tue ich?« Dafür gab es bisher nur die
        # Kommandozeile – auf einem Server also nichts.
        wartung = QGroupBox("Wartung")
        wartungszeile = QHBoxLayout(wartung)
        for beschriftung, hinweis, ziel in (
            ("Archiv prüfen",
             "Hält die Hash-Kette gegen die Ablage: Ist jede Mail noch "
             "da, und liegt dort nichts, was nicht im Journal steht?\n\n"
             "Das Archiv wird dabei nur gelesen.",
             "pruefen"),
            ("Tresor prüfen",
             "Lässt sich jeder Eintrag öffnen – und reicht er für alle "
             "eingerichteten Postfächer?\n\n"
             "Fehlt einem Postfach die Anmeldung, holt der Dienst von "
             "dort keine Post und meldet es nicht als Fehler.",
             "tresor_pruefen"),
            ("Tagesbericht …",
             "MailBurg schickt Ihnen täglich (oder seltener), was es "
             "getan hat – und sofort, wenn etwas klemmt.\n\n"
             "Bleibt die Mail aus, läuft der Dienst nicht mehr. Das ist "
             "dann selbst der Befund.",
             "bericht"),
            ("Mails einlesen …",
             "Post aus Dateien übernehmen – ein Verzeichnis mit "
             ".eml-Dateien, ein Maildir, eine MBOX-Datei oder ein "
             "Thunderbird-Profil.\n\n"
             "Der Dienst wird dafür angehalten und bleibt es, bis Sie "
             "ihn wieder starten: Zwei Vorgänge, die gleichzeitig ins "
             "selbe Archiv schreiben, reißen die Hash-Kette.",
             "einlesen"),
        ):
            knopf = QPushButton(beschriftung)
            knopf.setToolTip(hinweis)
            knopf.clicked.connect(
                lambda _=False, z=ziel: self._wartung(z)
            )
            wartungszeile.addWidget(knopf)
        wartungszeile.addStretch(1)
        senkrecht.addWidget(wartung)

        # -- Protokoll ------------------------------------------------------
        protokollkasten = QGroupBox("Was der Dienst meldet")
        innen = QVBoxLayout(protokollkasten)
        self.protokoll = QPlainTextEdit()
        self.protokoll.setReadOnly(True)
        # **Aus der Schrift gerechnet, nicht in Pixeln geraten.** Fünf
        # Zeilen reichen, um zu sehen, dass etwas passiert ist; wer mehr
        # braucht, zieht das Fenster auf. Acht machten es in der
        # Standardgröße höher als der Bildschirm bei 24 pt.
        self.protokoll.setMinimumHeight(self.fontMetrics().height() * 5)
        innen.addWidget(self.protokoll, 1)
        holen = QPushButton("Ereignisprotokoll holen")
        holen.setToolTip(
            "Die Meldungen des Dienstes aus dem Windows-Ereignisprotokoll – "
            "dort steht, warum ein Start fehlschlägt."
        )
        holen.clicked.connect(self._ereignisse)
        innen.addWidget(holen)
        senkrecht.addWidget(protokollkasten)

        self.auffrischen()

        # **Die Anfangsgröße kommt aus dem Inhalt, nicht aus zwei Zahlen.**
        # Geratene Maße sitzen falsch, sobald jemand die Schrift ändert –
        # und in MailBurg lässt sie sich einstellen. In der Standardgröße
        # wird nicht gerollt; der Rollbereich ist die Rückfalllinie für
        # kleine Bildschirme, nicht der Normalzustand.
        #
        # **Und genau deshalb darf hier nicht `self.sizeHint()` stehen.**
        # Ein Rollbereich meldet nach außen nur, dass er rollen kann –
        # nicht, wie hoch sein Inhalt ist. Mit `self.sizeHint()` ging
        # das Fenster 691 px hoch auf, während der Bildschirm noch
        # 392 px frei hatte, und rollte vom ersten Augenblick an. Der
        # Kommentar darüber sagte dabei schon das Richtige; nur der Code
        # tat es nicht. Gefragt wird deshalb das Widget *im*
        # Rollbereich (`mitte`), das die ganze Liste trägt – dieselbe
        # Stelle, an der `werkzeuge/screenshots_einrichtung.py` am
        # 06.10. über dasselbe gestolpert ist.
        self.resize(self.sizeHint().width(), self._wunschhoehe(rollen, mitte))

    def _wunschhoehe(self, rollen: QScrollArea, mitte: QWidget) -> int:
        """Wie hoch das Fenster aufgehen soll, damit nichts rollt.

        Zwei Dinge kommen zusammen, und keines davon ist geraten:

        **Die Höhe des Inhalts** steht in ``mitte``, nicht im
        Rollbereich und nicht im Fenster. Was oberhalb und unterhalb
        davon noch Platz braucht – Menüleiste, Rahmen –, ergibt sich
        als Unterschied zwischen dem, was das Fenster meldet, und dem,
        was der Rollbereich darin für sich verlangt.

        **Und der Bildschirm setzt die Grenze.** Auf einem kleinen oder
        entfernten Bildschirm reicht der Platz bei großer Schrift
        nicht – dann *soll* gerollt werden. Ein Fenster, das über den
        Rand hinausgeht, ist schlimmer als eines mit Rollbalken: Dort
        liegen die Knöpfe außerhalb des Sichtbaren.
        """
        zugabe = max(0, self.sizeHint().height() - rollen.sizeHint().height())
        hoehe = mitte.sizeHint().height() + zugabe
        schirm = self.screen()
        if schirm is not None:
            hoehe = min(hoehe, schirm.availableGeometry().height())
        return hoehe

    # ------------------------------------------------------------ Zustand

    def _umgebung_laden(self) -> Umgebung:
        """Was schon eingerichtet ist – aus der Registry, nicht geraten."""
        werte = einrichtung.gesetzte_variablen()
        from mailburg.server import einstellungen as lage

        from mailburg.core import paths

        ort = werte.get(lage.ARCHIV, "").strip()
        roh = werte.get(lage.ANSCHLUSS, "").strip()
        gemeinsam = (
            werte.get(paths.EINSTELLUNGEN, "").strip()
            or werte.get(paths.DATEN, "").strip()
        )
        return Umgebung(
            archiv=Path(ort) if ort else None,
            adresse=werte.get(lage.ADRESSE, "").strip() or lage.STANDARD_ADRESSE,
            anschluss=int(roh) if roh.isdigit() else lage.STANDARD_ANSCHLUSS,
            einstellungen=Path(gemeinsam) if gemeinsam else None,
            daten=Path(gemeinsam) if gemeinsam else None,
            abruf=int(takt) if (takt := werte.get(
                "MAILBURG_ABRUF", "").strip()).isdigit() else 0,
            abrufpause=werte.get("MAILBURG_ABRUF_PAUSE", "").strip(),
        )

    def _aus_den_feldern(self) -> Umgebung:
        ort = self.archivfeld.text().strip()
        gemeinsam = self.gemeinsamfeld.text().strip()
        return Umgebung(
            archiv=Path(ort) if ort else None,
            adresse=self.netz.currentData(),
            anschluss=self.port.value(),
            # **Ein Ordner für beides.** Einstellungen und Index getrennt
            # einstellbar zu machen, wäre zwei Felder für eine
            # Entscheidung, die niemand getrennt trifft.
            einstellungen=Path(gemeinsam) if gemeinsam else None,
            daten=Path(gemeinsam) if gemeinsam else None,
            # **Aus der alten Umgebung übernehmen, nicht aus einem Feld.**
            # Für den Abruf gibt es keines; er wird über seinen eigenen
            # Knopf gesetzt. Ohne diese Zeile fiele er bei jedem
            # »Übernehmen« heraus - derselbe Fehler wie heute Mittag mit
            # LOCALAPPDATA, nur eine Ebene höher.
            abruf=self.umgebung.abruf,
            abrufpause=self.umgebung.abrufpause,
        )

    def auffrischen(self) -> None:
        """Alles neu prüfen und die Liste neu malen."""
        self.umgebung = self._aus_den_feldern()
        bild = einrichtung.alles_pruefen(self.umgebung, self.stand)

        while self.listenlayout.count():
            altes = self.listenlayout.takeAt(0).widget()
            if altes is not None:
                altes.deleteLater()

        for befund in bild.befunde:
            self.listenlayout.addWidget(Zeile(befund, self._abhilfe))

        self._ampel_stellen(bild)

    def _ampel_stellen(self, bild) -> None:
        """Die Ampel und den Knopf daneben auf den Stand bringen."""
        lage = bild.ampel
        text, abhilfe = einrichtung.ampeltext(bild)
        knopf = KNOEPFE[abhilfe][0] if abhilfe in KNOEPFE else ""

        self.ampel.setText(ZEICHEN[lage] * 3)
        self.ampel.setStyleSheet(
            f"color: {FARBEN[lage]}; font-size: 20pt; font-weight: bold;"
        )
        self.ampeltext.setText(text)
        self._ampel_abhilfe = abhilfe
        self.ampelknopf.setText(knopf or "")
        self.ampelknopf.setVisible(bool(knopf))

    def _ampel_handeln(self) -> None:
        """Führt zu dem, was als Nächstes dran ist."""
        if self._ampel_abhilfe:
            self._abhilfe(self._ampel_abhilfe)

    def _warnung_pflegen(self) -> None:
        if self.netz.currentData() == "127.0.0.1":
            self.warnung.setText("")
            return
        self.warnung.setText(
            "Achtung: Im Netz spricht der Dienst HTTP. Anmeldename und "
            "Passwort gehen im Klartext über die Leitung. Für den "
            "dauerhaften Betrieb gehört ein Reverse Proxy mit TLS davor "
            "– unter Windows der IIS."
        )

    # ------------------------------------------------------------ Handeln

    def _abhilfe(self, was: str) -> None:
        if was == "archiv":
            self._archiv_waehlen()
        elif was == "zugang":
            self._zugaenge()
        elif was == "pakete":
            self._pakete()
        elif was == "uebernehmen":
            self._uebernehmen()
        elif was == "tresor":
            self._tresor()
        elif was == "abruf":
            self._abruf()
        elif was == "nachsehen":
            self._nach_updates_sehen()
        elif was == "aktualisieren":
            self._aktualisieren()
        elif was == "dienst_anlegen":
            self._dienst("anlegen")
        elif was == "dienst_start":
            self._dienst("starten")
        elif was == "starttyp":
            self._starttyp_richten()

    def _archiv_waehlen(self) -> None:
        ordner = QFileDialog.getExistingDirectory(
            self, "Archivordner wählen", self.archivfeld.text()
        )
        if ordner:
            self.archivfeld.setText(ordner)
            self.auffrischen()

    def _vorfuehrarchiv(self) -> None:
        ordner = QFileDialog.getExistingDirectory(
            self, "Wo soll das Vorführarchiv liegen? (leerer Ordner)"
        )
        if not ordner:
            return
        self._melden(f"Lege ein Vorführarchiv in »{ordner}« an …")
        try:
            from werkzeuge.vorfuehrarchiv import anlegen
        except ImportError:
            # In der gepackten Fassung liegt ``werkzeuge`` nicht daneben.
            self._melden(
                "Das Vorführarchiv lässt sich hier nicht anlegen – es "
                "gehört zum Quelltext, nicht zum Programm. Wählen Sie "
                "ein vorhandenes Archiv."
            )
            return
        try:
            anlegen(Path(ordner))
        except Exception as fehler:  # noqa: BLE001
            self._melden(f"Ging nicht: {fehler}")
            return
        self.archivfeld.setText(ordner)
        self._melden("Angelegt: 27 erfundene Mails, alle auf .example.")
        self.auffrischen()

    def _einlesen(self) -> None:
        """Post aus Dateien übernehmen – mit angehaltenem Dienst.

        **Der Dienst muss stehen, und er bleibt es danach.** Zwei
        Prozesse, die gleichzeitig ins selbe Archiv schreiben, reißen
        die Hash-Kette; das ist am 2026-09-21 passiert. Ihn hinterher
        von selbst wieder zu starten wäre bequem und falsch: Ein großer
        Einlesevorgang läuft über Stunden, und wer ihn nachts anstößt,
        will morgens selbst entscheiden, wann wieder Betrieb ist. Der
        Knopf *Starten* steht gleich daneben.
        """
        ort = self.archivfeld.text().strip()
        if not ort:
            QMessageBox.information(
                self, "Erst das Archiv",
                "Eingelesen wird in ein Archiv. Wählen Sie zuerst eines.",
            )
            return
        self._einlesen_mit_archiv(ort)

    def _wartung(self, ziel: str) -> None:
        """Verteiler der Wartungsknöpfe."""
        if ziel == "einlesen":
            self._einlesen()
        elif ziel == "pruefen":
            self._archiv_pruefen()
        elif ziel == "tresor_pruefen":
            self._tresor_pruefen()
        elif ziel == "bericht":
            self._bericht_einrichten()

    def _bericht_einrichten(self) -> None:
        """Wohin, wann und wie oft der Bericht geht.

        **Ein eigenes Postfach, nicht eines der archivierten.** Wer den
        Bericht über dasselbe Konto schickt, das archiviert wird,
        bekommt ihn beim nächsten Abruf ins Archiv zurück – und ein
        Archiv, das sich mit seinen eigenen Statusmeldungen füllt, ist
        ein schlechter Scherz.
        """
        from mailburg.core import bericht as berichtsmodul
        from mailburg.ui.berichtsdialog import Berichtsdialog

        dialog = Berichtsdialog(berichtsmodul.Lage.aus_umgebung(), self)
        if not dialog.exec():
            return

        neu, passwort = dialog.ergebnis()
        self._melden("Tagesbericht einstellen …")
        try:
            for zeile in einrichtung.werte_setzen(neu.als_variablen()):
                self._melden(f"  {zeile}")
        except OSError as fehler:
            self._melden(f"  Ging nicht: {fehler}")
            return

        if passwort:
            from mailburg.core import tresor

            if not tresor.verfuegbar():
                QMessageBox.warning(
                    self, "Kein Tresor",
                    "Das Versandpasswort gehört in den Tresor, und der ist "
                    "noch nicht eingerichtet. Ohne ihn stünde es im "
                    "Klartext neben der Konfiguration.\n\n"
                    "Richten Sie zuerst den Tresor ein; die übrigen "
                    "Angaben sind gespeichert.",
                )
            else:
                tresor.setzen(berichtsmodul.TRESORSCHLUESSEL, passwort)
                self._melden("  Versandpasswort im Tresor abgelegt.")

        self._melden(
            "Der Dienst liest das beim Starten – bitte einmal anhalten "
            "und starten."
        )
        self.auffrischen()

    def _archiv_pruefen(self) -> None:
        """Hash-Kette gegen Ablage – und sagen, was zu tun ist.

        **Ein Befund ohne Weg ist nur eine schlechte Nachricht.** Wer
        auf einem Server liest, dass die Hash-Kette beschädigt ist, muss
        erfahren, was das heißt und was er tun kann; sonst ruft er an
        und fragt, ob die Mails weg sind.
        """
        ort = self.archivfeld.text().strip()
        if not ort:
            QMessageBox.information(
                self, "Erst das Archiv",
                "Geprüft wird ein Archiv. Wählen Sie zuerst eines.",
            )
            return

        from mailburg.core.archive import Archive

        try:
            # Lesend: Eine Prüfung darf einen laufenden Abruf nicht
            # aussperren, und ändern will sie ohnehin nichts.
            with Archive.open(ort, exclusive=False) as archiv:
                bericht = archiv.verify()
        except Exception as fehler:  # noqa: BLE001
            QMessageBox.warning(self, "Archiv prüfen", str(fehler))
            return

        text, heikel = pruefbericht(bericht)
        self._melden(text.replace("\n", " · "))
        if heikel:
            QMessageBox.warning(self, "Archiv prüfen", text)
        else:
            QMessageBox.information(self, "Archiv prüfen", text)

    def _tresor_pruefen(self) -> None:
        """Reicht, was im Tresor liegt, für die eingerichteten Postfächer?"""
        from mailburg.core import accounts, tresor

        if not tresor.verfuegbar():
            QMessageBox.information(
                self, "Tresor",
                "Es ist kein Hauptschlüssel eingerichtet. Ohne ihn holt "
                "der Dienst keine Post – auf einem Arbeitsplatz ist das "
                "in Ordnung, auf einem Server nicht.",
            )
            return

        eintraege = tresor.eintraege()
        schlecht = []
        for name in eintraege:
            try:
                tresor.holen(name)
            except tresor.TresorFehler:
                schlecht.append(name)

        konten = accounts.Kontenliste().konten
        vorhanden = set(eintraege)
        ohne = [
            k.name for k in konten
            if k.schluessel not in vorhanden
            and not (k.per_oauth2 and k.token_schluessel in vorhanden)
        ]

        text, heikel = tresorbericht(len(eintraege), schlecht, ohne, len(konten))
        self._melden(text.replace("\n", " · "))
        if heikel:
            QMessageBox.warning(self, "Tresor prüfen", text)
        else:
            QMessageBox.information(self, "Tresor prüfen", text)

    def _einlesen_mit_archiv(self, ort: str) -> None:

        lief, _ = einrichtung.dienst_zustand()
        if lief is Lage.GUT:
            antwort = QMessageBox.question(
                self, "Dienst anhalten?",
                "Zum Einlesen muss der Dienst stehen – sonst schreiben "
                "zwei Vorgänge gleichzeitig ins Archiv.\n\n"
                "Er wird jetzt angehalten und bleibt es, bis Sie ihn "
                "mit »Starten« wieder in Betrieb nehmen. Solange ist "
                "das Archiv im Browser nicht erreichbar.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if antwort != QMessageBox.Yes:
                return
            geschafft, meldung = einrichtung.dienst_stoppen()
            self._melden(meldung)
            if not geschafft:
                QMessageBox.warning(
                    self, "Dienst läuft weiter",
                    "Der Dienst ließ sich nicht anhalten. Eingelesen wird "
                    "deshalb nicht – das Risiko für die Hash-Kette wäre "
                    "zu groß.\n\n" + meldung,
                )
                return
            self.auffrischen()

        from mailburg.core.archive import Archive
        from mailburg.ui.einlesen import Einlesedialog

        try:
            with Archive.open(ort, exclusive=True) as archiv:
                Einlesedialog(archiv, self).exec()
        except Exception as fehler:  # noqa: BLE001
            QMessageBox.warning(self, "Einlesen", str(fehler))
        finally:
            self.auffrischen()

    def _zugaenge(self) -> None:
        ort = self.archivfeld.text().strip()
        if not ort:
            QMessageBox.information(
                self, "Erst das Archiv",
                "Zugänge liegen im Archiv. Wählen Sie zuerst eines.",
            )
            return

        from mailburg.core.archive import Archive
        from mailburg.ui.zugaenge import Zugangsdialog

        try:
            with Archive.open(ort, exclusive=True) as archiv:
                Zugangsdialog(self, archiv).exec()
        except Exception as fehler:  # noqa: BLE001
            QMessageBox.warning(self, "Archiv", str(fehler))
            return
        self.auffrischen()

    def _pakete(self) -> None:
        """Den Befehl zeigen, statt ihn auszuführen.

        **pip im laufenden Programm wäre falsch.** Die gepackte Fassung
        hat gar kein pip, und in einer venv weiß nur der Mensch, welche
        gemeint ist. Ein Befehl zum Kopieren ist ehrlicher als ein Knopf,
        der manchmal wirkt.
        """
        fehlend = []
        for befund in einrichtung.alles_pruefen(self.umgebung).befunde:
            if befund.einzelheiten.startswith("pip install"):
                fehlend.append(befund.einzelheiten)
        if not fehlend:
            self._melden("Es fehlt kein Paket.")
            return
        self._melden(
            "In einer PowerShell als Administrator, im MailBurg-Ordner:\n  "
            + "\n  ".join(dict.fromkeys(fehlend))
        )

    def _uebernehmen(self) -> None:
        self.umgebung = self._aus_den_feldern()
        if self.umgebung.archiv is None:
            QMessageBox.information(
                self, "Kein Archiv", "Wählen Sie zuerst ein Archiv."
            )
            return
        if not einrichtung.ist_administrator():
            QMessageBox.warning(
                self, "Rechte fehlen",
                "Systemweite Einstellungen brauchen Administratorrechte. "
                "Starten Sie das Programm mit Rechtsklick → »Als "
                "Administrator ausführen«.",
            )
            return
        try:
            getan = einrichtung.variablen_setzen(self.umgebung)
        except OSError as fehler:
            self._melden(f"Ging nicht: {fehler}")
            return
        self._melden("Übernommen:\n  " + "\n  ".join(getan))
        self._melden(
            "Läuft der Dienst schon, muss er neu starten, damit er die "
            "neuen Werte liest."
        )
        self.auffrischen()

    def _dienst(self, was: str) -> None:
        handlung = {
            "anlegen": einrichtung.dienst_anlegen,
            "starten": einrichtung.dienst_starten,
            "stoppen": einrichtung.dienst_stoppen,
            "entfernen": einrichtung.dienst_entfernen,
        }[was]
        self._melden(f"Dienst {was} …")
        geklappt, ausgabe = handlung()
        self._melden(ausgabe or ("fertig." if geklappt else "ohne Ausgabe."))

        # **Nach dem Einrichten die Werte nachziehen.** Den Dienstschlüssel
        # gibt es erst jetzt; ein »Übernehmen« davor konnte ihn nicht
        # beschreiben. Wer sich darauf verlässt, dass der Mensch ein
        # zweites Mal drückt, baut auf eine Reihenfolge, die nirgends
        # steht – am 2026-10-02 hat genau das eine halbe Stunde gekostet.
        if geklappt and was == "anlegen" and self.umgebung.archiv:
            try:
                for zeile in einrichtung.variablen_setzen(self.umgebung):
                    self._melden(f"  {zeile}")
            except OSError as fehler:
                self._melden(f"  Einstellungen nicht geschrieben: {fehler}")

        if not geklappt:
            self._melden(
                "Der Grund steht meistens im Ereignisprotokoll – "
                "der Knopf darunter holt es."
            )
        self.auffrischen()

    def _nach_updates_sehen(self) -> None:
        """Einmal fragen und das Ergebnis behalten."""
        from mailburg.server import aktualisierung

        self._melden("Frage GitHub nach der neuesten Fassung …")
        self.stand = aktualisierung.nachsehen()
        if self.stand.fehler:
            self._melden(f"  {self.stand.fehler}")
            self._melden(
                "  Ohne Internet lässt sich das nicht feststellen – "
                "alles andere läuft weiter."
            )
        elif self.stand.neuer:
            self._melden(
                f"  {self.stand.draussen} ist draußen, hier läuft "
                f"{self.stand.hier}."
            )
            if self.stand.seite:
                self._melden(f"  {self.stand.seite}")
        else:
            self._melden(f"  {self.stand.hier} ist die neueste.")
        self.auffrischen()

    def _aktualisieren(self) -> None:
        """Neue Fassung einspielen – und den Dienst danach durchstarten.

        **In dieser Reihenfolge, mit Grund.** Solange der Dienst läuft,
        hat er seinen Code im Speicher; eine Installation daneben stört
        ihn nicht. Ihn vorher anzuhalten hieße: Steht etwas in pip quer,
        bleibt er unten – und zwar genau dann, wenn gerade jemand sucht.
        """
        from mailburg.server import aktualisierung

        if self.stand is None or not self.stand.neuer:
            self._melden("Nichts einzuspielen – erst nachsehen.")
            return

        antwort = QMessageBox.question(
            self, "Update einspielen?",
            f"Fassung {self.stand.draussen} wird geladen und installiert.\n\n"
            f"Der Dienst wird dabei einmal angehalten; wer gerade im "
            f"Browser sucht, muss die Seite neu laden.\n\n"
            f"Das Archiv wird nicht angefasst.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            self._melden("Abgebrochen.")
            return

        geklappt = aktualisierung.einspielen(self.stand, melden=self._melden)
        if not geklappt:
            self._melden("Es bleibt bei der alten Fassung.")
            self.auffrischen()
            return

        if einrichtung.ist_windows():
            self._melden("Dienst durchstarten …")
            for schritt, tun in (
                ("stoppen", einrichtung.dienst_stoppen),
                ("starten", einrichtung.dienst_starten),
            ):
                _, ausgabe = tun()
                self._melden(f"  {schritt}: {ausgabe.strip() or 'fertig'}")

        self._melden(
            "Fertig. **Dieses Fenster bitte schließen und neu öffnen** – "
            "es läuft noch mit dem alten Code im Speicher."
        )
        self.stand = None
        self.auffrischen()

    def _gemeinsam_waehlen(self) -> None:
        ordner = QFileDialog.getExistingDirectory(
            self, "Ordner für Einstellungen, Tresor und Suchindex",
            self.gemeinsamfeld.text(),
        )
        if ordner:
            self.gemeinsamfeld.setText(ordner)
            self.auffrischen()

    def _tresor(self) -> None:
        """Den Hauptschlüssel anlegen und dem Dienst beibringen."""
        self.umgebung = self._aus_den_feldern()
        if self.umgebung.einstellungen is None:
            QMessageBox.information(
                self, "Erst der gemeinsame Ordner",
                "Der Tresor muss dort liegen, wo der Dienst ihn findet. "
                "Wählen Sie oben einen gemeinsamen Ordner – etwa "
                "C:\\MailBurg-Daten.",
            )
            return
        if not einrichtung.ist_administrator():
            QMessageBox.warning(
                self, "Rechte fehlen",
                "Den Eintrag am Dienst darf nur ein Administrator "
                "schreiben. Starten Sie das Programm mit Rechtsklick → "
                "»Als Administrator ausführen«.",
            )
            return

        self._melden("Tresor einrichten …")
        for zeile in einrichtung.tresor_einrichten(self.umgebung):
            self._melden(f"  {zeile}")
        self.auffrischen()

    def _abruf(self) -> None:
        """Takt und Ruhezeit abfragen und beim Dienst eintragen.

        **Zwei Fragen, keine Maske.** Ein eigener Dialog für zwei Zahlen
        wäre mehr Fenster als Inhalt; Qt bringt für genau das etwas mit.
        """
        from PySide6.QtWidgets import QInputDialog

        self.umgebung = self._aus_den_feldern()
        if not einrichtung.ist_administrator():
            QMessageBox.warning(
                self, "Rechte fehlen",
                "Den Eintrag am Dienst darf nur ein Administrator "
                "schreiben.",
            )
            return

        takt, gut = QInputDialog.getInt(
            self, "Wie oft Post holen?",
            "Alle wie viel Minuten soll der Dienst nachsehen?\n\n"
            "30 ist ein vernünftiger Wert: neu genug, um nichts zu "
            "verpassen,\nselten genug, um den Mailserver nicht zu "
            "belästigen.\n\n0 schaltet den Abruf ab.",
            30, 0, 24 * 60, 5,
        )
        if not gut:
            return

        pause = ""
        if takt:
            # **Die Ruhezeit ist kein Beiwerk.** Läuft die nächtliche
            # Sicherung, während MailBurg ins Journal schreibt, erwischt
            # das Band einen Zwischenstand.
            pause, gut = QInputDialog.getText(
                self, "Wann soll Ruhe sein?",
                "Zeitraum, in dem nicht geholt wird – für die nächtliche "
                "Sicherung.\n\nFormat HH:MM-HH:MM, etwa 01:30-03:00. "
                "Leer lassen heißt: immer holen.",
                text=self.umgebung.abrufpause or "",
            )
            if not gut:
                return

        self.umgebung.abruf = takt
        self.umgebung.abrufpause = pause.strip()

        self._melden(
            f"Abruf: alle {takt} Minuten" if takt else "Abruf: aus"
        )
        try:
            for zeile in einrichtung.variablen_setzen(self.umgebung):
                self._melden(f"  {zeile}")
        except OSError as fehler:
            self._melden(f"  Ging nicht: {fehler}")
            return

        self._melden(
            "Der Dienst liest den Takt beim Starten – bitte einmal "
            "anhalten und starten."
        )
        self.auffrischen()

    def _verknuepfungen(self) -> None:
        self.umgebung = self._aus_den_feldern()
        self._melden("Lege Symbole an …")
        for zeile in einrichtung.verknuepfungen_anlegen(self.umgebung):
            self._melden(zeile)

    def _starttyp_richten(self) -> None:
        """Den Dienst neu anlegen, diesmal automatisch startend.

        Einen vorhandenen Dienst umzustellen ginge über ``sc config``;
        ihn abzubauen und neu anzulegen geht denselben Weg wie das erste
        Einrichten und hat damit einen Fehlerfall weniger.
        """
        self._melden("Dienst abbauen und neu einrichten …")
        for schritt in ("stoppen", "entfernen", "anlegen"):
            geklappt, ausgabe = {
                "stoppen": einrichtung.dienst_stoppen,
                "entfernen": einrichtung.dienst_entfernen,
                "anlegen": einrichtung.dienst_anlegen,
            }[schritt]()
            self._melden(f"  {schritt}: {ausgabe.strip() or 'fertig'}")
            if schritt == "anlegen" and geklappt and self.umgebung.archiv:
                try:
                    for zeile in einrichtung.variablen_setzen(self.umgebung):
                        self._melden(f"  {zeile}")
                except OSError as fehler:
                    self._melden(f"  Einstellungen: {fehler}")
        self.auffrischen()

    def _ereignisse(self) -> None:
        self._melden("--- Ereignisprotokoll ---")
        for zeile in einrichtung.ereignisse():
            self._melden(zeile)

    def _melden(self, text: str) -> None:
        self.protokoll.appendPlainText(text)
        leiste = self.protokoll.verticalScrollBar()
        leiste.setValue(leiste.maximum())


    def _wappen_setzen(self) -> None:
        """Das rote Wappen ins Fenster.

        **Es fehlte seit jeher**, und das fällt gerade hier auf: Wer das
        Fenster neben dem blauen Programmfenster in der Leiste hat,
        unterscheidet beide am Wappen. Ohne eines steht dort ein leeres
        Blatt – bei einem Programm, das Vertrauen wecken soll, wirkt das
        unnötig schäbig. Derselbe Befund wie am 2026-08-28 bei der
        gepackten Windows-Fassung.

        Fehlt die Datei, bleibt es beim leeren Blatt: Ein Symbol ist
        kein Grund, ein Fenster nicht zu öffnen.
        """
        from PySide6.QtGui import QIcon

        from mailburg import bilder

        for name in ("server/icon-256.png", "server/icon-64.png"):
            ort = bilder.finden(name)
            if ort is not None:
                self.setWindowIcon(QIcon(str(ort)))
                return


def starten() -> int:
    """Einstieg für ``mailburg-server-einrichten`` und die .exe."""
    import sys

    from PySide6.QtWidgets import QApplication

    from mailburg.ui import farben

    anwendung = QApplication.instance() or QApplication(sys.argv)
    # Dieselben drei Zeilen wie in ``ui/app.py``: Alle Farben kommen aus
    # der Systempalette, sonst sitzt das Fenster im dunklen Thema falsch.
    anwendung.setStyleSheet(farben.bereichsrahmen())
    farben.platzhalter_aufhellen(anwendung)
    farben.auswahlfelder_verbreitern(anwendung)
    fenster = Einrichtungsfenster()
    fenster.show()
    return anwendung.exec()


if __name__ == "__main__":
    raise SystemExit(starten())
