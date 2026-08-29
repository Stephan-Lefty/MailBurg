"""Zahlwörter, die sich nach der Zahl richten.

»1 Mails im Archiv« steht in der Statuszeile, sobald genau eine Mail
darin liegt – bei einem frisch angelegten Archiv also immer. Es ist ein
winziger Fehler, aber einer, den jeder sofort sieht, und er steht
ausgerechnet dort, wo ein neuer Anwender zum ersten Mal nachsieht, ob
sein Archiv etwas enthält.

Am 2026-08-29 auf einem Windows-Bild für die Anleitung aufgefallen.

**Warum in core und nicht bei der Oberfläche.** Die Kommandozeile zählt
dieselben Dinge und hatte dieselben Stellen. Zwei Fassungen desselben
Plurals laufen irgendwann auseinander.
"""

from __future__ import annotations


def anzahl(zahl: int, einzahl: str, mehrzahl: str = "") -> str:
    """»1 Mail«, »5 Mails« – mit Tausenderpunkten.

    ``mehrzahl`` ohne Angabe ist die Einzahl mit angehängtem ``s``. Das
    trägt bei »Mail«, »Datei« nicht – deshalb lässt es sich angeben.
    """
    form = einzahl if abs(zahl) == 1 else (mehrzahl or einzahl + "s")
    return f"{zahl:,}".replace(",", ".") + f" {form}"


def mails(zahl: int) -> str:
    """Der häufigste Fall, damit ihn niemand einzeln schreiben muss."""
    return anzahl(zahl, "Mail", "Mails")


def dateien(zahl: int) -> str:
    return anzahl(zahl, "Datei", "Dateien")


def nachrichten(zahl: int) -> str:
    return anzahl(zahl, "Nachricht", "Nachrichten")


def postfaecher(zahl: int) -> str:
    return anzahl(zahl, "Postfach", "Postfächer")
