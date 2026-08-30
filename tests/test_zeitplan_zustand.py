"""Der Sicherungsdialog zeigte immer die Vorgaben.

**Was daran schlimm war.** Der Dialog las zurück, *ob* gesichert wird
und *wohin* – nicht aber, wie oft und wie viele Stände. Beim Öffnen
stand deshalb immer »täglich« und »immer dieselbe Datei ersetzen« da,
unabhängig davon, was tatsächlich eingerichtet war.

Wer darin etwas anderes änderte – den Zielordner etwa – und auf
Übernehmen ging, schrieb den Zeitplan mit den Vorgaben neu. Aus
»monatlich mit zwei Ständen« wurde ein tägliches Überschreiben
derselben Datei: aus zwei Sicherungsständen einer, ohne Meldung, ohne
Nachfrage.

Am 2026-08-30 gefunden, während der Dialog aus anderem Anlass gelesen
wurde. Aufgefallen wäre es sonst erst, wenn jemand eine Sicherung
gebraucht hätte, die es nicht mehr gibt.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import zeitplan


class HaltungLesenTest(unittest.TestCase):
    """Aus der Befehlszeile zurücklesen, was eingestellt wurde."""

    def test_ersetzen_heisst_null(self):
        self.assertEqual(
            zeitplan._behalten_aus("mailburg sichern --leise --ersetzen …"), 0
        )

    def test_die_zahl_wird_gelesen(self):
        self.assertEqual(
            zeitplan._behalten_aus("mailburg sichern --leise --behalten 2 …"), 2
        )

    def test_auch_zweistellig(self):
        self.assertEqual(
            zeitplan._behalten_aus("… --behalten 30 …"), 30
        )

    def test_ohne_angabe_die_vorgabe(self):
        """Eine Datei aus einer älteren Fassung kennt beides nicht."""
        self.assertEqual(zeitplan._behalten_aus("mailburg sichern …"), 0)

    def test_hin_und_zurueck(self):
        """Was ``_haltung`` schreibt, muss ``_behalten_aus`` lesen können."""
        for wert in (0, 1, 2, 7, 30):
            with self.subTest(wert=wert):
                geschrieben = zeitplan._haltung(wert)
                self.assertEqual(zeitplan._behalten_aus(geschrieben), wert)


class TaktLesenTest(unittest.TestCase):
    def test_aus_systemd_wird_deutsch(self):
        self.assertEqual(zeitplan._takt_aus("weekly"), "wöchentlich")
        self.assertEqual(zeitplan._takt_aus("monthly"), "monatlich")
        self.assertEqual(zeitplan._takt_aus("daily"), "täglich")

    def test_unbekanntes_bleibt_leer(self):
        """Ein von Hand gesetztes OnCalendar soll nichts vortäuschen."""
        self.assertEqual(zeitplan._takt_aus("Mon *-*-* 04:00:00"), "")

    def test_jeder_takt_kommt_zurueck(self):
        for name, wert in zeitplan.TAKTE_SICHERUNG.items():
            with self.subTest(takt=name):
                self.assertEqual(zeitplan._takt_aus(wert), name)


class ZustandVollstaendigTest(unittest.TestCase):
    """Der Fall, um den es geht: monatlich, zwei Stände, wiedergefunden."""

    def _eingerichtet(self, dienste: Path, takt: str, behalten: int):
        einheit = "mailburg-sicherung-probe"
        (dienste / f"{einheit}.service").write_text(
            f'ExecStart=/usr/bin/mailburg sichern --leise '
            f'{zeitplan._haltung(behalten)} "/home/martha/Archiv" '
            f'"/media/martha/Platte/Sicherung"\n',
            encoding="utf-8",
        )
        (dienste / f"{einheit}.timer").write_text(
            f"[Timer]\nOnCalendar={zeitplan.TAKTE_SICHERUNG[takt]}\n",
            encoding="utf-8",
        )

    def test_monatlich_mit_zwei_staenden_bleibt_erhalten(self):
        with tempfile.TemporaryDirectory() as ordner:
            dienste = Path(ordner)
            self._eingerichtet(dienste, "monatlich", 2)

            with mock.patch.object(zeitplan, "DIENSTE", dienste), \
                 mock.patch.object(zeitplan, "_windows", lambda: False), \
                 mock.patch.object(zeitplan, "moeglich", lambda: (True, "")), \
                 mock.patch.object(
                     zeitplan, "_einheitsname",
                     lambda p: "mailburg-sicherung-probe"), \
                 mock.patch.object(
                     zeitplan, "_systemctl",
                     lambda *a: mock.Mock(stdout="enabled\n", returncode=0)):
                stand = zeitplan.sicherung_zustand("/home/martha/Archiv")

        self.assertTrue(stand.laeuft)
        self.assertEqual(stand.takt_sicherung, "monatlich")
        self.assertEqual(stand.behalten, 2)
        self.assertEqual(stand.archiv, "/media/martha/Platte/Sicherung")

    def test_ersetzen_kommt_als_null_zurueck(self):
        with tempfile.TemporaryDirectory() as ordner:
            dienste = Path(ordner)
            self._eingerichtet(dienste, "täglich", 0)

            with mock.patch.object(zeitplan, "DIENSTE", dienste), \
                 mock.patch.object(zeitplan, "_windows", lambda: False), \
                 mock.patch.object(zeitplan, "moeglich", lambda: (True, "")), \
                 mock.patch.object(
                     zeitplan, "_einheitsname",
                     lambda p: "mailburg-sicherung-probe"), \
                 mock.patch.object(
                     zeitplan, "_systemctl",
                     lambda *a: mock.Mock(stdout="enabled\n", returncode=0)):
                stand = zeitplan.sicherung_zustand("/home/martha/Archiv")

        self.assertEqual(stand.takt_sicherung, "täglich")
        self.assertEqual(stand.behalten, 0)


if __name__ == "__main__":
    unittest.main()
