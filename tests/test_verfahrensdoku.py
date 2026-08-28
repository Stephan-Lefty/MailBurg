"""Der Entwurf einer Verfahrensdokumentation nach GoBD.

Die GoBD verlangen sie für jedes System, das steuerlich erhebliche
Daten verarbeitet (Rz. 151 ff.). MailBurg kann den technischen Teil aus
seiner eigenen Konfiguration erzeugen.

**Der wichtigste Prüfpunkt hier ist, dass die Lücken sichtbar bleiben.**
Eine Dokumentation, die vollständig aussieht und es nicht ist, wäre
schlimmer als gar keine: Sie fällt erst in der Prüfung auf, und dann
ist keine Zeit mehr.
"""

from __future__ import annotations

import pathlib
import tempfile
import unittest

from mailburg.core import verfahrensdoku
from mailburg.core.accounts import Konto, Kontenliste
from mailburg.core.archive import Archive


class EntwurfTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "Geschaeftsarchiv"
        Archive.create(self.pfad, mode="geschaeftlich").close()

        with Archive.open(self.pfad) as archiv:
            archiv.add(
                b"From: post@example.org\r\nTo: wir@example.net\r\n"
                b"Subject: Test\r\nDate: Mon, 14 Jan 2020 09:00:00 +0100\r\n"
                b"Message-ID: <a@example.org>\r\n\r\nText\r\n",
                account="firma", folder="INBOX",
            )
            self.kennung = str(archiv.uuid)

    def _text(self, konten=None, zeitplaene=None) -> str:
        with Archive.open(self.pfad, exclusive=False) as archiv:
            return verfahrensdoku.erzeugen(archiv, konten, zeitplaene)

    def test_die_verantwortung_steht_ganz_oben(self) -> None:
        """Nicht im Kleingedruckten: Es ist die wichtigste Aussage."""
        text = self._text()
        kopf = text[: text.index("## 1.")]

        self.assertIn("Steuerpflichtige", kopf)
        self.assertIn("Entwurf", kopf)

    def test_die_luecken_sind_ausgezeichnet(self) -> None:
        text = self._text()

        self.assertIn(verfahrensdoku.LUECKE, text)
        self.assertGreater(text.count(verfahrensdoku.LUECKE), 8)

    def test_was_mailburg_weiss_steht_drin(self) -> None:
        from mailburg import __version__

        text = self._text()

        self.assertIn(__version__, text)
        self.assertIn(self.kennung, text)
        self.assertIn("SHA-256", text)
        self.assertIn("Hash", text.replace("Fingerabdruck", "Hash"))

    def test_die_grenzen_stehen_auch_drin(self) -> None:
        """»Keine Software ist GoBD-konform« gehört in dieses Papier.

        Wer es einem Prüfer vorlegt, soll nicht behaupten, ein Programm
        habe die Pflichten erfüllt.
        """
        text = self._text()

        self.assertIn("Keine Software ist GoBD-konform", text)
        self.assertIn("unterstützt", text)

    def test_auch_die_grenze_der_hashkette(self) -> None:
        """Wer Zugriff hat, kann sie neu berechnen – das gehört gesagt."""
        text = self._text()

        self.assertIn("neu berechnen", text)
        self.assertIn("Siegel", text)


class PostfaecherTest(unittest.TestCase):
    """Nur die Postfächer dieses Archivs.

    Die Kontenliste gilt für das ganze Programm; wer zwei Archive führt,
    hätte sonst in beiden Dokumentationen dieselben Postfächer stehen –
    und in keiner der beiden stünde die Wahrheit.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "A"
        Archive.create(self.pfad, mode="geschaeftlich").close()
        with Archive.open(self.pfad, exclusive=False) as archiv:
            self.kennung = str(archiv.uuid)

    def _liste(self) -> Kontenliste:
        liste = Kontenliste()
        liste.konten = [
            Konto(name="Firma", server="imap.example.org",
                  benutzer="post@example.org", archive=[self.kennung],
                  ausschluss=["Papierkorb", "Spam"]),
            Konto(name="Fremd", server="imap.example.net",
                  benutzer="anderes@example.net", archive=["fremde-kennung"]),
        ]
        return liste

    def _text(self) -> str:
        with Archive.open(self.pfad, exclusive=False) as archiv:
            return verfahrensdoku.erzeugen(archiv, self._liste())

    def test_nur_die_eigenen(self) -> None:
        text = self._text()

        self.assertIn("post@example.org", text)
        self.assertNotIn("anderes@example.net", text)

    def test_die_ausgeschlossenen_ordner_stehen_dabei(self) -> None:
        """Was nicht archiviert wird, ist für einen Prüfer wesentlich."""
        text = self._text()

        self.assertIn("Papierkorb", text)
        self.assertIn("Spam", text)

    def test_ohne_zuordnung_wird_es_gesagt(self) -> None:
        """Ein Archiv ohne Postfach kann Absicht sein – oder ein Versehen."""
        liste = Kontenliste()
        liste.konten = [
            Konto(name="Fremd", server="imap.example.net",
                  benutzer="x@example.net", archive=["fremd"]),
        ]
        with Archive.open(self.pfad, exclusive=False) as archiv:
            text = verfahrensdoku.erzeugen(archiv, liste)

        self.assertIn("kein Postfach zugeordnet", text)


class TaktTest(unittest.TestCase):
    """»Alle 1440 Minuten« ist keine Angabe, mit der jemand rechnet.

    Ein Prüfer liest dieses Papier, kein Programmierer.
    """

    def test_taegliches(self) -> None:
        self.assertEqual(verfahrensdoku.takt_in_worten(1440), "einmal täglich")

    def test_mehrere_tage(self) -> None:
        self.assertEqual(verfahrensdoku.takt_in_worten(2880), "alle 2 Tage")

    def test_stuendlich(self) -> None:
        self.assertEqual(verfahrensdoku.takt_in_worten(60), "stündlich")
        self.assertEqual(verfahrensdoku.takt_in_worten(120), "alle 2 Stunden")

    def test_minuten_bleiben_minuten(self) -> None:
        self.assertEqual(verfahrensdoku.takt_in_worten(30), "alle 30 Minuten")


class PrivatarchivTest(unittest.TestCase):
    """Ein Privatarchiv nennt keine Fristen – es hat keine."""

    def test_keine_aufbewahrungsfristen_im_text(self) -> None:
        with tempfile.TemporaryDirectory() as ordner:
            pfad = pathlib.Path(ordner) / "P"
            Archive.create(pfad, mode="privat").close()
            with Archive.open(pfad, exclusive=False) as archiv:
                text = verfahrensdoku.erzeugen(archiv)

        self.assertNotIn("**Aufbewahrungsfristen.**", text)


if __name__ == "__main__":
    unittest.main()
