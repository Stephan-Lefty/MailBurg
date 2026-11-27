"""Meldungen, die den Weg zeigen statt nur den Fehler.

**Zwei Befunde aus einem Nachmittag, und sie haben dieselbe Wurzel.**
Am 2026-11-27 räumte Stephan eine Installation auf. Dabei scheiterte
er an zwei Stellen – nicht an MailBurg, sondern an dem, was MailBurg
ihm sagte:

1. ``mailburg konten entfernen`` meldete »Ein Konto namens X gibt es
   nicht« und verschwieg die vorhandenen, obwohl die Liste im selben
   Augenblick geladen war. Drei Versuche, einer davon mit der
   vollständigen Zeile aus der Ausgabe des Programms selbst.
2. ``mailburg info`` verlangte den Archivpfad – genau das, wonach er
   suchte. Eine Liste der bekannten Archive gab es nur im Fenster.

*Eine Auskunft ist erst dann eine, wenn sie dort landet, wo jemand
hinsieht* – hier in der Spielart: Die Auskunft ist vorhanden und wird
nicht herausgegeben.

**Geprüft wird über die echte Kommandozeile**, nicht an den
Funktionen. Beim Verschlüsselungsbefehl am 2026-08-31 fand erst der
Durchstich einen Namenskonflikt, den kein Einzeltest sah.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def _lauf(*argumente, config: Path):
    """Ruft MailBurg so auf, wie ein Mensch es täte."""
    umgebung = dict(os.environ)
    umgebung["XDG_CONFIG_HOME"] = str(config)
    umgebung["PYTHONPATH"] = str(WURZEL)
    return subprocess.run(
        [sys.executable, "-m", "mailburg", *argumente],
        capture_output=True, text=True, check=False, env=umgebung,
    )


class KeinKontoTest(unittest.TestCase):
    """Was passiert, wenn der genannte Name nicht stimmt."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.config = Path(self.ordner.name)
        (self.config / "mailburg").mkdir()
        self.addCleanup(self.ordner.cleanup)

    def _konten(self, *namen):
        (self.config / "mailburg" / "konten.json").write_text(
            json.dumps({"konten": [
                {"name": n, "server": "imap.example.org", "port": 993,
                 "benutzer": f"{n.lower()}@example.org", "ssl": True}
                for n in namen
            ]}), encoding="utf-8")

    def test_die_vorhandenen_namen_stehen_dabei(self):
        """**Die Liste ist in diesem Augenblick geladen.** Sie nicht
        zu nennen, kostet einen zweiten Befehl – und wer ihn nicht
        kennt, rät weiter."""
        self._konten("Google", "Firma")

        lauf = _lauf("konten", "entfernen", "Goggle", config=self.config)

        self.assertEqual(lauf.returncode, 2)
        self.assertIn("Google", lauf.stderr)
        self.assertIn("Firma", lauf.stderr)

    def test_ein_name_steht_fuer_sich_auf_einer_zeile(self):
        """Damit er sich herauskopieren lässt, ohne dass etwas
        mitkommt – dieselbe Lehre wie beim Komma hinter einem
        Paketnamen zwei Tage zuvor."""
        self._konten("Google")

        lauf = _lauf("konten", "entfernen", "Falsch", config=self.config)

        self.assertIn("\n    Google", lauf.stderr)

    def test_eine_andere_schreibweise_wird_benannt(self):
        """Sonst sucht der Anwender den Fehler im Namen statt in den
        Großbuchstaben. ``finden()`` vergleicht genau."""
        self._konten("Google")

        lauf = _lauf("konten", "entfernen", "google", config=self.config)

        self.assertIn("Groß- und Kleinschreibung", lauf.stderr)
        self.assertIn("Google", lauf.stderr)

    def test_ohne_jedes_konto_hilft_keine_liste(self):
        """Dann ist die Antwort der Weg dorthin, nicht eine leere
        Aufzählung."""
        self._konten()

        lauf = _lauf("konten", "entfernen", "Google", config=self.config)

        self.assertIn("keines eingerichtet", lauf.stderr)
        self.assertIn("mailburg konten hinzufuegen", lauf.stderr)

    def test_dasselbe_gilt_fuer_die_anderen_befehle(self):
        """**An jeder Stelle gleich.** ``finden()`` geht an fünf
        Stellen leer aus; stünde die gute Meldung nur bei
        ``entfernen``, wäre der nächste Anwender bei ``passwort``
        genauso ratlos."""
        self._konten("Google")

        for befehl in (("konten", "passwort", "Goggle"),
                       ("konten", "spamfilter", "Goggle", "--aus")):
            with self.subTest(befehl=befehl[1]):
                lauf = _lauf(*befehl, config=self.config)
                self.assertIn("Google", lauf.stderr)


class ArchivlisteTest(unittest.TestCase):
    """``mailburg archive`` – die Liste, die es nur im Fenster gab."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.config = Path(self.ordner.name)
        (self.config / "mailburg").mkdir()
        self.addCleanup(self.ordner.cleanup)

    def _gemerkt(self, **inhalt):
        (self.config / "mailburg" / "oberflaeche.json").write_text(
            json.dumps(inhalt), encoding="utf-8")

    def _archiv(self, name: str) -> Path:
        ort = self.config / name
        ort.mkdir()
        (ort / "archive.json").write_text(
            json.dumps({"name": name, "uuid": "x"}), encoding="utf-8")
        return ort

    def test_sie_nennt_namen_und_ort(self):
        ort = self._archiv("Geschaeftsarchiv")
        self._gemerkt(archiv=str(ort), zuletzt=[str(ort)])

        lauf = _lauf("archive", config=self.config)

        self.assertEqual(lauf.returncode, 0)
        self.assertIn("Geschaeftsarchiv", lauf.stdout)
        self.assertIn(str(ort), lauf.stdout)

    def test_ein_abgezogenes_archiv_wird_als_solches_erkannt(self):
        """**Sonst liest sich der Eintrag wie ein vorhandenes
        Archiv.** Eine externe Platte kann abgezogen, ein Ordner
        umgehängt sein – und wer den Pfad daraufhin für falsch hält,
        legt ein zweites Archiv an."""
        self._gemerkt(zuletzt=["/gibt/es/nicht/Archiv"])

        lauf = _lauf("archive", config=self.config)

        self.assertIn("nicht erreichbar", lauf.stdout)
        self.assertIn("nicht verloren", lauf.stdout)

    def test_ohne_archiv_steht_da_wie_man_eines_anlegt(self):
        lauf = _lauf("archive", config=self.config)

        self.assertEqual(lauf.returncode, 0)
        self.assertIn("mailburg anlegen", lauf.stdout)

    def test_sie_oeffnet_dabei_kein_archiv(self):
        """**Eine Liste darf nichts sperren.** Ein Archiv zu öffnen
        setzt eine Sperrdatei und baut den Index auf; liefe dieser
        Befehl so, sperrte er beim Aufzählen jedes Archiv der Reihe
        nach aus."""
        ort = self._archiv("Archiv")
        self._gemerkt(zuletzt=[str(ort)])

        _lauf("archive", config=self.config)

        übrig = [p.name for p in ort.iterdir()]
        self.assertEqual(übrig, ["archive.json"], f"angelegt: {übrig}")


if __name__ == "__main__":
    unittest.main()
