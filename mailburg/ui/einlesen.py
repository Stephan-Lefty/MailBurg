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
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from mailburg.ui.arbeit import Einleselauf, Läufer

def _kandidaten() -> list[tuple[str, Path]]:
    """Orte, an denen Mailprogramme ihre lokalen Ordner ablegen könnten.

    **Die Pfade kommen aus dem Kern, nicht von hier.** Bis zum
    2026-09-21 führte dieser Dialog eine eigene Liste – und die war eine
    andere als die, nach der MailBurg sonst sucht: Thunderbird stand
    darin mit seinem Flatpak-Ordner, Evolution nur mit dem gewohnten,
    und Thunderbirds Snap-Ordner fehlte ganz, obwohl
    ``local.thunderbird_profile_dirs()`` ihn seit jeher kennt.

    Gemeldet hat es ein Anwender mit Evolution aus Flatpak: Der Dialog
    bot ihm nichts an, obwohl seine Post da war. **Zwei Listen über
    dieselbe Sache laufen auseinander**, und zwar immer zu Lasten der
    zweiten – wer einen Pfad ergänzt, tut das dort, wo er gerade
    arbeitet. ``tests/test_einlesen_orte.py`` hält beide jetzt zusammen.
    """
    from mailburg.sources import local

    heim = Path.home()
    kandidaten: list[tuple[str, Path]] = []

    # Evolution legt seine lokalen Ordner nach Maildir++ ab. Genau
    # dieser Fall war es, der 2026-09-03 gemeldet wurde.
    for ort in local.evolution_mailordner():
        kandidaten.append(("Evolution – lokale Ordner", ort))
    for ort in local.thunderbird_profile_dirs():
        kandidaten.append(("Thunderbird", ort))

    kandidaten += [
        ("KMail / Akonadi", heim / ".local/share/local-mail"),
        ("Maildir im Benutzerordner", heim / "Maildir"),
        ("Mail im Benutzerordner", heim / "Mail"),
    ]
    return kandidaten


#: Vorgeschlagen wird nur, was es wirklich gibt – ein Vorschlag ins Leere
#: verwirrt mehr, als er hilft. Steht dieselbe Anwendung zweimal da (etwa
#: klassisch *und* aus Flatpak installiert), bekommt sie den Pfad
#: dahinter; ohne ihn wären zwei gleichnamige Einträge nicht zu
#: unterscheiden.
def _bekannte_orte() -> list[tuple[str, Path]]:
    vorhanden = [(name, ort) for name, ort in _kandidaten() if ort.exists()]

    mehrfach = {
        name for name, _ in vorhanden
        if sum(1 for anderer, _ in vorhanden if anderer == name) > 1
    }
    return [
        (f"{name} – {ort}" if name in mehrfach else name, ort)
        for name, ort in vorhanden
    ]


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

        # **Eine Liste, kein Feld – seit dem 2026-10-06.** Stephan hat
        # zweiunddreißig MailStore-Archive, die zu etwa zwanzig Menschen
        # gehören: eine Person hat oft ein altes Postfach, ein neues und
        # ein eigenes Benutzerarchiv. Alle drei gehören unter denselben
        # Kontonamen – und zweiunddreißig einzelne Läufe von Hand sind
        # zweiunddreißig Gelegenheiten, sich zu vertippen.
        self.liste = QListWidget()
        self.liste.setSelectionMode(QListWidget.ExtendedSelection)
        # Höhe aus der Schrift, nicht aus einer geratenen Pixelzahl –
        # sonst sitzt sie falsch, sobald jemand die Schrift ändert.
        self.liste.setMinimumHeight(self.fontMetrics().height() * 5)
        self.liste.setToolTip(
            "Alles hier Aufgeführte landet unter demselben Kontonamen.\n\n"
            "Mehrere Ordner sind der Normalfall, wenn ein Mensch über die "
            "Jahre mehrere Adressen hatte."
        )
        self.liste.itemSelectionChanged.connect(self._auswahl_geaendert)

        waehlen = QPushButton("Ordner hinzufügen …")
        waehlen.clicked.connect(self._waehlen)
        datei = QPushButton("MBOX-Datei …")
        datei.clicked.connect(self._datei_waehlen)
        self.entfernen = QPushButton("Entfernen")
        self.entfernen.setEnabled(False)
        self.entfernen.clicked.connect(self._entfernen)

        knopfspalte = QVBoxLayout()
        knopfspalte.addWidget(waehlen)
        knopfspalte.addWidget(datei)
        knopfspalte.addWidget(self.entfernen)
        knopfspalte.addStretch(1)

        zeile = QHBoxLayout()
        zeile.addWidget(self.liste, 1)
        zeile.addLayout(knopfspalte)

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

        # **In der Vorgabe aus.** Papierkorb und Spamverdacht hat der
        # Anwender schon einmal aussortiert; sie ins Archiv zu holen,
        # macht diese Entscheidung rückgängig. Beim Abruf aus einem
        # Postfach ist das seit jeher so – von der Platte kam bis zum
        # 2026-09-07 alles herein.
        self.alles = QCheckBox(
            "Papierkorb, Spamverdacht und Entwürfe mitnehmen"
        )
        self.alles.setToolTip(
            "In der Vorgabe bleiben diese Ordner draußen, wie beim Abruf "
            "aus einem Postfach.\n\n"
            "Für ein Geschäftsarchiv kann das Gegenteil richtig sein: Wer "
            "belegen muss, was ihn erreicht hat, will auch den "
            "Spamordner – dort landet regelmäßig Post, die dorthin nicht "
            "gehört."
        )
        self.alles.toggled.connect(self._pruefen)

        self.anhangstext = QCheckBox(
            "Text aus Anhängen mitlesen (PDF, Word, Tabellen)"
        )
        self.anhangstext.setChecked(True)
        self.anhangstext.setToolTip(
            "Macht die Anhänge durchsuchbar. Kostet Zeit – bei sehr "
            "großen Beständen kann man es später mit »Eingescannte PDF "
            "lesen« nachholen."
        )

        # **Nur sichtbar, wenn es mehr als eine Quelle gibt.** Bei einem
        # einzelnen Ordner ist die Frage sinnlos – und ein Häkchen, das
        # meistens nichts tut, lädt dazu ein, es einmal falsch zu setzen.
        #
        # **Vorgabe: jede Quelle behält ihre Struktur.** Stephans Urteil
        # vom 2026-10-06: »eigentlich wäre es sinnvoll, wenn jedes
        # Verzeichnis auch wie in MailStore eine eigene Struktur hat.«
        # Wer aus einem anderen Archivprogramm kommt, erkennt seinen
        # Baum wieder – und das Zusammenlegen ist die Entscheidung, die
        # man bewusst trifft, nicht das, was von selbst passiert.
        self.herkunft = QCheckBox(
            "Jede Quelle behält ihre eigene Ordnerstruktur"
        )
        self.herkunft.setChecked(True)
        self.herkunft.setToolTip(
            "Mit Häkchen bekommt jede Quelle ihren Verzeichnisnamen als "
            "Oberordner – der Baum sieht aus wie in MailStore, und man "
            "sieht später noch, woher eine Mail kam.\n\n"
            "Ohne Häkchen verschmelzen gleichnamige Ordner: Aus drei "
            "Posteingängen wird einer mit der Post aus allen dreien.\n\n"
            "Die Mails selbst behalten in beiden Fällen alles: Eine Suche "
            "nach der alten Adresse findet sie weiterhin."
        )
        self.herkunft.hide()
        self.herkunft.toggled.connect(self._pruefen)

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
        aufbau.addWidget(self.herkunft)
        aufbau.addWidget(self.alles)
        aufbau.addWidget(self.anhangstext)
        aufbau.addWidget(self.balken)
        aufbau.addStretch(1)
        aufbau.addWidget(self.knoepfe)

        self._vorschlagen()
        self._pruefen()

    # ------------------------------------------------------------ Wählen

    def _vorschlagen(self) -> None:
        """Trägt den ersten brauchbaren Ort ein, ohne ihn aufzudrängen.

        **Brauchbar heißt: MailBurg kann etwas damit anfangen.** Dass ein
        Verzeichnis existiert, sagt darüber nichts – ein leeres
        ``~/.local/share/evolution/mail/local`` bleibt stehen, wenn
        jemand von der klassischen Installation auf Flatpak wechselt, und
        wäre nach der bloßen Reihenfolge der erste Vorschlag gewesen.
        Vorgeschlagen würde dann genau der Ordner ohne Post.
        """
        orte = _bekannte_orte()
        if not orte:
            return

        ort = next((o for _, o in orte if self._taugt(o)), orte[0][1])
        self.pfade_setzen(ort)
        if len(orte) > 1:
            # Mit vollem Pfad, nicht nur mit dem Namen: Wer dieselbe
            # Anwendung klassisch und aus Flatpak installiert hat, sieht
            # sonst zweimal »Evolution« und weiß nicht, welches welches ist.
            weitere = ", ".join(str(o) for _, o in orte if o != ort)
            self.liste.setToolTip(f"Auch gefunden: {weitere}")

    @staticmethod
    def _taugt(ort: Path) -> bool:
        """Ob sich dieser Ort als Quelle öffnen lässt."""
        from mailburg.sources import local

        try:
            quelle = local.open_path(ort)
        except (ValueError, FileNotFoundError, OSError):
            return False
        quelle.close()
        return True

    # -------------------------------------------------------- Die Liste

    def pfade(self) -> list[Path]:
        """Die gewählten Quellen, in der Reihenfolge der Liste."""
        return [
            Path(self.liste.item(i).text()) for i in range(self.liste.count())
        ]

    def pfade_setzen(self, *orte) -> None:
        """Ersetzt die Liste – nimmt einzelne Pfade oder eine Folge davon."""
        gesammelt: list[str] = []
        for ort in orte:
            if isinstance(ort, (str, Path)):
                gesammelt.append(str(ort))
            else:
                gesammelt += [str(o) for o in ort]
        self.liste.clear()
        self.liste.addItems([o for o in gesammelt if o])
        self._nach_der_liste()

    def _hinzufuegen(self, ort: str) -> None:
        """Nimmt einen Ort auf – aber keinen zweimal.

        **Zweimal dieselbe Quelle wäre nicht schlimm, aber verwirrend.**
        Doppelt eingelesen wird nichts (der Inhaltshash entscheidet),
        die Liste sähe nur aus, als täte sie doppelte Arbeit.
        """
        if ort in [str(p) for p in self.pfade()]:
            return
        self.liste.addItem(ort)
        self._nach_der_liste()

    def _nach_der_liste(self) -> None:
        """Was sich ändert, wenn Quellen dazukommen oder wegfallen."""
        # Die Frage nach der Herkunft stellt sich erst ab zwei Quellen.
        self.herkunft.setVisible(self.liste.count() > 1)
        self._auswahl_geaendert()
        self._pruefen()

    def _auswahl_geaendert(self) -> None:
        self.entfernen.setEnabled(bool(self.liste.selectedItems()))

    def _entfernen(self) -> None:
        for eintrag in self.liste.selectedItems():
            self.liste.takeItem(self.liste.row(eintrag))
        self._nach_der_liste()

    def _waehlen(self) -> None:
        zuletzt = self.pfade()
        ort = QFileDialog.getExistingDirectory(
            self, "Mailordner auswählen",
            str(zuletzt[-1].parent) if zuletzt else str(Path.home()),
        )
        if ort:
            self._hinzufuegen(ort)

    def _datei_waehlen(self) -> None:
        zuletzt = self.pfade()
        ort, _ = QFileDialog.getOpenFileName(
            self, "MBOX-Datei auswählen",
            str(zuletzt[-1].parent) if zuletzt else str(Path.home()),
        )
        if ort:
            self._hinzufuegen(ort)

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
        orte = self.pfade()
        if not orte:
            self.befund.setText(self._kontowarnung())
            self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
            return

        if len(orte) == 1:
            gut, meldung = self._befund(orte[0])
            farbe = "" if gut else " color:palette(mid);"
            self.befund.setText(
                f"<span style='{farbe}'>{meldung}</span>{self._kontowarnung()}"
            )
            self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(gut)
            return

        # **Bei vielen Quellen zählt der Befund, nicht die Aufzählung.**
        # Zweiunddreißig Ordnerlisten untereinander liest niemand – und
        # sie würden den Dialog über den Bildschirm hinauswachsen lassen.
        # Interessant ist nur, ob eine davon klemmt.
        schlecht = [(ort, meldung) for ort, meldung in
                    ((o, self._befund(o)) for o in orte) if not meldung[0]]
        gut = not schlecht
        if gut:
            # **Wohin sie gehen, steht dabei.** Der Kontoname ist nach
            # dem Lauf nicht mehr zu ändern (es gibt keinen Befehl
            # dafür); wer ihn hier falsch liest, merkt es erst im Baum.
            ziel = self.konto.currentText().strip()
            wohin = f" nach »{ziel}«" if ziel else " – Kontoname fehlt noch"
            getrennt = (
                " Jede behält ihre eigene Ordnerstruktur."
                if self.herkunft.isChecked()
                else " Gleichnamige Ordner verschmelzen."
            )
            meldung = (
                f"<b>{len(orte)} Quellen</b>{wohin}.{getrennt}"
            )
        else:
            namen = ", ".join(ort.name for ort, _ in schlecht[:3])
            weiter = f" und {len(schlecht) - 3} weitere" if len(schlecht) > 3 else ""
            meldung = (
                f"<b>{len(schlecht)} von {len(orte)} Quellen klemmen:</b> "
                f"{namen}{weiter}.<br>"
                f"<span style='color:palette(mid)'>{schlecht[0][1][1]}</span>"
            )
        farbe = "" if gut else " color:palette(mid);"
        self.befund.setText(
            f"<span style='{farbe}'>{meldung}</span>{self._kontowarnung()}"
        )
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(gut)

    def _befund(self, ort: Path) -> tuple[bool, str]:
        from mailburg.sources import local

        if not ort.exists():
            return False, "Diesen Ordner gibt es nicht."
        try:
            quelle = local.open_path(ort, alles=self.alles.isChecked())
        except (ValueError, FileNotFoundError) as exc:
            return False, str(exc)
        try:
            ordner = quelle.folders()
        except Exception:  # noqa: BLE001 – der Befund darf nie scheitern
            ordner = []
        finally:
            quelle.close()

        # **Was draußen bleibt, steht daneben.** Eine stille Auslassung
        # wäre schlimmer als keine: Wer später eine Mail sucht, die nie
        # angekommen ist, hält das Archiv für unvollständig, ohne je zu
        # erfahren, dass es eine Entscheidung war.
        weg = sorted(getattr(quelle, "uebergangen", ()) or ())
        nachsatz = (
            f"<br><span style='color:palette(mid)'>Übergangen: "
            f"{', '.join(weg)} – Papierkorb, Spamverdacht und Entwürfe "
            f"bleiben draußen.</span>"
            if weg else ""
        )

        if not ordner:
            return True, f"Erkannt: {quelle.describe()}{nachsatz}"
        gezeigt = ", ".join(ordner[:6])
        rest = f" und {len(ordner) - 6} weitere" if len(ordner) > 6 else ""
        return True, (
            f"<b>Erkannt:</b> {quelle.describe()}<br>"
            f"{len(ordner)} Ordner: {gezeigt}{rest}{nachsatz}"
        )

    # ------------------------------------------------------------ Laufen

    def _starten(self) -> None:
        orte = self.pfade()
        if not orte:
            return
        # **Der Rückfall auf den Ordnernamen gilt nur bei einer Quelle.**
        # Bei mehreren wäre er eine Lotterie: Welcher der zweiunddreißig
        # Namen soll es sein? Deshalb verlangt der Dialog dort einen.
        name = self.konto.currentText().strip() or orte[0].name

        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
        self.knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        self.balken.show()

        auftrag = Einleselauf(
            self.archiv.root, orte, name,
            mit_anhangstext=self.anhangstext.isChecked(),
            alles=self.alles.isChecked(),
            zusammenlegen=not self.herkunft.isChecked(),
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
