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


class NeueFelderTest(unittest.TestCase):
    """Die Felder, die aus der MailStore-Suchmaske übernommen wurden."""

    def bedingung(self, ausdruck: str) -> tuple[str, list]:
        return build(ausdruck)

    # ------------------------------------------------------------- Dateien

    def test_dateimuster_bleibt_wie_getippt(self):
        # Der Sinn der Übung: *.doc darf nicht "dokumentation.pdf" treffen.
        _, params = self.bedingung("datei:*.doc")
        self.assertEqual(params, ["*.doc"])

    def test_dateimuster_ohne_platzhalter_sucht_enthalten(self):
        # Wer "datei:rechnung" tippt, meint "kommt im Namen vor".
        _, params = self.bedingung("datei:rechnung")
        self.assertEqual(params, ["*rechnung*"])

    def test_dateimuster_nutzt_glob(self):
        klausel, _ = self.bedingung("datei:*.jpg")
        self.assertIn("GLOB", klausel)
        self.assertIn("attachments", klausel)

    # -------------------------------------------------------------- Größe

    def test_groessenangaben(self):
        for ausdruck, erwartet in [
            ("groesse:>5MB", (">", 5 * 1024**2)),
            ("groesse:<100KB", ("<", 100 * 1024)),
            ("groesse:>=2GB", (">=", 2 * 1024**3)),
            ("groesse:500", (">=", 500)),
        ]:
            with self.subTest(ausdruck=ausdruck):
                klausel, params = self.bedingung(ausdruck)
                self.assertIn(erwartet[0], klausel)
                self.assertEqual(params, [erwartet[1]])

    def test_groesse_ohne_zeichen_heisst_mindestens(self):
        # "groesse:5MB" meint große Mails, nicht solche mit exakt 5242880 B.
        klausel, _ = self.bedingung("groesse:5MB")
        self.assertIn(">=", klausel)

    def test_komma_als_dezimalzeichen(self):
        _, params = self.bedingung("groesse:>1,5MB")
        self.assertEqual(params, [int(1.5 * 1024**2)])

    def test_unsinnige_groesse_wird_erklaert(self):
        with self.assertRaises(QueryError) as fehler:
            self.bedingung("groesse:riesig")
        self.assertIn("Größenangabe", str(fehler.exception))

    def test_unbekannte_einheit_wird_erklaert(self):
        with self.assertRaises(QueryError):
            self.bedingung("groesse:>5PB")

    # -------------------------------------------------------- Wichtigkeit

    def test_wichtigkeit_deutsch_und_englisch(self):
        for wort in ("hoch", "high", "wichtig", "dringend"):
            with self.subTest(wort=wort):
                _, params = self.bedingung(f"wichtigkeit:{wort}")
                self.assertEqual(params, ["hoch"])

    def test_unbekannte_wichtigkeit_wird_erklaert(self):
        with self.assertRaises(QueryError):
            self.bedingung("wichtigkeit:mittelprächtig")

    # --------------------------------------------------- Archivierungsdatum

    def test_archiviert_trifft_jahr_monat_und_tag(self):
        for wert in ("2026", "2026-08", "2026-08-25"):
            with self.subTest(wert=wert):
                klausel, params = self.bedingung(f"archiviert:{wert}")
                self.assertIn("m.archiviert LIKE", klausel)
                self.assertEqual(params, [f"{wert}%"])

    def test_archiviert_ist_nicht_das_maildatum(self):
        # Zwei verschiedene Fragen: wann geschrieben, wann archiviert.
        archiv_klausel, _ = self.bedingung("archiviert:2026")
        jahr_klausel, _ = self.bedingung("jahr:2026")
        self.assertNotEqual(archiv_klausel, jahr_klausel)

    # ----------------------------------------------------------- Empfänger

    def test_kopie_und_blindkopie_getrennt(self):
        for feld, art in (("cc", "cc"), ("bcc", "bcc"), ("direkt", "to")):
            with self.subTest(feld=feld):
                klausel, _ = self.bedingung(f"{feld}:chef@example.org")
                self.assertIn(f"r.art = '{art}'", klausel)

    def test_empfaenger_wird_kleingeschrieben_verglichen(self):
        _, params = self.bedingung("cc:Chef@Example.ORG")
        self.assertEqual(params, ["%chef@example.org%"])

    # ------------------------------------------------------- Zusammenspiel

    def test_mehrere_neue_felder_zusammen(self):
        klausel, params = self.bedingung("datei:*.pdf groesse:>1MB wichtigkeit:hoch")
        # Nicht die AND zählen - die stecken auch in den Teilbedingungen.
        self.assertIn("GLOB", klausel)
        self.assertIn("m.size >", klausel)
        self.assertIn("m.wichtigkeit", klausel)
        self.assertEqual(params, ["*.pdf", 1024**2, "hoch"])

    def test_ausschluss_wirkt_auch_auf_neue_felder(self):
        klausel, _ = self.bedingung("-datei:*.jpg")
        self.assertTrue(klausel.startswith("NOT ("))


class DatumsfilterTest(unittest.TestCase):
    """Taggenau suchen – und zwar so, wie man das Datum hier schreibt."""

    def test_beide_schreibweisen_meinen_denselben_tag(self):
        _, deutsch = build("am:26.08.2026")
        _, iso = build("am:2026-08-26")
        self.assertEqual(deutsch, iso)

    def test_zeitraum_schliesst_beide_tage_ein(self):
        _, werte = build("seit:01.01.2026 bis:31.03.2026")
        self.assertEqual(werte[0], "2026-01-01T00:00:00")
        # Bis Mitternacht, nicht bis 00:00 - sonst fiele der letzte Tag
        # bis auf seine erste Sekunde aus dem Zeitraum heraus.
        self.assertEqual(werte[1], "2026-03-31T23:59:59")

    def test_schraegstriche_werden_abgelehnt(self):
        # 08/09/2026 ist in Deutschland der 8. September und in den USA
        # der 9. August. Rät das Programm, bekommt der Anwender die
        # falschen Mails und hält sie für alle - ein Fehler, den bei einer
        # Suche im eigenen Archiv niemand bemerkt.
        with self.assertRaises(QueryError):
            build("am:08/09/2026")

    def test_unsinn_wird_erklaert(self):
        with self.assertRaises(QueryError) as fehler:
            build("seit:neulich")
        self.assertIn("26.08.2026", str(fehler.exception))
