"""Die jährliche Nachfrage nach abgelaufenen Fristen.

**Einmal im Jahr, nicht bei jedem Start.** Fristen laufen zum
Jahresende ab; eine Meldung, die ab dem 1. Januar bei jedem Öffnen
erscheint, wird nach der dritten Wiederholung weggeklickt, ohne gelesen
zu werden – und dann auch beim vierten Mal, wenn es darauf ankäme.

Der 1. Mai als Stichtag hat einen Grund: Im Januar steckt man im
Jahresabschluss, und ob eine laufende Betriebsprüfung den Ablauf hemmt,
weiß man im Frühjahr eher.

**Zwei Archivarten, zwei Töne.** Im Geschäftsarchiv ist der Bericht eine
Pflichterinnerung: Die Frist ist abgelaufen, und nach ihrem Ablauf
verlangt die DSGVO, dass personenbezogene Daten auch wieder
verschwinden. Im Privatarchiv gibt es keine Fristen – dort ist es ein
Angebot beim Aufräumen, und Alter ist ein schlechter Ratgeber: Die Mail
vom verstorbenen Vater aus 2012 ist mehr wert als die von gestern.

Gelöscht wird in beiden Fällen nichts von selbst.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

# Die Logik steht in mailburg.core.nachfrage - sie ist eine Rechnung,
# keine Darstellung, und dürfte Qt nicht voraussetzen. Hier nur
# weitergereicht, damit Aufrufer nicht zwei Module kennen müssen.
from mailburg.core.nachfrage import (  # noqa: F401
    SCHLUESSEL,
    gefragt_vermerken,
    steht_an,
    zuletzt_gefragt,
)


class Fristendialog(QDialog):
    """Zeigt, was seine Frist hinter sich hat – und fragt nichts weiter."""

    def __init__(self, archiv, treffer: list, eltern=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        self.treffer = treffer
        self.ansehen = False

        geschaeftlich = archiv.mode.is_business
        self.setWindowTitle(
            "Aufbewahrungsfristen" if geschaeftlich else "Alte Post"
        )

        aufbau = QVBoxLayout(self)

        if geschaeftlich:
            kopf = (
                f"<b>{len(treffer)} Mails</b> haben ihre Aufbewahrungsfrist "
                f"hinter sich."
            )
            erklaerung = (
                "Fristen wirken in beide Richtungen. Sie schützen vor zu "
                "frühem Löschen – und nach ihrem Ablauf verlangt die DSGVO, "
                "dass personenbezogene Daten auch wieder verschwinden."
            )
            vorbehalt = (
                "<b>Gelöscht wird nichts von selbst.</b> Ob eine "
                "Betriebsprüfung läuft, ob ein Rechtsstreit anhängig ist "
                "oder eine Branchenvorschrift länger bindet, kann das "
                "Programm nicht wissen. Fragen Sie im Zweifel Ihren "
                "Steuerberater."
            )
        else:
            from mailburg.core.archive import ALT_AB_JAHREN

            kopf = (
                f"<b>{len(treffer)} Mails</b> sind älter als "
                f"{ALT_AB_JAHREN} Jahre."
            )
            erklaerung = (
                "Ein Privatarchiv kennt keine Aufbewahrungsfristen. Sie "
                "dürfen alles behalten, solange Sie wollen."
            )
            vorbehalt = (
                "<b>Alter ist kein Grund zum Löschen.</b> Bei privater Post "
                "sagt das Datum wenig darüber, was einem wichtig ist – eine "
                "Nachricht von jemandem, den es nicht mehr gibt, wiegt "
                "schwerer als die von gestern. Sehen Sie es sich an, wenn "
                "Sie mögen, und lassen Sie liegen, was bleiben soll."
            )

        for text, fett in ((kopf, True), (erklaerung, False)):
            marke = QLabel(text)
            marke.setWordWrap(True)
            aufbau.addWidget(marke)
            if fett:
                aufbau.addSpacing(4)

        verteilung = self._nach_jahr()
        if verteilung:
            jahre = QLabel(verteilung)
            jahre.setWordWrap(True)
            jahre.setContentsMargins(0, 8, 0, 8)
            aufbau.addWidget(jahre)

        schluss = QLabel(vorbehalt)
        schluss.setWordWrap(True)
        aufbau.addWidget(schluss)

        aufbau.addSpacing(8)
        merker = QLabel(
            f"Diese Frage kommt einmal im Jahr, ab dem "
            f"{archiv.policy.review_day}. "
            f"{_MONATE[archiv.policy.review_month]}."
        )
        merker.setWordWrap(True)
        aufbau.addWidget(merker)

        knoepfe = QDialogButtonBox(self)
        zeigen = QPushButton("Ansehen")
        zeigen.setDefault(True)
        zeigen.clicked.connect(self._ansehen)
        knoepfe.addButton(zeigen, QDialogButtonBox.AcceptRole)
        knoepfe.addButton("Nicht jetzt", QDialogButtonBox.RejectRole)
        knoepfe.rejected.connect(self.reject)
        aufbau.addWidget(knoepfe)

    def _ansehen(self) -> None:
        self.ansehen = True
        self.accept()

    def _nach_jahr(self) -> str:
        zaehler: dict[str, int] = {}
        for eintrag in self.treffer:
            jahr = (eintrag.date or "?")[:4]
            zaehler[jahr] = zaehler.get(jahr, 0) + 1
        if not zaehler:
            return ""
        return "Aus diesen Jahren: " + ", ".join(
            f"{jahr} ({anzahl})" for jahr, anzahl in sorted(zaehler.items())
        )


_MONATE = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober",
    11: "November", 12: "Dezember",
}
