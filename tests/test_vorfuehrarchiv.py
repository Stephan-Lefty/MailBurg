"""Das Archiv zum Vorführen.

Wer MailBurg in einem Video zeigt, darf dabei nicht seine eigene Post
zeigen. Dieses Werkzeug legt dafür ein Archiv mit erfundener Post an –
und die Prüfung, die hier am meisten wiegt, ist nicht, ob es läuft,
sondern **ob wirklich nichts Echtes darin steht**.
"""

from __future__ import annotations

import tempfile
import unittest
from importlib import util
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def _werkzeug():
    laden = util.spec_from_file_location(
        "vorfuehrarchiv", WURZEL / "werkzeuge" / "vorfuehrarchiv.py"
    )
    modul = util.module_from_spec(laden)
    laden.loader.exec_module(modul)
    return modul


class ErfundeneDatenTest(unittest.TestCase):
    """Keine echte Adresse, keine echte Domain."""

    def setUp(self):
        self.werkzeug = _werkzeug()

    def test_jede_adresse_endet_auf_example(self):
        """RFC 2606 reserviert diese Endung – sie gehört nie jemandem.

        Stünde in einer Vorführung eine echte Domain, bekäme deren
        Inhaber Post von allen, die das Beispiel nachspielen.
        """
        adressen = [eintrag[1] for eintrag in self.werkzeug.POST]
        adressen += [eintrag[1] for eintrag in self.werkzeug.ZWEITE_POST]
        adressen += [self.werkzeug.ICH, self.werkzeug.ZWEITES]

        for adresse in adressen:
            with self.subTest(adresse=adresse):
                self.assertTrue(
                    adresse.endswith(".example"),
                    f"{adresse} ist keine reservierte Beispieladresse",
                )

    def test_die_post_reicht_ueber_mehrere_jahre(self):
        """Sonst findet »jahr:« nichts und die Vorführung fällt in sich zusammen."""
        alter = [eintrag[4] for eintrag in self.werkzeug.POST]

        self.assertTrue(any(t < 90 for t in alter), "nichts Frisches")
        self.assertTrue(any(365 < t < 700 for t in alter), "nichts aus dem Vorjahr")
        self.assertTrue(any(t > 700 for t in alter), "nichts Älteres")

    def test_mehrere_ordner_und_zwei_postfaecher(self):
        """Ein Postfachbaum mit einem Eintrag zeigt nicht, wozu er da ist."""
        ordner = {eintrag[2] for eintrag in self.werkzeug.POST}

        self.assertGreaterEqual(len(ordner), 4)
        self.assertNotEqual(self.werkzeug.ICH, self.werkzeug.ZWEITES)


class AngelegtesArchivTest(unittest.TestCase):
    """Was herauskommt, muss sich auch durchsuchen lassen."""

    def setUp(self):
        self.werkzeug = _werkzeug()

    def test_die_suche_findet_etwas(self):
        """Der eigentliche Zweck – und der Grund für das ``with``.

        Journal und Index schreiben ihren letzten Stand erst beim
        Schließen weg. Ohne das läge die Post zwar auf der Platte, die
        Suche fände aber nichts: genau das, was vorgeführt werden soll.
        """
        from mailburg.core.archive import Archive

        with tempfile.TemporaryDirectory() as ordner:
            ziel = Path(ordner) / "Vorfuehrung"
            anzahl = self.werkzeug.anlegen(ziel)

            with Archive.open(ziel) as archiv:
                self.assertEqual(archiv.index.count(), anzahl)
                self.assertTrue(archiv.index.search("rechnung"))
                self.assertTrue(archiv.index.search("von:kraemer"))

    def test_geschaeftlich_ist_die_vorgabe(self):
        """Nur dort gibt es Journal, Einstufung, Fristen und Auskunft."""
        from mailburg.core.archive import Archive

        with tempfile.TemporaryDirectory() as ordner:
            ziel = Path(ordner) / "Vorfuehrung"
            self.werkzeug.anlegen(ziel)

            with Archive.open(ziel) as archiv:
                self.assertTrue(archiv.mode.is_business)

    def test_privat_auf_wunsch(self):
        from mailburg.core.archive import Archive

        with tempfile.TemporaryDirectory() as ordner:
            ziel = Path(ordner) / "Vorfuehrung"
            self.werkzeug.anlegen(ziel, geschaeftlich=False)

            with Archive.open(ziel) as archiv:
                self.assertFalse(archiv.mode.is_business)


class LoeschschutzTest(unittest.TestCase):
    """``--neu`` löscht einen Ordner. Das darf nicht der falsche sein."""

    def setUp(self):
        self.werkzeug = _werkzeug()

    def test_fremder_ordner_bleibt_stehen(self):
        """Ein vertipptes Ziel darf kein fremdes Archiv mitnehmen."""
        with tempfile.TemporaryDirectory() as ordner:
            fremd = Path(ordner) / "Wichtig"
            fremd.mkdir()
            (fremd / "unterlagen.txt").write_text("nicht weg", encoding="utf-8")

            code = self.werkzeug.main([str(fremd), "--neu"])

            self.assertEqual(code, 1)
            self.assertTrue((fremd / "unterlagen.txt").is_file())

    def test_ohne_neu_wird_nichts_angefasst(self):
        with tempfile.TemporaryDirectory() as ordner:
            code = self.werkzeug.main([ordner])

            self.assertEqual(code, 1)


class LesbarkeitsWerkzeugTest(unittest.TestCase):
    """`werkzeuge/lesbarkeit.py` – dieselbe Frage, anderes Werkzeug.

    Es misst die Fenster nach und schreibt einen Bericht. Bis zum
    2026-09-06 las es dabei die **echten** Postfächer des Rechners, und
    deren Adressen standen samt Mailserver in der Ausgabe – also in
    genau dem Text, den man in einen Fehlerbericht kopiert.
    """

    def setUp(self):
        laden = util.spec_from_file_location(
            "lesbarkeit", WURZEL / "werkzeuge" / "lesbarkeit.py"
        )
        self.werkzeug = util.module_from_spec(laden)
        laden.loader.exec_module(self.werkzeug)

    def test_jede_adresse_endet_auf_example(self):
        for konto in self.werkzeug.PROBEKONTEN:
            for feld in ("server", "benutzer"):
                with self.subTest(konto=konto["name"], feld=feld):
                    self.assertTrue(
                        konto[feld].endswith(".example"),
                        f"{konto[feld]} ist keine reservierte Beispieladresse",
                    )

    def test_geschrieben_wird_nur_in_die_uebergebene_datei(self):
        """**Der Schutz der echten Kontenliste.**

        Ein ``Kontenliste()`` ohne Pfad nähme ``config_dir()`` – fiele
        der Patch darüber je weg, überschriebe ein Messwerkzeug die
        Postfächer des Anwenders. Deshalb wird das Ziel übergeben.
        """
        from unittest import mock

        from mailburg.core import paths

        with tempfile.TemporaryDirectory() as ordner:
            ziel = Path(ordner) / "einstellungen" / "konten.json"
            echt = Path(ordner) / "echt"
            with mock.patch.object(paths, "config_dir", return_value=echt):
                self.werkzeug._konten_erfinden(ziel)

            self.assertTrue(ziel.is_file())
            self.assertFalse(echt.exists(), "Es hat woanders hin geschrieben")

    def test_ein_langer_eintrag_ist_dabei(self):
        """Sonst bewiese die Messung der Auswahlfelder nichts.

        Geprüft wird dort, ob ein Feld seinen längsten Eintrag zeigen
        kann. Mit drei kurzen Namen liefe die Prüfung durch, ohne je
        einen engen Fall gesehen zu haben.
        """
        laengen = [len(k["benutzer"]) for k in self.werkzeug.PROBEKONTEN]

        self.assertGreater(max(laengen), 40)

    def test_das_hauptfenster_wird_mitgeprueft(self):
        """**Das Fenster, das den ganzen Tag offensteht, darf nicht fehlen.**

        Bis zum 2026-09-10 prüfte das Werkzeug nur die Dialoge und den
        Assistenten. Ausgenommen war ausgerechnet das Fenster, in dem
        der Anwender die meiste Zeit verbringt – weil es sich offscreen
        schwerer bemessen lässt. Beim ersten Lauf fand es sofort einen
        abgeschnittenen Spaltenkopf.

        Geprüft wird, dass der Dialoglauf das Hauptfenster wirklich
        aufruft, nicht bloß, dass die Funktion existiert: **Eine
        Funktion, die niemand ruft, ist keine Prüfung.**

        Gelesen wird der Quelltext, nicht ein Lauf mit Attrappen. Ein
        nachgestellter Lauf bräuchte Qt und einen Bildschirm; wo der
        fehlt, überspränge sich der Test selbst – und ein Wächter, der
        sich überspringen kann, hält nichts fest.
        """
        import inspect

        quelle = inspect.getsource(self.werkzeug._dialoge)

        self.assertIn(
            "_hauptfenster(", quelle, "Das Hauptfenster wird nicht geprüft"
        )

    def test_jedes_fenster_der_oberflaeche_ist_eingetragen(self):
        """**Der Wächter, der das Werkzeug auf dem Stand hält.**

        Stephans Zuruf am 2026-09-12, und er hatte recht: Das Werkzeug
        kannte zehn Fenster. Die Oberfläche hatte einunddreißig. Es
        meldete »nichts abgeschnitten« und meinte damit die zehn – ein
        Prüfwerkzeug, das schweigend an zwei Dritteln vorbeisieht, ist
        schlimmer als keines, weil man ihm glaubt.

        Der Nachbau von Hand hilft nicht: Wer ein Fenster baut, denkt an
        das Fenster, nicht an die Liste. Deshalb zählt der Test die
        Fenster selbst nach. **Ein neues Fenster ohne Eintrag macht ihn
        rot** – einzutragen ist es entweder als Bauplan, als Sonderfall
        oder als begründete Ausnahme. Nur nicht stillschweigend.

        Gelesen wird der Quelltext (AST), nicht der Import: So läuft der
        Test auch dort, wo kein Qt liegt.
        """
        import ast

        fenstertypen = {"QDialog", "QMainWindow", "QWizard", "QWizardPage"}
        bekannt = (
            {pfad for pfad, _, _ in self.werkzeug.BAUPLAENE}
            | set(self.werkzeug.SONDERFAELLE)
            | set(self.werkzeug.AUSGENOMMEN)
        )

        fehlend = []
        for datei in sorted((WURZEL / "mailburg" / "ui").glob("*.py")):
            baum = ast.parse(datei.read_text(encoding="utf-8"))
            for knoten in ast.walk(baum):
                if not isinstance(knoten, ast.ClassDef):
                    continue
                basen = {
                    b.id for b in knoten.bases if isinstance(b, ast.Name)
                }
                if not basen & fenstertypen:
                    continue
                pfad = f"mailburg.ui.{datei.stem}.{knoten.name}"
                if pfad not in bekannt:
                    fehlend.append(pfad)

        self.assertEqual(
            fehlend,
            [],
            "Diese Fenster prüft niemand auf Lesbarkeit. Trage sie in "
            "werkzeuge/lesbarkeit.py ein – als BAUPLAENE, SONDERFAELLE "
            "oder mit einem Grund in AUSGENOMMEN: " + ", ".join(fehlend),
        )

    def test_keine_ausnahme_ohne_grund(self):
        """Eine Ausnahme ohne Grund ist keine Entscheidung, sondern eine
        Lücke, die niemand mehr sieht."""
        for pfad, grund in self.werkzeug.AUSGENOMMEN.items():
            with self.subTest(fenster=pfad):
                self.assertTrue(
                    grund and grund.strip(), f"{pfad} ist ohne Grund ausgenommen"
                )

    def test_kein_eintrag_zeigt_ins_leere(self):
        """**Ein Eintrag auf eine gelöschte Klasse prüft nichts mehr.**

        Der Wächter oben findet neue Fenster. Diesen Weg braucht es für
        die andere Richtung: Wer ein Fenster umbenennt, lässt sonst einen
        Eintrag stehen, der auf nichts zeigt – und die Liste sieht
        weiterhin vollständig aus.
        """
        import ast

        vorhanden = set()
        for datei in sorted((WURZEL / "mailburg" / "ui").glob("*.py")):
            baum = ast.parse(datei.read_text(encoding="utf-8"))
            for knoten in ast.walk(baum):
                if isinstance(knoten, ast.ClassDef):
                    vorhanden.add(f"mailburg.ui.{datei.stem}.{knoten.name}")

        eingetragen = (
            {pfad for pfad, _, _ in self.werkzeug.BAUPLAENE}
            | set(self.werkzeug.SONDERFAELLE)
            | set(self.werkzeug.AUSGENOMMEN)
        )

        self.assertEqual(
            sorted(eingetragen - vorhanden),
            [],
            "Diese Einträge in werkzeuge/lesbarkeit.py zeigen auf Klassen, "
            "die es nicht mehr gibt",
        )


if __name__ == "__main__":
    unittest.main()
