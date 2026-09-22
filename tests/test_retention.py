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


class KeinWegVorbei(unittest.TestCase):
    """Die Fristprüfung darf im Programm nicht umgehbar sein.

    `Archive.delete()` nimmt einen Parameter `override_retention`. Er ist
    für Tests da – und wäre für den Nächsten, der eine Löschfunktion
    baut, ein offenes Tor. Stephans Ansage dazu am 2026-09-22: Post, die
    noch unter Aufbewahrungspflicht steht, wird **nicht über MailBurg**
    gelöscht. Nicht mit Warnung, nicht mit Rückfrage – gar nicht.

    Dieser Test ist deshalb dieselbe Sorte Wächter wie der in
    `test_sicht.py`: Er schlägt an, sobald jemand den Schalter im
    Programmcode setzt.
    """

    #: Namen, die eine Fristprüfung aushebeln würden. Der erste ist der
    #: historische; wer einen neuen erfindet, trägt ihn hier ein – und
    #: merkt dabei, dass er etwas tut, das nicht vorgesehen ist.
    AUSHEBELND = ("override_retention", "frist_uebergehen", "ohne_frist")

    def test_kein_aufrufer_hebelt_die_fristpruefung_aus(self) -> None:
        """Über den Syntaxbaum, nicht über die Textsuche.

        Ein `grep` findet den Namen auch in Docstrings und Kommentaren –
        und meldet dann ausgerechnet die Stelle, an der *erklärt* wird,
        warum es den Schalter nicht mehr gibt. Beim ersten Lauf ist mir
        genau das passiert. Ein Wächter, der auf seine eigene
        Begründung anschlägt, wird abgeschaltet statt beachtet.
        """
        import ast
        import pathlib

        wurzel = pathlib.Path(__file__).resolve().parent.parent / "mailburg"
        fundstellen = []
        for datei in sorted(wurzel.rglob("*.py")):
            baum = ast.parse(datei.read_text(encoding="utf-8"), str(datei))
            for knoten in ast.walk(baum):
                if not isinstance(knoten, ast.Call):
                    continue
                for schluessel in knoten.keywords:
                    if (schluessel.arg in self.AUSHEBELND
                            and not (isinstance(schluessel.value, ast.Constant)
                                     and schluessel.value.value is False)):
                        fundstellen.append(
                            f"{datei.relative_to(wurzel)}:{knoten.lineno}"
                        )
        self.assertEqual(
            fundstellen, [],
            "Die Fristprüfung wird hier umgangen: "
            + ", ".join(fundstellen)
            + " – gesperrte Post wird nicht über MailBurg gelöscht.",
        )

    def test_die_kommandozeile_bietet_keinen_schalter(self) -> None:
        """Auch nicht unter einem anderen Namen."""
        import pathlib

        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "__main__.py"
        ).read_text(encoding="utf-8")
        for verdacht in ("--trotzdem", "--frist-ignorieren", "--ohne-frist",
                         "--override"):
            self.assertNotIn(
                verdacht, quelle,
                f"{verdacht} wäre ein Weg an der Aufbewahrungsfrist vorbei",
            )


if __name__ == "__main__":
    unittest.main()
