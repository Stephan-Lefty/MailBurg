"""Der Weg zurück – auf der Kommandozeile.

**Sichern konnte MailBurg von Anfang an, zurückholen bis zum
2026-09-21 nur im Fenster.** ``sicherung.entpacken()`` und
``uebernehmen()`` hatten genau einen Aufrufer: ``ui/sichern.py``.

Auf einem Server gibt es kein Fenster – und dort wird eine
Wiederherstellung am ehesten gebraucht, nämlich dann, wenn etwas
kaputt ist. **Ein Archivprogramm, dessen Rückweg an einer grafischen
Oberfläche hängt, hat im Ernstfall keinen.**

Aufgefallen beim Durchspielen der Verschlüsselung: Die Prüfliste
verlangte »Sicherung in ein neues Archiv einspielen«, und das ließ
sich auf der Kommandozeile nicht machen.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from mailburg.__main__ import main
from mailburg.core.archive import Archive, Mode

try:
    import cryptography  # noqa: F401

    HAT_KRYPTO = True
except ImportError:  # pragma: no cover – der Kern kommt ohne aus
    HAT_KRYPTO = False

ROH = (
    b"From: absender@example.org\r\n"
    b"To: ich@example.org\r\n"
    b"Subject: Probe fuer die Wiederherstellung\r\n"
    b"Date: Mon, 21 Sep 2026 10:00:00 +0200\r\n"
    b"Message-ID: <probe-{n}@example.org>\r\n"
    b"\r\nInhalt {n}. Suchwort: Zwetschgenkuchen.\r\n"
)


class Grundlage(unittest.TestCase):
    """Ein kleines Archiv, gesichert – die Ausgangslage jedes Tests."""

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.basis = Path(self.ordner.name)

        self.quelle = self.basis / "Quelle"
        with Archive.create(self.quelle, mode=Mode.PRIVAT,
                            name="Quelle") as archiv:
            for n in range(3):
                archiv.add(ROH.replace(b"{n}", str(n).encode()),
                           account="Probe", folder="INBOX")

        from mailburg.core import sicherung

        # **Den Namen bestimmt MailBurg, nicht der Test.** Ohne
        # zstandard faellt das Packen auf LZMA zurueck und schreibt
        # .tar.xz. Ein fest vorgegebenes ».tar.zst« enthielte dann
        # LZMA, und das Zurueckholen verlangte ein Paket, das gar nicht
        # gebraucht wird. In der CI ohne Zusatzpakete am 2026-09-21
        # genau so aufgelaufen.
        ordner = self.basis / "Sicherungen"
        befund = sicherung.packen(self.quelle, ordner)
        self.sicherung = befund.ziel

    def _lauf(self, *argumente: str):
        ausgabe, fehler = io.StringIO(), io.StringIO()
        with redirect_stdout(ausgabe), redirect_stderr(fehler):
            code = main(list(argumente))
        return code, ausgabe.getvalue() + fehler.getvalue()


class InEinenLeerenOrdner(Grundlage):
    """Der Fall nach einem Plattenschaden: Das Archiv entsteht neu."""

    def test_es_kommt_zurueck(self) -> None:
        ziel = self.basis / "Neu"

        code, text = self._lauf("wiederherstellen", str(self.sicherung),
                                str(ziel), "--leise")

        self.assertEqual(code, 0, text)
        self.assertTrue((ziel / "archive.json").exists())

    def test_die_kette_ist_heil(self) -> None:
        """**Der eigentliche Punkt.**

        Ein Archiv, das zurückkommt, aber sein Protokoll nicht mehr
        belegen kann, ist für ein Geschäftsarchiv wertlos.
        """
        ziel = self.basis / "Neu"
        self._lauf("wiederherstellen", str(self.sicherung), str(ziel),
                   "--leise")

        with Archive.open(ziel, exclusive=False) as archiv:
            bericht = archiv.verify()

        self.assertTrue(bericht["chain_ok"], bericht["chain_errors"])
        self.assertEqual(bericht["expected"], 3)
        self.assertEqual(bericht["on_disk"], 3)

    def test_ein_volles_ziel_wird_abgelehnt(self) -> None:
        """Zwei Archive ineinander ergäben zwei unprüfbare Protokolle."""
        code, text = self._lauf("wiederherstellen", str(self.sicherung),
                                str(self.quelle))

        self.assertEqual(code, 2)
        self.assertIn("nicht leer", text)

    def test_der_hinweis_auf_den_suchindex_steht_dabei(self) -> None:
        """Er wird nicht mitgesichert – wer das nicht weiß, sucht ihn."""
        ziel = self.basis / "Neu"
        _, text = self._lauf("wiederherstellen", str(self.sicherung),
                             str(ziel), "--leise")

        self.assertIn("neuaufbau", text)


class InEinVorhandenesArchiv(Grundlage):
    """Nur die Nachrichten wandern – beide Ketten bleiben heil."""

    def setUp(self) -> None:
        super().setUp()
        self.ziel = self.basis / "Ziel"
        Archive.create(self.ziel, mode=Mode.PRIVAT, name="Ziel").close()

    def test_die_mails_kommen_an(self) -> None:
        code, text = self._lauf("wiederherstellen", str(self.sicherung),
                                "--hinein", str(self.ziel), "--leise")

        self.assertEqual(code, 0, text)
        with Archive.open(self.ziel, exclusive=False) as archiv:
            self.assertEqual(archiv.index.count(), 3)

    def test_zweimal_legt_nichts_doppelt_ab(self) -> None:
        """**Die Eigenschaft, um die es geht.**

        Wer im Ernstfall wiederherstellt, weiß oft nicht mehr, welche
        Sicherung er schon eingelesen hat. Ein Archiv, das dabei
        Duplikate anlegt, macht aus einer Panne zwei.
        """
        for _ in range(2):
            self._lauf("wiederherstellen", str(self.sicherung),
                       "--hinein", str(self.ziel), "--leise")

        with Archive.open(self.ziel, exclusive=False) as archiv:
            self.assertEqual(archiv.index.count(), 3)

    def test_die_kette_des_ziels_bleibt_heil(self) -> None:
        self._lauf("wiederherstellen", str(self.sicherung),
                   "--hinein", str(self.ziel), "--leise")

        with Archive.open(self.ziel, exclusive=False) as archiv:
            bericht = archiv.verify()

        self.assertTrue(bericht["chain_ok"], bericht["chain_errors"])


class WohinDennUeberhaupt(Grundlage):
    """Ohne Ziel sagt der Befehl, welche zwei es gibt."""

    def test_ohne_ziel_erklaert_er_beide_wege(self) -> None:
        code, text = self._lauf("wiederherstellen", str(self.sicherung))

        self.assertEqual(code, 2)
        self.assertIn("--hinein", text)

    def test_beides_zusammen_geht_nicht(self) -> None:
        """Sonst bliebe offen, was von beidem gemeint war."""
        code, text = self._lauf("wiederherstellen", str(self.sicherung),
                                str(self.basis / "Neu"),
                                "--hinein", str(self.quelle))

        self.assertEqual(code, 2)
        self.assertIn("beides zusammen", text.lower())

    def test_eine_fehlende_datei_meldet_sich(self) -> None:
        code, text = self._lauf("wiederherstellen",
                                str(self.basis / "gibtsnicht.tar.zst"),
                                str(self.basis / "Neu"))

        self.assertEqual(code, 2)
        self.assertIn("gibt es nicht", text)


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class AusEinemVerschluesseltenArchiv(unittest.TestCase):
    """Eine Sicherung aus einem verschlüsselten Archiv.

    Sie ist selbst verschlüsselt – gepackt wird das Verzeichnis, wie es
    liegt. Ihr Passwort kann ein anderes sein als das des Zielarchivs;
    die beiden haben miteinander nichts zu tun.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.basis = Path(self.ordner.name)

        from mailburg.core import sicherung

        self.quelle = self.basis / "Verschluesselt"
        with Archive.create(self.quelle, mode=Mode.PRIVAT, name="V",
                            passwort="geheim-quelle") as archiv:
            archiv.add(ROH.replace(b"{n}", b"0"),
                       account="Probe", folder="INBOX")

        # **Den Namen bestimmt MailBurg, nicht der Test.** Ohne
        # zstandard faellt das Packen auf LZMA zurueck und schreibt
        # .tar.xz. Ein fest vorgegebenes ».tar.zst« enthielte dann
        # LZMA, und das Zurueckholen verlangte ein Paket, das gar nicht
        # gebraucht wird. In der CI ohne Zusatzpakete am 2026-09-21
        # genau so aufgelaufen.
        ordner = self.basis / "Sicherungen"
        befund = sicherung.packen(self.quelle, ordner)
        self.sicherung = befund.ziel

    def test_sie_wandert_in_ein_unverschluesseltes_archiv(self) -> None:
        ziel = self.basis / "Klar"
        Archive.create(ziel, mode=Mode.PRIVAT, name="Klar").close()

        ausgabe, fehler = io.StringIO(), io.StringIO()
        with redirect_stdout(ausgabe), redirect_stderr(fehler):
            code = main(["wiederherstellen", str(self.sicherung),
                         "--hinein", str(ziel),
                         "--passwort-der-sicherung", "geheim-quelle",
                         "--leise"])

        self.assertEqual(code, 0, ausgabe.getvalue() + fehler.getvalue())
        with Archive.open(ziel, exclusive=False) as archiv:
            self.assertEqual(archiv.index.count(), 1)

    def test_ohne_das_passwort_der_sicherung_geht_es_nicht(self) -> None:
        """Sonst prüfte der Test darüber nur, dass irgendetwas ankam."""
        ziel = self.basis / "Klar"
        Archive.create(ziel, mode=Mode.PRIVAT, name="Klar").close()

        ausgabe, fehler = io.StringIO(), io.StringIO()
        with redirect_stdout(ausgabe), redirect_stderr(fehler):
            code = main(["wiederherstellen", str(self.sicherung),
                         "--hinein", str(ziel), "--leise"])

        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
