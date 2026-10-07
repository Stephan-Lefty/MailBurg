"""Eine fehlende Mail muss man wiedererkennen können.

**Der Anlass kommt aus dem Betrieb (07.10.2026).** Nach der Übernahme
von 827.198 Mails aus MailStore meldete ``mailburg pruefen`` am
Geschäftsarchiv:

```
  FEHLEND:     2 Mails ohne Datei
    - 5286d60406624ea9…
    - 62b660a453bf565d…
```

**Mehr stand da nicht.** Welche Mails das sind, aus welchem Postfach,
von wann – alles das steht im Journal direkt daneben
(``archive.py:683`` schreibt ``account``, ``folder``, ``date``,
``sender``, ``subject`` in jeden Eintrag) und wurde nicht ausgegeben.
Herauszubekommen war es nur über ein Python-Schnipsel gegen das
Journal.

**Das ist die teure Sorte Lücke.** Bei geschäftlicher Post ist die
erste Frage nach einem solchen Befund nicht »wie viele«, sondern
»welche« – davon hängt ab, ob sie aus einer Sicherung zu holen sind,
ob eine Aufbewahrungsfrist betroffen ist und was im Übernahmeprotokoll
steht. Ausgerechnet das Werkzeug für den Schadensfall ließ den Anwender
mit zwei Hexzahlen stehen.

**Und ein Unterschied, an dem die ganze Ursachensuche hing:** ``date``
ist das Datum *der Mail*, ``ts`` der Zeitpunkt *der Aufnahme*. Beide
Mails trugen den 02.10. im Kopf; aufgenommen wurden sie ebenfalls am
02.10., nicht beim Umzug drei Tage später. Erst das hat die naheliegende
Erklärung widerlegt.
"""

from __future__ import annotations

import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from mailburg.core.archive import Archive

MAIL = (
    b"From: partner@beispiel.example\r\n"
    b"To: mueller@firma.example\r\n"
    b"Subject: {betreff}\r\n"
    b"Message-ID: <{nr}@beispiel.example>\r\n"
    b"Date: Fri, 2 Oct 2026 15:45:56 +0200\r\n"
    b"\r\nInhalt {nr}.\r\n"
)


def _mail(nr: int, betreff: str = "Reklamation") -> bytes:
    return (MAIL
            .replace(b"{nr}", str(nr).encode())
            .replace(b"{betreff}", betreff.encode()))


class FehlendeMailsTest(unittest.TestCase):
    """Die Angaben kommen aus dem Journal, nicht aus dem Index.

    **Mit Absicht so.** Der Index ist Beiwerk und wegwerfbar; wenn eine
    Mail fehlt, ist ohnehin fraglich, was noch stimmt. Das Journal ist
    die Wahrheit – und es ist die einzige Quelle, die auch dann noch
    Auskunft gibt, wenn der Index neu gebaut wurde und die fehlende
    Mail dabei stillschweigend hinausfiel.
    """

    def setUp(self) -> None:
        from mailburg.core import paths

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.basis = Path(self._tmp.name)
        for name in ("data_dir", "config_dir"):
            patcher = mock.patch.object(
                paths, name, return_value=self.basis / name
            )
            patcher.start()
            self.addCleanup(patcher.stop)
            (self.basis / name).mkdir(parents=True, exist_ok=True)

        self.wurzel = self.basis / "Archiv"
        with Archive.create(self.wurzel, name="Firma") as archiv:
            for nr in range(3):
                archiv.add(
                    _mail(nr, f"Reklamation {nr}"),
                    account="mueller@firma.example",
                    folder="INBOX",
                )
            self.verlorene = archiv.add(
                _mail(99, "AW: Reklamation - Türmuschelgriff"),
                account="mueller@firma.example",
                folder="INBOX/Reklamationen",
            )

    def _datei_wegnehmen(self) -> None:
        """Nimmt die Datei weg, ohne das Journal anzufassen.

        Das ist genau der Zustand vom 07.10.2026: Der Eintrag steht, die
        Datei ist fort. Ein Löschen über MailBurg sähe anders aus – es
        setzt einen Grabstein, und dann fehlt die Mail zu Recht.
        """
        with Archive.open(self.wurzel) as archiv:
            pfad = archiv.store.path_for(
                self.verlorene.hash, self.verlorene.bucket
            )
        treffer = list(pfad.parent.glob(pfad.name + "*"))
        self.assertEqual(len(treffer), 1, "Prüfaufbau: Datei nicht gefunden")
        treffer[0].unlink()

    def test_ohne_schaden_bleibt_die_liste_leer(self):
        """**Kein zweiter Journaldurchlauf im Regelbetrieb.** Er wäre bei
        einem großen Archiv teuer und beantwortet eine Frage, die
        niemand gestellt hat."""
        with Archive.open(self.wurzel, exclusive=False) as archiv:
            with mock.patch.object(
                archiv.journal, "read_all", wraps=archiv.journal.read_all
            ) as gelesen:
                befund = archiv.verify()
                vorher = gelesen.call_count

        self.assertTrue(befund["ok"])
        self.assertEqual(befund["fehlend"], [])
        # Einmal liest verify() das Journal für die Erwartungsliste.
        self.assertEqual(vorher, 1)

    def test_die_angaben_stehen_im_befund(self):
        self._datei_wegnehmen()

        with Archive.open(self.wurzel, exclusive=False) as archiv:
            befund = archiv.verify()

        self.assertEqual(len(befund["fehlend"]), 1)
        mail = befund["fehlend"][0]
        self.assertEqual(mail["hash"], self.verlorene.hash)
        self.assertEqual(mail["account"], "mueller@firma.example")
        self.assertEqual(mail["folder"], "INBOX/Reklamationen")
        self.assertIn("Türmuschelgriff", mail["subject"])
        self.assertEqual(mail["sender"], "partner@beispiel.example")

    def test_maildatum_und_aufnahme_sind_zweierlei(self):
        """**Der Unterschied, an dem am 07.10.2026 die Ursachensuche
        hing.** ``date`` steht im Kopf der Mail und kann Jahre zurück
        liegen; ``ts`` sagt, wann MailBurg sie aufgenommen hat. Nur das
        Zweite beantwortet die Frage »wann ist das passiert«.
        """
        self._datei_wegnehmen()

        with Archive.open(self.wurzel, exclusive=False) as archiv:
            mail = archiv.verify()["fehlend"][0]

        self.assertTrue(mail["date"].startswith("2026-10-02"))
        self.assertTrue(mail["ts"])
        self.assertNotEqual(mail["date"], mail["ts"])
        self.assertIsInstance(mail["seq"], int)

    def test_ohne_journaleintrag_bleibt_der_hash_stehen(self):
        """**Eine Mail darf nicht aus dem Befund fallen**, weil die
        Auskunft über sie fehlt. Das wäre der schlimmere Fall, nicht der
        harmlosere."""
        with Archive.open(self.wurzel, exclusive=False) as archiv:
            fehlend = archiv._fehlende_beschreiben(["a" * 64])

        self.assertEqual(fehlend, [{"hash": "a" * 64}])

    def test_die_reihenfolge_bleibt(self):
        """Der Befund zählt dieselben Mails in derselben Ordnung wie
        ``missing`` – sonst zeigt die Liste auf andere als die Zahl
        darüber."""
        self._datei_wegnehmen()

        with Archive.open(self.wurzel, exclusive=False) as archiv:
            befund = archiv.verify()

        self.assertEqual(
            [m["hash"] for m in befund["fehlend"]], befund["missing"]
        )


class AusgabeTest(unittest.TestCase):
    """Was ``mailburg pruefen`` davon auf den Bildschirm bringt."""

    def _ausgabe(self, mail: dict) -> str:
        from mailburg.__main__ import _fehlende_mail_nennen

        with mock.patch("sys.stdout", new=StringIO()) as gefangen:
            _fehlende_mail_nennen(mail)
        return gefangen.getvalue()

    def test_alles_wesentliche_steht_da(self):
        text = self._ausgabe({
            "hash": "5286d60406624ea9" + "0" * 48,
            "seq": 70763,
            "ts": "2026-10-02T13:59:05+00:00",
            "account": "mueller@firma.example",
            "folder": "INBOX",
            "date": "2026-10-02T15:45:56+02:00",
            "sender": "partner@beispiel.example",
            "subject": "WG: Einkaufspreis für die OVL XL",
        })

        self.assertIn("5286d60406624ea9", text)
        self.assertIn("mueller@firma.example", text)
        self.assertIn("INBOX", text)
        self.assertIn("02.10.2026", text)
        self.assertIn("partner@beispiel.example", text)
        self.assertIn("Einkaufspreis", text)
        self.assertIn("70763", text)

    def test_der_aufnahmezeitpunkt_ist_als_solcher_benannt(self):
        """**Zwei Datumsangaben in einer Ausgabe brauchen Beschriftung.**
        Sonst liest man die eine als die andere – genau der Fehler, den
        ich am 07.10.2026 selbst gemacht habe."""
        text = self._ausgabe({
            "hash": "a" * 64,
            "ts": "2026-10-05T18:46:40+00:00",
            "date": "2026-10-02T15:45:56+02:00",
        })

        self.assertIn("aufgenommen", text)

    def test_ein_langer_betreff_wird_gekuerzt(self):
        """Weitergeleitete Ketten aus Geschäftspost sprengen jede Zeile;
        das Journal hält 200 Zeichen."""
        lang = "AW: Reklamation - " + "Türmuschelgriff für Sporthallentür " * 6
        text = self._ausgabe({"hash": "b" * 64, "subject": lang})

        self.assertIn("Reklamation", text)
        self.assertIn("…", text)
        self.assertTrue(
            max(len(zeile) for zeile in text.splitlines()) < 100,
            f"zu lange Zeile in:\n{text}",
        )

    def test_mit_nichts_als_dem_hash_bricht_es_nicht(self):
        """Der Rückfall, wenn das Journal keine Auskunft gibt."""
        text = self._ausgabe({"hash": "c" * 64})

        self.assertIn("cccccccccccccccc", text)
        self.assertTrue(text.endswith("\n"))

    def test_fehlende_werden_gedeckelt(self):
        """**Bei einem größeren Schaden keine Bildschirmflut.** Die
        Gesamtzahl steht in der Zeile darüber; was darunter folgt, soll
        sie erläutern und nicht verdecken.
        """
        from mailburg.__main__ import FEHLENDE_NENNEN

        self.assertGreater(FEHLENDE_NENNEN, 0)
        self.assertLessEqual(FEHLENDE_NENNEN, 25)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
