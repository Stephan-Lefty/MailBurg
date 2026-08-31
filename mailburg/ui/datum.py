"""Datumsangaben so schreiben, wie MailBurg spricht: deutsch.

Intern ist alles ISO: ``2026-08-26T21:14:03+02:00``. Das ist richtig so –
eindeutig, sortierbar, zeitzonenfest. Nur hinschreiben sollte man es
niemandem.

**Fest deutsch, nicht nach Systemsprache.** Bis zum 2026-08-31 kam das
Format aus :class:`QLocale`, also aus den Systemeinstellungen. Das war
für sich vertretbar – wer in den USA sitzt, liest ``8/26/2026`` – stand
aber im Widerspruch zu ``ui/app.py``, das Qts eigene Beschriftungen
**fest** auf Deutsch stellt, mit der Begründung: Das Programm ist von
Grund auf deutsch, seine Meldungen sind es und die Suchsprache auch;
englische Knöpfe daneben wären kein Entgegenkommen, sondern ein Bruch.

Beides zusammen ergab »Weiter« neben »8/26/2026«. Aufgefallen ist es am
2026-08-31, als die Tests der Oberfläche zum ersten Mal in der CI
liefen: Auf einem Bauserver ohne Spracheinstellung stand dort
»26 08 2026«. Mit Stephan entschieden: **alles auf Deutsch.**

Die Umrechnung selbst liegt in :mod:`mailburg.core.sprache` – damit
Fenster und Weboberfläche dieselbe benutzen und nicht zwei Fassungen
desselben Formats auseinanderlaufen.

**Jahreszahlen immer vierstellig.** Qts Kurzformat kürzte sie auf zwei
Stellen – in einem Mailarchiv ein handfestes Problem: Post von 1998 und
Post von 2098 stünden beide als »98« da. Ein Archiv ist genau die Sorte
Programm, in der alte Jahreszahlen vorkommen.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDateTime, Qt

from mailburg.core import sprache

#: Das Muster für Eingabefelder, die ein Datum entgegennehmen –
#: ``QDateEdit`` und Verwandte. Dieselbe Schreibweise wie in der Anzeige
#: und in der Suchsprache (``seit:01.01.2025``).
MUSTER = "dd.MM.yyyy"


def tag(wert: str | datetime | None) -> str:
    """Nur der Tag – für die Trefferliste, wo jede Spalte Platz kostet."""
    zeitpunkt = _lesen(wert)
    if zeitpunkt is None:
        return ""
    return sprache.zeitpunkt(_iso(zeitpunkt)).split(",")[0]


def tag_und_zeit(wert: str | datetime | None) -> str:
    """Tag und Uhrzeit – für die Vorschau, wo es genau sein darf."""
    zeitpunkt = _lesen(wert)
    if zeitpunkt is None:
        return ""
    return sprache.zeitpunkt(_iso(zeitpunkt)).replace(",", "")


def _iso(zeitpunkt: QDateTime) -> str:
    return zeitpunkt.toString(Qt.ISODate)


def _lesen(wert: str | datetime | None) -> QDateTime | None:
    """Nimmt entgegen, was im Archiv steht – und gibt bei Unsinn nichts zurück.

    Kopfzeilen aus zwanzig Jahren Mailverkehr enthalten alles: abgeschnittene
    Datumsangaben, Zeitzonen, die es nicht gibt, leere Felder. Nichts davon
    darf die Trefferliste zum Absturz bringen.
    """
    if wert is None or wert == "":
        return None
    if isinstance(wert, datetime):
        return QDateTime.fromString(wert.isoformat(timespec="seconds"), Qt.ISODate)

    zeitpunkt = QDateTime.fromString(wert, Qt.ISODate)
    if zeitpunkt.isValid():
        return zeitpunkt
    # Manche Einträge tragen nur den Tag, ohne Uhrzeit.
    nur_tag = QDateTime.fromString(wert[:10], "yyyy-MM-dd")
    return nur_tag if nur_tag.isValid() else None
