"""Die Rechteverwaltung – Kern und Oberfläche.

Der Kern ist das Wichtigere: Eine Regel, die nur der Dialog kennt, gilt
für die Kommandozeile nicht und für den Server, der später dazukommt,
auch nicht.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mailburg.core.archive import Archive, Mode
from mailburg.core.benutzer import Benutzer, BenutzerFehler, Benutzerliste

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None


class LetzterVerwalterTest(unittest.TestCase):
    """Wer verwaltet, darf sich nicht selbst aussperren.

    Sonst hat das Archiv niemanden mehr, der Zugänge vergeben kann – und
    das ließe sich nur noch von der Kommandozeile aus reparieren. Wer am
    Server sitzt, kann das; wer im Browser vor einer Oberfläche steht,
    die ihn gerade ausgesperrt hat, nicht.
    """

    def _mit_verwalter(self) -> Benutzerliste:
        liste = Benutzerliste()
        chef = Benutzer("chef", verwalter=True)
        chef.passwort_setzen("ein-langes-passwort")
        liste.hinzufuegen(chef)
        return liste

    def test_das_recht_abgeben_geht_nicht(self):
        vorher = self._mit_verwalter()
        nachher = Benutzerliste.aus_daten(vorher.als_daten())
        nachher.finden("chef").verwalter = False

        with self.assertRaises(BenutzerFehler):
            nachher.pruefen_gegen(vorher)

    def test_sich_selbst_stilllegen_geht_nicht(self):
        vorher = self._mit_verwalter()
        nachher = Benutzerliste.aus_daten(vorher.als_daten())
        nachher.finden("chef").aktiv = False

        with self.assertRaises(BenutzerFehler):
            nachher.pruefen_gegen(vorher)

    def test_sich_selbst_entfernen_geht_nicht(self):
        vorher = self._mit_verwalter()
        nachher = Benutzerliste.aus_daten(vorher.als_daten())
        nachher.entfernen("chef")

        with self.assertRaises(BenutzerFehler):
            nachher.pruefen_gegen(vorher)

    def test_mit_einem_nachfolger_geht_es(self):
        vorher = self._mit_verwalter()
        nachher = Benutzerliste.aus_daten(vorher.als_daten())
        nachher.hinzufuegen(Benutzer("neu", verwalter=True))
        nachher.finden("chef").verwalter = False

        nachher.pruefen_gegen(vorher)  # wirft nicht

    def test_ein_stillgelegter_nachfolger_zaehlt_nicht(self):
        """Er kann sich ja nicht anmelden."""
        vorher = self._mit_verwalter()
        nachher = Benutzerliste.aus_daten(vorher.als_daten())
        nachher.hinzufuegen(Benutzer("neu", verwalter=True, aktiv=False))
        nachher.finden("chef").verwalter = False

        with self.assertRaises(BenutzerFehler):
            nachher.pruefen_gegen(vorher)

    def test_ein_archiv_ohne_verwalter_darf_eines_bleiben(self):
        """Sonst käme man nie zum ersten."""
        Benutzerliste().pruefen_gegen(Benutzerliste())  # wirft nicht

    def test_die_regel_gilt_auch_am_archiv(self):
        """Nicht nur im Dialog – sonst umginge sie jeder andere Weg."""
        with tempfile.TemporaryDirectory() as ordner:
            wo = Path(ordner) / "Archiv"
            with Archive.create(wo, name="P", mode=Mode.GESCHAEFTLICH) as archiv:
                archiv.benutzer_setzen(self._mit_verwalter(), actor="chef")

                entrechtet = archiv.benutzer
                entrechtet.finden("chef").verwalter = False

                with self.assertRaises(BenutzerFehler):
                    archiv.benutzer_setzen(entrechtet, actor="chef")

                # Und der Zustand auf der Platte ist unverändert.
                self.assertTrue(archiv.benutzer.finden("chef").verwalter)


@unittest.skipIf(QApplication is None, "PySide6 fehlt")
class DialogTest(unittest.TestCase):
    """Was der Dialog anzeigt – der Teil, der über Bedienbarkeit entscheidet."""

    @classmethod
    def setUpClass(cls):
        cls.anwendung = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        self.archiv = Archive.create(
            self.wo, name="Probe", mode=Mode.GESCHAEFTLICH
        )
        self.addCleanup(self.archiv.close)

    def _dialog(self):
        from mailburg.ui.zugaenge import Zugangsdialog

        dialog = Zugangsdialog(archiv=self.archiv)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_ein_leeres_archiv_zeigt_keine_zugaenge(self):
        dialog = self._dialog()

        self.assertEqual(dialog.leute.count(), 0)
        self.assertFalse(dialog.rechte_seite.isEnabled())

    def test_wer_nichts_sieht_bekommt_es_gesagt(self):
        """Der häufigste Fehler beim Anlegen – und er fällt sonst nicht auf."""
        liste = self.archiv.benutzer
        liste.hinzufuegen(Benutzer("anna"))
        self.archiv.benutzer_setzen(liste)

        dialog = self._dialog()
        dialog.leute.setCurrentRow(0)

        self.assertIn("Sieht nichts", dialog.folge.text())

    def test_wer_alles_sieht_bekommt_es_auch_gesagt(self):
        liste = self.archiv.benutzer
        liste.hinzufuegen(Benutzer("chef", alle_postfaecher=True))
        self.archiv.benutzer_setzen(liste)

        dialog = self._dialog()
        dialog.leute.setCurrentRow(0)

        self.assertIn("alle Postfächer", dialog.folge.text())
        # Einzelne Postfächer anzukreuzen wäre dann sinnlos.
        self.assertFalse(dialog.postfachkasten.isEnabled())

    def test_ein_stillgelegter_zugang_ist_erkennbar(self):
        liste = self.archiv.benutzer
        liste.hinzufuegen(Benutzer("alt", aktiv=False))
        self.archiv.benutzer_setzen(liste)

        dialog = self._dialog()

        self.assertIn("stillgelegt", dialog.leute.item(0).text())
        dialog.leute.setCurrentRow(0)
        self.assertIn("Stillgelegt", dialog.folge.text())
        self.assertEqual(dialog.stilllegen.text(), "Wieder zulassen")

    def test_ein_recht_wird_uebernommen(self):
        liste = self.archiv.benutzer
        liste.hinzufuegen(Benutzer("anna"))
        self.archiv.benutzer_setzen(liste)

        dialog = self._dialog()
        dialog.leute.setCurrentRow(0)
        dialog.sieht_alles.setChecked(True)

        self.assertTrue(dialog._gewaehlt().alle_postfaecher)
        self.assertIn("alle Postfächer", dialog.folge.text())

    def test_das_laden_veraendert_nichts(self):
        """Ein Dialog, der beim Öffnen etwas umstellt, ist eine Falle."""
        liste = self.archiv.benutzer
        liste.hinzufuegen(Benutzer("anna", postfaecher=["buchhaltung"]))
        liste.hinzufuegen(Benutzer("chef", alle_postfaecher=True))
        self.archiv.benutzer_setzen(liste)
        vorher = self.archiv.benutzer.als_daten()

        dialog = self._dialog()
        dialog.leute.setCurrentRow(0)
        dialog.leute.setCurrentRow(1)
        dialog.leute.setCurrentRow(0)

        self.assertEqual(dialog.liste.als_daten(), vorher)

    def test_ein_postfach_aus_dem_archiv_steht_zur_wahl(self):
        self.archiv.add(
            b"From: a@example.org\r\nSubject: Test\r\n\r\nText\r\n",
            account="buchhaltung", folder="INBOX",
        )
        liste = self.archiv.benutzer
        liste.hinzufuegen(Benutzer("anna"))
        self.archiv.benutzer_setzen(liste)

        dialog = self._dialog()
        dialog.leute.setCurrentRow(0)

        self.assertEqual(
            [dialog.kaesten.item(i).text() for i in range(dialog.kaesten.count())],
            ["buchhaltung"],
        )


if __name__ == "__main__":
    unittest.main()
