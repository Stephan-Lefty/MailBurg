"""Zugänge zum Archiv und ihre Rechte.

Die Grundlage der Server Edition: Dort greifen mehrere Menschen auf
denselben Bestand zu und sollen verschiedenes sehen.

Geprüft wird vor allem, was still schiefgehen kann – ein Passwort, das
auch falsch akzeptiert wird; ein Recht, das mehr öffnet als gedacht;
ein Prüfwert, der im Journal landet und dort nie wieder wegzubekommen
ist.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mailburg.core.archive import Archive, Mode
from mailburg.core.benutzer import (
    Benutzer,
    BenutzerFehler,
    Benutzerliste,
    passwort_pruefwert,
    passwort_stimmt,
)


class PasswortTest(unittest.TestCase):
    def test_das_richtige_passwort_stimmt(self):
        wert = passwort_pruefwert("ein-langes-passwort")

        self.assertTrue(passwort_stimmt(wert, "ein-langes-passwort"))
        self.assertFalse(passwort_stimmt(wert, "ein-langes-passwor"))
        self.assertFalse(passwort_stimmt(wert, ""))

    def test_zweimal_dasselbe_passwort_ergibt_zwei_pruefwerte(self):
        """Ohne Salz verriete die Liste, wer dasselbe Passwort hat."""
        self.assertNotEqual(
            passwort_pruefwert("dasselbe-passwort"),
            passwort_pruefwert("dasselbe-passwort"),
        )

    def test_der_pruefwert_nennt_sein_verfahren(self):
        """Sonst lässt sich später nicht auf Argon2 wechseln."""
        wert = passwort_pruefwert("ein-langes-passwort")

        art, kosten, block, parallel, salz, ergebnis = wert.split("$")
        self.assertEqual(art, "scrypt")
        self.assertGreaterEqual(int(kosten), 2 ** 14)
        self.assertTrue(salz and ergebnis)

    def test_ein_kaputter_pruefwert_laesst_niemanden_ein(self):
        """Nicht »wirft eine Ausnahme« – das könnte jemand abfangen."""
        for kaputt in ("", "unsinn", "scrypt$x$y$z$a$b", "argon2$1$2$3$a$b",
                       "scrypt$16384$8$1$nur-vier-teile"):
            with self.subTest(wert=kaputt):
                self.assertFalse(passwort_stimmt(kaputt, "irgendwas"))

    def test_zu_kurze_passwoerter_werden_abgewiesen(self):
        eintrag = Benutzer("anna")

        with self.assertRaises(BenutzerFehler):
            eintrag.passwort_setzen("kurz")
        self.assertEqual(eintrag.pruefwert, "")


class NamenTest(unittest.TestCase):
    def test_gross_und_klein_sind_derselbe_zugang(self):
        """Sonst wären »Anna« und »anna« zwei Zugänge mit zwei Rechten."""
        self.assertEqual(Benutzer("Anna").name, "anna")
        self.assertEqual(Benutzer("  ANNA  ").name, "anna")

    def test_unzulaessige_namen(self):
        for name in ("", "a", "ab", "-anna", "anna-", "an na", "anna@example",
                     "änna", "a" * 40):
            with self.subTest(name=name):
                with self.assertRaises(BenutzerFehler):
                    Benutzer(name)

    def test_zulaessige_namen(self):
        for name in ("anna", "a.b", "max_mustermann", "buero2"):
            with self.subTest(name=name):
                self.assertEqual(Benutzer(name).name, name)


class RechteTest(unittest.TestCase):
    def test_wer_nichts_zugeordnet_bekommt_sieht_nichts(self):
        """Die sichere Vorgabe: erst zuordnen, dann sehen."""
        neu = Benutzer("neu")

        self.assertFalse(neu.darf_sehen("buchhaltung"))
        self.assertEqual(neu.sichtbare_postfaecher(["buchhaltung"]), [])

    def test_zugeordnete_postfaecher(self):
        anna = Benutzer("anna", postfaecher=["buchhaltung", "einkauf"])

        self.assertTrue(anna.darf_sehen("buchhaltung"))
        self.assertFalse(anna.darf_sehen("vertrieb"))
        self.assertEqual(
            anna.sichtbare_postfaecher(["vertrieb", "einkauf", "buchhaltung"]),
            ["einkauf", "buchhaltung"],
        )

    def test_wer_alles_darf_sieht_auch_das_neue_postfach(self):
        """Der Grund für den Schalter statt einer Liste aller Postfächer.

        Käme morgen ein Postfach dazu, müsste eine Liste nachgepflegt
        werden – und würde es nicht, bis jemand etwas vermisst.
        """
        chef = Benutzer("chef", alle_postfaecher=True)

        self.assertTrue(chef.darf_sehen("gibt-es-erst-seit-heute"))

    def test_verwalter_darf_nicht_automatisch_alles_lesen(self):
        """Wer die Technik betreut, muss keine Geschäftspost lesen dürfen."""
        technik = Benutzer("technik", verwalter=True)

        self.assertFalse(technik.darf_sehen("buchhaltung"))

    def test_stillgelegt_sieht_nichts_mehr(self):
        anna = Benutzer("anna", alle_postfaecher=True, aktiv=False)

        self.assertFalse(anna.darf_sehen("buchhaltung"))
        self.assertEqual(anna.sichtbare_postfaecher(["buchhaltung"]), [])


class AnmeldenTest(unittest.TestCase):
    def setUp(self):
        self.liste = Benutzerliste()
        self.anna = Benutzer("anna", anzeigename="Anna Feldmann")
        self.anna.passwort_setzen("ein-langes-passwort")
        self.liste.hinzufuegen(self.anna)

    def test_richtig(self):
        self.assertIs(
            self.liste.anmelden("anna", "ein-langes-passwort"), self.anna
        )

    def test_auch_mit_grossbuchstaben(self):
        self.assertIs(
            self.liste.anmelden("Anna", "ein-langes-passwort"), self.anna
        )

    def test_falsches_passwort(self):
        self.assertIsNone(self.liste.anmelden("anna", "daneben"))

    def test_unbekannter_name(self):
        self.assertIsNone(self.liste.anmelden("niemand", "egal"))

    def test_unzulaessiger_name_wirft_nicht(self):
        """Aus einem Anmeldefeld kommt alles Mögliche."""
        self.assertIsNone(self.liste.anmelden("' OR 1=1 --", "egal"))

    def test_stillgelegt_kommt_nicht_hinein(self):
        self.anna.aktiv = False

        self.assertIsNone(self.liste.anmelden("anna", "ein-langes-passwort"))

    def test_ohne_passwort_kommt_niemand_hinein(self):
        """Ein Zugang, dem nie eines gesetzt wurde, ist kein offenes Tor."""
        self.liste.hinzufuegen(Benutzer("ohne"))

        self.assertIsNone(self.liste.anmelden("ohne", ""))
        self.assertIsNone(self.liste.anmelden("ohne", "irgendwas"))

    def test_unbekannter_name_dauert_aehnlich_lang(self):
        """Sonst verriete die Uhr, welche Anmeldenamen es gibt.

        Großzügig geprüft: Es geht nicht um Gleichheit auf die
        Millisekunde, sondern darum, dass nicht der eine Fall gerechnet
        wird und der andere sofort zurückkommt.
        """
        import time

        def dauer(name: str) -> float:
            start = time.perf_counter()
            self.liste.anmelden(name, "ein-langes-passwort")
            return time.perf_counter() - start

        bekannt = min(dauer("anna") for _ in range(3))
        unbekannt = min(dauer("niemand") for _ in range(3))

        self.assertGreater(
            unbekannt, bekannt / 3,
            "Bei unbekanntem Namen wird offenbar gar nicht gerechnet",
        )


class ListeTest(unittest.TestCase):
    def test_denselben_namen_zweimal(self):
        liste = Benutzerliste()
        liste.hinzufuegen(Benutzer("anna"))

        with self.assertRaises(BenutzerFehler):
            liste.hinzufuegen(Benutzer("Anna"))

    def test_entfernen(self):
        liste = Benutzerliste()
        liste.hinzufuegen(Benutzer("anna"))

        self.assertTrue(liste.entfernen("anna"))
        self.assertFalse(liste.entfernen("anna"))
        self.assertEqual(len(liste), 0)

    def test_verwalter_werden_aufgezaehlt(self):
        liste = Benutzerliste()
        liste.hinzufuegen(Benutzer("chef", verwalter=True))
        liste.hinzufuegen(Benutzer("alt", verwalter=True, aktiv=False))
        liste.hinzufuegen(Benutzer("anna"))

        self.assertEqual([b.name for b in liste.verwalter], ["chef"])


class DateiTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name)

    def test_hin_und_zurueck(self):
        liste = Benutzerliste()
        anna = Benutzer("anna", anzeigename="Anna Feldmann",
                        postfaecher=["buchhaltung"])
        anna.passwort_setzen("ein-langes-passwort")
        liste.hinzufuegen(anna)
        liste.schreiben(self.wo)

        wieder = Benutzerliste.lesen(self.wo)
        self.assertIsNotNone(wieder.anmelden("anna", "ein-langes-passwort"))
        self.assertEqual(wieder.finden("anna").anzeigename, "Anna Feldmann")

    def test_ohne_datei_ist_die_liste_leer(self):
        self.assertEqual(len(Benutzerliste.lesen(self.wo)), 0)

    def test_kaputte_datei_verschliesst_das_archiv_nicht(self):
        (self.wo / "benutzer.json").write_text("{kein json", encoding="utf-8")

        self.assertEqual(len(Benutzerliste.lesen(self.wo)), 0)

    def test_ein_unlesbarer_eintrag_nimmt_nicht_die_uebrigen_mit(self):
        (self.wo / "benutzer.json").write_text(json.dumps({
            "fassung": 1,
            "benutzer": [
                {"name": "-unzulaessig-"},
                {"name": "anna", "anzeigename": "Anna"},
                "gar kein Wörterbuch",
            ],
        }), encoding="utf-8")

        liste = Benutzerliste.lesen(self.wo)
        self.assertEqual([b.name for b in liste], ["anna"])

    @unittest.skipIf(sys.platform == "win32", "Rechte gibt es dort anders")
    def test_die_datei_gehoert_nur_dem_benutzer(self):
        """In ihr stehen die Prüfwerte der Passwörter."""
        Benutzerliste().schreiben(self.wo)

        rechte = (self.wo / "benutzer.json").stat().st_mode & 0o777
        self.assertEqual(rechte, 0o600)


class ImArchivTest(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"

    def _archiv(self):
        return Archive.create(self.wo, name="Probe", mode=Mode.GESCHAEFTLICH)

    def test_ein_frisches_archiv_hat_keine_benutzer(self):
        with self._archiv() as archiv:
            self.assertEqual(len(archiv.benutzer), 0)

    def test_setzen_und_wiederfinden(self):
        with self._archiv() as archiv:
            liste = archiv.benutzer
            anna = Benutzer("anna", postfaecher=["buchhaltung"])
            anna.passwort_setzen("ein-langes-passwort")
            liste.hinzufuegen(anna)
            archiv.benutzer_setzen(liste, actor="chef")

            wieder = archiv.benutzer
            self.assertIsNotNone(wieder.anmelden("anna", "ein-langes-passwort"))

    def test_jede_aenderung_steht_im_journal(self):
        """Wer wann welchen Zugang bekam, gehört zur Verfahrensdokumentation."""
        with self._archiv() as archiv:
            liste = archiv.benutzer
            liste.hinzufuegen(Benutzer("anna"))
            archiv.benutzer_setzen(liste, actor="chef")

            eintraege = [e for e in archiv.journal.read_all()
                         if e.get("op") == "users"]
            self.assertEqual(len(eintraege), 1)
            self.assertEqual(eintraege[0]["actor"], "chef")
            self.assertEqual(
                [b["name"] for b in eintraege[0]["users"]["benutzer"]], ["anna"]
            )

    def test_keine_pruefwerte_im_journal(self):
        """Was dort einmal steht, steht dort für immer.

        Ein Prüfwert, der sich später als angreifbar herausstellt, ließe
        sich nicht mehr entfernen, ohne die Hash-Kette zu zerreißen.
        """
        with self._archiv() as archiv:
            liste = archiv.benutzer
            anna = Benutzer("anna")
            anna.passwort_setzen("ein-langes-passwort")
            liste.hinzufuegen(anna)
            archiv.benutzer_setzen(liste, actor="chef")

            protokoll = "".join(
                json.dumps(e, ensure_ascii=False)
                for e in archiv.journal.read_all()
            )
            self.assertNotIn("pruefwert", protokoll)
            self.assertNotIn("scrypt$", protokoll)

    def test_ohne_aenderung_kein_eintrag(self):
        """Sonst wüchse das Journal bei jedem Öffnen eines Dialogs."""
        with self._archiv() as archiv:
            liste = archiv.benutzer
            liste.hinzufuegen(Benutzer("anna"))
            archiv.benutzer_setzen(liste, actor="chef")
            archiv.benutzer_setzen(archiv.benutzer, actor="chef")

            eintraege = [e for e in archiv.journal.read_all()
                         if e.get("op") == "users"]
            self.assertEqual(len(eintraege), 1)

    def test_die_hash_kette_bleibt_heil(self):
        with self._archiv() as archiv:
            liste = archiv.benutzer
            liste.hinzufuegen(Benutzer("anna"))
            archiv.benutzer_setzen(liste, actor="chef")

            self.assertTrue(archiv.journal.verify().ok)

    def test_ein_neues_passwort_kommt_nicht_ins_journal(self):
        """Auch beim Ändern nicht – und die Änderung selbst schon."""
        with self._archiv() as archiv:
            liste = archiv.benutzer
            anna = Benutzer("anna")
            anna.passwort_setzen("das-erste-passwort")
            liste.hinzufuegen(anna)
            archiv.benutzer_setzen(liste, actor="chef")

            liste = archiv.benutzer
            liste.finden("anna").passwort_setzen("das-zweite-passwort")
            liste.finden("anna").anzeigename = "Anna F."
            archiv.benutzer_setzen(liste, actor="chef")

            protokoll = "".join(
                json.dumps(e, ensure_ascii=False)
                for e in archiv.journal.read_all()
            )
            self.assertNotIn("scrypt$", protokoll)
            self.assertIn("Anna F.", protokoll)
            self.assertIsNotNone(
                archiv.benutzer.anmelden("anna", "das-zweite-passwort")
            )


if __name__ == "__main__":
    unittest.main()
