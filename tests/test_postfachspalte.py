"""Die Postfachspalte im Browser, wenn es viele Postfächer sind.

**Der Anlass kommt aus dem Betrieb (06.10.2026).** Stephans Firmenarchiv
zeigt sieben Postfächer, die alle auf ``@ourww.hostedoffice.ag`` enden –
zweiundzwanzig Zeichen, die bei jedem Eintrag gleich sind und das, was
sie unterscheidet, aus dem Bild drängen. Jeder Eintrag brach über zwei
Zeilen um; sieben füllten damit die halbe Seitenhöhe.

Aus MailStore kommen gut zwanzig weitere dazu. Seine Frage, wörtlich:
*»Das heißt die Liste links wird unübersichtlich«* – und sein Vorschlag
dazu: *»Wir können ja die Struktur so lassen, aber die Anzeige im
Browser nach unseren Bedürfnissen anpassen.«* Genau das passiert hier:
**an den Daten ändert sich nichts, nur an der Darstellung.**
"""

from __future__ import annotations

import unittest

from mailburg.server.seiten import _gemeinsame_domain, _kurzname

#: Die sieben laufenden Postfächer, wie sie am 06.10.2026 im Browser
#: standen – nur die Domain ist eine erfundene.
LAUFEND = {
    f"{name}@firma.example": zahl
    for name, zahl in (
        ("buchhaltung", 26912), ("bunze", 469), ("gaertner", 158),
        ("habefa", 1023), ("roesner", 40019), ("sitebah", 78),
        ("wulff", 1634),
    )
}


class GemeinsameDomainTest(unittest.TestCase):
    def test_enden_alle_gleich_wird_sie_erkannt(self):
        self.assertEqual(_gemeinsame_domain(LAUFEND), "firma.example")

    def test_eine_fremde_adresse_kippt_die_kuerzung_nicht(self):
        """**Stephans Frage vom 06.10.2026**, wörtlich: »wenn später
        roesner@freemail.example dazu kommt«.

        Der erste Entwurf verlangte, dass *alle* Adressen gleich enden –
        dann hätte eine einzige fremde alle siebenundzwanzig Einträge
        wieder lang gemacht. Gekürzt wird deshalb die **häufigste**
        Domain; die fremde bleibt vollständig stehen und hebt sich
        dadurch sogar ab. Dasselbe Muster benutzen Mailprogramme seit
        jeher.
        """
        gemischt = {**LAUFEND, "roesner@gmail.example": 230}

        self.assertEqual(_gemeinsame_domain(gemischt), "firma.example")
        self.assertEqual(
            _kurzname("roesner@gmail.example", "firma.example"),
            "roesner@gmail.example",
        )

    def test_zwei_gleich_haeufige_domains_entscheiden_nach_dem_namen(self):
        """**Eine Anzeige darf nicht davon abhängen, in welcher
        Reihenfolge die Konten aus der Datenbank kamen.** Bei
        Gleichstand gewinnt die alphabetisch erste – dieselbe Spalte
        sieht damit bei jedem Aufruf gleich aus.
        """
        patt = {
            "a@aaa.example": 1, "b@aaa.example": 2, "c@aaa.example": 3,
            "d@bbb.example": 4, "e@bbb.example": 5, "f@bbb.example": 6,
        }

        self.assertEqual(_gemeinsame_domain(patt), "aaa.example")

    def test_unter_drei_gleichen_lohnt_es_nicht(self):
        """Bei zweien spart das Weglassen eine Zeile und kostet die
        Eindeutigkeit auf den ersten Blick."""
        wenige = {"a@firma.example": 1, "b@firma.example": 2,
                  "Stephan Rösner": 3}

        self.assertEqual(_gemeinsame_domain(wenige), "")

    def test_namen_ohne_adresse_stehen_nicht_im_weg(self):
        """Ein eingelesener Bestand heißt »Stephan Rösner« oder
        »Outlook Persönlich«. Das ist keine Adresse, der eine Domain
        fehlt – es darf die Kürzung der übrigen nicht verhindern."""
        gemischt = {**LAUFEND, "Stephan Rösner": 51200,
                    "Outlook Persönlich": 8400}

        self.assertEqual(_gemeinsame_domain(gemischt), "firma.example")

    def test_eine_kollision_verhindert_die_kuerzung(self):
        """**Beim Prüfen an echten Daten aufgefallen.**

        Stephan legt den MailStore-Altbestand unter Klarnamen ab, der
        laufende Abruf läuft unter der Adresse. Hieße der Altbestand
        »Buchhaltung«, stünde er nach dem Kürzen neben »buchhaltung« –
        zwei Einträge, die sich in einem Großbuchstaben unterscheiden.

        Im Postfachbaum sähen sie aus wie derselbe. Genau davor warnt
        der Einlesedialog beim Vergeben des Namens; die Anzeige darf es
        nicht selbst herbeiführen.
        """
        kollidiert = {**LAUFEND, "Buchhaltung": 31000}

        self.assertEqual(_gemeinsame_domain(kollidiert), "")

    def test_ohne_jede_adresse_bleibt_alles_wie_es_ist(self):
        self.assertEqual(
            _gemeinsame_domain({"Stephan Rösner": 1, "Outlook": 2}), ""
        )

    def test_ein_einzelnes_postfach_wird_nicht_gekuerzt(self):
        """Es gibt nichts, wovon es sich abheben müsste – und der volle
        Name sagt mehr."""
        self.assertEqual(
            _gemeinsame_domain({"roesner@firma.example": 1}), ""
        )


class KurznameTest(unittest.TestCase):
    def test_die_domain_faellt_weg(self):
        self.assertEqual(
            _kurzname("buchhaltung@firma.example", "firma.example"),
            "buchhaltung",
        )

    def test_ohne_gemeinsame_domain_bleibt_alles_stehen(self):
        self.assertEqual(
            _kurzname("buchhaltung@firma.example", ""),
            "buchhaltung@firma.example",
        )

    def test_ein_anderer_name_bleibt_unberuehrt(self):
        self.assertEqual(
            _kurzname("Stephan Rösner", "firma.example"), "Stephan Rösner"
        )

    def test_ein_name_wird_nie_leer(self):
        """**Ein Postfach, das genau so heißt wie die Domain**, würde
        sonst zu einem leeren Kasten in der Spalte."""
        self.assertEqual(
            _kurzname("@firma.example", "firma.example"), "@firma.example"
        )

    def test_eine_andere_domain_wird_nicht_abgeschnitten(self):
        self.assertEqual(
            _kurzname("wer@anders.example", "firma.example"),
            "wer@anders.example",
        )


class DarstellungTest(unittest.TestCase):
    """Was am Ende in der Seite steht."""

    def _spalte(self, postfaecher):
        from mailburg.server.seiten import _postfachleiste

        return _postfachleiste(postfaecher, "", offen=True)

    def test_in_der_spalte_steht_der_kurze_name(self):
        seite = self._spalte(LAUFEND)

        self.assertIn("<em>buchhaltung</em>", seite)
        self.assertNotIn("<em>buchhaltung@firma.example</em>", seite)

    def test_der_volle_name_bleibt_nachlesbar(self):
        """**Was angezeigt wird, ist gekürzt; was gemeint ist, muss
        nachlesbar bleiben.** Sonst unterscheidet niemand zwei
        Postfächer, die sich erst hinter der Kürzung unterscheiden – und
        eine Vorlesesoftware nennt nur den Rumpf.
        """
        seite = self._spalte(LAUFEND)

        self.assertIn('title="buchhaltung@firma.example"', seite)

    def test_die_suche_zielt_weiterhin_auf_den_vollen_namen(self):
        """**Der wichtigste Test hier.** Gekürzt wird die Anzeige, nicht
        die Abfrage. Stünde im Link »konto:buchhaltung«, fände der Klick
        nichts – die Kontosuche ist groß- und kleinempfindlich und kennt
        nur den vollen Namen.
        """
        seite = self._spalte(LAUFEND)

        self.assertIn("buchhaltung%40firma.example", seite)

    def test_sortiert_ohne_ruecksicht_auf_grossschreibung(self):
        """Sonst stünden alle Klarnamen oben und alle Adressen unten,
        weil »B« vor »b« kommt – und »Buchhaltung« landete weit weg von
        »buchhaltung@…«, obwohl beide dasselbe Postfach meinen.
        """
        seite = self._spalte({
            "wulff@firma.example": 1, "Anton": 2, "buchhaltung@firma.example": 3,
        })
        reihenfolge = [
            teil.split("</em>")[0] for teil in seite.split("<em>")[1:]
        ]

        self.assertEqual(
            [name.casefold() for name in reihenfolge],
            sorted(name.casefold() for name in reihenfolge),
        )

    def test_die_spalte_sagt_was_sie_weglaesst(self):
        """**Sonst rät man, zu welcher Domain »roesner« gehört** –
        besonders, sobald daneben ein vollständiges
        »roesner@gmail.example« steht."""
        seite = self._spalte(LAUFEND)

        self.assertIn("@firma.example", seite)
        self.assertIn("fehlt", seite)

    def test_ohne_kuerzung_steht_dieser_satz_nicht_da(self):
        """Ein Hinweis auf etwas, das nicht passiert ist, verwirrt."""
        seite = self._spalte({"Stephan Rösner": 1, "Outlook": 2})

        self.assertNotIn("fehlt", seite)

    def test_eine_zeile_je_postfach(self):
        """**Das war der Anlass.** Umgebrochen wurde bis zum 06.10.2026
        mit ``overflow-wrap: anywhere``; jeder Eintrag war zwei Zeilen
        hoch. Bei gut zwanzig Postfächern ist das unbenutzbar.
        """
        from mailburg.server.seiten import _KOPF

        self.assertIn("text-overflow: ellipsis", _KOPF)
        self.assertNotIn("overflow-wrap: anywhere", _KOPF)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
