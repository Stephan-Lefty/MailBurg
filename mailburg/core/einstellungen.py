"""Was sich MailBurg von Sitzung zu Sitzung merkt.

Welches Archiv zuletzt offen war, welche zuvor, wie groß das Fenster
zuletzt stand, wann die jährliche Fristenfrage zuletzt kam.

**Warum das im Kern liegt und nicht in der Oberfläche.** Bis zum
2026-08-31 stand es in ``ui/app.py`` – dort war es einmal entstanden,
weil die Oberfläche der erste war, der etwas zu merken hatte. Nur holten
sich ``core/archive.py`` und ``core/nachfrage.py`` es von dort ab, und
damit zeigte der Kern auf ein Frontend.

Aufgefallen ist es beim Entwurf der Server Edition: Ein Dienst, der beim
Start ein Modul namens ``ui`` einlädt, holt sich früher oder später eine
Qt-Abhängigkeit auf eine Maschine ohne Bildschirm – und merkt es an dem
Tag, an dem jemand ihn neu aufsetzt. ``tests/test_schichten.py`` wacht
seitdem darüber, dass der Kern kein Frontend kennt.

**Die Datei heißt weiterhin ``oberflaeche.json``.** Der Name passt nicht
mehr, aber umbenennen hieße: Jeder verliert beim nächsten Start seine
gemerkte Fenstergröße, seine Archivliste und seine Schriftgröße. Dafür
ist ein stimmiger Dateiname zu wenig wert.

**Ein Dienst braucht davon fast nichts.** Er hat keine Fenstergröße und
keine »zuletzt benutzten« Pfade eines Menschen; sein Archiv steht in
seiner Konfiguration. Was er über dieses Modul dennoch erreicht – die
Auflösung von Archivkennungen zu Namen in ``core/archive.py`` – wird
dann eine eigene Antwort brauchen. Das ist im Entwurf vermerkt.
"""

from __future__ import annotations

import json
from pathlib import Path

from mailburg.core import paths


def _datei() -> Path:
    return paths.config_dir() / "oberflaeche.json"


def gemerktes() -> dict:
    """Alles, was sich MailBurg von Sitzung zu Sitzung merkt."""
    try:
        inhalt = json.loads(_datei().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return inhalt if isinstance(inhalt, dict) else {}


def merken_unter(schluessel: str, wert) -> None:
    """Ändert einen Eintrag, ohne die übrigen zu verlieren.

    Die frühere Fassung schrieb die Datei jedes Mal komplett neu. Damit
    hätte das Merken des Archivs die gemerkte Fenstergröße gelöscht – ein
    Fehler, der erst Wochen später als »das Fenster vergisst wieder alles«
    aufgefallen wäre.
    """
    stand = gemerktes()
    stand[schluessel] = wert
    try:
        _datei().write_text(
            json.dumps(stand, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        # Sich etwas nicht merken zu können ist ärgerlich, aber kein
        # Grund, das Programm nicht zu starten.
        pass


def zuletzt_gemerkt() -> Path | None:
    """Das Archiv, das zuletzt offen war."""
    pfad = gemerktes().get("archiv")
    if not pfad:
        return None
    ort = Path(pfad)
    # Nur wenn dort auch heute noch ein Archiv liegt: Eine externe Platte
    # kann abgezogen sein, ein Ordner umbenannt.
    return ort if (ort / "archive.json").exists() else None


#: So viele Archive stehen im Menü. Wenige genug, dass die Liste nicht
#: selbst zur Suche wird.
ZULETZT = 6


def merken(pfad: Path) -> None:
    merken_unter("archiv", str(pfad))

    # Die zuletzt benutzten obenauf, ohne Doppelungen. Wer zwei Archive
    # führt - ein geschäftliches und ein privates -, wechselt ständig
    # zwischen ihnen und soll dafür keinen Dateidialog brauchen.
    liste = [str(pfad)] + [p for p in zuletzt_benutzte_pfade() if p != str(pfad)]
    merken_unter("zuletzt", liste[:ZULETZT])


def zuletzt_benutzte_pfade() -> list[str]:
    """Die zuletzt geöffneten Archive, ungeprüft."""
    liste = gemerktes().get("zuletzt", [])
    return [p for p in liste if isinstance(p, str)]


def zuletzt_benutzte() -> list[Path]:
    """Die zuletzt geöffneten Archive, die es auch heute noch gibt.

    Eine externe Platte kann abgezogen, ein Ordner umbenannt sein. Ein
    Menüeintrag, der ins Leere führt, ist ärgerlicher als ein fehlender.
    """
    return [Path(p) for p in zuletzt_benutzte_pfade()
            if (Path(p) / "archive.json").exists()]
