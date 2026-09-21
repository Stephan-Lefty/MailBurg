"""Suchordner und die Liste »Zuletzt gesucht«.

Gebaut auf einen Wunsch vom 2026-09-21: Wer seine Post bisher in
lokalen Ordnern sortiert hat und sie nun MailBurg überlässt, verliert
eine Ordnungsebene. Ein Suchordner ist der Ersatz – ein Name für einen
Suchausdruck, nicht ein Behälter für Post.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import suchordner
from mailburg.search.query import QueryError

ARCHIV = "11111111-2222-3333-4444-555555555555"
ANDERES = "99999999-8888-7777-6666-555555555555"


class MitEigenerDatei(unittest.TestCase):
    """Jeder Test bekommt ein frisches ``oberflaeche.json``.

    **Ohne das schriebe der Testlauf in die echten Einstellungen.** Der
    Fehler wäre nicht laut: Er zeigte sich als Suchordner namens
    »Test« im Fenster des Anwenders. Dieselbe Falle wie 2026-09-07 beim
    Messwerkzeug, das die echten Postfächer las.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.config = Path(self.ordner.name)
        patcher = mock.patch(
            "mailburg.core.paths.config_dir", return_value=self.config
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.ordner.cleanup)

    def datei(self) -> dict:
        pfad = self.config / "oberflaeche.json"
        if not pfad.exists():
            return {}
        return json.loads(pfad.read_text(encoding="utf-8"))


class AnlegenUndLesen(MitEigenerDatei):

    def test_angelegt_ist_wiederzufinden(self) -> None:
        suchordner.hinzufuegen(ARCHIV, "Telekom", "von:telekom")
        geladen = suchordner.laden(ARCHIV)
        self.assertEqual([(o.name, o.ausdruck) for o in geladen],
                         [("Telekom", "von:telekom")])

    def test_reihenfolge_bleibt(self) -> None:
        for name in ("eins", "zwei", "drei"):
            suchordner.hinzufuegen(ARCHIV, name, f"betreff:{name}")
        self.assertEqual([o.name for o in suchordner.laden(ARCHIV)],
                         ["eins", "zwei", "drei"])

    def test_jedes_archiv_hat_eigene(self) -> None:
        """Ein Ausdruck mit ``konto:Firma`` ergibt anderswo nichts.

        Ein Suchordner, der immer leer ist, sieht aus wie ein Fehler –
        deshalb wird nach Archivkennung getrennt.
        """
        suchordner.hinzufuegen(ARCHIV, "Firma", "konto:Firma")
        suchordner.hinzufuegen(ANDERES, "Privat", "konto:Privat")

        self.assertEqual([o.name for o in suchordner.laden(ARCHIV)], ["Firma"])
        self.assertEqual([o.name for o in suchordner.laden(ANDERES)], ["Privat"])

    def test_ein_archiv_aendern_laesst_das_andere_stehen(self) -> None:
        suchordner.hinzufuegen(ARCHIV, "a", "betreff:a")
        suchordner.hinzufuegen(ANDERES, "b", "betreff:b")
        suchordner.entfernen(ARCHIV, "a")
        self.assertEqual([o.name for o in suchordner.laden(ANDERES)], ["b"])

    def test_leere_liste_bleibt_nicht_stehen(self) -> None:
        """Sonst wächst die Datei mit jedem je geöffneten Archiv."""
        suchordner.hinzufuegen(ARCHIV, "a", "betreff:a")
        suchordner.entfernen(ARCHIV, "a")
        self.assertNotIn(ARCHIV, self.datei().get("suchordner", {}))


class WasAbgelehntWird(MitEigenerDatei):

    def test_kaputter_ausdruck(self) -> None:
        """**Vor dem Anlegen, nicht beim Anklicken.**

        Ein Suchordner, der Wochen später »Der Suchausdruck stimmt
        nicht« meldet, ist schlimmer als keiner: Woran es lag, weiß
        dann niemand mehr.
        """
        with self.assertRaises(QueryError):
            suchordner.hinzufuegen(ARCHIV, "Kaputt", "jahr:zwanzig")
        self.assertEqual(suchordner.laden(ARCHIV), [])

    def test_ohne_namen(self) -> None:
        with self.assertRaises(ValueError):
            suchordner.hinzufuegen(ARCHIV, "   ", "von:telekom")

    def test_ohne_ausdruck(self) -> None:
        """Ein Suchordner ohne Ausdruck fände alles."""
        with self.assertRaises(ValueError):
            suchordner.hinzufuegen(ARCHIV, "Alles", "  ")

    def test_zu_langer_name(self) -> None:
        with self.assertRaises(ValueError):
            suchordner.hinzufuegen(
                ARCHIV, "x" * (suchordner.NAME_MAX + 1), "von:telekom"
            )

    def test_name_zweimal(self) -> None:
        suchordner.hinzufuegen(ARCHIV, "Telekom", "von:telekom")
        with self.assertRaises(suchordner.NameVergeben):
            suchordner.hinzufuegen(ARCHIV, "Telekom", "von:anderswo")

    def test_name_zweimal_auch_anders_geschrieben(self) -> None:
        """»telekom« und »Telekom« sähen im Baum aus wie zwei Ordner.

        Derselbe Befund wie beim Kontonamen im Einlesedialog: Fast
        gleich ist hier das Gefährliche.
        """
        suchordner.hinzufuegen(ARCHIV, "Telekom", "von:telekom")
        with self.assertRaises(suchordner.NameVergeben):
            suchordner.hinzufuegen(ARCHIV, "  TELEKOM ", "von:anderswo")

    def test_leerzeichen_werden_zusammengezogen(self) -> None:
        ordner = suchordner.hinzufuegen(ARCHIV, "  Zwei   Worte  ", "von:x")
        self.assertEqual(ordner.name, "Zwei Worte")


class Aendern(MitEigenerDatei):

    def test_umbenennen_behaelt_die_stelle(self) -> None:
        for name in ("eins", "zwei", "drei"):
            suchordner.hinzufuegen(ARCHIV, name, f"betreff:{name}")
        suchordner.aendern(ARCHIV, "zwei", "ZWEI", "betreff:neu")
        self.assertEqual([o.name for o in suchordner.laden(ARCHIV)],
                         ["eins", "ZWEI", "drei"])

    def test_nur_den_ausdruck_aendern(self) -> None:
        suchordner.hinzufuegen(ARCHIV, "Telekom", "von:telekom")
        suchordner.aendern(ARCHIV, "Telekom", "Telekom", "von:telekom.example")
        self.assertEqual(suchordner.laden(ARCHIV)[0].ausdruck,
                         "von:telekom.example")

    def test_auf_einen_vergebenen_namen(self) -> None:
        suchordner.hinzufuegen(ARCHIV, "eins", "betreff:eins")
        suchordner.hinzufuegen(ARCHIV, "zwei", "betreff:zwei")
        with self.assertRaises(suchordner.NameVergeben):
            suchordner.aendern(ARCHIV, "zwei", "eins", "betreff:zwei")

    def test_was_es_nicht_gibt(self) -> None:
        with self.assertRaises(KeyError):
            suchordner.aendern(ARCHIV, "weg", "neu", "betreff:x")

    def test_kaputter_ausdruck_laesst_den_alten_stehen(self) -> None:
        suchordner.hinzufuegen(ARCHIV, "Telekom", "von:telekom")
        with self.assertRaises(QueryError):
            suchordner.aendern(ARCHIV, "Telekom", "Telekom", "jahr:zwanzig")
        self.assertEqual(suchordner.laden(ARCHIV)[0].ausdruck, "von:telekom")


class Verschieben(MitEigenerDatei):

    def test_neue_reihenfolge(self) -> None:
        for name in ("a", "b", "c"):
            suchordner.hinzufuegen(ARCHIV, name, f"betreff:{name}")
        suchordner.verschieben(ARCHIV, ["c", "a", "b"])
        self.assertEqual([o.name for o in suchordner.laden(ARCHIV)],
                         ["c", "a", "b"])

    def test_eine_unvollstaendige_reihenfolge_verschluckt_keinen(self) -> None:
        """Sonst wäre ein Ordner weg, ohne dass ihn jemand entfernt hat."""
        for name in ("a", "b", "c"):
            suchordner.hinzufuegen(ARCHIV, name, f"betreff:{name}")
        suchordner.verschieben(ARCHIV, ["c"])
        self.assertEqual(sorted(o.name for o in suchordner.laden(ARCHIV)),
                         ["a", "b", "c"])

    def test_unbekannte_namen_stoeren_nicht(self) -> None:
        suchordner.hinzufuegen(ARCHIV, "a", "betreff:a")
        suchordner.verschieben(ARCHIV, ["gibtsnicht", "a"])
        self.assertEqual([o.name for o in suchordner.laden(ARCHIV)], ["a"])


class VerdorbeneDatei(MitEigenerDatei):
    """Ein von Hand bearbeitetes ``oberflaeche.json`` darf nichts kosten.

    Gelesen wird beim Aufbau des Fensters – eine Ausnahme dort heißt:
    MailBurg startet nicht mehr.
    """

    def schreiben(self, inhalt) -> None:
        (self.config / "oberflaeche.json").write_text(
            json.dumps({"suchordner": inhalt}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_kein_dict(self) -> None:
        (self.config / "oberflaeche.json").write_text(
            json.dumps({"suchordner": "unsinn"}), encoding="utf-8"
        )
        self.assertEqual(suchordner.laden(ARCHIV), [])

    def test_eintraege_ohne_namen_werden_uebergangen(self) -> None:
        self.schreiben({ARCHIV: [
            {"ausdruck": "von:x"},
            {"name": "gut", "ausdruck": "von:y"},
            "unsinn",
            {"name": "ohne ausdruck"},
        ]})
        self.assertEqual([o.name for o in suchordner.laden(ARCHIV)], ["gut"])


class ZuletztGesucht(MitEigenerDatei):

    def test_der_juengste_steht_oben(self) -> None:
        suchordner.suche_merken(ARCHIV, "rechnung")
        suchordner.suche_merken(ARCHIV, "vertrag")
        self.assertEqual(suchordner.zuletzt_gesucht(ARCHIV),
                         ["vertrag", "rechnung"])

    def test_dasselbe_zweimal_steht_einmal_da(self) -> None:
        suchordner.suche_merken(ARCHIV, "rechnung")
        suchordner.suche_merken(ARCHIV, "vertrag")
        suchordner.suche_merken(ARCHIV, "rechnung")
        self.assertEqual(suchordner.zuletzt_gesucht(ARCHIV),
                         ["rechnung", "vertrag"])

    def test_vom_tippen_bleibt_der_laengste_stand(self) -> None:
        """**Der eigentliche Grund für die Präfixregel.**

        MailBurg sucht schon während der Eingabe. Ohne diese Regel
        stünden nach einem einzigen getippten Wort acht Zwischenstände
        in der Liste, und die richtige Suche wäre darin nicht mehr zu
        finden.
        """
        for stand in ("r", "re", "rec", "rech", "rechnung"):
            suchordner.suche_merken(ARCHIV, stand)
        self.assertEqual(suchordner.zuletzt_gesucht(ARCHIV), ["rechnung"])

    def test_auch_beim_zurueckloeschen(self) -> None:
        """Wer Zeichen wegnimmt, erzeugt ebenfalls keine neue Frage."""
        suchordner.suche_merken(ARCHIV, "rechnung")
        suchordner.suche_merken(ARCHIV, "rech")
        self.assertEqual(suchordner.zuletzt_gesucht(ARCHIV), ["rech"])

    def test_eine_andere_suche_tritt_daneben(self) -> None:
        suchordner.suche_merken(ARCHIV, "rechnung")
        suchordner.suche_merken(ARCHIV, "vertrag")
        self.assertEqual(len(suchordner.zuletzt_gesucht(ARCHIV)), 2)

    def test_nicht_laenger_als_erlaubt(self) -> None:
        for i in range(suchordner.HISTORIE + 5):
            suchordner.suche_merken(ARCHIV, f"suche-{i:02d}")
        self.assertEqual(len(suchordner.zuletzt_gesucht(ARCHIV)),
                         suchordner.HISTORIE)

    def test_leeres_wird_nicht_gemerkt(self) -> None:
        suchordner.suche_merken(ARCHIV, "   ")
        self.assertEqual(suchordner.zuletzt_gesucht(ARCHIV), [])

    def test_je_archiv_getrennt(self) -> None:
        suchordner.suche_merken(ARCHIV, "rechnung")
        self.assertEqual(suchordner.zuletzt_gesucht(ANDERES), [])

    def test_leeren_raeumt_nur_das_eigene_archiv(self) -> None:
        suchordner.suche_merken(ARCHIV, "rechnung")
        suchordner.suche_merken(ANDERES, "vertrag")
        suchordner.historie_leeren(ARCHIV)
        self.assertEqual(suchordner.zuletzt_gesucht(ARCHIV), [])
        self.assertEqual(suchordner.zuletzt_gesucht(ANDERES), ["vertrag"])

    def test_leeren_loescht_wirklich_aus_der_datei(self) -> None:
        """**Nicht nur aus der Anzeige.**

        Der Zweck dieses Wegs ist, eine Spur loszuwerden. Ein Leeren,
        das die Zeile in der Datei stehen lässt, wäre eine falsche
        Zusage – und zwar die teuerste Sorte.
        """
        suchordner.suche_merken(ARCHIV, "eine sehr private sache")
        suchordner.historie_leeren(ARCHIV)
        roh = (self.config / "oberflaeche.json").read_text(encoding="utf-8")
        self.assertNotIn("private sache", roh)


class NebenDenAnderenEinstellungen(MitEigenerDatei):
    """Suchordner dürfen nicht kosten, was sonst gemerkt wird."""

    def test_fenstergroesse_ueberlebt(self) -> None:
        from mailburg.core import einstellungen

        einstellungen.merken_unter("groesse", [1200, 800])
        suchordner.hinzufuegen(ARCHIV, "Telekom", "von:telekom")
        suchordner.suche_merken(ARCHIV, "rechnung")
        self.assertEqual(einstellungen.gemerktes().get("groesse"), [1200, 800])


if __name__ == "__main__":
    unittest.main()
