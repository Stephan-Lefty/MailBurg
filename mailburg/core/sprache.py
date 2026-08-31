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


def eintraege(zahl: int) -> str:
    return anzahl(zahl, "Eintrag", "Einträge")


def groesse(bytes_zahl: int) -> str:
    """»820 KB«, »6,8 MB« – Dateigrößen für Menschen.

    Stand bis zum 2026-08-31 als ``_lesbar`` in ``core/orte.py``, wo es
    für den freien Plattenplatz entstanden war. Die Weboberfläche
    braucht dasselbe für die Größe einer Mail; zwei Fassungen derselben
    Umrechnung wichen früher oder später um ein Komma voneinander ab.
    """
    wert = float(bytes_zahl)
    for einheit in ("B", "KB", "MB", "GB", "TB"):
        if wert < 1024 or einheit == "TB":
            if einheit in ("B", "KB"):
                return f"{wert:.0f} {einheit}"
            return f"{wert:.1f} {einheit}".replace(".", ",")
        wert /= 1024
    return f"{wert:.1f} TB".replace(".", ",")


def zeitpunkt(iso: str) -> str:
    """»25.08.2026, 09:46« aus einem ISO-Zeitstempel.

    **Fest deutsch, nicht nach Systemsprache.** Am 2026-08-31 mit
    Stephan so entschieden: Das Programm spricht durchgehend deutsch –
    seine Meldungen, seine Knöpfe, seine Suchsprache. Ein Datum, das
    davon abweicht, weil der Rechner anders eingestellt ist, wäre der
    einzige Fremdkörper.

    Diese Funktion ist seitdem die einzige Stelle, an der ein Datum für
    Menschen entsteht – ``ui/datum.py`` ruft sie auf, der Server
    ebenfalls. Zwei Fassungen desselben Formats liefen früher oder
    später auseinander.
    """
    from datetime import datetime

    if not iso:
        return ""
    try:
        wann = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{wann:%d.%m.%Y, %H:%M}"
