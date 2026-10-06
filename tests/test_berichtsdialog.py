"""Der Dialog, in dem der Tagesbericht eingestellt wird.

Geprüft wird vor allem die **Rundreise**: Was aus den Feldern
herauskommt, muss dasselbe sein, was ``bericht.Lage.aus_umgebung()``
daraus wieder liest. Laufen die beiden auseinander, stellt der Verwalter
etwas ein, das der Dienst anders versteht – und merkt es erst, wenn die
Mail ausbleibt oder zur falschen Zeit kommt.
"""

from __future__ import annotations

import os
import unittest
from datetime import time as uhrzeit
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

from mailburg.core import bericht


@unittest.skipIf(QApplication is None, "PySide6 ist nicht installiert")
class BerichtsdialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, lage=None):
        from mailburg.ui.berichtsdialog import Berichtsdialog

        return Berichtsdialog(lage or bericht.Lage())

    def test_die_felder_stehen_auf_dem_bisherigen_stand(self):
        dialog = self._dialog(bericht.Lage(
            an="chef@example.org", zeit=uhrzeit(6, 30), takt_tage=7,
            smtp="mail.example.org", anschluss=465,
            von="archiv@example.org", benutzer="archiv",
        ))

        self.assertEqual(dialog.an.text(), "chef@example.org")
        self.assertEqual(dialog.smtp.text(), "mail.example.org:465")
        self.assertEqual(dialog.takt.currentData(), 7)
        self.assertEqual(dialog.uhr.time().hour(), 6)

    def test_die_rundreise_haelt(self):
        """**Der eigentliche Test.** Was der Dialog schreibt, muss der
        Dienst genauso wieder lesen."""
        dialog = self._dialog()
        dialog.an.setText("chef@example.org")
        dialog.smtp.setText("mail.example.org:465")
        dialog.von.setText("archiv@example.org")
        dialog.benutzer.setText("archiv")
        dialog.takt.setCurrentIndex(dialog.takt.findData(14))
        from PySide6.QtCore import QTime

        dialog.uhr.setTime(QTime(6, 45))

        neu, _ = dialog.ergebnis()

        with mock.patch.dict(os.environ, neu.als_variablen()):
            wieder = bericht.Lage.aus_umgebung()

        self.assertEqual(wieder.an, "chef@example.org")
        self.assertEqual(wieder.smtp, "mail.example.org")
        self.assertEqual(wieder.anschluss, 465)
        self.assertEqual(wieder.von, "archiv@example.org")
        self.assertEqual(wieder.zeit, uhrzeit(6, 45))
        self.assertEqual(wieder.takt_tage, 14)
        self.assertTrue(wieder.eingerichtet)

    def test_das_passwort_kommt_getrennt_zurueck(self):
        """Es geht in den Tresor, nicht in die Registry – also darf es
        auch nicht unter den Variablen auftauchen."""
        dialog = self._dialog()
        dialog.passwort.setText("geheim")

        neu, passwort = dialog.ergebnis()

        self.assertEqual(passwort, "geheim")
        self.assertNotIn("geheim", str(neu.als_variablen()))

    def test_ein_leeres_passwortfeld_laesst_den_tresor_in_ruhe(self):
        """Sonst löschte jedes Öffnen-und-Bestätigen das hinterlegte
        Passwort."""
        _, passwort = self._dialog().ergebnis()

        self.assertEqual(passwort, "")

    def test_die_takte_kommen_aus_dem_kern(self):
        """Damit Fenster und Doku nicht auseinanderlaufen."""
        dialog = self._dialog()

        im_feld = [dialog.takt.itemData(i) for i in range(dialog.takt.count())]
        self.assertEqual(im_feld, [t for _, t in bericht.TAKTE])



@unittest.skipIf(QApplication is None, "PySide6 ist nicht installiert")
class ProbeTest(unittest.TestCase):
    """Der Knopf, der vor dem nächsten Morgen Bescheid sagt.

    **Ohne ihn erführe man erst dann, dass das Passwort nicht stimmt.**
    Eine Einrichtung, die sich einen Tag später als falsch herausstellt,
    ist genau die Sorte, vor der diese Funktion warnen soll.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self):
        from mailburg.ui.berichtsdialog import Berichtsdialog

        dialog = Berichtsdialog(bericht.Lage())
        dialog.an.setText("chef@example.org")
        dialog.smtp.setText("mail.example.org:587")
        dialog.von.setText("archiv@example.org")
        return dialog

    def test_die_probe_nimmt_die_felder_und_nicht_das_gespeicherte(self):
        """Wer etwas ändert und auf Probe drückt, will wissen, ob *die
        Änderung* trägt."""
        from PySide6.QtWidgets import QMessageBox

        dialog = self._dialog()
        dialog.smtp.setText("neuer.example.org:2525")
        gesehen = {}

        def merken(lage, betreff, text, pw=""):
            gesehen["smtp"] = lage.smtp
            gesehen["anschluss"] = lage.anschluss

        with mock.patch("mailburg.core.bericht.senden", side_effect=merken), \
                mock.patch.object(QMessageBox, "information"):
            dialog._probe()

        self.assertEqual(gesehen["smtp"], "neuer.example.org")
        self.assertEqual(gesehen["anschluss"], 2525)

    def test_eine_halbe_einrichtung_wird_abgewiesen(self):
        from PySide6.QtWidgets import QMessageBox

        from mailburg.ui.berichtsdialog import Berichtsdialog

        dialog = Berichtsdialog(bericht.Lage())
        dialog.an.setText("chef@example.org")

        with mock.patch("mailburg.core.bericht.senden") as senden, \
                mock.patch.object(QMessageBox, "information") as hinweis:
            dialog._probe()

        senden.assert_not_called()
        hinweis.assert_called_once()

    def test_ein_fehler_wird_genannt_und_nicht_verschluckt(self):
        """**Sonst sähe eine gescheiterte Probe aus wie eine
        gelungene** – und das wäre schlimmer als gar keine."""
        from PySide6.QtWidgets import QMessageBox

        dialog = self._dialog()

        with mock.patch(
            "mailburg.core.bericht.senden",
            side_effect=bericht.VersandFehler("Anmeldung abgelehnt"),
        ), mock.patch.object(QMessageBox, "warning") as warnung, \
                mock.patch.object(QMessageBox, "information") as erfolg:
            dialog._probe()

        warnung.assert_called_once()
        erfolg.assert_not_called()
        self.assertIn("Anmeldung abgelehnt", str(warnung.call_args))

    def test_ohne_eingetipptes_passwort_kommt_es_aus_dem_tresor(self):
        from PySide6.QtWidgets import QMessageBox

        dialog = self._dialog()
        gesehen = {}

        with mock.patch(
            "mailburg.core.bericht.senden",
            side_effect=lambda l, b, t, pw="": gesehen.update(pw=pw),
        ), mock.patch("mailburg.core.tresor.verfuegbar", return_value=True), \
                mock.patch(
                    "mailburg.core.tresor.holen", return_value="aus-dem-tresor"
                ), mock.patch.object(QMessageBox, "information"):
            dialog._probe()

        self.assertEqual(gesehen["pw"], "aus-dem-tresor")

if __name__ == "__main__":
    unittest.main()
