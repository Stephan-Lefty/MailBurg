"""Wann MailBurg nach abgelaufenen Fristen fragt – und wann nicht mehr.

**Einmal im Jahr, nicht bei jedem Start.** Fristen laufen zum
Jahresende ab; eine Meldung, die ab dem 1. Januar bei jedem Öffnen
erscheint, wird nach der dritten Wiederholung weggeklickt, ohne gelesen
zu werden – und dann auch beim vierten Mal, wenn es darauf ankäme.

**Warum das hier steht und nicht bei der Oberfläche.** Ob eine
Nachfrage ansteht, ist eine Rechnung, keine Darstellung. Im
Oberflächenmodul zöge sie Qt herein – und der CI-Lauf, der MailBurg
bewusst mit der nackten Standardbibliothek prüft, bräche daran. Genau
das ist am 2026-08-28 passiert.
"""

from __future__ import annotations

from datetime import date

#: Unter diesem Schlüssel steht in den Programmeinstellungen, wann
#: zuletzt gefragt wurde – als ``{Archivkennung: Jahr}``.
#:
#: **Dort und nicht im Archiv.** »Wann habe ich zuletzt gefragt« ist
#: keine Eigenschaft des Archivs, sondern eine des Anwenders. Und ein
#: Archiv, das beim bloßen Ansehen verändert wird, wäre bei einem
#: Programm mit Hash-Kette die falsche Gewohnheit.
SCHLUESSEL = "fristenpruefung"


def zuletzt_gefragt(kennung: str) -> int | None:
    """Das Jahr, in dem zuletzt gefragt wurde – ``None``, wenn noch nie."""
    from mailburg.ui.app import gemerktes

    stand = gemerktes().get(SCHLUESSEL, {})
    if not isinstance(stand, dict):
        # Eine von Hand verhunzte Einstellungsdatei darf das Programm
        # nicht aufhalten. Im Zweifel: noch nie gefragt.
        return None
    wert = stand.get(kennung)
    return wert if isinstance(wert, int) else None


def gefragt_vermerken(kennung: str, jahr: int | None = None) -> None:
    """Hält fest, dass für dieses Archiv in diesem Jahr gefragt wurde."""
    from mailburg.ui.app import gemerktes, merken_unter

    stand = gemerktes().get(SCHLUESSEL, {})
    if not isinstance(stand, dict):
        stand = {}
    stand[kennung] = jahr if jahr is not None else date.today().year
    merken_unter(SCHLUESSEL, stand)


def steht_an(archiv, heute: date | None = None) -> bool:
    """Ob die jährliche Nachfrage für dieses Archiv fällig ist."""
    return archiv.policy.review_due(zuletzt_gefragt(str(archiv.uuid)), heute)
