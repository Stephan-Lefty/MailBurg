"""Tests für die Texterkennung – vor allem für das, was sie *nicht* tut.

Der teuerste Fehler der Texterkennung ist doppelte Arbeit. Ein Vertrag,
der einmal weitergeleitet und dreimal beantwortet wurde, hängt an fünf
Mails. Fünf verschiedene Mails – aber ein einziges Dokument, Byte für
Byte dasselbe. Wer das nicht bemerkt, lässt tesseract fünfmal über
dieselben zwanzig Seiten laufen und bekommt fünfmal denselben Text.

Aufgefallen ist es am 2026-08-26 an einem echten Geschäftsarchiv: Von
zwölf verbliebenen Aufträgen waren es drei Dokumente. Eine
23-MB-Vollmacht stand neunmal in der Warteschlange.

Die Erkennung selbst wird hier nicht ausgeführt – tesseract ist auf
einem Testrechner nicht vorauszusetzen, und was es ausrechnet, ist auch
nicht Gegenstand dieser Tests. Ersetzt wird sie durch einen Zähler.
"""

from __future__ import annotations

import email.utils
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from mailburg.core import erkennung
from mailburg.core.archive import Archive
from mailburg.extract import ocr


def mail_mit_anhang(betreff: str, dateiname: str, inhalt: bytes,
                    tag: int = 14) -> bytes:
    """Eine Mail mit genau einem PDF-Anhang.

    ``inhalt`` bestimmt, ob zwei Mails denselben Anhang tragen: Die
    Erkennung vergleicht die Bytes des Anhangs, nicht den Dateinamen.
    """
    datum = email.utils.format_datetime(
        datetime(2025, 3, tag, 9, 30, tzinfo=timezone.utc)
    )
    import base64

    kodiert = base64.b64encode(inhalt).decode("ascii")
    return (
        f"From: Martha Mustermann <martha@example.com>\r\n"
        f"To: post@example.org\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: {datum}\r\n"
        'Content-Type: multipart/mixed; boundary="G"\r\n\r\n'
        "--G\r\nContent-Type: text/plain\r\n\r\n"
        "Anbei.\r\n"
        f"--G\r\nContent-Type: application/pdf\r\n"
        f"Content-Transfer-Encoding: base64\r\n"
        f'Content-Disposition: attachment; filename="{dateiname}"\r\n\r\n'
        f"{kodiert}\r\n--G--\r\n"
    ).encode("utf-8")


#: Groß genug, um die Größenschwelle zu überschreiten – darunter lohnt
#: die Erkennung nicht und die Warteschlange lässt es liegen.
GROSS = erkennung.GROESSENSCHWELLE + 5_000


class TestDoppelteAnhaenge(unittest.TestCase):
    """Derselbe Anhang an mehreren Mails wird nur einmal gelesen."""

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.archiv = Archive.create(Path(self.ordner.name) / "A", name="Probe")
        self.gelesen: list[bytes] = []

    def tearDown(self) -> None:
        self.archiv.close()
        self.ordner.cleanup()

    def _ablegen(self, mails: list[bytes]) -> None:
        for nr, roh in enumerate(mails):
            self.archiv.add(roh, account="probe", folder=f"INBOX/{nr}")
        # Die Anhänge als »ohne Textebene« markieren. Im Betrieb macht
        # das die Extraktion beim Archivieren; hier wären es Attrappen,
        # aus denen poppler nie Text holen könnte.
        self.archiv.index.db.execute("UPDATE attachments SET text_zeichen = 0")
        self.archiv.index.commit()

    def _durchlauf(self, **kw):
        def gefaelscht(nutzlast, **_):
            self.gelesen.append(nutzlast)
            ergebnis = ocr.Ergebnis()
            ergebnis.text = f"Erkannt: {len(nutzlast)} Bytes"
            ergebnis.seiten = 3
            return ergebnis

        with mock.patch.object(ocr, "bereit", return_value=(True, "")), \
                mock.patch.object(ocr, "text_aus_pdf", side_effect=gefaelscht):
            return erkennung.durchlauf(
                self.archiv, budget_sekunden=0, budget_dokumente=0, **kw
            )

    # --------------------------------------------------------------- Kern

    def test_derselbe_anhang_wird_nur_einmal_gelesen(self) -> None:
        gleich = b"%PDF-Vollmacht" + b"x" * GROSS
        self._ablegen([
            mail_mit_anhang("Vollmacht", "Vollmacht.pdf", gleich, tag=1),
            mail_mit_anhang("Fwd: Vollmacht", "Vollmacht.pdf", gleich, tag=2),
            mail_mit_anhang("Re: Vollmacht", "Vollmacht.pdf", gleich, tag=3),
        ])

        stat = self._durchlauf(gleichzeitig=1)

        self.assertEqual(len(self.gelesen), 1, "tesseract lief mehr als einmal")
        self.assertEqual(stat.gelesen, 3, "nicht alle drei Mails gelten als erledigt")
        self.assertEqual(stat.doppelt, 2)
        self.assertEqual(stat.seiten, 3, "Seiten doppelt gezählt")
        self.assertEqual(stat.offen_danach, 0)

    def test_greift_auch_innerhalb_eines_buendels(self) -> None:
        """Die Dubletten liegen nach der Größensortierung nebeneinander.

        Damit landen sie im selben Bündel – wo ein Zwischenspeicher, der
        erst nach dem Bündel gefüllt wird, zu spät käme. Genau dieser
        Fall wäre in der Praxis der Regelfall.
        """
        gleich = b"%PDF-Zeugnismappe" + b"y" * GROSS
        self._ablegen([
            mail_mit_anhang(f"Mappe {i}", "Zeugnismappe.pdf", gleich, tag=i)
            for i in range(1, 5)
        ])

        stat = self._durchlauf(gleichzeitig=4)

        self.assertEqual(len(self.gelesen), 1)
        self.assertEqual(stat.gelesen, 4)
        self.assertEqual(stat.doppelt, 3)

    def test_verschiedene_anhaenge_werden_einzeln_gelesen(self) -> None:
        """Der gleiche Dateiname macht noch keine Dublette."""
        self._ablegen([
            mail_mit_anhang("Rechnung März", "Rechnung.pdf",
                            b"%PDF-A" + b"a" * GROSS, tag=1),
            mail_mit_anhang("Rechnung April", "Rechnung.pdf",
                            b"%PDF-B" + b"b" * GROSS, tag=2),
        ])

        stat = self._durchlauf(gleichzeitig=2)

        self.assertEqual(len(self.gelesen), 2)
        self.assertEqual(stat.gelesen, 2)
        self.assertEqual(stat.doppelt, 0)
        self.assertEqual(stat.seiten, 6)

    def test_jede_mail_wird_einzeln_durchsuchbar(self) -> None:
        """Der Sinn der Sache: Auch die Abschriften muss man finden.

        Gespart wird die Erkennung, nicht der Eintrag im Suchindex. Der
        hängt an der Mail – wer nach dem Inhalt sucht, soll alle drei
        Mails finden, nicht nur die zuerst gelesene.
        """
        gleich = b"%PDF-Kuendigung" + b"z" * GROSS
        self._ablegen([
            mail_mit_anhang("Kündigung", "K.pdf", gleich, tag=1),
            mail_mit_anhang("Fwd: Kündigung", "K.pdf", gleich, tag=2),
        ])

        self._durchlauf(gleichzeitig=2)

        treffer = self.archiv.index.search("Erkannt")
        self.assertEqual(
            len(treffer), 2,
            "die Abschrift ist nicht durchsuchbar geworden",
        )

    def test_gescheiterter_erstling_gilt_auch_fuer_die_abschrift(self) -> None:
        """Was beim Erstling nicht zu lesen war, ist auch sonst nicht lesbar.

        Beide werden als gescheitert vermerkt – nicht offengelassen. Ein
        Dokument ohne erkennbaren Text bleibt auch beim zehnten Anlauf
        ohne erkennbaren Text; wer es offenließe, hätte eine
        Warteschlange, die nie leer wird.

        Der Abbruch wegen Zeitablauf ist etwas anderes: Da hat die
        Erkennung nicht versagt, sondern nicht zu Ende gearbeitet. Dann
        wird nichts vermerkt und der nächste Lauf beginnt von vorn.
        """
        gleich = b"%PDF-Kaputt" + b"q" * GROSS
        self._ablegen([
            mail_mit_anhang("Kaputt", "K.pdf", gleich, tag=1),
            mail_mit_anhang("Fwd: Kaputt", "K.pdf", gleich, tag=2),
        ])

        def leer(nutzlast, **_):
            self.gelesen.append(nutzlast)
            ergebnis = ocr.Ergebnis()
            ergebnis.fehler = "nichts zu erkennen"
            return ergebnis

        with mock.patch.object(ocr, "bereit", return_value=(True, "")), \
                mock.patch.object(ocr, "text_aus_pdf", side_effect=leer):
            stat = erkennung.durchlauf(
                self.archiv, budget_sekunden=0, budget_dokumente=0,
                gleichzeitig=2,
            )

        self.assertEqual(stat.gescheitert, 2)
        self.assertEqual(len(self.gelesen), 1, "die Abschrift wurde erneut gelesen")
        self.assertEqual(stat.offen_danach, 0)


class TestReihenfolge(unittest.TestCase):
    """Die kleinsten Dokumente zuerst."""

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.archiv = Archive.create(Path(self.ordner.name) / "A", name="Probe")

    def tearDown(self) -> None:
        self.archiv.close()
        self.ordner.cleanup()

    def test_kleine_vor_grossen(self) -> None:
        """Wer abbricht, soll möglichst viel erledigt haben.

        Ein 20-MB-Scan kann eine Viertelstunde dauern. Steht er vorn,
        passiert in dieser Viertelstunde sichtbar nichts.
        """
        for name, groesse in (("gross", GROSS * 4), ("klein", GROSS),
                              ("mittel", GROSS * 2)):
            self.archiv.add(
                mail_mit_anhang(name, f"{name}.pdf", b"%PDF" + b"x" * groesse),
                account="probe", folder="INBOX",
            )
        self.archiv.index.db.execute("UPDATE attachments SET text_zeichen = 0")
        self.archiv.index.commit()

        offen = erkennung.Warteschlange(self.archiv.index).offen(grenze=10)

        self.assertEqual(
            [n for _, _, n in offen],
            ["klein.pdf", "mittel.pdf", "gross.pdf"],
        )


if __name__ == "__main__":
    unittest.main()
