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
from mailburg.ui import bilder
from mailburg.ui.arbeit import Anmeldeprobe, Läufer


def _schluesselbund_satz() -> str:
    """Benennt den Schlüsselbund beim Namen, statt ihn zu umschreiben.

    Wer wissen will, wo sein Passwort gelandet ist, sucht nach einem
    Programm in seinem Menü – nicht nach »dem Schlüsselbund des Systems«.
    """
    name = accounts.schluesselbund_name()
    if not name:
        return (
            "<b>nirgends</b>: Auf diesem Rechner ist kein Schlüsselbund "
            "erreichbar, deshalb wird das Passwort bei jedem Abruf neu "
            "erfragt"
        )
    return f"in die <b>{name}</b>"


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

            "<p style='margin-top:14px'><b>Was MailBurg mit Ihren Postfächern "
            "macht – und was nicht</b></p>"
            "<p>Es liest sie. Mehr nicht. Es löscht dort nichts, verschiebt "
            "nichts und markiert nichts als gelesen. In Ihrem Mailprogramm "
            "sieht hinterher alles aus wie vorher; was ungelesen war, ist es "
            "weiterhin. Und sollten Sie MailBurg eines Tages nicht mehr "
            "verwenden, finden Sie Ihre Postfächer unverändert vor.</p>"

            "<p style='margin-top:14px'><b>Wohin Ihre Post geht</b></p>"
            "<p>In einen Ordner, den Sie gleich selbst bestimmen: auf die "
            "Platte im Rechner, auf eine externe Platte oder in Ihre eigene "
            "Nextcloud.</p>"
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
            "<p>Sie müssen uns das alles nicht glauben. Der gesamte "
            "Quelltext ist offen einsehbar – wer nachprüfen möchte, was das "
            "Programm tut, kann es tun, und wer es selbst nicht kann, kann "
            "jemanden fragen, der es kann. Das ist der Unterschied zu einem "
            "Versprechen.</p>"

            "<p style='margin-top:14px'><b>Sie bleiben unabhängig</b></p>"
            "<p>Jede Mail liegt einzeln im Archiv, in dem Format, in dem "
            "Mails nun einmal gespeichert werden. Auch ohne MailBurg kommen "
            "Sie an jede einzelne heran – mit jedem Mailprogramm, das "
            "<i>.eml</i>-Dateien öffnen kann. Sie sind an dieses Programm "
            "nicht gebunden.</p>"

            f"<p style='margin-top:14px'><b>Ihre Passwörter</b></p>"
            f"<p>Die brauchen wir, um Ihre Postfächer abzurufen – sonst "
            f"nichts. Sie kommen {_schluesselbund_satz()}, also dorthin, wo "
            f"auch Ihr Mailprogramm seine Passwörter aufbewahrt. In keine "
            f"Datei, die man kopieren könnte, und schon gar nicht ins "
            f"Internet.</p>"

            "<p style='margin-top:14px'><i>Sie haben schon ein Archiv? Geben "
            "Sie im nächsten Schritt dessen Ordner an – MailBurg erkennt es "
            "und verwendet es weiter.</i></p>"
        )
        text.setWordWrap(True)
        text.setTextFormat(Qt.RichText)

        rollbar = QScrollArea()
        rollbar.setWidget(text)
        rollbar.setWidgetResizable(True)
        rollbar.setFrameShape(QScrollArea.NoFrame)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(self.banner)
        aufbau.addWidget(rollbar, 1)


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
            "<p>Eine interne Platte, eine externe Platte oder ein Ordner, den "
            "Nextcloud abgleicht – alles möglich. Sie können das Archiv "
            "später auch verschieben; MailBurg findet es wieder.</p>"
            "<p><b>Was in diesem Ordner entsteht:</b> ein Unterordner "
            "<i>mail</i> mit Ihren Nachrichten, nach Monaten sortiert, und "
            "ein Unterordner <i>meta</i> mit dem Protokoll darüber, was wann "
            "aufgenommen wurde. Sonst nichts.</p>"
            "<p><b>Sichern sollten Sie diesen Ordner</b> wie alle wichtigen "
            "Daten. Der Suchindex gehört nicht dazu – der liegt getrennt "
            "davon und lässt sich jederzeit aus dem Archiv neu erzeugen.</p>"
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

        bund = accounts.schluesselbund_name()
        ablage = (
            f"Ihre Passwörter kommen in die <b>{bund}</b>"
            if bund
            else "<b>Achtung:</b> Auf diesem Rechner ist kein Schlüsselbund "
                 "erreichbar. Die Passwörter werden dann bei jedem Abruf neu "
                 "erfragt – gespeichert werden sie nicht"
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
            if uebergangen:
                text += (
                    f"<p><b>Nicht dabei:</b> {', '.join(uebergangen)}. "
                    f"Diese Konten lassen sich nicht über IMAP abrufen. Ihre "
                    f"Nachrichten liegen aber meist lokal vor und können "
                    f"später aus dem Mailprogramm eingelesen werden.</p>"
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
        zu_pruefen = [z for z in self.zeilen if z.gewaehlt]
        if not zu_pruefen:
            # Alles schon eingerichtet? Dann ist nichts zu tun, und der
            # Anwender soll weitergehen dürfen statt ermahnt zu werden.
            if self.zeilen and all(getattr(z, "bereits_da", False) for z in self.zeilen):
                self.wizard().konten = [z.konto for z in self.zeilen]
                return True
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
            if not zeile.gewaehlt:
                continue
            if liste.finden(zeile.konto.name) or liste.finden_nach_postfach(
                zeile.konto.benutzer, zeile.konto.server
            ):
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

            "<p style='margin-top:12px'><b>Damit es von allein weiterläuft</b></p>"
            "<p>Sinnvoll ist ein regelmäßiger Abruf im Hintergrund – sonst "
            "muss jemand daran denken. Eingerichtet wird er einmalig mit "
            "<i>./install.sh --zeitsteuerung</i>; die Anleitung dazu liegt "
            "im Ordner <i>docs</i>.</p>"

            "<p style='margin-top:12px'><i>Alles hier Eingestellte lässt sich "
            "später ändern. Postfächer kommen hinzu oder fallen weg, das "
            "Archiv darf umziehen.</i></p>"
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
        self.setMinimumSize(680, 520)

        self.addPage(WillkommenSeite())
        self.addPage(ArchivSeite())
        self.addPage(KontenSeite())
        self.abschluss = AbschlussSeite()
        self.addPage(self.abschluss)

    @property
    def soll_abrufen(self) -> bool:
        return self.abschluss.gleich_abrufen.isChecked()
