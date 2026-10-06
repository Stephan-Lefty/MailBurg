"""Was die Wartungswerkzeuge einem Verwalter sagen.

**Die Texte sind hier das Eigentliche, nicht die Knöpfe.** Ein Verwalter
sieht eine beschädigte Hash-Kette höchstens einmal – und genau dann muss
dastehen, was das heißt und was er tun kann. Deshalb stehen die
Textbildner als eigene Funktionen im Modul und werden hier ohne Qt
geprüft.

Der Anlass ist der 2026-10-06: An diesem Tag meldete der Dienst »Nichts
Neues in 7 Postfächern«, während alle sieben an einem Fehler gescheitert
waren. Eine Auskunft, die beruhigt und nicht stimmt, ist teurer als gar
keine.
"""

from __future__ import annotations

import unittest

from mailburg.core.bericht import pruefbericht, tresorbericht


def _heil(**mehr):
    """Ein Prüfbericht ohne Beanstandung – Grundlage für die Abwandlungen."""
    bericht = {
        "chain_ok": True,
        "chain_entries": 70133,
        "chain_errors": [],
        "chain_bekannt": [],
        "unvollstaendig": [],
        "missing": [],
        "unexpected": [],
    }
    bericht.update(mehr)
    return bericht


class PruefberichtTest(unittest.TestCase):
    def test_ein_heiles_archiv_sagt_es_klar(self):
        text, heikel = pruefbericht(_heil())

        self.assertFalse(heikel)
        self.assertIn("unversehrt", text)
        self.assertIn("in Ordnung", text)
        self.assertIn("70133", text)

    def test_eine_gerissene_kette_ist_heikel(self):
        text, heikel = pruefbericht(
            _heil(chain_ok=False, chain_errors=["bei 488", "bei 489"])
        )

        self.assertTrue(heikel)
        self.assertIn("BESCHÄDIGT", text)
        self.assertNotIn("in Ordnung", text)

    def test_eine_gerissene_kette_erklaert_sich(self):
        """**Sonst ruft der Verwalter an und fragt, ob die Mails weg
        sind.** Beanstandet ist die Lückenlosigkeit, nicht der Bestand –
        das ist ein Unterschied, den niemand von selbst kennt.
        """
        text, _ = pruefbericht(_heil(chain_ok=False, chain_errors=["x"]))

        self.assertIn("Mails selbst sind davon nicht betroffen", text)
        self.assertIn("kettenvermerk", text)
        self.assertIn("zweiter Vorgang", text)

    def test_fehlende_dateien_werden_genannt(self):
        text, heikel = pruefbericht(_heil(missing=["a", "b", "c"]))

        self.assertTrue(heikel)
        self.assertIn("3 Mail(s)", text)

    def test_untergeschobene_dateien_heissen_beim_namen(self):
        """Die interessanteste der drei Fragen: Eine Datei, die jemand
        von Hand hineingelegt hat, ist nicht archiviert."""
        text, heikel = pruefbericht(_heil(unexpected=["fremd"]))

        self.assertTrue(heikel)
        self.assertIn("untergeschoben", text)

    def test_eine_vermerkte_bruchstelle_bleibt_sichtbar(self):
        """**Ein Vermerk erklärt einen Bruch, er lässt ihn nicht
        verschwinden.** Wer prüft, muss ihn sehen – sonst hätte der
        Vermerk die Stelle aus der Welt geschafft."""
        text, heikel = pruefbericht(_heil(chain_bekannt=["bei 488"]))

        self.assertFalse(heikel)
        self.assertIn("vermerkte Stelle", text)
        self.assertNotIn("unversehrt", text)

    def test_unvollstaendige_eintraege_zaehlen_als_befund(self):
        text, heikel = pruefbericht(_heil(unvollstaendig=[17]))

        self.assertTrue(heikel)
        self.assertIn("welche Mail", text)


class TresorberichtTest(unittest.TestCase):
    def test_ein_vollstaendiger_tresor(self):
        text, heikel = tresorbericht(7, [], [], 7)

        self.assertFalse(heikel)
        self.assertIn("7 Einträge", text)
        self.assertIn("Alle 7", text)

    def test_ein_postfach_ohne_anmeldung_ist_der_teure_fall(self):
        """**Der Dienst meldet das nicht als Fehler.** Er überspringt
        das Postfach – und ein Archiv, das nichts mehr dazubekommt,
        sieht aus wie eines, in dem gerade nichts ankam."""
        text, heikel = tresorbericht(6, [], ["buchhaltung"], 7)

        self.assertTrue(heikel)
        self.assertIn("buchhaltung", text)
        self.assertIn("kommt einfach nichts an", text)
        self.assertIn("tresor uebernehmen", text)

    def test_ein_unlesbarer_eintrag_nennt_den_wahrscheinlichen_grund(self):
        text, heikel = tresorbericht(7, ["post@example.org"], [], 7)

        self.assertTrue(heikel)
        self.assertIn("falsche Hauptschlüssel", text)

    def test_beides_zusammen(self):
        text, heikel = tresorbericht(5, ["a@example.org"], ["buero"], 7)

        self.assertTrue(heikel)
        self.assertIn("buero", text)
        self.assertIn("öffnen", text)


if __name__ == "__main__":
    unittest.main()
