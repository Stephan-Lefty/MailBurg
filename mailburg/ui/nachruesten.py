"""Der eine Dialog für fehlende Pakete – überall derselbe.

**An jeder Stelle gleich, und das ist die eigentliche Vorgabe.**
Stephan am 2026-11-25, nach einem Nachmittag mit drei verschiedenen
Hinweisen auf drei fehlende Pakete:

    Egal wo man MailBurg installiert, wir müssen dem User immer die
    Chance geben, dass er per Klick die Pakete nachinstallieren kann
    […] Alles andere macht kein Sinn und das muss an jeder Stelle, wo
    was nachinstalliert werden muss, gleich sein.

Deshalb gibt es hier genau ein Fenster und keinen Baukasten. Wer
irgendwo im Programm feststellt, dass etwas fehlt, ruft
:func:`fehlendes_nachruesten` auf und bekommt entweder ``True``
zurück – dann ist alles da und es kann weitergehen – oder ``False``,
weil der Anwender abgebrochen hat.

**Was der Dialog dem Anwender schuldet**, in dieser Reihenfolge:

1. *Warum* etwas gebraucht wird, in einem Satz ohne Fachjargon. Ein
   Paketname ist keine Begründung.
2. Dass gleich **nach dem Passwort gefragt** wird. Eine Abfrage, die
   unangekündigt kommt, wirkt wie ein Übergriff – und wer sie
   wegklickt, kommt nicht weiter und weiß nicht, warum.
3. Den **Befehl, der laufen wird**. Ein Programm, das ungefragt
   Pakete installiert, hat sein Vertrauen verspielt, auch wenn es
   das Richtige tut.
4. Einen Weg **hinaus**: Abbrechen muss möglich sein.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from mailburg.core import nachruesten as kern
from mailburg.ui.fliesstext import Fliesstext


def fehlendes_nachruesten(eltern=None, nur=None) -> bool:
    """Zeigt den Dialog, wenn etwas fehlt – sonst gar nichts.

    ``nur`` grenzt auf bestimmte Bausteine ein; ohne Angabe geht es um
    alles. Gibt zurück, ob jetzt alles da ist.

    **Fehlt nichts, erscheint kein Fenster.** Ein Dialog, der »alles
    in Ordnung« meldet, ist ein Klick, den niemand gebraucht hat.
    """
    fehlende = [b for b in kern.fehlendes() if nur is None or b in nur]
    if not fehlende:
        return True
    dialog = Nachruestdialog(fehlende, eltern)
    dialog.exec()
    return dialog.geschafft


class Nachruestdialog(QDialog):
    """Was fehlt, warum, und ein Knopf, der es holt."""

    def __init__(self, fehlende, eltern=None) -> None:
        super().__init__(eltern)
        self.fehlende = list(fehlende)
        self.geschafft = False
        self._marke: Path | None = None
        self._uhr: QTimer | None = None

        self.setWindowTitle("MailBurg fehlt noch etwas")
        aufbau = QVBoxLayout(self)

        self.text = Fliesstext(self._erklaerung())
        aufbau.addWidget(self.text)

        # **Der Befehl steht da, bevor er läuft.** Nicht im Kleingedruckten
        # und nicht erst hinterher.
        self.befehlsfeld = QPlainTextEdit(kern.zum_abtippen(self.fehlende))
        self.befehlsfeld.setReadOnly(True)
        self.befehlsfeld.setMaximumHeight(60)
        aufbau.addWidget(self.befehlsfeld)

        self.stand = QLabel("")
        self.stand.setWordWrap(True)
        self.stand.setTextInteractionFlags(Qt.TextSelectableByMouse)
        aufbau.addWidget(self.stand)

        self.knoepfe = QDialogButtonBox()
        self.installieren = self.knoepfe.addButton(
            "Pakete installieren", QDialogButtonBox.AcceptRole)
        self.weiter = self.knoepfe.addButton(
            "Weiter", QDialogButtonBox.AcceptRole)
        self.abbrechen = self.knoepfe.addButton(
            "Abbrechen", QDialogButtonBox.RejectRole)
        self.installieren.clicked.connect(self._starten)
        self.weiter.clicked.connect(self.accept)
        self.abbrechen.clicked.connect(self.reject)
        aufbau.addWidget(self.knoepfe)

        # **Weiter ist zu, solange etwas fehlt.** Stephans Vorgabe:
        # erst nach der Installation klickbar. Ein Knopf, der zu früh
        # geht, führt in eine Einrichtung, die später stecken bleibt.
        self.weiter.setEnabled(False)

        hindernis = kern.warum_nicht()
        if hindernis:
            # Kein Knopf, aber auch keine Sackgasse: Der Befehl steht
            # oben und lässt sich abtippen.
            self.installieren.setEnabled(False)
            self.stand.setText(
                f"{hindernis}\n\nDer Befehl oben hilft weiter – er "
                f"gehört in ein Terminal."
            )
            self.weiter.setEnabled(True)

    def _erklaerung(self) -> str:
        zeilen = [
            "MailBurg kann noch nicht alles, was es soll. Dafür fehlen "
            "Programme, die nicht mitgeliefert werden – sie kommen aus "
            "der Paketverwaltung Ihres Systems und bekommen von dort "
            "auch ihre Sicherheitsupdates.\n",
        ]
        for baustein in self.fehlende:
            zeilen.append(f"• {baustein.name}: {baustein.wofuer}")
        # **Keine Sternchen.** Ein QLabel kennt kein Markdown; sie
        # stünden wörtlich da. Und HTML wäre hier schlimmer: Qt hielte
        # dann den ganzen Text für HTML und verschluckte die
        # Zeilenumbrüche der Aufzählung darüber.
        zeilen.append(
            "\nEin Klick auf »Pakete installieren« öffnet ein Fenster, "
            "in dem Sie nach Ihrem Passwort gefragt werden – dem Ihres "
            "Benutzerkontos. Ohne das darf kein Programm etwas "
            "installieren.\n\n"
            "Das Fenster schließt sich von selbst, sobald es fertig "
            "ist. Danach geht es hier weiter."
        )
        return "\n".join(zeilen)

    def _starten(self) -> None:
        self.installieren.setEnabled(False)
        self.stand.setText(
            "Das Terminal ist offen. Bitte dort das Passwort eingeben – "
            "danach geht es hier weiter."
        )

        ordner = Path(tempfile.gettempdir())
        self._marke = ordner / f"mailburg-nachruesten-{os_pid()}.fertig"
        self._marke.unlink(missing_ok=True)

        if kern.im_terminal(self.fehlende, self._marke) is None:
            self.stand.setText(
                "Es ließ sich kein Terminal öffnen. Der Befehl oben "
                "hilft weiter."
            )
            self.weiter.setEnabled(True)
            return

        # **Auf die Datei warten, nicht auf den Prozess.**
        # ``gnome-terminal`` kehrt sofort zurück; die Begründung steht
        # bei ``kern.im_terminal``.
        self._uhr = QTimer(self)
        self._uhr.setInterval(500)
        self._uhr.timeout.connect(self._nachsehen)
        self._uhr.start()

    def _nachsehen(self) -> None:
        if self._marke is None or not self._marke.exists():
            return
        if self._uhr is not None:
            self._uhr.stop()
        self._marke.unlink(missing_ok=True)

        self.geschafft, meldung = kern.ergebnis(self.fehlende)
        self.stand.setText(meldung)
        self.weiter.setEnabled(True)
        if self.geschafft:
            self.befehlsfeld.hide()
            self.weiter.setDefault(True)
        else:
            self.installieren.setEnabled(True)


def os_pid() -> int:
    """Die eigene Vorgangsnummer – damit zwei Fenster sich nicht ins
    Gehege kommen."""
    import os

    return os.getpid()
