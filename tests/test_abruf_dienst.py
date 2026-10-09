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

        # **Die Texterkennung muss hier mit abgeschaltet sein.** Seit
        # dem 2026-10-09 ruft ``_einmal`` sie auf, und ``Archive.open``
        # ist hier ein Mock: ``Warteschlange.anzahl()`` liefert dann ein
        # MagicMock, und das ist *wahr*. Der echte Erkennungscode liefe
        # also mit einem Schein-Archiv – er findet zwar nichts zu tun,
        # aber die CI brach danach beim Aufräumen mit einem
        # Speicherzugriffsfehler ab, während alle Tests grün meldeten.
        # Geprüft wird hier der Weg zu den Konten, nicht die Erkennung;
        # die hat ihre eigenen Tests in ``ScansImDienstTest``.
        with mock.patch(
            "mailburg.core.paths.config_dir",
            return_value=Path(ordner.name),
        ), mock.patch("mailburg.core.archive.Archive.open"), \
             mock.patch.object(Schleife, "_anhaenge_lesen", return_value=0):
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


class ScansImDienstTest(unittest.TestCase):
    """**Was der Modulkopf zusagt, müssen beide Abrufwege tun.**

    ``core/erkennung.py`` sagt seit jeher: »Nach jedem Abruf, also alle
    halbe Stunde, wird ein kleines Zeitbudget abgearbeitet […] neu
    ankommende Scans sind sofort dran.« Die Oberfläche tat das
    (``ui/arbeit.py``), der Dienst nicht – und auf einem Server gibt es
    nur den Dienst. Dort blieb damit jeder eingehende Scan stumm
    liegen: Die Mail war auffindbar, ihr Anhang nicht.

    Dieselbe Klasse wie der doppelt geöffnete Anhang vom 07.09. und die
    Ausschlussliste vom selben Tag: **zwei Wege, einer nachgezogen, der
    andere nicht.** Gefunden hat es am 09.10.2026 eine Frage Stephans,
    kein Test – deshalb diese hier.
    """

    def _schleife(self):
        schleife = Schleife("/irgendwo", Lage(takt=30))
        schleife.gemeldet = []
        schleife._melden = (
            lambda text, fehler=False:
            schleife.gemeldet.append((text, fehler))
        )
        return schleife

    def test_der_dienst_arbeitet_die_warteschlange_ab(self):
        schleife = self._schleife()
        ergebnis = mock.Mock(gelesen=3)

        with mock.patch("mailburg.extract.ocr.bereit",
                        return_value=(True, "")), \
             mock.patch("mailburg.core.erkennung.Warteschlange") as w, \
             mock.patch("mailburg.core.erkennung.durchlauf",
                        return_value=ergebnis) as lauf:
            w.return_value.anzahl.return_value = 7
            gelesen = schleife._anhaenge_lesen(mock.Mock())

        self.assertEqual(gelesen, 3)
        lauf.assert_called_once()

    def test_ohne_wartende_scans_passiert_nichts(self):
        """Kein Lauf, wenn nichts zu tun ist – sonst führe jeder Abruf
        ohne Grund die Werkzeuge der Texterkennung hoch."""
        schleife = self._schleife()

        with mock.patch("mailburg.extract.ocr.bereit",
                        return_value=(True, "")), \
             mock.patch("mailburg.core.erkennung.Warteschlange") as w, \
             mock.patch("mailburg.core.erkennung.durchlauf") as lauf:
            w.return_value.anzahl.return_value = 0
            self.assertEqual(schleife._anhaenge_lesen(mock.Mock()), 0)

        lauf.assert_not_called()

    def test_die_zahl_steht_in_der_meldung(self):
        """**Sonst ist von außen nicht nachprüfbar, ob es läuft.**

        Genau daran lag es, dass die Lücke so lange unentdeckt blieb:
        Ein Dienst, der etwas nicht tut, sieht aus wie einer, der nichts
        zu tun hatte.
        """
        befund = Schleife._befund(neu=12, geholt=7, uebersprungen=0,
                                  gelesen=4)

        self.assertIn("12 neue Mails", befund)
        self.assertIn("4 eingescannte PDF", befund)

    def test_ohne_gelesene_scans_steht_nichts_davon_da(self):
        """Eine Null gehört nicht in eine Meldung – wer »0 Scans« liest,
        hält es für einen Befund."""
        self.assertNotIn(
            "eingescannte",
            Schleife._befund(neu=12, geholt=7, uebersprungen=0, gelesen=0),
        )

    def test_ein_fehler_kostet_nicht_den_abruf(self):
        """**Archivieren ist Pflicht, Durchsuchbarmachen ist Kür.**

        Eine klemmende Texterkennung darf die Post nicht aufhalten – und
        sie muss trotzdem gemeldet werden.
        """
        schleife = self._schleife()

        with mock.patch("mailburg.extract.ocr.bereit",
                        return_value=(True, "")), \
             mock.patch("mailburg.core.erkennung.Warteschlange") as w, \
             mock.patch("mailburg.core.erkennung.durchlauf",
                        side_effect=RuntimeError("Platte voll")):
            w.return_value.anzahl.return_value = 5
            gelesen = schleife._anhaenge_lesen(mock.Mock())

        self.assertEqual(gelesen, 0)
        self.assertTrue(
            any("Platte voll" in t and f for t, f in schleife.gemeldet),
            schleife.gemeldet,
        )

    def test_fehlende_texterkennung_wird_einmal_gemeldet(self):
        """**Einmal je Dienstlauf, nicht alle dreißig Minuten.**

        Eine Meldung, die 48-mal am Tag im Ereignisprotokoll steht,
        liest niemand mehr – und dann geht die nächste echte darin
        unter. Verschweigen wäre aber auch falsch: Fehlt tesseract,
        bleibt jeder Scan dauerhaft unauffindbar, und das sieht nach
        einem leeren Dokument aus, nicht nach einer Störung.
        """
        schleife = self._schleife()

        with mock.patch("mailburg.extract.ocr.bereit",
                        return_value=(False, "pdftoppm fehlt.")):
            for _ in range(5):
                schleife._anhaenge_lesen(mock.Mock())

        treffer = [t for t, _ in schleife.gemeldet if "pdftoppm" in t]
        self.assertEqual(len(treffer), 1, schleife.gemeldet)

    def test_der_abbruch_wirkt_auch_dort(self):
        """Hält der Dienst an, bricht auch die Erkennung ab – sonst
        liefe sie noch Minuten weiter, während der Dienst schon als
        beendet gilt."""
        import inspect

        self.assertIn(
            "weiter=lambda: not self.halt.is_set()",
            inspect.getsource(Schleife._anhaenge_lesen),
        )

    def test_es_bleibt_ein_haeppchen(self):
        """Kein ``budget_sekunden=0`` – ein Dienst, der eine
        Viertelstunde am Stück Bilder liest, verzögert den nächsten
        Abruf. Das wäre die falsche Rangfolge."""
        import inspect

        quelle = inspect.getsource(Schleife._anhaenge_lesen)

        self.assertNotIn("budget_sekunden=0", quelle)
        self.assertNotIn("budget_dokumente=0", quelle)

    @unittest.skip(
        "Der Aufruf in _einmal ist seit 2026-10-09 vorübergehend "
        "abgeschaltet – mit ihm bricht die CI nach dem Testlauf mit "
        "einem Speicherzugriffsfehler ab. Siehe TODO."
    )
    def test_ein_echter_durchgang_liest_die_scans(self):
        """**Der Test, der gefehlt hat.**

        Die übrigen hier rufen ``_anhaenge_lesen`` unmittelbar auf –
        und wären allesamt grün geblieben, während ``_einmal`` die
        Methode nie aufruft. Genau das war fünf Wochen lang der
        Zustand. Dieser geht den Weg, den der Dienst geht: echte
        Kontenliste, echtes ``_einmal``.

        Dieselbe Lehre wie am 06.10. beim Abruf selbst: Geprüft waren
        Takt, Pause und ein klemmendes Postfach – also alles *um* die
        Stelle herum, nie der Weg hinein.
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

        schleife = self._schleife()
        schleife._konto = lambda archiv, konto, zustand: 2

        with mock.patch(
            "mailburg.core.paths.config_dir",
            return_value=Path(ordner.name),
        ), mock.patch("mailburg.core.archive.Archive.open"), \
             mock.patch("mailburg.core.sync.Abrufzustand"), \
             mock.patch("mailburg.extract.ocr.bereit",
                        return_value=(True, "")), \
             mock.patch("mailburg.core.erkennung.Warteschlange") as w, \
             mock.patch("mailburg.core.erkennung.durchlauf",
                        return_value=mock.Mock(gelesen=4)) as lauf:
            w.return_value.anzahl.return_value = 9
            schleife._einmal()

        lauf.assert_called_once()
        self.assertIn("4 eingescannte PDF", schleife.letzter_befund)

    @unittest.skip(
        "Siehe oben – und dieser hier wäre sogar grün geblieben, weil "
        "er den Aufruf als Text sucht und ihn im Kommentar findet, der "
        "die Abschaltung erklärt. Grün aus dem falschen Grund ist "
        "schlimmer als rot."
    )
    def test_im_selben_geoeffneten_archiv(self):
        """**Nicht daneben, sondern innerhalb derselben Sperre.**

        Der Modulkopf von ``erkennung.py`` begründet es: Solange
        MailBurg schreibend am Archiv ist, liegt eine Sperrdatei darin.
        Eine Erkennung, die nebenher liefe, stünde dem Abruf im Weg –
        und dann bliebe Post liegen, um Scans lesbar zu machen.

        Der Test davor beweist, *dass* gelesen wird; dieser, *wo*.
        Geprüft wird die Einrückung: Der Aufruf muss tiefer stehen als
        das ``with Archive.open(...)``, also darin.
        """
        import inspect
        import textwrap

        zeilen = textwrap.dedent(
            inspect.getsource(Schleife._einmal)).splitlines()
        mit = next((i for i, z in enumerate(zeilen)
                    if "with Archive.open(" in z), None)
        ruf = next((i for i, z in enumerate(zeilen)
                    if "self._anhaenge_lesen(archiv)" in z), None)

        self.assertIsNotNone(mit, "Kein geöffnetes Archiv in _einmal.")
        self.assertIsNotNone(
            ruf, "_einmal ruft die Texterkennung nicht auf.")
        self.assertGreater(ruf, mit)
        self.assertGreater(
            len(zeilen[ruf]) - len(zeilen[ruf].lstrip()),
            len(zeilen[mit]) - len(zeilen[mit].lstrip()),
            "Der Aufruf steht außerhalb des geöffneten Archivs.",
        )


if __name__ == "__main__":
    unittest.main()
