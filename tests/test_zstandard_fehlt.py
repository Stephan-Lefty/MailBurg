"""Was passiert, wenn Zstandard auf diesem Rechner fehlt.

**Gemeldet am 2026-09-22 von einer Anwenderin.** Sie hatte das
Debian-Paket eingerichtet, klickte in der Trefferliste eine Mail an und
bekam einen Traceback. In ihrem Archiv liegen Nachrichten, die mit
Zstandard gepackt sind; auf ihrem Rechner fehlte die Anbindung an
Python.

Drei Fehler wirkten dabei zusammen, und jeder für sich wäre harmlos
gewesen:

1. `python3-zstandard` stand unter *Suggests* – das installiert apt
   nicht mit. Begründet war das mit »packt nur besser«; das stimmt beim
   Schreiben, beim **Lesen** ist es Voraussetzung.
2. Die Meldung nannte das Paket »zstandard«. So heißt es bei pip; unter
   Debian heißt es `python3-zstandard`. Sie installierte daraufhin
   `zstd` – das Kommandozeilenwerkzeug – und schrieb: »Python ist
   aktuell und Zstandard auch.« Beides stimmte.
3. `compress.ensure_readable()` sollte das beim Öffnen abfangen. Der
   Modulkopf beschrieb diese Funktion seit jeher – **es gab sie nie.**
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import compress


class OhneZstandard(unittest.TestCase):
    """Alles hier läuft so, als fehlte die Unterstützung."""

    def setUp(self) -> None:
        patcher = mock.patch.object(compress, "_ZSTD_KIND", None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.archiv = Path(self._tmp.name)

    def _mail_ablegen(self, endung: str) -> None:
        ordner = self.archiv / "mail" / "2026" / "09" / "3f"
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / f"3f8a9c1e.eml{endung}").write_bytes(b"egal")

    def test_ein_zst_archiv_faellt_beim_oeffnen_auf(self) -> None:
        """Und nicht erst beim Klick auf eine Nachricht."""
        self._mail_ablegen(".zst")
        with self.assertRaises(RuntimeError) as fall:
            compress.ensure_readable(self.archiv)
        self.assertIn("Zstandard", str(fall.exception))

    def test_ein_xz_archiv_laesst_sich_oeffnen(self) -> None:
        """LZMA steckt in der Standardbibliothek – da fehlt nichts."""
        self._mail_ablegen(".xz")
        compress.ensure_readable(self.archiv)

    def test_ein_leeres_archiv_laesst_sich_oeffnen(self) -> None:
        """Ein frisch angelegtes hat noch keinen mail-Ordner."""
        compress.ensure_readable(self.archiv)

    def test_die_meldung_nennt_das_richtige_paket(self) -> None:
        """**Der Fehler, der die Anwenderin in die Irre schickte.**

        »zstandard« ist der Name bei pip. Wer unter Debian danach sucht,
        findet nichts – oder das Falsche.
        """
        self._mail_ablegen(".zst")
        with mock.patch.object(
            compress, "__file__",
            "/usr/lib/python3/dist-packages/mailburg/core/compress.py",
        ):
            with self.assertRaises(RuntimeError) as fall:
                compress.ensure_readable(self.archiv)
        text = str(fall.exception)
        self.assertIn("python3-zstandard", text)
        self.assertIn("apt install", text)

    def test_bei_pip_steht_der_pip_name(self) -> None:
        self._mail_ablegen(".zst")
        with mock.patch.object(
            compress, "__file__", "/home/jemand/MailBurg/mailburg/core/compress.py",
        ):
            with self.assertRaises(RuntimeError) as fall:
                compress.ensure_readable(self.archiv)
        text = str(fall.exception)
        self.assertIn("pip install zstandard", text)
        self.assertNotIn("apt install", text)

    def test_auch_die_meldung_beim_entpacken_hilft_weiter(self) -> None:
        """Sie kann trotz der Prüfung auftreten – etwa bei einer

        Sicherung, die auf einem anderen Rechner gepackt wurde.
        """
        with self.assertRaises(RuntimeError) as fall:
            compress.decompress(b"egal", ".zst")
        self.assertIn("Abhilfe", str(fall.exception))


class MitZstandard(unittest.TestCase):
    def test_mit_unterstuetzung_wird_nicht_gesucht(self) -> None:
        """Ein Durchlauf durch 700.000 Dateien beim Öffnen wäre zu teuer."""
        if compress._ZSTD_KIND is None:
            self.skipTest("Auf diesem Rechner fehlt Zstandard ohnehin")
        with mock.patch("pathlib.Path.rglob") as gesucht:
            compress.ensure_readable(Path("/gibt/es/nicht"))
        gesucht.assert_not_called()


class ImDebianPaket(unittest.TestCase):
    """Das Paket muss mitbringen, was zum Lesen nötig ist."""

    def test_zstandard_ist_keine_blosse_empfehlung_mehr(self) -> None:
        import importlib.util
        import pathlib

        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "werkzeuge" / "deb_bauen.py"
        )
        spec = importlib.util.spec_from_file_location("deb_bauen", quelle)
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)

        self.assertIn("python3-zstandard", modul.RECOMMENDS)
        self.assertNotIn(
            "python3-zstandard", modul.SUGGESTS,
            "Unter Suggests installiert apt es nicht mit – und dann "
            "lässt sich kein zst-gepacktes Archiv mehr lesen",
        )


if __name__ == "__main__":
    unittest.main()
