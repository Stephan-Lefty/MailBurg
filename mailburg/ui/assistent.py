"""Die Ersteinrichtung: Archiv anlegen, Postfächer eintragen.

Wer MailBurg zum ersten Mal startet, hat weder Archiv noch Konten. Genau
das ist der Teil, den bisher nur die Kommandozeile konnte – und niemand
tippt freiwillig ``konten hinzufuegen --server … --port 143 --starttls``.

Drei Schritte, mehr nicht: Wohin kommt das Archiv, welche Postfächer, und
dann läuft es. Was Thunderbird schon weiß, wird übernommen; die Passwörter
gibt der Anwender einmal ein, sie wandern in den Schlüsselbund.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from mailburg import APP_NAME, QUELLTEXT_URL
from mailburg.core import accounts, orte
from mailburg.core.accounts import Konto, Kontenliste
from mailburg.core.archive import Archive, ArchiveError, Mode
from mailburg.core.retention import QUELLEN, Jurisdiction
from mailburg.ui import bilder, farben
from mailburg.ui.arbeit import Anmeldeprobe, Läufer, alle_abbrechen
from mailburg.ui.zeitplan import Zeitplanwahl


def _schluesselbund_satz() -> str:
    """Benennt den Schlüsselbund beim Namen, statt ihn zu umschreiben.

    Wer wissen will, wo sein Passwort gelandet ist, sucht nach einem
    Programm in seinem Menü – nicht nach »dem Schlüsselbund des Systems«.
    """
    name = accounts.schluesselbund_name()
    if not name:
        # Den Grund nennen, nicht bloß die Folge: Fehlt das Paket
        # keyring, ist »auf diesem Rechner nicht erreichbar« schlicht
        # falsch - der Rechner hat einen, MailBurg wurde nur ohne den
        # passenden Zusatz installiert.
        return f"<b>nirgends</b>: {accounts.schluesselbund_lage()[1]}"
    return f"in die <b>{name}</b>"


def sichtbarkeit_anbieten(feld: QLineEdit) -> None:
    """Rüstet ein Passwortfeld mit einer Umschaltung auf Klartext aus.

    App-Passwörter sind lange Zeichenfolgen ohne Sinn, die man aus einer
    Weboberfläche abschreibt. Sie blind einzutippen und danach nur zu
    erfahren, dass die Anmeldung nicht klappte, ist eine Zumutung –
    besonders, weil man den Fehler nicht findet.

    Die Umschaltung sitzt im Feld selbst und nicht daneben: So bleibt sie
    dem Auge nahe an der Stelle, um die es geht, und braucht keinen Platz
    in einer ohnehin engen Zeile.
    """
    from PySide6.QtGui import QIcon

    zeigen = QIcon.fromTheme("view-visible")
    verbergen = QIcon.fromTheme("view-hidden")

    if zeigen.isNull() or verbergen.isNull():
        # Ohne Symbolthema – etwa unter Windows – tut es ein Wort. Besser
        # als eine Schaltfläche, die man nicht sieht.
        zeigen = QIcon()
        verbergen = QIcon()

    aktion = feld.addAction(zeigen, QLineEdit.TrailingPosition)
    aktion.setToolTip("Passwort anzeigen")
    if zeigen.isNull():
        aktion.setText("Zeigen")

    def umschalten() -> None:
        versteckt = feld.echoMode() == QLineEdit.Password
        feld.setEchoMode(QLineEdit.Normal if versteckt else QLineEdit.Password)
        aktion.setIcon(verbergen if versteckt else zeigen)
        aktion.setToolTip("Passwort verbergen" if versteckt else "Passwort anzeigen")
        if zeigen.isNull():
            aktion.setText("Verbergen" if versteckt else "Zeigen")

    aktion.triggered.connect(umschalten)


class PasswortNachfrage(QDialog):
    """Fragt nach einem Passwort, wenn die Anmeldung nicht geklappt hat.

    Eine Warnung, die man nur wegklicken kann, lässt den Anwender ratlos
    zurück: Er weiß, dass es nicht ging, aber der Weg zurück ins Feld ist
    seine Sache. Hier kann er es gleich richtigstellen – oder das Postfach
    für diesmal auslassen und später nachholen.
    """

    def __init__(self, konto: Konto, grund: str, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Anmeldung nicht möglich")
        self.setMinimumWidth(560)

        kopf = QLabel(
            f"<b>{konto.name}</b> lässt sich nicht abrufen."
        )
        kopf.setTextFormat(Qt.RichText)

        erklaerung = QLabel(grund)
        erklaerung.setWordWrap(True)
        erklaerung.setEnabled(False)

        rat = QLabel(self._rat(konto, grund))
        rat.setWordWrap(True)
        rat.setTextFormat(Qt.RichText)
        rat.setOpenExternalLinks(True)

        self.passwort = QLineEdit()
        self.passwort.setEchoMode(QLineEdit.Password)
        self.passwort.setPlaceholderText("Passwort erneut eingeben")
        self.passwort.setAccessibleName(f"Passwort für {konto.name}")
        sichtbarkeit_anbieten(self.passwort)
        self.passwort.returnPressed.connect(self.accept)

        knoepfe = QDialogButtonBox()
        self.erneut = knoepfe.addButton(
            "Erneut versuchen", QDialogButtonBox.AcceptRole
        )
        self.ueberspringen = knoepfe.addButton(
            "Dieses Postfach auslassen", QDialogButtonBox.RejectRole
        )
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(kopf)
        aufbau.addWidget(erklaerung)
        aufbau.addSpacing(8)
        aufbau.addWidget(rat)
        aufbau.addSpacing(8)
        aufbau.addWidget(self.passwort)
        aufbau.addWidget(knoepfe)

    @staticmethod
    def _rat(konto: Konto, grund: str) -> str:
        """Ein Hinweis, der zum Fehler passt – keine allgemeine Belehrung."""
        if not grund:
            return ""

        if "abgelehnt" in grund or "AUTHENTICATIONFAILED" in grund.upper():
            anbieter = konto.server.lower()
            if any(
                name in anbieter
                for name in ("gmail", "google", "gmx", "web.de", "outlook", "office365")
            ):
                return (
                    "Dieser Anbieter lässt das Kennwort der Weboberfläche für "
                    "den Zugriff von außen nicht zu. Sie brauchen ein eigens "
                    "erzeugtes <b>App-Passwort</b> aus den Sicherheits"
                    "einstellungen Ihres Kontos."
                )
            if konto.ist_lokale_bruecke:
                return (
                    "Bei einem Brückenprogramm wie der Proton Mail Bridge gilt "
                    "<b>nicht</b> das Passwort Ihres Kontos beim Anbieter, "
                    "sondern das, welches die Brücke selbst anzeigt."
                )
            return (
                "Der Server hat Benutzernamen oder Passwort abgelehnt. Prüfen "
                "Sie beides – mit dem Auge rechts im Feld können Sie das "
                "Passwort im Klartext sehen."
            )

        if "Keine Verbindung" in grund:
            return (
                "Der Server war nicht erreichbar. Das kann an der "
                "Internetverbindung liegen, an einem Tippfehler im Servernamen "
                "– oder daran, dass ein Brückenprogramm gerade nicht läuft."
            )

        if "Zertifikat" in grund:
            return (
                "Das ist kein Passwortproblem. Sie können hier abbrechen und "
                "das Postfach von Hand mit dem vorgeschlagenen Servernamen "
                "eintragen."
            )
        return ""


class WillkommenSeite(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Willkommen")
        self.setSubTitle(
            f"{APP_NAME} archiviert Ihre E-Mail an einem Ort, den Sie "
            f"bestimmen, und macht sie durchsuchbar."
        )

        # Das Banner gehört hierher, nicht in eine Ecke: Wer ein Programm
        # zum ersten Mal startet, soll sehen, dass er beim richtigen ist.
        self.banner = QLabel()
        self.banner.setAlignment(Qt.AlignCenter)
        bild = bilder.banner(520)
        if bild is not None:
            self.banner.setPixmap(bild)
        else:
            self.banner.hide()

        text = QLabel(
            "<p>In zwei Schritten ist alles eingerichtet: <b>wohin</b> Ihr "
            "Archiv kommt und <b>welche Postfächer</b> hinein sollen.</p>"

            "<p style='margin-top:14px'><b>Ihre Postfächer werden nur "
            "gelesen.</b> Mehr nicht. MailBurg löscht dort nichts, verschiebt "
            "nichts und markiert nichts als gelesen. In Ihrem Mailprogramm "
            "sieht hinterher alles aus wie vorher; was ungelesen war, ist es "
            "weiterhin. Und sollten Sie MailBurg eines Tages nicht mehr "
            "verwenden, finden Sie Ihre Postfächer unverändert vor.</p>"

            "<p><b>Wohin Ihre Post geht,</b> bestimmen Sie gleich selbst: auf "
            "die Platte im Rechner, auf eine externe Platte oder in Ihre "
            "eigene Nextcloud.</p>"
            "<p>Die Cloud ist dabei ausdrücklich vorgesehen und keine "
            "Notlösung. Jede Mail ist eine eigene Datei, und was einmal "
            "abgelegt ist, ändert sich nie wieder – das ist ja der Sinn "
            "eines Archivs. Ihre Cloud muss jede Mail deshalb genau einmal "
            "übertragen und danach nie wieder anfassen. Programme, die alles "
            "in eine einzige große Datei schreiben, müssen die bei jeder "
            "neuen Nachricht erneut abgleichen.</p>"
            "<p><b>Was nicht passiert:</b> MailBurg baut Verbindungen "
            "ausschließlich zu Ihren eigenen Mailservern auf, um die Post "
            "abzuholen. Sonst zu niemandem. Es gibt keine Anmeldung bei uns, "
            "keinen Lizenzschlüssel und keine Kennnummer, unter der Sie "
            "irgendwo geführt würden. Es wird auch nicht gezählt, wie oft Sie "
            "das Programm öffnen oder wonach Sie suchen, und es werden keine "
            "Fehlerberichte verschickt.</p>"
            "<p><b>Auch nicht nach Aktualisierungen.</b> Viele Programme "
            "fragen beim Start beim Hersteller nach, ob es eine neuere "
            "Fassung gibt. Das klingt harmlos, ist aber ein regelmäßiger "
            "Anruf, bei dem Ihr Rechner verrät, dass und wann jemand das "
            "Programm benutzt – mitsamt Ihrer Internetadresse. MailBurg tut "
            "das nicht. Der Preis dafür: Sie erfahren von neuen Fassungen "
            "nicht von selbst, sondern müssen gelegentlich nachsehen.</p>"
            f"<p><b>Transparenz ist uns wichtig:</b> Der gesamte "
            f"{farben.verweis(QUELLTEXT_URL, 'Quelltext')} ist offen einsehbar – "
            f"wer nachprüfen möchte, was das Programm tut, kann es tun, und "
            f"wer es selbst nicht kann, kann jemanden fragen, der es kann. "
            f"Das ist der Unterschied zu einem Versprechen.</p>"

            "<p><b>Sie bleiben unabhängig.</b> Jede Mail liegt einzeln im "
            "Archiv, in dem Format, in dem Mails nun einmal gespeichert "
            "werden. Auch ohne MailBurg kommen Sie an jede einzelne heran – "
            "mit jedem Mailprogramm, das <i>.eml</i>-Dateien öffnen kann. Sie "
            "sind an dieses Programm nicht gebunden.</p>"

            f"<p><b>Ihre Passwörter</b> brauchen wir, um die Postfächer "
            f"abzurufen – sonst nichts. Sie kommen {_schluesselbund_satz()}, "
            f"also dorthin, wo auch Ihr Mailprogramm seine Passwörter "
            f"aufbewahrt. In keine Datei, die man kopieren könnte, und schon "
            f"gar nicht ins Internet.</p>"

            "<p style='margin-top:14px'><i>Sie haben schon ein Archiv? Geben "
            "Sie im nächsten Schritt dessen Ordner an – MailBurg erkennt es "
            "und verwendet es weiter.</i></p>"
        )
        text.setWordWrap(True)
        text.setTextFormat(Qt.RichText)
        # Ohne das wäre der Verweis nur blauer Text: Qt öffnet Adressen im
        # Browser erst, wenn man es ausdrücklich erlaubt.
        text.setOpenExternalLinks(True)
        text.setTextInteractionFlags(
            Qt.TextBrowserInteraction | Qt.TextSelectableByMouse
        )

        rollbar = QScrollArea()
        rollbar.setWidget(text)
        rollbar.setWidgetResizable(True)
        rollbar.setFrameShape(QScrollArea.NoFrame)
        # **Der Rollbalken bleibt sichtbar.** Auf 1280 x 800 - keine
        # seltene Größe, viele ältere Notebooks haben sie - passt dieser
        # Text nicht auf eine Seite. Qt blendet den Balken dann zwar ein,
        # aber so zurückhaltend, dass man ihn übersieht: Der Text wirkt
        # zu Ende, und wer nicht scrollt, erfährt nie, dass MailBurg
        # nichts nach Hause meldet und die Passwörter im Schlüsselbund
        # liegen. Ausgerechnet das, wofür dieser Text da ist.
        #
        # Gekürzt wird er nicht - die Ausführlichkeit ist Absicht. Also
        # muss sichtbar sein, dass es weitergeht (2026-08-28).
        rollbar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(self.banner)
        aufbau.addWidget(rollbar, 1)


class ArchivSeite(QWizardPage):
    """Wohin das Archiv kommt und nach welchen Regeln es geführt wird."""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Das Archiv")
        self.setSubTitle("Wo sollen Ihre Mails liegen?")

        # Was tatsächlich zur Verfügung steht, statt eines einzelnen
        # Vorschlags: Dass der Ort frei wählbar ist, sieht man einem
        # Eingabefeld nicht an – und was hinter »Auswählen…« steckt,
        # erfährt nur, wer daraufklickt.
        self.orte = orte.vorschlagen()
        self.ortswahl = QComboBox()
        self.ortswahl.setAccessibleName("Ablageort")
        for ort in self.orte:
            beschriftung = ort.beschriftung
            if ort.freier_platz:
                beschriftung += f"   ({ort.freier_platz})"
            self.ortswahl.addItem(beschriftung, ort)
        self.ortswahl.addItem("Anderer Ordner …", None)
        self.ortswahl.currentIndexChanged.connect(self._ort_gewaehlt)

        self.pfad = QLineEdit()
        self.pfad.setPlaceholderText("noch nichts gewählt")
        self.pfad.setText(str(self.orte[0].pfad) if self.orte else str(Path.home()))
        # Damit Vorlesehilfen etwas anzusagen haben.
        self.pfad.setAccessibleName("Ort des Archivs")

        blaettern = QPushButton("Auswählen …")
        blaettern.clicked.connect(self._waehlen)

        zeile = QHBoxLayout()
        zeile.addWidget(self.pfad, 1)
        zeile.addWidget(blaettern)


        self.platzhinweis = QLabel()
        self.platzhinweis.setWordWrap(True)
        self.platzhinweis.hide()

        # **Warum »Weiter« grau ist.** Das Archiv soll bewusst platziert
        # werden, deshalb legt MailBurg keinen Ordner von sich aus an -
        # wer zwanzig Jahre Post irgendwohin legt, soll diesen Ort
        # ausgewählt haben. Nur sah man dem toten Knopf das nicht an: Im
        # Feld stand ein Pfad, der Knopf blieb grau, und der naheliegende
        # Schluss war "das Programm ist kaputt". Am 2026-08-27 unter
        # Windows aufgefallen, wo der vorgeschlagene Ordner regelmäßig
        # noch nicht existiert.
        self.ordnerhinweis = QLabel()
        self.ordnerhinweis.setWordWrap(True)
        self.ordnerhinweis.hide()
        self.pfad.textChanged.connect(self._ordner_pruefen)

        hinweis = QLabel(
            "<p>Eine interne Platte, eine externe Platte oder ein Ordner, den "
            "Nextcloud abgleicht – alles möglich. Sie können das Archiv "
            "später auch verschieben; MailBurg findet es wieder.</p>"
            "<p><b>Was in diesem Ordner entsteht:</b> ein Unterordner "
            "<i>mail</i> mit Ihren Nachrichten, nach Monaten sortiert, und "
            "ein Unterordner <i>meta</i> mit dem Protokoll darüber, was wann "
            "aufgenommen wurde. Sonst nichts.</p>"
            "<p><b>Dieser Ordner braucht eine Sicherung.</b> Solange Ihre "
            "Post auch noch im Postfach liegt, wäre ein Plattendefekt "
            "ärgerlich. Sobald Sie aber anfangen, das Postfach zu entlasten, "
            "ist dieses Archiv die <i>einzige</i> Kopie – und dann hängt "
            "alles an einer einzigen Platte.</p>"
            "<p>Deshalb: möglichst nicht auf derselben Platte wie das "
            "System, und in jedem Fall regelmäßig woandershin sichern. Der "
            "Suchindex gehört nicht dazu – der liegt getrennt und lässt sich "
            "jederzeit aus dem Archiv neu erzeugen.</p>"
        )
        hinweis.setWordWrap(True)
        hinweis.setTextFormat(Qt.RichText)

        self.privat = QRadioButton("Privatarchiv")
        self.privat.setChecked(True)
        self.geschaeftlich = QRadioButton("Geschäftsarchiv")

        privat_text = QLabel(
            "Für Ihre eigene Post. Keine Aufbewahrungsfristen, löschen "
            "können Sie jederzeit. Das entspricht der Rechtslage: Wer "
            "ausschließlich eigene Mails archiviert, unterliegt der DSGVO "
            "gar nicht."
        )
        geschaeft_text = QLabel(
            "Für geschäftliche Post. Jeder Vorgang wird protokolliert und "
            "die Kette der Einträge gegen nachträgliche Änderungen "
            "gesichert; gelöscht wird nur mit Vermerk, und "
            "Aufbewahrungsfristen bremsen zu frühes Löschen.\n\n"
            "MailBurg unterstützt damit einen revisionssicheren Betrieb – "
            "herstellen kann ihn keine Software allein. Dazu gehören eine "
            "Verfahrensdokumentation und geregelte Abläufe bei Ihnen im "
            "Betrieb. Wer etwas anderes verspricht, macht Sie angreifbar."
        )
        for beschriftung in (privat_text, geschaeft_text):
            beschriftung.setWordWrap(True)
            beschriftung.setIndent(24)
            beschriftung.setEnabled(False)

        self.rechtsraum = QComboBox()
        for gebiet, name in (
            (Jurisdiction.DE, "Deutschland"),
            (Jurisdiction.AT, "Österreich"),
            (Jurisdiction.CH, "Schweiz"),
        ):
            self.rechtsraum.addItem(name, gebiet)
        self.rechtsraum.setEnabled(False)
        self.rechtsraum.setAccessibleName("Rechtsraum für die Aufbewahrungsfristen")

        # Die Fundstelle zum gewählten Recht, damit niemand unserer
        # Zusammenfassung glauben muss. Amtliche Quellen, keine
        # Kanzleiseiten.
        self.quelle = QLabel()
        self.quelle.setOpenExternalLinks(True)
        self.quelle.setTextFormat(Qt.RichText)
        self.quelle.setWordWrap(True)
        self.quelle.setIndent(4)
        self.rechtsraum.currentIndexChanged.connect(self._quelle_erneuern)

        fristen = QFormLayout()
        fristen.addRow("Fristen nach dem Recht von:", self.rechtsraum)
        fristen.addRow("", self.quelle)
        self.geschaeftlich.toggled.connect(self.rechtsraum.setEnabled)
        self.geschaeftlich.toggled.connect(self.quelle.setEnabled)
        self.quelle.setEnabled(False)

        art = QGroupBox("Wofür ist das Archiv?")
        innen = QVBoxLayout(art)
        innen.addWidget(self.privat)
        innen.addWidget(privat_text)
        innen.addWidget(self.geschaeftlich)
        innen.addWidget(geschaeft_text)
        innen.addLayout(fristen)

        inhalt = QWidget()
        innen = QVBoxLayout(inhalt)
        innen.setContentsMargins(0, 0, 12, 0)
        innen.addWidget(QLabel("Wo soll das Archiv liegen?"))
        innen.addWidget(self.ortswahl)
        innen.addWidget(self.pfad_beschriftung())
        innen.addLayout(zeile)
        innen.addWidget(self.ordnerhinweis)
        innen.addWidget(self.platzhinweis)
        innen.addWidget(hinweis)
        innen.addSpacing(12)
        innen.addWidget(art)
        innen.addStretch()

        # Wie auf der Willkommensseite: Lieber rollen als abschneiden.
        # Ortsauswahl, Erklärung, Betriebsart und Fundstelle zusammen
        # brauchen mehr Höhe, als ein Fenster vernünftigerweise hat.
        rollbar = QScrollArea()
        rollbar.setWidget(inhalt)
        rollbar.setWidgetResizable(True)
        rollbar.setFrameShape(QScrollArea.NoFrame)
        # Wie auf der Willkommensseite: sichtbar, dass es weitergeht.
        rollbar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        rollbar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        aufbau = QVBoxLayout(self)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.addWidget(rollbar)

        self._quelle_erneuern()
        self.registerField("archivpfad*", self.pfad)

        # Einmal von Hand: Der Hinweis hängt sonst an einem Wechsel, und
        # der findet für die Vorauswahl nie statt - ausgerechnet dort, wo
        # er am nötigsten ist.
        if self.orte:
            self._ort_gewaehlt(0)

    def _quelle_erneuern(self) -> None:
        """Zeigt die Vorschrift, nach der gerechnet wird."""
        gebiet = self.rechtsraum.currentData()
        bezeichnung, adresse = QUELLEN[gebiet]
        self.quelle.setText(
            f"Maßgeblich ist {farben.verweis(adresse, bezeichnung)}. "
            f"MailBurg rechnet danach – entscheiden müssen Sie oder Ihre "
            f"Steuerberatung."
        )

    def pfad_beschriftung(self) -> QLabel:
        beschriftung = QLabel("Vollständiger Pfad:")
        beschriftung.setBuddy(self.pfad)
        return beschriftung

    def _ordner_pruefen(self, text: str) -> None:
        """Sagt, wenn der gewählte Ordner noch nicht existiert.

        Ohne Vorwurf und ohne Ausrufezeichen: Es ist kein Fehler, einen
        Ordner noch nicht angelegt zu haben. Es muss nur dastehen.
        """
        wo = text.strip()
        if wo and not Path(wo).expanduser().is_dir():
            self.ordnerhinweis.setText(
                "Diesen Ordner gibt es noch nicht. Wählen Sie über "
                "<i>Auswählen …</i> einen vorhandenen aus oder legen Sie ihn "
                "dort an – erst dann geht es weiter."
            )
            self.ordnerhinweis.setTextFormat(Qt.RichText)
            self.ordnerhinweis.show()
        else:
            self.ordnerhinweis.hide()

    def _ort_gewaehlt(self, stelle: int) -> None:
        ort = self.ortswahl.itemData(stelle)
        if ort is None:
            # "Anderer Ordner …" - dann gleich den Dateidialog öffnen.
            self._waehlen()
            return

        self.pfad.setText(str(ort.pfad))

        if ort.auf_systemplatte:
            self.platzhinweis.setText(
                "<b>Das liegt auf derselben Platte wie Ihr System.</b> Geht "
                "sie kaputt, sind Rechner und Archiv zugleich weg. Eine "
                "zweite Platte oder Ihre Cloud wäre sicherer – und in jedem "
                "Fall braucht das Archiv eine Sicherung."
            )
            self.platzhinweis.setTextFormat(Qt.RichText)
            self.platzhinweis.show()
            return

        if ort.eng:
            self.platzhinweis.setText(
                f"<b>Wenig Platz:</b> Dort sind nur noch {ort.freier_platz.split(' von')[0]}. "
                f"Ein Mailarchiv wächst über die Jahre – rechnen Sie mit "
                f"etwa der Hälfte dessen, was Ihre Postfächer belegen."
            )
            self.platzhinweis.setTextFormat(Qt.RichText)
            self.platzhinweis.show()
        elif ort.art == "extern":
            self.platzhinweis.setText(
                "Auf einer externen Platte ist das Archiv nur erreichbar, "
                "solange sie angesteckt ist. Der Abruf im Hintergrund "
                "scheitert dann, solange sie fehlt – verloren geht dabei "
                "nichts, es wird nur nachgeholt."
            )
            self.platzhinweis.setTextFormat(Qt.RichText)
            self.platzhinweis.show()
        elif ort.art == "cloud":
            self.platzhinweis.setText(
                "Gut gewählt: In der Cloud liegt das Archiv auch dann noch, "
                "wenn dieser Rechner einmal ausfällt. Nur sollten nicht zwei "
                "Rechner gleichzeitig hineinschreiben – MailBurg verhindert "
                "das mit einer Sperre."
            )
            self.platzhinweis.setTextFormat(Qt.RichText)
            self.platzhinweis.show()
        else:
            self.platzhinweis.hide()

    def _waehlen(self) -> None:
        gewaehlt = QFileDialog.getExistingDirectory(
            self, "Ordner für das Archiv", self.pfad.text()
        )
        if gewaehlt:
            ziel = Path(gewaehlt)
            # Wer einen leeren Ordner wählt, meint ihn selbst. Wer sein
            # Benutzerverzeichnis wählt, meint das sicher nicht - dort
            # kommt ein Unterordner hinein.
            if ziel == Path.home() or any(ziel.iterdir()):
                ziel = ziel / orte.VORGABENAME
            self.pfad.setText(str(ziel))

    @property
    def betriebsart(self) -> Mode:
        return Mode.GESCHAEFTLICH if self.geschaeftlich.isChecked() else Mode.PRIVAT

    def validatePage(self) -> bool:
        ziel = Path(self.pfad.text()).expanduser()

        if (ziel / "archive.json").exists():
            antwort = QMessageBox.question(
                self,
                "Archiv vorhanden",
                f"In {ziel} liegt bereits ein Archiv.\n\n"
                f"Möchten Sie dieses weiterverwenden?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if antwort == QMessageBox.Yes:
                self.wizard().archiv_pfad = ziel
                return True
            return False

        if ziel.exists() and any(ziel.iterdir()):
            QMessageBox.warning(
                self,
                "Ordner nicht leer",
                f"In {ziel} liegen bereits Dateien.\n\nBitte wählen Sie einen "
                f"leeren oder einen neuen Ordner – so bleibt später "
                f"nachvollziehbar, was zum Archiv gehört und was nicht.",
            )
            return False

        try:
            archiv = Archive.create(
                ziel,
                mode=self.betriebsart,
                jurisdiction=self.rechtsraum.currentData(),
            )
        except (ArchiveError, OSError) as exc:
            QMessageBox.critical(self, "Anlegen gescheitert", str(exc))
            return False

        # Die Kennung merken, nicht nur den Pfad: Postfächer werden ihr
        # zugeordnet, und ein Archiv auf einer externen Platte liegt
        # morgen woanders.
        self.wizard().archiv_kennung = archiv.uuid
        archiv.close()
        self.wizard().archiv_pfad = ziel
        return True


class KontoZeile(QWidget):
    """Ein Postfach im Einrichtungsschritt, mit Passwortfeld und Zustand."""

    def __init__(self, konto: Konto, gitter: QGridLayout, zeile: int) -> None:
        super().__init__()
        self.konto = konto
        self.laeufer: Läufer | None = None

        self.ankreuz = QCheckBox(konto.name)
        self.ankreuz.setChecked(True)
        self.ankreuz.setToolTip(f"{konto.benutzer} auf {konto.server}:{konto.port}")

        # Nur das zeigen, was nicht schon im Namen steht. Bei Konten aus
        # Thunderbird ist der Name die Mailadresse – sie ein zweites Mal
        # danebenzuschreiben, füllt die Zeile ohne jeden Gewinn.
        if konto.name.casefold() == konto.benutzer.casefold():
            beschreibung = f"{konto.server}:{konto.port}"
        else:
            beschreibung = f"{konto.benutzer} — {konto.server}:{konto.port}"
        if konto.ist_lokale_bruecke:
            beschreibung += "   (Brücke auf diesem Rechner)"
        self.beschreibung = QLabel(beschreibung)
        self.beschreibung.setEnabled(False)
        # Umbrechen statt überstehen: Eine lange Adresse auf einem
        # Brückenport ist breiter als manches Fenster.
        self.beschreibung.setWordWrap(True)
        # Nebeneinander bräuchten Name und Beschreibung zusammen mehr
        # Breite, als ein Fenster vernünftigerweise hat – dann steht die
        # Hälfte außerhalb, und man rollt waagerecht.
        self.beschreibung.setIndent(22)

        self.passwort = QLineEdit()
        self.passwort.setEchoMode(QLineEdit.Password)
        self.passwort.setPlaceholderText("Passwort")
        self.passwort.setAccessibleName(f"Passwort für {konto.name}")
        self.passwort.setMinimumWidth(190)
        sichtbarkeit_anbieten(self.passwort)

        self.zustand = QLabel("")
        self.zustand.setWordWrap(True)
        self.zustand.setMinimumWidth(150)

        # Zwei Zeilen je Postfach: oben Name, Passwort und Zustand,
        # darunter eingerückt, worum es sich handelt.
        oben = zeile * 2
        gitter.addWidget(self.ankreuz, oben, 0)
        gitter.addWidget(self.passwort, oben, 1)
        gitter.addWidget(self.zustand, oben, 2)
        gitter.addWidget(self.beschreibung, oben + 1, 0, 1, 3)

        # **Der freie Platz gehört ganz nach unten.** Ohne diese Zeile
        # verteilt QGridLayout ihn gleichmäßig auf alle Zeilen - bei
        # einem einzigen Postfach steht der Name dann oben und die
        # Beschreibung in der Mitte des Fensters, mit einer Handbreit
        # Leere dazwischen. Am 2026-08-28 in der Windows-Fassung
        # aufgefallen, wo genau ein Postfach eingetragen war.
        # Die Dehnung wandert mit: Zeile `oben + 2` war beim vorigen
        # Postfach noch das Ende der Liste und muss zurückgenommen
        # werden, sonst klafft es mittendrin.
        gitter.setRowStretch(oben, 0)
        gitter.setRowStretch(oben + 1, 0)
        gitter.setRowStretch(oben + 2, 1)

    @property
    def gewaehlt(self) -> bool:
        return self.ankreuz.isChecked()

    def melden(self, text: str, gut: bool | None = None) -> None:
        self.zustand.setStyleSheet(farben.stil(gut))
        self.zustand.setText(text)


class KontenSeite(QWizardPage):
    """Postfächer eintragen – vorbelegt aus Thunderbird, wenn vorhanden."""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Ihre Postfächer")
        self.setSubTitle("Welche Postfächer sollen archiviert werden?")
        self.zeilen: list[KontoZeile] = []
        self._laeufer: list[Läufer] = []
        self._zu_zeile: dict = {}
        self._durchgewinkt = False
        self._offen = 0

        self.herkunft = QLabel()
        self.herkunft.setWordWrap(True)

        self.gitter = QGridLayout()
        self.gitter.setColumnStretch(0, 1)   # Name darf wachsen
        self.gitter.setColumnStretch(1, 0)   # Passwortfeld bleibt, wie es ist
        self.gitter.setColumnStretch(2, 0)   # Zustand ebenso
        self.gitter.setVerticalSpacing(2)

        inhalt = QWidget()
        inhalt.setLayout(self.gitter)
        rollbereich = QScrollArea()
        rollbereich.setWidget(inhalt)
        rollbereich.setWidgetResizable(True)
        rollbereich.setMinimumHeight(260)
        # Waagerecht rollen zu müssen ist immer ein Fehler im Aufbau.
        rollbereich.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        weiteres = QPushButton("Weiteres Postfach von Hand eintragen …")
        weiteres.clicked.connect(self._von_hand)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(self.herkunft)
        aufbau.addWidget(rollbereich, 1)
        aufbau.addWidget(weiteres)

    def initializePage(self) -> None:
        if self.zeilen:
            return
        self._aus_thunderbird_laden()

    def _aus_thunderbird_laden(self) -> None:
        from mailburg.core import uebernahme
        from mailburg.sources import local

        gefunden: list[Konto] = []
        vergeben: set[str] = set()

        for profil in local.find_thunderbird_profiles():
            try:
                funde = uebernahme.aus_thunderbird(profil)
            except (FileNotFoundError, OSError):
                continue
            # Was sich nicht über IMAP abrufen lässt, wird stillschweigend
            # übergangen. Es aufzuzählen hieße, in einem Mailarchiv fremde
            # Postfächer aufzulisten - darunter Testprofile ganz anderer
            # Programme, die in MailBurg nichts verloren haben.
            brauchbar = [f for f in funde if f.brauchbar]
            uebernahme.namen_entzerren(brauchbar, vergeben)
            gefunden += [f.konto for f in brauchbar]

        bund = accounts.schluesselbund_name()
        ablage = (
            f"Ihre Passwörter kommen in die <b>{bund}</b>"
            if bund
            else f"<b>Achtung:</b> {accounts.schluesselbund_lage()[1]} "
                 f"Gespeichert werden sie nicht."
        )

        if gefunden:
            text = (
                f"<p><b>{len(gefunden)} Postfächer aus Thunderbird "
                f"übernommen.</b> Server, Benutzername und Verschlüsselung "
                f"sind bereits eingetragen – ergänzen Sie bitte nur noch die "
                f"Passwörter.</p>"

                f"<p><b>Warum müssen Sie die Passwörter noch einmal "
                f"eingeben?</b> Weil MailBurg sie aus Thunderbird nicht "
                f"ausliest. Technisch ginge das – aber ein Programm, das die "
                f"Passwörter anderer Programme abgreift, verhält sich wie "
                f"Schadsoftware. Einem Archiv vertrauen Sie jahrzehntealte "
                f"Post an; dieses Vertrauen ist mehr wert als die gesparte "
                f"Tipparbeit. Übernommen haben wir deshalb nur die "
                f"Einstellungen, die in einer gewöhnlichen Textdatei stehen.</p>"

                f"<p>{ablage}. Verwendet werden sie ausschließlich, um Ihre "
                f"Post abzuholen. Jedes Postfach wird gleich einmal "
                f"ausprobiert, damit Sie sofort sehen, ob es klappt.</p>"
            )
        else:
            text = (
                "<p><b>Kein Thunderbird-Profil gefunden.</b> Tragen Sie Ihre "
                "Postfächer bitte von Hand ein – Sie brauchen dafür den "
                "IMAP-Server Ihres Anbieters, Ihre Mailadresse und das "
                "Passwort.</p>"
                f"<p>{ablage}.</p>"
                "<p><i>Bei Gmail, GMX, Web.de und Outlook genügt das Kennwort "
                "der Weboberfläche nicht – diese Anbieter verlangen ein eigens "
                "erzeugtes App-Passwort.</i></p>"
            )
        self.herkunft.setText(text)

        for konto in gefunden:
            self._zeile_anlegen(konto)

    def _zeile_anlegen(self, konto: Konto) -> None:
        zeile = KontoZeile(konto, self.gitter, len(self.zeilen))

        # Dasselbe Postfach nicht zweimal einrichten. Der Name ist frei
        # gewählt und sagt darüber nichts aus - wer beim ersten Mal "Firma"
        # eingetragen hat, bekäme es hier als "post@firma.de" erneut
        # angeboten und riefe es fortan doppelt ab.
        schon_da = Kontenliste().finden_nach_postfach(konto.benutzer, konto.server)
        if schon_da is not None:
            # Nicht vorangekreuzt, aber auch nicht gesperrt: Es könnte
            # Gründe geben, dasselbe Postfach ein zweites Mal einzurichten.
            # Die Entscheidung bleibt beim Anwender, er soll sie nur nicht
            # aus Versehen treffen.
            zeile.ankreuz.setChecked(False)
            zeile.melden(f"schon als »{schon_da.name}« eingerichtet")
            zeile.bereits_da = True

        self.zeilen.append(zeile)

    def _von_hand(self) -> None:
        dialog = KontoDialog(self)
        if dialog.exec():
            self._zeile_anlegen(dialog.konto())

    def validatePage(self) -> bool:
        if self._durchgewinkt:
            # Die Anmeldungen laufen nebenläufig. Deshalb sagt diese
            # Methode zunächst Nein und schickt die Seite selbst weiter,
            # sobald alle Antworten da sind - und genau dieses
            # Weiterschicken landet hier ein zweites Mal. Wer das nicht
            # abfängt, prüft erneut, schickt erneut weiter, prüft erneut:
            # Die Zustandsspalte flackerte zwischen »prüfe …« und »in
            # Ordnung«, und der Mailserver bekam bei jedem Umlauf drei
            # frische Anmeldungen.
            self._durchgewinkt = False
            return True

        zu_pruefen = [z for z in self.zeilen if z.gewaehlt]
        if not zu_pruefen:
            # Schon eingerichtete Postfächer sind Grund genug weiterzugehen.
            # Es müssen ausdrücklich nicht *alle* sein: Wer acht Postfächer
            # hat, sechs eingerichtet und zwei bewusst ausgelassen, wurde
            # hier sonst festgehalten und um eine Auswahl gebeten, die er
            # gerade absichtlich nicht getroffen hat.
            fertige = [z for z in self.zeilen if getattr(z, "bereits_da", False)]
            if fertige:
                self.wizard().konten = [z.konto for z in fertige]
                return True
            # **Fragen, nicht verbieten.** »Ohne Postfach gibt es nichts
            # zu archivieren« stimmt nicht: Wer ein Archiv anlegt, um
            # ein Thunderbird-Profil oder eine Sicherung hineinzulesen,
            # braucht kein Postfach. Bis zum 2026-08-29 kam er hier
            # nicht weiter – aufgefallen, als Stephan für die Anleitung
            # ein Beispielarchiv anlegen wollte.
            antwort = QMessageBox.question(
                self,
                "Kein Postfach gewählt",
                "Ohne Postfach wird beim Abruf nichts geholt.\n\n"
                "Das kann gewollt sein – etwa für ein Archiv, in das Sie "
                "nur ein Thunderbird-Profil oder eine Sicherung "
                "einlesen. Postfächer lassen sich jederzeit nachtragen "
                "unter Einstellungen → Postfächer verwalten.\n\n"
                "Ohne Postfach fortfahren?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if antwort == QMessageBox.Yes:
                self.wizard().konten = []
                return True
            return False

        # Ein eingerichtetes Postfach hat sein Passwort im Schlüsselbund;
        # das Eingabefeld bleibt deshalb absichtlich leer. Wer nur aufs
        # Feld schaut, hält es für vergessen und fragt danach - nach einem
        # Passwort, das MailBurg längst besitzt und schon erprobt hat.
        versorgt = [z for z in zu_pruefen if self._schon_versorgt(z)]
        neu = [z for z in zu_pruefen if z not in versorgt]

        ohne_passwort = [z for z in neu if not z.passwort.text()]
        for zeile in ohne_passwort:
            # Nicht ermahnen, sondern fragen. Wer acht Postfächer vor sich
            # hat, übersieht leicht eines - ihn dann zurückzuschicken, statt
            # ihm das Feld hinzuhalten, ist unnötige Arbeit.
            dialog = PasswortNachfrage(
                zeile.konto,
                "Für dieses Postfach fehlt noch das Passwort.",
                self,
            )
            if dialog.exec() and dialog.passwort.text():
                zeile.passwort.setText(dialog.passwort.text())
            else:
                zeile.ankreuz.setChecked(False)
                zeile.melden("ohne Passwort übergangen")
                zeile.zustand.setToolTip(
                    "Sie können dieses Postfach später über "
                    "»Postfächer verwalten« nachtragen."
                )

        zu_pruefen = [z for z in neu if z.gewaehlt and z.passwort.text()]
        if not zu_pruefen:
            # Nichts Neues zu prüfen. Sind versorgte Postfächer angekreuzt,
            # ist alles beisammen und es geht weiter.
            if any(z.gewaehlt for z in versorgt):
                self._speichern()
                return True
            return False

        # Anmeldungen laufen nebenläufig; die Seite gibt erst frei, wenn
        # alle durch sind. Sonst stünde der Anwender vor einem Fenster, das
        # sich nicht mehr rührt.
        self._offen = len(zu_pruefen)
        self._weiter_freigeben(False)
        for zeile in zu_pruefen:
            self._pruefen(zeile)
        return False

    def _pruefen(self, zeile: KontoZeile) -> None:
        zeile.melden("prüfe …")
        auftrag = Anmeldeprobe(zeile.konto, zeile.passwort.text())
        laeufer = Läufer(auftrag)
        self._laeufer.append(laeufer)

        # Gebundene Methoden dieser Seite, ausdrücklich keine Lambdas.
        # Siehe die Regel in ``ui/arbeit.py``: Ein Lambda hat keine
        # Fadenzugehörigkeit, Qt ruft es deshalb im Arbeitsfaden auf – und
        # die Zeilen darunter fassen Widgets an. Welche Zeile gemeint ist,
        # steht im Wörterbuch; den Auftrag liefert ``sender()``.
        self._zu_zeile[auftrag] = zeile
        auftrag.fertig.connect(self._probe_geglueckt)
        auftrag.gescheitert.connect(self._probe_gescheitert)
        laeufer.starten()

    def _probe_geglueckt(self, ordner: list[str]) -> None:
        zeile = self._zu_zeile.pop(self.sender(), None)
        if zeile is not None:
            self._geklappt(zeile, ordner)

    def _probe_gescheitert(self, text: str) -> None:
        zeile = self._zu_zeile.pop(self.sender(), None)
        if zeile is not None:
            self._misslungen(zeile, text)

    def _geklappt(self, zeile: KontoZeile, ordner: list[str]) -> None:
        zeile.melden(f"in Ordnung, {len(ordner)} Ordner", gut=True)
        zeile.fehler = ""
        self._abschliessen()

    def _misslungen(self, zeile: KontoZeile, text: str) -> None:
        # Hier wird nur vermerkt, nicht gefragt. Scheitern drei Postfächer
        # fast gleichzeitig, kämen sonst drei modale Dialoge ineinander -
        # verschachtelte Ereignisschleifen, und die Oberfläche steht.
        # Gefragt wird gesammelt, wenn alle Prüfungen durch sind.
        zeile.melden("Anmeldung gescheitert", gut=False)
        zeile.fehler = text
        zeile.zustand.setToolTip(text)
        self._abschliessen()

    def _namen_anbieten(self, zeile: KontoZeile) -> bool:
        """Fragt, ob der beglaubigte Name verwendet werden soll.

        Der Vorschlag wird eigens ermittelt und nicht aus der
        Fehlermeldung herausgelesen: Ein Text, an dem eine Funktion hängt,
        lässt sich nicht mehr umformulieren, ohne sie zu zerbrechen – und
        umformuliert wird an Fehlermeldungen ständig.
        """
        from mailburg.core import tlsdiagnose

        befund = tlsdiagnose.untersuchen(
            zeile.konto.server, zeile.konto.port, starttls=not zeile.konto.ssl
        )
        if not befund.vorschlag:
            return False
        vorschlag = befund.vorschlag

        antwort = QMessageBox.question(
            self.window(),
            "Anderer Servername nötig",
            f"<p>Das Zertifikat von <b>{zeile.konto.server}</b> ist nicht auf "
            f"diesen Namen ausgestellt.</p>"
            f"<p>Das ist bei Anbietern mit vielen Kunden der Normalfall: Der "
            f"Mailserver läuft unter dem Namen des Anbieters, Ihre Adresse "
            f"zeigt nur dorthin.</p>"
            f"<p>Soll stattdessen <b>{vorschlag}</b> verwendet werden? Das ist "
            f"derselbe Server – nur unter dem Namen, für den sein Zertifikat "
            f"gilt. Die Verbindung wird dann vollständig geprüft.</p>",
            QMessageBox.Yes | QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return False

        zeile.konto.server = vorschlag
        zeile.beschreibung.setText(f"{vorschlag}:{zeile.konto.port}")
        zeile.fehler = ""
        zeile.melden("Servername berichtigt")
        return True

    def _schon_versorgt(self, zeile: KontoZeile) -> bool:
        """Eingerichtet, mit erprobtem Passwort im Schlüsselbund."""
        if not getattr(zeile, "bereits_da", False):
            return False
        return bool(accounts.passwort_holen(zeile.konto))

    def _weiter_freigeben(self, frei: bool) -> None:
        """Sperrt »Weiter«, solange Anmeldungen laufen."""
        assistent = self.wizard()
        if assistent is None:
            return
        for knopf in (QWizard.NextButton, QWizard.BackButton):
            assistent.button(knopf).setEnabled(frei)

    def _abschliessen(self) -> None:
        self._offen -= 1
        if self._offen > 0:
            return

        self._weiter_freigeben(True)
        gescheitert = [z for z in self.zeilen if z.gewaehlt and getattr(z, "fehler", "")]

        if gescheitert:
            nochmal = []

            # Zuerst die Zertifikatsfälle: Dort liegt es am Servernamen,
            # nicht am Passwort. Wer hier nach dem Passwort gefragt würde,
            # gäbe dasselbe noch einmal ein - und es scheiterte wieder.
            for zeile in list(gescheitert):
                if "gilt nicht für" in zeile.fehler and self._namen_anbieten(zeile):
                    gescheitert.remove(zeile)
                    nochmal.append(zeile)

            for zeile in gescheitert:
                dialog = PasswortNachfrage(zeile.konto, zeile.fehler, self.window())
                if dialog.exec() and dialog.passwort.text():
                    zeile.passwort.setText(dialog.passwort.text())
                    zeile.fehler = ""
                    nochmal.append(zeile)
                else:
                    # Sichtbar stehen lassen, statt stillschweigend
                    # abzuwählen - und dazuschreiben, woran es lag. "Nicht
                    # eingerichtet" allein ließe den Anwender rätseln, ob
                    # er etwas falsch gemacht hat.
                    grund = zeile.fehler
                    zeile.ankreuz.setChecked(False)
                    zeile.fehler = ""
                    zeile.melden("nicht eingerichtet – Anmeldung schlug fehl", gut=False)
                    zeile.zustand.setToolTip(
                        f"{grund}\n\nSie können es später über »Postfächer "
                        f"verwalten« nachtragen."
                    )

            if nochmal:
                self._offen = len(nochmal)
                self._weiter_freigeben(False)
                for zeile in nochmal:
                    self._pruefen(zeile)
                return

            if not any(z.gewaehlt for z in self.zeilen):
                QMessageBox.information(
                    self,
                    "Kein Postfach eingerichtet",
                    "Es wurde kein Postfach eingerichtet. Sie können später "
                    "jederzeit welche hinzufügen.",
                )
                return

        self._speichern()
        self._durchgewinkt = True
        self.wizard().next()

    def _speichern(self) -> None:
        liste = Kontenliste()
        for zeile in self.zeilen:
            if not zeile.gewaehlt:
                continue
            if liste.finden(zeile.konto.name) or liste.finden_nach_postfach(
                zeile.konto.benutzer, zeile.konto.server
            ):
                continue
            liste.hinzufuegen(zeile.konto)
            accounts.passwort_setzen(zeile.konto, zeile.passwort.text())

        # **Und dem soeben angelegten Archiv zuordnen.** Ohne das steht
        # der Anwender nach der Einrichtung vor der Meldung "Diesem
        # Archiv ist kein Postfach zugeordnet" - die Einrichtung führte
        # dann in eine Sackgasse.
        #
        # Am 2026-08-27 unter Windows aufgefallen, einen Tag nachdem die
        # Zuordnung eingeführt wurde: Abruf, Zeitplan und Hauptfenster
        # waren umgestellt, der Assistent nicht. Wer neu einrichtet,
        # merkt so etwas sofort - wer das Programm gebaut hat, nie.
        kennung = getattr(self.wizard(), "archiv_kennung", "")
        if kennung:
            for zeile in self.zeilen:
                if zeile.gewaehlt:
                    liste.zuordnen(zeile.konto.name, kennung)
        self.wizard().konten = [z.konto for z in self.zeilen if z.gewaehlt]


class KontoDialog(QDialog):
    """Ein Postfach von Hand – für alles, was nicht in Thunderbird steht."""

    def __init__(self, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Postfach eintragen")

        self.name = QLineEdit()
        self.name.setPlaceholderText("z. B. Firma")
        self.benutzer = QLineEdit()
        self.benutzer.setPlaceholderText("post@example.org")
        self.server = QLineEdit()
        self.server.setPlaceholderText("imap.example.org")
        self.passwort = QLineEdit()
        self.passwort.setEchoMode(QLineEdit.Password)
        self.passwort.setPlaceholderText("Passwort oder App-Passwort")
        self.passwort.setAccessibleName("Passwort")
        sichtbarkeit_anbieten(self.passwort)

        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(993)
        self.verschluesselung = QComboBox()
        self.verschluesselung.addItem("Durchgehend verschlüsselt (Port 993)", True)
        self.verschluesselung.addItem("STARTTLS (Port 143)", False)
        self.verschluesselung.currentIndexChanged.connect(self._port_anpassen)

        formular = QFormLayout()
        formular.addRow("Name im Archiv:", self.name)
        formular.addRow("Mailadresse:", self.benutzer)
        formular.addRow("IMAP-Server:", self.server)
        formular.addRow("Verschlüsselung:", self.verschluesselung)
        formular.addRow("Port:", self.port)
        formular.addRow("Passwort:", self.passwort)

        # Erst prüfen, dann übernehmen: Ein Postfach, das sich nicht
        # anmelden kann, in der Liste zu haben, führt nur dazu, dass jeder
        # Abruf mit einem Fehler endet - und irgendwann sieht niemand mehr
        # hin. Deshalb bleibt "Übernehmen" gesperrt, bis der Test durch ist.
        self.pruefknopf = QPushButton("Verbindung testen")
        self.pruefknopf.clicked.connect(self._pruefen)
        self.pruefstand = QLabel("Noch nicht geprüft")
        self.pruefstand.setWordWrap(True)
        self.pruefstand.setEnabled(False)

        pruefzeile = QHBoxLayout()
        pruefzeile.addWidget(self.pruefknopf)
        pruefzeile.addWidget(self.pruefstand, 1)

        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.uebernehmen_knopf = knoepfe.button(QDialogButtonBox.Ok)
        self.uebernehmen_knopf.setText("Übernehmen")
        self.uebernehmen_knopf.setEnabled(False)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)

        # **Ein Ausweg für den Fall, dass der Server gerade nicht da ist.**
        # Die Prüfung vor dem Übernehmen ist richtig - ein Postfach, das
        # sich nicht anmelden kann, führt zu Abrufen, die immer scheitern,
        # und irgendwann sieht niemand mehr hin.
        #
        # Sie ist aber nicht in jeder Lage zu erfüllen: Wer offline
        # einrichtet, wer die Proton-Brücke noch nicht gestartet hat oder
        # wessen Server gerade wartet, kam bisher gar nicht weiter - der
        # Assistent verlangt mindestens ein Postfach. Am 2026-08-28 in der
        # Windows-Fassung aufgefallen, als ein erfundener Server für die
        # Anleitungsbilder eingetragen werden sollte.
        #
        # Deshalb ein zweiter Weg, deutlich als solcher gekennzeichnet.
        self.ungeprueft_knopf = QPushButton("Ohne Prüfung übernehmen")
        self.ungeprueft_knopf.setToolTip(
            "Für den Fall, dass der Server gerade nicht erreichbar ist – "
            "etwa ohne Netz oder wenn ein Brückenprogramm noch nicht läuft. "
            "Beim ersten Abruf zeigt sich, ob die Angaben stimmen."
        )
        self.ungeprueft_knopf.clicked.connect(self._ohne_pruefung)
        knoepfe.addButton(self.ungeprueft_knopf, QDialogButtonBox.ActionRole)
        # **Erst nach einem Versuch.** Solange »Übernehmen« ausgegraut
        # ist, wäre dies der einzige anklickbare Weg nach vorn – und
        # damit läge der ungeprüfte Weg näher als der geprüfte. Am
        # 2026-08-29 unter Windows aufgefallen: »Ohne Prüfung durchkommen
        # kommt jetzt schon, vor dem Verbindungstest.«
        #
        # Wer den Test nicht bestehen *kann* – ohne Netz, Brücke noch
        # nicht gestartet –, drückt einmal auf »Verbindung testen«, sieht
        # das Scheitern und bekommt den Knopf dann angeboten. Ein Klick
        # mehr, aber einer, nach dem man weiß, woran man ist.
        self.ungeprueft_knopf.setVisible(False)

        aufbau = QVBoxLayout(self)
        aufbau.addLayout(formular)
        aufbau.addLayout(pruefzeile)
        aufbau.addWidget(knoepfe)

        # Jede Änderung macht das Prüfergebnis wertlos.
        for feld in (self.name, self.benutzer, self.server, self.passwort):
            feld.textChanged.connect(self._ungeprueft)
        self.port.valueChanged.connect(self._ungeprueft)
        self.verschluesselung.currentIndexChanged.connect(self._ungeprueft)

        self._laeufer = None
        self.ordner: list[str] = []

    def _port_anpassen(self, stelle: int) -> None:
        self.port.setValue(993 if self.verschluesselung.itemData(stelle) else 143)

    def _ungeprueft(self) -> None:
        """Setzt den Prüfstand zurück, sobald sich etwas ändert."""
        self.uebernehmen_knopf.setEnabled(False)
        self.pruefstand.setText("Noch nicht geprüft")
        self.pruefstand.setStyleSheet("")
        # Auch den zweiten Weg wieder verbergen: Wer den Servernamen
        # ändert, hat einen neuen Versuch verdient - und soll ihn nicht
        # überspringen können, ohne ihn gesehen zu haben.
        self.ungeprueft_knopf.setVisible(False)

    def _ohne_pruefung(self) -> None:
        """Übernimmt das Postfach, ohne dass die Verbindung stand.

        Mit Rückfrage: Wer hier landet, hat meist einen Tippfehler im
        Servernamen – und der fiele sonst erst beim ersten Abruf auf,
        wenn niemand mehr davorsitzt.
        """
        if not self.benutzer.text().strip() or not self.server.text().strip():
            QMessageBox.information(
                self,
                "Angaben fehlen",
                "Mailadresse und Server brauchen wir in jedem Fall.",
            )
            return

        antwort = QMessageBox.question(
            self,
            "Ohne Prüfung übernehmen?",
            f"Die Verbindung zu <b>{self.server.text().strip()}</b> wurde "
            f"nicht geprüft.<br><br>"
            f"Das ist sinnvoll, wenn der Server gerade nicht erreichbar ist – "
            f"ohne Netz etwa, oder wenn ein Brückenprogramm noch nicht läuft. "
            f"Stimmen die Angaben nicht, merken Sie es beim ersten Abruf.<br><br>"
            f"Trotzdem übernehmen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if antwort == QMessageBox.Yes:
            self.accept()

    def _pruefen(self) -> None:
        """Meldet sich einmal an und holt die Ordnerliste."""
        konto = self.konto()
        if not konto.server or not konto.benutzer:
            self.pruefstand.setText("Bitte Mailadresse und Server angeben.")
            return
        if not self.passwort.text():
            self.pruefstand.setText("Ohne Passwort lässt sich nichts prüfen.")
            return

        self.pruefknopf.setEnabled(False)
        self.pruefstand.setStyleSheet("")
        self.pruefstand.setText("Verbinde …")

        auftrag = Anmeldeprobe(konto, self.passwort.text())
        auftrag.fertig.connect(self._geglueckt)
        auftrag.gescheitert.connect(self._misslungen)
        self._laeufer = Läufer(auftrag)
        self._laeufer.starten()

    def _geglueckt(self, ordner: list) -> None:
        self.ordner = list(ordner)
        self.pruefknopf.setEnabled(True)
        self.pruefstand.setStyleSheet(farben.stil(True))
        self.pruefstand.setText(
            f"Anmeldung in Ordnung – {len(ordner)} Ordner würden archiviert."
        )
        self.uebernehmen_knopf.setEnabled(True)
        self.uebernehmen_knopf.setFocus()

    def done(self, ergebnis: int) -> None:
        alle_abbrechen()
        super().done(ergebnis)

    def _misslungen(self, text: str) -> None:
        self.pruefknopf.setEnabled(True)
        self.pruefstand.setStyleSheet(farben.stil(False))
        # Nur die erste Zeile: Die ausführliche Erklärung steht im Dialog,
        # der beim Abruf erscheint, und würde hier den Platz sprengen.
        self.pruefstand.setText(text.split("\n")[0])
        self.uebernehmen_knopf.setEnabled(False)
        # **Jetzt erst der zweite Weg.** Wer bis hierher kommt, hat es
        # versucht und weiß, woran er ist – unterwegs ohne Netz, eine
        # Brücke, die nicht läuft, ein Server, den es erst morgen gibt.
        # Vorher angeboten wäre er der einzige anklickbare Knopf gewesen
        # und damit eine Einladung, die Prüfung zu überspringen.
        self.ungeprueft_knopf.setVisible(True)

    def konto(self) -> Konto:
        server = self.server.text().strip()
        return Konto(
            name=self.name.text().strip() or self.benutzer.text().strip(),
            server=server,
            benutzer=self.benutzer.text().strip(),
            port=self.port.value(),
            ssl=bool(self.verschluesselung.currentData()),
            bruecke=server.lower() in accounts.LOKALE_ADRESSEN,
        )


class AbschlussSeite(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Fertig")
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.RichText)

        self.gleich_abrufen = QCheckBox("Jetzt den ersten Abruf starten")
        self.gleich_abrufen.setChecked(True)

        aufbau = QVBoxLayout(self)
        # Der Hintergrundabruf wurde bisher als Terminalbefehl empfohlen -
        # mitten in einer grafischen Einrichtung, und noch dazu einer, der
        # das Quellverzeichnis voraussetzt. Wer MailBurg installiert hat,
        # hat es gerade nicht. Angelegt werden zwei Textdateien im eigenen
        # Benutzerverzeichnis; das kann das Programm selbst.
        self.plan = Zeitplanwahl()

        ueberschrift = QLabel("<b>Damit es von allein weiterläuft</b>")
        ueberschrift.setTextFormat(Qt.RichText)

        aufbau.addWidget(self.text)
        aufbau.addSpacing(12)
        aufbau.addWidget(ueberschrift)
        aufbau.addWidget(self.plan)
        aufbau.addSpacing(12)
        aufbau.addWidget(self.gleich_abrufen)

        # Ganz zum Schluss, nicht mittendrin: Der Satz nimmt dem Ganzen die
        # Endgültigkeit, und das wirkt erst, wenn alles gesagt ist.
        nachsatz = QLabel(
            "<i>Alles hier Eingestellte lässt sich später ändern. Postfächer "
            "kommen hinzu oder fallen weg, der Abstand ist verstellbar, das "
            "Archiv darf umziehen.</i>"
        )
        nachsatz.setWordWrap(True)
        nachsatz.setTextFormat(Qt.RichText)
        aufbau.addSpacing(12)
        aufbau.addWidget(nachsatz)
        aufbau.addStretch()

    def validatePage(self) -> bool:
        # Erst hier anlegen, nicht schon beim Anklicken: Wer den Assistenten
        # noch abbricht, soll keinen Zeitplan hinterlassen haben.
        self.plan.archiv = self.wizard().archiv_pfad
        geklappt, text = self.plan.anwenden()
        if not geklappt and text:
            QMessageBox.information(self, "Abruf im Hintergrund", text)
        return True

    def initializePage(self) -> None:
        assistent = self.wizard()
        anzahl = len(getattr(assistent, "konten", []))
        bund = accounts.schluesselbund_name()

        self.text.setText(
            f"<p>Das Archiv liegt in <b>{assistent.archiv_pfad}</b>, "
            f"{anzahl} Postfächer sind eingerichtet"
            + (f", die Passwörter in der {bund}." if bund else ".")
            + "</p>"

            "<p style='margin-top:12px'><b>Was jetzt passiert</b></p>"
            "<p>Der erste Abruf holt alles, was in den Postfächern liegt. Bei "
            "einem gewachsenen Bestand kann das eine Weile dauern – Sie "
            "können in der Zwischenzeit weiterarbeiten, und wenn Sie "
            "abbrechen, macht der nächste Abruf dort weiter, wo dieser "
            "aufgehört hat. Verloren geht dabei nichts.</p>"
            "<p>Danach wird nur noch geholt, was neu dazugekommen ist. Das "
            "dauert dann Sekunden.</p>"

        )


class Einrichtungsassistent(QWizard):
    """Führt durch die Ersteinrichtung."""

    def __init__(self, eltern=None) -> None:
        super().__init__(eltern)
        self.archiv_pfad: Path | None = None
        self.konten: list[Konto] = []

        self.setWindowTitle(f"{APP_NAME} einrichten")
        self.setWizardStyle(QWizard.ModernStyle)

        # Auch ohne Qts Übersetzungsdateien deutsch. Die fehlen in
        # abgespeckten Installationen gern einmal, und "Next" neben
        # "Willkommen" sieht nach halber Arbeit aus.
        self.setButtonText(QWizard.NextButton, "&Weiter >")
        self.setButtonText(QWizard.BackButton, "< &Zurück")
        self.setButtonText(QWizard.CancelButton, "Abbrechen")
        self.setButtonText(QWizard.FinishButton, "&Fertig")
        self.setButtonText(QWizard.HelpButton, "Hilfe")
        # Der Anwender soll jederzeit zurück können, ohne etwas zu verlieren.
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        # Eine Größe für alle Schritte. Ein Assistent, dessen Fenster bei
        # jedem Weiter springt, wirkt unfertig - und man verliert die
        # Stelle, an der man gerade gelesen hat.
        self.setMinimumSize(880, 720)
        self.resize(880, 720)

        self.addPage(WillkommenSeite())
        self.addPage(ArchivSeite())
        self.addPage(KontenSeite())
        self.abschluss = AbschlussSeite()
        self.addPage(self.abschluss)

    @property
    def soll_abrufen(self) -> bool:
        return self.abschluss.gleich_abrufen.isChecked()

    def done(self, ergebnis: int) -> None:
        """Beim Schließen die Prüfläufe abbestellen – ohne zu warten.

        Warten würde die Oberfläche einfrieren, und zwar ausgerechnet
        dann, wenn jemand abbrechen will, weil etwas hängt. Die Fäden
        halten sich selbst am Leben und räumen sich auf.
        """
        alle_abbrechen()
        super().done(ergebnis)
