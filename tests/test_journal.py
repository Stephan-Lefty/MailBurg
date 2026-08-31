"""Tests für das Journal und seine Hash-Kette.

Der Kern: Eine nachträgliche Änderung muss auffallen – auch dann, wenn der
Fälscher den Eigenhash des geänderten Eintrags korrekt mitrechnet.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class TestFlush(unittest.TestCase):
    """Das Auf-die-Platte-Zwingen muss auf allen Systemen funktionieren."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.meta = Path(self._tmp.name) / "meta"
        self.journal = Journal(self.meta)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_der_deskriptor_fuer_fsync_hat_schreibrecht(self) -> None:
        """Windows verweigert fsync auf einem nur lesend geöffneten Deskriptor.

        Der Fehler ließ dort am 25.08.2026 jeden einzelnen Test scheitern –
        nicht nur die des Journals, denn schon ``Archive.create`` kommt hier
        vorbei. Aufgefallen ist er lange nicht, weil unter Linux alles lief:
        POSIX erlaubt fsync auch lesend.

        Nachstellen lässt sich das ohne Windows nur an der Ursache selbst,
        also am Zugriffsmodus des Deskriptors, den fsync bekommt.
        """
        try:
            import fcntl
        except ImportError:  # pragma: no cover – auf Windows prüft es die CI
            self.skipTest("fcntl gibt es nur auf POSIX")

        modi: list[int] = []
        echtes_fsync = os.fsync

        def mitschreiben(fd: int) -> None:
            modi.append(fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE)
            echtes_fsync(fd)

        self.journal.append("note", text="etwas, das auf die Platte muss")
        with mock.patch.object(os, "fsync", mitschreiben):
            self.journal.flush()

        self.assertTrue(modi, "flush() hat gar nicht synchronisiert")
        for modus in modi:
            self.assertNotEqual(
                modus, os.O_RDONLY,
                "nur lesend geöffnet – unter Windows scheitert fsync damit",
            )

    def test_ohne_aenderung_wird_nichts_synchronisiert(self) -> None:
        """Sonst kostet jeder Aufruf eine Plattenumdrehung ohne Anlass."""
        self.journal.append("note", text="eins")
        self.journal.flush()
        with mock.patch.object(os, "fsync") as fsync:
            self.journal.flush()
        fsync.assert_not_called()

    def test_der_eintrag_steht_danach_wirklich_da(self) -> None:
        self.journal.append("note", text="bleibt")
        self.journal.flush()
        wieder = Journal(self.meta)
        self.assertEqual(wieder.count, 1)
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


class TestAbgebrocheneZeile(unittest.TestCase):
    """Ein Stromausfall mitten im Schreiben.

    Der Docstring von ``_scan_tail`` hat das seit jeher behauptet, der
    Code tat es bis zum 2026-08-31 nicht: Eine halb geschriebene letzte
    Zeile ließ ``json.loads`` werfen, und das Archiv war überhaupt nicht
    mehr zu öffnen. Aufgefallen ist es am verschlüsselten Journal – gilt
    aber genauso ohne Verschlüsselung.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.meta = Path(self._tmp.name) / "meta"
        journal = Journal(self.meta)
        journal.append("add", hash="a" * 64, bucket="2025/03", account="firma")
        journal.append("add", hash="b" * 64, bucket="2025/03", account="firma")
        journal.close()
        self.datei = next(self.meta.glob("*.jsonl"))

    def test_eine_halbe_letzte_zeile_sperrt_nicht_das_ganze_archiv(self) -> None:
        with self.datei.open("ab") as handle:
            handle.write(b'{"seq":3,"op":"a')

        wieder = Journal(self.meta)

        # Der angefangene Eintrag zählt als nie geschrieben.
        self.assertEqual(wieder.count, 2)

    def test_danach_geht_es_lueckenlos_weiter(self) -> None:
        """Der nächste Eintrag muss anschließen, nicht mit dem Rest verschmelzen.

        Eine abgebrochene Zeile endet nicht auf einem Zeilenumbruch – der
        kam ja nicht mehr. Bliebe sie stehen, klebte der nächste Eintrag
        an ihr fest, und aus einem verlorenen würden zwei.
        """
        with self.datei.open("ab") as handle:
            handle.write(b'{"seq":3,"op":"a')

        wieder = Journal(self.meta)
        wieder.append("add", hash="c" * 64, bucket="2025/03", account="firma")

        eintraege = list(wieder.read_all())
        self.assertEqual([e["seq"] for e in eintraege], [1, 2, 3])
        self.assertTrue(wieder.verify().ok)

    def test_eine_kaputte_zeile_mittendrin_wird_nicht_verschwiegen(self) -> None:
        """Die kann kein Absturz verursacht haben – da ist etwas anderes los.

        Und sie wird als solche gemeldet, nicht als Traceback über eine
        JSON-Zeile: Wer sein Archiv nicht mehr aufbekommt, braucht einen
        Satz dazu, wo seine Mails geblieben sind.
        """
        from mailburg.core.journal import JournalBeschaedigt

        zeilen = self.datei.read_bytes().splitlines()
        zeilen[0] = b'{"seq":1,"op":"kap'
        self.datei.write_bytes(b"\n".join(zeilen) + b"\n")

        with self.assertRaises(JournalBeschaedigt) as gefangen:
            Journal(self.meta)

        self.assertIn("Ihre Mails liegen davon unberührt", str(gefangen.exception))


if __name__ == "__main__":
    unittest.main()
