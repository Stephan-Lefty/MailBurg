"""Aufbewahrungsfristen für Deutschland, Österreich und die Schweiz.

Alle Fristen an einer Stelle, mit Fundstelle im Kommentar. Ändert der
Gesetzgeber etwas, ist genau diese Datei anzupassen – nirgends sonst im
Programm steht eine Jahreszahl.

**Kein Rechtsrat.** Die Tabellen bilden den Regelfall ab. Ob eine bestimmte
Mail Handelsbrief oder Buchungsbeleg ist, ob eine Branchenvorschrift längere
Fristen setzt und ob eine laufende Prüfung den Ablauf hemmt, kann nur der
Anwender oder sein Steuerberater beurteilen. Das Programm rechnet, es
entscheidet nicht.

**In beide Richtungen.** Fristen schützen nicht nur vor zu frühem Löschen.
Nach Ablauf verlangt Art. 5 Abs. 1 lit. e DSGVO (Speicherbegrenzung), dass
personenbezogene Daten auch wieder verschwinden. Deshalb liefert dieses
Modul beides: :func:`is_locked` für den Schutz und :func:`is_due` für die
Fälligkeit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Jurisdiction(StrEnum):
    """Rechtsraum, nach dem gerechnet wird."""

    DE = "de"
    AT = "at"
    CH = "ch"


class Category(StrEnum):
    """Wozu eine Mail aufbewahrungsrechtlich zählt."""

    HANDELSBRIEF = "handelsbrief"
    """Geschäftliche Korrespondenz ohne Belegcharakter."""

    BUCHUNGSBELEG = "buchungsbeleg"
    """Rechnung, Quittung, Kontoauszug – alles, was eine Buchung stützt."""

    PRIVAT = "privat"
    """Keine Aufbewahrungspflicht; darf jederzeit weg."""

    UNBESTIMMT = "unbestimmt"
    """Noch nicht eingeordnet. Wird wie aufbewahrungspflichtig behandelt."""


#: Fristen in Jahren, gerechnet ab dem Ende des Kalenderjahres.
#:
#: Deutschland  Handelsbriefe 6 Jahre (§ 257 Abs. 4 HGB, § 147 Abs. 3 AO),
#:              Buchungsbelege 8 Jahre. Die Verkürzung von 10 auf 8 Jahre
#:              brachte das Vierte Bürokratieentlastungsgesetz zum
#:              1. Januar 2025. Für Unternehmen unter Aufsicht der BaFin
#:              bleibt es bei 10 Jahren – siehe Hinweis unten.
#: Österreich   7 Jahre (§ 132 BAO, § 212 UGB).
#: Schweiz      10 Jahre (Art. 958f OR, ergänzt durch die GeBüV).
_YEARS: dict[tuple[Jurisdiction, Category], int] = {
    (Jurisdiction.DE, Category.HANDELSBRIEF): 6,
    (Jurisdiction.DE, Category.BUCHUNGSBELEG): 8,
    (Jurisdiction.DE, Category.UNBESTIMMT): 8,
    (Jurisdiction.AT, Category.HANDELSBRIEF): 7,
    (Jurisdiction.AT, Category.BUCHUNGSBELEG): 7,
    (Jurisdiction.AT, Category.UNBESTIMMT): 7,
    (Jurisdiction.CH, Category.HANDELSBRIEF): 10,
    (Jurisdiction.CH, Category.BUCHUNGSBELEG): 10,
    (Jurisdiction.CH, Category.UNBESTIMMT): 10,
}

#: Sonderfall Deutschland: Wer der Aufsicht der BaFin unterliegt, behält für
#: Buchungsbelege die zehnjährige Frist. Als Schalter in den
#: Archiveinstellungen, nicht als Automatik – das kann nur der Anwender wissen.
_DE_BAFIN_YEARS = 10


@dataclass(frozen=True)
class Policy:
    """Die Fristenregel eines Archivs."""

    jurisdiction: Jurisdiction = Jurisdiction.DE
    bafin_supervised: bool = False
    """Nur Deutschland: verlängert Buchungsbelege wieder auf zehn Jahre."""

    def years(self, category: Category) -> int | None:
        """Aufbewahrungsdauer in Jahren, oder ``None`` ohne Pflicht."""
        if category is Category.PRIVAT:
            return None
        if (
            self.jurisdiction is Jurisdiction.DE
            and self.bafin_supervised
            and category in (Category.BUCHUNGSBELEG, Category.UNBESTIMMT)
        ):
            return _DE_BAFIN_YEARS
        return _YEARS.get((self.jurisdiction, category))

    def expires_end_of(self, category: Category, reference: date) -> int | None:
        """Das Kalenderjahr, mit dessen Ablauf die Frist endet.

        Die Uhr beginnt nicht am Tag der Mail, sondern zum Schluss des
        Kalenderjahres, in dem sie entstand – so steht es gleichlautend in
        § 147 Abs. 4 AO, § 132 BAO und Art. 958f OR. Eine Rechnung vom
        März 2025 ist in Deutschland also bis Ende 2033 zu halten, nicht bis
        März 2033.
        """
        years = self.years(category)
        if years is None:
            return None
        return reference.year + years

    def is_locked(self, category: Category, reference: date, today: date | None = None) -> bool:
        """Sagt, ob die Mail noch aufbewahrt werden muss."""
        end_year = self.expires_end_of(category, reference)
        if end_year is None:
            return False
        return (today or date.today()).year <= end_year

    def is_due(self, category: Category, reference: date, today: date | None = None) -> bool:
        """Sagt, ob die Frist abgelaufen ist und die Mail gelöscht werden sollte.

        Bewusst nur eine Aussage, keine Handlung: gelöscht wird ausschließlich
        nach ausdrücklicher Bestätigung. Ein Programm, das eigenmächtig
        Geschäftsunterlagen entfernt, richtet mehr Schaden an als jede zu
        lange Aufbewahrung.
        """
        end_year = self.expires_end_of(category, reference)
        if end_year is None:
            return False
        return (today or date.today()).year > end_year


def describe(policy: Policy) -> str:
    """Ein Satz, der die geltenden Fristen für die Oberfläche zusammenfasst."""
    names = {
        Jurisdiction.DE: "Deutschland",
        Jurisdiction.AT: "Österreich",
        Jurisdiction.CH: "Schweiz",
    }
    handel = policy.years(Category.HANDELSBRIEF)
    beleg = policy.years(Category.BUCHUNGSBELEG)
    return (
        f"{names[policy.jurisdiction]}: Handelsbriefe {handel} Jahre, "
        f"Buchungsbelege {beleg} Jahre, jeweils ab Ende des Kalenderjahres."
    )
