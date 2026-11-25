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
        """Der Text des Dialogs – als HTML, und das ist kein Zierrat.

        **``Fliesstext`` setzt ``Qt.RichText``**, und damit werden
        Zeilenumbrüche zu Leerzeichen. Am 2026-11-25 stand die
        Aufzählung der fehlenden Teile deshalb als ein einziger
        Absatz im Fenster: »… ihre Sicherheitsupdates. • PDF lesen:
        Ohne das ist …«. Lesbar war das nicht mehr.

        Ich hatte das Gegenteil angenommen und in einem Kommentar
        festgehalten – ein Screenshot aus der Erprobung hat es
        widerlegt. *Eine Annahme über die Oberfläche prüft man am
        Bild, nicht am Quelltext.*
        """
        import html as _html

        stuecke = [
            "<p>MailBurg kann noch nicht alles, was es soll. Dafür "
            "fehlen Programme, die nicht mitgeliefert werden – sie "
            "kommen aus der Paketverwaltung Ihres Systems und "
            "bekommen von dort auch ihre Sicherheitsupdates.</p>",
            "<ul>",
        ]
        for baustein in self.fehlende:
            # Maskiert, obwohl die Texte aus diesem Repo stammen: Was
            # einmal als HTML gilt, gilt es für jeden späteren Eintrag
            # auch – und der kommt vielleicht aus einer Paketliste.
            stuecke.append(
                f"<li><b>{_html.escape(baustein.name)}</b> – "
                f"{_html.escape(baustein.wofuer)}</li>"
            )
        stuecke.append("</ul>")
        stuecke.append(
            "<p>Ein Klick auf <b>Pakete installieren</b> öffnet ein "
            "Fenster, in dem Sie <b>nach Ihrem Passwort gefragt "
            "werden</b> – dem Ihres Benutzerkontos. Ohne das darf kein "
            "Programm etwas installieren.</p>"
            "<p>Das Fenster schließt sich von selbst, sobald es fertig "
            "ist. Danach geht es hier weiter.</p>"
        )
        return "".join(stuecke)

    def _terminalplatz(self) -> tuple[int, int]:
        """Wohin das Terminal gelegt werden soll – neben dieses Fenster.

        **Gemessen wird gegen den Dialog, nicht gegen das
        Hauptfenster.** Stephan am 2026-11-25: »Das Terminal landet
        hinter dem MailBurg Fenster«, und auf dem Bild lag es
        tatsächlich *über* dem Assistenten und nur unter diesem
        Dialog. Der Dialog ist das, was im Weg steht – und er steht
        in der Mitte, während das Hauptfenster oft den ganzen
        Bildschirm füllt. »Neben das Hauptfenster« hieße dann
        irgendwo außerhalb.

        Die Breite eines Terminals kennen wir nicht; geschätzt wird
        sie aus achtzig Zeichen der festen Systemschrift. **Keine
        geratene Pixelzahl** – die säße bei vergrößerter Schrift
        falsch, und wer eine Bildschirmtastatur oder große Schrift
        braucht, ist genau der, der die Passwortabfrage nicht suchen
        sollte.
        """
        from PySide6.QtGui import QFontDatabase, QFontMetrics

        fest = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        breite = QFontMetrics(fest).horizontalAdvance("0") * 80
        abstand = QFontMetrics(fest).height()

        meiner = self.frameGeometry()
        schirm = self.screen().availableGeometry()

        rechts = meiner.right() + abstand
        if rechts + breite <= schirm.right():
            return rechts, meiner.top()

        links = meiner.left() - abstand - breite
        if links >= schirm.left():
            return links, meiner.top()

        # Kein Platz daneben: dann wenigstens nicht darunter. Oben
        # links bleibt von einem mittigen Dialog fast immer frei.
        return schirm.left() + abstand, schirm.top() + abstand

    def _starten(self) -> None:
        self.installieren.setEnabled(False)
        # **»Alt+Tab« steht dabei, und das ist kein Eingeständnis.**
        # Die Position ist ein Wunsch an den Fenstermanager; unter
        # Wayland verfällt er. Ein Hinweis, der nur im Normalfall
        # stimmt, hilft gerade dem nicht, bei dem es schiefging.
        self.stand.setText(
            "Das Terminal ist offen – es sollte neben diesem Fenster "
            "liegen. Bitte dort das Passwort eingeben; danach geht es "
            "hier weiter. Ist es verdeckt, holen Sie es mit Alt+Tab "
            "nach vorn."
        )

        ordner = Path(tempfile.gettempdir())
        self._marke = ordner / f"mailburg-nachruesten-{os_pid()}.fertig"
        self._marke.unlink(missing_ok=True)

        if kern.im_terminal(
            self.fehlende, self._marke, self._terminalplatz()
        ) is None:
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
