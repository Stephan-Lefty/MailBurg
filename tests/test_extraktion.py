"""Tests für die Textextraktion aus Anhängen.

Der Schwerpunkt liegt auf Robustheit. Ein Anhang, der sich nicht lesen
lässt, darf niemals verhindern, dass die Mail archiviert wird – deshalb
sind hier vor allem kaputte, gelogene und leere Dateien versammelt.
"""

from __future__ import annotations

import io
import unittest
import zipfile

from mailburg.extract import office, pdf, text


def docx_bauen(inhalt: str) -> bytes:
    """Baut ein DOCX mit dem angegebenen Text – so schlank wie möglich."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr(
            "word/document.xml",
            '<?xml version="1.0"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{inhalt}</w:t></w:r></w:p></w:body></w:document>",
        )
    return puffer.getvalue()


def odt_bauen(inhalt: str) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr(
            "content.xml",
            '<?xml version="1.0"?>'
            '<office:document-content xmlns:office="urn:oasis:x" xmlns:text="urn:oasis:y">'
            f"<office:body><text:p>{inhalt}</text:p></office:body></office:document-content>",
        )
    return puffer.getvalue()


class TestBueroformate(unittest.TestCase):
    def test_docx(self) -> None:
        ergebnis = office.text_aus_zip_dokument(docx_bauen("Schlussrechnung Südhang"), "docx")
        self.assertIn("Schlussrechnung", ergebnis)
        self.assertIn("Südhang", ergebnis)

    def test_odt(self) -> None:
        ergebnis = office.text_aus_zip_dokument(odt_bauen("Vertrag über Grüße"), "odt")
        self.assertIn("Vertrag", ergebnis)
        self.assertIn("Grüße", ergebnis)

    def test_makrovariante_wird_wie_das_original_behandelt(self) -> None:
        ergebnis = office.text_aus_zip_dokument(docx_bauen("Inhalt"), "docm")
        self.assertIn("Inhalt", ergebnis)

    def test_kein_zip_ergibt_leeren_text(self) -> None:
        self.assertEqual(office.text_aus_zip_dokument(b"kein zip", "docx"), "")

    def test_zip_ohne_erwarteten_inhalt(self) -> None:
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w") as z:
            z.writestr("irgendwas.txt", "Text")
        self.assertEqual(office.text_aus_zip_dokument(puffer.getvalue(), "docx"), "")

    def test_kaputtes_xml_im_zip(self) -> None:
        """Ein unvollständiges Dokument darf keinen Fehler auslösen."""
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w") as z:
            z.writestr("word/document.xml", "<w:document><w:t>offen")
        self.assertEqual(office.text_aus_zip_dokument(puffer.getvalue(), "docx"), "")

    def test_unbekannte_endung(self) -> None:
        self.assertEqual(office.text_aus_zip_dokument(docx_bauen("x"), "xyz"), "")

    def test_leere_daten(self) -> None:
        self.assertEqual(office.text_aus_zip_dokument(b"", "docx"), "")


class TestRtf(unittest.TestCase):
    def test_einfacher_text(self) -> None:
        roh = rb"{\rtf1\ansi\deff0 {\fonttbl{\f0 Arial;}}Hallo Welt\par}"
        ergebnis = office.text_aus_rtf(roh)
        self.assertIn("Hallo Welt", ergebnis)

    def test_umlaute_in_hexschreibweise(self) -> None:
        roh = rb"{\rtf1\ansi Gr\'fc\'dfe aus M\'fcnchen}"
        ergebnis = office.text_aus_rtf(roh)
        self.assertIn("Grüße", ergebnis)

    def test_kein_rtf(self) -> None:
        self.assertEqual(office.text_aus_rtf(b"nur Text"), "")


class TestPdf(unittest.TestCase):
    def test_kein_pdf(self) -> None:
        self.assertEqual(pdf.text_aus_pdf(b"kein PDF"), "")

    def test_leere_daten(self) -> None:
        self.assertEqual(pdf.text_aus_pdf(b""), "")

    def test_abgeschnittenes_pdf_stuerzt_nicht_ab(self) -> None:
        """Nur der Kopf stimmt, der Rest fehlt – kommt bei Mailanhängen vor."""
        self.assertIsInstance(pdf.text_aus_pdf(b"%PDF-1.4\nabgeschnitten"), str)

    def test_gescanntes_erkennen(self) -> None:
        gross = b"x" * 200_000
        self.assertTrue(pdf.ist_wohl_gescannt(gross, ""))
        self.assertFalse(pdf.ist_wohl_gescannt(gross, "viel Text " * 100))
        self.assertFalse(pdf.ist_wohl_gescannt(b"klein", ""))


class TestDispatcher(unittest.TestCase):
    def test_bilder_werden_uebergangen(self) -> None:
        for name in ("bild.png", "foto.JPG", "logo.gif"):
            with self.subTest(name=name):
                self.assertEqual(text.aus_anhang(name, "image/png", b"\x89PNG..").art, "uebergangen")

    def test_archive_werden_uebergangen(self) -> None:
        self.assertEqual(text.aus_anhang("x.zip", "application/zip", b"PK\x03\x04").art,
                         "uebergangen")

    def test_reiner_text(self) -> None:
        ergebnis = text.aus_anhang("notiz.txt", "text/plain", "Rechnung über 100 €".encode())
        self.assertIn("Rechnung", ergebnis.text)

    def test_docx_ueber_dispatcher(self) -> None:
        ergebnis = text.aus_anhang("brief.docx", "application/octet-stream", docx_bauen("Angebot"))
        self.assertEqual(ergebnis.art, "office")
        self.assertIn("Angebot", ergebnis.text)

    def test_gelogener_mimetyp_schadet_nicht(self) -> None:
        """In Mails steht oft application/octet-stream für alles."""
        ergebnis = text.aus_anhang("x.docx", "application/octet-stream", docx_bauen("Text"))
        self.assertIn("Text", ergebnis.text)

    def test_zu_grosser_anhang(self) -> None:
        gross = b"x" * (text.MAX_ANHANG_BYTES + 1)
        ergebnis = text.aus_anhang("riesig.pdf", "application/pdf", gross)
        self.assertEqual(ergebnis.art, "uebergangen")
        self.assertTrue(ergebnis.hinweis)

    def test_leerer_anhang(self) -> None:
        self.assertEqual(text.aus_anhang("leer.pdf", "application/pdf", b"").art, "leer")

    def test_unbekannte_endung_mit_textinhalt(self) -> None:
        """Namenlose Anhänge sind häufig – wenn es Text ist, nehmen wir ihn."""
        ergebnis = text.aus_anhang("unbenannt.dat", "application/octet-stream",
                                   b"Sehr geehrte Damen und Herren")
        self.assertIn("geehrte", ergebnis.text)

    def test_unbekannte_endung_mit_binaerinhalt(self) -> None:
        ergebnis = text.aus_anhang("unbenannt.dat", "application/octet-stream",
                                   bytes(range(256)) * 8)
        self.assertEqual(ergebnis.art, "uebergangen")

    def test_nichts_wirft(self) -> None:
        """Die zentrale Zusage dieses Moduls."""
        proben = [b"", b"\x00" * 100, b"%PDF-1.4", b"PK\x03\x04", b"{\\rtf1", bytes(range(256))]
        for name in ("x.pdf", "x.docx", "x.rtf", "x.txt", "x", "x.unbekannt"):
            for daten in proben:
                with self.subTest(name=name, laenge=len(daten)):
                    ergebnis = text.aus_anhang(name, "application/octet-stream", daten)
                    self.assertIsInstance(ergebnis.text, str)


class TestGanzeMail(unittest.TestCase):
    def _mail_mit_anhang(self, dateiname: str, nutzdaten: bytes) -> object:
        import base64

        from mailburg.extract.message import parse

        kodiert = base64.b64encode(nutzdaten).decode()
        roh = (
            "From: a@example.org\r\nSubject: Mit Anhang\r\n"
            'Content-Type: multipart/mixed; boundary="G"\r\n\r\n'
            "--G\r\nContent-Type: text/plain\r\n\r\nSiehe Anhang.\r\n"
            f"--G\r\nContent-Type: application/octet-stream\r\n"
            f'Content-Disposition: attachment; filename="{dateiname}"\r\n'
            f"Content-Transfer-Encoding: base64\r\n\r\n{kodiert}\r\n--G--\r\n"
        ).encode()
        return parse(roh, with_payloads=True)

    def test_text_und_zaehlung(self) -> None:
        zerlegt = self._mail_mit_anhang("angebot.docx", docx_bauen("Fassadensanierung"))
        inhalt, zaehlung = text.aus_mail(zerlegt)
        self.assertIn("Fassadensanierung", inhalt)
        self.assertEqual(zaehlung.get("office"), 1)

    def test_dateiname_wandert_in_den_text(self) -> None:
        """Wer nach 'Rechnung 2025' sucht, meint oft den Dateinamen."""
        zerlegt = self._mail_mit_anhang("rechnung-2025.docx", docx_bauen("Inhalt"))
        inhalt, _ = text.aus_mail(zerlegt)
        self.assertIn("rechnung-2025", inhalt)

    def test_mail_ohne_anhang(self) -> None:
        from mailburg.extract.message import parse

        zerlegt = parse(b"From: a@example.org\r\nSubject: X\r\n\r\nNur Text", with_payloads=True)
        inhalt, zaehlung = text.aus_mail(zerlegt)
        self.assertEqual(inhalt, "")
        self.assertEqual(zaehlung, {})


if __name__ == "__main__":
    unittest.main()


class AnhangsvermerkTest(unittest.TestCase):
    """Je Anhang festhalten, wie viel Text er hergab.

    Ohne diesen Vermerk ließe sich später nicht sagen, *welcher* Anhang
    einer Mail die Texterkennung braucht – eine Nachricht mit lesbarem
    Angebot und eingescanntem Lieferschein gälte als erledigt.
    """

    def zerlegt(self, *anhaenge):
        from mailburg.extract.message import Attachment, ParsedMessage

        nachricht = ParsedMessage()
        nachricht.attachments = [
            Attachment(filename=n, mime_type=m, size=len(d), payload=d)
            for n, m, d in anhaenge
        ]
        return nachricht

    def test_zeichenzahl_wird_je_anhang_vermerkt(self):
        from mailburg.extract import text

        nachricht = self.zerlegt(
            ("notiz.txt", "text/plain", b"Hier steht Text drin."),
            ("bild.png", "image/png", b"\x89PNG" + b"x" * 500),
        )
        text.aus_mail(nachricht)

        self.assertGreater(nachricht.attachments[0].text_zeichen, 0)
        self.assertEqual(nachricht.attachments[1].text_zeichen, 0)

    def test_gescanntes_pdf_bekommt_null(self):
        # Genau daran erkennt die Warteschlange später ihre Kandidaten.
        from mailburg.extract import text

        gescannt = b"%PDF-1.4\n" + b"\x00\xff" * 60_000
        nachricht = self.zerlegt(("scan.pdf", "application/pdf", gescannt))
        text.aus_mail(nachricht)
        self.assertEqual(nachricht.attachments[0].text_zeichen, 0)

    def test_die_anhaenge_bleiben_vollzaehlig(self):
        from mailburg.extract import text

        nachricht = self.zerlegt(
            ("a.txt", "text/plain", b"eins"),
            ("b.txt", "text/plain", b"zwei"),
            ("c.png", "image/png", b"\x89PNG"),
        )
        text.aus_mail(nachricht)
        self.assertEqual(
            [a.filename for a in nachricht.attachments], ["a.txt", "b.txt", "c.png"]
        )


class AufloesungTest(unittest.TestCase):
    """Die Auflösung muss sich nach der Seitengröße richten.

    300 dpi ist eine Angabe je Zoll – wie groß das Bild wird, hängt
    daran, wie groß die Seite ist. Ein A4-Blatt ergibt knapp neun
    Megapixel, ein Scan aus der iPhone-Kamera-App misst aber 4507 × 6681
    Punkte statt 595 × 842: bei 300 dpi wären das 523 Megapixel. Daran
    erstickt tesseract, und zwar stumm – es meldet keinen Fehler,
    sondern liefert nichts.

    Am 2026-08-26 an einem echten Archiv gefunden: Zwei von sechs
    liegengebliebenen Dokumenten gingen hierauf zurück.
    """

    def _dpi(self, breite: float, hoehe: float, gross: bool = False) -> int:
        from mailburg.extract.ocr import Seitenmasse, _aufloesung

        return _aufloesung(
            Seitenmasse(seiten=1, breite=breite, hoehe=hoehe), gross
        )

    def test_uebliche_papierformate_bleiben_unangetastet(self) -> None:
        """Der Normalfall darf sich durch die Begrenzung nicht ändern."""
        from mailburg.extract.ocr import AUFLOESUNG

        for name, breite, hoehe in (
            ("A4 hoch", 595, 842), ("A4 quer", 842, 595),
            ("A3", 842, 1191), ("Letter", 612, 792),
        ):
            with self.subTest(format=name):
                self.assertEqual(self._dpi(breite, hoehe), AUFLOESUNG)

    def test_riesige_seiten_werden_gedrosselt(self) -> None:
        from mailburg.extract.ocr import MAX_KANTE

        dpi = self._dpi(4507, 6681)

        self.assertLess(dpi, 100)
        # Und zwar genau so weit, dass die längere Kante die Grenze
        # ungefähr trifft - nicht weiter.
        self.assertAlmostEqual(6681 / 72 * dpi, MAX_KANTE, delta=200)

    def test_niemals_unter_die_lesbarkeitsgrenze(self) -> None:
        """Ein absurd großes Dokument darf nicht zu Brei werden.

        Lieber ein Bild, an dem tesseract vielleicht noch scheitert, als
        eines, bei dem es sicher scheitert.
        """
        self.assertGreaterEqual(self._dpi(50_000, 80_000), 30)

    def test_ohne_seitenmasse_gilt_der_standardwert(self) -> None:
        """pdfinfo kann schweigen – dann wird nicht geraten."""
        from mailburg.extract.ocr import AUFLOESUNG, AUFLOESUNG_GROSS

        self.assertEqual(self._dpi(0, 0), AUFLOESUNG)
        self.assertEqual(self._dpi(0, 0, gross=True), AUFLOESUNG_GROSS)

    def test_grosse_dateien_bleiben_gröber(self) -> None:
        from mailburg.extract.ocr import AUFLOESUNG_GROSS

        self.assertEqual(self._dpi(595, 842, gross=True), AUFLOESUNG_GROSS)


class VerschluesseltePdfTest(unittest.TestCase):
    """Ein Dokument, das nach einem Passwort verlangt, ist nicht kaputt.

    Es ist zu. Der Unterschied gehört in die Meldung: »kein Text
    erkannt« schickt den Anwender auf die Suche nach einem Fehler, den
    es nicht gibt.
    """

    def test_passwortschutz_wird_erkannt_und_benannt(self) -> None:
        import subprocess
        from unittest import mock

        from mailburg.extract import ocr

        antwort = subprocess.CompletedProcess(
            [], 1, stdout="", stderr="Command Line Error: Incorrect password\n"
        )
        with mock.patch.object(subprocess, "run", return_value=antwort):
            masse = ocr._pdfinfo(__import__("pathlib").Path("/tmp/egal.pdf"))

        self.assertTrue(masse.verschluesselt)

    def test_ein_schreibgeschuetztes_pdf_gilt_nicht_als_gesperrt(self) -> None:
        """Viele PDF sind nur gegen Drucken geschützt und lesbar.

        »Encrypted: yes« allein sagt also nichts. Erst wenn pdfinfo
        obendrein keine Seitenzahl herausrückt, ist wirklich zu.
        """
        import subprocess
        from unittest import mock

        from mailburg.extract import ocr

        antwort = subprocess.CompletedProcess(
            [], 0,
            stdout="Pages:          3\nEncrypted:      yes (print:no)\n"
                   "Page size:      595.276 x 841.89 pts (A4)\n",
            stderr="",
        )
        with mock.patch.object(subprocess, "run", return_value=antwort):
            masse = ocr._pdfinfo(__import__("pathlib").Path("/tmp/egal.pdf"))

        self.assertFalse(masse.verschluesselt)
        self.assertEqual(masse.seiten, 3)
        self.assertAlmostEqual(masse.breite, 595.276, places=2)
        self.assertAlmostEqual(masse.hoehe, 841.89, places=2)
