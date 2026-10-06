"""Auch der Import bündelt die Meldungen von pypdf.

**Der Anlass kommt aus dem Betrieb (06.10.2026).** Beim Einlesen von
827.198 Mails aus MailStore lief mitten im Lauf die Meldungsflut über
den Bildschirm:

```
Ignoring wrong pointing object 400 0 (offset 0)
Ignoring wrong pointing object 413 0 (offset 0)
Ignoring wrong pointing object 5 0 (offset 0)
```

Gebündelt wurde das seit dem 02.10. – **aber nur im Neuaufbau.** Der
Import, über den die meisten PDF überhaupt erst hereinkommen, hatte den
Block nie bekommen. Zwei Wege, einer nachgezogen, der andere nicht; in
diesem Projekt inzwischen die sechste Instanz derselben Klasse.

**Gezählt, nicht unterdrückt.** Ein Auffangnetz, das Auskunft wegwirft,
ist genauso falsch wie eines, das sie erfindet – am Ende des Laufs
steht, was wie oft vorkam.
"""

from __future__ import annotations

import inspect
import logging
import unittest

from mailburg.extract import pdf


class BuendelungTest(unittest.TestCase):
    """Was die Hülle tut, unabhängig vom Aufrufer."""

    def test_gleichartige_meldungen_werden_zusammengefasst(self):
        """**Der Wortlaut vor dem Einsetzen entscheidet.** pypdf setzt
        in fast jede Meldung Zahlen ein; gezählt man die fertige, wäre
        jede ihr eigener Eintrag – und zusammengefasst würde nur das
        ohnehin Wortgleiche.
        """
        log = logging.getLogger("pypdf._reader")

        with pdf.meldungen_buendeln() as gezaehlt:
            for nummer in (400, 413, 5, 27):
                log.warning(
                    "Ignoring wrong pointing object %d 0 (offset 0)", nummer
                )
            log.warning("EOF marker not found")
            log.warning("EOF marker not found")

        self.assertEqual(sum(gezaehlt.values()), 6)
        self.assertEqual(len(gezaehlt), 2, f"nicht gebündelt: {dict(gezaehlt)}")
        self.assertEqual(max(gezaehlt.values()), 4)

    def test_nichts_geht_dabei_verloren(self):
        """Die Summe der Zählung ist die Zahl der Meldungen."""
        log = logging.getLogger("pypdf._reader")

        with pdf.meldungen_buendeln() as gezaehlt:
            for i in range(17):
                log.warning("Irgendetwas %d", i)

        self.assertEqual(sum(gezaehlt.values()), 17)


class BeideWegeTest(unittest.TestCase):
    """**Der Wächter gegen das Auseinanderlaufen.**

    Geprüft wird der Sinn, nicht ein Wortlaut: Beide Befehle, die PDF
    lesen, müssen die Bündelung verwenden *und* den Befund hinterher
    melden. Ein Block ohne Meldung wäre ein Verschlucken.
    """

    def _quelle(self, name: str) -> str:
        from mailburg import __main__ as cli

        return inspect.getsource(getattr(cli, name))

    def test_der_import_buendelt(self):
        quelle = self._quelle("cmd_importieren")

        self.assertIn("meldungen_buendeln()", quelle)
        self.assertIn("_pdf_befund_melden", quelle)

    def test_der_neuaufbau_buendelt(self):
        quelle = self._quelle("cmd_neuaufbau")

        self.assertIn("meldungen_buendeln()", quelle)
        self.assertIn("_pdf_befund_melden", quelle)

    def test_wer_pdf_liest_meldet_auch(self):
        """**Beides gehört zusammen.** Wer bündelt, ohne hinterher zu
        melden, macht aus einer lauten Auskunft eine stille – und das
        ist schlimmer als die Flut, denn dann weiß niemand mehr, dass
        die Anhänge klemmten.
        """
        from mailburg import __main__ as cli

        for name in dir(cli):
            if not name.startswith("cmd_"):
                continue
            quelle = inspect.getsource(getattr(cli, name))
            if "meldungen_buendeln()" not in quelle:
                continue
            with self.subTest(befehl=name):
                self.assertIn(
                    "_pdf_befund_melden", quelle,
                    f"{name} bündelt die Meldungen, meldet den Befund aber "
                    f"nicht – damit verschluckt es sie.",
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
