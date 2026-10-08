"""Was in der Befehlsübersicht steht, muss es auch geben.

**Eine Übersicht veraltet still.** Wird ein Befehl umbenannt oder eine
Option entfernt, merkt das niemand – bis jemand abtippt, was dort steht,
und eine Fehlermeldung bekommt. Dann ist die Übersicht nicht nur
nutzlos, sondern schädlich: Sie hat jemanden auf einen Weg geschickt,
den es nicht gibt.

**Dieser Test liest beide Seiten.** Die Befehle kommen aus
``build_parser()`` – also aus dem Programm selbst –, die Behauptungen
aus ``docs/befehle.md``. Was dort steht und hier fehlt, macht ihn rot.

**Die Gegenrichtung prüft er bewusst nicht.** Ein Befehl, der in der
Übersicht fehlt, ist eine Lücke; ein Befehl, den es nicht gibt, ist ein
Fehler. Nur das Zweite soll einen Testlauf anhalten – sonst stünde
jedem neuen Unterbefehl erst eine Doku-Pflicht im Weg, und das endet
damit, dass jemand den Test entschärft.

Dieselbe Bauart wie der Wächter über die Menüpunkte im Handbuch
(``tests/test_hilfe.py``): Eine Zusage in der Doku schuldet eine
Prüfung.
"""

from __future__ import annotations

import argparse
import re
import unittest
from pathlib import Path

UEBERSICHT = Path(__file__).resolve().parent.parent / "docs" / "befehle.md"

#: Zeilen, die mit »mailburg « beginnen, sind Beispiele zum Abtippen.
#: Alles andere im Dokument ist Fließtext und wird nicht geprüft – dort
#: stehen Befehle in Anführungszeichen mitten im Satz, und die zu
#: zerlegen hieße, einen Parser für Prosa zu schreiben.
BEISPIEL = re.compile(r"^\s*mailburg ([a-z][\w-]*)(.*)$")

#: Optionen erkennt man am doppelten Strich. ``--help`` lassen wir aus:
#: Das kennt jeder Unterbefehl, ohne dass es im Parser steht.
OPTION = re.compile(r"(--[a-zäöüß][\w-]*)")


def _parser_abbild() -> tuple[set[str], dict[str, set[str]]]:
    """Welche Befehle und Optionen es wirklich gibt."""
    from mailburg.__main__ import build_parser

    parser = build_parser()
    unter = next(
        a for a in parser._actions
        if isinstance(a, argparse._SubParsersAction)
    )

    befehle = set(unter.choices)
    erlaubt: dict[str, set[str]] = {}
    for name, teil in unter.choices.items():
        gefunden = {o for a in teil._actions for o in a.option_strings}
        # Unterbefehle zweiter Ebene (konten liste, tresor pruefen …)
        # bringen eigene Optionen mit; für diesen Test genügt, dass sie
        # irgendwo unter ihrem Hauptbefehl vorkommen.
        for tiefer in (a for a in teil._actions
                       if isinstance(a, argparse._SubParsersAction)):
            for zweite, sp in tiefer.choices.items():
                gefunden.add(zweite)
                gefunden |= {o for a in sp._actions for o in a.option_strings}
        erlaubt[name] = gefunden
    return befehle, erlaubt


class BefehlsuebersichtTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(
            UEBERSICHT.is_file(),
            f"{UEBERSICHT} fehlt – die Übersicht ist Teil der Anleitungen.",
        )
        self.text = UEBERSICHT.read_text(encoding="utf-8")
        self.befehle, self.optionen = _parser_abbild()

    def _beispiele(self):
        for nummer, zeile in enumerate(self.text.splitlines(), 1):
            treffer = BEISPIEL.match(zeile)
            if treffer:
                yield nummer, treffer.group(1), treffer.group(2)

    def test_es_gibt_beispiele(self):
        """**Der Wächter muss etwas zu bewachen haben.** Wäre das Format
        der Datei einmal anders, fände die Suche nichts – und ein Test,
        der nichts findet, ist grün und wertlos."""
        self.assertGreater(len(list(self._beispiele())), 30)

    def test_jeder_genannte_befehl_existiert(self):
        unbekannt = [
            f"Zeile {nr}: »mailburg {bef}« gibt es nicht"
            for nr, bef, _ in self._beispiele()
            if bef not in self.befehle
        ]
        self.assertEqual(unbekannt, [])

    def test_jede_genannte_option_existiert(self):
        unbekannt = []
        for nr, bef, rest in self._beispiele():
            if bef not in self.befehle:
                continue
            for option in OPTION.findall(rest):
                if option == "--help":
                    continue
                if option not in self.optionen[bef]:
                    unbekannt.append(
                        f"Zeile {nr}: »{bef} {option}« gibt es nicht")
        self.assertEqual(unbekannt, [])

    def test_die_uebersicht_ist_verlinkt(self):
        """Eine Anleitung, die in keinem Verzeichnis steht, findet
        niemand – und sie veraltet dann besonders schnell."""
        verzeichnis = (UEBERSICHT.parent / "README.md").read_text(
            encoding="utf-8")

        self.assertIn("befehle.md", verzeichnis)

    def test_die_drei_regeln_stehen_oben(self):
        """**Sie stammen aus Schaden, nicht aus Vorsicht.** Wer die
        Übersicht umbaut, soll sie nicht beiläufig verlieren: Jede der
        drei hat im Betrieb schon Daten gekostet oder Stunden.
        """
        kopf = self.text[:self.text.find("## 1.")]

        self.assertIn("Sichern", kopf)
        self.assertIn("Suchindex", kopf)
        self.assertIn("Kontonamen", kopf)

    def test_keine_echten_daten(self):
        """Die Übersicht liegt im öffentlichen Repo. Beispiele gehören
        auf ``example``-Namen, Pfade auf Platzhalter."""
        verdacht = [wort for wort in ("hostedoffice", "Sitebah", "HaBeFa")
                    if wort.lower() in self.text.lower()]

        self.assertEqual(verdacht, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
