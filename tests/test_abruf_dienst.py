"""Der Dienst holt selbst Post – ohne angemeldeten Benutzer.

**Warum es das geben muss.** Der Zeitplan lief unter Windows über die
Aufgabenplanung, und die trägt ``InteractiveToken``: Die Aufgabe läuft
nur, solange jemand angemeldet ist. Auf einem Server ist sonntagabends
niemand angemeldet – die Aufgabe stünde in der Liste und täte nichts.

Am 2026-10-02 im Code bestätigt, bevor es jemanden getroffen hat.
"""

from __future__ import annotations

import os
import unittest
from datetime import time as uhrzeit
from unittest import mock

from mailburg.server.abruf import PAUSE, TAKT, Lage, Schleife, _pause_lesen


class LageTest(unittest.TestCase):
    def test_ohne_angabe_wird_nicht_geholt(self):
        """**Die Vorgabe ist aus, und das ist Absicht.**

        Ein Dienst, der ungefragt anfängt, fremde Postfächer abzurufen,
        wäre eine Überraschung – dieselbe Haltung wie beim Lauschen, das
        auch nur auf dem eigenen Rechner beginnt.
        """
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(Lage.aus_umgebung().an)

    def test_ein_takt_schaltet_ein(self):
        with mock.patch.dict(os.environ, {TAKT: "30"}):
            lage = Lage.aus_umgebung()

        self.assertTrue(lage.an)
        self.assertEqual(lage.takt, 30)

    def test_unsinn_im_takt_schaltet_ab_statt_abzustuerzen(self):
        with mock.patch.dict(os.environ, {TAKT: "halbstündlich"}):
            self.assertFalse(Lage.aus_umgebung().an)

    def test_eine_negative_zahl_wird_nicht_zu_einer_schleife(self):
        with mock.patch.dict(os.environ, {TAKT: "-5"}):
            self.assertFalse(Lage.aus_umgebung().an)


class PauseTest(unittest.TestCase):
    """Die Ruhezeit für die nächtliche Sicherung."""

    def test_eine_pause_wird_gelesen(self):
        von, bis = _pause_lesen("01:30-03:00")

        self.assertEqual(von, uhrzeit(1, 30))
        self.assertEqual(bis, uhrzeit(3, 0))

    def test_unsinn_gilt_als_keine_pause(self):
        """**Lieber zu oft abrufen als stillschweigend gar nicht.**

        Ein Tippfehler darf nicht dazu führen, dass monatelang keine
        Post ankommt.
        """
        for roh in ("", "nachts", "25:00-26:00", "01:30"):
            with self.subTest(angabe=roh):
                self.assertEqual(_pause_lesen(roh), (None, None))

    def test_innerhalb_der_pause_ruht_es(self):
        lage = Lage(takt=30, pause_von=uhrzeit(1, 30), pause_bis=uhrzeit(3, 0))

        self.assertTrue(lage.pausiert(uhrzeit(2, 0)))
        self.assertFalse(lage.pausiert(uhrzeit(4, 0)))
        self.assertFalse(lage.pausiert(uhrzeit(1, 0)))

    def test_ueber_mitternacht_hinweg(self):
        """**Der häufigste Fall bei einer nächtlichen Sicherung.**

        »23:00-02:00« – eine Prüfung mit ``<=`` allein fände dort nie
        ein Fenster.
        """
        lage = Lage(takt=30, pause_von=uhrzeit(23, 0), pause_bis=uhrzeit(2, 0))

        self.assertTrue(lage.pausiert(uhrzeit(23, 30)))
        self.assertTrue(lage.pausiert(uhrzeit(1, 0)))
        self.assertFalse(lage.pausiert(uhrzeit(12, 0)))
        self.assertFalse(lage.pausiert(uhrzeit(22, 59)))

    def test_ohne_pause_laeuft_es_immer(self):
        lage = Lage(takt=30)

        for stunde in (0, 6, 12, 23):
            self.assertFalse(lage.pausiert(uhrzeit(stunde, 0)))


class SchleifeTest(unittest.TestCase):
    def test_ohne_takt_startet_kein_faden(self):
        schleife = Schleife("/irgendwo", Lage(takt=0))

        schleife.starten()

        self.assertIsNone(schleife.faden)

    def test_ein_klemmendes_postfach_beendet_den_lauf_nicht(self):
        """**Dieselbe Regel wie beim Abgleich.**

        Wer nach dem ersten Fehler aufhört, verliert die Post aller
        übrigen Postfächer. Was übersprungen wurde, wird genannt.
        """
        schleife = Schleife("/irgendwo", Lage(takt=30))
        gemeldet: list[str] = []
        schleife._melden = lambda text, fehler=False: gemeldet.append(text)

        konto = mock.Mock(name="buero")
        konto.name = "buero"
        with mock.patch(
            "mailburg.sources.quelle_fuer", side_effect=OSError("weg")
        ):
            zahl = schleife._konto(mock.Mock(), konto)

        self.assertEqual(zahl, 0)
        self.assertTrue(any("übersprungen" in z for z in gemeldet))

    def test_ein_fehler_schaltet_den_abruf_nicht_ab(self):
        """**Der Faden darf nicht sterben.**

        Was aus ``_einmal`` durchkäme, beendete die Schleife – und der
        Abruf hörte auf, ohne dass etwas rot wird. Genau die Sorte
        Fehler, die erst auffällt, wenn Wochen fehlen.
        """
        import inspect

        from mailburg.server import abruf

        quelle = inspect.getsource(abruf.Schleife._schleife)

        self.assertIn("except Exception", quelle)
        self.assertIn("self._einmal()", quelle)

    def test_der_erste_lauf_wartet(self):
        """Beim Hochfahren ist das Netz womöglich noch nicht da."""
        import inspect

        from mailburg.server import abruf

        quelle = inspect.getsource(abruf.Schleife._schleife)

        self.assertIn("self.halt.wait(60)", quelle)


class DienstTest(unittest.TestCase):
    """Der Abruf hängt im Dienst, nicht in einer zweiten Stelle."""

    def test_der_dienst_startet_die_schleife(self):
        import inspect

        from mailburg.server import dienst

        self.assertIn("_abruf_starten", inspect.getsource(dienst.starten))

    def test_der_windows_dienst_auch(self):
        from pathlib import Path

        from mailburg.server import windows_dienst

        quelle = Path(windows_dienst.__file__).read_text("utf-8")

        self.assertIn("_abruf_starten", quelle)
        # Erst den Abruf anhalten, dann den Webserver – sonst bleibt
        # eine angefangene Journalzeile zurück.
        self.assertLess(
            quelle.index("self.abruf.anhalten()"),
            quelle.index("faden.join(timeout=ABKLINGEN)"),
        )


if __name__ == "__main__":
    unittest.main()
