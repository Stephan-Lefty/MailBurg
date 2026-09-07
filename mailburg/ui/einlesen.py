"""Lokale Mailordner ins Archiv einlesen – Maildir, MBOX, Thunderbird.

**Der Anlass ist eine Rückmeldung vom 2026-09-03.** Ein Anwender
wünschte sich, MailBurg möge »auch Mails aus lokalen Ordnern im MBox-
oder Maildir-Format auslesen und archivieren« können. Es konnte das seit
der ersten Fassung – nur ausschließlich über ``mailburg importieren`` im
Terminal. Im Fenster gab es dafür keinen einzigen Menüpunkt.

Das ist die eigentliche Lehre: **Eine Funktion, die niemand findet, gibt
es für den Anwender nicht.** Der Wunsch nach etwas Vorhandenem ist ein
Befund über die Oberfläche, nicht über den Funktionsumfang.

Der Dialog erklärt deshalb auch, *was* eingelesen werden kann, und zeigt
schon vor dem Start, was MailBurg im gewählten Ordner erkannt hat. Wer
den Namen »Maildir« nicht kennt, soll trotzdem sehen, ob er das Richtige
gewählt hat.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from mailburg.ui.arbeit import Einleselauf, Läufer

#: Orte, an denen Mailprogramme ihre lokalen Ordner ablegen. Sie werden
#: nur vorgeschlagen, wenn es sie wirklich gibt – ein Vorschlag ins Leere
#: verwirrt mehr, als er hilft.
def _bekannte_orte() -> list[tuple[str, Path]]:
    heim = Path.home()
    kandidaten = [
        # Evolution legt seine lokalen Ordner nach Maildir++ ab. Genau
        # dieser Fall war es, der 2026-09-03 gemeldet wurde.
        ("Evolution – lokale Ordner", heim / ".local/share/evolution/mail/local"),
        ("Thunderbird", heim / ".thunderbird"),
        ("Thunderbird (Flatpak)",
         heim / ".var/app/org.mozilla.Thunderbird/.thunderbird"),
        ("KMail / Akonadi", heim / ".local/share/local-mail"),
        ("Maildir im Benutzerordner", heim / "Maildir"),
        ("Mail im Benutzerordner", heim / "Mail"),
    ]
    return [(name, ort) for name, ort in kandidaten if ort.exists()]


class Einlesedialog(QDialog):
    """Fragt nach Ordner und Kontonamen und liest dann ein."""

    def __init__(self, archiv, eltern=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        self.laeufer = None
        self.setWindowTitle("Lokale Mailordner einlesen")

        erklaerung = QLabel(
            "<p>MailBurg kann Post aus Dateien auf Ihrer Platte übernehmen – "
            "auch aus Postfächern, die es online längst nicht mehr gibt.</p>"
            "<p><b>Erkannt werden:</b> Thunderbird-Profile mit allen Konten "
            "und Unterordnern, Maildir-Verzeichnisse (so legt Evolution "
            "seine lokalen Ordner ab), einzelne MBOX-Dateien und "
            "Verzeichnisse voller <tt>.eml</tt>-Dateien.</p>"
            "<p>Gelesen wird nur. An den Dateien ändert MailBurg nichts.</p>"
        )
        erklaerung.setWordWrap(True)
        # Ohne das drückt Qt umbrechenden Text zusammen, statt nach der
        # nötigen Höhe zu fragen - siehe die Runden vom 2026-08-31.
        erklaerung.setSizePolicy(
            erklaerung.sizePolicy().horizontalPolicy(),
            erklaerung.sizePolicy().verticalPolicy(),
        )
        erklaerung.sizePolicy().setHeightForWidth(True)

        self.pfad = QLineEdit()
        self.pfad.setPlaceholderText("Noch kein Ordner gewählt")
        self.pfad.textChanged.connect(self._pruefen)

        waehlen = QPushButton("Ordner auswählen …")
        waehlen.clicked.connect(self._waehlen)
        datei = QPushButton("MBOX-Datei …")
        datei.clicked.connect(self._datei_waehlen)

        zeile = QHBoxLayout()
        zeile.addWidget(self.pfad, 1)
        zeile.addWidget(waehlen)
        zeile.addWidget(datei)

        # **Zur Auswahl, nicht zum Abtippen.** Wer alte Post zu einem
        # Postfach einliest, das längst abgerufen wird, muss denselben
        # Namen treffen – ein »Firma « mit Leerzeichen oder ein kleines
        # »firma« ergibt stillschweigend einen zweiten Zweig im
        # Postfachbaum, und dieselbe Adresse steht zweimal da.
        #
        # Am 2026-09-07 aus Stephans Lage: Er exportiert ein Postfach
        # aus MailStore, das im Archiv weiterläuft.
        #
        # **Editierbar bleibt es trotzdem**, denn der häufigere Fall ist
        # ein Bestand, der zu keinem laufenden Postfach gehört.
        self.konto = QComboBox()
        self.konto.setEditable(True)
        self.konto.lineEdit().setPlaceholderText("z. B. Alt-Thunderbird")
        self.konto.addItem("")
        for name in self._vorhandene_konten():
            self.konto.addItem(name)
        self.konto.setToolTip(
            "Unter diesem Namen erscheinen die Mails später im "
            "Postfachbaum. Bleibt das Feld leer, nimmt MailBurg den "
            "Namen des Ordners.\n\n"
            "Zur Auswahl stehen die Postfächer, die es hier schon gibt: "
            "Wer alte Post zu einem davon einliest, wählt es aus – dann "
            "steht alles zusammen."
        )
        self.konto.currentTextChanged.connect(self._pruefen)

        self.befund = QLabel()
        self.befund.setWordWrap(True)
        self.befund.setTextFormat(Qt.RichText)

        self.anhangstext = QCheckBox(
            "Text aus Anhängen mitlesen (PDF, Word, Tabellen)"
        )
        self.anhangstext.setChecked(True)
        self.anhangstext.setToolTip(
            "Macht die Anhänge durchsuchbar. Kostet Zeit – bei sehr "
            "großen Beständen kann man es später mit »Eingescannte PDF "
            "lesen« nachholen."
        )

        felder = QFormLayout()
        felder.addRow("Woher:", zeile)
        felder.addRow("Kontoname:", self.konto)

        self.balken = QProgressBar()
        self.balken.setRange(0, 0)
        self.balken.hide()

        self.knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.knoepfe.button(QDialogButtonBox.Ok).setText("Einlesen")
        self.knoepfe.accepted.connect(self._starten)
        self.knoepfe.rejected.connect(self._abbrechen_oder_schliessen)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(erklaerung)
        aufbau.addLayout(felder)
        aufbau.addWidget(self.befund)
        aufbau.addWidget(self.anhangstext)
        aufbau.addWidget(self.balken)
        aufbau.addStretch(1)
        aufbau.addWidget(self.knoepfe)

        self._vorschlagen()
        self._pruefen()

    # ------------------------------------------------------------ Wählen

    def _vorschlagen(self) -> None:
        """Trägt den ersten gefundenen Ort ein, ohne ihn aufzudrängen."""
        orte = _bekannte_orte()
        if not orte:
            return
        name, ort = orte[0]
        self.pfad.setText(str(ort))
        if len(orte) > 1:
            weitere = ", ".join(n for n, _ in orte[1:])
            self.pfad.setToolTip(f"Auch gefunden: {weitere}")

    def _waehlen(self) -> None:
        ort = QFileDialog.getExistingDirectory(
            self, "Mailordner auswählen", self.pfad.text() or str(Path.home())
        )
        if ort:
            self.pfad.setText(ort)

    def _datei_waehlen(self) -> None:
        ort, _ = QFileDialog.getOpenFileName(
            self, "MBOX-Datei auswählen", self.pfad.text() or str(Path.home())
        )
        if ort:
            self.pfad.setText(ort)

    # ------------------------------------------------------------ Prüfen

    def _vorhandene_konten(self) -> list[str]:
        """Postfächer, die es in diesem Archiv schon gibt.

        **Aus dem Archiv, nicht aus der Kontenliste.** Gefragt ist, unter
        welchem Namen hier bereits Post liegt – dazu zählen auch früher
        eingelesene Bestände, die nie ein IMAP-Konto hatten. Die
        eingerichteten Postfächer kommen dazu, denn eines davon kann
        eingerichtet, aber noch nie abgerufen worden sein.
        """
        namen = set()
        try:
            namen |= {konto for konto, _, _ in self.archiv.index.accounts()}
        except Exception:  # noqa: BLE001 – die Liste darf nie den Dialog kosten
            pass
        try:
            from mailburg.core.accounts import Kontenliste

            namen |= {k.name for k in Kontenliste().konten}
        except Exception:  # noqa: BLE001
            pass
        return sorted(namen)

    def _kontowarnung(self) -> str:
        """Warnt vor einem Namen, der einem vorhandenen fast gleicht.

        **Fast ist hier das Gefährliche.** »firma« und »Firma « sehen im
        Postfachbaum aus wie derselbe Eintrag, sind aber zwei – und wer
        alte Post zu einem laufenden Postfach einliest, merkt es erst,
        wenn er sie dort sucht und nicht findet.
        """
        getippt = self.konto.currentText().strip()
        if not getippt:
            return ""
        vorhanden = self._vorhandene_konten()
        if getippt in vorhanden:
            return ""
        for name in vorhanden:
            if name.casefold() == getippt.casefold():
                return (
                    f"<br><b>Achtung:</b> Es gibt hier schon »{name}«. "
                    f"Mit »{getippt}« entsteht ein zweiter Eintrag im "
                    f"Postfachbaum, der genauso aussieht."
                )
        return ""

    def _pruefen(self) -> None:
        """Sagt vor dem Start, was MailBurg dort erkannt hat.

        **Sonst erfährt man es erst nach dem Klick.** Wer »Maildir« nicht
        kennt, kann einem Pfadfeld nicht ansehen, ob er das Richtige
        gewählt hat – der Befund darunter beantwortet genau das.
        """
        text = self.pfad.text().strip()
        gut = False
        if not text:
            self.befund.setText(self._kontowarnung())
        else:
            gut, meldung = self._befund(Path(text))
            farbe = "" if gut else " color:palette(mid);"
            self.befund.setText(
                f"<span style='{farbe}'>{meldung}</span>{self._kontowarnung()}"
            )
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(gut)

    @staticmethod
    def _befund(ort: Path) -> tuple[bool, str]:
        from mailburg.sources import local

        if not ort.exists():
            return False, "Diesen Ordner gibt es nicht."
        try:
            quelle = local.open_path(ort)
        except (ValueError, FileNotFoundError) as exc:
            return False, str(exc)
        try:
            ordner = quelle.folders()
        except Exception:  # noqa: BLE001 – der Befund darf nie scheitern
            ordner = []
        finally:
            quelle.close()

        if not ordner:
            return True, f"Erkannt: {quelle.describe()}"
        gezeigt = ", ".join(ordner[:6])
        rest = f" und {len(ordner) - 6} weitere" if len(ordner) > 6 else ""
        return True, (
            f"<b>Erkannt:</b> {quelle.describe()}<br>"
            f"{len(ordner)} Ordner: {gezeigt}{rest}"
        )

    # ------------------------------------------------------------ Laufen

    def _starten(self) -> None:
        ort = Path(self.pfad.text().strip())
        name = self.konto.currentText().strip() or ort.name

        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        self.balken.show()

        auftrag = Einleselauf(
            self.archiv.root, ort, name,
            mit_anhangstext=self.anhangstext.isChecked(),
        )
        auftrag.meldung.connect(self.befund.setText)
        auftrag.fertig.connect(self._fertig)
        auftrag.gescheitert.connect(self._gescheitert)

        self.laeufer = Läufer(auftrag)
        self.laeufer.starten()

    def _abbrechen_oder_schliessen(self) -> None:
        """Der zweite Knopf bedeutet zweierlei, je nach Lage."""
        if self.laeufer is not None:
            self.laeufer.auftrag.abbrechen()
            self.befund.setText("Wird abgebrochen …")
            return
        self.reject()

    def _fertig(self, stat) -> None:
        self.laeufer = None
        self.balken.hide()
        QMessageBox.information(
            self,
            "Eingelesen",
            f"{stat.gelesen} Nachrichten gelesen, {stat.neu} neu ins "
            f"Archiv aufgenommen.\n\n"
            + (
                f"{stat.vorhanden} waren schon da – dieselbe Mail zweimal "
                f"einzulesen erzeugt keine zweite Datei.\n"
                if stat.vorhanden else ""
            )
            + (
                f"{stat.fehlgeschlagen} ließen sich nicht lesen und wurden "
                f"übergangen."
                if stat.fehlgeschlagen else ""
            ),
        )
        self.accept()

    def _gescheitert(self, text: str) -> None:
        self.laeufer = None
        self.balken.hide()
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(True)
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Schließen")
        QMessageBox.critical(self, "Einlesen gescheitert", text)
