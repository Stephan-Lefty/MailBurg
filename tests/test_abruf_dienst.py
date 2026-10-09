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
            "mailburg.core.accounts.passwort_holen", return_value="geheim"
        ), mock.patch(
            "mailburg.sources.quelle_fuer", side_effect=OSError("weg")
        ):
            zahl = schleife._konto(mock.Mock(), konto, mock.Mock())

        self.assertIsNone(zahl)
        self.assertTrue(any("übersprungen" in z for z in gemeldet))

    def test_das_passwort_kommt_aus_dem_tresor_und_geht_an_die_quelle(self):
        """**Der zweite Fehler, der am 2026-10-06 auflief.**

        Hier stand ``quelle_fuer(konto)`` – ohne Passwort, ohne
        Höchststand, ohne Abrufzustand. Der Aufruf kam nie bis zum
        Server: ``quelle_fuer() missing 1 required positional argument``.
        Alle sieben Postfächer wurden übersprungen.

        **Höchststand und Zustand gehören dazu, nicht nur das
        Passwort.** Ohne sie holte jeder Lauf das ganze Postfach erneut
        – alle dreißig Minuten, bei 70.000 Mails.
        """
        schleife = Schleife("/irgendwo", Lage(takt=30))
        schleife._melden = lambda text, fehler=False: None

        konto = mock.Mock()
        konto.name = "buero"
        konto.per_oauth2 = False
        konto.betreffmarken = ()
        zustand = mock.Mock()

        with mock.patch(
            "mailburg.core.accounts.passwort_holen", return_value="geheim"
        ), mock.patch("mailburg.sources.quelle_fuer") as quelle_fuer, \
                mock.patch(
                    "mailburg.core.importer.importieren",
                    return_value=mock.Mock(neu=3)):
            zahl = schleife._konto(mock.Mock(), konto, zustand)

        self.assertEqual(zahl, 3)
        args, kwargs = quelle_fuer.call_args
        self.assertEqual(args[1], "geheim")
        self.assertIn("hoechststand", kwargs)
        self.assertIs(kwargs["zustand"], zustand)

    def test_ohne_passwort_im_tresor_gibt_es_einen_eigenen_rat(self):
        """**Ein Dienst kann nicht nachfragen.**

        Fehlt das Passwort, ist das etwas anderes als ein Netzfehler:
        Hier muss ein Mensch auf dem Server etwas hinterlegen. Also
        gehört der Weg dorthin in die Meldung.
        """
        schleife = Schleife("/irgendwo", Lage(takt=30))
        gemeldet: list[str] = []
        schleife._melden = lambda text, fehler=False: gemeldet.append(text)

        konto = mock.Mock()
        konto.name = "buero"
        konto.per_oauth2 = False

        with mock.patch(
            "mailburg.core.accounts.passwort_holen", return_value=None
        ):
            zahl = schleife._konto(mock.Mock(), konto, mock.Mock())

        self.assertIsNone(zahl)
        self.assertTrue(any("tresor uebernehmen" in z for z in gemeldet))

    def test_uebersprungene_postfaecher_gelten_nicht_als_geprueft(self):
        """**Die Meldung, die beruhigte und nicht stimmte.**

        Am 2026-10-06 stand im Ereignisprotokoll »Nichts Neues in 7
        Postfächern«, während alle sieben an einem Fehler gescheitert
        waren. Wer das liest, sucht die ausbleibende Post anderswo.
        """
        self.assertIn("Nichts Neues in 3", Schleife._befund(0, 3, 0))
        self.assertIn("7 Postfächer übersprungen", Schleife._befund(0, 0, 7))
        self.assertNotIn("Nichts Neues", Schleife._befund(0, 0, 7))

        beides = Schleife._befund(5, 2, 1)
        self.assertIn("5 neue Mails aus 2", beides)
        self.assertIn("1 Postfächer übersprungen", beides)

    def test_ein_durchgang_liest_die_eingerichteten_postfaecher(self):
        """**Der Fehler, der den Abruf im Dienst lahmlegte.**

        Hier stand ``for k in Kontenliste()`` – und ``Kontenliste`` ist
        kein Behälter, sondern hat einen (``.konten``). Das wirft in der
        ersten Zeile von ``_einmal``, bei jedem Lauf, und landet im
        weiten ``except`` der Schleife: Der Dienst läuft weiter, meldet
        »alle 30 Minuten« und holt nichts.

        **Warum kein Test das gefunden hat:** Die vorhandenen prüften
        Takt, Pause und ein klemmendes Postfach – also alles um
        ``_einmal`` herum, nie den Weg hinein. Dieser geht durch die
        Stelle, an der es krachte, mit einer echten Kontenliste.
        """
        import tempfile
        from pathlib import Path

        from mailburg.core.accounts import Konto, Kontenliste

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        liste = Kontenliste(Path(ordner.name) / "konten.json")
        liste.konten = [
            Konto(name="buero", server="imap.example.org",
                  benutzer="buero@example.org"),
        ]
        liste.speichern()

        schleife = Schleife("/irgendwo", Lage(takt=30))
        schleife._melden = lambda text, fehler=False: None
        geholt: list[str] = []
        schleife._konto = (
            lambda archiv, konto, zustand: geholt.append(konto.name) or 0
        )

        with mock.patch(
            "mailburg.core.paths.config_dir",
            return_value=Path(ordner.name),
        ), mock.patch("mailburg.core.archive.Archive.open"):
            schleife._einmal()

        self.assertEqual(geholt, ["buero"])
        self.assertNotIn("Keine Postfächer", schleife.letzter_befund or "")

    def test_ohne_postfaecher_wird_es_gesagt_statt_zu_krachen(self):
        """Die Gegenprobe: Ein leerer Ordner ist kein Fehler."""
        import tempfile
        from pathlib import Path

        schleife = Schleife("/irgendwo", Lage(takt=30))
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)

        with mock.patch(
            "mailburg.core.paths.config_dir",
            return_value=Path(ordner.name),
        ):
            schleife._einmal()

        self.assertIn("Keine Postfächer", schleife.letzter_befund)

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
