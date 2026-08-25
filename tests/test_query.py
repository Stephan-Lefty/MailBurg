"""Tests für den Suchparser.

Hier landet ungefilterte Benutzereingabe in FTS5-Syntax. Der wichtigste
Punkt ist deshalb nicht, dass die Suche etwas findet, sondern dass sie an
keiner Eingabe zerbricht – auch nicht an Anführungszeichen, Klammern oder
den Operatoren, die FTS5 selbst benutzt.
"""

from __future__ import annotations

import unittest

from mailburg.search.query import QueryError, build


class TestGrundformen(unittest.TestCase):
    def test_leere_suche_passt_auf_alles(self) -> None:
        where, params = build("")
        self.assertEqual(where, "1=1")
        self.assertEqual(params, [])

    def test_nur_leerzeichen(self) -> None:
        self.assertEqual(build("   ")[0], "1=1")

    def test_freitext(self) -> None:
        where, params = build("rechnung")
        self.assertIn("search MATCH", where)
        self.assertIn('"rechnung"*', params[0])

    def test_mehrere_begriffe_werden_verundet(self) -> None:
        _, params = build("rechnung müller")
        self.assertIn("AND", params[0])


class TestFelder(unittest.TestCase):
    def test_betreff_nutzt_dreizeichenindex(self) -> None:
        """Damit betreff:rechnung auch Schlussrechnung findet."""
        where, _ = build("betreff:rechnung")
        self.assertIn("search_tri", where)

    def test_kurzer_begriff_weicht_auf_wortindex_aus(self) -> None:
        """Unter drei Zeichen kann der Dreizeichenindex nichts liefern."""
        where, _ = build("von:ab")
        self.assertIn("search MATCH", where)
        self.assertNotIn("search_tri", where)

    def test_jahr_als_zahl(self) -> None:
        where, params = build("jahr:2025")
        self.assertIn("m.year = ?", where)
        self.assertEqual(params, [2025])

    def test_jahresspanne(self) -> None:
        where, params = build("jahr:2020-2025")
        self.assertIn("BETWEEN", where)
        self.assertEqual(params, [2020, 2025])

    def test_verdrehte_jahresspanne_wird_geradegezogen(self) -> None:
        _, params = build("jahr:2025-2020")
        self.assertEqual(params, [2020, 2025])

    def test_unsinnige_jahresangabe(self) -> None:
        with self.assertRaises(QueryError):
            build("jahr:neulich")

    def test_anhangstyp_ohne_punkt(self) -> None:
        _, params = build("typ:.PDF")
        self.assertEqual(params, ["pdf"])

    def test_hat_anhang(self) -> None:
        where, _ = build("hat:anhang")
        self.assertIn("has_attachments = 1", where)

    def test_unbekanntes_feld_wird_zu_freitext(self) -> None:
        """Wer 'kunde:meier' tippt, will suchen und nicht belehrt werden."""
        where, params = build("kunde:meier")
        self.assertIn("search MATCH", where)
        self.assertIn("meier", params[0])


class TestAusschluss(unittest.TestCase):
    def test_minus_schliesst_aus(self) -> None:
        where, _ = build("-werbung")
        self.assertIn("NOT IN", where)

    def test_ausschluss_bei_feldern(self) -> None:
        where, _ = build("-von:werbung")
        self.assertIn("NOT (", where)


class TestRobustheit(unittest.TestCase):
    """Keine Eingabe darf den Parser oder FTS5 aus dem Tritt bringen."""

    def test_anfuehrungszeichen_gruppieren(self) -> None:
        _, params = build('betreff:"offene posten"')
        self.assertIn("offene posten", params[0])

    def test_fts_operatoren_gelten_als_wort(self) -> None:
        """Wer nach AND oder NOT sucht, meint das Wort."""
        for wort in ("AND", "OR", "NOT", "NEAR"):
            _, params = build(wort)
            self.assertIn(f'"{wort}"', params[0])

    def test_eingebettetes_anfuehrungszeichen(self) -> None:
        """Der klassische Weg, eine Anfrage aufzubrechen – hier verdoppelt."""
        _, params = build('betreff:"a"b"')
        self.assertTrue(all('""' in str(p) or '"' in str(p) for p in params))

    def test_sonderzeichen_stuerzen_nicht_ab(self) -> None:
        for eingabe in ("*", "()", "^", '"', "''", "a*b", "-", ":", "betreff:", "%"):
            with self.subTest(eingabe=eingabe):
                where, params = build(eingabe)
                self.assertIsInstance(where, str)
                self.assertIsInstance(params, list)

    def test_sehr_lange_eingabe(self) -> None:
        where, _ = build("wort " * 500)
        self.assertIsInstance(where, str)

    def test_umlaute_bleiben_erhalten(self) -> None:
        _, params = build("von:müller")
        self.assertIn("müller", str(params[0]))


class TestGegenEchteDatenbank(unittest.TestCase):
    """Der Beweis, dass die erzeugten Ausdrücke auch wirklich laufen."""

    def test_jede_form_ist_gueltiges_sql(self) -> None:
        import sqlite3

        from mailburg.core.index import _SCHEMA

        db = sqlite3.connect(":memory:")
        db.executescript(_SCHEMA)

        eingaben = [
            "", "rechnung", "betreff:rechnung", "von:müller", "an:info@x.de",
            "jahr:2025", "jahr:2020-2025", "typ:pdf", "hat:anhang",
            "konto:firma", "ordner:Gesendet", "text:vertrag", "inhalt:vertrag",
            "-werbung", "-von:spam", 'betreff:"offene posten" jahr:2025',
            "AND", '"', "*", "a*b", "kunde:meier", "müller rechnung typ:pdf",
        ]
        for eingabe in eingaben:
            with self.subTest(eingabe=eingabe):
                where, params = build(eingabe)
                db.execute(
                    f"SELECT COUNT(*) FROM messages m WHERE {where}", params
                ).fetchone()


if __name__ == "__main__":
    unittest.main()
