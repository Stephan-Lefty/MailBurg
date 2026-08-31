"""Den regelmäßigen Abruf einstellen – am Ende der Einrichtung und später.

Zwei Fragen beantwortet diese Ansicht, und beide stellen sich Anwender
sofort: *Muss dafür etwas laufen?* und *Wie oft?* Die erste beantwortet
der Text, die zweite das Auswahlfeld.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mailburg.core import orte, zeitplan
from mailburg.ui import farben

#: Die angebotenen Abstände. Bewusst wenige: Wer zwischen siebzehn
#: Möglichkeiten wählen soll, wählt gar nicht.
TAKTE: list[tuple[str, int]] = [
    ("alle 15 Minuten", 15),
    ("alle 30 Minuten", 30),
    ("stündlich", 60),
    ("alle 4 Stunden", 240),
    ("einmal am Tag", 1440),
]

#: Wie viele Sicherungsstände aufbewahrt werden. Die Null bedeutet
#: »immer dieselbe Datei überschreiben« – so versteht es auch
#: ``core.zeitplan._haltung``, das daraus ``--ersetzen`` macht.
HALTUNGEN: list[tuple[str, int]] = [
    ("immer dieselbe Datei ersetzen", 0),
    ("die letzten 2 Stände", 2),
    ("die letzten 3 Stände", 3),
    ("die letzten 5 Stände", 5),
    ("die letzten 7 Stände", 7),
    ("die letzten 14 Stände", 14),
    ("die letzten 30 Stände", 30),
]


def _erster_vorhandener(pfad: str | None) -> str:
    """Ein Startordner, den es wirklich gibt.

    Der Dateidialog bekommt einen Ordner mit, in dem er aufgehen soll.
    Gibt es ihn nicht, macht Windows sich auf die Suche – über die
    Netzwerkumgebung, mit Zeitüberschreitung. Für den Anwender sieht das
    aus, als hinge das Programm: erst eine Sanduhr, dann irgendwann doch
    der Dialog.

    Das trat auf, seit der Dialog einen Ordner *vorschlägt*: Der
    Vorschlag ist ja gerade noch nicht angelegt. Am 2026-08-30 unter
    Windows aufgefallen, einen Tag nachdem der Vorschlag eingebaut
    wurde.

    Deshalb hier zum nächsten vorhandenen Elternordner hochgehen – bei
    ``D:\\Sicherungen\\MailBurg-Sicherung`` also zu ``D:\\Sicherungen``
    oder ``D:\\``. Bleibt gar nichts übrig, das Benutzerverzeichnis.
    """
    if pfad and pfad.strip():
        stelle = Path(pfad.strip()).expanduser()
        for kandidat in (stelle, *stelle.parents):
            try:
                if kandidat.is_dir():
                    return str(kandidat)
            except OSError:
                # Ein abgezogenes Laufwerk oder ein unerreichbarer
                # Netzpfad – weiter nach oben, nicht aufgeben.
                continue
    return str(Path.home())


def _wie_das_system_schreibt(pfad: str | None) -> str:
    """Trennzeichen so, wie der Anwender sie kennt.

    Qt gibt Pfade immer mit Schrägstrich zurück – auch unter Windows.
    Wer dort über »Auswählen …« einen Ordner heraussuchte, bekam
    ``C:/Users/…`` zu sehen, obwohl Windows selbst überall
    ``C:\\Users\\…`` schreibt.

    Aufgefallen am 2026-08-29 auf einem Bild aus der Windows-VM. In den
    anderen Auswahlfeldern trat es nicht auf: Dort geht der Pfad erst
    durch ``pathlib.Path``, und dessen ``str()`` setzt von sich aus die
    Trennzeichen des laufenden Systems. Nur hier landete der rohe
    Qt-Text unmittelbar im Eingabefeld.

    Auf den Pfad selbst hat das keine Auswirkung – Windows nimmt beide
    Schreibweisen an. Es geht allein darum, was dasteht.
    """
    if not pfad:
        return ""
    return str(Path(pfad))


class Zeitplanwahl(QWidget):
    """Ankreuzfeld und Abstand – zum Einbauen in Seiten und Dialoge."""

    def __init__(self, eltern=None, archiv=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        stand = zeitplan.zustand(self.archiv)

        self.an = QCheckBox("Neue Post regelmäßig im Hintergrund holen")
        self.an.setChecked(stand.laeuft or stand.moeglich)
        self.an.toggled.connect(self._umschalten)

        self.takt = QComboBox()
        for beschriftung, minuten in TAKTE:
            self.takt.addItem(beschriftung, minuten)
        self.takt.setCurrentIndex(
            max(0, [m for _, m in TAKTE].index(stand.takt))
            if stand.takt in [m for _, m in TAKTE]
            else 1
        )
        self.takt.setAccessibleName("Abstand zwischen den Abrufen")

        reihe = QHBoxLayout()
        reihe.addSpacing(24)
        reihe.addWidget(QLabel("Abstand:"))
        reihe.addWidget(self.takt)
        reihe.addStretch()

        self.hinweis = QLabel()
        self.hinweis.setWordWrap(True)
        self.hinweis.setTextFormat(Qt.RichText)
        self.hinweis.setText(
            "<p style='margin-left:24px'>Dafür muss MailBurg <b>nicht</b> "
            "geöffnet bleiben und auch nicht in den Autostart – geholt wird "
            "im Hintergrund, ganz ohne Fenster.</p>"
            "<p style='margin-left:24px'>Nötig ist nur, dass Sie angemeldet "
            "sind: Die Passwörter liegen im Schlüsselbund, und der öffnet "
            "sich erst mit Ihrer Anmeldung. War der Rechner aus, wird der "
            "versäumte Abruf beim nächsten Anmelden nachgeholt.</p>"
        )

        aufbau = QVBoxLayout(self)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.addWidget(self.an)
        aufbau.addLayout(reihe)
        aufbau.addWidget(self.hinweis)

        if not stand.moeglich:
            self.an.setChecked(False)
            self.an.setEnabled(False)
            self.hinweis.setText(f"<p style='margin-left:24px'>{stand.grund}</p>")
        self._umschalten(self.an.isChecked())

    def _umschalten(self, an: bool) -> None:
        self.takt.setEnabled(an)

    def anwenden(self) -> tuple[bool, str]:
        """Richtet ein oder schaltet ab – je nach Häkchen."""
        if not self.an.isEnabled():
            return True, ""
        if not self.an.isChecked():
            return zeitplan.abschalten(self.archiv)
        archiv = self.archiv
        if archiv is None:
            from mailburg.core.einstellungen import zuletzt_gemerkt

            archiv = zuletzt_gemerkt()
        if archiv is None:
            return False, "Es ist kein Archiv eingerichtet."
        return zeitplan.einrichten(archiv, self.takt.currentData())


class Sicherungswahl(QWidget):
    """Wie oft das Archiv weggepackt wird – und wohin."""

    def __init__(self, eltern=None, archiv=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        stand = zeitplan.sicherung_zustand(archiv)

        self.an = QCheckBox("Das Archiv regelmäßig in eine Datei sichern")
        self.an.setChecked(stand.laeuft)
        self.an.toggled.connect(self._umschalten)

        self.takt = QComboBox()
        for bezeichnung in zeitplan.TAKTE_SICHERUNG:
            self.takt.addItem(bezeichnung, bezeichnung)
        self.takt.setAccessibleName("Wie oft gesichert wird")
        # **Zeigen, was eingerichtet ist, nicht die Vorgabe.** Sonst
        # überschreibt ein Übernehmen die eigene Einstellung, ohne dass
        # irgendwo etwas davon steht.
        if stand.takt_sicherung:
            gefunden = self.takt.findData(stand.takt_sicherung)
            if gefunden >= 0:
                self.takt.setCurrentIndex(gefunden)

        self.ziel = QLineEdit(_wie_das_system_schreibt(stand.archiv))
        self.ziel.setPlaceholderText(
            "Ordner für die Sicherungen – am besten in der Cloud"
        )
        self.suchen = QPushButton("Auswählen …")
        self.suchen.clicked.connect(self._ordner_waehlen)

        # **Das war ein Zahlenfeld und sah aus wie eine Auswahlliste.**
        # Direkt daneben steht mit »Wie oft« eine echte Auswahlliste;
        # unter Windows 11 gleichen sich die beiden Pfeile so sehr, dass
        # Stephan am 2026-08-30 darauf klickte und meldete: »das rechte
        # Pulldown geht nicht«. Es klappte nichts auf, weil es nichts
        # aufzuklappen gab – man musste die Zahl hineintippen.
        #
        # Eine Liste ist hier ohnehin das Richtige: Zwischen 17 und 18
        # Ständen wählt niemand, und die Fälle, die vorkommen, sind
        # abzählbar.
        self.behalten = QComboBox()
        for beschriftung, wert in HALTUNGEN:
            self.behalten.addItem(beschriftung, wert)
        self.behalten.setAccessibleName("Wie viele Stände aufbewahrt werden")
        # Auch hier: den eingerichteten Wert zeigen. Steht dort eine
        # Zahl, die die Liste nicht führt – von Hand eingetragen oder aus
        # einer früheren Fassung –, kommt sie hinzu, statt stillschweigend
        # auf die Vorgabe zu fallen.
        if stand.behalten:
            gefunden = self.behalten.findData(stand.behalten)
            if gefunden < 0:
                self.behalten.addItem(
                    f"die letzten {stand.behalten} Stände", stand.behalten
                )
                gefunden = self.behalten.count() - 1
            self.behalten.setCurrentIndex(gefunden)
        self.behalten.setToolTip(
            "»Immer dieselbe Datei ersetzen« hält den Platzbedarf "
            "gleich – bei Nextcloud sinnvoll, weil der Server die "
            "Versionen ohnehin führt. Andernfalls wird je Lauf eine "
            "Datei mit Datum angelegt und nur die eingestellte Zahl "
            "behalten; ohne Grenze läuft die Platte irgendwann voll, "
            "und dann scheitert ausgerechnet die Sicherung, auf die es "
            "ankäme."
        )

        reihe = QHBoxLayout()
        reihe.addSpacing(24)
        reihe.addWidget(QLabel("Wie oft:"))
        reihe.addWidget(self.takt)
        reihe.addWidget(QLabel("behalten:"))
        reihe.addWidget(self.behalten)
        reihe.addStretch()

        zielreihe = QHBoxLayout()
        zielreihe.addSpacing(24)
        zielreihe.addWidget(QLabel("Ordner:"))
        zielreihe.addWidget(self.ziel, 1)
        zielreihe.addWidget(self.suchen)

        hinweis = QLabel(
            "<p style='margin-left:24px'>Gepackt wird das ganze Archiv in "
            "<b>eine Datei</b> mit Datum im Namen. Viel kleiner wird sie "
            "nicht – Ihre Mails liegen schon komprimiert –, aber ein "
            "Cloud-Programm kommt mit einer Datei um ein Vielfaches "
            "schneller zurecht als mit zehntausend.</p>"
            "<p style='margin-left:24px'><b>Nicht auf dieselbe Platte wie "
            "das Archiv.</b> Eine Sicherung, die neben dem Original liegt, "
            "geht mit ihm zusammen verloren.</p>"
        )
        hinweis.setWordWrap(True)
        hinweis.setTextFormat(Qt.RichText)

        aufbau = QVBoxLayout(self)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.addWidget(self.an)
        aufbau.addLayout(reihe)
        aufbau.addLayout(zielreihe)
        aufbau.addWidget(hinweis)

        if not stand.moeglich:
            self.an.setChecked(False)
            self.an.setEnabled(False)
        self._umschalten(self.an.isChecked())

    def _umschalten(self, an: bool) -> None:
        for teil in (self.takt, self.behalten, self.ziel, self.suchen):
            teil.setEnabled(an)

        # Wer ankreuzt, will sichern – dann soll nicht als Nächstes eine
        # Fehlermeldung kommen, weil das Feld leer ist, das der Dialog
        # selbst leer gelassen hat. Nur beim Ankreuzen und nur, wenn
        # nichts drinsteht: Eine getroffene Wahl wird nie überschrieben.
        if an and not self.ziel.text().strip():
            vorschlag = orte.sicherungsort_vorschlagen(self.archiv)
            if vorschlag is not None:
                self.ziel.setText(_wie_das_system_schreibt(str(vorschlag)))

    def _ordner_waehlen(self) -> None:
        gewaehlt = QFileDialog.getExistingDirectory(
            self, "Ordner für die Sicherungen", _erster_vorhandener(self.ziel.text())
        )
        if gewaehlt:
            self.ziel.setText(_wie_das_system_schreibt(gewaehlt))

    def anwenden(self) -> tuple[bool, str]:
        if not self.an.isEnabled():
            return True, ""
        archiv = self.archiv
        if archiv is None:
            from mailburg.core.einstellungen import zuletzt_gemerkt

            archiv = zuletzt_gemerkt()
        if archiv is None:
            return False, "Es ist kein Archiv eingerichtet."
        if not self.an.isChecked():
            return zeitplan.sicherung_abschalten(archiv)
        if not self.ziel.text().strip():
            return False, "Bitte einen Ordner für die Sicherungen wählen."
        return zeitplan.sicherung_einrichten(
            archiv, self.ziel.text().strip(),
            self.takt.currentData(), self.behalten.currentData(),
        )


class Zeitplandialog(QDialog):
    """Abruf und Sicherung – beides, was von selbst laufen soll."""

    def __init__(self, eltern=None, archiv=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Was von selbst laufen soll")
        self.setMinimumWidth(620)

        self.wahl = Zeitplanwahl(archiv=archiv)
        self.sicherung = Sicherungswahl(archiv=archiv)
        self.meldung = QLabel()
        self.meldung.setWordWrap(True)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        knoepfe.button(QDialogButtonBox.Save).setText("Übernehmen")
        knoepfe.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self._übernehmen)
        knoepfe.rejected.connect(self.reject)

        trenner = QFrame()
        trenner.setFrameShape(QFrame.HLine)

        # **Dieser Dialog rollt.** Er trägt vier längere Absätze, und
        # was sie erklären, ist nicht schmückend: dass MailBurg für den
        # Abruf nicht offen bleiben muss, dass die Passwörter am
        # Schlüsselbund hängen und deshalb eine Anmeldung nötig ist,
        # dass ein versäumter Abruf nachgeholt wird.
        #
        # Bei eingestellter Schriftgröße passte das nicht mehr hinein.
        # Stephan hat es am 2026-08-31 zweimal gemeldet – beim zweiten
        # Mal fehlten ganze Absätze. Eine Mindestgröße half nur, solange
        # niemand das Fenster kleiner zieht; ein Rollbereich hilft
        # immer.
        #
        # Die Knöpfe bleiben draußen: »Übernehmen« darf nie
        # wegscrollen.
        inhalt = QWidget()
        innen = QVBoxLayout(inhalt)
        innen.setContentsMargins(0, 0, 12, 0)
        innen.addWidget(self.wahl)
        innen.addWidget(trenner)
        innen.addWidget(self.sicherung)
        innen.addWidget(self.meldung)
        innen.addStretch()

        rollbar = QScrollArea()
        rollbar.setWidget(inhalt)
        rollbar.setWidgetResizable(True)
        rollbar.setFrameShape(QScrollArea.NoFrame)
        # Waagerecht rollen zu müssen ist immer ein Fehler im Aufbau.
        rollbar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(rollbar, 1)
        aufbau.addWidget(knoepfe)

    def _übernehmen(self) -> None:
        geklappt, text = self.wahl.anwenden()
        if geklappt:
            geklappt, text = self.sicherung.anwenden()
        if geklappt:
            self.accept()
            return
        # Nicht schließen, wenn es nicht geklappt hat: Sonst geht der
        # Anwender davon aus, es sei eingerichtet.
        self.meldung.setStyleSheet(farben.stil(False))
        self.meldung.setText(text)
