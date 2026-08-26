"""Datenmodelle für die Oberfläche.

Qt trennt Daten und Darstellung, und das ist hier keine Förmlichkeit: Ein
Archiv kann eine halbe Million Mails enthalten. Sie alle in eine Liste zu
laden, hieße mehrere Gigabyte in den Speicher zu ziehen, damit der Anwender
die ersten dreißig Zeilen ansieht.

Deshalb wird nachgeladen, während gerollt wird. Die Suche liefert die
Gesamtzahl sofort – die steht in der Kopfzeile –, die Zeilen selbst kommen
in Blöcken nach.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from mailburg.ui import datum

#: So viele Treffer werden auf einmal nachgeladen. Groß genug, dass beim
#: Rollen keine Lücke entsteht, klein genug für eine sofortige Anzeige.
BLOCK = 200


class Trefferliste(QAbstractTableModel):
    """Die Suchergebnisse eines Archivs."""

    SPALTEN = ("📎", "Datum", "Absender", "Betreff", "Größe")

    #: Was in der Kopfzeile zu schmal ist, muss wenigstens vorgelesen
    #: werden können. Ein Spaltenkopf ohne Text ist für einen Screenreader
    #: eine namenlose Spalte.
    SPALTENNAMEN = ("Anhang", "Datum", "Absender", "Betreff", "Größe")

    #: Die Sortierfelder des Index, in der Reihenfolge der Spalten.
    SORTIERUNG = ("anhang", "datum", "absender", "betreff", "groesse")

    def __init__(self, suchindex=None) -> None:
        super().__init__()
        # Nicht "index" nennen: index() ist eine Kernmethode von Qts
        # Modellklasse. Wird sie durch ein Attribut verdeckt, scheitert
        # jede Anzeige mit "'Index' object is not callable" - und zwar
        # erst zur Laufzeit, tief in Qt.
        self.suchindex = suchindex
        self.ausdruck = ""
        self.treffer: list = []
        self.gesamt = 0
        self.sortierung = "datum"
        self.absteigend = True

    # ------------------------------------------------------------- Abfragen

    def suchen(self, ausdruck: str) -> None:
        """Setzt die Liste auf ein neues Suchergebnis."""
        self.beginResetModel()
        self.ausdruck = ausdruck
        self.treffer = []
        self.gesamt = 0
        if self.suchindex is not None:
            self.gesamt = self.suchindex.count(ausdruck)
            self.treffer = self.suchindex.search(
                ausdruck, limit=BLOCK,
                sortierung=self.sortierung, absteigend=self.absteigend,
            )
        self.endResetModel()

    def treffer_bei(self, zeile: int):
        if 0 <= zeile < len(self.treffer):
            return self.treffer[zeile]
        return None

    # ------------------------------------------------- Qt-Modellschnittstelle

    def rowCount(self, eltern=QModelIndex()) -> int:
        return 0 if eltern.isValid() else len(self.treffer)

    def columnCount(self, eltern=QModelIndex()) -> int:
        return len(self.SPALTEN)

    def canFetchMore(self, eltern=QModelIndex()) -> bool:
        return not eltern.isValid() and len(self.treffer) < self.gesamt

    def fetchMore(self, eltern=QModelIndex()) -> None:
        if eltern.isValid() or self.suchindex is None:
            return
        nachschub = self.suchindex.search(
            self.ausdruck, limit=BLOCK, offset=len(self.treffer),
            sortierung=self.sortierung, absteigend=self.absteigend,
        )
        if not nachschub:
            # Sonst fragte Qt endlos nach, wenn die Gesamtzahl nicht mehr
            # zur Wirklichkeit passt.
            self.gesamt = len(self.treffer)
            return
        anfang = len(self.treffer)
        self.beginInsertRows(QModelIndex(), anfang, anfang + len(nachschub) - 1)
        self.treffer.extend(nachschub)
        self.endInsertRows()

    def headerData(self, abschnitt: int, richtung, rolle=Qt.DisplayRole):
        if richtung != Qt.Horizontal:
            return None
        if rolle == Qt.DisplayRole:
            return self.SPALTEN[abschnitt]
        if rolle in (Qt.ToolTipRole, Qt.AccessibleTextRole):
            return self.SPALTENNAMEN[abschnitt]
        return None

    def sort(self, spalte: int, reihenfolge=Qt.AscendingOrder) -> None:
        """Sortiert neu – im Index, nicht in der geladenen Liste.

        Die Liste enthält immer nur die ersten paar hundert Treffer und
        lädt beim Blättern nach. Sie an Ort und Stelle umzusortieren
        ordnete deshalb nur diesen Ausschnitt: Die alphabetisch erste Mail
        des Archivs stünde nicht oben, sondern irgendwo - je nachdem, wie
        weit jemand vorher gescrollt hat.
        """
        if not 0 <= spalte < len(self.SORTIERUNG):
            return
        self.sortierung = self.SORTIERUNG[spalte]
        self.absteigend = reihenfolge == Qt.DescendingOrder
        self.suchen(self.ausdruck)

    def data(self, stelle: QModelIndex, rolle=Qt.DisplayRole):
        if not stelle.isValid():
            return None
        treffer = self.treffer[stelle.row()]
        spalte = stelle.column()

        if rolle == Qt.DisplayRole:
            if spalte == 0:
                return "📎" if treffer.has_attachments else ""
            if spalte == 1:
                # Nur der Tag; die Uhrzeit interessiert in einer Liste nicht.
                # In der Sprache des Systems, nicht als ISO-Zeichenkette.
                # Sortiert wird ohnehin in SQL, nicht über diesen Text.
                return datum.tag(treffer.date)
            if spalte == 2:
                return treffer.from_name or treffer.from_addr
            if spalte == 3:
                return treffer.subject or "(kein Betreff)"
            if spalte == 4:
                return menschenlesbar(treffer.size)

        if rolle == Qt.ToolTipRole:
            if spalte == 2:
                return treffer.sender_display
            if spalte == 3:
                return treffer.subject

        if rolle == Qt.TextAlignmentRole and spalte == 4:
            return int(Qt.AlignRight | Qt.AlignVCenter)

        return None


def menschenlesbar(bytes_zahl: int) -> str:
    """Bytezahl in etwas, das man vorlesen kann."""
    wert = float(bytes_zahl)
    for einheit in ("B", "KB", "MB", "GB"):
        if wert < 1024 or einheit == "GB":
            return f"{int(wert)} B" if einheit == "B" else f"{wert:.1f} {einheit}"
        wert /= 1024
    return f"{wert:.1f} GB"
