"""Was ein bestimmter Benutzer im Archiv sehen darf.

Ein schmales Ding mit einer einzigen Aufgabe: den Rechten eines
Benutzers eine SQL-Bedingung zu geben, die in **jede** Abfrage
eingesetzt wird.

**Warum das in die Abfrage gehört und nicht dahinter.** Wer erst sucht
und dann wegfiltert, baut ein Leck. Die Trefferzahl stimmt dann nicht
mit dem überein, was in der Liste steht – und aus »1.284 Treffer, davon
12 sichtbar« liest jeder heraus, dass es 1.272 weitere gibt. Dasselbe
gilt für die Sortierung, für das Blättern und für jede Statistik. Was
jemand nicht sehen darf, darf auch in keiner Zahl auftauchen.

**Die Vorgabe ist »alles«, und das ist kein Versehen.** Auf dem
Arbeitsplatz gibt es keine Benutzer: Wer am Rechner sitzt, hat das
Archiv ohnehin, und eine Prüfung davor wäre Theater. Die Vorgabe auf
»nichts« zu setzen hieße, dass Kommandozeile und Desktop-Fenster nichts
mehr finden.

Damit die Vorgabe niemandem stillschweigend durchrutscht, heißt sie
``Sicht.alles()`` und muss benannt werden. Und ``tests/test_sicht.py``
prüft nach, dass jede lesende Methode des Index eine Sicht annimmt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sicht:
    """Die Postfächer, die jemand sehen darf."""

    #: Alles sehen. Dann spielen ``konten`` keine Rolle.
    alles: bool = True

    #: Sonst: genau diese Postfächer.
    konten: frozenset[str] = frozenset()

    @classmethod
    def alles_sehen(cls) -> Sicht:
        """Für den Arbeitsplatz, die Kommandozeile und den Verwalter."""
        return cls(alles=True)

    @classmethod
    def nichts_sehen(cls) -> Sicht:
        """Für einen Zugang, dem noch kein Postfach zugeordnet ist."""
        return cls(alles=False, konten=frozenset())

    @classmethod
    def fuer(cls, benutzer) -> Sicht:
        """Die Sicht eines Benutzers aus :mod:`mailburg.core.benutzer`.

        Ein stillgelegter Zugang sieht nichts – auch dann nicht, wenn
        bei ihm »alle Postfächer« angekreuzt ist. Sonst hinge die
        Wirkung des Stilllegens daran, dass es überall abgefragt wird.
        """
        if benutzer is None:
            return cls.alles_sehen()
        if not getattr(benutzer, "aktiv", True):
            return cls.nichts_sehen()
        if getattr(benutzer, "alle_postfaecher", False):
            return cls.alles_sehen()
        return cls(alles=False, konten=frozenset(benutzer.postfaecher))

    @property
    def unbeschraenkt(self) -> bool:
        return self.alles

    def darf_sehen(self, konto: str) -> bool:
        return self.alles or konto in self.konten

    def gefiltert(self, konten) -> list[str]:
        """Von einer Aufzählung von Postfächern die erlaubten, in Reihenfolge."""
        return [konto for konto in konten if self.darf_sehen(konto)]

    def bedingung(self, tabelle: str = "m") -> tuple[str, list[str]]:
        """Die SQL-Bedingung und ihre Werte.

        Immer eine gültige Bedingung, nie eine leere Zeichenkette: So
        lässt sie sich ohne Fallunterscheidung mit ``AND`` anhängen, und
        niemand kann sie versehentlich weglassen, weil sie »gerade leer«
        ist.

        Der Fall »sieht nichts« ergibt ``0`` – eine Bedingung, die auf
        nichts zutrifft. Nicht ``1``: Ein Zugang ohne zugeordnete
        Postfächer soll nichts finden, nicht alles.
        """
        if self.alles:
            return "1", []
        if not self.konten:
            return "0", []

        # Sortiert, damit dieselbe Sicht immer dieselbe Abfrage ergibt –
        # das hilft SQLites Zwischenspeicher für Abfragepläne und macht
        # Fehlersuche lesbar.
        werte = sorted(self.konten)
        platzhalter = ",".join("?" for _ in werte)
        return (
            f"EXISTS (SELECT 1 FROM locations l_sicht "
            f"WHERE l_sicht.msg_id = {tabelle}.id "
            f"AND l_sicht.account IN ({platzhalter}))",
            werte,
        )
