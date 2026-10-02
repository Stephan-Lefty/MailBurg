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
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

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
        self.setWindowTitle("MailBurg im Browser – einrichten")
        self.umgebung = self._umgebung_laden()

        mitte = QWidget()
        self.setCentralWidget(mitte)
        senkrecht = QVBoxLayout(mitte)

        senkrecht.addWidget(Fliesstext(
            "<p>Hier wird eingerichtet, was nötig ist, damit das Archiv im "
            "Browser erreichbar ist – auf diesem Rechner und, wenn Sie es "
            "wollen, im Netz.</p>"
            "<p>Die Liste prüft sich selbst. Wo etwas fehlt, steht der "
            "Knopf daneben.</p>"
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
        self.resize(self.sizeHint())

    # ------------------------------------------------------------ Zustand

    def _umgebung_laden(self) -> Umgebung:
        """Was schon eingerichtet ist – aus der Registry, nicht geraten."""
        werte = einrichtung.gesetzte_variablen()
        from mailburg.server import einstellungen as lage

        ort = werte.get(lage.ARCHIV, "").strip()
        roh = werte.get(lage.ANSCHLUSS, "").strip()
        return Umgebung(
            archiv=Path(ort) if ort else None,
            adresse=werte.get(lage.ADRESSE, "").strip() or lage.STANDARD_ADRESSE,
            anschluss=int(roh) if roh.isdigit() else lage.STANDARD_ANSCHLUSS,
        )

    def _aus_den_feldern(self) -> Umgebung:
        ort = self.archivfeld.text().strip()
        return Umgebung(
            archiv=Path(ort) if ort else None,
            adresse=self.netz.currentData(),
            anschluss=self.port.value(),
        )

    def auffrischen(self) -> None:
        """Alles neu prüfen und die Liste neu malen."""
        self.umgebung = self._aus_den_feldern()
        bild = einrichtung.alles_pruefen(self.umgebung)

        while self.listenlayout.count():
            altes = self.listenlayout.takeAt(0).widget()
            if altes is not None:
                altes.deleteLater()

        for befund in bild.befunde:
            self.listenlayout.addWidget(Zeile(befund, self._abhilfe))

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
