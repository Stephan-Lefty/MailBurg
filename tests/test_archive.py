"""Tests für das Archiv als Ganzes – Ablage, Journal und Index im Zusammenspiel.

Hier hängt der Suchindex mit drin, deshalb wird sein Ablageort auf ein
Wegwerfverzeichnis umgebogen. Sonst schriebe der Testlauf in das echte
Benutzerverzeichnis.
"""

from __future__ import annotations

import email.utils
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from mailburg.core import paths
from mailburg.core.archive import Archive, ArchiveError, ArchiveLocked, Mode, RetentionLocked
from mailburg.core.retention import Jurisdiction


def probe(betreff: str, absender: str = "mueller@beispiel.de", jahr: int = 2025,
          body: str = "Inhalt", anhang: str = "", name: str = "Josef Müller") -> bytes:
    """Baut eine Testmail."""
    datum = email.utils.format_datetime(datetime(jahr, 3, 14, 9, 30, tzinfo=timezone.utc))
    if anhang:
        return (
            f"From: {name} <{absender}>\r\n"
            f"To: stephan@beispiel.de\r\n"
            f"Subject: {betreff}\r\n"
            f"Date: {datum}\r\n"
            'Content-Type: multipart/mixed; boundary="G"\r\n\r\n'
            "--G\r\nContent-Type: text/plain\r\n\r\n"
            f"{body}\r\n"
            f'--G\r\nContent-Type: application/pdf\r\n'
            f'Content-Disposition: attachment; filename="{anhang}"\r\n\r\n'
            "PDF\r\n--G--\r\n"
        ).encode("utf-8")
    return (
        f"From: {name} <{absender}>\r\n"
        f"To: stephan@beispiel.de\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: {datum}\r\n\r\n"
        f"{body}\r\n"
    ).encode("utf-8")


class ArchiveTestCase(unittest.TestCase):
    """Grundgerüst mit umgebogenem Indexverzeichnis."""

    mode = Mode.PRIVAT

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        patcher = mock.patch.object(paths, "data_dir", return_value=self.base / "daten")
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.base / "daten").mkdir(parents=True, exist_ok=True)

        self.archive = Archive.create(
            self.base / "archiv", mode=self.mode, jurisdiction=Jurisdiction.DE, name="Test"
        )
        self.addCleanup(self._close)

    def _close(self) -> None:
        try:
            self.archive.close()
        except Exception:  # noqa: BLE001 – im Abbau nicht mehr wichtig
            pass
        self._tmp.cleanup()


class TestAnlegen(ArchiveTestCase):
    def test_verzeichnisse_und_kennung(self) -> None:
        self.assertTrue((self.archive.root / "archive.json").exists())
        self.assertTrue((self.archive.root / "mail").is_dir())
        self.assertTrue((self.archive.root / "meta").is_dir())
        self.assertTrue(self.archive.uuid)

    def test_erster_journaleintrag_verankert_die_kette(self) -> None:
        eintraege = list(self.archive.journal.read_all())
        self.assertEqual(eintraege[0]["op"], "create")
        self.assertEqual(eintraege[0]["uuid"], self.archive.uuid)

    def test_zweimal_anlegen_geht_nicht(self) -> None:
        with self.assertRaises(ArchiveError):
            Archive.create(self.archive.root)

    def test_oeffnen_ohne_archiv(self) -> None:
        with self.assertRaises(ArchiveError):
            Archive.open(self.base / "gibtsnicht")


class TestAufnehmen(ArchiveTestCase):
    def test_mail_landet_in_ablage_journal_und_index(self) -> None:
        result = self.archive.add(probe("Schlussrechnung"), account="firma", folder="INBOX")
        self.archive.index.commit()

        self.assertTrue(result.stored)
        self.assertTrue(result.indexed)
        self.assertTrue(self.archive.store.exists(result.hash, result.bucket))
        self.assertEqual(self.archive.index.statistics()["mails"], 1)

    def test_dieselbe_mail_zweimal(self) -> None:
        roh = probe("Einmalig")
        first = self.archive.add(roh, account="firma", folder="INBOX")
        second = self.archive.add(roh, account="firma", folder="INBOX")
        self.archive.index.commit()

        self.assertTrue(first.stored)
        self.assertFalse(second.stored, "Die Mail wurde doppelt abgelegt.")
        self.assertEqual(self.archive.index.statistics()["mails"], 1)

    def test_gleiche_mail_in_zwei_konten_zaehlt_einmal_liegt_zweimal(self) -> None:
        """Ein Fundort mehr, aber keine zweite Datei und kein zweiter Treffer."""
        roh = probe("Rundschreiben")
        self.archive.add(roh, account="firma", folder="INBOX")
        self.archive.add(roh, account="privat", folder="Posteingang")
        self.archive.index.commit()

        stats = self.archive.index.statistics()
        self.assertEqual(stats["mails"], 1)
        self.assertEqual(stats["fundorte"], 2)

    def test_anhaenge_werden_erfasst(self) -> None:
        self.archive.add(
            probe("Mit Beleg", anhang="rechnung.pdf"), account="firma", folder="INBOX"
        )
        self.archive.index.commit()
        self.assertEqual(self.archive.index.statistics()["anhaenge"], 1)

    def test_mail_ohne_datum(self) -> None:
        roh = b"From: a@example.org\r\nSubject: Zeitlos\r\n\r\nOhne Datumszeile"
        result = self.archive.add(roh, account="firma", folder="INBOX")
        self.archive.index.commit()
        self.assertTrue(result.stored)
        self.assertEqual(len(self.archive.index.search("zeitlos")), 1)


class TestSuchen(ArchiveTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.archive.add(
            probe("Schlussrechnung 2025-0042", anhang="rechnung.pdf", name="Josef Müller"),
            account="firma", folder="INBOX",
        )
        self.archive.add(
            probe("Rückfrage zur Bestellung", "info@lieferant.at", 2024, name="Lieferant AG"),
            account="firma", folder="Gesendet",
        )
        self.archive.add(
            probe("Newsletter März", "news@werbung.example", 2025,
                  body="Sonderangebote", name="Werbung"),
            account="privat", folder="INBOX",
        )
        self.archive.index.commit()

    def test_freitext(self) -> None:
        self.assertEqual(len(self.archive.index.search("sonderangebote")), 1)

    def test_teilwort_im_betreff(self) -> None:
        """Der eigentliche Grund für den Dreizeichenindex: deutsche Komposita."""
        treffer = self.archive.index.search("betreff:rechnung")
        self.assertEqual(len(treffer), 1)
        self.assertIn("Schlussrechnung", treffer[0].subject)

    def test_umlaut_im_absender(self) -> None:
        self.assertEqual(len(self.archive.index.search("von:müller")), 1)

    def test_absender_auch_ohne_umlaut_zu_finden(self) -> None:
        """Wer den Umlaut nicht tippt, soll trotzdem etwas finden."""
        self.assertEqual(len(self.archive.index.search("von:muller")), 1)

    def test_nach_jahr(self) -> None:
        self.assertEqual(len(self.archive.index.search("jahr:2024")), 1)
        self.assertEqual(len(self.archive.index.search("jahr:2024-2025")), 3)

    def test_nach_anhangstyp(self) -> None:
        self.assertEqual(len(self.archive.index.search("typ:pdf")), 1)

    def test_nur_mit_anhang(self) -> None:
        self.assertEqual(len(self.archive.index.search("hat:anhang")), 1)

    def test_nach_konto(self) -> None:
        self.assertEqual(len(self.archive.index.search("konto:privat")), 1)

    def test_ausschluss(self) -> None:
        self.assertEqual(len(self.archive.index.search("-sonderangebote")), 2)

    def test_bedingungen_werden_verundet(self) -> None:
        """Jeder weitere Begriff muss die Trefferliste kleiner machen."""
        self.assertEqual(len(self.archive.index.search("jahr:2025")), 2)
        self.assertEqual(len(self.archive.index.search("von:müller jahr:2025")), 1)
        self.assertEqual(len(self.archive.index.search("von:müller jahr:2024")), 0)

    def test_leere_suche_liefert_alles(self) -> None:
        self.assertEqual(len(self.archive.index.search("")), 3)

    def test_ohne_treffer(self) -> None:
        self.assertEqual(self.archive.index.search("giraffenzuechterverein"), [])


class TestPruefen(ArchiveTestCase):
    def test_frisches_archiv_ist_heil(self) -> None:
        for i in range(5):
            self.archive.add(probe(f"Mail {i}"), account="firma", folder="INBOX")
        self.archive.index.commit()

        bericht = self.archive.verify()
        self.assertTrue(bericht["ok"], bericht)
        self.assertEqual(bericht["expected"], 5)
        self.assertEqual(bericht["on_disk"], 5)

    def test_fehlende_datei_faellt_auf(self) -> None:
        result = self.archive.add(probe("Verschwindet"), account="firma", folder="INBOX")
        self.archive.store.remove(result.hash, result.bucket)  # am Journal vorbei

        bericht = self.archive.verify()
        self.assertFalse(bericht["ok"])
        self.assertIn(result.hash, bericht["missing"])

    def test_untergeschobene_datei_faellt_auf(self) -> None:
        """Eine Mail von Hand in mail/ zu legen, ist keine Archivierung."""
        self.archive.store.put(probe("Untergeschoben"), datetime(2025, 3, 14, tzinfo=timezone.utc))

        bericht = self.archive.verify()
        self.assertFalse(bericht["ok"])
        self.assertEqual(len(bericht["unexpected"]), 1)


class TestNeuaufbauMitErkanntemText(ArchiveTestCase):
    """Text aus eingescannten PDF muss den Neuaufbau überleben.

    **Warum das wichtiger ist, als es klingt.** Texterkennung dauert
    Stunden; an Stephans Bestand waren es 431 Dokumente. Der erkannte
    Text liegt deshalb in einem Nebenspeicher neben dem Index –
    ausdrücklich damit ein Neuaufbau ihn nicht vernichtet.

    Nur holte ihn dort niemand ab. Wer den Index neu baute, fand seine
    Scans anschließend nicht mehr – ohne dass irgendwo etwas fehlte
    oder eine Meldung kam. Man musste ``mailburg texterkennung``
    hinterherschieben und von selbst darauf kommen.

    Aufgefallen am 2026-08-31 nach der Umstellung auf Schemafassung 2.
    """

    def _mit_scan(self) -> str:
        """Legt eine Mail mit »eingescanntem« Anhang ab, gibt ihren Hash."""
        self.archive.add(
            probe("Eingescannt", anhang="scan.pdf"),
            account="firma", folder="INBOX",
        )
        self.archive.index.commit()
        return self.archive.index.search("betreff:eingescannt")[0].hash

    def _erkannt(self, digest: str, text: str) -> None:
        """Legt Text so ab, wie es die Texterkennung tut."""
        from mailburg.core.erkennung import Textspeicher, _kennung

        Textspeicher().schreiben(f"{digest}-{_kennung('scan.pdf')}", text)

    def test_der_erkannte_text_ist_danach_wieder_auffindbar(self) -> None:
        digest = self._mit_scan()
        self._erkannt(digest, "Rechnungsnummer 4711 ueber 250 Euro")

        self.archive.rebuild_index()

        self.assertEqual(len(self.archive.index.search("4711")), 1)

    def test_der_mailtext_geht_darueber_nicht_verloren(self) -> None:
        """Angehängt, nicht ersetzt – sonst wäre der Gewinn ein Verlust."""
        digest = self._mit_scan()
        self._erkannt(digest, "Rechnungsnummer 4711")

        self.archive.rebuild_index()

        self.assertEqual(len(self.archive.index.search("4711")), 1)
        self.assertEqual(len(self.archive.index.search("betreff:eingescannt")), 1)

    def test_ohne_erkannten_text_aendert_sich_nichts(self) -> None:
        """Der häufige Fall darf davon nichts merken."""
        self._mit_scan()

        anzahl = self.archive.rebuild_index()

        self.assertEqual(anzahl, 1)
        self.assertEqual(len(self.archive.index.search("4711")), 0)

    def test_es_wird_nichts_neu_erkannt(self) -> None:
        """Gelesen wird, was dasteht – erkannt wird hier nichts.

        Sonst würde aus einem Neuaufbau von Minuten wieder einer von
        Stunden, und zwar unangekündigt. Geprüft am Textspeicher: Wer
        nur liest, schreibt nicht.
        """
        from unittest import mock

        from mailburg.core.erkennung import Textspeicher

        digest = self._mit_scan()
        self._erkannt(digest, "schon erkannt")

        with mock.patch.object(Textspeicher, "schreiben") as geschrieben:
            self.archive.rebuild_index()

        geschrieben.assert_not_called()
        self.assertEqual(len(self.archive.index.search("schon")), 1)


class TestNeuaufbau(ArchiveTestCase):
    def test_index_entsteht_vollstaendig_neu(self) -> None:
        """Der Beweis, dass der Index entbehrlich ist."""
        self.archive.add(probe("Erste", anhang="a.pdf"), account="firma", folder="INBOX")
        self.archive.add(probe("Zweite", jahr=2024), account="firma", folder="Gesendet")
        self.archive.add(probe("Dritte"), account="privat", folder="INBOX")
        self.archive.index.commit()
        vorher = self.archive.index.statistics()

        anzahl = self.archive.rebuild_index()

        self.assertEqual(anzahl, 3)
        self.assertEqual(self.archive.index.statistics(), vorher)
        self.assertEqual(len(self.archive.index.search("betreff:zweite")), 1)

    def test_fundorte_bleiben_erhalten(self) -> None:
        roh = probe("In zwei Konten")
        self.archive.add(roh, account="firma", folder="INBOX")
        self.archive.add(roh, account="privat", folder="Posteingang")
        self.archive.index.commit()

        self.archive.rebuild_index()
        self.assertEqual(self.archive.index.statistics()["fundorte"], 2)

    def test_geloeschte_mails_kommen_nicht_zurueck(self) -> None:
        """Ein Grabstein muss den Neuaufbau überleben – sonst wäre er wertlos."""
        result = self.archive.add(probe("Zu löschen"), account="firma", folder="INBOX")
        self.archive.add(probe("Bleibt"), account="firma", folder="INBOX")
        self.archive.index.commit()
        self.archive.delete(result.hash, result.bucket, reason="dsgvo_art17", actor="test")

        self.archive.rebuild_index()
        self.assertEqual(self.archive.index.statistics()["mails"], 1)
        self.assertEqual(self.archive.index.search("betreff:löschen"), [])


class TestLoeschen(ArchiveTestCase):
    def test_inhalt_weg_vorgang_bleibt(self) -> None:
        result = self.archive.add(probe("Auf Wunsch entfernt"), account="firma", folder="INBOX")
        self.archive.index.commit()

        self.archive.delete(
            result.hash, result.bucket,
            reason="dsgvo_art17", actor="stephan", note="Ersuchen vom 2026-08-25",
        )

        self.assertFalse(self.archive.store.exists(result.hash, result.bucket))
        self.assertEqual(self.archive.index.statistics()["mails"], 0)

        grabstein = list(self.archive.journal.read_all())[-1]
        self.assertEqual(grabstein["op"], "delete")
        self.assertEqual(grabstein["reason"], "dsgvo_art17")
        self.assertEqual(grabstein["actor"], "stephan")

    def test_kette_bleibt_nach_dem_loeschen_heil(self) -> None:
        result = self.archive.add(probe("X"), account="firma", folder="INBOX")
        self.archive.index.commit()
        self.archive.delete(result.hash, result.bucket, reason="privat")

        self.assertTrue(self.archive.verify()["ok"])

    def test_privatarchiv_kennt_keine_sperre(self) -> None:
        result = self.archive.add(probe("Neulich", jahr=2025), account="privat", folder="INBOX")
        self.archive.index.commit()
        self.archive.delete(result.hash, result.bucket, reason="aufgeraeumt")
        self.assertEqual(self.archive.index.statistics()["mails"], 0)


class TestGeschaeftsarchiv(ArchiveTestCase):
    mode = Mode.GESCHAEFTLICH

    def test_frist_schuetzt_vor_dem_loeschen(self) -> None:
        """Eine Mail von 2025 ist in Deutschland bis Ende 2033 zu halten."""
        result = self.archive.add(probe("Beleg", jahr=2025), account="firma", folder="INBOX")
        self.archive.index.commit()

        with self.assertRaises(RetentionLocked):
            self.archive.delete(result.hash, result.bucket, reason="versehen")

        self.assertTrue(self.archive.store.exists(result.hash, result.bucket))

    def test_loeschen_bleibt_mit_ausdruecklicher_begruendung_moeglich(self) -> None:
        """Sonst ließe sich ein Löschverlangen nach Art. 17 nie erfüllen."""
        result = self.archive.add(probe("Beleg", jahr=2025), account="firma", folder="INBOX")
        self.archive.index.commit()

        self.archive.delete(
            result.hash, result.bucket,
            reason="dsgvo_art17", actor="stephan", override_retention=True,
        )
        self.assertFalse(self.archive.store.exists(result.hash, result.bucket))

    def test_abgelaufene_frist_gibt_die_mail_frei(self) -> None:
        result = self.archive.add(probe("Uralt", jahr=2005), account="firma", folder="INBOX")
        self.archive.index.commit()
        self.archive.delete(result.hash, result.bucket, reason="frist_abgelaufen")
        self.assertEqual(self.archive.index.statistics()["mails"], 0)

    def test_siegel_haelt_den_stand_fest(self) -> None:
        self.archive.add(probe("Vor dem Siegel"), account="firma", folder="INBOX")
        eintrag = self.archive.seal()

        self.assertEqual(eintrag["op"], "seal")
        self.assertGreaterEqual(eintrag["count"], 2)
        self.assertTrue(self.archive.verify()["chain_ok"])


class TestVerwaisteSperre(ArchiveTestCase):
    """Eine Sperre, deren Vorgang nicht mehr läuft.

    **Der Fall kommt vor, und zwar bei Abstürzen.** Am 2026-09-01 hat
    Stephan im Geschäftsarchiv F5 gedrückt und bekam »Abruf
    gescheitert« – die Sperre stammte von einem Lauf zwei Stunden
    zuvor, den es nicht mehr gab.

    MailBurg wusste das sogar: In der Meldung stand »der Vorgang, der es
    hielt, läuft nicht mehr … die Datei kann gelöscht werden«. Nur
    musste der Anwender dann ins Terminal, um eine versteckte Datei auf
    einer externen Platte zu entfernen. Wer das nicht kann, kommt an
    sein Archiv nicht mehr heran – und das bei einem Programm, dessen
    einzige Aufgabe es ist, Post zugänglich zu halten.
    """

    def _sperre_legen(self, host: str, pid: int) -> None:
        import json
        from mailburg.core.archive import LOCK_FILE

        (self.archive.root / LOCK_FILE).write_text(
            json.dumps({
                "host": host, "pid": pid,
                "since": "2026-08-31T16:21:30+00:00",
            }),
            encoding="utf-8",
        )

    def _tote_pid(self) -> int:
        """Eine Prozessnummer, die es sicher nicht gibt."""
        import os

        for kandidat in range(99999, 90000, -1):
            try:
                os.kill(kandidat, 0)
            except ProcessLookupError:
                return kandidat
            except PermissionError:
                continue
        raise AssertionError("keine freie Prozessnummer gefunden")

    def test_eine_verwaiste_sperre_wird_uebernommen(self) -> None:
        import socket

        self.archive.close()
        self._sperre_legen(socket.gethostname(), self._tote_pid())

        wieder = Archive.open(self.archive.root)
        try:
            self.assertEqual(wieder.uuid, self.archive.uuid)
        finally:
            wieder.close()

    def test_eine_fremde_sperre_bleibt_unangetastet(self) -> None:
        """Über einen anderen Rechner lässt sich nichts sagen.

        Beim Archiv in der Cloud ist das keine Theorie: Läuft MailBurg
        zu Hause und in der Firma, hielte die Sperre dort zu Recht – und
        sie wegzuräumen hieße, zwei Läufe gleichzeitig ans selbe Journal
        zu lassen.
        """
        self.archive.close()
        self._sperre_legen("ein-anderer-rechner", 4242)

        with self.assertRaises(ArchiveLocked):
            Archive.open(self.archive.root)

    def test_eine_laufende_sperre_bleibt_unangetastet(self) -> None:
        """Der häufigste Fall überhaupt: der Abruf im Hintergrund."""
        import os
        import socket

        self.archive.close()
        self._sperre_legen(socket.gethostname(), os.getpid())

        with self.assertRaises(ArchiveLocked):
            Archive.open(self.archive.root)

    def test_ohne_prozessnummer_wird_nichts_angefasst(self) -> None:
        """Alte Sperrdateien führten keine PID – dann gilt Vorsicht."""
        import json
        from mailburg.core.archive import LOCK_FILE

        self.archive.close()
        (self.archive.root / LOCK_FILE).write_text(
            json.dumps({"host": "irgendwer"}), encoding="utf-8"
        )

        with self.assertRaises(ArchiveLocked):
            Archive.open(self.archive.root)


class TestSperre(ArchiveTestCase):
    def test_zweites_oeffnen_wird_abgewiesen(self) -> None:
        """Sonst schreiben zwei Rechner über Nextcloud gleichzeitig ins Journal."""
        with self.assertRaises(ArchiveLocked):
            Archive.open(self.archive.root)

    def test_nur_lesend_geht_immer(self) -> None:
        zweites = Archive.open(self.archive.root, exclusive=False)
        try:
            self.assertEqual(zweites.uuid, self.archive.uuid)
        finally:
            zweites.close()

    def test_sperre_wird_beim_schliessen_freigegeben(self) -> None:
        self.archive.close()
        wieder = Archive.open(self.archive.root)
        try:
            self.assertEqual(wieder.uuid, self.archive.uuid)
        finally:
            wieder.close()
        # Damit das Aufräumen in tearDown nicht erneut schließt:
        self.archive = wieder

    def test_rechnername_mit_umlaut_bleibt_lesbar(self) -> None:
        """Die Sperrdatei wird als UTF-8 gelesen, also muss sie so entstehen.

        Ohne ausdrückliche Angabe nimmt Python die Kodierung des Systems –
        cp1252 unter Windows, ASCII bei LC_ALL=C. Ein Rechner namens
        »Büro-PC« hinterließe dann eine Sperrdatei, die sich nicht mehr lesen
        lässt, und der Hinweis, wo das Archiv gerade offen ist, wäre weg.
        """
        self.archive.close()
        with mock.patch("socket.gethostname", return_value="Büro-PC"):
            gesperrt = Archive.open(self.archive.root)
        try:
            with self.assertRaises(ArchiveLocked) as gefangen:
                Archive.open(self.archive.root)
            self.assertIn("Büro-PC", str(gefangen.exception))
        finally:
            gesperrt.close()
        self.archive = gesperrt


if __name__ == "__main__":
    unittest.main()


class SperrmeldungTest(unittest.TestCase):
    """Zum Löschen der Sperrdatei darf nur geraten werden, wenn es stimmt.

    Meistens hält sie kein Absturz, sondern der geplante Abruf im
    Hintergrund. Wer dann löscht, hat zwei Läufe gleichzeitig am selben
    Journal - genau das, was die Sperre verhindern soll.
    """

    def erklaerung(self, **held):
        import pathlib
        import socket

        from mailburg.core.archive import _sperre_erklaeren

        held.setdefault("host", socket.gethostname())
        held.setdefault("since", "2026-08-26T07:37:03+00:00")
        return _sperre_erklaeren(pathlib.Path("/wo/auch/immer/.mailburg-lock"), held)

    def test_laufender_vorgang_wird_nicht_zum_loeschen_empfohlen(self):
        import os

        text = self.erklaerung(pid=os.getpid())

        self.assertIn("Geduld", text)
        # Das Entscheidende: kein Wort, das jemanden zum Löschen verleitet.
        # Wer hier eine Anleitung bekäme, hätte zwei Abrufe gleichzeitig
        # am selben Journal.
        for wort in ("löschen", "gelöscht", "entfernen", ".mailburg-lock"):
            self.assertNotIn(wort, text.lower().replace("löschen", "löschen"))

    def test_toter_vorgang_darf_weggeraeumt_werden(self):
        # Eine PID, die es sicher nicht gibt.
        text = self.erklaerung(pid=4_000_000)

        self.assertIn("Überbleibsel", text)
        self.assertIn("gelöscht werden", text)

    def test_fremder_rechner_bekommt_keine_ferndiagnose(self):
        # Über die Prozesse eines anderen Rechners lässt sich von hier aus
        # nichts sagen. Raten wäre schlimmer als Schweigen.
        text = self.erklaerung(host="anderer-rechner", pid=1)

        self.assertIn("anderer-rechner", text)
        self.assertIn("dort erst schließen", text)

    def test_alte_sperrdatei_ohne_pid(self):
        text = self.erklaerung()
        self.assertIn("2026-08-26", text)


class MailsStattFundorteTest(unittest.TestCase):
    """Eine Mail in zwei Ordnern ist eine Mail, nicht zwei."""

    def setUp(self):
        import pathlib
        import tempfile

        from mailburg.core.archive import Archive

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.archive = Archive.create(pathlib.Path(self.ordner.name) / "A")
        self.addCleanup(self.archive.close)

    def test_dieselbe_mail_in_zwei_ordnern_zaehlt_einmal(self):
        # Genau die Lage bei Proton: Jede Mail liegt in ihrem Ordner und
        # zusätzlich unter jedem ihrer Etiketten. Wer die Ordnerzahlen
        # addiert, kommt auf eine Zahl, die es nicht gibt - im Betrieb
        # gemessen 2.877 statt der tatsächlichen 2.078.
        roh = probe("Rechnung")
        self.archive.add(roh, account="proton", folder="Archive")
        self.archive.add(roh, account="proton", folder="Labels/Finanzamt")

        fundorte = sum(n for k, _, n in self.archive.index.accounts()
                       if k == "proton")
        self.assertEqual(fundorte, 2, "zwei Fundorte, das ist richtig so")
        self.assertEqual(self.archive.index.account_totals()["proton"], 1)
        self.assertEqual(self.archive.index.count(), 1)

    def test_getrennte_konten_werden_getrennt_gezaehlt(self):
        self.archive.add(probe("Eins"), account="a", folder="INBOX")
        self.archive.add(probe("Zwei"), account="b", folder="INBOX")

        self.assertEqual(self.archive.index.account_totals(), {"a": 1, "b": 1})


class RueckgabeTest(unittest.TestCase):
    """Der Weg zurück: als Datei und ins Postfach."""

    def setUp(self):
        import pathlib
        import tempfile

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name)

    def test_als_datei_bekommt_die_endung(self):
        from mailburg.core.rueckgabe import als_datei

        abgelegt = als_datei(b"From: a@example.org\r\n\r\nText", self.ziel / "Rechnung")

        self.assertEqual(abgelegt.suffix, ".eml")
        self.assertEqual(abgelegt.read_bytes(), b"From: a@example.org\r\n\r\nText")

    def test_bytegenau_gespeichert(self):
        # Kopfzeilen und Zeilenenden unverändert - sonst ist eine
        # vorhandene DKIM-Signatur hinüber, und die Mail im Postfach wäre
        # nicht mehr dieselbe wie die im Archiv.
        from mailburg.core.rueckgabe import als_datei

        roh = b"Received: von irgendwo\r\nSubject: Test\r\n\r\nZeile\r\nZeile\r\n"
        abgelegt = als_datei(roh, self.ziel / "m.eml")

        self.assertEqual(abgelegt.read_bytes(), roh)

    def test_zeitstempel_kommt_aus_der_mail(self):
        # Ohne diese Angabe setzt der Server das Datum von heute. Die Mail
        # stünde im Mailprogramm ganz oben statt an ihrem Platz in der
        # Zeit - bei zwanzig Jahre alter Post ein sinnloser Anblick.
        from mailburg.core.rueckgabe import _zeitstempel

        stempel = _zeitstempel(
            b"Date: Tue, 15 Mar 2016 09:12:00 +0100\r\nSubject: Alt\r\n\r\nText"
        )

        self.assertIn("15-Mar-2016", stempel)

    def test_ohne_datumszeile_wird_nicht_geraten(self):
        from mailburg.core.rueckgabe import _zeitstempel

        # Kein Absturz, kein erfundenes Datum aus der Mail - dann eben
        # heute.
        self.assertTrue(_zeitstempel(b"Subject: Ohne\r\n\r\nText"))

    def test_leere_nachricht_wird_abgelehnt(self):
        from unittest import mock

        from mailburg.core.rueckgabe import RueckgabeFehler, ins_postfach

        with self.assertRaises(RueckgabeFehler):
            ins_postfach(mock.Mock(), "geheim", "INBOX", b"")

    def test_ordner_mit_leerzeichen_wird_eingefasst(self):
        from mailburg.core.rueckgabe import _ordner_kodieren

        self.assertEqual(_ordner_kodieren("INBOX"), "INBOX")
        self.assertEqual(_ordner_kodieren("Alte Post"), '"Alte Post"')

    def test_dateiname_ohne_verbotene_zeichen(self):
        # Windows verbietet \ / : * ? " < > |, und ein Doppelpunkt steht
        # in fast jedem Betreff mit "Re:" oder "AW:".
        # Der Dateiname wird in der Oberfläche gebildet; ohne PySide6
        # gibt es sie nicht. Die CI läuft bewusst ohne Fremdpakete -
        # MailBurgs Kern kommt ohne aus, und das soll geprüft bleiben.
        try:
            from mailburg.ui.hauptfenster import _dateiname
        except ImportError:
            self.skipTest("PySide6 ist nicht installiert")

        name = _dateiname('Re: Angebot 3/2025 <wichtig?>')

        self.assertNotIn(":", name.removesuffix(".eml"))
        self.assertNotIn("/", name)
        self.assertTrue(name.endswith(".eml"))


class UngelesenZurueckTest(unittest.TestCase):
    """Wiederhergestellte Post muss auffindbar sein."""

    def _append_mitschreiben(self, **kwargs):
        from unittest import mock

        from mailburg.core import rueckgabe
        from mailburg.sources import imap

        mitgeschrieben = {}

        class GefaelschteVerbindung:
            def append(self, ordner, flags, wann, nachricht):
                mitgeschrieben["flags"] = flags
                mitgeschrieben["ordner"] = ordner
                return "OK", [b"APPENDUID"]

        class GefaelschteQuelle:
            def __init__(self, *a, **k):
                self._verbindung = GefaelschteVerbindung()

            def close(self):
                pass

        with mock.patch.object(imap, "ImapSource", GefaelschteQuelle):
            rueckgabe.ins_postfach(
                mock.Mock(), "geheim", "INBOX",
                b"Date: Tue, 15 Mar 2016 09:12:00 +0100\r\n\r\nText",
                **kwargs,
            )
        return mitgeschrieben

    def test_ohne_angabe_kommt_sie_ungelesen_zurueck(self):
        # Sie kommt mit ihrem alten Datum und steht damit mitten in der
        # Post von damals. Als gelesen markiert fände man sie dort nie
        # wieder.
        self.assertEqual(self._append_mitschreiben().get("flags"), "")

    def test_auf_wunsch_als_gelesen(self):
        self.assertEqual(
            self._append_mitschreiben(ungelesen=False).get("flags"), "\\Seen")


class SeitenfortschrittTest(unittest.TestCase):
    """Bei einem langen Scan muss sich zwischendurch etwas rühren."""

    def test_ocr_meldet_jede_seite(self):
        # Ohne diese Rückmeldung steht die Oberfläche bei einem
        # zwanzigseitigen Dokument fast zwei Minuten auf demselben Wert -
        # und wer nichts sieht, hält das Programm für abgestürzt.
        import inspect

        from mailburg.extract import ocr

        unterschrift = inspect.signature(ocr.text_aus_pdf)
        self.assertIn("je_seite", unterschrift.parameters)

    def test_die_meldung_geht_bis_in_den_durchlauf(self):
        import inspect

        from mailburg.core import erkennung

        self.assertIn("je_seite",
                      inspect.signature(erkennung.durchlauf).parameters)

    def test_abbruch_wird_zwischen_dokumenten_geprueft(self):
        # Mitten in einem Dokument abzubrechen hieße: Es gilt als
        # erledigt, ist aber nur halb gelesen - und käme nie wieder dran.
        import inspect

        from mailburg.core import erkennung

        quelle = inspect.getsource(erkennung.durchlauf)
        vor_abbruch = quelle.index("if weiter is not None and not weiter():")
        vermerk = quelle.index("archiv.index.commit()")
        self.assertLess(vermerk, vor_abbruch,
                        "erst festschreiben, dann abbrechen")


class ErkennungsreihenfolgeTest(unittest.TestCase):
    """Kleine Dokumente zuerst - sonst steht die Anzeige minutenlang still."""

    def test_sortiert_nach_groesse(self):
        import inspect

        from mailburg.core.erkennung import Warteschlange

        quelle = inspect.getsource(Warteschlange.offen)
        # Ein einseitiger Scan ist in vier Sekunden gelesen, ein
        # zwanzigseitiger Brocken braucht eine halbe Stunde. Bei einem
        # Lauf mit Zeitbudget entscheidet die Reihenfolge, wie viel
        # überhaupt geschafft wird.
        self.assertIn("ORDER BY a.size ASC", quelle)

    def test_grosse_scans_werden_groeber_gerastert(self):
        # 23 MB bei 300 dpi ergeben Bilder von dreißig Megabyte, und eine
        # einzige Seite braucht dann zwei Minuten - genau so lange, wie
        # die Zeitgrenze erlaubt.
        from mailburg.extract import ocr

        self.assertLess(ocr.AUFLOESUNG_GROSS, ocr.AUFLOESUNG)
        # Unter 200 dpi wird tesseract unsicher.
        self.assertGreaterEqual(ocr.AUFLOESUNG_GROSS, 200)


class SicherungTest(unittest.TestCase):
    """Packen und wieder herausholen - beides muss verlässlich sein."""

    def setUp(self):
        import pathlib
        import tempfile

        from mailburg.core.archive import Archive

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = pathlib.Path(self.ordner.name)
        self.archiv = Archive.create(self.wo / "A", name="Probe")
        for betreff in ("Eins", "Zwei", "Drei"):
            self.archiv.add(probe(betreff), account="a", folder="INBOX")
        self.archiv.close()

    def test_rundlauf_erhaelt_die_kette(self):
        # Der eigentliche Beweis: Was wieder herauskommt, lässt sich
        # prüfen. Eine Sicherung, von der niemand weiß, ob sie lesbar
        # ist, ist nur eine halbe.
        from mailburg.core import sicherung
        from mailburg.core.archive import Archive

        # Die Endung nicht festschreiben: Zstandard steckt erst ab
        # Python 3.14 in der Standardbibliothek, davor braucht es ein
        # Paket. Fehlt es, packt MailBurg mit LZMA - und genau dieser
        # Rückfall soll mitgeprüft werden, statt den Test umzuwerfen.
        paket = self.wo / f"sicherung.{sicherung._endung()}"
        sicherung.packen(self.wo / "A", paket)
        sicherung.entpacken(paket, self.wo / "Zurueck")

        with Archive.open(self.wo / "Zurueck", exclusive=False) as zurueck:
            bericht = zurueck.verify()
        self.assertTrue(bericht["chain_ok"])
        self.assertEqual(bericht["expected"], 3)
        self.assertEqual(bericht["on_disk"], 3)

    def test_die_sperrdatei_wird_nicht_mitgepackt(self):
        # Sie beschreibt einen Zustand, kein Archivgut - und im Ziel
        # würde sie ein Archiv als geöffnet ausweisen, das niemand
        # geöffnet hat.
        import tarfile

        from mailburg.core import sicherung

        (self.wo / "A" / ".mailburg-lock").write_text("{}", encoding="utf-8")
        paket = self.wo / "s.tar.xz"
        sicherung.packen(self.wo / "A", paket)

        import lzma

        with lzma.open(paket, "rb") as roh, tarfile.open(fileobj=roh, mode="r|") as b:
            namen = [e.name for e in b]
        self.assertNotIn(".mailburg-lock", namen)

    def test_nicht_in_ein_volles_verzeichnis(self):
        # Zwei Protokolle ineinander ergäben eines, das sich nicht mehr
        # prüfen lässt.
        from mailburg.core import sicherung
        from mailburg.core.sicherung import SicherungFehler

        paket = self.wo / "s.tar.zst"
        sicherung.packen(self.wo / "A", paket)

        with self.assertRaises(SicherungFehler) as fehler:
            sicherung.entpacken(paket, self.wo / "A")
        self.assertIn("nicht leer", str(fehler.exception))

    def test_ohne_archiv_wird_nichts_gepackt(self):
        from mailburg.core import sicherung
        from mailburg.core.sicherung import SicherungFehler

        leer = self.wo / "leer"
        leer.mkdir()
        with self.assertRaises(SicherungFehler):
            sicherung.packen(leer, self.wo / "x.tar.zst")

    def test_dateiname_traegt_das_datum(self):
        from datetime import date

        from mailburg.core import sicherung

        name = sicherung.vorschlag(self.wo / "A", "Mailarchiv")
        self.assertIn(date.today().isoformat(), name)
        self.assertTrue(name.endswith((".tar.zst", ".tar.xz")))

    def test_pfade_aus_dem_ziel_heraus_werden_uebergangen(self):
        # Ein Bündel aus fremder Hand könnte "../../etc/…" enthalten;
        # tarfile folgt dem bereitwillig.
        import inspect

        from mailburg.core import sicherung

        quelle = inspect.getsource(sicherung.entpacken)
        self.assertIn('".." in Path(', quelle)
        self.assertIn('filter="data"', quelle)


class SicherungsnamenTest(unittest.TestCase):
    """Ein Dateiname wandert durch fremde Hände."""

    def test_umlaute_werden_umgeschrieben(self):
        # macOS speichert Umlaute anders als Linux, manche Weboberfläche
        # zeigt sie als Fragezeichen, und wer die Datei später per
        # Kommandozeile sucht, tippt sie falsch.
        from mailburg.core.sicherung import dateiname

        name = dateiname("Geschäftsarchiv")

        self.assertTrue(name.startswith("MailBurg-Geschaeftsarchiv."))
        self.assertTrue(name.isascii())

    def test_leerzeichen_werden_bindestriche(self):
        from mailburg.core.sicherung import dateiname

        self.assertIn("Mailarchiv-Stephan", dateiname("Mailarchiv Stephan"))

    def test_kein_datum_im_namen(self):
        # Diese Sicherung wird ersetzt, nicht gesammelt.
        from datetime import date

        from mailburg.core.sicherung import dateiname

        self.assertNotIn(str(date.today().year), dateiname("Privatarchiv"))

    def test_leerer_name_ergibt_trotzdem_einen(self):
        from mailburg.core.sicherung import dateiname

        self.assertTrue(dateiname("").startswith("MailBurg-"))

    def test_erst_daneben_dann_umbenennen(self):
        # Wer wöchentlich unter demselben Namen ersetzt, hätte sonst ein
        # Zeitfenster von Minuten, in dem die alte Sicherung schon
        # überschrieben und die neue noch nicht fertig ist.
        import inspect

        from mailburg.core import sicherung

        quelle = inspect.getsource(sicherung.packen)
        self.assertIn("unfertig", quelle)
        self.assertIn("vorlaeufig.replace(ziel)", quelle)


class SicherungsnameAusdruecklichTest(unittest.TestCase):
    """Der Dateiname folgt nicht zwingend dem Archivnamen."""

    def test_name_lässt_sich_vorgeben(self):
        # Stephans Archiv heißt intern "Mailarchiv", die Sicherung sollte
        # aber "MailBurg-Geschaeftsarchiv" heißen. Ohne diese Angabe
        # bekommt man einen Dateinamen, den man hinterher von Hand
        # richtigstellt - und beim nächsten Lauf wieder.
        from mailburg.core.sicherung import dateiname

        self.assertEqual(
            dateiname("Geschaeftsarchiv").split(".")[0],
            "MailBurg-Geschaeftsarchiv",
        )

    def test_die_kommandozeile_kennt_den_schalter(self):
        from mailburg.__main__ import build_parser

        args = build_parser().parse_args(
            ["sichern", "--name", "Geschaeftsarchiv", "A", "B"]
        )
        self.assertEqual(args.name, "Geschaeftsarchiv")


class OhneBudgetDurchlaufenTest(unittest.TestCase):
    """Ein Lauf ohne Budget muss auch ohne Budget laufen."""

    def test_die_warteschlange_wird_nicht_bei_vierzig_gekappt(self):
        # max(0 * 4, 40) ergab 40: Der Lauf hörte nach vierzig Dokumenten
        # auf und fragte, ob er weitermachen soll. Wer die Texterkennung
        # unbeaufsichtigt startete, fand sie danach wartend vor.
        import inspect

        from mailburg.core import erkennung

        quelle = inspect.getsource(erkennung.durchlauf)
        self.assertNotIn("max(budget_dokumente * 4, 40)", quelle)
        self.assertIn("if budget_dokumente else 100_000", quelle)

    def test_mit_budget_bleibt_der_vorrat_begrenzt(self):
        # Beim Häppchen nach dem Abruf soll nicht die ganze Warteschlange
        # geholt werden - das kostet bei zehntausend Anhängen Zeit für
        # nichts.
        import inspect

        from mailburg.core import erkennung

        self.assertIn("(budget_dokumente * 4)",
                      inspect.getsource(erkennung.durchlauf))


class LoeschbefehlTest(unittest.TestCase):
    """Mails eines Postfachs wieder aus dem Archiv nehmen.

    Nötig geworden, weil ein Programmfehler in beide Archive dieselben
    Postfächer geholt hatte (2026-08-26). Der Befehl räumt so etwas auf –
    und muss dabei genau das Gegenteil dessen tun, was ein unbedachtes
    »alles von diesem Konto weg« täte.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "A"
        self.archive = Archive.create(self.wo, name="Probe")

    def _befehl(self, konto: str, wirklich: bool = True) -> int:
        """Ruft den Befehl auf – der öffnet das Archiv selbst, exklusiv.

        Deshalb muss unseres vorher zu sein. Genau das ist im Betrieb
        auch so: Der Befehl läuft, während die Oberfläche geschlossen ist.
        """
        import argparse

        from mailburg.__main__ import cmd_loeschen

        self.archive.close()
        try:
            return cmd_loeschen(argparse.Namespace(
                archiv=str(self.wo), konto=konto,
                grund="irrtuemlich_archiviert", notiz="", wirklich=wirklich,
            ))
        finally:
            self.archive = Archive.open(self.wo)
            self.addCleanup(self.archive.close)

    def _zeilen(self):
        return self.archive.index.db.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]

    def test_nur_was_ausschliesslich_dort_haengt(self) -> None:
        """Eine Mail, die auch anderswo liegt, verlöre sonst zu viel.

        Sie steht in zwei Postfächern – etwa, weil sie an beide ging.
        Wer das Konto aufräumt, will den Fundort loswerden, nicht die
        Nachricht.
        """
        beide = probe("An beide")
        self.archive.add(beide, account="Firma", folder="INBOX")
        self.archive.add(beide, account="Privat", folder="INBOX")
        self.archive.add(probe("Nur Firma"), account="Firma", folder="INBOX")

        self.assertEqual(self._zeilen(), 2)

        self._befehl("Firma")

        # Die gemeinsame bleibt, die alleinige geht.
        uebrig = [r[0] for r in self.archive.index.db.execute(
            "SELECT subject FROM messages")]
        self.assertEqual(uebrig, ["An beide"])

    def test_der_trockenlauf_ist_die_voreinstellung(self) -> None:
        """Wer löscht, tut es einmal – wer sich vertut, merkt es später."""
        self.archive.add(probe("Bleibt"), account="Firma", folder="INBOX")

        self._befehl("Firma", wirklich=False)

        self.assertEqual(self._zeilen(), 1)

    def test_ein_unbekanntes_postfach_ist_kein_fehler(self) -> None:
        self.archive.add(probe("Da"), account="Firma", folder="INBOX")

        ergebnis = self._befehl("Gibtsnicht")

        self.assertEqual(ergebnis, 0)
        self.assertEqual(self._zeilen(), 1)
