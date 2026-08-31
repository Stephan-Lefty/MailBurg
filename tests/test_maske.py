"""Die ausführliche Suche – ein Kern für zwei Masken.

Bis zum 2026-08-31 stand die Übersetzung »ausgefüllte Felder →
Suchausdruck« in ``ui/suchmaske.py``, verwoben mit Qt-Widgets. Für den
Browser hätte es sie ein zweites Mal gebraucht – und zwei Fassungen
weichen voneinander ab, sobald jemand ein Feld ergänzt. Dann fände
dieselbe Eingabe im Fenster etwas anderes als im Browser.
"""

from __future__ import annotations

import unittest

from mailburg.search.maske import FELDER, ausdruck, leer, quoten


class QuotenTest(unittest.TestCase):
    def test_ohne_leerzeichen_bleibt_es_wie_es_ist(self):
        self.assertEqual(quoten("rechnung"), "rechnung")

    def test_mit_leerzeichen_kommt_es_in_anfuehrungszeichen(self):
        self.assertEqual(quoten("offene posten"), '"offene posten"')

    def test_leeres_bleibt_leer(self):
        self.assertEqual(quoten("   "), "")


class AusdruckTest(unittest.TestCase):
    def test_nichts_ausgefuellt(self):
        self.assertEqual(ausdruck({}), "")
        self.assertTrue(leer({}))

    def test_freitext_bekommt_kein_praefix(self):
        self.assertEqual(ausdruck({"begriff": "rechnung"}), "rechnung")

    def test_die_felder_bekommen_ihr_schluesselwort(self):
        self.assertEqual(
            ausdruck({"von": "müller", "betreff": "mahnung"}),
            "von:müller betreff:mahnung",
        )

    def test_mehrere_woerter_werden_geklammert(self):
        self.assertEqual(
            ausdruck({"betreff": "offene posten"}), 'betreff:"offene posten"'
        )

    def test_das_haeckchen_traegt_seinen_ganzen_ausdruck(self):
        self.assertEqual(ausdruck({"mit_anhang": "on"}), "hat:anhang")

    def test_ein_leeres_haeckchen_zaehlt_nicht(self):
        for wert in ("", "0", "false", "nein"):
            with self.subTest(wert=wert):
                self.assertEqual(ausdruck({"mit_anhang": wert}), "")

    def test_der_punkt_vor_der_endung_ist_egal(self):
        """»pdf« und ».pdf« meinen dasselbe."""
        self.assertEqual(ausdruck({"typ": ".pdf"}), "typ:pdf")
        self.assertEqual(ausdruck({"typ": "pdf"}), "typ:pdf")

    def test_ausschluesse_werden_einzeln_gesetzt(self):
        self.assertEqual(
            ausdruck({"ohne": "werbung newsletter"}), "-werbung -newsletter"
        )

    def test_die_reihenfolge_folgt_den_feldern(self):
        """Damit derselbe Ausdruck herauskommt, egal wie das Formular kommt."""
        vorwaerts = ausdruck({"begriff": "a", "von": "b", "jahr": "2025"})
        rueckwaerts = ausdruck({"jahr": "2025", "von": "b", "begriff": "a"})

        self.assertEqual(vorwaerts, rueckwaerts)
        self.assertEqual(vorwaerts, "a von:b jahr:2025")

    def test_unbekannte_felder_werden_uebergangen(self):
        """Ein Formular aus dem Netz enthält, was jemand hineinschreibt."""
        self.assertEqual(
            ausdruck({"begriff": "rechnung", "unfug": "; DROP TABLE"}),
            "rechnung",
        )

    def test_ein_zeitraum(self):
        self.assertEqual(
            ausdruck({"seit": "01.01.2025", "bis": "31.12.2025"}),
            "seit:01.01.2025 bis:31.12.2025",
        )


class FelderTest(unittest.TestCase):
    """Die Liste selbst – sie ist die gemeinsame Grundlage."""

    def test_jedes_feld_hat_eine_beschriftung(self):
        for feld in FELDER:
            with self.subTest(feld=feld.name):
                self.assertTrue(feld.beschriftung)

    def test_kein_name_doppelt(self):
        namen = [f.name for f in FELDER]
        self.assertEqual(len(namen), len(set(namen)))

    def test_die_arten_sind_bekannt(self):
        for feld in FELDER:
            with self.subTest(feld=feld.name):
                self.assertIn(feld.art, ("text", "haken", "auswahl", "datum"))

    def test_auswahlfelder_haben_werte_oder_bekommen_sie(self):
        """Postfach und Ordner kommen aus dem Archiv, der Rest steht fest."""
        for feld in FELDER:
            if feld.art != "auswahl":
                continue
            with self.subTest(feld=feld.name):
                self.assertTrue(
                    feld.auswahl or feld.name in ("konto", "ordner"),
                    f"{feld.name} ist eine Auswahl ohne Werte",
                )


class BeideMaskenTest(unittest.TestCase):
    """Fenster und Browser müssen dasselbe ergeben."""

    def test_die_oberflaeche_benutzt_denselben_kern(self):
        """Sonst wäre die Doppelung nur verschoben."""
        from pathlib import Path

        quelle = (
            Path(__file__).resolve().parent.parent
            / "mailburg" / "ui" / "suchmaske.py"
        ).read_text(encoding="utf-8")

        self.assertIn("from mailburg.search.maske import", quelle)
        # Die alte, eigene Übersetzung darf nicht wieder auftauchen.
        self.assertNotIn('teile.append(f"{name}:', quelle)

    def test_der_server_benutzt_ihn_auch(self):
        from pathlib import Path

        quelle = (
            Path(__file__).resolve().parent.parent
            / "mailburg" / "server" / "lesen.py"
        ).read_text(encoding="utf-8")

        self.assertIn("from mailburg.search.maske import", quelle)




class DeutschesDatumTest(unittest.TestCase):
    """Ein Datum sieht überall gleich aus – am 2026-08-31 entschieden.

    Vorher kam das Format aus ``QLocale``, also aus den
    Systemeinstellungen, während das übrige Programm fest deutsch
    spricht. Auf einem englischen Rechner stand »Weiter« neben
    »8/24/2026«, auf einem Bauserver »24 08 2026«.
    """

    def test_der_kern_schreibt_deutsch(self):
        from mailburg.core.sprache import zeitpunkt

        self.assertEqual(
            zeitpunkt("2026-08-25T07:46:11+00:00"), "25.08.2026, 07:46"
        )

    def test_unbrauchbares_bleibt_stehen_statt_zu_werfen(self):
        """In zwanzig Jahren Mail steht alles Mögliche in einem Datumsfeld."""
        from mailburg.core.sprache import zeitpunkt

        self.assertEqual(zeitpunkt(""), "")
        self.assertEqual(zeitpunkt("unsinn"), "unsinn")

    def test_die_oberflaeche_fragt_nicht_mehr_die_systemsprache(self):
        from pathlib import Path

        wurzel = Path(__file__).resolve().parent.parent / "mailburg" / "ui"
        for name in ("datum.py", "suchmaske.py"):
            quelle = (wurzel / name).read_text(encoding="utf-8")
            # Im Fließtext darf QLocale vorkommen - im Code nicht mehr.
            code = "\n".join(
                zeile for zeile in quelle.splitlines()
                if not zeile.lstrip().startswith(("#", '"', "*", "-"))
            )
            with self.subTest(datei=name):
                self.assertNotIn("QLocale(", code)

    def test_eingabe_und_anzeige_haben_dieselbe_schreibweise(self):
        """Zwei Formate für dasselbe Datum im selben Fenster wären eine Zumutung.

        ``ui/datum.py`` zieht PySide6 herein, und das fehlt im ersten
        CI-Lauf – der prüft ausdrücklich den Kern ohne Zusätze. Ohne
        diese Weiche war er seit dem 2026-08-31 rot.
        """
        try:
            from mailburg.ui.datum import MUSTER
        except ImportError:  # pragma: no cover – nur ohne PySide6
            self.skipTest("PySide6 fehlt")

        self.assertEqual(MUSTER, "dd.MM.yyyy")


if __name__ == "__main__":
    unittest.main()
