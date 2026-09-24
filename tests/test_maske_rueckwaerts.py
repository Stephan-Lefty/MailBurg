"""Vom Suchausdruck zurück in die Maske.

**Von joka63 angestoßen (2026-09-22).** Wer einen gespeicherten
Suchordner bearbeitet und auf *Ausführlich …* geht, erwartet die Felder
gefüllt. Er hatte es zuerst selbst gebaut, indem er die Feldwerte
zusätzlich ablegte – und war damit unzufrieden: zwei Quellen für
dieselbe Sache laufen auseinander.

**Und er hat die bessere Bauform gleich mitgeliefert (2026-09-23):** Den
Knopf nur anbieten, wenn die Umwandlung gelingt. Die Maske schreibt
zurück; was sie nicht darstellen kann, wäre nach einem OK still weg.
Statt diesen Sonderfall zu erklären, gibt es ihn nicht.

Der wichtigste Test hier ist deshalb nicht die Rundreise **Felder →
Ausdruck → Felder**, sondern die Gegenrichtung: **Ausdruck → Felder →
Ausdruck** für alles, was `felder()` als machbar meldet. Genau darauf
verlässt sich der Knopf, wenn er sich anbietet.
"""

from __future__ import annotations

import itertools
import unittest

from mailburg.search.maske import FELDER, ausdruck, felder


class HinUndZurueck(unittest.TestCase):
    """Felder → Ausdruck → Felder, für alles, was die Maske erzeugt."""

    #: Ein plausibler Wert je Feld, nach Art.
    PROBEN = {
        "begriff": ("rechnung", "offene posten"),
        "von": ("telekom", "müller@example.org"),
        "an": ("info@example.org",),
        "betreff": ("Rechnung", "offene Posten"),
        "datei": ("*.pdf",),
        "konto": ("Firma",),
        "ordner": ("Gesendet",),
        "jahr": ("2025", "2020-2024"),
        "seit": ("01.01.2026",),
        "bis": ("31.03.2026",),
        "archiviert": ("2026",),
        "mit_anhang": ("1",),
        "typ": ("pdf",),
        "groesse": (">5MB", "<100KB"),
        "wichtigkeit": ("hoch",),
        "ohne": ("werbung", "werbung newsletter"),
    }

    def test_jedes_feld_einzeln(self) -> None:
        for feld in FELDER:
            for wert in self.PROBEN[feld.name]:
                with self.subTest(feld=feld.name, wert=wert):
                    eingabe = {feld.name: wert}
                    zurueck = felder(ausdruck(eingabe))
                    self.assertEqual(zurueck, eingabe)

    def test_paare_von_feldern(self) -> None:
        """Zwei Felder gleichzeitig – so sucht man wirklich."""
        namen = [f.name for f in FELDER]
        for a, b in itertools.combinations(namen, 2):
            eingabe = {a: self.PROBEN[a][0], b: self.PROBEN[b][0]}
            with self.subTest(felder=(a, b)):
                self.assertEqual(felder(ausdruck(eingabe)), eingabe)

    def test_alle_felder_zugleich(self) -> None:
        eingabe = {name: werte[0] for name, werte in self.PROBEN.items()}
        self.assertEqual(felder(ausdruck(eingabe)), eingabe)

    def test_leer_bleibt_leer(self) -> None:
        self.assertEqual(felder(""), {})
        self.assertEqual(felder("   "), {})


class ZurueckUndHin(unittest.TestCase):
    """**Die Zusage, auf die sich der Knopf verlässt.**

    Meldet `felder()` »das geht«, darf beim Zurückbauen nichts
    verlorengehen. Sonst öffnet sich die Maske genau dort, wo der
    Verlust als ausgeschlossen galt – und beim OK verschwindet ein
    Stück Suchausdruck, ohne dass jemand es merkt.
    """

    AUSDRUECKE = (
        "rechnung",
        "von:telekom",
        "von:telekom betreff:Rechnung",
        '"offene posten"',
        '"offene posten" jahr:2025',
        "hat:anhang",
        "hat:anhang typ:pdf",
        "-werbung",
        "-werbung -newsletter",
        "konto:Firma ordner:Gesendet",
        "groesse:>5MB",
        "seit:01.01.2026 bis:31.03.2026",
        "wichtigkeit:hoch",
        "jahr:2020-2024",
    )

    def test_wer_umwandelbar_ist_kommt_unveraendert_zurueck(self) -> None:
        for text in self.AUSDRUECKE:
            with self.subTest(ausdruck=text):
                werte = felder(text)
                self.assertIsNotNone(werte, f"{text!r} sollte umwandelbar sein")
                self.assertEqual(sorted(ausdruck(werte).split()),
                                 sorted(text.split()))


class NichtAbbildbar(unittest.TestCase):
    """Was die Maske nicht kann, muss ``None`` ergeben.

    Jeder Fall hier ist einer, in dem der Knopf ausgegraut gehört.
    """

    def test_zwei_freie_woerter(self) -> None:
        """**Der wichtigste Fall, und der unauffälligste.**

        ``rechnung müller`` sind zwei Bedingungen (beide müssen
        zutreffen). Die Maske hat nur ein Begriffsfeld und machte daraus
        ``"rechnung müller"`` – eine Phrase, und damit eine andere
        Suche. Wer das übersieht, ändert stillschweigend, was der
        Suchordner findet.
        """
        self.assertIsNone(felder("rechnung müller"))

    def test_dasselbe_feld_zweimal(self) -> None:
        self.assertIsNone(felder("von:a von:b"))

    def test_wort_ohne_maskenfeld(self) -> None:
        """Die Suchsprache kann mehr als die Maske – das ist Absicht."""
        self.assertIsNone(felder("ist:ungelesen"))

    def test_verneintes_feld(self) -> None:
        """»-von:telekom« erzeugt die Maske nicht; ihr »ohne« ist Freitext."""
        self.assertIsNone(felder("-von:telekom"))

    def test_verneinte_phrase(self) -> None:
        self.assertIsNone(felder('-"offene posten"'))

    def test_freitext_und_phrase_gemischt(self) -> None:
        self.assertIsNone(felder('rechnung "offene posten"'))


if __name__ == "__main__":
    unittest.main()
