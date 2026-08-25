"""Tests für das Journal und seine Hash-Kette.

Der Kern: Eine nachträgliche Änderung muss auffallen – auch dann, wenn der
Fälscher den Eigenhash des geänderten Eintrags korrekt mitrechnet.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mailburg.core.journal import GENESIS_PREV, Journal, canonical, entry_hash


class TestKanonischeForm(unittest.TestCase):
    """Zwei Rechner müssen für denselben Eintrag dieselben Bytes erzeugen."""

    def test_reihenfolge_der_schluessel_egal(self) -> None:
        a = {"b": 2, "a": 1, "c": 3}
        b = {"c": 3, "a": 1, "b": 2}
        self.assertEqual(canonical(a), canonical(b))

    def test_umlaute_bleiben_umlaute(self) -> None:
        """Kein Ausweichen auf \\uXXXX – sonst hinge der Hash an der Python-Fassung."""
        raw = canonical({"subject": "Rückfrage"})
        self.assertIn("Rückfrage".encode(), raw)

    def test_eigenhash_ignoriert_sich_selbst(self) -> None:
        entry = {"seq": 1, "op": "note", "text": "hallo"}
        without = entry_hash(entry)
        entry["self"] = without
        self.assertEqual(entry_hash(entry), without)


class TestKette(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.meta = Path(self._tmp.name) / "meta"
        self.journal = Journal(self.meta)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_erster_eintrag_haengt_am_ursprung(self) -> None:
        entry = self.journal.append("create", uuid="x")
        self.assertEqual(entry["prev"], GENESIS_PREV)
        self.assertEqual(entry["seq"], 1)

    def test_eintraege_haengen_aneinander(self) -> None:
        first = self.journal.append("note", text="eins")
        second = self.journal.append("note", text="zwei")
        self.assertEqual(second["prev"], first["self"])
        self.assertEqual(second["seq"], 2)

    def test_unberuehrte_kette_ist_heil(self) -> None:
        for i in range(20):
            self.journal.append("note", text=f"Eintrag {i}")
        result = self.journal.verify()
        self.assertTrue(result.ok, f"unerwartete Fundstellen: {result.errors}")
        self.assertEqual(result.entries, 20)

    def test_unbekannter_vorgang_wird_abgelehnt(self) -> None:
        with self.assertRaises(ValueError):
            self.journal.append("loeschen_ohne_spur", hash="x")

    def test_zustand_ueberlebt_das_schliessen(self) -> None:
        """Nach dem Wiederöffnen muss die Kette dort weitergehen, wo sie aufhörte."""
        self.journal.append("note", text="vorher")
        last = self.journal.append("note", text="auch vorher")
        self.journal.close()

        wieder = Journal(self.meta)
        self.assertEqual(wieder.count, 2)
        self.assertEqual(wieder.last_hash, last["self"])
        weiter = wieder.append("note", text="nachher")
        self.assertEqual(weiter["seq"], 3)
        self.assertEqual(weiter["prev"], last["self"])
        self.assertTrue(wieder.verify().ok)


class TestManipulation(unittest.TestCase):
    """Was passieren muss, wenn jemand das Journal von Hand bearbeitet."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.meta = Path(self._tmp.name) / "meta"
        self.journal = Journal(self.meta)
        for i in range(5):
            self.journal.append("add", hash=f"{i:064x}", bucket="2026/08", subject=f"Mail {i}")
        self.journal.flush()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _segment(self) -> Path:
        return sorted(self.meta.glob("*.jsonl"))[0]

    def _lines(self) -> list[dict]:
        return [json.loads(z) for z in self._segment().read_text("utf-8").splitlines()]

    def _write(self, entries: list[dict]) -> None:
        self._segment().write_text(
            "\n".join(canonical(e).decode() for e in entries) + "\n", encoding="utf-8"
        )

    def test_geaenderter_inhalt_faellt_auf(self) -> None:
        """Plumpe Änderung ohne Nachrechnen des Eigenhashes."""
        entries = self._lines()
        entries[2]["subject"] = "Harmlos"
        self._write(entries)

        result = Journal(self.meta).verify()
        self.assertFalse(result.ok)
        self.assertTrue(
            any("Eigenhash" in e.problem for e in result.errors),
            f"erwartet wurde ein Hinweis auf den Eigenhash, bekam: {result.errors}",
        )

    def test_geaenderter_inhalt_mit_nachgerechnetem_hash_faellt_auch_auf(self) -> None:
        """Der wichtigste Test überhaupt.

        Ein Fälscher, der weiß, wie der Eigenhash entsteht, rechnet ihn
        natürlich mit. Genau dagegen ist die Verkettung da: Der folgende
        Eintrag zeigt weiterhin auf den alten Wert.
        """
        entries = self._lines()
        entries[2]["subject"] = "Harmlos"
        entries[2]["self"] = entry_hash(entries[2])
        self._write(entries)

        result = Journal(self.meta).verify()
        self.assertFalse(result.ok, "Die Fälschung blieb unbemerkt.")
        self.assertTrue(
            any("Kette gerissen" in e.problem for e in result.errors),
            f"erwartet wurde ein Kettenbruch, bekam: {result.errors}",
        )

    def test_entfernter_eintrag_faellt_auf(self) -> None:
        """Eine Mail aus dem Protokoll zu streichen, hinterlässt eine Lücke."""
        entries = self._lines()
        del entries[2]
        self._write(entries)

        result = Journal(self.meta).verify()
        self.assertFalse(result.ok)
        self.assertTrue(
            any("Folgenummer" in e.problem or "Kette" in e.problem for e in result.errors)
        )

    def test_angehaengter_eintrag_ohne_kette_faellt_auf(self) -> None:
        """Etwas hinten anzufügen, ohne die Kette zu bedienen, geht nicht durch."""
        entries = self._lines()
        entries.append({"seq": 99, "ts": "2026-01-01T00:00:00+00:00", "op": "add",
                        "hash": "f" * 64, "bucket": "2026/01", "prev": "0" * 64,
                        "self": "unsinn"})
        self._write(entries)

        result = Journal(self.meta).verify()
        self.assertFalse(result.ok)


class TestGrabsteine(unittest.TestCase):
    """Gelöscht wird der Inhalt, nicht die Tatsache."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self._tmp.name) / "meta")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_loeschen_bleibt_im_protokoll(self) -> None:
        digest = "a" * 64
        self.journal.append("add", hash=digest, bucket="2025/03", account="firma")
        self.journal.append(
            "delete", hash=digest, bucket="2025/03",
            reason="dsgvo_art17", actor="stephan", note="Löschersuchen vom 2026-08-25",
        )

        entries = list(self.journal.read_all())
        tombstone = entries[-1]
        self.assertEqual(tombstone["op"], "delete")
        self.assertEqual(tombstone["reason"], "dsgvo_art17")
        self.assertEqual(tombstone["hash"], digest)
        # Und die Kette hält trotzdem.
        self.assertTrue(self.journal.verify().ok)


if __name__ == "__main__":
    unittest.main()
