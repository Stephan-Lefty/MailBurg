"""Was passiert, wenn der Datenträger mit dem Archiv verschwindet.

Externe Platte abgezogen, Netzlaufwerk getrennt, Cloud-Ordner nicht mehr
eingehängt. Stephans beide Archive liegen auf einer USB-Platte, das ist
also kein Gedankenspiel.

**Zwei Fragen sind zu beantworten**, und die zweite ist die wichtigere:
Meldet MailBurg es verständlich? Und bleibt das Archiv heil?

Am 2026-08-28 nachgestellt, indem der Archivordner mitten im Import
weggezogen wurde – für das Programm fast dasselbe wie eine abgezogene
Platte: Neue Zugriffe scheitern, offene Dateien laufen weiter. Ergebnis
damals: ein nackter Python-Traceback, aber ein unversehrtes Archiv.
"""

from __future__ import annotations

import pathlib
import tempfile
import unittest
from unittest import mock

from mailburg.core.archive import Archive


class MeldungTest(unittest.TestCase):
    """Ein Traceback beantwortet die einzige wichtige Frage nicht."""

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.archiv = pathlib.Path(self.ordner.name) / "Archiv"
        Archive.create(self.archiv).close()

    def _lauf(self, fehler: Exception, weg: bool) -> tuple[int, str]:
        import contextlib
        import io

        from mailburg import __main__ as cli

        if weg:
            import shutil

            shutil.rmtree(self.archiv)

        fehlerstrom = io.StringIO()
        with mock.patch.object(cli, "cmd_pruefen", side_effect=fehler):
            with contextlib.redirect_stderr(fehlerstrom):
                code = cli.main(["pruefen", str(self.archiv)])
        return code, fehlerstrom.getvalue()

    def test_verschwundene_platte_wird_benannt(self) -> None:
        code, text = self._lauf(FileNotFoundError(2, "No such file"), weg=True)

        self.assertEqual(code, 4)
        self.assertIn("nicht mehr erreichbar", text)
        self.assertIn("Platte", text)

    def test_und_die_beruhigung_steht_dabei(self) -> None:
        """»Ist mein Archiv jetzt kaputt?« – das ist die eigentliche Frage.

        Die Antwort ist nein, und sie ist belegbar: MailBurg schreibt in
        der Reihenfolge Ablage, Journal, Index.
        """
        _code, text = self._lauf(FileNotFoundError(2, "weg"), weg=True)

        self.assertIn("nichts zu Schaden", text)
        self.assertIn("pruefen", text)

    def test_ein_anderer_fehler_wird_nicht_umgedeutet(self) -> None:
        """Nicht jeder OSError ist eine abgezogene Platte.

        Liegt das Archiv noch da, wäre die Erklärung schlicht falsch –
        und eine falsche Erklärung schickt den Anwender in die falsche
        Richtung.
        """
        code, text = self._lauf(PermissionError(13, "Permission denied"), weg=False)

        self.assertEqual(code, 2)
        self.assertNotIn("abgezogene Platte", text)
        self.assertIn("Zugriff", text)


class UnversehrtheitTest(unittest.TestCase):
    """Das Archiv muss einen Abbruch mitten im Schreiben überstehen.

    Das ist die Zusage, auf der alles andere ruht: Ein Archiv, das bei
    einem Stromausfall oder einer abgezogenen Platte beschädigt zurück-
    bleibt, taugt nicht als Archiv.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.archiv = pathlib.Path(self.ordner.name) / "Archiv"
        Archive.create(self.archiv).close()

    def _mail(self, nr: int) -> bytes:
        return (
            f"From: absender{nr}@example.org\r\n"
            f"To: empfang@example.net\r\n"
            f"Subject: Vorgang {nr}\r\n"
            f"Message-ID: <lauf-{nr}@example.org>\r\n"
            f"\r\n"
            f"Inhalt {nr}\r\n"
        ).encode()

    def test_nach_einem_abbruch_stimmt_die_hashkette(self) -> None:
        with Archive.open(self.archiv) as archiv:
            for nr in range(20):
                archiv.add(self._mail(nr), account="probe", folder="INBOX")

        # Ein Abbruch mitten im Schreiben: Die letzte Mail landet in der
        # Ablage, der Journaleintrag nicht mehr.
        with Archive.open(self.archiv) as archiv:
            with mock.patch.object(
                archiv.journal, "append", side_effect=OSError(5, "E/A-Fehler")
            ):
                with self.assertRaises(OSError):
                    archiv.add(self._mail(99), account="probe", folder="INBOX")

        with Archive.open(self.archiv) as archiv:
            bericht = archiv.verify()

        self.assertTrue(
            bericht["chain_ok"],
            f"Hash-Kette beschädigt: {bericht['chain_errors']}",
        )
        # Die zwanzig heilen Mails müssen vollständig da sein. Ob die
        # abgebrochene mitgezählt wird, ist zweitrangig - sie liegt
        # allenfalls als Datei ohne Journaleintrag herum, und das ist
        # die harmlose Richtung: lieber eine Mail zu viel in der Ablage
        # als ein Journaleintrag ohne Mail.
        self.assertGreaterEqual(bericht["expected"], 20)
        self.assertEqual(bericht["missing"], [])


if __name__ == "__main__":
    unittest.main()
