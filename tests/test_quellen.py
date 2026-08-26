"""Tests für die Mailquellen auf der eigenen Platte.

Schwerpunkt ist das Verzeichnis voller ``.eml``-Dateien. Das ist das
übliche Ergebnis, wenn ein anderes Archivprogramm seine Post herausrückt
– MailStore, Outlook, ein Webmailer –, und damit der Weg, auf dem eine
über Jahre gewachsene Sammlung in ein neues Archiv kommt.

Zwei Dinge dürfen dabei nicht schiefgehen. Die Bytes müssen bleiben, wie
sie sind: Auf ihnen beruht der Inhaltshash, und wer eine Mail
»geradezieht«, macht sie unbeweisbar. Und die Ordnerstruktur muss
erhalten bleiben – sie ist oft die einzige Ordnung, die eine solche
Sammlung noch hat.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mailburg.sources.local import EmlOrdnerSource, _emlx_auspacken, open_path


def mail(betreff: str) -> bytes:
    return (
        f"From: Martha Mustermann <martha@example.com>\r\n"
        f"To: post@example.org\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: Fri, 14 Mar 2025 09:30:00 +0000\r\n\r\n"
        f"Inhalt von {betreff}.\r\n"
    ).encode("utf-8")


class EmlOrdnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name)

    def _ablegen(self, pfad: str, inhalt: bytes) -> Path:
        ziel = self.wo / pfad
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(inhalt)
        return ziel

    # ------------------------------------------------------------- Erkennen

    def test_ein_verzeichnis_mit_eml_wird_erkannt(self) -> None:
        self._ablegen("Rechnungen/2024/eins.eml", mail("Rechnung"))

        quelle = open_path(self.wo)

        self.assertIsInstance(quelle, EmlOrdnerSource)

    def test_ein_leeres_verzeichnis_wird_abgelehnt(self) -> None:
        """Lieber eine klare Absage als eine Quelle, die nichts liefert."""
        with self.assertRaises(ValueError) as fehler:
            open_path(self.wo)

        # Die Meldung muss sagen, was erwartet wurde – sonst rät der
        # Anwender, welchen Ordner er hätte wählen sollen.
        self.assertIn(".eml", str(fehler.exception))

    def test_eine_tiefer_liegende_mail_genuegt(self) -> None:
        """Bei einem Export liegen die Mails selten ganz oben."""
        self._ablegen("a/b/c/d/tief.eml", mail("Tief"))

        self.assertIsInstance(open_path(self.wo), EmlOrdnerSource)

    # -------------------------------------------------------------- Ordner

    def test_die_verzeichnisse_werden_zu_fundorten(self) -> None:
        self._ablegen("Rechnungen/2024/eins.eml", mail("A"))
        self._ablegen("Rechnungen/2025/zwei.eml", mail("B"))
        self._ablegen("Privat/drei.eml", mail("C"))

        self.assertEqual(
            EmlOrdnerSource(self.wo).folders(),
            ["Privat", "Rechnungen/2024", "Rechnungen/2025"],
        )

    def test_eine_mail_ganz_oben_bekommt_den_kontonamen(self) -> None:
        """».« wäre ein Fundort, den niemand so geschrieben hätte."""
        self._ablegen("allein.eml", mail("Allein"))

        quelle = EmlOrdnerSource(self.wo, account="MailStore")

        self.assertEqual(quelle.folders(), ["MailStore"])

    # --------------------------------------------------------------- Lesen

    def test_die_bytes_bleiben_unveraendert(self) -> None:
        """Der Inhaltshash hängt daran – hier wird nichts geradegezogen."""
        roh = mail("Unverändert")
        self._ablegen("Ordner/eins.eml", roh)

        nachrichten = list(EmlOrdnerSource(self.wo).iter_messages())

        self.assertEqual(len(nachrichten), 1)
        self.assertEqual(nachrichten[0].raw, roh)
        self.assertEqual(nachrichten[0].folder, "Ordner")

    def test_leere_dateien_werden_uebergangen(self) -> None:
        self._ablegen("Ordner/leer.eml", b"")
        self._ablegen("Ordner/voll.eml", mail("Voll"))

        nachrichten = list(EmlOrdnerSource(self.wo).iter_messages())

        self.assertEqual(len(nachrichten), 1)

    def test_fremde_dateien_stoeren_nicht(self) -> None:
        """Neben den Mails liegt bei einem Export oft Beiwerk."""
        self._ablegen("Ordner/eins.eml", mail("Eins"))
        self._ablegen("Ordner/index.html", "<html>Übersicht</html>".encode("utf-8"))
        self._ablegen("Ordner/Anhang.pdf", b"%PDF-1.4")

        nachrichten = list(EmlOrdnerSource(self.wo).iter_messages())

        self.assertEqual(len(nachrichten), 1)

    def test_versteckte_dateien_werden_uebergangen(self) -> None:
        self._ablegen("Ordner/.gelöscht.eml", mail("Weg"))
        self._ablegen("Ordner/eins.eml", mail("Da"))

        nachrichten = list(EmlOrdnerSource(self.wo).iter_messages())

        self.assertEqual(len(nachrichten), 1)

    def test_eine_unlesbare_datei_haelt_den_import_nicht_an(self) -> None:
        """Bei zehntausend Mails darf eine kaputte nicht alles kippen.

        Was fehlt, fällt beim Abgleich der Anzahl auf – das ist besser,
        als bei Mail 4.000 abzubrechen und von vorn anfangen zu müssen.
        """
        import os

        self._ablegen("Ordner/eins.eml", mail("Eins"))
        gesperrt = self._ablegen("Ordner/zwei.eml", mail("Zwei"))
        os.chmod(gesperrt, 0o000)
        self.addCleanup(os.chmod, gesperrt, 0o644)

        if os.geteuid() == 0:
            self.skipTest("als root ist keine Datei unlesbar")

        nachrichten = list(EmlOrdnerSource(self.wo).iter_messages())

        self.assertEqual(len(nachrichten), 1)


class EmlxTest(unittest.TestCase):
    """Apple Mail legt dieselbe Mail mit Beiwerk ab.

    Der Aufbau: eine Zeile mit der Länge, dann die Mail, dann ein
    Property-List-Anhang mit Apples Verwaltungsdaten. Beides gehört nicht
    zur Mail – bliebe es stehen, sähe dieselbe Nachricht unter macOS
    anders aus als überall sonst, und der Inhaltshash wiche ab.
    """

    def test_laengenangabe_und_anhang_fallen_weg(self) -> None:
        roh = mail("Von Apple")
        datei = str(len(roh)).encode() + b"\n" + roh + b"<?xml version=...?>"

        self.assertEqual(_emlx_auspacken(datei), roh)

    def test_eine_unsinnige_laengenangabe_laesst_alles_stehen(self) -> None:
        """Lieber eine Mail mit Beiwerk als gar keine."""
        datei = b"keine Zahl\nInhalt"

        self.assertEqual(_emlx_auspacken(datei), datei)

    def test_eine_zu_grosse_laengenangabe_laesst_alles_stehen(self) -> None:
        datei = b"99999\nkurz"

        self.assertEqual(_emlx_auspacken(datei), datei)

    def test_emlx_dateien_werden_beim_lesen_ausgepackt(self) -> None:
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        wo = Path(ordner.name)
        roh = mail("Von Apple")
        (wo / "Posteingang").mkdir()
        (wo / "Posteingang" / "eins.emlx").write_bytes(
            str(len(roh)).encode() + b"\n" + roh + b"<?xml version=...?>"
        )

        nachrichten = list(EmlOrdnerSource(wo).iter_messages())

        self.assertEqual(nachrichten[0].raw, roh)


if __name__ == "__main__":
    unittest.main()
