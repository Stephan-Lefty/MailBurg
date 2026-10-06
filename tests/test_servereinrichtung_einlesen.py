"""Mails einlesen aus dem Einrichtungsfenster.

**Der Anlass kommt aus dem Betrieb, 2026-10-06.** Ein Firmenarchiv war
gerade auf einen Windows Server gezogen, und der größere Teil des
Bestands lag noch in MailStore – 827.199 Mails, die als Verzeichnisse
voller ``.eml``-Dateien herüberkommen. Einlesen ging auf dem Server nur
über die Kommandozeile.

Dieselbe Lehre wie am 2026-09-03 bei der blauen Fassung: *Eine
Funktion, die niemand findet, gibt es für den Anwender nicht.*

**Worum es in diesen Tests wirklich geht**, ist aber nicht der Knopf,
sondern die Sperre dahinter: Zwei Prozesse, die gleichzeitig ins selbe
Archiv schreiben, reißen die Hash-Kette. Das ist am 2026-09-21
passiert, und dort gab es keinen Dienst, der alle dreißig Minuten
abruft.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError:  # pragma: no cover
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 ist nicht installiert")
class EinlesenAusDemFensterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _fenster(self, archiv: str = "/irgendwo/Archiv"):
        from mailburg.ui.servereinrichtung import Einrichtungsfenster

        fenster = Einrichtungsfenster()
        fenster.archivfeld.setText(archiv)
        fenster._melden = lambda *_a, **_k: None
        fenster.auffrischen = lambda *_a, **_k: None
        return fenster

    def test_der_knopf_ist_da(self):
        """Ohne ihn führt auf einem Server kein Weg zum Einlesen."""
        from PySide6.QtWidgets import QPushButton

        beschriftungen = [
            k.text() for k in self._fenster().findChildren(QPushButton)
        ]

        self.assertIn("Mails einlesen …", beschriftungen)

    def test_ohne_archiv_wird_nichts_eingelesen(self):
        fenster = self._fenster(archiv="")

        with mock.patch.object(QMessageBox, "information") as hinweis, \
                mock.patch("mailburg.core.archive.Archive.open") as oeffnen:
            fenster._einlesen()

        hinweis.assert_called_once()
        oeffnen.assert_not_called()

    def test_ein_laufender_dienst_wird_erst_angehalten(self):
        from mailburg.server.einrichtung import Lage

        fenster = self._fenster()

        with mock.patch(
            "mailburg.server.einrichtung.dienst_zustand",
            return_value=(Lage.GUT, "Läuft."),
        ), mock.patch(
            "mailburg.server.einrichtung.dienst_stoppen",
            return_value=(True, "angehalten"),
        ) as stoppen, mock.patch.object(
            QMessageBox, "question", return_value=QMessageBox.Yes
        ), mock.patch("mailburg.core.archive.Archive.open"), \
                mock.patch("mailburg.ui.einlesen.Einlesedialog"):
            fenster._einlesen()

        stoppen.assert_called_once()

    def test_wer_nein_sagt_behaelt_seinen_dienst(self):
        from mailburg.server.einrichtung import Lage

        fenster = self._fenster()

        with mock.patch(
            "mailburg.server.einrichtung.dienst_zustand",
            return_value=(Lage.GUT, "Läuft."),
        ), mock.patch(
            "mailburg.server.einrichtung.dienst_stoppen"
        ) as stoppen, mock.patch.object(
            QMessageBox, "question", return_value=QMessageBox.No
        ), mock.patch("mailburg.core.archive.Archive.open") as oeffnen:
            fenster._einlesen()

        stoppen.assert_not_called()
        oeffnen.assert_not_called()

    def test_ein_dienst_der_sich_nicht_anhalten_laesst_verhindert_das_einlesen(self):
        """**Der wichtigste Test hier.**

        Wenn das Anhalten scheitert und trotzdem eingelesen würde,
        schrieben zwei Vorgänge gleichzeitig ins Archiv – genau der
        Fall, gegen den die ganze Rückfrage gebaut ist. Dann lieber gar
        nicht einlesen.
        """
        from mailburg.server.einrichtung import Lage

        fenster = self._fenster()

        with mock.patch(
            "mailburg.server.einrichtung.dienst_zustand",
            return_value=(Lage.GUT, "Läuft."),
        ), mock.patch(
            "mailburg.server.einrichtung.dienst_stoppen",
            return_value=(False, "ging nicht"),
        ), mock.patch.object(
            QMessageBox, "question", return_value=QMessageBox.Yes
        ), mock.patch.object(QMessageBox, "warning") as warnung, \
                mock.patch("mailburg.core.archive.Archive.open") as oeffnen:
            fenster._einlesen()

        warnung.assert_called_once()
        oeffnen.assert_not_called()

    def test_der_dienst_startet_hinterher_nicht_von_selbst(self):
        """**Stephans Vorgabe vom 2026-10-06.**

        Ein großer Einlesevorgang läuft über Stunden. Wer ihn abends
        anstößt, will morgens selbst entscheiden, wann wieder Betrieb
        ist – und nicht, dass der Abruf mitten in einen zweiten
        Durchgang hineinfährt. Der Knopf *Starten* steht gleich daneben.
        """
        from mailburg.server.einrichtung import Lage

        fenster = self._fenster()

        with mock.patch(
            "mailburg.server.einrichtung.dienst_zustand",
            return_value=(Lage.GUT, "Läuft."),
        ), mock.patch(
            "mailburg.server.einrichtung.dienst_stoppen",
            return_value=(True, "angehalten"),
        ), mock.patch(
            "mailburg.server.einrichtung.dienst_starten"
        ) as starten, mock.patch.object(
            QMessageBox, "question", return_value=QMessageBox.Yes
        ), mock.patch("mailburg.core.archive.Archive.open"), \
                mock.patch("mailburg.ui.einlesen.Einlesedialog"):
            fenster._einlesen()

        starten.assert_not_called()

    def test_ein_stehender_dienst_wird_nicht_gefragt(self):
        """Keine Rückfrage, wo es nichts zu entscheiden gibt."""
        from mailburg.server.einrichtung import Lage

        fenster = self._fenster()

        with mock.patch(
            "mailburg.server.einrichtung.dienst_zustand",
            return_value=(Lage.FEHLT, "Eingerichtet, läuft aber nicht."),
        ), mock.patch.object(QMessageBox, "question") as frage, \
                mock.patch("mailburg.core.archive.Archive.open") as oeffnen, \
                mock.patch("mailburg.ui.einlesen.Einlesedialog"):
            fenster._einlesen()

        frage.assert_not_called()
        oeffnen.assert_called_once()

    def test_das_archiv_wird_exklusiv_geoeffnet(self):
        """Die Sperrdatei ist die zweite Linie hinter dem Anhalten – sie
        hält auch einen Abruf von Hand ab."""
        from mailburg.server.einrichtung import Lage

        fenster = self._fenster()

        with mock.patch(
            "mailburg.server.einrichtung.dienst_zustand",
            return_value=(Lage.FEHLT, "steht"),
        ), mock.patch("mailburg.core.archive.Archive.open") as oeffnen, \
                mock.patch("mailburg.ui.einlesen.Einlesedialog"):
            fenster._einlesen()

        _, kwargs = oeffnen.call_args
        self.assertTrue(kwargs.get("exclusive"))


if __name__ == "__main__":
    unittest.main()
