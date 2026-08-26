"""Die ausführliche Suche als Maske.

Wer nur ``rechnung`` sucht, tippt das oben ins Feld und ist fertig. Diese
Maske ist für den anderen Fall: alle Rechnungen eines Lieferanten aus dem
vorletzten Jahr, mit Anhang, größer als ein Megabyte. Das schreibt niemand
freihändig hin, ohne die Sprache zu kennen.

**Sie kann nichts, was die Suchsprache nicht kann.** Das ist keine
Beschränkung, sondern der Zweck: Die Maske baut einen Suchausdruck
zusammen und zeigt ihn an. Wer sie ein paarmal benutzt hat, kennt die
Sprache nebenbei – und kann dieselbe Abfrage in der Zeitsteuerung
verwenden. Gäbe es Möglichkeiten, die nur hier bestehen, wäre die
Kommandozeile der schwächere Weg, und irgendwann liefen beide
auseinander.
"""

from __future__ import annotations

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)


def quoten(wert: str) -> str:
    """Setzt einen Wert in Anführungszeichen, wenn er Leerzeichen enthält."""
    wert = wert.strip()
    if not wert:
        return ""
    return f'"{wert}"' if " " in wert else wert


def _datumsmuster() -> str:
    """Das Datumsmuster der Systemsprache, mit vierstelligem Jahr.

    Dieselbe Regel wie in :mod:`mailburg.ui.datum`: Qts Kurzformat kürzt
    die Jahreszahl auf zwei Stellen, und in einem Archiv stünden Post von
    1998 und Post von 2098 dann beide als »98« da.
    """
    muster = QLocale().dateFormat(QLocale.ShortFormat)
    return muster if "yyyy" in muster else muster.replace("yy", "yyyy")


class Suchmaske(QDialog):
    """Stellt einen Suchausdruck aus Feldern zusammen."""

    def __init__(self, archiv=None, ausdruck: str = "", eltern=None) -> None:
        super().__init__(eltern)
        self.archiv = archiv
        self.setWindowTitle("Ausführlich suchen")
        self.setMinimumWidth(640)

        self.begriff = QLineEdit(ausdruck if " " not in ausdruck and ":" not in ausdruck else "")
        self.begriff.setPlaceholderText("Wort oder Wortteil – findet auch mitten im Wort")
        self.begriff.setAccessibleName("Suchbegriff")

        self.von = QLineEdit()
        self.von.setPlaceholderText("Name oder Adresse")
        self.an = QLineEdit()
        self.an.setPlaceholderText("Name oder Adresse")
        self.betreff = QLineEdit()
        self.datei = QLineEdit()
        self.datei.setPlaceholderText("z. B. *.pdf oder Rechnung*")

        oben = QFormLayout()
        oben.addRow("Suchen nach:", self.begriff)
        oben.addRow("Von:", self.von)
        oben.addRow("An, Kopie oder Blindkopie:", self.an)
        oben.addRow("Betreff:", self.betreff)
        oben.addRow("Dateiname eines Anhangs:", self.datei)

        # ------------------------------------------------------- Eingrenzen

        self.konto = QComboBox()
        self.konto.addItem("(alle)", "")
        self.ordner = QComboBox()
        self.ordner.addItem("(alle)", "")
        self.ordner.setEditable(True)
        self._konten_fuellen()

        self.jahr_von = QSpinBox()
        self.jahr_von.setRange(0, 2100)
        self.jahr_von.setSpecialValueText("(alle)")
        self.jahr_bis = QSpinBox()
        self.jahr_bis.setRange(0, 2100)
        self.jahr_bis.setSpecialValueText("(alle)")

        jahre = QHBoxLayout()
        jahre.addWidget(self.jahr_von)
        jahre.addWidget(QLabel("bis"))
        jahre.addWidget(self.jahr_bis)
        jahre.addStretch()

        # Ein Kalender statt eines Eingabefelds: Wer einen Zeitraum
        # sucht, weiß meist "Anfang März bis Ostern" und nicht das genaue
        # Datum. Im Kalender sieht er es.
        self.zeitraum_an = QCheckBox("Nur aus einem Zeitraum")
        self.zeitraum_an.toggled.connect(self._zeitraum_umschalten)

        heute = QDate.currentDate()
        self.datum_von = QDateEdit(heute.addYears(-1))
        self.datum_bis = QDateEdit(heute)
        for feld in (self.datum_von, self.datum_bis):
            feld.setCalendarPopup(True)
            feld.setDisplayFormat(_datumsmuster())
            # Ein Archiv reicht weiter zurück als die Vorgabe von 1752.
            feld.setMinimumDate(QDate(1970, 1, 1))
            feld.setMaximumDate(heute.addYears(1))
        self.datum_von.setAccessibleName("Zeitraum von")
        self.datum_bis.setAccessibleName("Zeitraum bis")

        zeitraum = QHBoxLayout()
        zeitraum.addWidget(self.datum_von)
        zeitraum.addWidget(QLabel("bis"))
        zeitraum.addWidget(self.datum_bis)
        zeitraum.addStretch()

        self.archiviert = QLineEdit()
        self.archiviert.setPlaceholderText("2026 · 2026-08 · 26.08.2026")

        self.mit_anhang = QCheckBox("Nur Nachrichten mit Anhang")
        self.typ = QLineEdit()
        self.typ.setPlaceholderText("pdf, docx, jpg …")

        self.groesse_art = QComboBox()
        for beschriftung, zeichen in (
            ("(egal)", ""), ("größer als", ">"), ("kleiner als", "<")
        ):
            self.groesse_art.addItem(beschriftung, zeichen)
        self.groesse_wert = QLineEdit()
        self.groesse_wert.setPlaceholderText("5MB")
        self.groesse_wert.setMaximumWidth(120)

        groesse = QHBoxLayout()
        groesse.addWidget(self.groesse_art)
        groesse.addWidget(self.groesse_wert)
        groesse.addStretch()

        self.wichtigkeit = QComboBox()
        for beschriftung, wert in (
            ("(egal)", ""), ("hoch", "hoch"), ("normal", "normal"), ("niedrig", "niedrig")
        ):
            self.wichtigkeit.addItem(beschriftung, wert)

        self.ohne = QLineEdit()
        self.ohne.setPlaceholderText("Wörter, die nicht vorkommen sollen")

        unten = QFormLayout()
        unten.addRow("Postfach:", self.konto)
        unten.addRow("Ordner:", self.ordner)
        unten.addRow("Jahr:", jahre)
        unten.addRow("", self.zeitraum_an)
        unten.addRow("Zeitraum:", zeitraum)
        unten.addRow("Ins Archiv gekommen:", self.archiviert)
        unten.addRow("", self.mit_anhang)
        unten.addRow("Anhang vom Typ:", self.typ)
        unten.addRow("Größe:", groesse)
        unten.addRow("Wichtigkeit:", self.wichtigkeit)
        unten.addRow("Ohne:", self.ohne)

        eingrenzen = QGroupBox("Eingrenzen")
        eingrenzen.setLayout(unten)

        # ----------------------------------------------- Der fertige Ausdruck

        self.vorschau = QLineEdit()
        self.vorschau.setReadOnly(True)
        self.vorschau.setAccessibleName("Daraus entstehender Suchausdruck")
        self.vorschau.setStyleSheet("font-family: monospace")

        erklaerung = QLabel(
            "Das ist der Ausdruck, der gesucht wird. Sie können ihn kopieren "
            "und genauso auf der Kommandozeile verwenden."
        )
        erklaerung.setWordWrap(True)
        erklaerung.setEnabled(False)

        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoepfe.button(QDialogButtonBox.Ok).setText("Suchen")
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addLayout(oben)
        aufbau.addWidget(eingrenzen)
        aufbau.addSpacing(6)
        aufbau.addWidget(QLabel("Suchausdruck:"))
        aufbau.addWidget(self.vorschau)
        aufbau.addWidget(erklaerung)
        aufbau.addWidget(knoepfe)

        for feld in (self.begriff, self.von, self.an, self.betreff, self.datei,
                     self.archiviert, self.typ, self.groesse_wert, self.ohne):
            feld.textChanged.connect(self._vorschau_erneuern)
        for auswahl in (self.konto, self.ordner, self.groesse_art, self.wichtigkeit):
            auswahl.currentIndexChanged.connect(self._vorschau_erneuern)
        self.ordner.editTextChanged.connect(self._vorschau_erneuern)
        for zahl in (self.jahr_von, self.jahr_bis):
            zahl.valueChanged.connect(self._vorschau_erneuern)
        for kalender in (self.datum_von, self.datum_bis):
            kalender.dateChanged.connect(self._vorschau_erneuern)
        self.mit_anhang.toggled.connect(self._vorschau_erneuern)

        self._vorschau_erneuern()

    def _zeitraum_umschalten(self, an: bool) -> None:
        self.datum_von.setEnabled(an)
        self.datum_bis.setEnabled(an)
        self._vorschau_erneuern()

    def _konten_fuellen(self) -> None:
        if self.archiv is None:
            return
        konten: list[str] = []
        ordner: list[str] = []
        for konto, ordnername, _ in self.archiv.index.accounts():
            if konto not in konten:
                konten.append(konto)
            if ordnername not in ordner:
                ordner.append(ordnername)
        for name in konten:
            self.konto.addItem(name, name)
        for name in sorted(ordner):
            self.ordner.addItem(name, name)
        self.ordner.setCurrentIndex(0)

    # --------------------------------------------------------- Zusammenbauen

    def ausdruck(self) -> str:
        """Setzt aus den Feldern einen Suchausdruck zusammen."""
        teile: list[str] = []

        if self.begriff.text().strip():
            teile.append(quoten(self.begriff.text()))
        for feld, name in (
            (self.von, "von"), (self.an, "an"), (self.betreff, "betreff"),
            (self.datei, "datei"),
        ):
            if feld.text().strip():
                teile.append(f"{name}:{quoten(feld.text())}")

        konto = self.konto.currentData()
        if konto:
            teile.append(f"konto:{quoten(konto)}")
        ordner = self.ordner.currentText().strip()
        if ordner and not ordner.startswith("("):
            teile.append(f"ordner:{quoten(ordner)}")

        if self.zeitraum_an.isChecked():
            frueh, spaet = sorted(
                (self.datum_von.date(), self.datum_bis.date())
            )
            teile.append(f"seit:{frueh.toString('dd.MM.yyyy')}")
            teile.append(f"bis:{spaet.toString('dd.MM.yyyy')}")

        von, bis = self.jahr_von.value(), self.jahr_bis.value()
        if von and bis and von != bis:
            teile.append(f"jahr:{min(von, bis)}-{max(von, bis)}")
        elif von or bis:
            teile.append(f"jahr:{von or bis}")

        if self.archiviert.text().strip():
            teile.append(f"archiviert:{self.archiviert.text().strip()}")
        if self.mit_anhang.isChecked():
            teile.append("hat:anhang")
        if self.typ.text().strip():
            teile.append(f"typ:{self.typ.text().strip().lstrip('.')}")

        zeichen = self.groesse_art.currentData()
        wert = self.groesse_wert.text().strip()
        if wert:
            teile.append(f"groesse:{zeichen}{wert}")

        wichtig = self.wichtigkeit.currentData()
        if wichtig:
            teile.append(f"wichtigkeit:{wichtig}")

        for wort in self.ohne.text().split():
            teile.append(f"-{wort}")

        return " ".join(teile)

    def _vorschau_erneuern(self) -> None:
        fertig = self.ausdruck()
        self.vorschau.setText(fertig)
        self.vorschau.setPlaceholderText(
            "noch nichts eingegrenzt – das fände alles"
        )
