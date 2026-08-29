"""Ein Postfach per OAuth2 anmelden – das Fenster dazu.

**Warum das ein eigenes Fenster braucht.** Bei einem Passwort genügt ein
Eingabefeld. Hier muss der Anwender vorher eine Anwendung registriert
haben, und das weiß er nicht von selbst. Das Fenster sagt, was zu tun
ist, bevor es etwas verlangt.

**Die Anmeldung läuft im Browser.** MailBurg öffnet ihn und wartet auf
die Rückkehr. Das kann Minuten dauern – Passwort suchen, Zwei-Faktor
bestätigen, Berechtigungen lesen –, deshalb läuft das Warten in einem
eigenen Faden und das Fenster bleibt ansprechbar.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from mailburg.core.oauth2 import ANBIETER


class _Anmeldelauf(QObject):
    """Wartet auf die Rückkehr aus dem Browser, ohne das Fenster zu blockieren."""

    fertig = Signal(object)
    gescheitert = Signal(str)

    def __init__(self, anbieter, kennung) -> None:
        super().__init__()
        self.anbieter = anbieter
        self.kennung = kennung

    def laufen(self) -> None:
        from mailburg.core.oauth2 import OAuthFehler
        from mailburg.core.oauth2_anmelden import anmelden

        try:
            self.fertig.emit(anmelden(self.anbieter, self.kennung))
        except OAuthFehler as exc:
            self.gescheitert.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.gescheitert.emit(f"Unerwarteter Fehler: {exc}")


class Anmeldedialog(QDialog):
    """Fragt nach Anbieter und Anwendungskennung und meldet dann an."""

    def __init__(self, konto, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle(f"Anmelden: {konto.name}")
        self.konto = konto
        self.token = None
        self._faden = None

        aufbau = QVBoxLayout(self)

        einleitung = QLabel(
            "Manche Anbieter nehmen kein Passwort mehr an – Microsoft hat "
            "das für alle Konten abgeschaltet. Statt eines Passworts "
            "melden Sie sich einmal im Browser an; MailBurg bekommt "
            "danach eine Zugangsmarke, die es selbsttätig erneuert."
        )
        einleitung.setWordWrap(True)
        aufbau.addWidget(einleitung)

        aufbau.addSpacing(8)
        aufbau.addWidget(QLabel("<b>Anbieter</b>"))
        self.anbieter = QComboBox()
        for kennung, dienst in ANBIETER.items():
            self.anbieter.addItem(dienst.name, kennung)
        if konto.oauth_anbieter:
            stelle = self.anbieter.findData(konto.oauth_anbieter)
            if stelle >= 0:
                self.anbieter.setCurrentIndex(stelle)
        self.anbieter.currentIndexChanged.connect(self._hinweis_zeigen)
        aufbau.addWidget(self.anbieter)

        aufbau.addSpacing(8)
        aufbau.addWidget(QLabel("<b>Kennung Ihrer registrierten Anwendung</b>"))
        self.kennung = QLineEdit(konto.oauth_kennung)
        self.kennung.setPlaceholderText(
            "11111111-2222-3333-4444-555555555555"
        )
        aufbau.addWidget(self.kennung)

        # **Warum es keine mitgelieferte Kennung gibt.** Ohne diesen
        # Satz wirkt die Abfrage wie eine Schikane.
        self.hinweis = QLabel("")
        self.hinweis.setWordWrap(True)
        self.hinweis.setTextFormat(Qt.RichText)
        self.hinweis.setContentsMargins(0, 8, 0, 0)
        aufbau.addWidget(self.hinweis)
        self._hinweis_zeigen()

        self.stand = QLabel("")
        self.stand.setWordWrap(True)
        self.stand.setContentsMargins(0, 8, 0, 0)
        aufbau.addWidget(self.stand)

        self.knoepfe = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self.knoepfe.button(QDialogButtonBox.Ok).setText("Im Browser anmelden")
        self.knoepfe.accepted.connect(self._anmelden)
        self.knoepfe.rejected.connect(self.reject)
        aufbau.addWidget(self.knoepfe)

    def _gewaehlter_anbieter(self):
        return ANBIETER[self.anbieter.currentData()]

    def _hinweis_zeigen(self) -> None:
        dienst = self._gewaehlter_anbieter()
        self.hinweis.setText(
            f"<b>MailBurg bringt keine eigene Kennung mit.</b> Google "
            f"verlangt für den vollen Postfachzugriff ein jährlich zu "
            f"wiederholendes Sicherheitsaudit – für ein quelloffenes "
            f"Programm ohne Einnahmen nicht tragbar. Sie registrieren "
            f"deshalb eine Anwendung auf Ihren Namen.<br><br>"
            f"{dienst.hinweis}<br><br>"
            f"Schritt für Schritt steht das in <i>docs/oauth2.md</i>."
        )

    def _anmelden(self) -> None:
        from mailburg.core import accounts

        kennung = self.kennung.text().strip()
        if not kennung:
            self.stand.setText(
                "<b>Es fehlt die Kennung.</b> Ohne sie weiß der Anbieter "
                "nicht, welcher Anwendung er den Zugriff erlauben soll."
            )
            return

        geht, grund = accounts.schluesselbund_lage()
        if not geht:
            # Ohne Schlüsselbund müssten die Marken in eine Datei. Ein
            # Erneuerungs-Token ist auf Monate hinaus ein Vollzugang zum
            # Postfach - mehr wert als das Passwort, weil es die
            # Zwei-Faktor-Anmeldung schon hinter sich hat.
            QMessageBox.warning(self, "Kein Schlüsselbund", grund)
            return

        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)
        self.stand.setText(
            "Der Browser sollte sich öffnen. Melden Sie sich dort an und "
            "erlauben Sie MailBurg den Zugriff – dieses Fenster wartet "
            "solange."
        )

        lauf = _Anmeldelauf(self._gewaehlter_anbieter(), kennung)
        faden = QThread(self)
        lauf.moveToThread(faden)
        faden.started.connect(lauf.laufen)
        lauf.fertig.connect(self._geglueckt)
        lauf.gescheitert.connect(self._gescheitert)
        for signal in (lauf.fertig, lauf.gescheitert):
            signal.connect(faden.quit)
        faden.finished.connect(lauf.deleteLater)
        self._faden, self._lauf = faden, lauf
        faden.start()

    def _geglueckt(self, token) -> None:
        from mailburg.core import accounts

        self.konto.oauth_anbieter = self._gewaehlter_anbieter().kennung
        self.konto.oauth_kennung = self.kennung.text().strip()
        self.token = token

        if not accounts.token_setzen(self.konto, token):
            QMessageBox.warning(
                self,
                "Nicht abgelegt",
                "Die Anmeldung hat geklappt, ließ sich aber nicht im "
                "Schlüsselbund ablegen. In eine Datei geschrieben wird sie "
                "nicht – versuchen Sie es erneut, wenn der Schlüsselbund "
                "wieder erreichbar ist.",
            )
            self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(True)
            return

        self.accept()

    def _gescheitert(self, meldung: str) -> None:
        self.knoepfe.button(QDialogButtonBox.Ok).setEnabled(True)
        self.stand.setText(f"<b>Nicht angemeldet.</b> {meldung}")
