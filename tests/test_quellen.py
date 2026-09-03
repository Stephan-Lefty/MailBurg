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


class EvolutionMaildirTest(unittest.TestCase):
    """Eine Sammlung von Maildir-Ordnern ohne eigenes ``cur/``.

    **Der Anlass, gemeldet am 2026-09-03.** Ein Anwender ist unter
    GNOME von Thunderbird auf Evolution umgestiegen und wünschte sich,
    »dass MailBurg auch Mails aus lokalen Ordnern im MBox- oder
    Maildir-Format auslesen und archivieren könnte«.

    Beides konnte MailBurg längst – nur nicht in *dieser* Form. Evolution
    legt seine lokalen Ordner nach Maildir++ ab: Die Wurzel enthält kein
    ``cur/``, sondern Unterverzeichnisse ``.Inbox``, ``.Sent``. Wer sie
    auswählte, bekam die Meldung, das sei kein Maildir.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "local"
        self.wo.mkdir()

    def _maildir(self, name: str, *betreffs: str) -> Path:
        ort = self.wo / name
        for teil in ("cur", "new", "tmp"):
            (ort / teil).mkdir(parents=True)
        for nummer, betreff in enumerate(betreffs):
            # Der Doppelpunkt-Teil ist Maildirs Zustandskodierung.
            (ort / "cur" / f"170000000.{nummer}.rechner:2,S").write_bytes(
                mail(betreff)
            )
        return ort

    def test_evolutions_ordner_werden_erkannt(self):
        self._maildir(".Inbox", "Eins")
        self._maildir(".Sent", "Zwei")

        quelle = open_path(self.wo, "Evolution")
        self.addCleanup(quelle.close)

        self.assertEqual(sorted(quelle.folders()), ["Inbox", "Sent"])

    def test_der_punkt_faellt_weg(self):
        # Sonst stünde im Archiv ein Ordner namens ".Inbox", den
        # niemand wiedererkennt.
        self._maildir(".Inbox", "Eins")
        quelle = open_path(self.wo)
        self.addCleanup(quelle.close)

        self.assertIn("Inbox", quelle.folders())
        self.assertNotIn(".Inbox", quelle.folders())

    def test_maildir_plus_plus_verschachtelt_ueber_punkte(self):
        # ".Projekte.2025" ist der Ordner "2025" unter "Projekte".
        self._maildir(".Projekte.2025", "Eins")
        quelle = open_path(self.wo)
        self.addCleanup(quelle.close)

        self.assertEqual(quelle.folders(), ["Projekte/2025"])

    def test_die_mails_kommen_mit_ordner_und_zustand(self):
        self._maildir(".Inbox", "Eins", "Zwei")
        self._maildir(".Sent", "Drei")

        quelle = open_path(self.wo)
        self.addCleanup(quelle.close)
        nachrichten = list(quelle.iter_messages())

        self.assertEqual(len(nachrichten), 3)
        self.assertEqual(
            sorted({n.folder for n in nachrichten}), ["Inbox", "Sent"]
        )
        self.assertIn("S", nachrichten[0].flags)

    def test_die_bytes_bleiben_unangetastet(self):
        # Der Inhaltshash hängt daran, und mit ihm die DKIM-Signatur.
        self._maildir(".Inbox", "Rechnung")
        quelle = open_path(self.wo)
        self.addCleanup(quelle.close)

        [nachricht] = list(quelle.iter_messages())
        self.assertEqual(nachricht.raw, mail("Rechnung"))

    def test_nebeneinander_gesicherte_maildirs_ohne_punkt(self):
        # Dieselbe Form entsteht, wenn jemand mehrere Maildirs sichert.
        self._maildir("Firma", "Eins")
        self._maildir("Privat", "Zwei")

        quelle = open_path(self.wo)
        self.addCleanup(quelle.close)

        self.assertEqual(sorted(quelle.folders()), ["Firma", "Privat"])

    def test_ein_echtes_maildir_geht_weiterhin_den_alten_weg(self):
        # Die Wurzel selbst hat cur/ - dann ist es ein einzelnes
        # Maildir, keine Sammlung.
        for teil in ("cur", "new", "tmp"):
            (self.wo / teil).mkdir()
        (self.wo / "cur" / "170000000.0.rechner:2,S").write_bytes(mail("Eins"))

        quelle = open_path(self.wo)
        self.addCleanup(quelle.close)

        self.assertIn("INBOX", quelle.folders())

    def test_ein_leeres_verzeichnis_bleibt_ein_fehler(self):
        (self.wo / "nur-ein-ordner").mkdir()

        with self.assertRaises(ValueError) as fall:
            open_path(self.wo)

        # Und die Meldung nennt den Weg, der zum Ziel führt.
        self.assertIn("Evolution", str(fall.exception))


class MaildirZustandTest(unittest.TestCase):
    """Der Lesezustand beim Einlesen eines gewöhnlichen Maildirs.

    **Ein Fehler, der seit jeher drinsteckte.** Maildir kodiert den
    Zustand im Dateinamen hinter ``:2,``. Der Code zerlegte dafür den
    Schlüssel von ``mailbox.Maildir`` – der diesen Teil aber gar nicht
    enthält, weil Python ihn abschneidet. Das Ergebnis war *immer* ein
    leerer Zustand: Jede eingelesene Mail landete als ungelesen im
    Archiv, auch die vor Jahren beantwortete.

    Gefunden am 2026-09-03, und zwar nur, weil für Evolution ein Test
    geschrieben wurde, der den Zustand mitprüft.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Maildir"
        for teil in ("cur", "new", "tmp"):
            (self.wo / teil).mkdir(parents=True)

    def _mail(self, name: str, inhalt: bytes) -> None:
        unter = "new" if ":2," not in name else "cur"
        (self.wo / unter / name).write_bytes(inhalt)

    def test_gelesen_und_beantwortet_kommen_an(self):
        self._mail("170000000.1.rechner:2,SR", mail("Beantwortet"))

        quelle = open_path(self.wo)
        self.addCleanup(quelle.close)
        [nachricht] = list(quelle.iter_messages())

        self.assertIn("S", nachricht.flags)
        self.assertIn("R", nachricht.flags)

    def test_eine_neue_mail_traegt_keinen_zustand(self):
        # In new/ liegt, was noch niemand gesehen hat - dort gibt es
        # keinen ":2,"-Teil, und das ist richtig so.
        self._mail("170000000.2.rechner", mail("Neu"))

        quelle = open_path(self.wo)
        self.addCleanup(quelle.close)
        [nachricht] = list(quelle.iter_messages())

        self.assertEqual(nachricht.flags, "")

    def test_zwei_mails_bekommen_nicht_denselben_zustand(self):
        self._mail("170000000.3.rechner:2,S", mail("Gelesen"))
        self._mail("170000000.4.rechner:2,", mail("Ungelesen"))

        quelle = open_path(self.wo)
        self.addCleanup(quelle.close)
        nach_betreff = {
            n.raw.split(b"Subject: ")[1].split(b"\r\n")[0].decode(): n.flags
            for n in quelle.iter_messages()
        }

        self.assertEqual(nach_betreff["Gelesen"], "S")
        self.assertEqual(nach_betreff["Ungelesen"], "")
