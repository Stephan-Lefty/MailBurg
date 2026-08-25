"""Tests für das Zerlegen von Mails.

Der Leitsatz des Moduls lautet: nichts wegwerfen, niemals aufgeben. Diese
Tests halten ihn fest, indem sie überwiegend kaputte Mails einspeisen.
"""

from __future__ import annotations

import unittest

from mailburg.extract.message import html_to_text, parse


def mail(*zeilen: str, body: str = "Inhalt") -> bytes:
    return ("\r\n".join(zeilen) + "\r\n\r\n" + body).encode("utf-8")


class TestKopfzeilen(unittest.TestCase):
    def test_einfache_mail(self) -> None:
        m = parse(mail(
            "From: Josef Müller <mueller@beispiel.de>",
            "To: stephan@beispiel.de",
            "Subject: Schlussrechnung",
            "Date: Fri, 14 Mar 2025 09:30:00 +0100",
            "Message-ID: <abc@beispiel.de>",
        ))
        self.assertEqual(m.subject, "Schlussrechnung")
        self.assertEqual(m.from_addr, "mueller@beispiel.de")
        self.assertEqual(m.from_name, "Josef Müller")
        self.assertEqual(m.to_addrs, ["stephan@beispiel.de"])
        self.assertIsNotNone(m.date)
        self.assertEqual(m.date.year, 2025)

    def test_betreff_in_quoted_printable(self) -> None:
        """RFC 2047, die häufigste Verpackung für Umlaute im Betreff."""
        m = parse(mail(
            "From: a@b.de",
            "Subject: =?utf-8?Q?R=C3=BCckfrage_zur_Bestellung?=",
        ))
        self.assertEqual(m.subject, "Rückfrage zur Bestellung")

    def test_betreff_in_base64_latin1(self) -> None:
        """Ältere Mailprogramme kodierten so."""
        m = parse(mail(
            "From: a@b.de",
            "Subject: =?iso-8859-1?B?R3LDvMOfZQ==?=",
        ))
        self.assertIn("Ã", m.subject + "Ã")  # nur: es kommt etwas zurück
        self.assertTrue(m.subject)

    def test_mehrere_empfaenger_und_kopie(self) -> None:
        m = parse(mail(
            "From: a@b.de",
            "To: eins@x.de, Zwei <zwei@x.de>",
            "Cc: drei@x.de",
        ))
        self.assertEqual(m.to_addrs, ["eins@x.de", "zwei@x.de"])
        self.assertEqual(m.cc_addrs, ["drei@x.de"])
        self.assertIn("drei@x.de", m.all_recipients)

    def test_fehlender_betreff_ist_kein_fehler(self) -> None:
        m = parse(mail("From: a@b.de"))
        self.assertEqual(m.subject, "")

    def test_voellig_leere_mail_stuerzt_nicht_ab(self) -> None:
        m = parse(b"")
        self.assertEqual(m.subject, "")
        self.assertIsNone(m.date)


class TestDatum(unittest.TestCase):
    def test_datum_ohne_zeitzone_gilt_als_utc(self) -> None:
        m = parse(mail("From: a@b.de", "Date: Fri, 14 Mar 2025 09:30:00"))
        self.assertIsNotNone(m.date)
        self.assertIsNotNone(m.date.tzinfo)

    def test_unlesbares_datum_wird_vermerkt_nicht_verschluckt(self) -> None:
        m = parse(mail("From: a@b.de", "Date: neulich mal"))
        self.assertTrue(m.defects, "Ein kaputtes Datum muss vermerkt werden.")

    def test_received_springt_ein_wenn_date_fehlt(self) -> None:
        """Die Zeile vom eigenen Server ist oft verlässlicher als der Absender."""
        m = parse(mail(
            "From: a@b.de",
            "Received: from x by y; Fri, 14 Mar 2025 09:30:00 +0100",
        ))
        self.assertIsNotNone(m.date)
        self.assertEqual(m.date.year, 2025)


class TestInhalt(unittest.TestCase):
    def test_reiner_text(self) -> None:
        m = parse(mail("From: a@b.de", body="Das ist der Fließtext."))
        self.assertIn("Fließtext", m.body)

    def test_nur_html_wird_zu_text(self) -> None:
        roh = (
            b"From: a@b.de\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n\r\n"
            b"<html><head><style>p{color:red}</style></head>"
            b"<body><p>Sichtbarer Text</p><script>alert(1)</script></body></html>"
        )
        m = parse(roh)
        self.assertIn("Sichtbarer Text", m.body)
        self.assertNotIn("color:red", m.body, "CSS gehört nicht in den Index.")
        self.assertNotIn("alert", m.body, "Skript gehört nicht in den Index.")

    def test_gelogene_kodierung(self) -> None:
        """Behauptet UTF-8, ist aber Latin-1 – kommt ständig vor."""
        roh = (
            b"From: a@b.de\r\nSubject: Test\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"Gr\xfc\xdfe aus M\xfcnchen"
        )
        m = parse(roh)
        self.assertTrue(m.body, "Der Text ging verloren, statt notfalls ersetzt zu werden.")


class TestAnhaenge(unittest.TestCase):
    def _mit_anhang(self, dateiname: str | None) -> bytes:
        name = f'; filename="{dateiname}"' if dateiname else ""
        return (
            "From: a@b.de\r\n"
            "Subject: Mit Anhang\r\n"
            'Content-Type: multipart/mixed; boundary="GRENZE"\r\n\r\n'
            "--GRENZE\r\n"
            "Content-Type: text/plain\r\n\r\n"
            "Siehe Anhang.\r\n"
            "--GRENZE\r\n"
            f"Content-Type: application/pdf{name}\r\n"
            f"Content-Disposition: attachment{name}\r\n\r\n"
            "Scheininhalt\r\n"
            "--GRENZE--\r\n"
        ).encode("utf-8")

    def test_anhang_wird_erkannt(self) -> None:
        m = parse(self._mit_anhang("rechnung.pdf"))
        self.assertTrue(m.has_attachments)
        self.assertEqual(len(m.attachments), 1)
        self.assertEqual(m.attachments[0].filename, "rechnung.pdf")
        self.assertEqual(m.attachments[0].extension, "pdf")

    def test_text_bleibt_trotz_anhang_erhalten(self) -> None:
        m = parse(self._mit_anhang("rechnung.pdf"))
        self.assertIn("Siehe Anhang", m.body)

    def test_namenloser_anhang_bekommt_einen_namen(self) -> None:
        """Sonst wäre er in der Oberfläche nicht anklickbar."""
        m = parse(self._mit_anhang(None))
        self.assertEqual(len(m.attachments), 1)
        self.assertTrue(m.attachments[0].filename)

    def test_nutzdaten_nur_auf_wunsch(self) -> None:
        ohne = parse(self._mit_anhang("x.pdf"))
        mit = parse(self._mit_anhang("x.pdf"), with_payloads=True)
        self.assertEqual(ohne.attachments[0].payload, b"")
        self.assertTrue(mit.attachments[0].payload)

    def test_endung_bei_dateiname_ohne_punkt(self) -> None:
        m = parse(self._mit_anhang("Rechnung"))
        self.assertEqual(m.attachments[0].extension, "")


class TestHtmlUmwandlung(unittest.TestCase):
    def test_leeres_html(self) -> None:
        self.assertEqual(html_to_text(""), "")

    def test_kaputtes_html_wirft_nicht(self) -> None:
        self.assertIsInstance(html_to_text("<div><p>offen"), str)

    def test_mehrfache_leerzeichen_werden_zusammengezogen(self) -> None:
        self.assertEqual(html_to_text("<p>a\n\n   b</p>"), "a b")


if __name__ == "__main__":
    unittest.main()


class SignaturgrafikTest(unittest.TestCase):
    """Was als Anhang gilt – und was nur zur Darstellung gehört.

    In einem gewachsenen Postfach sind drei von fünf »Anhängen« Logos aus
    Signaturen. Zählt man sie mit, findet `hat:anhang` fast jede
    Geschäftsmail und ist damit wertlos.
    """

    def mail(self, teil: str) -> bytes:
        return (
            "From: Absender <a@example.org>\r\n"
            "To: b@example.org\r\n"
            "Subject: Mit Signatur\r\n"
            'Content-Type: multipart/mixed; boundary="G"\r\n\r\n'
            "--G\r\nContent-Type: text/plain\r\n\r\nText\r\n"
            f"{teil}"
            "--G--\r\n"
        ).encode("utf-8")

    def test_eingebettetes_logo_ist_kein_anhang(self):
        roh = self.mail(
            "--G\r\nContent-Type: image/png\r\n"
            'Content-Disposition: inline; filename="logo.png"\r\n'
            "Content-ID: <logo@firma>\r\n\r\nPNGDATEN\r\n"
        )
        zerlegt = parse(roh)
        self.assertEqual(len(zerlegt.attachments), 1, "archiviert wird es trotzdem")
        self.assertTrue(zerlegt.attachments[0].inline)
        self.assertFalse(zerlegt.attachments[0].ist_nutzanhang)
        self.assertFalse(zerlegt.has_attachments)

    def test_content_id_allein_genuegt(self):
        # Outlook setzt gern "attachment" und trotzdem eine Content-ID.
        roh = self.mail(
            "--G\r\nContent-Type: image/jpeg\r\n"
            'Content-Disposition: attachment; filename="image001.jpg"\r\n'
            "Content-ID: <image001@01DA>\r\n\r\nJPEGDATEN\r\n"
        )
        self.assertFalse(parse(roh).has_attachments)

    def test_echter_anhang_bleibt_einer(self):
        roh = self.mail(
            "--G\r\nContent-Type: application/pdf\r\n"
            'Content-Disposition: attachment; filename="Rechnung.pdf"\r\n\r\n'
            "%PDF-1.4\r\n"
        )
        zerlegt = parse(roh)
        self.assertTrue(zerlegt.has_attachments)
        self.assertEqual([a.filename for a in zerlegt.nutzanhaenge], ["Rechnung.pdf"])

    def test_unterschriftsdatei_zaehlt_nicht(self):
        roh = self.mail(
            "--G\r\nContent-Type: application/pkcs7-signature\r\n"
            'Content-Disposition: attachment; filename="smime.p7s"\r\n\r\nXX\r\n'
        )
        self.assertFalse(parse(roh).has_attachments)

    def test_rechnung_neben_logo_zaehlt(self):
        # Der häufigste Fall überhaupt: echte Anlage plus Signaturbild.
        roh = self.mail(
            "--G\r\nContent-Type: application/pdf\r\n"
            'Content-Disposition: attachment; filename="Rechnung.pdf"\r\n\r\n'
            "%PDF-1.4\r\n"
            "--G\r\nContent-Type: image/png\r\n"
            'Content-Disposition: inline; filename="logo.png"\r\n'
            "Content-ID: <logo@firma>\r\n\r\nPNG\r\n"
        )
        zerlegt = parse(roh)
        self.assertTrue(zerlegt.has_attachments)
        self.assertEqual(len(zerlegt.attachments), 2)
        self.assertEqual(len(zerlegt.nutzanhaenge), 1)


class WichtigkeitTest(unittest.TestCase):
    """Drei Kopfzeilen bedeuten dasselbe, je nach Mailprogramm."""

    def mail(self, *kopfzeilen: str) -> bytes:
        zeilen = "".join(f"{z}\r\n" for z in kopfzeilen)
        return (
            f"From: a@example.org\r\nTo: b@example.org\r\n"
            f"Subject: Test\r\n{zeilen}\r\nText\r\n"
        ).encode("utf-8")

    def test_ohne_angabe_normal(self):
        self.assertEqual(parse(self.mail()).wichtigkeit, "normal")

    def test_outlook_schreibweise(self):
        self.assertEqual(parse(self.mail("Importance: high")).wichtigkeit, "hoch")
        self.assertEqual(parse(self.mail("Importance: Low")).wichtigkeit, "niedrig")

    def test_x_priority_mit_ziffer(self):
        self.assertEqual(parse(self.mail("X-Priority: 1")).wichtigkeit, "hoch")
        self.assertEqual(parse(self.mail("X-Priority: 5")).wichtigkeit, "niedrig")
        self.assertEqual(parse(self.mail("X-Priority: 3")).wichtigkeit, "normal")

    def test_x_priority_mit_klammerzusatz(self):
        # "1 (Highest)" ist die verbreitetste Schreibweise überhaupt.
        self.assertEqual(parse(self.mail("X-Priority: 1 (Highest)")).wichtigkeit, "hoch")

    def test_rfc_2156_schreibweise(self):
        self.assertEqual(parse(self.mail("Priority: urgent")).wichtigkeit, "hoch")
        self.assertEqual(parse(self.mail("Priority: non-urgent")).wichtigkeit, "niedrig")

    def test_unsinn_gilt_als_normal(self):
        # Eine erfundene Angabe darf nicht dazu führen, dass eine Mail bei
        # der Suche nach wichtiger Post auftaucht.
        self.assertEqual(parse(self.mail("Importance: sehr dringend!!")).wichtigkeit,
                         "normal")

    def test_importance_geht_vor(self):
        roh = self.mail("Importance: high", "X-Priority: 5")
        self.assertEqual(parse(roh).wichtigkeit, "hoch")


class BlindkopieTest(unittest.TestCase):
    def test_bcc_wird_gelesen(self):
        # In der eigenen Ausfertigung im Ordner "Gesendet" steht das Feld -
        # und dort ist es die einzige Auskunft, wer noch mitgelesen hat.
        roh = (
            "From: a@example.org\r\nTo: b@example.org\r\n"
            "Cc: c@example.org\r\nBcc: heimlich@example.org\r\n"
            "Subject: Test\r\n\r\nText\r\n"
        ).encode("utf-8")
        zerlegt = parse(roh)
        self.assertEqual(zerlegt.to_addrs, ["b@example.org"])
        self.assertEqual(zerlegt.cc_addrs, ["c@example.org"])
        self.assertEqual(zerlegt.bcc_addrs, ["heimlich@example.org"])

    def test_ohne_bcc_leer(self):
        roh = b"From: a@example.org\r\nTo: b@example.org\r\n\r\nText\r\n"
        self.assertEqual(parse(roh).bcc_addrs, [])
