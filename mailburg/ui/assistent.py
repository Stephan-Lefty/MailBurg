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

from mailburg import APP_NAME
from mailburg.core import accounts
from mailburg.core.accounts import Konto, Kontenliste
from mailburg.core.archive import Archive, ArchiveError, Mode
from mailburg.core.retention import Jurisdiction
from mailburg.ui.arbeit import Anmeldeprobe, Läufer


class WillkommenSeite(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Willkommen")
        self.setSubTitle(
            f"{APP_NAME} sammelt Ihre E-Mail an einem Ort, den Sie bestimmen, "
            f"und macht sie durchsuchbar."
        )

        text = QLabel(
            "<p>In den nächsten Schritten legen wir fest, <b>wohin</b> Ihr "
            "Archiv kommt und <b>welche Postfächer</b> hinein sollen.</p>"
            "<p>Ihre Postfächer werden dabei nur gelesen. Gelöscht wird dort "
            "nichts, und ungelesene Post bleibt ungelesen.</p>"
            "<p>Die Passwörter kommen in den Schlüsselbund Ihres Systems – "
            "nicht in eine Datei.</p>"
        )
        text.setWordWrap(True)
        text.setTextFormat(Qt.RichText)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(text)
        aufbau.addStretch()


class ArchivSeite(QWizardPage):
    """Wohin das Archiv kommt und nach welchen Regeln es geführt wird."""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Das Archiv")
        self.setSubTitle("Wo sollen Ihre Mails liegen?")

        self.pfad = QLineEdit()
        self.pfad.setPlaceholderText("noch nichts gewählt")
        self.pfad.setText(str(Path.home() / "Mailarchiv"))
        # Damit Vorlesehilfen etwas anzusagen haben.
        self.pfad.setAccessibleName("Ort des Archivs")

        blaettern = QPushButton("Auswählen …")
        blaettern.clicked.connect(self._waehlen)

        zeile = QHBoxLayout()
        zeile.addWidget(self.pfad, 1)
        zeile.addWidget(blaettern)

        hinweis = QLabel(
            "Eine interne Platte, eine externe Platte oder ein Ordner, den "
            "Nextcloud abgleicht – alles möglich. Der Suchindex wird "
            "getrennt davon abgelegt und kann jederzeit neu entstehen."
        )
        hinweis.setWordWrap(True)

        self.privat = QRadioButton("Privatarchiv")
        self.privat.setChecked(True)
        self.geschaeftlich = QRadioButton("Geschäftsarchiv")

        privat_text = QLabel(
            "Keine Fristen, löschen jederzeit. Wer ausschließlich eigene "
            "Post archiviert, unterliegt der DSGVO gar nicht."
        )
        geschaeft_text = QLabel(
            "Mit Hash-Kette, Grabsteinen und Aufbewahrungsfristen. "
            "Unterstützt einen revisionssicheren Betrieb – herstellen kann "
            "ihn keine Software allein, dazu gehört auch eine "
            "Verfahrensdokumentation."
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

        fristen = QFormLayout()
        fristen.addRow("Fristen nach dem Recht von:", self.rechtsraum)
        self.geschaeftlich.toggled.connect(self.rechtsraum.setEnabled)

        art = QGroupBox("Wofür ist das Archiv?")
        innen = QVBoxLayout(art)
        innen.addWidget(self.privat)
        innen.addWidget(privat_text)
        innen.addWidget(self.geschaeftlich)
        innen.addWidget(geschaeft_text)
        innen.addLayout(fristen)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(QLabel("Ort des Archivs:"))
        aufbau.addLayout(zeile)
        aufbau.addWidget(hinweis)
        aufbau.addSpacing(12)
        aufbau.addWidget(art)
        aufbau.addStretch()

        self.registerField("archivpfad*", self.pfad)

    def _waehlen(self) -> None:
        gewaehlt = QFileDialog.getExistingDirectory(
            self, "Ordner für das Archiv", self.pfad.text()
        )
        if gewaehlt:
            self.pfad.setText(gewaehlt)

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

        beschreibung = f"{konto.benutzer} — {konto.server}:{konto.port}"
        if konto.ist_lokale_bruecke:
            beschreibung += "  (Brücke auf diesem Rechner)"
        self.beschreibung = QLabel(beschreibung)
        self.beschreibung.setEnabled(False)

        self.passwort = QLineEdit()
        self.passwort.setEchoMode(QLineEdit.Password)
        self.passwort.setPlaceholderText("Passwort")
        self.passwort.setAccessibleName(f"Passwort für {konto.name}")

        self.zustand = QLabel("")
        self.zustand.setMinimumWidth(180)

        gitter.addWidget(self.ankreuz, zeile, 0)
        gitter.addWidget(self.beschreibung, zeile, 1)
        gitter.addWidget(self.passwort, zeile, 2)
        gitter.addWidget(self.zustand, zeile, 3)

    @property
    def gewaehlt(self) -> bool:
        return self.ankreuz.isChecked()

    def melden(self, text: str, gut: bool | None = None) -> None:
        farbe = {True: "#2e7d32", False: "#c62828", None: ""}[gut]
        self.zustand.setStyleSheet(f"color: {farbe}" if farbe else "")
        self.zustand.setText(text)


class KontenSeite(QWizardPage):
    """Postfächer eintragen – vorbelegt aus Thunderbird, wenn vorhanden."""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Ihre Postfächer")
        self.setSubTitle("Welche Postfächer sollen archiviert werden?")
        self.zeilen: list[KontoZeile] = []
        self._laeufer: list[Läufer] = []
        self._offen = 0

        self.herkunft = QLabel()
        self.herkunft.setWordWrap(True)

        self.gitter = QGridLayout()
        self.gitter.setColumnStretch(1, 1)

        inhalt = QWidget()
        inhalt.setLayout(self.gitter)
        rollbereich = QScrollArea()
        rollbereich.setWidget(inhalt)
        rollbereich.setWidgetResizable(True)
        rollbereich.setMinimumHeight(240)

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
        uebergangen: list[str] = []

        for profil in local.find_thunderbird_profiles():
            try:
                funde = uebernahme.aus_thunderbird(profil)
            except (FileNotFoundError, OSError):
                continue
            brauchbar = [f for f in funde if f.brauchbar]
            uebergangen += [f"{f.konto.name} ({f.art.upper()})" for f in funde
                            if not f.brauchbar]
            uebernahme.namen_entzerren(brauchbar, vergeben)
            gefunden += [f.konto for f in brauchbar]

        if gefunden:
            text = (
                f"<b>{len(gefunden)} Postfächer aus Thunderbird übernommen.</b> "
                f"Server und Benutzernamen sind bereits eingetragen – bitte nur "
                f"noch die Passwörter ergänzen.<br>"
                f"<i>Die Passwörter selbst werden aus Thunderbird nicht "
                f"ausgelesen. Ein Programm, das die Passwörter anderer Programme "
                f"abgreift, hat in einem Archiv nichts zu suchen.</i>"
            )
            if uebergangen:
                text += (
                    f"<br><br>Nicht abrufbar und daher nicht dabei: "
                    f"{', '.join(uebergangen)}."
                )
        else:
            text = (
                "<b>Kein Thunderbird-Profil gefunden.</b><br>"
                "Tragen Sie Ihre Postfächer bitte von Hand ein."
            )
        self.herkunft.setText(text)

        for konto in gefunden:
            self._zeile_anlegen(konto)

    def _zeile_anlegen(self, konto: Konto) -> None:
        zeile = KontoZeile(konto, self.gitter, len(self.zeilen))
        self.zeilen.append(zeile)

    def _von_hand(self) -> None:
        dialog = KontoDialog(self)
        if dialog.exec():
            self._zeile_anlegen(dialog.konto())

    def validatePage(self) -> bool:
        zu_pruefen = [z for z in self.zeilen if z.gewaehlt]
        if not zu_pruefen:
            QMessageBox.information(
                self,
                "Kein Postfach gewählt",
                "Ohne Postfach gibt es nichts zu archivieren. Wählen Sie "
                "mindestens eines aus oder tragen Sie eines von Hand ein.",
            )
            return False

        ohne_passwort = [z for z in zu_pruefen if not z.passwort.text()]
        if ohne_passwort:
            QMessageBox.information(
                self,
                "Passwort fehlt",
                "Für folgende Postfächer fehlt noch das Passwort:\n\n"
                + "\n".join(f"• {z.konto.name}" for z in ohne_passwort),
            )
            return False

        # Anmeldungen laufen nebenläufig; die Seite gibt erst frei, wenn
        # alle durch sind. Sonst stünde der Anwender vor einem Fenster, das
        # sich nicht mehr rührt.
        self._offen = len(zu_pruefen)
        self.wizard().button(QWizard.NextButton).setEnabled(False)
        for zeile in zu_pruefen:
            self._pruefen(zeile)
        return False

    def _pruefen(self, zeile: KontoZeile) -> None:
        zeile.melden("prüfe …")
        auftrag = Anmeldeprobe(zeile.konto, zeile.passwort.text())
        laeufer = Läufer(auftrag)
        self._laeufer.append(laeufer)

        auftrag.fertig.connect(lambda ordner, z=zeile: self._geklappt(z, ordner))
        auftrag.gescheitert.connect(lambda text, z=zeile: self._misslungen(z, text))
        laeufer.starten()

    def _geklappt(self, zeile: KontoZeile, ordner: list[str]) -> None:
        zeile.melden(f"in Ordnung, {len(ordner)} Ordner", gut=True)
        zeile.fehler = ""
        self._abschliessen()

    def _misslungen(self, zeile: KontoZeile, text: str) -> None:
        # Der häufigste Fall bei eigenen Domänen: Der Mailserver läuft beim
        # Hoster unter dessen Namen. Mailprogramme lassen den Anwender hier
        # eine Ausnahme anklicken, die die Prüfung für immer aushebelt. Wir
        # bieten stattdessen den Namen an, unter dem sie gelingt.
        if "gilt nicht für" in text and self._namen_anbieten(zeile, text):
            return

        zeile.melden("Anmeldung gescheitert", gut=False)
        zeile.fehler = text
        zeile.zustand.setToolTip(text)
        self._abschliessen()

    def _namen_anbieten(self, zeile: KontoZeile, text: str) -> bool:
        """Fragt, ob der beglaubigte Name verwendet werden soll."""
        import re

        treffer = re.search(r"Mit --server (\S+) wird", text)
        if not treffer:
            return False
        vorschlag = treffer.group(1)

        antwort = QMessageBox.question(
            self,
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
        zeile.beschreibung.setText(
            f"{zeile.konto.benutzer} — {vorschlag}:{zeile.konto.port}"
        )
        zeile.melden("prüfe erneut …")
        self._pruefen(zeile)
        return True

    def _abschliessen(self) -> None:
        self._offen -= 1
        if self._offen > 0:
            return

        self.wizard().button(QWizard.NextButton).setEnabled(True)
        gescheitert = [z for z in self.zeilen if z.gewaehlt and getattr(z, "fehler", "")]

        if gescheitert:
            QMessageBox.warning(
                self,
                "Nicht alle Anmeldungen haben geklappt",
                "Bei folgenden Postfächern hat die Anmeldung nicht "
                "funktioniert:\n\n"
                + "\n\n".join(f"{z.konto.name}:\n{z.fehler}" for z in gescheitert),
            )
            return

        self._speichern()
        self.wizard().next()

    def _speichern(self) -> None:
        liste = Kontenliste()
        for zeile in self.zeilen:
            if not zeile.gewaehlt or liste.finden(zeile.konto.name):
                continue
            liste.hinzufuegen(zeile.konto)
            accounts.passwort_setzen(zeile.konto, zeile.passwort.text())
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

        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addLayout(formular)
        aufbau.addWidget(knoepfe)

    def _port_anpassen(self, stelle: int) -> None:
        self.port.setValue(993 if self.verschluesselung.itemData(stelle) else 143)

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
        aufbau.addWidget(self.text)
        aufbau.addSpacing(12)
        aufbau.addWidget(self.gleich_abrufen)
        aufbau.addStretch()

    def initializePage(self) -> None:
        assistent = self.wizard()
        anzahl = len(getattr(assistent, "konten", []))
        self.text.setText(
            f"<p>Das Archiv liegt in <b>{assistent.archiv_pfad}</b>, "
            f"{anzahl} Postfächer sind eingerichtet.</p>"
            f"<p>Der erste Abruf holt alles, was in den Postfächern liegt – "
            f"das kann bei großen Beständen dauern. Danach wird nur noch "
            f"geholt, was neu dazukommt.</p>"
        )


class Einrichtungsassistent(QWizard):
    """Führt durch die Ersteinrichtung."""

    def __init__(self, eltern=None) -> None:
        super().__init__(eltern)
        self.archiv_pfad: Path | None = None
        self.konten: list[Konto] = []

        self.setWindowTitle(f"{APP_NAME} einrichten")
        self.setWizardStyle(QWizard.ModernStyle)
        # Der Anwender soll jederzeit zurück können, ohne etwas zu verlieren.
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setMinimumSize(680, 520)

        self.addPage(WillkommenSeite())
        self.addPage(ArchivSeite())
        self.addPage(KontenSeite())
        self.abschluss = AbschlussSeite()
        self.addPage(self.abschluss)

    @property
    def soll_abrufen(self) -> bool:
        return self.abschluss.gleich_abrufen.isChecked()
