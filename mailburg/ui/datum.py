"""Datumsangaben so schreiben, wie der Anwender sie liest.

Intern ist alles ISO: ``2026-08-26T21:14:03+02:00``. Das ist richtig so –
eindeutig, sortierbar, zeitzonenfest. Nur hinschreiben sollte man es
niemandem. Wer in Deutschland sitzt, liest ``26.08.2026``, wer in den USA
sitzt, ``8/26/2026``, und beide sind es aus ihrer Sicht gewohnt.

Das Format kommt deshalb von :class:`QLocale`, also aus den
Systemeinstellungen. MailBurg legt es nicht fest, es fragt nach.

**Jahreszahlen immer vierstellig.** Qts Kurzformat kürzt sie auf zwei
Stellen ab – in einem Mailarchiv ein handfestes Problem: Post von 1998
und Post von 2098 stünden beide als »98« da. Ein Archiv ist genau die
Sorte Programm, in der alte Jahreszahlen vorkommen.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDateTime, QLocale, Qt


def _muster(art: QLocale.FormatType) -> str:
    """Das Datumsmuster der Systemsprache, mit vierstelligem Jahr."""
    muster = QLocale().dateFormat(art)
    if "yyyy" not in muster:
        muster = muster.replace("yy", "yyyy")
    return muster


def tag(wert: str | datetime | None) -> str:
    """Nur der Tag – für die Trefferliste, wo jede Spalte Platz kostet."""
    zeitpunkt = _lesen(wert)
    if zeitpunkt is None:
        return ""
    return QLocale().toString(zeitpunkt.date(), _muster(QLocale.ShortFormat))


def tag_und_zeit(wert: str | datetime | None) -> str:
    """Tag und Uhrzeit – für die Vorschau, wo es genau sein darf."""
    zeitpunkt = _lesen(wert)
    if zeitpunkt is None:
        return ""
    ort = QLocale()
    return (
        f"{ort.toString(zeitpunkt.date(), _muster(QLocale.ShortFormat))} "
        f"{ort.toString(zeitpunkt.time(), 'HH:mm')}"
    )


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
