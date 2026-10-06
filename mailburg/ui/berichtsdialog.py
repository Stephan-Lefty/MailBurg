"""Wohin der Tagesbericht geht, wann und über welchen Weg.

**Warum das ein eigener Dialog ist und keine drei Abfragen.** Takt und
Ruhezeit beim Abruf sind zwei Zahlen; hier hängen sieben Angaben
zusammen, und sechs davon sind wertlos ohne die siebte. Wer sie
nacheinander abgefragt bekommt, weiß beim dritten Fenster nicht mehr,
wofür.

**Das Passwort steht nicht in der Registry.** Es geht in den Tresor –
dieselbe Begründung wie bei den Postfächern: Was ein Dienst ohne Zutun
braucht, muss er finden, und es soll trotzdem nicht im Klartext neben
der Konfiguration stehen.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTimeEdit,
    QVBoxLayout,
)

from mailburg.core import bericht
from mailburg.ui.fliesstext import Fliesstext


class Berichtsdialog(QDialog):
    """Die sieben Angaben auf einmal."""

    def __init__(self, lage: bericht.Lage, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Tagesbericht einrichten")

        senkrecht = QVBoxLayout(self)
        senkrecht.addWidget(Fliesstext(
            "<p>MailBurg schickt Ihnen, was es getan hat: wie viele Mails "
            "dazugekommen sind und ob das Archiv in Ordnung ist.</p>"
            "<p><b>Eine Störung kommt sofort</b> und wartet nicht auf die "
            "eingestellte Uhrzeit. Sie wiederholt sich nicht, solange sie "
            "dieselbe bleibt – und es kommt eine Entwarnung, sobald sie "
            "behoben ist.</p>"
            "<p><b>Bleibt eine Mail aus, läuft der Dienst nicht mehr.</b> "
            "Das ist dann selbst der Befund.</p>"
        ))

        formular = QFormLayout()

        self.an = QLineEdit(lage.an)
        self.an.setPlaceholderText("verwalter@example.org")
        formular.addRow("Bericht an:", self.an)

        self.uhr = QTimeEdit()
        self.uhr.setDisplayFormat("HH:mm")
        from PySide6.QtCore import QTime

        self.uhr.setTime(QTime(lage.zeit.hour, lage.zeit.minute))
        formular.addRow("Uhrzeit:", self.uhr)

        self.takt = QComboBox()
        for wort, tage in bericht.TAKTE:
            self.takt.addItem(wort, tage)
        stelle = self.takt.findData(lage.takt_tage)
        self.takt.setCurrentIndex(stelle if stelle >= 0 else 0)
        self.takt.setToolTip(
            "Wie oft die gute Nachricht kommt. Störungen gehen davon "
            "unberührt sofort hinaus.\n\n"
            "Täglich ist für einen Firmenserver richtig; für ein "
            "Privatarchiv genügt seltener. Wer dreißig gleichlautende "
            "Mails im Monat bekommt, liest keine davon."
        )
        formular.addRow("Wenn alles läuft:", self.takt)

        self.smtp = QLineEdit(
            f"{lage.smtp}:{lage.anschluss}" if lage.smtp else ""
        )
        self.smtp.setPlaceholderText("mail.example.org:587")
        self.smtp.setToolTip(
            "Der Postausgangsserver, über den MailBurg verschickt.\n\n"
            "Nehmen Sie ein eigenes Postfach – nicht eines der "
            "archivierten. Sonst landet jeder Bericht beim nächsten "
            "Abruf wieder im Archiv."
        )
        formular.addRow("Postausgang:", self.smtp)

        self.von = QLineEdit(lage.von)
        self.von.setPlaceholderText("archiv@example.org")
        formular.addRow("Absender:", self.von)

        self.benutzer = QLineEdit(lage.benutzer)
        self.benutzer.setPlaceholderText("meist dieselbe Adresse")
        formular.addRow("Anmeldename:", self.benutzer)

        self.passwort = QLineEdit()
        self.passwort.setEchoMode(QLineEdit.Password)
        self.passwort.setPlaceholderText(
            "leer lassen heißt: unverändert"
        )
        self.passwort.setToolTip(
            "Wird im Tresor abgelegt, nicht in der Registry."
        )
        formular.addRow("Passwort:", self.passwort)

        senkrecht.addLayout(formular)

        senkrecht.addWidget(Fliesstext(
            "<p>Verschickt wird über STARTTLS. Hat Ihr Server das nicht, "
            "gibt es eine Absage statt einer unverschlüsselten "
            "Verbindung.</p>"
        ))

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        senkrecht.addWidget(knoepfe)

    def ergebnis(self) -> tuple[Lageanteil, str]:
        """Die neue Lage und das Passwort – getrennt, weil sie getrennt
        aufbewahrt werden."""
        smtp, anschluss = bericht._server_lesen(self.smtp.text())
        zeit = self.uhr.time()
        neu = Lageanteil(
            an=self.an.text().strip(),
            stunde=zeit.hour(),
            minute=zeit.minute(),
            takt_tage=self.takt.currentData() or bericht.STANDARDTAKT,
            smtp=smtp,
            anschluss=anschluss,
            von=self.von.text().strip(),
            benutzer=self.benutzer.text().strip(),
        )
        return neu, self.passwort.text()


class Lageanteil:
    """Was der Dialog zurückgibt – und wie es in Variablen aussieht.

    **Eigene kleine Klasse statt ``bericht.Lage``.** Dort steht eine
    ``time``; hier kommen Stunde und Minute aus einem Qt-Feld, und die
    Umwandlung in Variablen ist das, was der Aufrufer braucht. Sie hier
    zu halten spart dem Kern eine Abhängigkeit, die er nicht hat.
    """

    def __init__(self, *, an: str, stunde: int, minute: int, takt_tage: int,
                 smtp: str, anschluss: int, von: str, benutzer: str) -> None:
        self.an = an
        self.stunde = stunde
        self.minute = minute
        self.takt_tage = takt_tage
        self.smtp = smtp
        self.anschluss = anschluss
        self.von = von
        self.benutzer = benutzer

    def als_variablen(self) -> dict[str, str]:
        return {
            bericht.AN: self.an,
            bericht.UHR: f"{self.stunde:02d}:{self.minute:02d}",
            bericht.TAKT: str(self.takt_tage),
            bericht.SMTP: (
                f"{self.smtp}:{self.anschluss}" if self.smtp else ""
            ),
            bericht.VON: self.von,
            bericht.BENUTZER: self.benutzer,
        }
