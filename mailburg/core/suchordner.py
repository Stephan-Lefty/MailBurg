"""Gespeicherte Suchen – benannt, im Baum, jederzeit aktuell.

**Der Anlass ist eine Rückmeldung vom 2026-09-21.** Ein Anwender hatte
seine Post jahrelang in *lokalen Ordnern* von Thunderbird und Evolution
sortiert und damit die Postfächer beim Anbieter aufgeräumt. Beim Umstieg
ordnet er diese Bestände wieder den Postfächern zu – MailBurg archiviert
ja von nun an. Damit verliert er eine Ordnungsebene, die er vorher
hatte, und wünscht sich dafür einen Ersatz: Suchordner, wie Evolution
sie kennt und Thunderbird als »virtuelle Ordner«.

**Ein Suchordner ist ein Name für einen Suchausdruck, mehr nicht.** Er
enthält keine Mails, er kopiert nichts, er verschiebt nichts. Wer ihn
anklickt, löst dieselbe Suche aus, die er auch hätte tippen können.
Genau deshalb passt er zu MailBurg: Die ausführliche Suche baut ohnehin
nichts anderes zusammen als einen Ausdruck, und der Postfachbaum trägt
an jedem Eintrag längst einen (``konto:… ordner:…``). Ein Suchordner
setzt sich daneben, ohne dass irgendetwas Neues nötig wäre.

**Daraus folgt der wichtigste Unterschied zum lokalen Ordner:** Ein
Suchordner ist immer aktuell. Was heute ankommt und auf ihn passt, steht
morgen darin, ohne dass jemand einsortiert. Und umgekehrt: Was er
anzeigt, liegt trotzdem dort, wo es hingehört – im Postfach, aus dem es
stammt. Eine Mail lässt sich nicht »in einen Suchordner legen«.

Drei Festlegungen, die nicht ohne Kenntnis des Grundes aufgemacht
werden sollten:

**Je Archiv, nicht für alle zusammen.** Ein Ausdruck wie
``konto:Firma betreff:Rechnung`` ergibt in einem Privatarchiv ohne
dieses Postfach null Treffer – ein Ordner, der immer leer ist, sieht
aus wie ein Fehler. Geführt wird deshalb nach der Archivkennung.

**Neben dem Archiv, nicht darin.** Ein Suchordner ist keine Post. Er
gehört nicht in die Hash-Kette, deren Zweck es ist, unverändert zu
bleiben – und ein Journaleintrag für »Suchordner umbenannt« würde
dieselbe Kette mit etwas füllen, das niemanden angeht. **Der Preis
steht in der Anleitung:** Wer sein Archiv an einen anderen Rechner
hängt, findet dort seine Suchordner nicht wieder.

**Der Ausdruck wird beim Anlegen geprüft.** Ein Suchordner, der beim
Anklicken »Der Suchausdruck stimmt nicht« meldet, ist schlimmer als
keiner: Angelegt hat man ihn vor Wochen, und woran es lag, weiß dann
niemand mehr.
"""

from __future__ import annotations

from dataclasses import dataclass

from mailburg.core import einstellungen
from mailburg.search.query import QueryError, build

#: Unter diesem Schlüssel stehen die Suchordner aller Archive.
SCHLUESSEL = "suchordner"

#: Und darunter die zuletzt benutzten Suchausdrücke.
SCHLUESSEL_HISTORIE = "zuletzt_gesucht"

#: So viele Einträge hält die Liste »Zuletzt gesucht«. Kurz genug, dass
#: sie in ein Menü passt, ohne selbst zum Suchen zu werden – und kurz
#: genug, dass nicht monatelang mitläuft, wonach jemand einmal gesucht
#: hat. Was dort steht, kann ein Name sein, eine Adresse, eine Diagnose.
HISTORIE = 10

#: Länger darf ein Name nicht sein. Er steht in einer Baumspalte neben
#: den Postfächern; alles darüber wird abgeschnitten angezeigt, und ein
#: abgeschnittener Name ist kein Name.
NAME_MAX = 60


@dataclass(frozen=True)
class Suchordner:
    """Ein Name und der Suchausdruck, für den er steht."""

    name: str
    ausdruck: str

    def als_dict(self) -> dict[str, str]:
        return {"name": self.name, "ausdruck": self.ausdruck}


class NameVergeben(ValueError):
    """Diesen Namen gibt es in diesem Archiv schon."""


def _alle() -> dict:
    stand = einstellungen.gemerktes().get(SCHLUESSEL)
    return stand if isinstance(stand, dict) else {}


def laden(kennung: str) -> list[Suchordner]:
    """Die Suchordner dieses Archivs, in der gespeicherten Reihenfolge.

    Unbrauchbare Einträge werden übergangen statt gemeldet: Diese Liste
    wird beim Aufbau des Fensters gelesen, und ein von Hand verdorbenes
    ``oberflaeche.json`` darf nicht den Start kosten.
    """
    gefunden = []
    for eintrag in _alle().get(kennung, []):
        if not isinstance(eintrag, dict):
            continue
        name = str(eintrag.get("name", "")).strip()
        ausdruck = str(eintrag.get("ausdruck", "")).strip()
        if name and ausdruck:
            gefunden.append(Suchordner(name, ausdruck))
    return gefunden


def speichern(kennung: str, ordner: list[Suchordner]) -> None:
    """Schreibt die Liste dieses Archivs, ohne die anderen anzufassen."""
    stand = _alle()
    if ordner:
        stand[kennung] = [o.als_dict() for o in ordner]
    else:
        # Eine leere Liste stehen zu lassen wäre kein Fehler, aber sie
        # wächst mit jedem je geöffneten Archiv mit.
        stand.pop(kennung, None)
    einstellungen.merken_unter(SCHLUESSEL, stand)


def pruefen(name: str, ausdruck: str) -> tuple[str, str]:
    """Nimmt Name und Ausdruck an – oder sagt, was daran nicht geht.

    Gibt beide zurück, wie sie gespeichert werden. Wer das Ergebnis
    verwirft und die Eingabe speichert, legt einen Ordner mit
    Leerzeichen am Rand an, der aussieht wie ein zweiter daneben.
    """
    name = " ".join(name.split())
    if not name:
        raise ValueError("Ein Suchordner braucht einen Namen.")
    if len(name) > NAME_MAX:
        raise ValueError(
            f"Der Name ist zu lang – höchstens {NAME_MAX} Zeichen. "
            f"Er steht im Baum neben den Postfächern."
        )

    ausdruck = ausdruck.strip()
    if not ausdruck:
        raise ValueError(
            "Ohne Suchausdruck fände der Ordner alles. Gemeint ist "
            "vermutlich eine Einschränkung – etwa von:telekom."
        )
    # Wirft QueryError, wenn die Suchsprache damit nichts anfangen kann.
    build(ausdruck)
    return name, ausdruck


def hinzufuegen(kennung: str, name: str, ausdruck: str) -> Suchordner:
    """Legt einen Suchordner an. Ein vergebener Name wird abgelehnt."""
    name, ausdruck = pruefen(name, ausdruck)
    vorhanden = laden(kennung)
    for ordner in vorhanden:
        if ordner.name.casefold() == name.casefold():
            raise NameVergeben(
                f"»{ordner.name}« gibt es hier schon. Wählen Sie einen "
                f"anderen Namen oder ändern Sie den vorhandenen Ordner."
            )
    neu = Suchordner(name, ausdruck)
    speichern(kennung, vorhanden + [neu])
    return neu


def aendern(kennung: str, alt: str, name: str, ausdruck: str) -> Suchordner:
    """Benennt um und ändert den Ausdruck – beides in einem Zug.

    **Umbenennen und Ändern sind derselbe Vorgang**, weil sie im Dialog
    derselbe sind: Wer den Ordner öffnet, sieht beide Felder und kann an
    beiden etwas tun. Zwei getrennte Wege hätten zwei getrennte
    Prüfungen, und die zweite wäre die schwächere.
    """
    name, ausdruck = pruefen(name, ausdruck)
    vorhanden = laden(kennung)
    for ordner in vorhanden:
        if ordner.name == alt:
            break
    else:
        raise KeyError(f"»{alt}« gibt es hier nicht.")

    for ordner in vorhanden:
        if ordner.name != alt and ordner.name.casefold() == name.casefold():
            raise NameVergeben(f"»{ordner.name}« gibt es hier schon.")

    neu = Suchordner(name, ausdruck)
    speichern(kennung, [neu if o.name == alt else o for o in vorhanden])
    return neu


def entfernen(kennung: str, name: str) -> bool:
    """Nimmt einen Suchordner weg. **An der Post ändert das nichts.**"""
    vorhanden = laden(kennung)
    uebrig = [o for o in vorhanden if o.name != name]
    if len(uebrig) == len(vorhanden):
        return False
    speichern(kennung, uebrig)
    return True


def verschieben(kennung: str, namen: list[str]) -> None:
    """Setzt die Reihenfolge – für das Ziehen im Baum.

    Namen, die es nicht gibt, werden übergangen; Ordner, die nicht
    genannt wurden, bleiben hinten stehen. Eine Reihenfolge darf keinen
    Ordner verschlucken.
    """
    vorhanden = {o.name: o for o in laden(kennung)}
    sortiert = [vorhanden.pop(n) for n in namen if n in vorhanden]
    speichern(kennung, sortiert + list(vorhanden.values()))


# --------------------------------------------------------------- Historie


def _alle_historien() -> dict:
    stand = einstellungen.gemerktes().get(SCHLUESSEL_HISTORIE)
    return stand if isinstance(stand, dict) else {}


def zuletzt_gesucht(kennung: str) -> list[str]:
    """Die zuletzt benutzten Suchausdrücke, der jüngste zuerst."""
    liste = _alle_historien().get(kennung, [])
    return [a for a in liste if isinstance(a, str) and a.strip()][:HISTORIE]


def suche_merken(kennung: str, ausdruck: str) -> None:
    """Nimmt einen Ausdruck in die Liste auf.

    **Das eigentliche Problem ist nicht die Wiederholung, sondern das
    Tippen.** MailBurg sucht schon während der Eingabe – wer
    ``rechnung telekom`` eintippt, löst dabei fünfzehn Suchen aus, und
    eine Liste, die jede davon aufnimmt, ist nach einem Wort voll. Von
    einer Tippfolge bleibt deshalb nur ihr längster Stand: Fängt der
    neue Ausdruck mit dem zuletzt gemerkten an oder umgekehrt, tritt er
    an dessen Stelle, statt sich danebenzusetzen.

    **Der Preis, und er ist bewusst gezahlt:** Wer erst ``rechnung``
    sucht und danach ``rechnung telekom``, behält nur das zweite. Die
    kürzere Suche ist in einem Zeichen wiederhergestellt; fünfzehn
    Zwischenstände sind nicht mehr zu sortieren.
    """
    ausdruck = ausdruck.strip()
    if not ausdruck:
        return

    liste = [a for a in zuletzt_gesucht(kennung) if a != ausdruck]
    if liste:
        oben = liste[0]
        if oben.startswith(ausdruck) or ausdruck.startswith(oben):
            liste = liste[1:]

    stand = _alle_historien()
    stand[kennung] = [ausdruck] + liste[: HISTORIE - 1]
    einstellungen.merken_unter(SCHLUESSEL_HISTORIE, stand)


def historie_leeren(kennung: str) -> None:
    """Vergisst, wonach in diesem Archiv gesucht wurde.

    **Warum es diesen Weg gibt.** Die Liste steht im Klartext in
    ``oberflaeche.json``, auch dann, wenn das Archiv selbst
    verschlüsselt ist – sie gehört zur Oberfläche, nicht zum Bestand. In
    einem Suchausdruck kann ein Name stehen, eine Adresse, eine
    Krankheit. Wer über die Schulter geschaut bekommt, soll die Liste
    loswerden können, ohne eine Datei zu suchen.
    """
    stand = _alle_historien()
    if stand.pop(kennung, None) is not None:
        einstellungen.merken_unter(SCHLUESSEL_HISTORIE, stand)


__all__ = [
    "HISTORIE",
    "NAME_MAX",
    "NameVergeben",
    "QueryError",
    "Suchordner",
    "aendern",
    "entfernen",
    "hinzufuegen",
    "historie_leeren",
    "laden",
    "pruefen",
    "speichern",
    "suche_merken",
    "verschieben",
    "zuletzt_gesucht",
]
