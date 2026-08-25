"""Tests für die Aufbewahrungsfristen.

Die Zahlen hier sind bewusst ausgeschrieben und nicht aus dem Modul
abgeleitet. Ändert jemand versehentlich eine Frist, soll der Test
fehlschlagen – nicht stillschweigend mitwandern.
"""

from __future__ import annotations

import unittest
from datetime import date

from mailburg.core.retention import Category, Jurisdiction, Policy, describe


class TestFristen(unittest.TestCase):
    def test_deutschland(self) -> None:
        """Handelsbriefe 6, Buchungsbelege 8 Jahre (seit dem BEG IV, 1.1.2025)."""
        policy = Policy(Jurisdiction.DE)
        self.assertEqual(policy.years(Category.HANDELSBRIEF), 6)
        self.assertEqual(policy.years(Category.BUCHUNGSBELEG), 8)

    def test_oesterreich(self) -> None:
        """§ 132 BAO: sieben Jahre für beides."""
        policy = Policy(Jurisdiction.AT)
        self.assertEqual(policy.years(Category.HANDELSBRIEF), 7)
        self.assertEqual(policy.years(Category.BUCHUNGSBELEG), 7)

    def test_schweiz(self) -> None:
        """Art. 958f OR: zehn Jahre."""
        policy = Policy(Jurisdiction.CH)
        self.assertEqual(policy.years(Category.HANDELSBRIEF), 10)
        self.assertEqual(policy.years(Category.BUCHUNGSBELEG), 10)

    def test_privates_hat_keine_frist(self) -> None:
        for raum in Jurisdiction:
            self.assertIsNone(Policy(raum).years(Category.PRIVAT))

    def test_unbestimmtes_gilt_als_pflichtig(self) -> None:
        """Im Zweifel aufbewahren – zu früh gelöscht ist schlimmer als zu spät."""
        policy = Policy(Jurisdiction.DE)
        self.assertIsNotNone(policy.years(Category.UNBESTIMMT))

    def test_bafin_verlaengert_wieder_auf_zehn(self) -> None:
        policy = Policy(Jurisdiction.DE, bafin_supervised=True)
        self.assertEqual(policy.years(Category.BUCHUNGSBELEG), 10)
        # Handelsbriefe bleiben davon unberührt.
        self.assertEqual(policy.years(Category.HANDELSBRIEF), 6)


class TestFristbeginn(unittest.TestCase):
    """Die Uhr läuft ab dem Ende des Kalenderjahres, nicht ab dem Maildatum."""

    def test_jahresende_nicht_maildatum(self) -> None:
        policy = Policy(Jurisdiction.DE)
        # Rechnung vom März 2025 + 8 Jahre -> Ende 2033, nicht März 2033.
        self.assertEqual(
            policy.expires_end_of(Category.BUCHUNGSBELEG, date(2025, 3, 14)), 2033
        )

    def test_dezember_und_januar_desselben_jahres_gleich(self) -> None:
        policy = Policy(Jurisdiction.DE)
        januar = policy.expires_end_of(Category.HANDELSBRIEF, date(2025, 1, 2))
        dezember = policy.expires_end_of(Category.HANDELSBRIEF, date(2025, 12, 30))
        self.assertEqual(januar, dezember)

    def test_privates_laeuft_nie_ab(self) -> None:
        policy = Policy(Jurisdiction.DE)
        self.assertIsNone(policy.expires_end_of(Category.PRIVAT, date(2025, 3, 14)))


class TestSperreUndFaelligkeit(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = Policy(Jurisdiction.DE)
        self.beleg = date(2025, 3, 14)  # Frist bis Ende 2033

    def test_waehrend_der_frist_gesperrt(self) -> None:
        self.assertTrue(
            self.policy.is_locked(Category.BUCHUNGSBELEG, self.beleg, date(2030, 6, 1))
        )
        self.assertFalse(
            self.policy.is_due(Category.BUCHUNGSBELEG, self.beleg, date(2030, 6, 1))
        )

    def test_im_letzten_jahr_noch_gesperrt(self) -> None:
        """Silvester 2033 gilt die Frist noch."""
        self.assertTrue(
            self.policy.is_locked(Category.BUCHUNGSBELEG, self.beleg, date(2033, 12, 31))
        )

    def test_danach_faellig(self) -> None:
        """Ab Neujahr 2034 darf – und soll – gelöscht werden."""
        self.assertFalse(
            self.policy.is_locked(Category.BUCHUNGSBELEG, self.beleg, date(2034, 1, 1))
        )
        self.assertTrue(
            self.policy.is_due(Category.BUCHUNGSBELEG, self.beleg, date(2034, 1, 1))
        )

    def test_privates_ist_nie_gesperrt(self) -> None:
        self.assertFalse(
            self.policy.is_locked(Category.PRIVAT, self.beleg, date(2026, 1, 1))
        )

    def test_privates_wird_nie_faellig(self) -> None:
        """Keine Pflicht zur Aufbewahrung heißt auch keine Pflicht zum Löschen."""
        self.assertFalse(self.policy.is_due(Category.PRIVAT, self.beleg, date(2099, 1, 1)))


class TestBeschreibung(unittest.TestCase):
    def test_nennt_land_und_jahre(self) -> None:
        text = describe(Policy(Jurisdiction.AT))
        self.assertIn("Österreich", text)
        self.assertIn("7", text)


if __name__ == "__main__":
    unittest.main()
