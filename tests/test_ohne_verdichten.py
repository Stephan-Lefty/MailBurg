"""Den Suchindex nicht nach jedem Lauf verdichten.

**Der Anlass kommt aus dem Betrieb (06.10.2026).** Beim Einlesen von
80.000 Mails aus MailStore stand das Journal nach knapp einer Stunde
still – aufgenommen war alles, aber der Lauf war nicht fertig. Gemessen
am Server:

```
Index:  2,28 GB   (vorher 1,07 GB)
WAL:    1,09 GB
CPU:    4 %
```

Das war ``index.optimize()``. Es verschmilzt den **gesamten**
Volltextindex zu einem Stück, nicht nur das Neue – und läuft nach jedem
Importlauf.

**Bei einem Bestand, der in achtzehn Läufen hereinkommt, ist das
siebzehnmal verworfene Arbeit.** Der Index wächst dabei auf zwölf
Gigabyte zu; jeder Lauf verdichtet länger als der vorige. Richtig ist:
siebzehnmal ohne, einmal am Schluss.

**Die Vorgabe bleibt »verdichten«.** Wer einen einzelnen Ordner
einliest, soll am Ende einen fertigen Index haben und nicht erst noch
einen zweiten Befehl kennen müssen.
"""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core.archive import Archive

MAIL = (
    b"From: partner@example.org\r\nTo: wer@example.net\r\n"
    b"Subject: Rechnung {nr}\r\nMessage-ID: <{nr}@example.org>\r\n"
    b"Date: Tue, 6 Oct 2026 09:00:00 +0200\r\n\r\nInhalt {nr}.\r\n"
)


class SchalterTest(unittest.TestCase):
    def setUp(self) -> None:
        from mailburg.core import paths

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.basis = Path(self._tmp.name)
        for name in ("data_dir", "config_dir"):
            patcher = mock.patch.object(
                paths, name, return_value=self.basis / name
            )
            patcher.start()
            self.addCleanup(patcher.stop)
            (self.basis / name).mkdir(parents=True, exist_ok=True)

        self.wurzel = self.basis / "Archiv"
        Archive.create(self.wurzel, name="P").close()
        quelle = self.basis / "Quelle" / "INBOX"
        quelle.mkdir(parents=True)
        for nr in range(5):
            (quelle / f"{nr}.eml").write_bytes(
                MAIL.replace(b"{nr}", str(nr).encode())
            )
        self.quelle = self.basis / "Quelle"

    def _lauf(self, *zusatz):
        from mailburg.__main__ import main

        with mock.patch.object(
            Archive, "open", side_effect=Archive.open, autospec=False
        ):
            with mock.patch(
                "mailburg.core.index.Index.optimize", autospec=True
            ) as verdichtet:
                main([
                    "importieren", str(self.wurzel), str(self.quelle),
                    "--konto", "Probe", "--ohne-anhangstext", *zusatz,
                ])
        return verdichtet

    def test_in_der_vorgabe_wird_verdichtet(self):
        """Wer einen einzelnen Ordner einliest, soll am Ende einen
        fertigen Index haben."""
        verdichtet = self._lauf()

        self.assertEqual(verdichtet.call_count, 1)

    def test_mit_dem_schalter_nicht(self):
        verdichtet = self._lauf("--ohne-verdichten")

        self.assertEqual(verdichtet.call_count, 0)

    def test_und_es_steht_dabei(self):
        """**Eine stille Auslassung wäre schlimmer als keine.** Wer
        nicht erfährt, dass der Index unverdichtet ist, sucht später in
        einem langsamen Archiv und hält das für den Normalzustand.
        """
        from mailburg.__main__ import main

        with mock.patch("mailburg.core.index.Index.optimize"):
            with mock.patch("sys.stdout") as ausgabe:
                main([
                    "importieren", str(self.wurzel), str(self.quelle),
                    "--konto", "Probe", "--ohne-anhangstext",
                    "--ohne-verdichten",
                ])

        gesagt = " ".join(
            str(ruf.args[0]) for ruf in ausgabe.write.call_args_list if ruf.args
        )
        self.assertIn("Nicht verdichtet", gesagt)
        self.assertIn("neuaufbau", gesagt)

    def test_die_suche_funktioniert_trotzdem(self):
        """**Unverdichtet heißt langsamer, nicht kaputt.** Sonst wäre
        der Schalter eine Falle statt einer Abkürzung."""
        self._lauf("--ohne-verdichten")

        with Archive.open(self.wurzel) as archiv:
            self.assertEqual(archiv.index.count(""), 5)
            self.assertEqual(archiv.index.count("Rechnung"), 5)
            self.assertEqual(archiv.index.count("Rechnung 3"), 1)


class VorgabeTest(unittest.TestCase):
    """**Der Wächter gegen ein verrutschtes Standardverhalten.**

    Wer einen einzelnen Ordner einliest, soll am Ende einen fertigen
    Index haben. Würde die Vorgabe umgedreht, hätte jeder Anwender
    stillschweigend einen unverdichteten Index – und das sieht man
    einem Archiv nicht an, man merkt es nur an der Suche.
    """

    def test_verdichtet_wird_ohne_zutun(self):
        from mailburg import __main__ as cli

        quelle = inspect.getsource(cli.cmd_importieren)

        self.assertIn("not args.ohne_verdichten", quelle)
        self.assertNotIn("args.verdichten", quelle)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
