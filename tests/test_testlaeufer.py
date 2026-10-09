"""Der Testläufer muss einen gescheiterten Test auch melden.

**Das ist der einzige Punkt, an dem hier etwas schiefgehen darf – und
er darf es nicht.** ``tests/lauf.py`` beendet den Prozess selbst, mit
``os._exit``, um einen Absturz beim Herunterfahren von Qt zu umgehen
(siehe den Modulkopf dort). Liefert er dabei versehentlich immer
``0``, ist die CI für immer grün, und kein gescheiterter Test fällt je
wieder auf. Das wäre schlimmer als der Absturz, den er behebt.

Deshalb prüft diese Datei beide Richtungen, und zwar in einem echten
Prozess: Ein ``os._exit`` lässt sich nicht abfangen, und was davor
passiert, muss man ihm von außen ansehen.
"""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def _in_eigenem_prozess(skript: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(skript)],
        cwd=str(WURZEL), capture_output=True, text=True, timeout=120,
    )


class RueckgabewertTest(unittest.TestCase):
    """Was die Tests sagen, muss am Prozessende ankommen."""

    def _lauf(self, ergebnis: int) -> subprocess.CompletedProcess:
        # ``laufen`` wird ersetzt, damit hier nicht die ganze Suite
        # noch einmal durchläuft – geprüft wird der Weg vom Ergebnis
        # zum Rückgabewert, nicht das Entdecken der Tests.
        return _in_eigenem_prozess(f"""
            import sys
            sys.path.insert(0, {str(WURZEL)!r})
            from tests import lauf
            lauf.laufen = lambda *a, **k: {ergebnis}
            lauf.main(["lauf.py"])
        """)

    def test_alles_gruen_gibt_null(self):
        self.assertEqual(self._lauf(0).returncode, 0)

    def test_ein_fehlschlag_gibt_eins(self):
        """**Der Test, auf den es ankommt.** Ohne ihn wäre ein Läufer,
        der stillschweigend immer Erfolg meldet, nicht zu
        unterscheiden von einem, der funktioniert."""
        self.assertEqual(self._lauf(1).returncode, 1)

    def test_das_wegwerfverzeichnis_verschwindet(self):
        """``os._exit`` überspringt die ``atexit``-Haken.

        Einer davon löscht das Wegwerfverzeichnis der Tests. Ohne den
        ausdrücklichen Aufruf bliebe nach jedem Lauf ein Ordner unter
        ``/tmp`` zurück – genau der Müll, den ``tests/__init__.py`` am
        26.08.2026 abstellen sollte (5.585 Dateien, 1,5 GB).
        """
        lauf = _in_eigenem_prozess(f"""
            import sys
            sys.path.insert(0, {str(WURZEL)!r})
            import tests
            from tests import lauf
            print(tests._WEGWERFBAR)
            lauf.laufen = lambda *a, **k: 0
            lauf.main(["lauf.py"])
        """)

        self.assertEqual(lauf.returncode, 0, lauf.stderr)
        ordner = Path(lauf.stdout.strip().splitlines()[0])
        self.assertFalse(
            ordner.exists(),
            f"»{ordner}« liegt noch da – das Aufräumen lief nicht.",
        )

    def test_die_fremden_haken_laufen_nicht(self):
        """**Und genau das ist der Witz an der Sache.**

        Hier stand zuerst ``atexit._run_exitfuncs()`` – das führt
        *alle* Haken aus, auch den von PySide6, der Qt abbaut. Damit
        stieß der Läufer denselben Absturz an, den er vermeiden soll:
        Der Prozess starb drei Sekunden nach der Zeile »OK«, mit
        Signal 6.

        Geprüft wird also, dass ein fremder Haken **nicht** läuft. Das
        ist eine ungewöhnliche Zusage für einen Test – deshalb steht
        hier, warum sie richtig ist.
        """
        with tempfile.TemporaryDirectory() as ordner:
            spur = Path(ordner) / "spur.txt"
            lauf = _in_eigenem_prozess(f"""
                import atexit, pathlib, sys
                sys.path.insert(0, {str(WURZEL)!r})
                from tests import lauf
                atexit.register(
                    lambda: pathlib.Path({str(spur)!r}).write_text("ja")
                )
                lauf.laufen = lambda *a, **k: 0
                lauf.main(["lauf.py"])
            """)

            self.assertEqual(lauf.returncode, 0, lauf.stderr)
            self.assertFalse(
                spur.is_file(),
                "Ein fremder atexit-Haken lief – dann läuft auch der "
                "von PySide6, und der bringt den Prozess um.",
            )

    def test_die_ergebniszeile_kommt_noch_an(self):
        """``os._exit`` schreibt gepufferte Ausgabe nicht mehr weg.

        Ohne das Leeren der Puffer fehlte am Ende die Zeile »OK« – und
        ein Testlauf ohne Ergebniszeile liest sich wie ein
        abgestürzter.
        """
        lauf = _in_eigenem_prozess(f"""
            import sys
            sys.path.insert(0, {str(WURZEL)!r})
            from tests import lauf
            print("letzte Zeile", end="")
            lauf.laufen = lambda *a, **k: 0
            lauf.main(["lauf.py"])
        """)

        self.assertEqual(lauf.returncode, 0, lauf.stderr)
        self.assertIn("letzte Zeile", lauf.stdout)


class EntdeckenTest(unittest.TestCase):
    """Dass er überhaupt findet, was er ausführen soll."""

    def _baum(self, inhalt: str) -> tuple[Path, Path]:
        """Ein Mini-Testbaum mit genau einer Datei darin.

        **Der Paketname trägt den Namen des Tests**, und das ist nicht
        Kosmetik: ``unittest`` merkt sich geladene Module und lehnt ein
        zweites gleichnamiges aus einem anderen Verzeichnis ab –
        »incorrectly imported … Is this module globally installed?«.
        Zwei Tests mit demselben Paketnamen gehen also nur einzeln
        durch, und der zweite scheitert aus einem Grund, der nichts
        mit seiner Sache zu tun hat.
        """
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        wurzel = Path(ordner.name)
        paket = wurzel / f"proben_{self._testMethodName}"
        paket.mkdir()
        (paket / "__init__.py").write_text("", encoding="utf-8")
        (paket / "test_probe.py").write_text(
            textwrap.dedent(inhalt), encoding="utf-8")
        return wurzel, paket

    def test_ein_bestandener_lauf_gibt_null(self):
        from tests.lauf import laufen

        wurzel, paket = self._baum("""
            import unittest

            class ProbeTest(unittest.TestCase):
                def test_geht(self):
                    self.assertTrue(True)
        """)

        self.assertEqual(
            laufen(start=paket, wurzel=wurzel, wortreich=0,
                   ausgabe=io.StringIO()), 0)

    def test_ein_gescheiterter_lauf_gibt_eins(self):
        from tests.lauf import laufen

        wurzel, paket = self._baum("""
            import unittest

            class ProbeTest(unittest.TestCase):
                def test_geht_nicht(self):
                    self.assertEqual(1, 2)
        """)

        self.assertEqual(
            laufen(start=paket, wurzel=wurzel, wortreich=0,
                   ausgabe=io.StringIO()), 1)

    def test_ein_fehler_beim_laden_zaehlt_auch(self):
        """**Eine Datei, die sich nicht importieren lässt, ist ein
        Fehlschlag** – kein Grund, sie zu überspringen. Genau so wäre
        am 01.10.2026 der f-string-Fehler durchgerutscht, der die
        Weboberfläche unter Python 3.11 gar nicht erst starten ließ.
        """
        from tests.lauf import laufen

        wurzel, paket = self._baum("""
            import unittest
            raise ImportError("etwas fehlt")
        """)

        self.assertEqual(
            laufen(start=paket, wurzel=wurzel, wortreich=0,
                   ausgabe=io.StringIO()), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
