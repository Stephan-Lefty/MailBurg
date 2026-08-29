"""Mails aufbewahrungsrechtlich einordnen – aus der Trefferliste heraus.

Das Gegenstück zu ``mailburg einstufen`` auf der Kommandozeile. Dieselbe
Logik, nur ohne Tippen: Man sucht, sieht die Treffer, und stuft sie ein.

**Warum über die Suche und nicht Mail für Mail.** Wer ein Archiv
einordnet, hat hunderte Belege vor sich, keine drei. »Alles von der
Steuerkanzlei ist Buchungsbeleg« ist eine Regel, die sich als
Suchausdruck schreiben lässt – und sie wird nachvollziehbar, weil jeder
einzelne Vorgang im Journal steht.

**Warum ein eigenes Fenster und kein stiller Menüpunkt.** Eine
Einstufung verlängert Aufbewahrungsfristen um Jahre und lässt sich nicht
formlos zurücknehmen. Was hier geschieht, muss vorher dastehen: wie
viele Mails betroffen sind, was sich für sie ändert und bis wann sie
danach gesperrt sind.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from mailburg.core import sprache
from mailburg.core.retention import Category

#: Die Kategorien in der Reihenfolge, in der man sie braucht, mit einer
#: Erklärung, die ohne Gesetzeskenntnis auskommt. »Handelsbrief« und
#: »Buchungsbeleg« sind Begriffe aus dem Handelsgesetzbuch – wer sie
#: nicht kennt, soll trotzdem richtig entscheiden können.
STUFEN: tuple[tuple[Category, str, str], ...] = (
    (
        Category.BUCHUNGSBELEG,
        "Buchungsbeleg",
        "Rechnung, Quittung, Kontoauszug – alles, was eine Buchung stützt.",
    ),
    (
        Category.HANDELSBRIEF,
        "Handelsbrief",
        "Geschäftliche Korrespondenz ohne Belegcharakter: Angebote, "
        "Auftragsbestätigungen, Schriftwechsel zu einem Vorgang.",
    ),
    (
        Category.PRIVAT,
        "Privat",
        "Keine Aufbewahrungspflicht. Darf jederzeit gelöscht werden.",
    ),
    (
        Category.UNBESTIMMT,
        "Noch nicht eingeordnet",
        "Der Ausgangszustand. Wird sicherheitshalber wie die längste "
        "Pflicht behandelt.",
    ),
)


class Einstufungsdialog(QDialog):
    """Fragt, wozu die Treffer einer Suche zählen sollen."""

    def __init__(self, archiv, ausdruck: str, treffer: list, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Aufbewahrung festlegen")
        self.archiv = archiv
        self.ausdruck = ausdruck
        self.treffer = treffer

        aufbau = QVBoxLayout(self)

        gefunden = QLabel(
            f"<b>{sprache.mails(len(treffer))}</b> "
            + ("sind" if len(treffer) != 1 else "ist")
            + " gerade gefunden"
            + (f" mit <i>{ausdruck}</i>." if ausdruck else " (das ganze Archiv).")
        )
        gefunden.setWordWrap(True)
        aufbau.addWidget(gefunden)

        verteilung = self._verteilung()
        if verteilung:
            stand = QLabel("Bisher eingeordnet als: " + verteilung)
            stand.setWordWrap(True)
            aufbau.addWidget(stand)

        aufbau.addSpacing(8)
        frage = QLabel("<b>Wozu zählen diese Mails?</b>")
        aufbau.addWidget(frage)

        self.knoepfe: list[tuple[Category, QRadioButton]] = []
        for stufe, name, erklaerung in STUFEN:
            knopf = QRadioButton(name)
            aufbau.addWidget(knopf)
            text = QLabel(erklaerung)
            text.setWordWrap(True)
            text.setContentsMargins(24, 0, 0, 6)
            # Gedämpft, aber lesbar: Die Erklärung ist der eigentliche
            # Inhalt der Entscheidung, nicht Beiwerk.
            text.setEnabled(False)
            aufbau.addWidget(text)
            self.knoepfe.append((stufe, knopf))

        self.knoepfe[0][1].setChecked(True)

        aufbau.addSpacing(4)
        # **Was danach gilt.** Ohne diesen Satz ist die Entscheidung
        # abstrakt: »Buchungsbeleg« sagt nichts, »gesperrt bis Ende 2033«
        # sagt alles.
        self.folge = QLabel("")
        self.folge.setWordWrap(True)
        self.folge.setTextFormat(Qt.RichText)
        aufbau.addWidget(self.folge)

        for _stufe, knopf in self.knoepfe:
            knopf.toggled.connect(self._folge_zeigen)
        self._folge_zeigen()

        hinweis = QLabel(
            "Jede Änderung wird im Journal des Archivs vermerkt – mit "
            "vorheriger und neuer Einordnung. Rückgängig machen heißt "
            "hier: noch einmal einstufen, und auch das steht dann dort."
        )
        hinweis.setWordWrap(True)
        aufbau.addSpacing(8)
        aufbau.addWidget(hinweis)

        knopfleiste = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        knopfleiste.button(QDialogButtonBox.Ok).setText("Einstufen")
        knopfleiste.accepted.connect(self.accept)
        knopfleiste.rejected.connect(self.reject)
        aufbau.addWidget(knopfleiste)

    def _verteilung(self) -> str:
        """Wie die Treffer bisher eingeordnet sind, als lesbarer Satz."""
        zaehler: dict[str, int] = {}
        for eintrag in self.treffer:
            wert = getattr(eintrag, "category", "") or "unbestimmt"
            zaehler[wert] = zaehler.get(wert, 0) + 1
        if len(zaehler) == 1 and "unbestimmt" in zaehler:
            return ""
        namen = {stufe.value: name for stufe, name, _ in STUFEN}
        return ", ".join(
            f"{anzahl}× {namen.get(wert, wert)}"
            for wert, anzahl in sorted(zaehler.items(), key=lambda p: -p[1])
        )

    def gewaehlt(self) -> Category:
        for stufe, knopf in self.knoepfe:
            if knopf.isChecked():
                return stufe
        return Category.UNBESTIMMT

    def _folge_zeigen(self) -> None:
        """Sagt, was die Wahl für die Löschsperre bedeutet."""
        stufe = self.gewaehlt()
        offen = sum(
            1 for t in self.treffer
            if (getattr(t, "category", "") or "unbestimmt") != stufe.value
        )
        if not offen:
            self.folge.setText(
                "<i>Diese Mail ist bereits so eingeordnet.</i>"
                if len(self.treffer) == 1
                else f"<i>Alle {len(self.treffer)} sind bereits so "
                     f"eingeordnet.</i>"
            )
            return

        # Auch der Folgesatz richtet sich nach der Zahl: »1 Mail wird
        # geändert. Sie sind dann acht Jahre geschützt« las sich falsch.
        eine = offen == 1
        if stufe is Category.PRIVAT:
            was = (
                "Sie darf dann jederzeit gelöscht werden."
                if eine
                else "Sie dürfen dann jederzeit gelöscht werden."
            )
        else:
            jahre = self.archiv.policy.years(stufe)
            was = (
                f"Sie {'ist' if eine else 'sind'} dann {jahre} Jahre lang "
                f"vor dem Löschen geschützt – gerechnet ab dem Ende des "
                f"Jahres, aus dem die Mail stammt."
            )
        self.folge.setText(
            f"<b>{sprache.mails(offen)}</b> "
            + ("werden" if offen != 1 else "wird")
            + f" geändert. {was}"
        )
