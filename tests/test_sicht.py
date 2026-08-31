"""Die Rechteprüfung in der Suche.

Der sicherheitskritische Teil der Server Edition. Geprüft wird deshalb
nicht, was ein Benutzer sieht – das fällt beim Benutzen auf –, sondern
was er **nicht** sieht. Und zwar bis hinunter zu den Zahlen: Eine
Trefferzahl, die mehr nennt als die Liste zeigt, verrät genau das, was
die Rechte verbergen sollen.
"""

from __future__ import annotations

import ast
import inspect
import tempfile
import unittest
from pathlib import Path

from mailburg.core.archive import Archive, Mode
from mailburg.core.benutzer import Benutzer
from mailburg.core.index import Index
from mailburg.core.sicht import Sicht


def _mail(betreff: str, absender: str = "wer@example.org") -> bytes:
    return (
        f"From: {absender}\r\n"
        f"To: martha@mailburg.example\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: Mon, 12 May 2025 09:14:00 +0000\r\n"
        f"Message-ID: <{abs(hash(betreff))}@example.org>\r\n"
        f"\r\n"
        f"Guten Tag, hier steht Rechnung.\r\n"
    ).encode()


class BedingungTest(unittest.TestCase):
    """Was die Sicht an SQL beiträgt."""

    def test_alles_ist_immer_wahr(self):
        self.assertEqual(Sicht.alles_sehen().bedingung(), ("1", []))

    def test_nichts_ist_immer_falsch(self):
        """Nicht »1«: Wer kein Postfach zugeordnet hat, findet nichts.

        Der umgekehrte Fehler wäre der schlimmste denkbare – ein neu
        angelegter Zugang ohne Rechte sähe alles.
        """
        self.assertEqual(Sicht.nichts_sehen().bedingung(), ("0", []))

    def test_die_bedingung_ist_nie_leer(self):
        """Sonst könnte sie jemand mit »if bedingung:« versehentlich weglassen."""
        for blick in (Sicht.alles_sehen(), Sicht.nichts_sehen(),
                      Sicht(alles=False, konten=frozenset({"a"}))):
            with self.subTest(sicht=blick):
                self.assertTrue(blick.bedingung()[0])

    def test_dieselbe_sicht_ergibt_dieselbe_abfrage(self):
        eine = Sicht(alles=False, konten=frozenset({"b", "a"}))
        andere = Sicht(alles=False, konten=frozenset({"a", "b"}))

        self.assertEqual(eine.bedingung(), andere.bedingung())

    def test_ein_stillgelegter_sieht_nichts(self):
        """Auch dann nicht, wenn bei ihm »alle Postfächer« steht."""
        alt = Benutzer("alt", alle_postfaecher=True, aktiv=False)

        self.assertEqual(Sicht.fuer(alt).bedingung(), ("0", []))

    def test_ohne_benutzer_gilt_alles(self):
        """Der Arbeitsplatz: Wer am Rechner sitzt, hat das Archiv ohnehin."""
        self.assertTrue(Sicht.fuer(None).unbeschraenkt)


class AmArchivTest(unittest.TestCase):
    """Die Wirkung an einem Archiv mit Post aus drei Postfächern."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.archiv = Archive.create(
            Path(self.ordner.name) / "Archiv", name="P", mode=Mode.GESCHAEFTLICH
        )
        self.addCleanup(self.archiv.close)

        for konto, betreffe in (
            ("buchhaltung", ["Rechnung Mai", "Rechnung Juni"]),
            ("vertrieb", ["Angebot", "Rechnung Kunde", "Nachfrage"]),
            ("geschaeftsfuehrung", ["Vertraulich"]),
        ):
            for betreff in betreffe:
                self.archiv.add(_mail(betreff), account=konto, folder="INBOX")

        self.nur_buchhaltung = Sicht(alles=False, konten=frozenset({"buchhaltung"}))

    def test_ohne_sicht_ist_alles_da(self):
        self.assertEqual(self.archiv.index.count(), 6)

    def test_die_suche_zeigt_nur_erlaubtes(self):
        treffer = self.archiv.index.search("", sicht=self.nur_buchhaltung)

        self.assertEqual(
            sorted(t.subject for t in treffer),
            ["Rechnung Juni", "Rechnung Mai"],
        )

    def test_die_trefferzahl_stimmt_mit_der_liste_ueberein(self):
        """Der eigentliche Punkt: keine Zahl, die mehr verspricht.

        Aus »6 Treffer, davon 2 sichtbar« liest jeder heraus, dass es
        vier weitere gibt.
        """
        gezaehlt = self.archiv.index.count(sicht=self.nur_buchhaltung)
        gefunden = self.archiv.index.search("", sicht=self.nur_buchhaltung)

        self.assertEqual(gezaehlt, len(gefunden))
        self.assertEqual(gezaehlt, 2)

    def test_auch_mit_suchbegriff(self):
        """Drei Betreffs nennen »Rechnung« – erlaubt sind zwei davon."""
        self.assertEqual(self.archiv.index.count("betreff:rechnung"), 3)
        self.assertEqual(
            self.archiv.index.count(
                "betreff:rechnung", sicht=self.nur_buchhaltung),
            2,
        )

    def test_wer_nichts_zugeordnet_hat_findet_nichts(self):
        leer = Sicht.nichts_sehen()

        self.assertEqual(self.archiv.index.count(sicht=leer), 0)
        self.assertEqual(self.archiv.index.search("", sicht=leer), [])
        self.assertEqual(self.archiv.index.search("rechnung", sicht=leer), [])

    def test_ein_fremdes_postfach_laesst_sich_nicht_erfragen(self):
        """`konto:` ist eine Suchhilfe, kein Schlüssel.

        Wer den Namen kennt und danach sucht, bekommt trotzdem nichts.
        """
        self.assertEqual(
            self.archiv.index.count(
                "konto:geschaeftsfuehrung", sicht=self.nur_buchhaltung
            ),
            0,
        )
        self.assertEqual(
            self.archiv.index.search(
                "konto:geschaeftsfuehrung", sicht=self.nur_buchhaltung
            ),
            [],
        )

    def test_der_postfachbaum_zeigt_nur_erlaubtes(self):
        """Schon die Namen der Postfächer verraten etwas."""
        konten = {k for k, _, _ in self.archiv.index.accounts(
            sicht=self.nur_buchhaltung)}

        self.assertEqual(konten, {"buchhaltung"})

    def test_die_zahlen_je_postfach_ebenso(self):
        summen = self.archiv.index.account_totals(sicht=self.nur_buchhaltung)

        self.assertEqual(summen, {"buchhaltung": 2})

    def test_die_gesamtzahl_unten_ist_fuer_jeden_eine_andere(self):
        alle = self.archiv.index.statistics()
        wenige = self.archiv.index.statistics(sicht=self.nur_buchhaltung)

        self.assertEqual(alle["mails"], 6)
        self.assertEqual(wenige["mails"], 2)
        self.assertLess(wenige["bytes"], alle["bytes"])

    def test_mehrere_postfaecher(self):
        zwei = Sicht(alles=False, konten=frozenset({"buchhaltung", "vertrieb"}))

        self.assertEqual(self.archiv.index.count(sicht=zwei), 5)

    def test_das_blaettern_bleibt_stimmig(self):
        """Sonst stünde auf Seite zwei, was auf Seite eins fehlte."""
        erste = self.archiv.index.search(
            "", limit=1, offset=0, sicht=self.nur_buchhaltung)
        zweite = self.archiv.index.search(
            "", limit=1, offset=1, sicht=self.nur_buchhaltung)
        dritte = self.archiv.index.search(
            "", limit=1, offset=2, sicht=self.nur_buchhaltung)

        self.assertEqual(len(erste), 1)
        self.assertEqual(len(zweite), 1)
        self.assertEqual(dritte, [])
        self.assertNotEqual(erste[0].hash, zweite[0].hash)


class MehrfachTest(unittest.TestCase):
    """Eine Mail kann in mehreren Postfächern liegen.

    Bei Rundmails ist das der Normalfall. Wer eines davon sehen darf,
    darf die Mail sehen – aber die übrigen Fundorte dürfen dabei nicht
    zum Vorschein kommen.
    """

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.archiv = Archive.create(
            Path(self.ordner.name) / "Archiv", name="P", mode=Mode.GESCHAEFTLICH
        )
        self.addCleanup(self.archiv.close)

        rundmail = _mail("An alle")
        self.archiv.add(rundmail, account="buchhaltung", folder="INBOX")
        self.archiv.add(rundmail, account="geschaeftsfuehrung", folder="INBOX")

        self.nur_buchhaltung = Sicht(alles=False, konten=frozenset({"buchhaltung"}))

    def test_die_mail_ist_sichtbar(self):
        treffer = self.archiv.index.search("", sicht=self.nur_buchhaltung)

        self.assertEqual([t.subject for t in treffer], ["An alle"])

    def test_sie_wird_nur_einmal_gezaehlt(self):
        """Zwei Fundorte, eine Mail – sonst stimmte die Zahl nicht."""
        self.assertEqual(self.archiv.index.count(sicht=self.nur_buchhaltung), 1)

    def test_der_zweite_fundort_bleibt_verborgen(self):
        konten = {k for k, _, _ in self.archiv.index.accounts(
            sicht=self.nur_buchhaltung)}

        self.assertEqual(konten, {"buchhaltung"})

    def test_auch_in_den_kennzahlen(self):
        """Zwei Fundorte zu melden, verriete das zweite Postfach."""
        zahlen = self.archiv.index.statistics(sicht=self.nur_buchhaltung)

        self.assertEqual(zahlen["mails"], 1)
        self.assertEqual(zahlen["fundorte"], 1)


class KeineLuecken(unittest.TestCase):
    """Was leicht vergessen wird, wenn später etwas dazukommt."""

    #: Lesende Methoden, die eine Sicht annehmen müssen. Wer eine neue
    #: hinzufügt, trägt sie hier ein – und merkt dabei, dass sie eine
    #: braucht.
    MUESSEN_FILTERN = (
        "search", "count", "accounts", "account_totals", "statistics",
        # Am 2026-08-31 dazugekommen, für den lesenden Zugriff im
        # Browser – und prompt von diesem Test gemeldet, weil sie hier
        # noch fehlte. Genau dafür ist er da.
        "nachricht",
    )

    #: Und diese ausdrücklich nicht. Sie beantworten keine Frage eines
    #: Menschen, sondern dienen dem Abgleich mit der Ablage und dem
    #: Abruf – dort gibt es keinen Benutzer, dem etwas verborgen bliebe.
    OHNE_SICHT = (
        "known_hashes", "has_location", "max_uid", "uids_im_ordner",
    )

    def test_jede_lesende_methode_nimmt_eine_sicht(self):
        for name in self.MUESSEN_FILTERN:
            with self.subTest(methode=name):
                unterschrift = inspect.signature(getattr(Index, name))
                self.assertIn(
                    "sicht", unterschrift.parameters,
                    f"Index.{name}() kennt keine Sicht – dort ließe sich "
                    f"vorbeisehen",
                )

    def test_die_ausnahmen_gibt_es_wirklich(self):
        """Sonst steht hier eine Ausnahme für etwas Verschwundenes."""
        for name in self.OHNE_SICHT:
            with self.subTest(methode=name):
                self.assertTrue(hasattr(Index, name))

    def test_keine_lesende_methode_fehlt_in_einer_der_beiden_listen(self):
        """Damit eine neue Abfrage nicht stillschweigend ungefiltert bleibt."""
        quelle = Path(Index.__module__.replace(".", "/") + ".py")
        baum = ast.parse(quelle.read_text(encoding="utf-8"))
        klasse = next(
            k for k in baum.body
            if isinstance(k, ast.ClassDef) and k.name == "Index"
        )

        # Methoden, die eine SELECT-Abfrage enthalten und nach außen
        # führen – Schreibvorgänge und Innereien bleiben außen vor.
        schreibend = {
            "add", "remove", "set_category", "commit", "optimize", "close",
            "ordner_umbenennen", "_mit_sicht",
        }
        lesend = set()
        for stueck in klasse.body:
            if not isinstance(stueck, ast.FunctionDef):
                continue
            if stueck.name.startswith("__") or stueck.name in schreibend:
                continue
            quelltext = ast.dump(stueck)
            if "SELECT" in quelltext or "select" in quelltext:
                lesend.add(stueck.name)

        unbekannt = lesend - set(self.MUESSEN_FILTERN) - set(self.OHNE_SICHT)
        self.assertEqual(
            unbekannt, set(),
            f"Neue lesende Methoden: {sorted(unbekannt)}. Entweder eine "
            f"Sicht einbauen oder in OHNE_SICHT eintragen – mit Begründung.",
        )


if __name__ == "__main__":
    unittest.main()
