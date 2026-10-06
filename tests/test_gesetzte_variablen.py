"""Was das Einrichtungsfenster beim Öffnen liest.

**Lesen und Schreiben müssen dieselbe Liste benutzen.** Bis zum
2026-10-06 las ``gesetzte_variablen()`` nur Archiv, Adresse und Port –
geschrieben wurden aber auch der gemeinsame Ordner und die Abrufwerte.

Die Folge war kein Schönheitsfehler: Das Feld *Gemeinsamer Ordner* stand
leer da, und die Prüfliste schloss daraus, der Dienst finde den Tresor
nicht. **Eine rote Ampel über einem Server, der seit Stunden sauber Post
holt** – und ein Verwalter, der nachsieht, nichts findet und beim
nächsten Mal auch der richtigen Meldung nicht mehr glaubt.
"""

from __future__ import annotations

import unittest

from mailburg.core import paths
from mailburg.server import einrichtung
from mailburg.server import einstellungen as lage


class GelesenTest(unittest.TestCase):
    def test_der_gemeinsame_ordner_wird_gelesen(self):
        """Der Fehler, der die Ampel rot machte."""
        self.assertIn(paths.EINSTELLUNGEN, einrichtung.GELESEN)
        self.assertIn(paths.DATEN, einrichtung.GELESEN)

    def test_auch_die_abrufwerte(self):
        """Sonst steht nach jedem Öffnen »kein Abruf« da, obwohl einer
        eingestellt ist."""
        self.assertIn("MAILBURG_ABRUF", einrichtung.GELESEN)
        self.assertIn("MAILBURG_ABRUF_PAUSE", einrichtung.GELESEN)

    def test_was_geschrieben_wird_laesst_sich_auch_lesen(self):
        """**Der eigentliche Wächter.**

        Jede Variable, die das Fenster schreibt, muss es beim nächsten
        Öffnen wiederfinden. Läuft das auseinander, zeigt es Felder
        leer, die gesetzt sind – und die Prüfliste zieht daraus
        falsche Schlüsse.
        """
        from pathlib import Path

        vollstaendig = einrichtung.Umgebung(
            archiv=Path("/irgendwo/Archiv"),
            adresse="0.0.0.0",
            anschluss=8383,
            einstellungen=Path("/irgendwo/Daten"),
            daten=Path("/irgendwo/Daten"),
            abruf=30,
            abrufpause="17:10-04:00",
        )

        for name in vollstaendig.als_variablen():
            with self.subTest(variable=name):
                self.assertIn(
                    name, einrichtung.GELESEN,
                    f"{name} wird geschrieben, aber nie wieder gelesen",
                )

    def test_die_liste_hat_keine_doppelten(self):
        self.assertEqual(
            len(einrichtung.GELESEN), len(set(einrichtung.GELESEN))
        )

    def test_archiv_und_adresse_sind_weiter_dabei(self):
        self.assertIn(lage.ARCHIV, einrichtung.GELESEN)
        self.assertIn(lage.ADRESSE, einrichtung.GELESEN)
        self.assertIn(lage.ANSCHLUSS, einrichtung.GELESEN)


if __name__ == "__main__":
    unittest.main()
