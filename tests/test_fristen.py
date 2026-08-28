"""Die jährliche Nachfrage nach abgelaufenen Fristen.

**Einmal im Jahr, nicht bei jedem Start.** Fristen laufen zum
Jahresende ab; eine Meldung, die ab dem 1. Januar bei jedem Öffnen
erscheint, wird nach der dritten Wiederholung weggeklickt, ohne gelesen
zu werden – und dann auch beim vierten Mal, wenn es darauf ankäme.

Der 1. Mai als Stichtag geht auf Stephan zurück (2026-08-28): Im Januar
steckt man im Jahresabschluss, und ob eine Betriebsprüfung den Ablauf
hemmt, weiß man im Frühjahr eher.
"""

from __future__ import annotations

import pathlib
import tempfile
import unittest
from datetime import date
from unittest import mock

from mailburg.core.archive import Archive
from mailburg.core.retention import Category, Jurisdiction, Policy


def _mail(betreff: str, jahr: int, kennung: str) -> bytes:
    return (
        f"From: post@example.org\r\n"
        f"To: ich@example.net\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: Mon, 14 Jan {jahr} 09:00:00 +0100\r\n"
        f"Message-ID: <{kennung}@example.org>\r\n"
        f"\r\n"
        f"Inhalt\r\n"
    ).encode()


class StichtagTest(unittest.TestCase):
    """Ab dem Stichtag, und dann Ruhe bis zum nächsten Jahr."""

    def setUp(self) -> None:
        self.regel = Policy(jurisdiction=Jurisdiction.DE)

    def test_vor_dem_stichtag_wird_nicht_gefragt(self) -> None:
        self.assertFalse(self.regel.review_due(None, date(2026, 4, 30)))

    def test_am_stichtag_schon(self) -> None:
        self.assertTrue(self.regel.review_due(None, date(2026, 5, 1)))

    def test_im_selben_jahr_nur_einmal(self) -> None:
        """Sonst klickt man sie weg, ohne sie zu lesen."""
        self.assertFalse(self.regel.review_due(2026, date(2026, 12, 31)))

    def test_im_naechsten_jahr_wieder(self) -> None:
        self.assertTrue(self.regel.review_due(2026, date(2027, 5, 1)))

    def test_der_stichtag_laesst_sich_verlegen(self) -> None:
        regel = Policy(review_month=1, review_day=15)
        self.assertTrue(regel.review_due(None, date(2026, 1, 15)))
        self.assertFalse(regel.review_due(None, date(2026, 1, 14)))


class FaelligeTest(unittest.TestCase):
    """Was im Geschäftsarchiv seine Frist hinter sich hat.

    Deutsches Recht: Handelsbriefe sechs Jahre, Buchungsbelege acht,
    gerechnet ab dem Ende des Kalenderjahres.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "Geschaeftsarchiv"
        Archive.create(self.pfad, mode="geschaeftlich").close()

        with Archive.open(self.pfad) as archiv:
            for jahr, kategorie, kennung in (
                (2015, Category.HANDELSBRIEF, "hb2015"),
                (2015, Category.BUCHUNGSBELEG, "bb2015"),
                (2019, Category.HANDELSBRIEF, "hb2019"),
                (2022, Category.BUCHUNGSBELEG, "bb2022"),
                (2015, Category.PRIVAT, "pr2015"),
            ):
                eintrag = archiv.add(
                    _mail(f"{kategorie.value} {jahr}", jahr, kennung),
                    account="firma", folder="INBOX",
                )
                archiv.classify(eintrag.hash, kategorie)

    def _betreffe(self, heute: date) -> set[str]:
        with Archive.open(self.pfad, exclusive=False) as archiv:
            return {t.subject for t in archiv.faellige(today=heute)}

    def test_abgelaufene_werden_gefunden(self) -> None:
        betreffe = self._betreffe(date(2026, 5, 1))

        self.assertIn("handelsbrief 2015", betreffe)  # 2015 + 6 = 2021
        self.assertIn("buchungsbeleg 2015", betreffe)  # 2015 + 8 = 2023

    def test_laufende_bleiben_aussen_vor(self) -> None:
        betreffe = self._betreffe(date(2026, 5, 1))

        self.assertNotIn("buchungsbeleg 2022", betreffe)  # bis Ende 2030
        # Der Handelsbrief von 2019 lief bis Ende 2025 - am 1. Mai 2026
        # ist er zu Recht fällig. Hier stand zuerst das Gegenteil; der
        # Test war falsch, nicht die Rechnung.
        self.assertIn("handelsbrief 2019", betreffe)

    def test_privates_taucht_nie_auf(self) -> None:
        """Ohne Frist gibt es nichts, was ablaufen könnte."""
        self.assertNotIn("privat 2015", self._betreffe(date(2026, 5, 1)))

    def test_die_grenze_verschiebt_sich_mit_dem_jahr(self) -> None:
        frueh = self._betreffe(date(2021, 5, 1))
        spaet = self._betreffe(date(2026, 5, 1))

        self.assertLess(len(frueh), len(spaet))


class AlteTest(unittest.TestCase):
    """Im Privatarchiv gibt es keine Fristen – nur Alter.

    Und Alter ist dort ein schlechter Ratgeber: Die Mail vom
    verstorbenen Vater aus 2012 ist mehr wert als die von gestern.
    Deshalb heißt die Methode ``alte`` und nicht ``faellige``.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "Privatarchiv"
        Archive.create(self.pfad, mode="privat").close()

        with Archive.open(self.pfad) as archiv:
            for jahr in (2012, 2018, 2025):
                archiv.add(_mail(f"Post {jahr}", jahr, f"p{jahr}"),
                           account="privat", folder="INBOX")

    def test_die_vorgabe_sind_zehn_jahre(self) -> None:
        """Nicht sechs – das ist die Handelsbrieffrist.

        Post von vor sechs Jahren ist oft noch in Gebrauch:
        Versicherungspolicen, Garantien, Kaufbelege. Was zehn Jahre alt
        ist, ist unstrittig alt.
        """
        from mailburg.core.archive import ALT_AB_JAHREN

        self.assertEqual(ALT_AB_JAHREN, 10)

    def test_nach_alter_ausgewaehlt(self) -> None:
        with Archive.open(self.pfad, exclusive=False) as archiv:
            alt = archiv.alte(jahre=6, today=date(2026, 5, 1))

        self.assertEqual({t.subject for t in alt}, {"Post 2012", "Post 2018"})

    def test_die_grenze_ist_einstellbar(self) -> None:
        with Archive.open(self.pfad, exclusive=False) as archiv:
            alt = archiv.alte(jahre=12, today=date(2026, 5, 1))

        self.assertEqual({t.subject for t in alt}, {"Post 2012"})


class MerkerTest(unittest.TestCase):
    """Wann zuletzt gefragt wurde, steht in den Programmeinstellungen.

    Nicht im Archiv: »Wann habe ich zuletzt gefragt« ist keine
    Eigenschaft des Archivs, sondern eine des Anwenders. Und ein Archiv,
    das beim bloßen Ansehen verändert wird, wäre bei einem Programm mit
    Hash-Kette die falsche Gewohnheit.
    """

    def test_nichts_gemerkt_heisst_noch_nie_gefragt(self) -> None:
        from mailburg.core import nachfrage as fristen

        with mock.patch("mailburg.ui.app.gemerktes", return_value={}):
            self.assertIsNone(fristen.zuletzt_gefragt("abc"))

    def test_vermerken_und_wiederfinden(self) -> None:
        from mailburg.core import nachfrage as fristen

        stand: dict = {}

        def merken(schluessel, wert):
            stand[schluessel] = wert

        with mock.patch("mailburg.ui.app.gemerktes", side_effect=lambda: stand):
            with mock.patch("mailburg.ui.app.merken_unter", side_effect=merken):
                fristen.gefragt_vermerken("abc", 2026)
                self.assertEqual(fristen.zuletzt_gefragt("abc"), 2026)

    def test_zwei_archive_getrennt(self) -> None:
        """Sonst verstummt das zweite Archiv, weil das erste gefragt wurde."""
        from mailburg.core import nachfrage as fristen

        stand: dict = {}

        def merken(schluessel, wert):
            stand[schluessel] = wert

        with mock.patch("mailburg.ui.app.gemerktes", side_effect=lambda: stand):
            with mock.patch("mailburg.ui.app.merken_unter", side_effect=merken):
                fristen.gefragt_vermerken("privat", 2026)
                self.assertIsNone(fristen.zuletzt_gefragt("geschaeftlich"))

    def test_kaputte_einstellung_wirft_nicht(self) -> None:
        """Eine von Hand verhunzte Datei darf das Programm nicht aufhalten."""
        from mailburg.core import nachfrage as fristen

        with mock.patch("mailburg.ui.app.gemerktes",
                        return_value={fristen.SCHLUESSEL: "unsinn"}):
            self.assertIsNone(fristen.zuletzt_gefragt("abc"))


class DialogTest(unittest.TestCase):
    """Zwei Archivarten, zwei Töne."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            raise unittest.SkipTest("PySide6 fehlt")
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, modus: str):
        from mailburg.ui.fristen import Fristendialog

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        pfad = pathlib.Path(ordner.name) / "A"
        Archive.create(pfad, mode=modus).close()
        with Archive.open(pfad) as archiv:
            archiv.add(_mail("Alt", 2012, "alt"), account="a", folder="INBOX")

        archiv = Archive.open(pfad, exclusive=False)
        self.addCleanup(archiv.close)
        treffer = archiv.index.search("", limit=10)
        return Fristendialog(archiv, treffer)

    def _texte(self, dialog) -> str:
        from PySide6.QtWidgets import QLabel

        return " ".join(k.text() for k in dialog.findChildren(QLabel))

    def test_geschaeftlich_nennt_die_pflicht(self) -> None:
        text = self._texte(self._dialog("geschaeftlich"))

        self.assertIn("DSGVO", text)
        self.assertIn("Aufbewahrungsfrist", text)
        self.assertIn("Steuerberater", text)

    def test_privat_nennt_ausdruecklich_keine_pflicht(self) -> None:
        """Sonst liest sich ein Angebot wie eine Aufforderung."""
        text = self._texte(self._dialog("privat"))

        self.assertIn("kein Grund zum Löschen", text)
        self.assertIn("behalten", text)
        self.assertNotIn("DSGVO", text)

    def test_beide_sagen_dass_nichts_von_selbst_geschieht(self) -> None:
        for modus in ("geschaeftlich", "privat"):
            with self.subTest(modus=modus):
                text = self._texte(self._dialog(modus))
                self.assertIn("einmal im Jahr", text)

    def test_ansehen_ist_die_vorgabe_aber_nicht_das_loeschen(self) -> None:
        """Es gibt keinen Knopf, der etwas entfernt – bewusst."""
        from PySide6.QtWidgets import QPushButton

        dialog = self._dialog("geschaeftlich")
        beschriftungen = {k.text() for k in dialog.findChildren(QPushButton)}

        self.assertIn("Ansehen", beschriftungen)
        for wort in ("Löschen", "Entfernen", "Alle löschen"):
            self.assertNotIn(wort, beschriftungen)


if __name__ == "__main__":
    unittest.main()
