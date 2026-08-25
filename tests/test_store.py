"""Tests für die Ablage."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mailburg.core.store import UNDATED_BUCKET, Store, bucket_for, content_hash

BEISPIEL = b"From: a@b.de\r\nSubject: Test\r\n\r\nInhalt mit Umlauten: \xc3\xa4\xc3\xb6\xc3\xbc\r\n"


class TestAdressierung(unittest.TestCase):
    def test_gleicher_inhalt_gleicher_hash(self) -> None:
        self.assertEqual(content_hash(BEISPIEL), content_hash(bytes(BEISPIEL)))

    def test_ein_byte_unterschied_anderer_hash(self) -> None:
        self.assertNotEqual(content_hash(BEISPIEL), content_hash(BEISPIEL + b" "))

    def test_monatsordner_aus_datum(self) -> None:
        self.assertEqual(bucket_for(datetime(2025, 3, 14, tzinfo=timezone.utc)), "2025/03")
        self.assertEqual(bucket_for(datetime(1999, 12, 1, tzinfo=timezone.utc)), "1999/12")

    def test_ohne_datum_eigener_ordner(self) -> None:
        self.assertEqual(bucket_for(None), UNDATED_BUCKET)


class TestAblage(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._tmp.name) / "mail")
        self.datum = datetime(2025, 3, 14, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_rundlauf(self) -> None:
        result = self.store.put(BEISPIEL, self.datum)
        self.assertTrue(result.stored)
        self.assertEqual(self.store.get(result.hash, result.bucket), BEISPIEL)

    def test_zweimal_ablegen_schreibt_einmal(self) -> None:
        first = self.store.put(BEISPIEL, self.datum)
        second = self.store.put(BEISPIEL, self.datum)
        self.assertTrue(first.stored)
        self.assertFalse(second.stored, "Die Mail wurde ein zweites Mal geschrieben.")
        self.assertEqual(first.hash, second.hash)

    def test_pfad_ergibt_sich_aus_hash_und_monat(self) -> None:
        """Der Ort muss berechenbar sein – daran hängt der Index-Neuaufbau."""
        result = self.store.put(BEISPIEL, self.datum)
        pfad = self.store.path_for(result.hash, result.bucket)
        self.assertEqual(pfad.parent.name, result.hash[:2])
        self.assertIn("2025", str(pfad))
        self.assertIn("03", str(pfad))

    def test_beschaedigte_datei_faellt_auf(self) -> None:
        """Der Dateiname ist der Hash – Bitfäule fällt beim Lesen auf."""
        result = self.store.put(BEISPIEL, self.datum)
        datei = self.store._find_existing(result.hash, result.bucket)
        assert datei is not None
        datei.write_bytes(b"\x00" * 40)

        with self.assertRaises(Exception) as ctx:
            self.store.get(result.hash, result.bucket)
        self.assertNotIsInstance(ctx.exception, FileNotFoundError)

    def test_fehlende_mail_meldet_sich_deutlich(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.store.get("b" * 64, "2025/03")

    def test_unsinnige_kennung_wird_abgelehnt(self) -> None:
        with self.assertRaises(ValueError):
            self.store.path_for("kein-hash", "2025/03")
        with self.assertRaises(ValueError):
            self.store.path_for("a" * 64, "../../etc")

    def test_entfernen(self) -> None:
        result = self.store.put(BEISPIEL, self.datum)
        self.assertTrue(self.store.remove(result.hash, result.bucket))
        self.assertFalse(self.store.exists(result.hash, result.bucket))
        self.assertFalse(self.store.remove(result.hash, result.bucket))

    def test_durchlauf_findet_alles_wieder(self) -> None:
        erwartet = set()
        for i in range(12):
            mail = BEISPIEL + f"Nummer {i}".encode()
            monat = datetime(2024, (i % 12) + 1, 5, tzinfo=timezone.utc)
            result = self.store.put(mail, monat)
            erwartet.add((result.hash, result.bucket))

        self.assertEqual(set(self.store.iter_all()), erwartet)

    def test_mails_ohne_datum_landen_im_sammelordner(self) -> None:
        result = self.store.put(BEISPIEL, None)
        self.assertEqual(result.bucket, UNDATED_BUCKET)
        self.assertEqual(self.store.get(result.hash, result.bucket), BEISPIEL)

    def test_bytes_bleiben_unveraendert(self) -> None:
        """Keine geglätteten Zeilenenden – sonst wäre DKIM nicht mehr prüfbar."""
        mit_crlf = b"From: a@b.de\r\nSubject: X\r\n\r\nZeile eins\r\nZeile zwei\r\n"
        result = self.store.put(mit_crlf, self.datum)
        self.assertEqual(self.store.get(result.hash, result.bucket), mit_crlf)


if __name__ == "__main__":
    unittest.main()
