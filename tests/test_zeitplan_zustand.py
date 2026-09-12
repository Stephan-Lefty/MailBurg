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


class ZeigtInsLeereTest(unittest.TestCase):
    """**Ein Zeitplan, der ins Leere zeigt, sieht aus wie einer, der geht.**

    Er steht in der Aufgabenplanung, er hat seine Uhrzeit, das Fenster
    meldet »Abruf: alle 30 Minuten«. Nur das Programm, das er startet,
    liegt nicht mehr dort. Der Abruf hört auf, ohne dass jemand etwas
    sieht – und in einem Archiv fällt das erst auf, wenn die Post fehlt,
    die man sucht.

    Dahin kommt man, ohne etwas falsch zu machen: Unter Windows steht
    der volle Pfad der ``MailBurg.exe`` in der Aufgabe, also stellt das
    Verschieben aus dem Download-Ordner den Abruf ab. Unter Linux trifft
    es den Pfad in der virtuellen Umgebung, sobald die Distribution
    Python anhebt.

    Am 2026-09-12 gebaut, nachdem Stephan gefragt hatte, warum die
    ``.exe`` keine Versionsnummer im Namen trägt. Sie trägt keine, damit
    genau das hier nicht bei jedem Update passiert – und dabei fiel auf,
    dass es beim Verschieben trotzdem passieren kann.
    """

    def _einheit(self, dienste: Path, programm: str) -> None:
        (dienste / "mailburg-abruf-probe.service").write_text(
            "[Unit]\nDescription=Probe\n\n[Service]\nType=oneshot\n"
            f'ExecStart={programm} abrufen --leise "/home/martha/Archiv"\n',
            encoding="utf-8",
        )

    def _pruefen(self, dienste: Path, archiv="/home/martha/Archiv"):
        with mock.patch.object(zeitplan, "DIENSTE", dienste), \
             mock.patch.object(zeitplan, "_windows", lambda: False), \
             mock.patch.object(
                 zeitplan, "_abrufeinheit", lambda p: "mailburg-abruf-probe"):
            return zeitplan.zeigt_ins_leere(archiv)

    def test_ein_verschwundenes_programm_wird_gemeldet(self):
        with tempfile.TemporaryDirectory() as ordner:
            dienste = Path(ordner)
            self._einheit(dienste, "/weg/damit/mailburg")

            kaputt, meldung = self._pruefen(dienste)

        self.assertTrue(kaputt)
        self.assertIn("/weg/damit/mailburg", meldung)

    def test_ein_vorhandenes_programm_ist_in_ordnung(self):
        with tempfile.TemporaryDirectory() as ordner:
            dienste = Path(ordner)
            echt = dienste / "mailburg"
            echt.write_text("#!/bin/sh\n", encoding="utf-8")
            self._einheit(dienste, str(echt))

            kaputt, meldung = self._pruefen(dienste)

        self.assertFalse(kaputt)
        self.assertEqual(meldung, "")

    def test_ohne_eingerichteten_abruf_wird_nichts_behauptet(self):
        """**Kein Zeitplan ist kein kaputter Zeitplan.**

        Wer hier meldete, schickte jedem, der den Abruf gar nicht
        eingerichtet hat, eine Warnung über einen Abruf, den es nicht
        gibt.
        """
        with tempfile.TemporaryDirectory() as ordner:
            kaputt, meldung = self._pruefen(Path(ordner))

        self.assertFalse(kaputt)
        self.assertEqual(meldung, "")

    def test_ein_pfad_mit_leerzeichen_bleibt_ganz(self):
        """Sonst gälte »/mit« als das Programm und »Leerzeichen/…« als
        Argument – und die Prüfung meldete bei jedem Anwender mit einem
        Leerzeichen im Pfad einen Fehler, den es nicht gibt. Unter
        Windows wäre das jeder zweite (``C:\\Program Files``)."""
        with tempfile.TemporaryDirectory() as ordner:
            dienste = Path(ordner)
            echt = dienste / "mit Leerzeichen" / "mailburg"
            echt.parent.mkdir()
            echt.write_text("#!/bin/sh\n", encoding="utf-8")
            self._einheit(dienste, f'"{echt}"')

            kaputt, meldung = self._pruefen(dienste)

        self.assertFalse(kaputt, meldung)

    def test_windows_fragt_die_aufgabenplanung(self):
        """**Nicht die eigene Kopie lesen.** Unter der Ablage liegt
        dieselbe Beschreibung, aber sie ist nur das, was MailBurg einmal
        hingeschrieben hat. Wer die Aufgabe von Hand ändert – und in der
        Aufgabenplanung kann man das –, ändert die echte."""
        from mailburg.core import aufgabenplanung

        xml = (
            '<?xml version="1.0"?>\n<Task>\n  <Actions>\n    <Exec>\n'
            '      <Command>C:\\weg\\MailBurg.exe</Command>\n'
            '    </Exec>\n  </Actions>\n</Task>\n'
        )
        with mock.patch.object(
            aufgabenplanung, "_schtasks",
            lambda *a: mock.Mock(stdout=xml, returncode=0),
        ):
            programm = aufgabenplanung.eingetragenes_programm(
                Path("/tmp/Archiv")
            )

        self.assertEqual(programm, "C:\\weg\\MailBurg.exe")

    def test_ohne_aufgabe_kommt_nichts_zurueck(self):
        """Und ``""`` heißt ausdrücklich nicht »in Ordnung« – der
        Aufrufer behandelt es als fehlende Auskunft, nicht als Befund."""
        from mailburg.core import aufgabenplanung

        with mock.patch.object(
            aufgabenplanung, "_schtasks",
            lambda *a: mock.Mock(stdout="", returncode=1),
        ):
            programm = aufgabenplanung.eingetragenes_programm(
                Path("/tmp/Archiv")
            )

        self.assertEqual(programm, "")

    def test_geradeziehen_behaelt_den_takt(self):
        """Wer alle 90 Minuten abruft, will das auch nach einem Umzug.
        Den Takt hier auf die Vorgabe zu setzen, verwürfe stillschweigend
        eine Entscheidung des Anwenders."""
        gemerkt = {}

        def merken(archiv, takt):
            gemerkt["takt"] = takt
            return True, ""

        with mock.patch.object(
                zeitplan, "zustand",
                lambda a: zeitplan.Zustand(laeuft=True, takt=90)), \
             mock.patch.object(zeitplan, "abschalten", lambda a: (True, "")), \
             mock.patch.object(zeitplan, "einrichten", merken):
            zeitplan.geradeziehen("/home/martha/Archiv")

        self.assertEqual(gemerkt["takt"], 90)


if __name__ == "__main__":
    unittest.main()
