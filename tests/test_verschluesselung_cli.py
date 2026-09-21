"""Verschlüsselte Archive auf der Kommandozeile.

**Warum das eigene Tests braucht.** Die Verschlüsselung selbst prüfen
:mod:`tests.test_krypto` und :mod:`tests.test_verschluesselung`. Hier
geht es um den Weg dorthin – und der lief beim ersten Durchstich am
2026-08-31 sofort auf die Nase: Es gab bereits ein
``_passwort_erfragen`` für Postfachpasswörter, und die später
definierte Funktion überschrieb die neue stillschweigend. ``mailburg
anlegen --verschluesseln`` brach mit einem ``TypeError`` ab.

Kein Test der Verschlüsselung hätte das gefunden, weil keiner durch die
Kommandozeile ging.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from mailburg import __main__ as haupt
from mailburg.__main__ import main
from mailburg.core import krypto, paths
from mailburg.core.archive import Archive

try:
    import cryptography  # noqa: F401

    HAT_KRYPTO = True
except ImportError:  # pragma: no cover – der Kern kommt ohne aus
    HAT_KRYPTO = False



@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class VerschluesseltAnlegenTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.basis = Path(self._tmp.name)

        patcher = mock.patch.object(
            paths, "data_dir", return_value=self.basis / "daten"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.basis / "daten").mkdir(parents=True, exist_ok=True)

        self._n = krypto.SCRYPT_N
        krypto.SCRYPT_N = 2 ** 8
        self.addCleanup(lambda: setattr(krypto, "SCRYPT_N", self._n))

        self.wurzel = self.basis / "Archiv"

    def _anlegen(self, passwort: str = "ein langes Passwort") -> str:
        """Legt ein verschlüsseltes Archiv an und gibt die Ausgabe zurück."""
        ausgabe = io.StringIO()
        with mock.patch.object(haupt, "eintippen", return_value=passwort):
            with redirect_stdout(ausgabe):
                code = main(["anlegen", str(self.wurzel), "--verschluesseln"])
        self.assertEqual(code, 0, ausgabe.getvalue())
        return ausgabe.getvalue()

    def test_anlegen_laeuft_ueberhaupt_durch(self):
        """Der Test, der am 2026-08-31 gefehlt hat."""
        self._anlegen()

        self.assertTrue(Archive.ist_verschluesselt(self.wurzel))

    def test_der_notschluessel_wird_ausgegeben(self):
        """Er ist genau hier zu sehen und nie wieder."""
        ausgabe = self._anlegen()

        import re

        gefunden = re.search(r"[A-Z2-9]{4}(?:-[A-Z2-9]{4}){7}", ausgabe)
        self.assertIsNotNone(gefunden, ausgabe)
        # Und er öffnet das Archiv tatsächlich.
        with Archive.open(self.wurzel, passwort=gefunden.group(0)) as archiv:
            self.assertEqual(archiv.index.count(), 0)

    def test_der_hinweis_zum_suchindex_steht_dabei(self):
        """Eine Verschlüsselung mit einer Lücke muss sie nennen."""
        ausgabe = self._anlegen()

        self.assertIn("Suchindex", ausgabe)

    def test_zwei_verschiedene_eingaben_legen_nichts_an(self):
        """Ein Tippfehler hier wäre später nicht mehr zu beheben."""
        eingaben = iter(["erstes", "zweites", "drittes", "drittes"])
        with mock.patch.object(haupt, "eintippen",
                               side_effect=lambda *a, **k: next(eingaben)):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = main(["anlegen", str(self.wurzel), "--verschluesseln"])

        self.assertEqual(code, 0)
        # Angelegt wurde es mit dem dritten, nicht mit dem ersten.
        with Archive.open(self.wurzel, passwort="drittes") as archiv:
            self.assertEqual(archiv.index.count(), 0)

    def test_ohne_den_schalter_bleibt_alles_wie_bisher(self):
        with redirect_stdout(io.StringIO()):
            code = main(["anlegen", str(self.wurzel)])

        self.assertEqual(code, 0)
        self.assertFalse(Archive.ist_verschluesselt(self.wurzel))


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class PasswortBefehlTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.basis = Path(self._tmp.name)

        patcher = mock.patch.object(
            paths, "data_dir", return_value=self.basis / "daten"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.basis / "daten").mkdir(parents=True, exist_ok=True)

        self._n = krypto.SCRYPT_N
        krypto.SCRYPT_N = 2 ** 8
        self.addCleanup(lambda: setattr(krypto, "SCRYPT_N", self._n))

        self.wurzel = self.basis / "Archiv"
        with Archive.create(self.wurzel, name="Test", passwort="altes") as archiv:
            self.notschluessel = archiv.notschluessel

    def _wechseln(self, *eingaben: str) -> int:
        werte = iter(eingaben)
        with mock.patch.object(haupt, "eintippen",
                               side_effect=lambda *a, **k: next(werte)):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return main(["passwort", "aendern", str(self.wurzel)])

    def test_wechseln_setzt_das_neue(self):
        self.assertEqual(self._wechseln("altes", "neues", "neues"), 0)

        with Archive.open(self.wurzel, passwort="neues") as archiv:
            self.assertEqual(archiv.index.count(), 0)

    def test_wechseln_geht_auch_mit_dem_notschluessel(self):
        """Wer das Passwort vergessen hat, will genau das tun."""
        self.assertEqual(
            self._wechseln(self.notschluessel, "neues", "neues"), 0
        )

        with Archive.open(self.wurzel, passwort="neues") as archiv:
            self.assertEqual(archiv.index.count(), 0)

    def test_mit_falschem_alten_passwort_wird_nichts_geaendert(self):
        vorher = (self.wurzel / "archive.json").read_text(encoding="utf-8")

        with mock.patch.object(haupt, "eintippen", return_value="daneben"):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = main(["passwort", "aendern", str(self.wurzel)])

        self.assertEqual(code, 4)
        self.assertEqual(
            (self.wurzel / "archive.json").read_text(encoding="utf-8"), vorher
        )

    def test_die_datei_bleibt_gueltiges_json(self):
        """Sie wird beim Wechsel neu geschrieben – geht die kaputt, ist alles weg."""
        self._wechseln("altes", "neues", "neues")

        meta = json.loads((self.wurzel / "archive.json").read_text(encoding="utf-8"))

        self.assertTrue(meta["encryption"]["huellen"]["passwort"])
        self.assertTrue(meta["encryption"]["huellen"]["notschluessel"])
        self.assertTrue(meta["uuid"])

    def test_bei_einem_offenen_archiv_kommt_eine_erklaerung(self):
        offen = self.basis / "Offen"
        Archive.create(offen, name="Offen").close()

        fehler = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(fehler):
            code = main(["passwort", "aendern", str(offen)])

        self.assertEqual(code, 2)
        self.assertIn("nicht verschlüsselt", fehler.getvalue())


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class OhneTerminalTest(unittest.TestCase):
    """Der gefährlichste Fehlerfall: ein Abruf, der nachts stehen bleibt."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.basis = Path(self._tmp.name)

        patcher = mock.patch.object(
            paths, "data_dir", return_value=self.basis / "daten"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.basis / "daten").mkdir(parents=True, exist_ok=True)

        self._n = krypto.SCRYPT_N
        krypto.SCRYPT_N = 2 ** 8
        self.addCleanup(lambda: setattr(krypto, "SCRYPT_N", self._n))

        self.wurzel = self.basis / "Archiv"
        Archive.create(self.wurzel, name="Test", passwort="geheim").close()

    def test_ohne_terminal_wird_nicht_gefragt_sondern_erklaert(self):
        """Eine Frage ins Leere hieße: der Zeitplan hängt, und niemand merkt es."""
        fehler = io.StringIO()
        with mock.patch("sys.stdin.isatty", return_value=False):
            with redirect_stdout(io.StringIO()), redirect_stderr(fehler):
                code = main(["info", str(self.wurzel)])

        self.assertEqual(code, 4)
        text = fehler.getvalue()
        self.assertIn("passwort hinterlegen", text)
        self.assertIn("MAILBURG_ARCHIVPASSWORTDATEI", text)

    def test_aus_der_umgebung_laeuft_es_durch(self):
        ausgabe = io.StringIO()
        with mock.patch.dict("os.environ", {"MAILBURG_ARCHIVPASSWORT": "geheim"}):
            with mock.patch("sys.stdin.isatty", return_value=False):
                with redirect_stdout(ausgabe):
                    code = main(["info", str(self.wurzel)])

        self.assertEqual(code, 0)
        self.assertIn("Kennung", ausgabe.getvalue())

    def test_ein_falsches_passwort_aus_der_umgebung_meldet_sich(self):
        fehler = io.StringIO()
        with mock.patch.dict("os.environ", {"MAILBURG_ARCHIVPASSWORT": "daneben"}):
            with redirect_stdout(io.StringIO()), redirect_stderr(fehler):
                code = main(["info", str(self.wurzel)])

        self.assertEqual(code, 4)
        self.assertIn("Notschlüssel", fehler.getvalue())




@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class PasswortOhneTastaturTest(unittest.TestCase):
    """Passwortabfragen ohne angeschlossene Tastatur.

    **Am 2026-09-21 beim Erproben der Verschlüsselung aufgelaufen**, und
    zwar dreimal an einem Nachmittag: beim Anlegen eines
    verschlüsselten Archivs, beim Passwortwechsel und beim Hinterlegen
    im Tresor. Jedes Mal ein Traceback – ``getpass.getpass`` wirft ohne
    Terminal einen ``EOFError``.

    Beim *Öffnen* war derselbe Fall seit jeher sauber gelöst, mit einer
    ``isatty``-Prüfung und einer Meldung, die den Ausweg nennt. Von
    zwölf Passwortabfragen in ``__main__`` hatte genau diese eine sie.

    **Wer ein Archiv aus einem Skript einrichtet, trifft das zuerst** –
    beim Aufsetzen eines Servers, in einem Container, in einer
    Automatisierung. Und dort sieht ein Traceback aus wie ein Fehler im
    Programm, nicht wie eine fehlende Eingabemöglichkeit.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = Path(self.ordner.name) / "Archiv"

    def _ohne_tty(self, *argumente: str):
        """Ruft die Kommandozeile so auf, wie ein Skript es täte."""
        from unittest import mock

        ausgabe, fehler = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin.isatty", return_value=False), \
                redirect_stdout(ausgabe), redirect_stderr(fehler):
            code = main(list(argumente))
        return code, ausgabe.getvalue() + fehler.getvalue()

    def test_anlegen_meldet_statt_abzustuerzen(self) -> None:
        code, text = self._ohne_tty("anlegen", str(self.ziel), "--verschluesseln")

        self.assertEqual(code, 2)
        self.assertIn("kein Terminal", text)
        self.assertFalse(self.ziel.exists(), "es darf nichts halbes entstehen")

    def test_die_meldung_nennt_den_ausweg(self) -> None:
        """Eine Meldung ohne Weg wäre nur ein höflicherer Absturz."""
        _, text = self._ohne_tty("anlegen", str(self.ziel), "--verschluesseln")

        self.assertIn("MAILBURG_ARCHIVPASSWORTDATEI", text)

    def test_die_umgebung_wird_beim_anlegen_gelesen(self) -> None:
        """**Der eigentliche Weg für ein Skript.**

        Beim Öffnen galt die Reihenfolge Umgebung → Tresor → fragen
        seit jeher. Beim Anlegen fragte MailBurg immer – wer ein
        verschlüsseltes Archiv automatisiert einrichten wollte, hatte
        gar keinen Weg.
        """
        import os
        from unittest import mock

        with mock.patch.dict(os.environ,
                             {"MAILBURG_ARCHIVPASSWORT": "aus-der-umgebung"}), \
                mock.patch("sys.stdin.isatty", return_value=False), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main(["anlegen", str(self.ziel), "--verschluesseln"])

        self.assertEqual(code, 0)
        self.assertTrue((self.ziel / "archive.json").exists())

        # Und es ist wirklich dieses Passwort.
        from mailburg.core.archive import Archive

        with Archive.open(self.ziel, passwort="aus-der-umgebung",
                          exclusive=False) as archiv:
            self.assertTrue(archiv.name)

    def test_ein_falsches_umgebungspasswort_oeffnet_nicht(self) -> None:
        """Sonst prüfte der Test darüber nur, dass irgendetwas entstand."""
        import os
        from unittest import mock

        from mailburg.core.krypto import KryptoFehler

        with mock.patch.dict(os.environ,
                             {"MAILBURG_ARCHIVPASSWORT": "aus-der-umgebung"}), \
                mock.patch("sys.stdin.isatty", return_value=False), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            main(["anlegen", str(self.ziel), "--verschluesseln"])

        from mailburg.core.archive import Archive

        with self.assertRaises(KryptoFehler):
            Archive.open(self.ziel, passwort="etwas anderes", exclusive=False)

    def test_der_tresor_meldet_statt_abzustuerzen(self) -> None:
        """``passwort hinterlegen`` ohne eingerichteten Hauptschlüssel.

        Ausgerechnet auf dem Weg, der für Server und Zeitplan gedacht
        ist. Die Meldung war gut – sie nennt die fehlende
        Umgebungsvariable –, kam aber als Traceback.
        """
        import os
        from unittest import mock

        with mock.patch.dict(os.environ,
                             {"MAILBURG_ARCHIVPASSWORT": "geheim"}), \
                mock.patch("sys.stdin.isatty", return_value=False), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            main(["anlegen", str(self.ziel), "--verschluesseln"])

        from unittest import mock as m2

        ausgabe, fehler = io.StringIO(), io.StringIO()
        with m2.patch.dict(os.environ, {}, clear=False), \
                m2.patch.object(haupt, "eintippen", return_value="geheim"), \
                redirect_stdout(ausgabe), redirect_stderr(fehler):
            for name in ("MAILBURG_SCHLUESSEL", "MAILBURG_SCHLUESSELDATEI"):
                os.environ.pop(name, None)
            code = main(["passwort", "hinterlegen", str(self.ziel)])

        self.assertEqual(code, 4)
        self.assertIn("Hauptschlüssel", ausgabe.getvalue() + fehler.getvalue())

if __name__ == "__main__":
    unittest.main()
