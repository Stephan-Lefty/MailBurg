"""Der Nachweis vor dem Aufräumen – im Fenster.

**Die Frage, die `mailburg pruefen` nicht beantworten kann.** Die
Gesundheitsprüfung sieht sich das Archiv an und sagt, ob es heil ist.
Ob darin *alles* liegt, kann sie nicht wissen – ein Archiv kann nicht
prüfen, was es nie gesehen hat. Genau dafür gibt es den Abgleich: Er
fragt den Server, was dort vor einem Stichtag liegt, und hält jede
einzelne Nummer gegen das Archiv.

Gebaut wurde er am 2026-08-25 für die Kommandozeile. Dort stand er
seitdem – vollständig, mit Stichtag und Kontoauswahl, und für alle
unsichtbar, die MailBurg über das Fenster benutzen. Das ist fast jeder.

Der Anlass, es nachzuholen, war ein Fehler am 2026-09-22: Zwei Tage
lang kam Post nicht an, das Archiv war dabei kerngesund, und
`mailburg pruefen` meldete zu Recht »alles in Ordnung«. Gefunden hat es
ein Mensch, dem auffiel, dass im Postfach etwas lag, was im Archiv
fehlte. **Genau diese Beobachtung macht der Abgleich von selbst.**
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from mailburg.ui.arbeit import Auftrag, Läufer
from mailburg.ui.fliesstext import Fliesstext

#: Zur Auswahl stehende Stichtage. Bewusst grob: Es geht darum, ob man
#: aufräumen kann, nicht um Tagesgenauigkeit.
ZEITRAEUME: list[tuple[str, int]] = [
    ("älter als 3 Monate", 90),
    ("älter als 6 Monate", 180),
    ("älter als 1 Jahr", 365),
    ("älter als 2 Jahre", 730),
]


class Abgleichlauf(Auftrag):
    """Fragt je Konto den Server und hält alles gegen das Archiv."""

    def __init__(self, archiv_pfad, konten, stichtag: date) -> None:
        super().__init__()
        self.archiv_pfad = archiv_pfad
        self.konten = list(konten)
        self.stichtag = stichtag

    def ausfuehren(self):
        from mailburg.core import abgleich as kern
        from mailburg.core import accounts
        from mailburg.core.archive import Archive
        from mailburg.core.sync import Abrufzustand
        from mailburg.sources import quelle_fuer
        from mailburg.sources.imap import ImapFehler

        befunde = []
        # Lesend öffnen: Der Abgleich ändert nichts, und das Hauptfenster
        # hält dasselbe Archiv offen.
        with Archive.open(self.archiv_pfad, exclusive=False) as archiv:
            zustand = Abrufzustand(archiv.uuid)
            for nummer, konto in enumerate(self.konten, 1):
                if self.abgebrochen:
                    break
                self.meldung.emit(f"{konto.name} wird geprüft …")
                self.fortschritt.emit(nummer - 1, len(self.konten))

                try:
                    quelle = quelle_fuer(
                        konto, accounts.passwort_holen(konto)
                    )
                except ImapFehler as exc:
                    # **Ein Postfach, das nicht antwortet, ist ein
                    # Befund und kein Grund aufzuhören.** Wer danach
                    # aufräumt, verlässt sich sonst auf eine Prüfung,
                    # die dieses Konto gar nicht gesehen hat.
                    befunde.append(
                        kern.Befund(konto=konto.name, stichtag=self.stichtag,
                                    fehler=str(exc))
                    )
                    continue

                try:
                    befunde.append(kern.pruefen(
                        archiv, quelle, konto.name, self.stichtag,
                        zustand=zustand,
                    ))
                finally:
                    quelle.close()

        self.fortschritt.emit(len(self.konten), len(self.konten))
        return befunde


class Abgleichdialog(QDialog):
    """Zeigt, ob alles Ältere wirklich im Archiv liegt."""

    fertig = Signal(object)

    def __init__(self, archiv, konten, eltern=None) -> None:
        super().__init__(eltern)
        self.setWindowTitle("Ist alles im Archiv?")
        self.setMinimumWidth(680)
        self.archiv = archiv
        self.konten = list(konten)
        self.laeufer = None
        self.befunde: list = []

        erklaerung = Fliesstext(
            "<p>Bevor Sie Ihr Postfach im Mailprogramm aufräumen lassen, "
            "sollten Sie wissen, ob das Archiv wirklich vollständig ist. "
            "MailBurg fragt dafür jedes Postfach, welche Nachrichten dort "
            "älter als ein Stichtag sind, und hält <b>jede einzelne</b> "
            "gegen das Archiv.</p>"
            "<p>Das ist etwas anderes als <i>Archiv prüfen</i>: Die Prüfung "
            "sagt, ob das Archiv heil ist. Ob darin alles liegt, kann sie "
            "nicht wissen – <b>ein Archiv kann nicht prüfen, was es nie "
            "gesehen hat.</b></p>"
            "<p>Es wird nur gelesen. Im Postfach ändert sich nichts.</p>"
        )

        kopf = QHBoxLayout()
        kopf.addWidget(QLabel("Prüfen, was"))
        self.zeitraum = QComboBox()
        for text, tage in ZEITRAEUME:
            self.zeitraum.addItem(text, tage)
        self.zeitraum.setCurrentIndex(1)
        self.zeitraum.setAccessibleName("Zeitraum")
        kopf.addWidget(self.zeitraum)
        kopf.addWidget(QLabel("ist – in"))
        self.kontowahl = QComboBox()
        self.kontowahl.addItem(
            f"allen {len(self.konten)} Postfächern dieses Archivs", None
        )
        for konto in self.konten:
            self.kontowahl.addItem(konto.name, konto.name)
        self.kontowahl.setAccessibleName("Postfach")
        kopf.addWidget(self.kontowahl, 1)

        self.balken = QProgressBar()
        self.balken.hide()
        self.stand = QLabel("")
        self.stand.setWordWrap(True)

        self.liste = QTreeWidget()
        self.liste.setHeaderLabels(["Postfach / Ordner", "Auf dem Server", "Befund"])
        self.liste.setColumnCount(3)
        # **Die Breite kommt von Qt, nicht von einer Zahl.** Bei 24 pt
        # war der Spaltenkopf »Befund« sonst 19 Pixel zu schmal – vom
        # Prüfwerkzeug gemeldet, bevor das Fenster je jemand gesehen
        # hat. Geratene Pixelzahlen sitzen falsch, sobald jemand die
        # Schrift ändert, und in MailBurg lässt sie sich ändern.
        spaltenkopf = self.liste.header()
        spaltenkopf.setSectionResizeMode(0, QHeaderView.Stretch)
        spaltenkopf.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        spaltenkopf.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.liste.hide()

        self.knoepfe = QDialogButtonBox()
        self.starten = QPushButton("Jetzt prüfen")
        self.starten.setDefault(True)
        self.knoepfe.addButton(self.starten, QDialogButtonBox.ActionRole)
        self.schliessen = self.knoepfe.addButton(QDialogButtonBox.Close)
        self.starten.clicked.connect(self._starten)
        self.knoepfe.rejected.connect(self.reject)
        self.schliessen.clicked.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(erklaerung)
        aufbau.addSpacing(8)
        aufbau.addLayout(kopf)
        aufbau.addSpacing(8)
        aufbau.addWidget(self.balken)
        aufbau.addWidget(self.stand)
        aufbau.addWidget(self.liste, 1)
        aufbau.addWidget(self.knoepfe)

        if not self.konten:
            self.stand.setText(
                "Diesem Archiv ist kein Postfach zugeordnet – es gibt nichts "
                "abzugleichen. Das ändern Sie unter "
                "Einstellungen → Postfächer."
            )
            self.starten.setEnabled(False)

    # ------------------------------------------------------------ Ablauf

    def _stichtag(self) -> date:
        from mailburg.core.abgleich import stichtag_aus_tagen

        return stichtag_aus_tagen(self.zeitraum.currentData())

    def _starten(self) -> None:
        gewaehlt = self.kontowahl.currentData()
        konten = (
            [k for k in self.konten if k.name == gewaehlt] if gewaehlt
            else self.konten
        )
        self.starten.setEnabled(False)
        self.zeitraum.setEnabled(False)
        self.kontowahl.setEnabled(False)
        self.liste.clear()
        self.liste.hide()
        self.balken.setRange(0, len(konten))
        self.balken.setValue(0)
        self.balken.show()

        auftrag = Abgleichlauf(self.archiv.root, konten, self._stichtag())
        # **Die Signale werden vor dem Start verbunden**, sonst geht ein
        # Ergebnis verloren, das schneller da ist als die Verbindung.
        # Und benannte Methoden statt Lambdas: Qt kann einem Lambda
        # keinen Faden zuordnen und ruft es im Arbeitsfaden auf – siehe
        # den Kommentar in ``ui/arbeit.py``.
        auftrag.meldung.connect(self.stand.setText)
        auftrag.fortschritt.connect(self._fortschritt)
        auftrag.fertig.connect(self._auswerten)
        auftrag.gescheitert.connect(self._gescheitert)
        self.laeufer = Läufer(auftrag)
        self.laeufer.starten()

    def _fortschritt(self, fertig: int, gesamt: int) -> None:
        self.balken.setRange(0, gesamt or 0)
        self.balken.setValue(fertig)

    def _gescheitert(self, grund: str) -> None:
        self.balken.hide()
        self.stand.setText(f"Der Abgleich ist nicht durchgelaufen: {grund}")
        self._freigeben()

    def _freigeben(self) -> None:
        self.starten.setEnabled(True)
        self.zeitraum.setEnabled(True)
        self.kontowahl.setEnabled(True)
        self.laeufer = None

    def _auswerten(self, befunde) -> None:
        from mailburg.core.abgleich import urteil

        self.befunde = list(befunde or [])
        self.balken.hide()
        self._freigeben()
        self._baum_fuellen()
        self.liste.show()

        # **Der schlechteste Befund bestimmt die Aussage.** Ein einziges
        # Postfach, das nicht antwortet, macht das Gesamturteil
        # unbrauchbar – wer danach aufräumt, verlässt sich auf eine
        # Prüfung, die dieses Konto gar nicht gesehen hat.
        bedenklich = [b for b in self.befunde if not b.unbedenklich]
        if not self.befunde:
            self.stand.setText("Es wurde nichts geprüft.")
        elif bedenklich:
            self.stand.setText(
                f"<b>In {len(bedenklich)} von {len(self.befunde)} Postfächern "
                f"sollte jetzt nichts aufgeräumt werden.</b><br>"
                + urteil(bedenklich[0]).replace("\n", "<br>")
            )
        else:
            tag = self.befunde[0].stichtag.strftime("%d.%m.%Y")
            gesamt = sum(b.geprueft for b in self.befunde)
            # Ohne eine einzige geprüfte Nachricht gibt es nichts
            # freizugeben. »Alle 0 sind im Archiv, räumen Sie
            # gefahrlos auf« wäre eine Unbedenklichkeitsbescheinigung
            # für einen Vergleich, den es nicht gab.
            self.stand.setText(
                f"<b>Alle {gesamt} Nachrichten vor dem {tag} sind im "
                f"Archiv.</b><br>Sie können sie im Mailprogramm gefahrlos "
                f"aufräumen lassen."
                if gesamt else
                f"<b>In keinem Postfach liegt etwas, was älter als der "
                f"{tag} wäre.</b><br>Es gab also nichts zu vergleichen."
            )
        self.stand.setTextFormat(Qt.RichText)
        self.fertig.emit(self.befunde)

    def _baum_fuellen(self) -> None:
        for befund in self.befunde:
            oben = QTreeWidgetItem(self.liste, [befund.konto, "", ""])
            if befund.fehler:
                oben.setText(2, "nicht erreichbar")
                oben.setToolTip(2, befund.fehler)
                continue

            oben.setText(1, str(befund.geprueft))
            # **»Vollständig« nur, wo etwas verglichen wurde.** Beim
            # ersten echten Einsatz am 2026-09-22 stand bei zwei
            # Postfächern »0 – vollständig«: Null geprüft, und daneben
            # eine Unbedenklichkeitsbescheinigung. Wo nichts war, wurde
            # nichts verglichen; das ist kein Befund, sondern die
            # Abwesenheit eines Befunds.
            #
            # Bei den Ordnern darunter stand es von Anfang an richtig.
            # Zwei Stellen, eine nachgezogen, die andere nicht – zum
            # wiederholten Mal in diesem Projekt.
            oben.setText(
                2,
                "unklar" if befund.unklar
                else f"{befund.fehlend} fehlen" if befund.fehlend
                else "vollständig" if befund.geprueft
                else "nichts so altes vorhanden",
            )
            for eintrag in befund.ordner:
                if eintrag.uidvalidity_geaendert:
                    lage = "Nummerierung geändert – kein Vergleich möglich"
                elif eintrag.fehlend:
                    lage = f"{len(eintrag.fehlend)} fehlen"
                elif eintrag.auf_dem_server:
                    lage = "vollständig"
                else:
                    lage = "nichts so altes vorhanden"
                QTreeWidgetItem(
                    oben,
                    [eintrag.ordner, str(eintrag.auf_dem_server), lage],
                )
            # Aufgeklappt nur, wo etwas zu sehen ist: Wer zehn
            # vollständige Postfächer hat, will keine hundert Ordner
            # durchscrollen, um die eine Fehlstelle zu finden.
            oben.setExpanded(bool(befund.fehlend) or befund.unklar)

    def reject(self) -> None:
        # **Bitten, nicht warten.** Ein ``wait()`` blockiert den Faden
        # der Oberfläche; bei einem Server, der nicht antwortet, hinge
        # das Fenster minutenlang. Der Läufer hält sich selbst am Leben
        # und räumt sich auf – siehe ``arbeit.alle_abbrechen``.
        if self.laeufer is not None:
            self.laeufer.auftrag.abbrechen()
        super().reject()
