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
        roh = b"From: a@b.de\r\nSubject: Zeitlos\r\n\r\nOhne Datumszeile"
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
