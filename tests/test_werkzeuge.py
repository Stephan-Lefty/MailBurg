"""Die mitgelieferten Hilfsprogramme.

Unter Windows bringt die gepackte ``MailBurg.exe`` poppler und tesseract
selbst mit. Der Anwender soll dafür nichts nachinstallieren müssen –
sonst wäre MailBurg dort eben doch nicht dieselbe Lösung wie unter Linux:
Ein Archiv, das eingescannte Rechnungen nicht findet, ist bei genau den
Dokumenten blind, die man später sucht.

Geprüft wird hier, dass die Programme *gefunden* werden. Ob sie laufen,
prüft der Bau-Workflow auf einem echten Windows – hier gibt es sie nicht.
"""

from __future__ import annotations

import os
import pathlib
import sys
import unittest
from unittest import mock

from mailburg.core import werkzeuge

WURZEL = pathlib.Path(__file__).resolve().parent.parent


class FundortTest(unittest.TestCase):
    """Wo nach den mitgelieferten Programmen gesucht wird."""

    def setUp(self) -> None:
        # Sonst schlägt der Merker aus einem früheren Test durch.
        werkzeuge._erledigt = False

    def test_ohne_gepackte_fassung_gibt_es_nichts(self) -> None:
        """Unter Linux ändert das Modul nichts – dort liegt alles im System."""
        self.assertIsNone(werkzeuge.mitgeliefert())
        self.assertFalse(werkzeuge.bereitstellen())

    def test_der_entpackte_ordner_wird_gefunden(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as ordner:
            (pathlib.Path(ordner) / werkzeuge.ORDNER).mkdir()
            with mock.patch.object(sys, "_MEIPASS", ordner, create=True):
                gefunden = werkzeuge.mitgeliefert()

        self.assertIsNotNone(gefunden)
        self.assertEqual(gefunden.name, werkzeuge.ORDNER)

    def test_er_kommt_vorn_in_den_suchpfad(self) -> None:
        """Was mitgeliefert wurde, ist erprobt – was auf dem Rechner steht, nicht.

        Wer tesseract selbst installiert hat, hat es womöglich ohne
        deutsche Sprachdaten. Ein deutscher Text mit englischem Modell
        gelesen wird zu Buchstabensalat mit zerstörten Umlauten.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as ordner:
            ort = pathlib.Path(ordner) / werkzeuge.ORDNER
            ort.mkdir()
            with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}):
                with mock.patch.object(sys, "_MEIPASS", ordner, create=True):
                    werkzeuge.bereitstellen()
                    self.assertTrue(
                        os.environ["PATH"].startswith(str(ort)),
                        os.environ["PATH"],
                    )

    def test_die_sprachdaten_werden_angemeldet(self) -> None:
        """Ohne TESSDATA_PREFIX findet tesseract sie nicht.

        Es sucht sie in einem Ordner, den es aus seinem eigenen
        Installationsort ableitet – und der ist bei einer entpackten
        ``.exe`` ein Zufallsverzeichnis unter ``%TEMP%``. Es meldet dann
        nicht »Sprachdaten fehlen«, sondern liefert stillschweigend
        nichts.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as ordner:
            ort = pathlib.Path(ordner) / werkzeuge.ORDNER
            (ort / "tessdata").mkdir(parents=True)
            with mock.patch.dict(os.environ, {"PATH": ""}):
                with mock.patch.object(sys, "_MEIPASS", ordner, create=True):
                    werkzeuge.bereitstellen()
                    self.assertEqual(
                        os.environ.get("TESSDATA_PREFIX"),
                        str(ort / "tessdata"),
                    )

    def test_zweimal_aufrufen_verlaengert_den_pfad_nicht(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as ordner:
            (pathlib.Path(ordner) / werkzeuge.ORDNER).mkdir()
            with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}):
                with mock.patch.object(sys, "_MEIPASS", ordner, create=True):
                    werkzeuge.bereitstellen()
                    einmal = os.environ["PATH"]
                    werkzeuge.bereitstellen()
                    self.assertEqual(os.environ["PATH"], einmal)


class BauplanTest(unittest.TestCase):
    """Der Bauplan muss die Werkzeuge einpacken."""

    def test_die_spec_nimmt_sie_mit(self) -> None:
        spec = (WURZEL / "werkzeuge" / "mailburg.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn("BEIGABEN", spec)
        self.assertIn('"werkzeuge"', spec)

    def test_der_workflow_beschafft_sie(self) -> None:
        text = (
            WURZEL / ".github" / "workflows" / "windows-exe.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("poppler", text)
        self.assertIn("tesseract", text)
        self.assertIn("deu", text)

    def test_die_fassungen_stehen_fest(self) -> None:
        """Ein »latest« hier bricht den Bau irgendwann ohne Zutun.

        Und es hieße, dass ein Bau in einem halben Jahr etwas anderes
        einpackt als der heutige – bei einem Archivprogramm, dessen
        Abschriften nachvollziehbar bleiben sollen, ist das die falsche
        Richtung.
        """
        text = (
            WURZEL / ".github" / "workflows" / "windows-exe.yml"
        ).read_text(encoding="utf-8")

        self.assertNotIn("releases/latest", text)
        self.assertIn("POPPLER:", text)
        self.assertIn("TESSDATA:", text)

    def test_die_herkunft_wird_dokumentiert(self) -> None:
        """poppler steht unter der GPL, MailBurg unter MIT.

        Beides in einer Datei weiterzugeben ist zulässig, solange die
        Programme eigenständig bleiben und aufgerufen statt eingebunden
        werden. Was die GPL verlangt, ist Klarheit darüber, was
        mitgeliefert wird und wo der Quellcode dazu liegt.
        """
        text = (
            WURZEL / ".github" / "workflows" / "windows-exe.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("HERKUNFT.txt", text)
        self.assertIn("GPL", text)
        self.assertIn("Apache", text)

    def test_die_fertige_datei_wird_darauf_geprueft(self) -> None:
        """Eingepackt heißt noch nicht gefunden.

        Genau dort saß der Fehler bei den Bildern: Sie steckten in der
        ``.exe`` und wurden trotzdem nicht gefunden, weil niemand in
        ``sys._MEIPASS`` nachsah.
        """
        text = (
            WURZEL / ".github" / "workflows" / "windows-exe.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("MailBurg.exe\" werkzeuge", text)
        self.assertIn("Texterkennung: ja", text)


class RatschlagTest(unittest.TestCase):
    """Der Rat muss zum System passen."""

    def test_unter_windows_kein_apt(self) -> None:
        """»sudo apt install« sagt einem Windows-Nutzer nur, dass er falsch ist."""
        from mailburg.extract import ocr

        with mock.patch.object(ocr, "_windows", return_value=True):
            with mock.patch.object(ocr.shutil, "which", return_value=None):
                _geht, grund = ocr.bereit()

        self.assertNotIn("apt install", grund)
        self.assertNotIn("pacman", grund)
        self.assertIn("MailBurg.exe", grund)

    def test_unter_linux_weiterhin_der_paketbefehl(self) -> None:
        from mailburg.extract import ocr

        with mock.patch.object(ocr, "_windows", return_value=False):
            with mock.patch.object(ocr.shutil, "which", return_value=None):
                _geht, grund = ocr.bereit()

        self.assertIn("apt install", grund)


if __name__ == "__main__":
    unittest.main()
