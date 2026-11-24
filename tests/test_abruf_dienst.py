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

        # **Die echte Bilanzklasse, kein Mock.** Ein ``Mock(neu=3)``
        # liefert für jedes weitere Feld wieder einen Mock, und
        # ``int()`` darauf wirft – der Fehler landete dann im
        # Auffangnetz von ``_konto``, und der Test las ein
        # »übersprungen«, wo keines war. Eine Attrappe, die nicht
        # aussieht wie die Wirklichkeit, misst etwas anderes.
        from mailburg.core.importer import Statistik

        with mock.patch(
            "mailburg.core.accounts.passwort_holen", return_value="geheim"
        ), mock.patch("mailburg.sources.quelle_fuer") as quelle_fuer, \
                mock.patch(
                    "mailburg.core.importer.importieren",
                    return_value=Statistik(neu=3)):
            bilanz = schleife._konto(mock.Mock(), konto, zustand)

        self.assertEqual(bilanz[0], 3)
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
        # ``_konto`` liefert seit dem 2026-11-04 (neu, mit_anhangstext,
        # eingescannt) statt einer blanken Zahl.
        schleife._konto = (
            lambda archiv, konto, zustand:
                geholt.append(konto.name) or (0, 0, 0)
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

    def test_der_anhangstext_steht_auch_in_der_meldung(self):
        """**Die Zahl, die seit dem 2026-10-09 gefehlt hat.**

        An jenem Tag kam über den Dienst eine Mail mit einem PDF an,
        das vollständig im Archiv liegt und aus dem sich bis heute kein
        Wort finden lässt – während derselbe Server von Hand sauber
        Anhangstext erzeugt. Ob der *Dienst* das tut, war von außen
        nicht nachprüfbar: Er meldete nur, wie viele Mails er geholt
        hat.
        """
        befund = Schleife._befund(neu=12, geholt=7, uebersprungen=0,
                                  mit_text=3)

        self.assertIn("Anhangstext aus 3 Mails", befund)

    def test_ohne_anhangstext_steht_das_ausdruecklich_da(self):
        """**Hier gehört die Null hin, und das ist die Ausnahme.**

        Sonst gilt: Eine Null ist kein Befund. Aber »neue Post
        angekommen, kein Anhangstext erzeugt« ist genau der Zustand,
        den vier Wochen lang niemand bemerkt hat – er sieht aus wie
        ein Tag ohne Anhänge.
        """
        befund = Schleife._befund(neu=12, geholt=7, uebersprungen=0,
                                  mit_text=0)

        self.assertIn("Kein Anhangstext erzeugt", befund)

    def test_ohne_neue_post_schweigt_die_zahl(self):
        """»0 von 0« wäre Rauschen in jeder halben Stunde."""
        befund = Schleife._befund(neu=0, geholt=7, uebersprungen=0,
                                  mit_text=0)

        self.assertNotIn("Anhangstext", befund)

    def test_wartende_scans_werden_genannt(self):
        """Ein PDF ohne Textebene ist noch nicht durchsuchbar – wer das
        nicht weiß, hält den Abruf für vollständig erledigt."""
        befund = Schleife._befund(neu=12, geholt=7, uebersprungen=0,
                                  mit_text=3, eingescannt=2)

        self.assertIn("2 PDF ohne Textebene", befund)

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
        schleife._konto = lambda archiv, konto, zustand: (2, 0, 0)

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

    def test_der_anhangstext_findet_den_weg_bis_in_die_meldung(self):
        """**Der Weg hinein, nicht nur die Formulierung am Ende.**

        Die Tests zu ``_befund`` prüfen, wie die Zahl *klingt*, wenn
        sie ankommt. Dieser prüft, dass sie ankommt: aus der echten
        ``Statistik`` von ``importieren`` über ``_konto`` und
        ``_einmal`` bis in ``letzter_befund``.

        Dieselbe Lehre wie am 06.10. und am 09.10.: Geprüft war jedes
        Mal alles *um* die Stelle herum. Eine Zahl, die unterwegs
        verlorengeht, sieht am Ende aus wie eine Null – und eine Null
        liest sich hier wie »heute kam nichts mit Anhang«.
        """
        import tempfile
        from pathlib import Path

        from mailburg.core.accounts import Konto, Kontenliste
        from mailburg.core.importer import Statistik

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        liste = Kontenliste(Path(ordner.name) / "konten.json")
        liste.konten = [
            Konto(name="buero", server="imap.example.org",
                  benutzer="buero@example.org"),
        ]
        liste.speichern()

        schleife = self._schleife()
        bilanz = Statistik(neu=5, mit_anhangstext=3)
        # ``eingescannt`` ist eine abgeleitete Eigenschaft und liest
        # genau diesen Schlüssel (importer.py). Den Namen geraten zu
        # haben hat diesen Test beim ersten Lauf rot gemacht – zu
        # Recht.
        bilanz.anhaenge["pdf:eingescannt"] = 2

        with mock.patch(
            "mailburg.core.paths.config_dir",
            return_value=Path(ordner.name),
        ), mock.patch("mailburg.core.archive.Archive.open"), \
             mock.patch("mailburg.core.sync.Abrufzustand"), \
             mock.patch("mailburg.core.accounts.passwort_holen",
                        return_value="geheim"), \
             mock.patch("mailburg.sources.quelle_fuer"), \
             mock.patch("mailburg.core.importer.importieren",
                        return_value=bilanz), \
             mock.patch.object(Schleife, "_anhaenge_lesen", return_value=0):
            schleife._einmal()

        self.assertIn("Anhangstext aus 3 Mails", schleife.letzter_befund)
        self.assertIn("2 PDF ohne Textebene", schleife.letzter_befund)

    def test_und_die_null_kommt_genauso_an(self):
        """Der Fall vom 2026-10-09: Post kam, Anhangstext nicht."""
        import tempfile
        from pathlib import Path

        from mailburg.core.accounts import Konto, Kontenliste
        from mailburg.core.importer import Statistik

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        liste = Kontenliste(Path(ordner.name) / "konten.json")
        liste.konten = [
            Konto(name="buero", server="imap.example.org",
                  benutzer="buero@example.org"),
        ]
        liste.speichern()

        schleife = self._schleife()

        with mock.patch(
            "mailburg.core.paths.config_dir",
            return_value=Path(ordner.name),
        ), mock.patch("mailburg.core.archive.Archive.open"), \
             mock.patch("mailburg.core.sync.Abrufzustand"), \
             mock.patch("mailburg.core.accounts.passwort_holen",
                        return_value="geheim"), \
             mock.patch("mailburg.sources.quelle_fuer"), \
             mock.patch("mailburg.core.importer.importieren",
                        return_value=Statistik(neu=1, mit_anhangstext=0)), \
             mock.patch.object(Schleife, "_anhaenge_lesen", return_value=0):
            schleife._einmal()

        self.assertIn("Kein Anhangstext erzeugt", schleife.letzter_befund)

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


class VorwaermenTest(unittest.TestCase):
    """Einmal am Tag den Suchindex anfassen, bevor es jemand tut.

    **Verschiebt eine Wartezeit, behebt sie nicht.** Der erste
    Seitenaufruf an einem Arbeitstag dauert auf dem Firmenserver eine
    halbe Minute (592.000 Mails, 7,26 GB Index); woran es liegt, ist
    offen. Vier Erklärungen sind gemessen und widerlegt.

    Die Dauer steht deshalb im Ereignisprotokoll – ein Vorwärmen, das
    die Beobachtung verdeckt, wäre ein schlechter Tausch.
    """

    def _schleife(self, **lage):
        schleife = Schleife("/irgendwo", Lage(takt=30, **lage))
        schleife.gemeldet = []
        schleife._melden = (
            lambda text, fehler=False:
            schleife.gemeldet.append((text, fehler))
        )
        return schleife

    def _morgens(self, stunde=7, tag=15):
        from datetime import datetime as dt

        return dt(2026, 12, tag, stunde, 0)

    def test_ohne_uhrzeit_passiert_nichts(self):
        """Die Vorgabe. Wer nichts einstellt, bekommt nichts."""
        schleife = self._schleife()

        with mock.patch("mailburg.core.archive.Archive.open") as oeffnen:
            self.assertFalse(
                schleife._vielleicht_vorwaermen(self._morgens()))

        oeffnen.assert_not_called()

    def test_vor_der_uhrzeit_passiert_nichts(self):
        from datetime import time as uhrzeit

        schleife = self._schleife(vorwaermen=uhrzeit(6, 0))

        with mock.patch("mailburg.core.archive.Archive.open") as oeffnen:
            self.assertFalse(
                schleife._vielleicht_vorwaermen(self._morgens(stunde=5)))

        oeffnen.assert_not_called()

    def test_danach_wird_einmal_gewaermt(self):
        from datetime import time as uhrzeit

        schleife = self._schleife(vorwaermen=uhrzeit(6, 0))

        with mock.patch("mailburg.core.archive.Archive.open") as oeffnen:
            self.assertTrue(
                schleife._vielleicht_vorwaermen(self._morgens()))

        oeffnen.assert_called_once()
        archiv = oeffnen.return_value.__enter__.return_value
        archiv.index.count.assert_called_once_with("")
        archiv.index.search.assert_called_once()

    def test_aber_nur_einmal_am_tag(self):
        """**Der Takt ist halbstündlich.** Ohne diese Sperre liefe das
        Vorwärmen von sechs Uhr bis Mitternacht sechsunddreißigmal –
        und schriebe ebenso viele Zeilen ins Protokoll."""
        from datetime import time as uhrzeit

        schleife = self._schleife(vorwaermen=uhrzeit(6, 0))

        with mock.patch("mailburg.core.archive.Archive.open") as oeffnen:
            schleife._vielleicht_vorwaermen(self._morgens(stunde=6))
            schleife._vielleicht_vorwaermen(self._morgens(stunde=7))
            schleife._vielleicht_vorwaermen(self._morgens(stunde=15))

        self.assertEqual(oeffnen.call_count, 1)

    def test_am_naechsten_tag_wieder(self):
        """Ein Haken müsste um Mitternacht zurückgesetzt werden – und
        dafür bräuchte es wieder jemanden, der daran denkt."""
        from datetime import time as uhrzeit

        schleife = self._schleife(vorwaermen=uhrzeit(6, 0))

        with mock.patch("mailburg.core.archive.Archive.open") as oeffnen:
            schleife._vielleicht_vorwaermen(self._morgens(tag=15))
            schleife._vielleicht_vorwaermen(self._morgens(tag=16))

        self.assertEqual(oeffnen.call_count, 2)

    def test_die_dauer_steht_in_der_meldung(self):
        """**Sonst verdeckt das Vorwärmen die einzige Spur.**

        Ohne Zahl wäre die Wartezeit weg – und mit ihr die
        Beobachtung, aus der sich die Ursache noch finden ließe. Wird
        aus einer halben Minute eine ganze, soll das dastehen.
        """
        from datetime import time as uhrzeit

        schleife = self._schleife(vorwaermen=uhrzeit(6, 0))

        with mock.patch("mailburg.core.archive.Archive.open"):
            schleife._vielleicht_vorwaermen(self._morgens())

        texte = [t for t, _ in schleife.gemeldet]
        self.assertTrue(
            any("vorgewärmt in" in t and "Sekunden" in t for t in texte),
            schleife.gemeldet,
        )

    def test_ein_fehler_haelt_den_dienst_nicht_auf(self):
        """**Vorwärmen ist Kür.** Ein Archiv, das gerade nicht
        aufgeht, ist kein Grund, keine Post mehr zu holen."""
        from datetime import time as uhrzeit

        schleife = self._schleife(vorwaermen=uhrzeit(6, 0))

        with mock.patch("mailburg.core.archive.Archive.open",
                        side_effect=OSError("Platte weg")):
            self.assertFalse(
                schleife._vielleicht_vorwaermen(self._morgens()))

        self.assertTrue(
            any("Vorwärmen fehlgeschlagen" in t and f
                for t, f in schleife.gemeldet),
            schleife.gemeldet,
        )

    def test_und_wird_nicht_in_jedem_takt_wiederholt(self):
        """Achtundvierzig Fehlermeldungen am Tag statt einer wären
        genau die Tapete, hinter der die nächste echte untergeht."""
        from datetime import time as uhrzeit

        schleife = self._schleife(vorwaermen=uhrzeit(6, 0))

        with mock.patch("mailburg.core.archive.Archive.open",
                        side_effect=OSError("Platte weg")) as oeffnen:
            schleife._vielleicht_vorwaermen(self._morgens(stunde=6))
            schleife._vielleicht_vorwaermen(self._morgens(stunde=7))

        self.assertEqual(oeffnen.call_count, 1)

    def test_die_uhrzeit_kommt_aus_der_umgebung(self):
        from datetime import time as uhrzeit

        with mock.patch.dict(os.environ, {"MAILBURG_VORWAERMEN": "06:30"}):
            self.assertEqual(
                Lage.aus_umgebung().vorwaermen, uhrzeit(6, 30))

    def test_ein_tippfehler_schaltet_es_ab_statt_zu_krachen(self):
        """Dieselbe Haltung wie bei der Pause: Was sich nicht lesen
        lässt, gilt als nicht eingestellt – es darf nicht den Dienst
        anhalten."""
        for unsinn in ("sechs", "25:00", "6", "-"):
            with self.subTest(unsinn=unsinn), \
                    mock.patch.dict(os.environ,
                                    {"MAILBURG_VORWAERMEN": unsinn}):
                self.assertIsNone(Lage.aus_umgebung().vorwaermen)

    def test_es_steht_vor_der_pausenpruefung(self):
        """**Sonst käme es auf einem Server mit nächtlicher Sicherung
        nie dran.** Die Ruhe reicht dort bis in den frühen Morgen, und
        genau dann soll vorgewärmt werden – hinter dem ``continue``
        wäre der Aufruf unerreichbar.
        """
        import inspect
        import textwrap

        zeilen = textwrap.dedent(
            inspect.getsource(Schleife._schleife)).splitlines()
        waermen = next((i for i, z in enumerate(zeilen)
                        if "_vielleicht_vorwaermen()" in z), None)
        pause = next((i for i, z in enumerate(zeilen)
                      if "self.lage.pausiert()" in z), None)

        self.assertIsNotNone(waermen, "Die Schleife wärmt nie vor.")
        self.assertIsNotNone(pause)
        self.assertLess(waermen, pause)


if __name__ == "__main__":
    unittest.main()
