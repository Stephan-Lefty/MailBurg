"""Mails mit gefälschtem Datum kleben nicht mehr oben.

**Der Befund stammt aus dem Betrieb, nicht aus einem Test.** Im
Firmenarchiv stehen seit Wochen zwei Spam-Nachrichten mit den Jahren
2029 und 2030 über jeder echten Mail – sortiert wird nach ``m.date``,
und eine Plausibilitätsprüfung gab es nicht. Stephan am 04.11.2026,
mit einem Bildschirmfoto.

**Die Regel dahinter ist einfach und prüfbar:** Eine Mail kann kein
Datum tragen, das *nach* ihrer Aufnahme ins Archiv liegt – sie war ja
vorher da. Steht dort trotzdem eines, ist es gefälscht oder von einem
kaputten Mailprogramm gesetzt. Sortiert wird dann nach dem Zeitpunkt
der Aufnahme.

**Angezeigt bleibt das echte Datum.** In einem Archivprogramm wäre
alles andere eine Verfälschung; hier wird ausschließlich die
Reihenfolge der Liste bestimmt.

**Verworfen, und zwar nach einer Messung:** derselbe Effekt über
``ORDER BY MIN(date, jetzt)``. Das braucht keine Spalte – macht aber
jeden Index unbrauchbar. An 600.000 Zeilen gemessen: 78 ms statt
0,15 ms, also das Vierhundertfache. Mit eigener Spalte und eigenem
Index bleibt es bei 0,15 ms.
"""

from __future__ import annotations

import pathlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone


def _mail(betreff: str, datum: str, kennung: str) -> bytes:
    return (
        f"From: Absender <post@example.org>\r\n"
        f"To: empfang@example.net\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: {datum}\r\n"
        f"Message-ID: <{kennung}@example.org>\r\n"
        f"\r\n"
        f"Inhalt von {betreff}.\r\n"
    ).encode()


def _aufnehmen(index, betreff: str, datum: str, kennung: str,
               archiviert: str) -> None:
    """Legt eine Mail mit frei gewähltem Aufnahmezeitpunkt ab.

    **Über ``index.add`` und nicht über ``Archive.add``**, weil der
    Zeitpunkt sonst immer »jetzt« wäre – und damit ließe sich die
    fragliche Lage nicht nachstellen: Im Firmenarchiv liegen die
    beiden Spam-Nachrichten seit dem 07.10.2026, während laufend neue
    Post dazukommt.

    Ein Test, der alles im selben Augenblick aufnimmt, misst etwas
    anderes. Das war der erste Anlauf hier, und er war grün an der
    falschen Stelle.
    """
    from mailburg.extract.message import parse

    roh = _mail(betreff, datum, kennung)
    index.add(
        digest=f"hash-{kennung}", bucket="ab", parsed=parse(roh),
        size=len(roh), account="probe", folder="INBOX",
        archiviert=archiviert,
    )


#: Der Tag, an dem im Firmenarchiv 589.058 Mails in einem Zug
#: aufgenommen wurden – und mit ihnen die beiden gefälschten.
UMZUG = "2026-10-07T12:00:00+02:00"

#: Und ein Abruf von danach.
SPAETER = "2026-11-04T08:00:00+01:00"


class SortierungTest(unittest.TestCase):
    """Die Trefferliste, an einem echten Archiv."""

    def setUp(self):
        from mailburg.core.archive import Archive

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "Probe"
        Archive.create(self.pfad).close()

        # Die Lage im Firmenarchiv: Altbestand aus dem Umzug, darunter
        # eine Mail mit gefälschtem Datum – und danach laufend neue
        # Post, die obenauf gehört.
        with Archive.open(self.pfad) as archiv:
            _aufnehmen(archiv.index, "Alt",
                       "Mon, 03 Mar 2025 10:00:00 +0100", "alt", UMZUG)
            _aufnehmen(archiv.index, "Spam",
                       "Thu, 01 Mar 2029 10:00:00 +0100", "spam", UMZUG)
            _aufnehmen(archiv.index, "Neu",
                       "Wed, 04 Nov 2026 08:00:00 +0100", "neu", SPAETER)
            archiv.index.commit()

    def _betreffs(self) -> list[str]:
        from mailburg.core.archive import Archive

        with Archive.open(self.pfad) as archiv:
            return [t.subject for t in archiv.index.search("")]

    def test_die_mail_aus_der_zukunft_steht_nicht_oben(self):
        """**Der Befund selbst.** Vor dem 27.11.2026 stand »Spam« an
        erster Stelle, und zwar dauerhaft – jeden Tag, bei jeder
        Suche, über jeder echten Nachricht."""
        self.assertNotEqual(self._betreffs()[0], "Spam")

    def test_die_echten_mails_stehen_in_ihrer_reihenfolge(self):
        """Die neueste zuerst – daran ändert sich nichts."""
        betreffs = self._betreffs()

        self.assertEqual(betreffs[0], "Neu")
        self.assertLess(betreffs.index("Neu"), betreffs.index("Alt"))

    def test_sie_verschwindet_aber_nicht(self):
        """**Verstecken wäre der falsche Weg.** Was im Archiv liegt,
        muss auffindbar bleiben – auch Spam; gerade bei einer
        Aufbewahrungspflicht entscheidet nicht die Plausibilität des
        Absenders darüber, was man wiederfindet."""
        self.assertIn("Spam", self._betreffs())

    def test_angezeigt_wird_das_echte_datum(self):
        """**Hier wird sortiert, nicht korrigiert.** Ein
        Archivprogramm, das Datumsangaben in den Daten verändert,
        hätte sein Versprechen gebrochen – und die Fälschung wäre
        hinterher nicht mehr erkennbar."""
        from mailburg.core.archive import Archive

        with Archive.open(self.pfad) as archiv:
            treffer = {t.subject: t for t in archiv.index.search("")}

        self.assertTrue(str(treffer["Spam"].date).startswith("2029"),
                        f"angezeigt wird {treffer['Spam'].date}")


class SortdatumTest(unittest.TestCase):
    """Was in der Spalte steht – nachgesehen, nicht angenommen."""

    def setUp(self):
        from mailburg.core.archive import Archive

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.pfad = pathlib.Path(self.ordner.name) / "Probe"
        Archive.create(self.pfad).close()

    def _spalten(self) -> list[tuple]:
        from mailburg.core.archive import Archive

        with Archive.open(self.pfad) as archiv:
            return archiv.index.db.execute(
                "SELECT subject, date, archiviert, sortdatum FROM messages"
            ).fetchall()

    def test_ein_glaubwuerdiges_datum_bleibt_stehen(self):
        from mailburg.core.archive import Archive

        with Archive.open(self.pfad) as archiv:
            archiv.add(_mail("Normal", "Mon, 03 Mar 2025 10:00:00 +0100", "n"),
                       account="probe", folder="INBOX")

        betreff, datum, _, sortdatum = self._spalten()[0]
        self.assertEqual(betreff, "Normal")
        self.assertEqual(sortdatum, datum)

    def test_ein_datum_nach_der_aufnahme_wird_gedeckelt(self):
        """**Die Positionsnummern im INSERT stimmen.** Der Ausdruck
        rechnet mit ``?3`` und ``?12``; wer oben eine Spalte einfügt,
        verschiebt beide. Ein vertauschtes Paar fiele sonst erst
        jemandem auf, dessen Trefferliste durcheinandergerät."""
        from mailburg.core.archive import Archive

        with Archive.open(self.pfad) as archiv:
            archiv.add(_mail("Zukunft", "Thu, 01 Mar 2029 10:00:00 +0100", "z"),
                       account="probe", folder="INBOX")

        _, datum, archiviert, sortdatum = self._spalten()[0]
        self.assertEqual(sortdatum, archiviert)
        self.assertNotEqual(sortdatum, datum)
        self.assertLess(sortdatum, datum)

    def test_eine_mail_ohne_datum_bleibt_ohne(self):
        """Es gibt Post ohne ``Date:``-Kopfzeile. Ein erfundenes
        Sortierdatum wäre schlimmer als gar keines – NULL rutscht ans
        Ende der Liste, und dort gehört eine undatierte Mail hin."""
        from mailburg.core.archive import Archive

        roh = (b"From: a@example.org\r\nTo: b@example.net\r\n"
               b"Subject: Ohne Datum\r\n\r\nText.\r\n")
        with Archive.open(self.pfad) as archiv:
            archiv.add(roh, account="probe", folder="INBOX")

        _, datum, _, sortdatum = self._spalten()[0]
        self.assertIsNone(datum)
        self.assertIsNone(sortdatum)


class NachruestenTest(unittest.TestCase):
    """Ein Index aus einer älteren Fassung bekommt die Spalte gefüllt.

    **Sonst stünde der ganze Altbestand auf NULL** – und in SQLite ist
    NULL der kleinste Wert. Bei absteigender Sortierung rutschte jede
    vorhandene Mail ans Ende: Der Index wäre nicht kaputt, er sähe nur
    leer aus. Genau die Sorte Fehler, die wie ein Datenverlust
    aussieht und keiner ist.
    """

    def test_der_altbestand_bekommt_sein_sortdatum(self):
        """**Der Altbestand wird über ein gekürztes Schema erzeugt**,
        nicht über ``ALTER TABLE … DROP COLUMN``.

        Der erste Anlauf tat genau das – und war lokal grün, in der
        CI rot:

            sqlite3.OperationalError: error in table messages after
            drop column: incomplete input

        SQLite liest beim Entfernen einer Spalte die gespeicherte
        ``CREATE TABLE``-Anweisung neu ein, und das Schema dieses
        Projekts ist voller ``--``-Kommentare. Ältere Fassungen
        kommen damit nicht zurecht. *Nebenbefund, der hier
        festgehalten gehört: In diesem Index lässt sich keine Spalte
        entfernen, solange die Kommentare dort stehen.*
        """
        import sqlite3

        from mailburg.core.archive import Archive
        from mailburg.core import index as index_modul

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        pfad = pathlib.Path(ordner.name) / "Probe"
        Archive.create(pfad).close()

        # Ein Index, wie ihn die Fassung vor dieser gebaut hätte: ohne
        # die Spalte und ohne ihren Index.
        #
        # **Mitsamt dem Kommentarblock davor und dem Komma dahinter.**
        # Ein schlichtes Suchmuster traf daneben, weil zwischen der
        # vorigen Spalte und dieser zwanzig Zeilen Begründung stehen –
        # und ein zeilenweiser Filter ließ ein Komma vor der
        # schließenden Klammer zurück. Beide Male meldete nicht der
        # Test den Fehler, sondern SQLite.
        import re

        ohne = re.sub(
            r",\n(?:[ \t]*--.*\n)*[ \t]*sortdatum\s+TEXT\n\);",
            "\n);", index_modul._SCHEMA)
        ohne = "\n".join(z for z in ohne.splitlines()
                         if "sortdatum" not in z)
        self.assertNotIn("sortdatum", ohne,
                         "Das Schema sieht anders aus als angenommen")

        with Archive.open(pfad) as archiv:
            ort = archiv.index.path
        sqlite3.connect(ort).close()
        import os

        os.remove(ort)
        db = sqlite3.connect(ort)
        db.executescript(ohne)
        db.commit()
        db.close()

        with Archive.open(pfad) as archiv:
            _aufnehmen(archiv.index, "Alt",
                       "Mon, 03 Mar 2025 10:00:00 +0100", "a", UMZUG)
            _aufnehmen(archiv.index, "Falsch",
                       "Thu, 01 Mar 2029 10:00:00 +0100", "f", UMZUG)
            _aufnehmen(archiv.index, "Neu",
                       "Wed, 04 Nov 2026 08:00:00 +0100", "n", SPAETER)
            archiv.index.commit()

        # Und jetzt öffnen – dabei muss das Nachrüsten greifen.
        with Archive.open(pfad) as archiv:
            zeilen = dict(archiv.index.db.execute(
                "SELECT subject, sortdatum FROM messages"))
            archiviert = dict(archiv.index.db.execute(
                "SELECT subject, archiviert FROM messages"))
            betreffs = [t.subject for t in archiv.index.search("")]

        self.assertIsNotNone(zeilen["Alt"], "Die Spalte blieb leer")
        self.assertEqual(zeilen["Falsch"], archiviert["Falsch"],
                         "Das gefälschte Datum wurde nicht gedeckelt")
        self.assertNotEqual(betreffs[0], "Falsch")

    def test_zweimal_oeffnen_rechnet_nicht_zweimal(self):
        """**Das Füllen läuft einmal, beim ersten Öffnen danach.** Bei
        einer halben Million Mails ist es eine knappe Sekunde – jedes
        Mal wäre es eine Sekunde zu viel, und schlimmer: Ein zweiter
        Lauf überschriebe ein inzwischen von Hand korrigiertes
        Sortierdatum."""
        from unittest import mock

        from mailburg.core.archive import Archive
        from mailburg.core.index import Index

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        pfad = pathlib.Path(ordner.name) / "Probe"
        Archive.create(pfad).close()

        with mock.patch.object(
                Index, "_frisch_gefuellt", autospec=True) as gefuellt:
            with Archive.open(pfad) as archiv:
                archiv.add(_mail("A", "Mon, 03 Mar 2025 10:00:00 +0100", "a"),
                           account="probe", folder="INBOX")
            with Archive.open(pfad):
                pass

        aufrufe = [a.args[2] for a in gefuellt.call_args_list]
        self.assertNotIn("sortdatum", aufrufe,
                         f"beim Öffnen eines fertigen Index gefüllt: {aufrufe}")


class SummeTest(unittest.TestCase):
    """Die Mailgrößen auf der Statusseite – ohne vollen Tabellenscan.

    Der Dienst zeigt die Summe bei jedem Aufruf von ``/zustand``.
    Ohne eigenen Index liest SQLite dafür jede Zeile mit allen
    Spalten; mit ihm nur den schlanken Index. Gemessen an 600.000
    Zeilen am 27.11.2026: 19 ms statt 46 – und das warm. Kalt
    entscheidet, wie viele Bytes von der Platte kommen.
    """

    def test_die_summe_liest_nur_den_index(self):
        from mailburg.core.archive import Archive

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        pfad = pathlib.Path(ordner.name) / "Probe"
        Archive.create(pfad).close()

        with Archive.open(pfad) as archiv:
            archiv.add(_mail("A", "Mon, 03 Mar 2025 10:00:00 +0100", "a"),
                       account="probe", folder="INBOX")
            plan = " ".join(
                zeile[3] for zeile in archiv.index.db.execute(
                    "EXPLAIN QUERY PLAN "
                    "SELECT COALESCE(SUM(size), 0) FROM messages"))

        self.assertIn("COVERING INDEX", plan,
                      f"Die Summe läuft über einen vollen Scan: {plan}")

    def test_und_sie_stimmt(self):
        """Ein Plan allein ist kein Ergebnis."""
        from mailburg.core.archive import Archive

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        pfad = pathlib.Path(ordner.name) / "Probe"
        Archive.create(pfad).close()

        roh = [_mail(f"M{i}", "Mon, 03 Mar 2025 10:00:00 +0100", f"m{i}")
               for i in range(3)]
        with Archive.open(pfad) as archiv:
            for mail in roh:
                archiv.add(mail, account="probe", folder="INBOX")
            gemeldet = archiv.index.statistics()["bytes"]

        self.assertEqual(gemeldet, sum(len(m) for m in roh))


if __name__ == "__main__":
    unittest.main()
