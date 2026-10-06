"""Die Ampel im Einrichtungsfenster.

**Siebzehn Zeilen beantworten nicht die Frage, mit der ein Verwalter
dieses Fenster öffnet:** Muss ich etwas tun? Erst danach interessiert
ihn, was.

Die drei Zustände sieht man auf einem Server höchstens einmal – und
genau dann muss der Satz stimmen. Deshalb stehen die Entscheidung
(``Gesamtbild.ampel``) und der Text (``ampeltext``) getrennt vom
Fenster und werden hier ohne Qt geprüft.
"""

from __future__ import annotations

import unittest

from mailburg.server.einrichtung import Befund, Gesamtbild, Lage
from mailburg.ui.servereinrichtung import ampeltext


def _bild(*lagen_und_titel) -> Gesamtbild:
    return Gesamtbild([
        Befund(titel, lage, f"{titel} steht so da.", abhilfe=abhilfe)
        for lage, titel, abhilfe in lagen_und_titel
    ])


class AmpelTest(unittest.TestCase):
    def test_alles_gut_ist_gruen(self):
        bild = _bild(
            (Lage.GUT, "Python", ""),
            (Lage.GUT, "Dienst", ""),
        )

        self.assertIs(bild.ampel, Lage.GUT)

    def test_ein_mangel_macht_rot(self):
        bild = _bild(
            (Lage.GUT, "Python", ""),
            (Lage.FEHLT, "Dienst", "dienst_anlegen"),
        )

        self.assertIs(bild.ampel, Lage.FEHLT)

    def test_rot_schlaegt_gelb(self):
        """Wer rot sieht, soll nicht erst das Gelbe abarbeiten."""
        bild = _bild(
            (Lage.ACHTUNG, "Abruf", "abruf"),
            (Lage.FEHLT, "Dienst", "dienst_anlegen"),
        )

        self.assertIs(bild.ampel, Lage.FEHLT)

    def test_nur_achtung_ist_gelb(self):
        bild = _bild(
            (Lage.GUT, "Dienst", ""),
            (Lage.ACHTUNG, "Abruf", "abruf"),
        )

        self.assertIs(bild.ampel, Lage.ACHTUNG)

    def test_unklares_macht_nicht_gelb(self):
        """**Sonst hätte man eine Ampel, die nie grün wird – und damit
        keine.** »Noch nicht nachgesehen« beim Update ist eine offene
        Frage, keine Störung.
        """
        bild = _bild(
            (Lage.GUT, "Dienst", ""),
            (Lage.UNKLAR, "Fassung", "nachsehen"),
        )

        self.assertIs(bild.ampel, Lage.GUT)


class AmpeltextTest(unittest.TestCase):
    def test_gruen_sagt_was_laeuft(self):
        text, knopf, abhilfe = ampeltext(_bild((Lage.GUT, "Dienst", "")))

        self.assertIn("läuft sauber", text)
        self.assertEqual(knopf, "")
        self.assertEqual(abhilfe, "")

    def test_rot_nennt_die_erste_offene_sache(self):
        """**Ein Knopf, nicht drei.** Die Liste steht in der
        Reihenfolge, in der sie abzuarbeiten ist – also führt der Knopf
        zur ersten offenen Sache."""
        text, knopf, abhilfe = ampeltext(_bild(
            (Lage.FEHLT, "Archiv", "archiv"),
            (Lage.FEHLT, "Dienst", "dienst_anlegen"),
        ))

        self.assertIn("Sofort handeln", text)
        self.assertIn("Archiv", text)
        self.assertEqual(abhilfe, "archiv")
        self.assertEqual(knopf, "Archiv wählen …")

    def test_rot_zaehlt_die_uebrigen_mit(self):
        """Sonst klickt jemand den einen Knopf und hält sich für fertig."""
        text, _, _ = ampeltext(_bild(
            (Lage.FEHLT, "Archiv", "archiv"),
            (Lage.FEHLT, "Dienst", "dienst_anlegen"),
            (Lage.FEHLT, "Zugänge", "zugang"),
        ))

        self.assertIn("und 2 weitere", text)

    def test_bei_einem_einzigen_mangel_steht_kein_weitere(self):
        text, _, _ = ampeltext(_bild((Lage.FEHLT, "Archiv", "archiv")))

        self.assertNotIn("weitere", text)

    def test_gelb_sagt_dass_es_warten_kann(self):
        text, knopf, abhilfe = ampeltext(_bild(
            (Lage.GUT, "Dienst", ""),
            (Lage.ACHTUNG, "Abruf", "abruf"),
        ))

        self.assertIn("keine Eile", text)
        self.assertIn("Abruf", text)
        self.assertEqual(abhilfe, "abruf")

    def test_ein_befund_ohne_knopf_laesst_den_knopf_weg(self):
        """Nicht jeder Mangel hat eine Abhilfe im Fenster – eine leere
        Schaltfläche wäre schlimmer als keine."""
        _, knopf, abhilfe = ampeltext(_bild(
            (Lage.FEHLT, "Betriebssystem", ""),
        ))

        self.assertEqual(knopf, "")
        self.assertEqual(abhilfe, "")


if __name__ == "__main__":
    unittest.main()
