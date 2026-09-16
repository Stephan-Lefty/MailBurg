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

try:
    import PySide6  # noqa: F401

    QT_DA = True
except ImportError:  # pragma: no cover
    QT_DA = False

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


@unittest.skipUnless(QT_DA, "Die Takte stehen bisher in einem Qt-Modul.")
class TakteInDerDokuTest(unittest.TestCase):
    """Die Doku nannte Abstände, die es nicht gab.

    In ``zeitsteuerung.md`` stand »Wählbar sind 10, 30, 60 oder 90
    Minuten«, in der Übersichtsgrafik »alle 10–90 Minuten«. Tatsächlich
    wählbar sind 15, 30, 60, 240 und 1440 Minuten. Weder 10 noch 90
    kamen je vor – die Angaben stammten aus einem früheren Entwurf und
    hatten die Änderung nicht mitbekommen.

    Am 2026-08-29 aufgefallen, als Stephan die Auswahlliste in der
    Windows-VM aufklappte und abbildete.
    """

    def test_die_doku_nennt_keine_erfundenen_takte(self):
        from mailburg.ui.zeitplan import TAKTE

        echte = {bezeichnung for bezeichnung, _ in TAKTE}
        ganz = (WURZEL / "docs" / "zeitsteuerung.md").read_text(
            encoding="utf-8"
        )

        # Nur der Abschnitt über die Oberfläche. Weiter unten stehen
        # Aufrufe von install.sh, und dort ist der Takt eine freie
        # Minutenzahl – »--alle 10« ist dort kein Fehler, sondern geht.
        text = ganz.split("## Wie oft?", 1)[1].split("\n## ", 1)[0]

        for erfunden in ("10 Minuten", "90 Minuten", "10–90"):
            self.assertNotIn(erfunden, text, f"»{erfunden}« gibt es nicht")

        for echt in echte:
            self.assertIn(
                echt, text, f"»{echt}« ist wählbar, steht aber nicht in der Doku"
            )

    def test_auch_die_uebersichtsgrafik(self):
        svg = (WURZEL / "assets" / "uebersicht.svg").read_text(encoding="utf-8")

        self.assertNotIn("10–90", svg)


class VerweiseInsLeereTest(unittest.TestCase):
    """**Ein Verweis auf einen Abschnitt, den es nicht gibt.**

    In ``erste-schritte.md`` stand seit jeher »Zu Proton in derselben
    Anleitung« – und in ``postfaecher-einrichten.md`` gab es zu Proton
    kein Wort. Wer dem Verweis folgte, suchte vergeblich.

    Aufgefallen am 2026-09-16, als Stephan erklärte, dass Proton ohne die
    Bridge gar nicht geht. Der Abschnitt steht jetzt dort; dieser Test
    hält fest, dass Verweise auf Abschnitte auch ankommen.

    **Was er nicht kann, und das ist die Mehrheit der Fälle:** Der
    ursprüngliche Verweis war gar kein Link, sondern ein Satz – »Zu
    Proton in derselben Anleitung«. Einen Verweis in Prosa findet kein
    Test; er wäre nur beim Lesen aufgefallen, und gelesen hat ihn zwei
    Wochen lang niemand.

    Geprüft werden hier ausschließlich Verweise der Form
    ``[…](datei.md#abschnitt)``. Beim Anlegen war das genau einer. Der
    Wert liegt also in der Zukunft, nicht in der Gegenwart – und wer
    einen Verweis in einen Satz schreibt statt in eine Klammer, umgeht
    diesen Test weiterhin.
    """

    @staticmethod
    def _anker(text: str) -> set[str]:
        """Die Sprungmarken, die Markdown aus Überschriften macht."""
        marken = set()
        for zeile in text.splitlines():
            if not zeile.startswith("#"):
                continue
            titel = zeile.lstrip("#").strip().lower()
            # Satzzeichen fallen weg, Leerzeichen werden zu Bindestrichen;
            # Umlaute bleiben stehen.
            sauber = re.sub(r"[^\w\s-]", "", titel, flags=re.UNICODE)
            marken.add(re.sub(r"\s+", "-", sauber.strip()))
        return marken

    def test_jeder_abschnittsverweis_kommt_an(self):
        fehlend = []

        for datei in sorted((WURZEL / "docs").glob("*.md")):
            text = datei.read_text(encoding="utf-8")
            for ziel, anker in re.findall(r"\]\((\S+?\.md)#([^)\s]+)\)", text):
                pfad = (datei.parent / ziel).resolve()
                if not pfad.is_file():
                    fehlend.append(f"{datei.name} → {ziel} (Datei fehlt)")
                    continue
                if anker.lower() not in self._anker(
                    pfad.read_text(encoding="utf-8")
                ):
                    fehlend.append(f"{datei.name} → {ziel}#{anker}")

        self.assertEqual(
            fehlend, [], "Diese Verweise zeigen ins Leere: " + ", ".join(fehlend)
        )

    def test_proton_steht_in_der_anleitung(self):
        """Der Anlass: Proton geht ohne die Bridge gar nicht, und das
        stand nirgends."""
        text = (
            WURZEL / "docs" / "postfaecher-einrichten.md"
        ).read_text(encoding="utf-8")

        self.assertIn("--proton", text)
        # Und der Betriebshinweis, der sonst Verwunderung stiftet.
        self.assertIn("Neuanmeldung der Bridge", text)


if __name__ == "__main__":
    unittest.main()
