"""Was passiert, wenn der Suchindex aus einer älteren Fassung stammt.

Am 2026-08-31 ging ``SCHEMA_VERSION`` von 1 auf 2 – der Gesprächsverlauf
brauchte eine neue Spalte, und die bliebe für bestehende Mails leer.
Nachrüsten allein reichte also nicht: Ein stiller, halb gefüllter Index
zeigte Verläufe an, die nur die Hälfte enthalten, ohne dass es jemandem
auffiele.

Der Preis dafür ist hart: **Ein Archiv aus 0.12 lässt sich mit der
neuen Fassung zunächst nicht öffnen.** Umso mehr muss stimmen, was
danach kommt. Hier steht, was dabei nicht schiefgehen darf – jeder Fall
stammt aus dem, was beim Bauen tatsächlich schiefging.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mailburg.core import index as index_modul
from mailburg.core import paths
from mailburg.core.archive import Archive, LOCK_FILE, Mode
from mailburg.core.index import SCHEMA_VERSION, IndexOutdated
from mailburg.core.retention import Jurisdiction

from tests.test_archive import probe


def _mail(betreff: str, *, kennung: str, antwort_auf: str = "") -> bytes:
    """Eine Mail mit Kennung – ``probe`` trägt keine, für Gespräche braucht es sie."""
    zeilen = [
        "From: Josef Müller <mueller@example.org>",
        "To: stephan@example.org",
        f"Subject: {betreff}",
        "Date: Fri, 14 Mar 2025 09:30:00 +0000",
        f"Message-ID: {kennung}",
    ]
    if antwort_auf:
        zeilen.append(f"In-Reply-To: {antwort_auf}")
        zeilen.append(f"References: {antwort_auf}")
    return ("\r\n".join(zeilen) + "\r\n\r\nInhalt\r\n").encode("utf-8")


class AeltererIndexTest(unittest.TestCase):
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
            self.wurzel, mode=Mode.PRIVAT, jurisdiction=Jurisdiction.DE, name="Test"
        ) as archiv:
            archiv.add(probe("Angebot"), account="firma", folder="INBOX")
            archiv.index.commit()
            self.index_datei = paths.index_path(archiv.uuid)

    def _auf_alte_fassung_setzen(self) -> None:
        """Stellt einen Index von 0.12 nach – dieselbe Datei, alte Nummer."""
        db = sqlite3.connect(self.index_datei)
        db.execute("PRAGMA user_version = 1")
        db.commit()
        db.close()

    # --------------------------------------------------------- die Meldung

    def test_das_archiv_laesst_sich_nicht_still_oeffnen(self) -> None:
        """Still weiterarbeiten hieße: Verläufe zeigen, die nur halb sind."""
        self._auf_alte_fassung_setzen()
        with self.assertRaises(IndexOutdated):
            Archive.open(self.wurzel)

    def test_die_meldung_nennt_den_befehl_der_hilft(self) -> None:
        """»Muss neu aufgebaut werden« ohne das Wie ist keine Hilfe."""
        self._auf_alte_fassung_setzen()
        with self.assertRaises(IndexOutdated) as gefangen:
            Archive.open(self.wurzel)

        text = str(gefangen.exception)
        self.assertIn("mailburg neuaufbau", text)
        # Und die wichtigste Zusicherung überhaupt.
        self.assertIn("Mails sind davon nicht betroffen", text)

    def test_die_fassungsnummern_haengen_am_fehler(self) -> None:
        """Damit ein Aufrufer entscheiden kann, statt Text zu zerlegen."""
        self._auf_alte_fassung_setzen()
        with self.assertRaises(IndexOutdated) as gefangen:
            Archive.open(self.wurzel)

        self.assertEqual(gefangen.exception.vorhanden, 1)
        self.assertEqual(gefangen.exception.gebraucht, SCHEMA_VERSION)

    # ---------------------------------------------------------- die Sperre

    def test_die_sperre_bleibt_nicht_liegen(self) -> None:
        """Sonst hätte man zwei Probleme statt einem.

        ``_acquire_lock`` läuft vor dem Öffnen des Index. Fliegt der
        Konstruktor danach, ruft niemand mehr ``close()`` – es gibt ja
        kein Objekt. Ohne Aufräumen hieße es beim nächsten Versuch
        »Archiv gesperrt«, und der Grund wäre nirgends zu sehen.
        """
        self._auf_alte_fassung_setzen()
        with self.assertRaises(IndexOutdated):
            Archive.open(self.wurzel)

        self.assertFalse(
            (self.wurzel / LOCK_FILE).exists(),
            "Die Sperrdatei blieb liegen, obwohl das Öffnen scheiterte.",
        )

    # -------------------------------------------------------- der Ausweg

    def test_der_neuaufbau_kommt_an_das_archiv_heran(self) -> None:
        """Der Befehl aus der Meldung darf nicht am selben Fehler scheitern."""
        self._auf_alte_fassung_setzen()
        with Archive.open(self.wurzel, index_verwerfen=True) as archiv:
            self.assertEqual(archiv.rebuild_index(), 1)
            self.assertEqual(archiv.index.count(), 1)

    def test_danach_geht_es_wieder_ohne_besondere_vorkehrung(self) -> None:
        self._auf_alte_fassung_setzen()
        with Archive.open(self.wurzel, index_verwerfen=True) as archiv:
            archiv.rebuild_index()

        with Archive.open(self.wurzel) as archiv:
            self.assertEqual(archiv.index.count(), 1)

    def test_der_neu_gebaute_index_kennt_die_gespraeche(self) -> None:
        """Der ganze Grund für den Neuaufbau – sonst wäre er umsonst.

        Und der Beweis, dass er aus dem Archiv kommt und nicht aus dem
        alten Index: Der ist zu diesem Zeitpunkt gelöscht. Die Kette
        steht in den Kopfzeilen der Mails, die bytegenau daliegen.
        """
        with Archive.open(self.wurzel) as archiv:
            archiv.add(
                _mail("Angebot", kennung="<eins@example.org>"),
                account="firma",
                folder="INBOX",
            )
            archiv.add(
                _mail("Re: Angebot", kennung="<zwei@example.org>",
                      antwort_auf="<eins@example.org>"),
                account="firma",
                folder="INBOX",
            )
            archiv.index.commit()
        self._auf_alte_fassung_setzen()

        with Archive.open(self.wurzel, index_verwerfen=True) as archiv:
            archiv.rebuild_index()
            wurzeln = {
                zeile[0]
                for zeile in archiv.index.db.execute(
                    "SELECT gespraech FROM messages WHERE gespraech <> ''"
                )
            }

        # Beide Mails hängen an derselben Wurzel – die Antwort über
        # ihre ``References``, die erste über ihre eigene Kennung.
        self.assertEqual(wurzeln, {"eins@example.org"})

    # ------------------------------------------------------- das Verwerfen

    def test_verwerfen_nimmt_wal_und_shm_mit(self) -> None:
        """Bleibt der Schreibvorrat liegen, spielt SQLite ihn nachträglich ein.

        Heraus käme ein Index, der halb aus der alten Fassung stammt –
        genau das, wovor das Löschen schützen soll.
        """
        for anhang in ("-wal", "-shm"):
            begleiter = self.index_datei.with_name(self.index_datei.name + anhang)
            begleiter.write_bytes(b"alt")

        index_modul.verwerfen(self.index_datei)

        self.assertFalse(self.index_datei.exists())
        for anhang in ("-wal", "-shm"):
            begleiter = self.index_datei.with_name(self.index_datei.name + anhang)
            self.assertFalse(begleiter.exists(), f"{anhang} blieb liegen")

    def test_verwerfen_stolpert_nicht_ueber_fehlende_dateien(self) -> None:
        """Es wird auch dort gerufen, wo noch nie ein Index lag."""
        index_modul.verwerfen(self.base / "gibt-es-nicht.sqlite")


class KommandozeileTest(unittest.TestCase):
    """Der Weg, den die Meldung vorschlägt, von außen betrachtet."""

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
            self.wurzel, mode=Mode.PRIVAT, jurisdiction=Jurisdiction.DE, name="Test"
        ) as archiv:
            archiv.add(probe("Angebot"), account="firma", folder="INBOX")
            archiv.index.commit()
            datei = paths.index_path(archiv.uuid)

        db = sqlite3.connect(datei)
        db.execute("PRAGMA user_version = 1")
        db.commit()
        db.close()

    def test_neuaufbau_laeuft_auf_einem_alten_index_durch(self) -> None:
        from mailburg.__main__ import main

        self.assertEqual(main(["neuaufbau", str(self.wurzel)]), 0)

    def test_ein_anderer_befehl_meldet_statt_abzustuerzen(self) -> None:
        """Ein Traceback wäre hier das Bild eines Datenverlusts."""
        import io
        from contextlib import redirect_stderr

        from mailburg.__main__ import main

        fehlerstrom = io.StringIO()
        with redirect_stderr(fehlerstrom):
            code = main(["info", str(self.wurzel)])

        self.assertEqual(code, 2)
        self.assertIn("mailburg neuaufbau", fehlerstrom.getvalue())


if __name__ == "__main__":
    unittest.main()
