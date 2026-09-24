"""Einen Suchordner anlegen oder ändern.

Zwei Felder, ein Name und ein Suchausdruck – und darunter die Antwort
auf die Frage, die man sonst erst nach dem Anlegen bekäme: **Wie viele
Treffer hat dieser Ausdruck gerade?** Dieselbe Entscheidung wie im
Einlesedialog, aus demselben Grund: Wer »Maildir« nicht kennt, sieht
einem Pfadfeld nichts an – und wer die Suchsprache nicht kennt, einem
Suchausdruck ebenso wenig.

**Null Treffer verhindern das Anlegen nicht.** Ein Suchordner für
Rechnungen eines Lieferanten, von dem seit Jahren keine kam, ist
trotzdem richtig – und morgen kommt eine. Gesagt wird es trotzdem,
denn viel öfter steht dahinter ein Tippfehler.

Der Grund, warum es diesen Dialog gibt, steht in
:mod:`mailburg.core.suchordner`.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from mailburg.core import suchordner as kern
from mailburg.ui.fliesstext import Fliesstext

#: So lange nach der letzten Taste wird gezählt. Dieselbe Pause wie im
#: Hauptfenster: Wer tippt, soll nicht bei jedem Buchstaben eine
#: Datenbankabfrage auslösen.
TIPPAUSE = 350


class Suchordnerdialog(QDialog):
    """Name und Suchausdruck – mit Trefferzahl darunter."""

    def __init__(self, archiv=None, name: str = "", ausdruck: str = "",
                 eltern=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        self.setWindowTitle(
            "Suchordner ändern" if name else "Suchordner anlegen"
        )
        self.setMinimumWidth(560)

        erklaerung = Fliesstext(
            "<p>Ein Suchordner ist ein <b>Name für eine Suche</b>. Er "
            "enthält keine Post und verschiebt nichts – wer ihn anklickt, "
            "löst dieselbe Suche aus, die er auch tippen könnte.</p>"
            "<p>Dafür ist er immer aktuell: Was morgen ankommt und darauf "
            "passt, steht darin, ohne dass jemand einsortiert.</p>"
        )

        self.name = QLineEdit(name)
        self.name.setPlaceholderText("z. B. Rechnungen Telekom")
        self.name.setMaxLength(kern.NAME_MAX)
        self.name.textChanged.connect(self._pruefen)

        self.ausdruck = QLineEdit(ausdruck)
        self.ausdruck.setPlaceholderText("von:telekom betreff:Rechnung")
        self.ausdruck.textChanged.connect(self._tippen)

        self.maske_knopf = QPushButton("Ausführlich …")
        self.maske_knopf.clicked.connect(self._maske)

        zeile = QHBoxLayout()
        zeile.addWidget(self.ausdruck, 1)
        zeile.addWidget(self.maske_knopf)

        felder = QFormLayout()
        felder.addRow("Name:", self.name)
        felder.addRow("Sucht nach:", zeile)

        self.befund = QLabel("")
        self.befund.setWordWrap(True)

        self.knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.knoepfe.button(QDialogButtonBox.Ok).setText("Übernehmen")
        self.knoepfe.accepted.connect(self.accept)
        self.knoepfe.rejected.connect(self.reject)

        self.tipp_uhr = QTimer(self)
        self.tipp_uhr.setSingleShot(True)
        self.tipp_uhr.timeout.connect(self._pruefen)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(erklaerung)
        aufbau.addLayout(felder)
        aufbau.addWidget(self.befund)
        aufbau.addStretch(1)
        aufbau.addWidget(self.knoepfe)

        self._pruefen()

    # ------------------------------------------------------------ Prüfen

    def _tippen(self) -> None:
        self.tipp_uhr.start(TIPPAUSE)

    def _maske(self) -> None:
        from mailburg.search import maske as kern_maske
        from mailburg.ui.suchmaske import Suchmaske

        text = self.ausdruck.text().strip()
        werte = kern_maske.felder(text)
        maske = Suchmaske(self.archiv, text, self)
        if werte:
            maske.werte_setzen(werte)
        if maske.exec() == QDialog.Accepted:
            self.ausdruck.setText(maske.ausdruck())

    def _maske_anbieten(self) -> None:
        """Den Knopf nur freigeben, wenn die Maske zurückführt.

        **joka63s Lösung, und sie ist besser als jede Teilübernahme.**
        Die Maske schreibt zurück: Wer sie mit OK schließt, ersetzt den
        Ausdruck durch das, was in ihren Feldern steht. Was sie nicht
        darstellen kann, wäre danach still weg – an einem Suchordner,
        den sich jemand zurechtgelegt hat.

        Man könnte das erklären. Besser ist, es unmöglich zu machen: Wo
        die Umwandlung nicht geht, gibt es den Weg nicht.

        Sein Argument dazu (23.09.2026): *»Ein GUI-Nutzer wird die
        Suchausdrücke in der Regel mit der Maske erstellen. Ein
        Power-User, der eigene Suchausdrücke mit dem Texteditor
        erstellt, kann dann auch auf die Maske verzichten.«*

        **Ein ausgegrauter Knopf muss sagen, warum** – sonst liest er
        sich als kaputt, und jemand meldet ihn als Fehler.
        """
        from mailburg.search import maske as kern_maske

        geht = kern_maske.felder(self.ausdruck.text().strip()) is not None
        self.maske_knopf.setEnabled(geht)
        self.maske_knopf.setToolTip(
            "Die Suche zusammenklicken statt sie zu tippen – das Ergebnis "
            "landet im Feld daneben."
            if geht else
            "Dieser Suchausdruck lässt sich in der Maske nicht abbilden – "
            "sie käme nicht vollständig dorthin zurück. Bearbeiten Sie ihn "
            "deshalb direkt im Feld daneben."
        )

    def _pruefen(self) -> None:
        """Sagt, ob das so geht – und wie viele Treffer es gerade gibt."""
        self.tipp_uhr.stop()
        gut, meldung = self._befund()
        farbe = "" if gut else " color:palette(mid);"
        self.befund.setText(f"<span style='{farbe}'>{meldung}</span>")
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(gut)
        # Der Ausdruck kann sich beim Tippen von abbildbar zu nicht
        # abbildbar wandeln – der Knopf muss mitziehen.
        self._maske_anbieten()

    def _befund(self) -> tuple[bool, str]:
        try:
            kern.pruefen(self.name.text(), self.ausdruck.text())
        except kern.QueryError as exc:
            return False, f"Der Suchausdruck stimmt nicht: {exc}"
        except ValueError as exc:
            return False, str(exc)

        if self.archiv is None:
            return True, ""

        try:
            anzahl = self.archiv.index.count(self.ausdruck.text().strip())
        except Exception:  # noqa: BLE001 – die Zahl darf nie den Dialog kosten
            return True, ""

        if not anzahl:
            # **Kein Hinderungsgrund, aber ein Hinweis.** Weit häufiger
            # als der Lieferant ohne Rechnung ist der Tippfehler.
            return True, (
                "Darauf passt <b>gerade keine</b> Nachricht. Das kann so "
                "gewollt sein – häufiger steckt ein Tippfehler dahinter."
            )
        gezaehlt = f"{anzahl:,}".replace(",", ".")
        return True, f"Darauf passen gerade <b>{gezaehlt}</b> Nachrichten."

    # ---------------------------------------------------------- Ergebnis

    def werte(self) -> tuple[str, str]:
        """Name und Ausdruck, so wie sie gespeichert werden."""
        return kern.pruefen(self.name.text(), self.ausdruck.text())
