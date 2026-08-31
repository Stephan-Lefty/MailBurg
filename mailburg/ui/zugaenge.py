"""Zugänge verwalten – die Oberfläche zu ``core.benutzer``.

Was ein Zugang ist und welche Rechte es gibt, steht dort. Hier geht es
darum, beides so zu zeigen, dass ein Verwalter es auch tut.

**Warum das eine Oberfläche braucht.** Bei fünfzig Menschen und sechzig
Postfächern ist die Rechtevergabe keine einmalige Sache, sondern
laufende Arbeit: Jemand kommt dazu, jemand wechselt die Abteilung,
jemand geht. Wenn das mühsam ist, bekommt am Ende jeder »darf alles« –
nicht aus Nachlässigkeit, sondern weil es schneller geht. Eine
Rechteverwaltung, die niemand benutzt, ist schlechter als keine: Sie
erweckt den Anschein, es gäbe Rechte.

**Zwei Bilder statt einer Tabelle.** Sechzig Postfächer als Spalten
wären nicht lesbar. Links stehen deshalb die Menschen, rechts die
Rechte des Gewählten – und die wichtigste Zeile im Fenster ist die, die
in einem Satz sagt, was er sehen darf.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from mailburg.core import sprache
from mailburg.core.benutzer import Benutzer, BenutzerFehler, Benutzerliste


class Zugangsdialog(QDialog):
    """Die Zugänge eines Archivs ansehen, anlegen, ändern, stilllegen."""

    def __init__(self, eltern=None, archiv=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        self.setWindowTitle("Zugänge zum Archiv")
        self.liste = archiv.benutzer if archiv is not None else Benutzerliste()
        self._laedt = False

        #: Die Postfächer, aus denen Post in diesem Archiv liegt. Nicht
        #: die eingerichteten Konten: Rechte gelten für das, was da ist.
        self.postfaecher = self._postfaecher_des_archivs()

        einleitung = QLabel(
            "<p>Wer sich an diesem Archiv anmelden darf – und welche "
            "Postfächer er dabei zu sehen bekommt.</p>"
            "<p>Solange MailBurg nur auf diesem Rechner läuft, ändert das "
            "nichts: Wer am Rechner sitzt, hat das Archiv ohnehin. Die "
            "Zugänge greifen, sobald es über einen Server erreichbar ist.</p>"
        )
        einleitung.setWordWrap(True)

        # -- links: die Menschen ------------------------------------------
        self.leute = QListWidget()
        self.leute.setSelectionMode(QAbstractItemView.SingleSelection)
        self.leute.currentRowChanged.connect(self._zeigen)
        self.leute.setMinimumWidth(220)

        neu = QPushButton("Hinzufügen …")
        neu.clicked.connect(self._anlegen)
        self.raus = QPushButton("Entfernen")
        self.raus.clicked.connect(self._entfernen)

        linke_knoepfe = QHBoxLayout()
        linke_knoepfe.addWidget(neu)
        linke_knoepfe.addWidget(self.raus)

        links = QVBoxLayout()
        links.addWidget(QLabel("<b>Zugänge</b>"))
        links.addWidget(self.leute, 1)
        links.addLayout(linke_knoepfe)

        # -- rechts: die Rechte des Gewählten -------------------------------
        self.anzeigename = QLineEdit()
        self.anzeigename.setPlaceholderText("Vor- und Nachname")
        self.anzeigename.textEdited.connect(self._name_uebernehmen)

        self.passwort = QPushButton("Passwort setzen …")
        self.passwort.clicked.connect(self._passwort)

        self.stilllegen = QPushButton("Stilllegen")
        self.stilllegen.clicked.connect(self._umschalten)

        kopf = QFormLayout()
        kopf.addRow("Name:", self.anzeigename)
        kopf.addRow("", self.passwort)
        kopf.addRow("", self.stilllegen)

        self.ist_verwalter = QCheckBox(
            "Darf Zugänge verwalten und Rechte vergeben"
        )
        self.ist_verwalter.toggled.connect(self._rolle_uebernehmen)
        self.sieht_alles = QCheckBox("Darf alle Postfächer sehen")
        self.sieht_alles.toggled.connect(self._rolle_uebernehmen)

        rollen_hinweis = QLabel(
            "Zwei verschiedene Dinge: Wer die Technik betreut, muss keine "
            "Post lesen dürfen – und wer alles liest, nicht über fremde "
            "Zugänge bestimmen."
        )
        rollen_hinweis.setWordWrap(True)
        rollen_hinweis.setEnabled(False)

        rollen = QVBoxLayout()
        rollen.addWidget(self.ist_verwalter)
        rollen.addWidget(self.sieht_alles)
        rollen.addWidget(rollen_hinweis)
        rollenkasten = QGroupBox("Rollen")
        rollenkasten.setLayout(rollen)

        self.kaesten = QListWidget()
        self.kaesten.itemChanged.connect(self._postfach_umgestellt)
        self.postfachkasten = QGroupBox("Diese Postfächer")
        innen = QVBoxLayout()
        innen.addWidget(self.kaesten)
        self.postfachkasten.setLayout(innen)

        #: Die wichtigste Zeile im Fenster: was der Gewählte sieht, in
        #: einem Satz. Ohne sie muss man aus Häkchen schließen.
        self.folge = QLabel()
        self.folge.setWordWrap(True)
        self.folge.setTextFormat(Qt.RichText)

        rechts = QVBoxLayout()
        rechts.addLayout(kopf)
        rechts.addWidget(rollenkasten)
        rechts.addWidget(self.postfachkasten, 1)
        rechts.addWidget(self.folge)

        self.rechte_seite = QGroupBox("Rechte")
        self.rechte_seite.setLayout(rechts)

        mitte = QHBoxLayout()
        mitte.addLayout(links, 1)
        mitte.addWidget(self.rechte_seite, 2)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        knoepfe.button(QDialogButtonBox.Save).setText("Übernehmen")
        knoepfe.accepted.connect(self._speichern)
        knoepfe.rejected.connect(self.reject)

        aussen = QVBoxLayout(self)
        aussen.addWidget(einleitung)
        aussen.addLayout(mitte, 1)
        aussen.addWidget(knoepfe)

        # **Nicht geraten, sondern gemessen.** 520 war zu wenig: Die
        # Erklärung zu den beiden Rechten brach nach einer Zeile ab, und
        # der Satz »Wer die Technik betreut, muss keine Geschäftspost
        # lesen dürfen« war halb weg - ausgerechnet der, der den
        # Unterschied erklärt. Am 2026-08-31 mit werkzeuge/lesbarkeit.py
        # nachgemessen: gebraucht werden 675.
        self.resize(760, 520)
        self.setMinimumHeight(self.sizeHint().height())
        self.resize(760, max(520, self.sizeHint().height()))
        self._fuellen()

    # -- Daten ------------------------------------------------------------

    def _postfaecher_des_archivs(self) -> list[str]:
        if self.archiv is None:
            return []
        try:
            return sorted({konto for konto, _, _ in self.archiv.index.accounts()})
        except Exception:  # noqa: BLE001 – ein leerer Index ist kein Fehler
            return []

    def _gewaehlt(self) -> Benutzer | None:
        zeile = self.leute.currentRow()
        if 0 <= zeile < len(self.liste.benutzer):
            return self.liste.benutzer[zeile]
        return None

    # -- Anzeige ----------------------------------------------------------

    def _fuellen(self) -> None:
        merken = self.leute.currentRow()
        self.leute.clear()
        for eintrag in self.liste:
            beschriftung = eintrag.anzeigename or eintrag.name
            if beschriftung != eintrag.name:
                beschriftung = f"{beschriftung} ({eintrag.name})"
            if not eintrag.aktiv:
                beschriftung += "  – stillgelegt"
            stueck = QListWidgetItem(beschriftung)
            if not eintrag.aktiv:
                stueck.setForeground(Qt.gray)
            self.leute.addItem(stueck)

        if self.liste.benutzer:
            self.leute.setCurrentRow(min(max(merken, 0), len(self.liste) - 1))
        else:
            self._zeigen(-1)

    def _zeigen(self, zeile: int) -> None:
        eintrag = self._gewaehlt()
        self.rechte_seite.setEnabled(eintrag is not None)
        self.raus.setEnabled(eintrag is not None)

        self._laedt = True
        try:
            if eintrag is None:
                self.anzeigename.clear()
                self.kaesten.clear()
                self.ist_verwalter.setChecked(False)
                self.sieht_alles.setChecked(False)
                self.folge.clear()
                return

            self.anzeigename.setText(eintrag.anzeigename)
            self.ist_verwalter.setChecked(eintrag.verwalter)
            self.sieht_alles.setChecked(eintrag.alle_postfaecher)
            self.stilllegen.setText(
                "Wieder zulassen" if not eintrag.aktiv else "Stilllegen"
            )

            self.kaesten.clear()
            for konto in self.postfaecher:
                stueck = QListWidgetItem(konto)
                stueck.setFlags(stueck.flags() | Qt.ItemIsUserCheckable)
                stueck.setCheckState(
                    Qt.Checked if konto in eintrag.postfaecher else Qt.Unchecked
                )
                self.kaesten.addItem(stueck)
        finally:
            self._laedt = False

        self._folge_beschreiben()

    def _folge_beschreiben(self) -> None:
        """Sagt in einem Satz, was der Gewählte sehen darf."""
        eintrag = self._gewaehlt()
        if eintrag is None:
            self.folge.clear()
            return

        # Die Postfächer sind nur wählbar, wenn nicht ohnehin alle gelten.
        self.postfachkasten.setEnabled(not eintrag.alle_postfaecher)

        if not eintrag.aktiv:
            text = ("<b>Stillgelegt.</b> Dieser Zugang meldet sich nicht mehr "
                    "an. Er bleibt eingetragen, damit sein Name im Journal "
                    "lesbar bleibt.")
        elif eintrag.alle_postfaecher:
            text = "Sieht <b>alle Postfächer</b> – auch die, die noch dazukommen."
        elif not eintrag.postfaecher:
            text = ("<b>Sieht nichts.</b> Dieser Zugang kann sich anmelden, "
                    "findet aber keine einzige Nachricht. Kreuzen Sie an, "
                    "was er sehen soll.")
        else:
            anzahl = len(eintrag.postfaecher)
            text = "Sieht {}.".format(
                sprache.anzahl(anzahl, "Postfach", "Postfächer")
            )
            fehlend = [k for k in eintrag.postfaecher if k not in self.postfaecher]
            if fehlend:
                text += (" Davon {} zurzeit nicht im Archiv – vielleicht "
                         "umbenannt oder noch nicht abgerufen.".format(
                             "liegt eines" if len(fehlend) == 1 else
                             f"liegen {len(fehlend)}"))

        if eintrag.verwalter and eintrag.aktiv:
            text += " Darf außerdem Zugänge verwalten."
        self.folge.setText(text)

    # -- Ändern -----------------------------------------------------------

    def _name_uebernehmen(self, text: str) -> None:
        eintrag = self._gewaehlt()
        if eintrag is not None and not self._laedt:
            eintrag.anzeigename = text

    def _rolle_uebernehmen(self) -> None:
        eintrag = self._gewaehlt()
        if eintrag is None or self._laedt:
            return
        eintrag.verwalter = self.ist_verwalter.isChecked()
        eintrag.alle_postfaecher = self.sieht_alles.isChecked()
        self._folge_beschreiben()
        self._fuellen()

    def _postfach_umgestellt(self, stueck: QListWidgetItem) -> None:
        eintrag = self._gewaehlt()
        if eintrag is None or self._laedt:
            return
        konto = stueck.text()
        if stueck.checkState() == Qt.Checked:
            if konto not in eintrag.postfaecher:
                eintrag.postfaecher.append(konto)
        elif konto in eintrag.postfaecher:
            eintrag.postfaecher.remove(konto)
        self._folge_beschreiben()

    def _anlegen(self) -> None:
        name, gedrueckt = QInputDialog.getText(
            self, "Zugang hinzufügen",
            "Anmeldename – Kleinbuchstaben, Ziffern, Punkt, Strich:",
        )
        if not gedrueckt or not name.strip():
            return

        try:
            neu = Benutzer(name)
            self.liste.hinzufuegen(neu)
        except BenutzerFehler as fehler:
            QMessageBox.warning(self, "Das geht so nicht", str(fehler))
            return

        # Gleich das Passwort: Ein Zugang ohne eines lässt niemanden
        # herein, sieht in der Liste aber aus wie ein fertiger.
        self._fuellen()
        self.leute.setCurrentRow(len(self.liste) - 1)
        self._passwort()

    def _passwort(self) -> None:
        eintrag = self._gewaehlt()
        if eintrag is None:
            return

        wort, gedrueckt = QInputDialog.getText(
            self, "Passwort setzen",
            f"Neues Passwort für »{eintrag.name}« – mindestens zehn Zeichen:",
            QLineEdit.Password,
        )
        if not gedrueckt:
            return
        try:
            eintrag.passwort_setzen(wort)
        except BenutzerFehler as fehler:
            QMessageBox.warning(self, "Das Passwort geht so nicht", str(fehler))
            return
        QMessageBox.information(
            self, "Gesetzt",
            f"Das Passwort für »{eintrag.name}« ist gesetzt. Es wird erst "
            f"mit »Übernehmen« gespeichert.",
        )

    def _umschalten(self) -> None:
        eintrag = self._gewaehlt()
        if eintrag is None:
            return
        eintrag.aktiv = not eintrag.aktiv
        self._fuellen()
        self._zeigen(self.leute.currentRow())

    def _entfernen(self) -> None:
        eintrag = self._gewaehlt()
        if eintrag is None:
            return

        antwort = QMessageBox.question(
            self, "Zugang entfernen",
            f"»{eintrag.name}« ganz aus der Liste nehmen?\n\n"
            f"Meistens ist Stilllegen richtiger: Der Zugang meldet sich dann "
            f"nicht mehr an, sein Name bleibt aber im Journal lesbar. Wer "
            f"entfernt wird, hinterlässt dort Vorgänge ohne Urheber.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return

        self.liste.entfernen(eintrag.name)
        self._fuellen()

    # -- Speichern --------------------------------------------------------

    def _speichern(self) -> None:
        if self.archiv is None:
            self.accept()
            return

        ohne_passwort = [b.name for b in self.liste if b.aktiv and not b.pruefwert]
        if ohne_passwort:
            antwort = QMessageBox.question(
                self, "Zugänge ohne Passwort",
                "Für {} ist kein Passwort gesetzt: {}.\n\n"
                "Diese Zugänge lassen niemanden herein – in der Liste sehen "
                "sie aber aus wie fertige. Trotzdem speichern?".format(
                    sprache.anzahl(len(ohne_passwort), "Zugang", "Zugänge"),
                    ", ".join(ohne_passwort),
                ),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if antwort != QMessageBox.Yes:
                return

        try:
            self.archiv.benutzer_setzen(self.liste)
        except BenutzerFehler as fehler:
            QMessageBox.warning(self, "So nicht", str(fehler))
            return
        except OSError as fehler:
            QMessageBox.warning(
                self, "Nicht gespeichert",
                f"Die Zugänge ließen sich nicht schreiben.\n\n{fehler}",
            )
            return

        self.accept()
