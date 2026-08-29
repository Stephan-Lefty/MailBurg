"""Die Bilder in der Anleitung.

Am 2026-08-29 stand in ``docs/windows.md`` unter dem letzten Schritt des
Assistenten ein Bild mit der Unterschrift »Die Abschlussseite des
Assistenten. Sie nennt den Ort des Archivs, die Zahl der eingerichteten
Postfächer …«. Zu sehen war darauf der **Willkommensbildschirm** – dasselbe
Fenster wie zwei Schritte davor, nur anders gescrollt. Beim Aufnehmen war
ein Bild zweimal gespeichert worden.

Was ein Bild zeigt, kann kein Test beurteilen. Was er kann: dafür sorgen,
dass in ``docs/bilder/`` nichts liegt, das nirgends eingebunden ist. Genau
so ein Rest wäre das falsche Bild gewesen, nachdem die Einbindung
herausgenommen war – und ein verwaistes Bild ist der Verdachtsfall, aus
dem sich die Verwechslung nachträglich noch aufklären lässt.
"""

from __future__ import annotations

import pathlib
import re
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
BILDER = WURZEL / "docs" / "bilder"


def _einbindungen() -> dict[pathlib.Path, list[pathlib.Path]]:
    """Jedes eingebundene Bild mit den Dateien, die es einbinden."""
    gefunden: dict[pathlib.Path, list[pathlib.Path]] = {}
    seiten = list(WURZEL.glob("docs/**/*.md")) + list(WURZEL.glob("*.md"))
    for seite in seiten:
        text = seite.read_text(encoding="utf-8")
        for ziel in re.findall(r"\]\(([^)]*bilder/[^)]+)\)", text):
            pfad = (seite.parent / ziel).resolve()
            gefunden.setdefault(pfad, []).append(seite)
    return gefunden


class DokuBilderTest(unittest.TestCase):
    def test_jede_einbindung_hat_eine_datei(self) -> None:
        fehlend = [
            f"{pfad.name} (eingebunden in "
            f"{', '.join(s.name for s in seiten)})"
            for pfad, seiten in _einbindungen().items()
            if not pfad.is_file()
        ]

        self.assertEqual(
            fehlend, [],
            "Die Anleitung verweist auf Bilder, die es nicht gibt:\n  "
            + "\n  ".join(fehlend),
        )

    def test_kein_bild_liegt_unbenutzt_herum(self) -> None:
        """Ein Bild, das nirgends steht, ist meist ein Überbleibsel."""
        eingebunden = set(_einbindungen())
        verwaist = sorted(
            p.name for p in BILDER.iterdir()
            if p.is_file() and p.resolve() not in eingebunden
        )

        self.assertEqual(
            verwaist, [],
            "In docs/bilder/ liegt etwas, das keine Seite einbindet:\n  "
            + "\n  ".join(verwaist)
            + "\n\nEntweder gehört es in die Anleitung oder es kann weg.",
        )

    def test_jedes_bild_hat_eine_beschreibung(self) -> None:
        """Ohne Alternativtext ist das Bild für Vorleseprogramme stumm."""
        ohne: list[str] = []
        seiten = list(WURZEL.glob("docs/**/*.md")) + list(WURZEL.glob("*.md"))
        for seite in seiten:
            text = seite.read_text(encoding="utf-8")
            for beschreibung, ziel in re.findall(
                r"!\[([^\]]*)\]\(([^)]*bilder/[^)]+)\)", text
            ):
                if len(beschreibung.strip()) < 20:
                    ohne.append(f"{seite.name}: {ziel} → »{beschreibung}«")

        self.assertEqual(
            ohne, [],
            "Diese Bilder haben keine brauchbare Beschreibung:\n  "
            + "\n  ".join(ohne),
        )


if __name__ == "__main__":
    unittest.main()
