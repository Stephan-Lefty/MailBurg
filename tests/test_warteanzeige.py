"""Der Hinweis, dass MailBurg gerade etwas tut.

**Der Anlass war eine Beobachtung, die sich nicht bestätigt hat.** Am
06.10.2026 dauerte eine Suche auf dem Firmenserver fünf bis sieben
Sekunden. Gemessen wurde danach der ganze Suchpfad über 70.269 Mails:
0,12 Sekunden. Die Verzögerung kam von außen – MailStore exportierte zur
selben Zeit 827.199 Mails auf dieselbe Maschine.

**Der Hinweis bleibt trotzdem**, und zwar genau deshalb: Eine solche
Last kann jederzeit wieder auftreten, und dann soll der Browser nicht
tot aussehen. Im Normalfall sieht ihn niemand.

Stephans Vorgabe, wörtlich: *»Dann keine Sanduhr – aber ein Hinweis das
MAILBurg etwas tut!«* Vorher standen ein blinkendes Wappen und ein
Ladebalken zur Debatte; beide ziehen das Auge an und sagen doch nur
»warte«.
"""

from __future__ import annotations

import re
import unittest

from mailburg.server import seiten


class WarteanzeigeTest(unittest.TestCase):
    def setUp(self):
        # **Eine wirklich gebaute Seite, kein Blick in die Vorlage.**
        # Im Kopf steckt eingebettetes JavaScript mit geschweiften
        # Klammern, und die Vorlage geht durch `.format()`. Beim Bauen
        # ist genau das schiefgegangen: eine einfache Klammer im Skript,
        # und jede Seite der Oberfläche wirft einen KeyError. Wer nur
        # `_KOPF` liest, findet das nie.
        self.seite = seiten.rechtliches()

    def test_der_hinweis_steht_in_der_seite(self):
        self.assertIn('id="laeufttext"', self.seite)
        self.assertIn("MailBurg sucht", self.seite)

    def test_er_meldet_sich_der_vorlesesoftware(self):
        """**Das Wichtigste daran, und nicht nur Beiwerk.**

        `role="status"` sagt dem Screenreader, dass er den Satz
        vorlesen soll, sobald er erscheint – ohne die Stelle zu
        verlassen, an der der Leser gerade ist. Ein rein sichtbarer
        Hinweis wäre für einen blinden Anwender gar keiner.
        """
        treffer = re.search(r'<div[^>]*id="laeufttext"[^>]*>', self.seite)

        self.assertIsNotNone(treffer, "Der Hinweis fehlt in der Seite.")
        self.assertIn('role="status"', treffer.group(0))

    def test_versteckt_bis_es_etwas_zu_melden_gibt(self):
        """Ohne diese Zeile stünde der Satz auf jeder Seite dauerhaft da
        – und ein Hinweis, der immer gilt, sagt nichts."""
        self.assertRegex(self.seite, r"#laeufttext\s*\{[^}]*display:\s*none")

    def test_keine_sanduhr_und_keine_bewegung(self):
        """**Stephans Entscheidung, als Test festgehalten.**

        Der Wortlaut ist hier nicht das Geprüfte, sondern die Sache:
        Nichts in dieser Oberfläche darf blinken, pochen oder laufen.
        Wer eine Animation einbaut, macht aus dem Hinweis wieder eine
        Sanduhr.
        """
        for unerwuenscht in ("@keyframes", "animation:", "animation-"):
            self.assertNotIn(unerwuenscht, self.seite, f"{unerwuenscht} gefunden")

    def test_der_verzug_ist_groesser_als_eine_gewoehnliche_suche(self):
        """Gemessen am Firmenarchiv: 0,12 s für den ganzen Suchpfad über
        70.269 Mails. Wer den Verzug darunter setzt, lässt den Hinweis
        bei *jeder* Suche aufblitzen – das ist Flackern, keine Auskunft.
        """
        verzug = re.search(r"\}\s*,\s*(\d+)\s*\)\s*;", self.seite)

        self.assertIsNotNone(verzug, "Kein setTimeout-Verzug gefunden.")
        self.assertGreaterEqual(int(verzug.group(1)), 300)

    def test_nichts_wird_nachgeladen(self):
        """Das Skript steht in der Seite. Ein Archiv im Firmennetz soll
        für eine Anzeige keinen fremden Server befragen – und auf einem
        Server ohne Internetzugang liefe sonst gar nichts."""
        self.assertNotRegex(self.seite, r"<script[^>]+src=")

    def test_genau_ein_skript_in_der_ganzen_oberflaeche(self):
        """**Die alte Festlegung, an ihrem neuen Ort.**

        Bis zum 06.10.2026 kam die Weboberfläche ohne jedes JavaScript
        aus, und ein Wächtertest in ``test_lesen.py`` hielt das fest
        (``assertNotIn("<script", …)``). Dieser Hinweis ist die
        Ausnahme – eine Anzeige, die ohne Skript nicht geht.

        **Eine Ausnahme bleibt nur eine, wenn sie gezählt wird.** Sonst
        wandert nach und nach Logik in den Browser, die ins Programm
        gehört: Ein Archiv soll lesbar bleiben, wenn in zehn Jahren
        niemand mehr dieses JavaScript ausführt.
        """
        self.assertEqual(self.seite.count("<script"), 1)

    def test_ohne_javascript_bleibt_alles_wie_zuvor(self):
        """Der Hinweis wird allein von JavaScript eingeschaltet. Fehlt
        es, fehlt die Anzeige – und keine Funktion."""
        # Eingeschaltet wird über eine Klasse am <html>, die es im
        # ausgelieferten Markup nicht gibt.
        self.assertNotRegex(self.seite, r"<html[^>]*class=[^>]*sucht")
        self.assertIn('classList.add("sucht")', self.seite)

    def test_zurueck_im_verlauf_raeumt_ihn_weg(self):
        """Der Browser zeigt beim Zurückgehen die Seite aus dem
        Zwischenspeicher – mitsamt dem Hinweis, der dann nichts mehr
        meldet. `pageshow` ist das Ereignis, das auch in diesem Fall
        kommt; `load` nicht."""
        self.assertIn("pageshow", self.seite)
        self.assertIn('classList.remove("sucht")', self.seite)


class JedeSeiteTest(unittest.TestCase):
    """**Der Hinweis gehört in jede Seite, nicht in die Trefferliste.**

    Das Lesen einer Nachricht holt sie von der Platte, und bei einem
    großen Anhang ist das die spürbarere Wartezeit. Läge der Hinweis
    nur bei der Suche, fehlte er genau dort, wo am längsten gewartet
    wird.
    """

    def test_auch_die_anmeldeseite_hat_ihn(self):
        # Wer sich anmeldet, hat noch keinen Eindruck davon, ob das
        # Programm überhaupt antwortet.
        self.assertIn('id="laeufttext"', seiten.anmeldung())

    def test_und_die_fehlerseite(self):
        # Sie wird gebaut, wenn schon etwas schiefging – eine
        # halbfertige Seite wäre dort besonders ärgerlich.
        self.assertIn(
            'id="laeufttext"',
            seiten.fehlerseite("Nicht gefunden", "Diese Seite gibt es nicht."),
        )
