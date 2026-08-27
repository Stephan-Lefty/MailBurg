"""Wer das Programm gemacht hat – und wohin mit Fehlern und Ideen.

Ein Archivprogramm bekommt man selten zu Gesicht: Es läuft im
Hintergrund, und man sucht darin, wenn etwas fehlt. Gerade dann will
man wissen, wem man es anvertraut hat und an wen man sich wenden kann.

**Die Kontaktadresse steht hier absichtlich im Klartext.** Sonst gilt
in diesem Projekt die Regel, keine echten Adressen in etwas zu
schreiben, das veröffentlicht wird – hier ist die Veröffentlichung der
Zweck. Ein Weg zurück zum Urheber gehört zu einem Programm, dem man
jahrzehntealte Post überlässt.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from mailburg import __version__
from mailburg.ui import farben
from mailburg.ui.fliesstext import Fliesstext

#: Wohin Fehler gemeldet werden sollen.
FEHLER_URL = "https://github.com/Stephan-Lefty/MailBurg/issues"

#: Wohin alles andere geht.
KONTAKT = "Stephan-Lefty@Protonmail.com"


def text() -> str:
    """Der Inhalt des Fensters, als Rich Text.

    Die Verweise bekommen ihre Farbe aus :mod:`farben`: Qts Standardblau
    ist auf dunklem Grund kaum zu finden.
    """
    return (
        f"<p><b>MailBurg {__version__}</b></p>"
        f"<p>Das Programm wurde nach bestem Wissen und Gewissen von "
        f"<b>Stephan Rösner</b> mit Hilfe von <b>Claude</b> als "
        f"KI-Unterstützung erstellt.</p>"
        f"<p>Sollten Fehler auftauchen, dann melden Sie sie bitte hier:<br>"
        f"{farben.verweis(FEHLER_URL, FEHLER_URL)}<br>"
        f"oder schicken Sie mir eine Mail an "
        f"{farben.verweis('mailto:' + KONTAKT, KONTAKT)}.</p>"
        f"<p>Wenn Sie Ideen und Anregungen haben, dann gerne auch an "
        f"{farben.verweis('mailto:' + KONTAKT, KONTAKT)}.</p>"
    )


class Infofenster(QDialog):
    """Ein Fenster, das nichts kann außer dastehen."""

    def __init__(self, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Über MailBurg")
        self.setMinimumWidth(520)

        self.inhalt = Fliesstext(text())
        # Anklickbar: Wer einen Fehler melden will, soll nicht abtippen.
        self.inhalt.setOpenExternalLinks(True)
        self.inhalt.setTextInteractionFlags(
            Qt.TextBrowserInteraction | Qt.TextSelectableByMouse
        )

        knoepfe = QDialogButtonBox(QDialogButtonBox.Close)
        knoepfe.button(QDialogButtonBox.Close).setText("Schließen")
        knoepfe.rejected.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(self.inhalt)
        aufbau.addWidget(knoepfe)


def oeffnen(eltern=None) -> None:
    Infofenster(eltern).exec()
