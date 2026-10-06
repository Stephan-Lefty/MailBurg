"""Wann der Dienst eine Mail schickt – und welche.

**Die Entscheidung ist hier das Heikle, nicht der Versand.** Eine
Störungsmeldung, die sich täglich wiederholt, wird weggefiltert; eine,
die ausbleibt, wenn sie gebraucht wird, ist nutzlos. Beides fällt im
Betrieb erst auf, wenn es zu spät ist – also wird es hier
durchgespielt.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from mailburg.core.archive import Archive, Mode
from mailburg.server import meldung


class MeldungTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"
        with Archive.create(self.wo, name="Prüfarchiv",
                            mode=Mode.GESCHAEFTLICH) as a:
            a.add(
                b"From: a@example.org\r\nSubject: Test\r\n\r\nText\r\n",
                account="buero", folder="INBOX",
            )

        self.daten = Path(self.ordner.name) / "daten"
        self.umgebung = mock.patch.dict("os.environ", {
            "MAILBURG_BERICHT_AN": "chef@example.org",
            "MAILBURG_BERICHT_SMTP": "mail.example.org",
            "MAILBURG_BERICHT_VON": "archiv@example.org",
            "MAILBURG_BERICHT_UHR": "07:00",
            "MAILBURG_BERICHT_TAKT": "1",
        })
        self.umgebung.start()
        self.addCleanup(self.umgebung.stop)

        self.daten_patch = mock.patch(
            "mailburg.core.paths.data_dir", return_value=self.daten
        )
        self.daten_patch.start()
        self.addCleanup(self.daten_patch.stop)

        self.verschickt: list[tuple[str, str]] = []
        self.senden = mock.patch(
            "mailburg.core.bericht.senden",
            side_effect=lambda lage, betreff, text, pw="": (
                self.verschickt.append((betreff, text))
            ),
        )
        self.senden.start()
        self.addCleanup(self.senden.stop)

    def _lauf(self, *, neu=0, uebersprungen=0, befund="Nichts Neues.",
              jetzt=None):
        return meldung.nach_einem_lauf(
            self.wo, neu=neu, uebersprungen=uebersprungen, befund=befund,
            jetzt=jetzt or datetime(2026, 10, 7, 8, 0),
        )

    # -- Der Tagesbericht ---------------------------------------------------

    def test_ohne_einrichtung_passiert_nichts(self):
        with mock.patch.dict("os.environ", {"MAILBURG_BERICHT_AN": ""}):
            self.assertEqual(self._lauf(), "nicht eingerichtet")

        self.assertEqual(self.verschickt, [])

    def test_der_erste_bericht_geht_hinaus(self):
        self.assertEqual(self._lauf(neu=5), "Bericht geschickt")

        betreff, text = self.verschickt[0]
        self.assertIn("Prüfarchiv", betreff)
        self.assertIn("in Ordnung", betreff)

    def test_am_selben_tag_nur_einmal(self):
        self._lauf()
        self.verschickt.clear()

        self.assertEqual(
            self._lauf(jetzt=datetime(2026, 10, 7, 18, 0)), "noch nicht fällig"
        )
        self.assertEqual(self.verschickt, [])

    def test_am_naechsten_tag_wieder(self):
        self._lauf()
        self.verschickt.clear()

        self.assertEqual(
            self._lauf(jetzt=datetime(2026, 10, 8, 8, 0)), "Bericht geschickt"
        )

    def test_der_takt_wird_beachtet(self):
        with mock.patch.dict("os.environ", {"MAILBURG_BERICHT_TAKT": "7"}):
            self._lauf()
            self.verschickt.clear()

            self.assertEqual(
                self._lauf(jetzt=datetime(2026, 10, 10, 8, 0)),
                "noch nicht fällig",
            )
            self.assertEqual(
                self._lauf(jetzt=datetime(2026, 10, 14, 8, 0)),
                "Bericht geschickt",
            )

    # -- Die Störung --------------------------------------------------------

    def test_ein_uebersprungenes_postfach_meldet_sich_sofort(self):
        """**Nicht auf den nächsten Morgen warten.** Wer um sieben
        erfährt, dass seit Mitternacht nichts mehr ankommt, hat sieben
        Stunden verloren."""
        ergebnis = self._lauf(
            uebersprungen=2, befund="2 Postfächer übersprungen.",
            jetzt=datetime(2026, 10, 7, 2, 0),
        )

        self.assertEqual(ergebnis, "Störung gemeldet")
        betreff, _ = self.verschickt[0]
        self.assertIn("STÖRUNG", betreff)

    def test_dieselbe_stoerung_kommt_nicht_zweimal(self):
        """Sonst legt der Empfänger nach dem dritten Mal eine Regel an –
        und bekommt auch die vierte nicht mehr, die etwas anderes
        sagt."""
        self._lauf(uebersprungen=2, befund="2 Postfächer übersprungen.")
        self.verschickt.clear()

        ergebnis = self._lauf(
            uebersprungen=2, befund="2 Postfächer übersprungen."
        )

        self.assertEqual(ergebnis, "Störung bekannt, nicht wiederholt")
        self.assertEqual(self.verschickt, [])

    def test_nach_der_stoerung_kommt_die_entwarnung(self):
        """**Ohne sie ist eine Störungsmeldung halb so viel wert.** Wer
        abends eine bekommt und morgens nichts hört, weiß nicht, ob es
        wieder läuft oder ob auch die Meldung nicht durchkommt."""
        self._lauf(uebersprungen=1, befund="1 Postfach übersprungen.")
        self.verschickt.clear()

        ergebnis = self._lauf()

        self.assertEqual(ergebnis, "Entwarnung gemeldet")
        betreff, _ = self.verschickt[0]
        self.assertIn("wieder in Ordnung", betreff)

    def test_die_stoerung_verstellt_den_tagesbericht_nicht(self):
        """Sonst bliebe der Bericht am Morgen aus, weil nachts eine
        Störung kam – und sein Ausbleiben wäre kein Signal mehr."""
        self._lauf(
            uebersprungen=1, befund="1 übersprungen.",
            jetzt=datetime(2026, 10, 7, 2, 0),
        )
        self._lauf(jetzt=datetime(2026, 10, 7, 6, 0))  # Entwarnung
        self.verschickt.clear()

        ergebnis = self._lauf(jetzt=datetime(2026, 10, 7, 8, 0))

        self.assertEqual(ergebnis, "Bericht geschickt")

    def test_der_stand_liegt_nicht_im_archiv(self):
        """**Es ist eine Sache des Rechners, nicht des Bestands.** Ein
        Archiv, das umzieht, soll am neuen Ort nicht glauben, es habe
        gestern berichtet."""
        self._lauf()

        self.assertTrue(list(self.daten.glob("bericht/*.json")))
        self.assertFalse(list(self.wo.glob("**/bericht*.json")))


if __name__ == "__main__":
    unittest.main()
