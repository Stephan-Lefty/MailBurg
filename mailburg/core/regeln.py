"""Regeln, die Post beim Aufnehmen einstufen.

**Wofür.** In einem Geschäftsarchiv landet private Post – der Verein,
die Familie, der Handwerker für die eigene Wohnung. Sie liegt dann unter
Aufbewahrungsfristen, die für sie gar nicht gelten: Zehn Jahre
Löschsperre auf einer Einladung zum Grillfest. Umgekehrt verlangt die
DSGVO, personenbezogene Daten zu löschen, sobald der Zweck entfällt –
und bei privater Post entfällt er sofort.

Von Hand nachzustufen wäre die Alternative. Das tut niemand über Jahre
hinweg bei jeder eingehenden Mail.

**Warum beim Einstufen und nicht beim Abruf.** Eine Regel, die schon das
Holen verhindert, wirft weg, was sie trifft – und wer später merkt, dass
sie zu weit griff, hat die Post verloren, falls sie im Postfach
inzwischen gelöscht wurde. Ein Archivprogramm soll im Zweifel behalten.
Deshalb kommt jede Mail ins Archiv; die Regel entscheidet nur, wie sie
eingestuft wird. Eine falsch gegriffene Regel lässt sich zurücknehmen,
eine nicht geholte Mail nicht.

**Jede Anwendung steht im Journal.** Mit Angabe der Regel, die gegriffen
hat. Für ein Geschäftsarchiv ist das keine Ordnungsliebe: Wer begründen
muss, warum eine Mail nicht der zehnjährigen Aufbewahrung unterlag, will
auf einen Eintrag zeigen können – und der hängt in der Hash-Kette.

Beschlossen mit Stephan am 2026-08-30.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

from mailburg.core.retention import Category

#: Wonach eine Regel schauen kann. Bewusst wenige Felder: Wer zwischen
#: fünfzehn Bedingungen wählen soll, legt keine Regel an.
FELDER = ("ordner", "von", "an")

BESCHRIFTUNG = {
    "ordner": "Ordner",
    "von": "Absender",
    "an": "Empfänger",
}


@dataclass
class Regel:
    """Eine Bedingung und die Einstufung, die daraus folgt.

    ``muster`` ist ein Suchmuster mit ``*`` und ``?``, nicht ein
    regulärer Ausdruck. Der Unterschied ist keine Kleinigkeit: ``*.pdf``
    versteht jeder, ``.*\\.pdf$`` niemand, der nicht programmiert. Und
    ein verunglückter regulärer Ausdruck kann alles treffen, ohne dass
    man es ihm ansieht.
    """

    feld: str
    muster: str
    kategorie: Category = Category.PRIVAT
    aktiv: bool = True
    bemerkung: str = ""

    def __post_init__(self) -> None:
        if self.feld not in FELDER:
            raise ValueError(
                f"Unbekanntes Feld: {self.feld!r}. Möglich sind: "
                + ", ".join(FELDER)
            )
        if not self.muster.strip():
            raise ValueError("Eine Regel ohne Muster träfe alles oder nichts.")
        self.kategorie = Category(self.kategorie)

    def trifft(self, ordner: str = "", von: str = "", an: str = "") -> bool:
        """Ob diese Regel auf eine Mail zutrifft.

        Groß- und Kleinschreibung spielt keine Rolle: Mailadressen sind
        im Domänenteil ohnehin unempfindlich dafür, und wer »Privat«
        eingibt, meint auch »privat«.
        """
        if not self.aktiv:
            return False
        wert = {"ordner": ordner, "von": von, "an": an}[self.feld]
        if not wert:
            return False
        return fnmatch.fnmatch(wert.lower(), self.muster.strip().lower())

    def beschreibung(self) -> str:
        """Ein Satz für Journal und Oberfläche."""
        return (
            f"{BESCHRIFTUNG[self.feld]} passt auf »{self.muster}« "
            f"→ {self.kategorie.value}"
        )

    def als_daten(self) -> dict:
        return {
            "feld": self.feld,
            "muster": self.muster,
            "kategorie": self.kategorie.value,
            "aktiv": self.aktiv,
            "bemerkung": self.bemerkung,
        }

    @classmethod
    def aus_daten(cls, daten: dict) -> "Regel":
        return cls(
            feld=daten.get("feld", "ordner"),
            muster=daten.get("muster", ""),
            kategorie=Category(daten.get("kategorie", Category.PRIVAT)),
            aktiv=bool(daten.get("aktiv", True)),
            bemerkung=daten.get("bemerkung", ""),
        )


@dataclass
class Regelwerk:
    """Alle Regeln eines Archivs, in ihrer Reihenfolge.

    **Die erste passende gewinnt.** Nicht die schärfste, nicht die
    zuletzt angelegte – die erste. Das ist die einzige Regelung, die
    sich ohne Nachdenken vorhersagen lässt, und wer eine Ausnahme
    braucht, schiebt sie nach oben.
    """

    regeln: list[Regel] = field(default_factory=list)

    def passende(
        self, ordner: str = "", von: str = "", an: str = ""
    ) -> Regel | None:
        for regel in self.regeln:
            if regel.trifft(ordner=ordner, von=von, an=an):
                return regel
        return None

    def einstufung(
        self, ordner: str = "", von: str = "", an: str = ""
    ) -> tuple[Category, str] | None:
        """Die Kategorie und die Begründung – oder ``None``.

        ``None`` heißt: keine Regel greift, es bleibt beim Üblichen.
        Ausdrücklich nicht ``UNBESTIMMT``, denn das wäre eine Aussage.
        """
        regel = self.passende(ordner=ordner, von=von, an=an)
        if regel is None:
            return None
        return regel.kategorie, regel.beschreibung()

    def als_daten(self) -> list[dict]:
        return [r.als_daten() for r in self.regeln]

    @classmethod
    def aus_daten(cls, daten) -> "Regelwerk":
        """Baut das Regelwerk aus dem, was in ``archive.json`` steht.

        Unbrauchbare Einträge werden übergangen, nicht mit einer
        Ausnahme quittiert: Eine kaputte Regel darf nicht dazu führen,
        dass sich das Archiv nicht mehr öffnen lässt.
        """
        if not isinstance(daten, list):
            return cls()
        gefunden = []
        for eintrag in daten:
            if not isinstance(eintrag, dict):
                continue
            try:
                gefunden.append(Regel.aus_daten(eintrag))
            except (ValueError, KeyError):
                continue
        return cls(gefunden)

    def __len__(self) -> int:
        return len(self.regeln)

    def __iter__(self):
        return iter(self.regeln)
