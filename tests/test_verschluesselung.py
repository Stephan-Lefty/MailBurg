"""Ein verschlüsseltes Archiv, von außen betrachtet.

:mod:`tests.test_krypto` prüft die Schlüssel für sich. Hier steht, was
davon im fertigen Archiv ankommt – und vor allem, was *nicht* auf der
Platte landen darf.

**Die Prüfungen sind absichtlich stumpf.** Sie suchen nach Klartext in
Dateien, statt Verfahren nachzurechnen. Ein Fehler in einer
Verschlüsselung fällt nämlich nicht dadurch auf, dass etwas nicht
funktioniert – es funktioniert alles weiter, nur liegt der Betreff noch
lesbar auf der Platte.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import krypto, paths
from mailburg.core.archive import Archive, Mode
from mailburg.core.krypto import FalschesPasswort
from mailburg.core.retention import Jurisdiction

PASSWORT = "ein ziemlich langes Passwort"

#: Alles daran ist verräterisch: Absender, Betreff, Text.
GEHEIME_MAIL = (
    b"From: Josef Meier <meier@example.org>\r\n"
    b"To: stephan@example.org\r\n"
    b"Subject: Kuendigung zum Quartalsende\r\n"
    b"Date: Fri, 14 Mar 2025 09:30:00 +0000\r\n"
    b"Message-ID: <eins@example.org>\r\n"
    b"\r\n"
    b"Sehr geehrte Damen und Herren, hiermit kuendige ich.\r\n"
)

#: Wonach in den Dateien gesucht wird – jedes davon stünde ohne
#: Verschlüsselung im Klartext auf der Platte.
VERRAETERISCH = [
    b"Kuendigung",
    b"meier@example.org",
    b"kuendige",
    b"Quartalsende",
]


class VerschluesseltesArchivTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        patcher = mock.patch.object(
            paths, "data_dir", return_value=self.base / "daten"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.base / "daten").mkdir(parents=True, exist_ok=True)

        # Kleine Kennwerte: Die Härte prüft test_krypto, hier zählt die
        # Mechanik. Mit 2^17 dauerte jeder einzelne Test eine Sekunde.
        self._n = krypto.SCRYPT_N
        krypto.SCRYPT_N = 2 ** 8
        self.addCleanup(self._n_zuruecksetzen)

        self.wurzel = self.base / "archiv"
        with Archive.create(
            self.wurzel, mode=Mode.PRIVAT, jurisdiction=Jurisdiction.DE,
            name="Geheim", passwort=PASSWORT,
        ) as archiv:
            self.notschluessel = archiv.notschluessel
            archiv.add(GEHEIME_MAIL, account="firma", folder="INBOX")
            archiv.index.commit()

    def _n_zuruecksetzen(self) -> None:
        krypto.SCRYPT_N = self._n

    def _dateien(self, unterordner: str) -> list[Path]:
        return [p for p in (self.wurzel / unterordner).rglob("*") if p.is_file()]

    # ------------------------------------------------- Was auf der Platte steht

    def test_in_der_ablage_steht_nichts_lesbares(self):
        for datei in self._dateien("mail"):
            inhalt = datei.read_bytes()
            for wort in VERRAETERISCH:
                with self.subTest(datei=datei.name, wort=wort):
                    self.assertNotIn(wort, inhalt)

    def test_im_journal_steht_nichts_lesbares(self):
        """Das Journal ist die Wahrheit – dort steht alles über jede Mail."""
        for datei in self._dateien("meta"):
            inhalt = datei.read_bytes()
            for wort in VERRAETERISCH + [b"firma", b"INBOX"]:
                with self.subTest(datei=datei.name, wort=wort):
                    self.assertNotIn(wort, inhalt)

    def test_der_dateiname_ist_nicht_der_hash_der_mail(self):
        """Sonst wäre »liegt diese Mail hier?« ohne Schlüssel beantwortet."""
        from mailburg.core.store import content_hash

        echter_hash = content_hash(GEHEIME_MAIL)
        namen = [p.name for p in self._dateien("mail")]

        self.assertEqual(len(namen), 1)
        self.assertNotIn(echter_hash, namen[0])

    def test_im_klartext_bleibt_nur_was_bleiben_muss(self):
        """``archive.json`` sagt, dass verschlüsselt wurde – und wie.

        Sie kann nicht selbst verschlüsselt sein: In ihr stehen die
        Angaben, die man zum Entschlüsseln braucht.
        """
        meta = json.loads((self.wurzel / "archive.json").read_text(encoding="utf-8"))

        self.assertTrue(meta["encryption"])
        self.assertEqual(meta["encryption"]["verfahren"], "aes-256-gcm")
        # Aber kein Schlüssel und kein Passwort.
        roh = (self.wurzel / "archive.json").read_text(encoding="utf-8")
        self.assertNotIn(PASSWORT, roh)
        self.assertNotIn(self.notschluessel, roh)

    # -------------------------------------------------------- Wieder herankommen

    def test_mit_passwort_geht_alles_wie_vorher(self):
        with Archive.open(self.wurzel, passwort=PASSWORT) as archiv:
            treffer = archiv.index.search("kuendigung")

            self.assertEqual(len(treffer), 1)
            self.assertEqual(
                archiv.store.get(treffer[0].hash, treffer[0].bucket), GEHEIME_MAIL
            )

    def test_der_notschluessel_oeffnet_es_auch(self):
        with Archive.open(self.wurzel, passwort=self.notschluessel) as archiv:
            self.assertEqual(archiv.index.count(), 1)

    def test_ohne_passwort_kommt_eine_verstaendliche_absage(self):
        with self.assertRaises(FalschesPasswort) as gefangen:
            Archive.open(self.wurzel)

        self.assertIn("verschlüsselt", str(gefangen.exception))

    def test_ein_falsches_passwort_oeffnet_nichts(self):
        with self.assertRaises(FalschesPasswort):
            Archive.open(self.wurzel, passwort="daneben")

    def test_die_sperre_bleibt_auch_hier_nicht_liegen(self):
        """Dieselbe Falle wie beim veralteten Index – siehe test_index_fassung."""
        from mailburg.core.archive import LOCK_FILE

        with self.assertRaises(FalschesPasswort):
            Archive.open(self.wurzel, passwort="daneben")

        self.assertFalse((self.wurzel / LOCK_FILE).exists())

    def test_von_aussen_erkennbar_ohne_es_zu_oeffnen(self):
        """Damit ein Aufrufer fragen kann, bevor er ins Leere greift."""
        self.assertTrue(Archive.ist_verschluesselt(self.wurzel))

    # --------------------------------------------------- Die Arbeitsgänge

    def test_die_kette_laesst_sich_pruefen(self):
        with Archive.open(self.wurzel, passwort=PASSWORT) as archiv:
            self.assertTrue(archiv.journal.verify().ok)

    def test_der_abgleich_findet_seine_dateien_wieder(self):
        """Er vergleicht Journal und Ablage – über verdeckte Namen."""
        with Archive.open(self.wurzel, passwort=PASSWORT) as archiv:
            bericht = archiv.verify()

            self.assertTrue(bericht["ok"], bericht)
            self.assertEqual(bericht["expected"], 1)
            self.assertEqual(bericht["on_disk"], 1)

    def test_eine_untergeschobene_datei_faellt_auf(self):
        gefaelscht = self.wurzel / "mail" / "2025" / "03" / "ab" / ("ab" + "0" * 62)
        gefaelscht.parent.mkdir(parents=True, exist_ok=True)
        gefaelscht.with_name(gefaelscht.name + ".eml.mbk").write_bytes(b"untergeschoben")

        with Archive.open(self.wurzel, passwort=PASSWORT) as archiv:
            self.assertFalse(archiv.verify()["ok"])

    def test_der_index_laesst_sich_neu_bauen(self):
        """Der Beweis, dass Journal und Ablage allein genügen."""
        with Archive.open(self.wurzel, passwort=PASSWORT) as archiv:
            self.assertEqual(archiv.rebuild_index(), 1)
            self.assertEqual(len(archiv.index.search("kuendigung")), 1)

    def test_eine_veraenderte_maildatei_faellt_beim_lesen_auf(self):
        datei = self._dateien("mail")[0]
        inhalt = bytearray(datei.read_bytes())
        inhalt[-1] ^= 0x01
        datei.write_bytes(bytes(inhalt))

        with Archive.open(self.wurzel, passwort=PASSWORT) as archiv:
            treffer = archiv.index.search("kuendigung")
            with self.assertRaises(krypto.KryptoFehler):
                archiv.store.get(treffer[0].hash, treffer[0].bucket)

    def test_eine_veraenderte_journalzeile_faellt_sofort_auf(self):
        """Und zwar beim Öffnen, mit einer Ansage statt eines Tracebacks.

        Betroffen ist hier die *erste* Zeile. Die letzte fiele unter die
        Nachsicht für abgebrochene Schreibvorgänge – ein Absturz kann nur
        sie erwischen.
        """
        from mailburg.core.journal import JournalBeschaedigt

        datei = [p for p in self._dateien("meta") if p.suffix == ".jsonl"][0]
        zeilen = datei.read_bytes().splitlines()
        zeilen[0] = zeilen[0][:-5] + b"AAAA="
        datei.write_bytes(b"\n".join(zeilen) + b"\n")

        with self.assertRaises(JournalBeschaedigt) as gefangen:
            Archive.open(self.wurzel, passwort=PASSWORT)

        text = str(gefangen.exception)
        self.assertIn("Ihre Mails liegen davon unberührt", text)
        self.assertIn("Sicherung", text)

    def test_auch_dann_bleibt_keine_sperre_liegen(self):
        from mailburg.core.archive import LOCK_FILE
        from mailburg.core.journal import JournalBeschaedigt

        datei = [p for p in self._dateien("meta") if p.suffix == ".jsonl"][0]
        zeilen = datei.read_bytes().splitlines()
        zeilen[0] = zeilen[0][:-5] + b"AAAA="
        datei.write_bytes(b"\n".join(zeilen) + b"\n")

        with self.assertRaises(JournalBeschaedigt):
            Archive.open(self.wurzel, passwort=PASSWORT)

        self.assertFalse((self.wurzel / LOCK_FILE).exists())


class UnverschluesseltBleibtUnveraendertTest(unittest.TestCase):
    """Der häufigste Fall darf von alldem nichts merken."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        patcher = mock.patch.object(
            paths, "data_dir", return_value=self.base / "daten"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.base / "daten").mkdir(parents=True, exist_ok=True)

        self.wurzel = self.base / "archiv"
        with Archive.create(
            self.wurzel, mode=Mode.PRIVAT, jurisdiction=Jurisdiction.DE, name="Offen"
        ) as archiv:
            archiv.add(GEHEIME_MAIL, account="firma", folder="INBOX")
            archiv.index.commit()

    def test_es_wird_nicht_nach_einem_passwort_gefragt(self):
        with Archive.open(self.wurzel) as archiv:
            self.assertEqual(archiv.index.count(), 1)

    def test_es_gilt_nicht_als_verschluesselt(self):
        self.assertFalse(Archive.ist_verschluesselt(self.wurzel))

    def test_der_dateiname_ist_weiterhin_der_hash(self):
        """Bestehende Archive dürfen sich nicht plötzlich anders verhalten."""
        from mailburg.core.store import content_hash

        dateien = [p for p in (self.wurzel / "mail").rglob("*") if p.is_file()]

        self.assertIn(content_hash(GEHEIME_MAIL), dateien[0].name)

    def test_das_journal_bleibt_lesbarer_text(self):
        datei = [p for p in (self.wurzel / "meta").rglob("*.jsonl")][0]

        self.assertIn(b'"op":"add"', datei.read_bytes())


class PasswortWechselAmArchivTest(unittest.TestCase):
    """Der Wechsel darf die Mails nicht anfassen."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        patcher = mock.patch.object(
            paths, "data_dir", return_value=self.base / "daten"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.base / "daten").mkdir(parents=True, exist_ok=True)

        self._n = krypto.SCRYPT_N
        krypto.SCRYPT_N = 2 ** 8
        self.addCleanup(lambda: setattr(krypto, "SCRYPT_N", self._n))

        self.wurzel = self.base / "archiv"
        with Archive.create(
            self.wurzel, mode=Mode.PRIVAT, jurisdiction=Jurisdiction.DE,
            name="Geheim", passwort="altes",
        ) as archiv:
            self.notschluessel = archiv.notschluessel
            archiv.add(GEHEIME_MAIL, account="firma", folder="INBOX")
            archiv.index.commit()

    def _wechseln(self, altes: str, neues: str) -> None:
        """Was ``mailburg passwort aendern`` tut, ohne die Abfrage."""
        datei = self.wurzel / "archive.json"
        meta = json.loads(datei.read_text(encoding="utf-8"))
        huelle = krypto.Huelle.aus_json(meta["encryption"])
        schluessel = huelle.oeffnen(altes)
        meta["encryption"] = huelle.passwort_wechseln(schluessel, neues).als_json()
        datei.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def test_danach_gilt_das_neue(self):
        self._wechseln("altes", "neues")

        with Archive.open(self.wurzel, passwort="neues") as archiv:
            self.assertEqual(archiv.index.count(), 1)

    def test_das_alte_gilt_nicht_mehr(self):
        self._wechseln("altes", "neues")

        with self.assertRaises(FalschesPasswort):
            Archive.open(self.wurzel, passwort="altes")

    def test_die_mails_bleiben_unangetastet(self):
        """Sonst müsste ein Wechsel 700.000 Dateien neu schreiben."""
        vorher = {
            p: p.read_bytes()
            for p in (self.wurzel / "mail").rglob("*") if p.is_file()
        }

        self._wechseln("altes", "neues")

        nachher = {
            p: p.read_bytes()
            for p in (self.wurzel / "mail").rglob("*") if p.is_file()
        }
        self.assertEqual(vorher, nachher)

    def test_der_notschluessel_gilt_weiter(self):
        self._wechseln("altes", "neues")

        with Archive.open(self.wurzel, passwort=self.notschluessel) as archiv:
            self.assertEqual(archiv.index.count(), 1)


if __name__ == "__main__":
    unittest.main()
