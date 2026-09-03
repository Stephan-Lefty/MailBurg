"""Viele Mails auf einmal aus dem Archiv auf die Platte zurück.

**Die eine Frage, um die es hier geht:** Was passiert, wenn man denselben
Lauf zweimal startet? Über IMAP wäre die Antwort »alles doppelt« – das
ist der Grund, warum der Weg auf die Platte zuerst gebaut wurde. Hier
muss sie »nichts« lauten, und zwar für jedes Format.
"""

from __future__ import annotations

import mailbox
import tempfile
import unittest
from pathlib import Path

from mailburg.core import zurueckspielen
from mailburg.core.archive import Archive, Mode


def _mail(betreff: str, tag: int = 12, text: str = "Guten Tag.") -> bytes:
    return (
        f"From: wer@example.org\r\n"
        f"To: martha@mailburg.example\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: Mon, {tag:02d} May 2025 09:14:00 +0000\r\n"
        f"Message-ID: <{betreff.replace(' ', '')}@example.org>\r\n"
        f"\r\n"
        f"{text}\r\n"
    ).encode()


class Grundlage(unittest.TestCase):
    """Ein kleines Archiv mit zwei Konten und drei Ordnern."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        wurzel = Path(self.tmp.name)
        self.ziel = wurzel / "Zurueck"
        self.archiv = Archive.create(wurzel / "Archiv", mode=Mode.PRIVAT)
        # Über das Attribut, nicht über die gebundene Methode: Der
        # Kommandozeilentest tauscht das Archivobjekt zwischendurch aus.
        self.addCleanup(lambda: self.archiv.close())

        self.archiv.add(
            _mail("Rechnung"), account="Firma", folder="INBOX",
            flags="\\Seen \\Answered",
        )
        self.archiv.add(
            _mail("Angebot", tag=13), account="Firma",
            folder="Projekte/2025", flags="",
        )
        self.archiv.add(
            _mail("Urlaub", tag=14), account="Privat", folder="INBOX",
            flags="S",
        )

    def _lauf(self, **wie):
        wie.setdefault("format", "maildir")
        return zurueckspielen.zurueckspielen(self.archiv, self.ziel, **wie)


class MaildirTest(Grundlage):
    """Das Format für alles, was wieder ein Postfach werden soll."""

    def test_jede_mail_liegt_einzeln_und_bytegenau(self):
        bericht = self._lauf()

        self.assertEqual(bericht.geschrieben, 3)
        dateien = list(self.ziel.rglob("*"))
        inhalte = {d.read_bytes() for d in dateien if d.is_file()}
        self.assertIn(_mail("Rechnung"), inhalte)

    def test_die_ordner_kommen_mit(self):
        self._lauf()

        # Maildir++ kennt keine Verzeichnisse - die Hierarchie steckt im
        # Namen, getrennt durch Punkte.
        self.assertTrue((self.ziel / ".Firma.INBOX" / "cur").is_dir())
        self.assertTrue((self.ziel / ".Firma.Projekte.2025" / "new").is_dir())
        self.assertTrue((self.ziel / ".Privat.INBOX").is_dir())

    def test_ohne_struktur_landet_alles_in_einem_topf(self):
        bericht = self._lauf(struktur=False)

        self.assertEqual(bericht.geschrieben, 3)
        self.assertEqual(len(list((self.ziel / "cur").iterdir())
                             + list((self.ziel / "new").iterdir())), 3)

    def test_der_lesezustand_ueberlebt(self):
        """Aus IMAP-Marken werden Maildir-Buchstaben.

        Beides kommt im Index vor: ``\\Seen \\Answered`` aus IMAP und
        ``S`` aus einem eingelesenen Maildir. Wer nur eines versteht,
        macht beim Zurückspielen gelesene Post wieder ungelesen.
        """
        self._lauf()

        gelesen = next((self.ziel / ".Firma.INBOX" / "cur").iterdir())
        self.assertEqual(gelesen.name.partition(":2,")[2], "RS")

        # Aus dem Maildir eingelesen, also schon in Buchstabenform.
        privat = next((self.ziel / ".Privat.INBOX" / "cur").iterdir())
        self.assertEqual(privat.name.partition(":2,")[2], "S")

        # Ungelesenes gehört nach new/ und trägt keinen Zustand.
        neu = list((self.ziel / ".Firma.Projekte.2025" / "new").iterdir())
        self.assertEqual(len(neu), 1)
        self.assertNotIn(":2,", neu[0].name)

    def test_python_liest_das_ergebnis_als_maildir(self):
        """Die Gegenprobe mit fremdem Werkzeug.

        Ein Format, das nur das eigene Programm versteht, ist kein
        Format. Pythons ``mailbox`` ist hier der unbestechliche Dritte.
        """
        self._lauf()

        kasten = mailbox.Maildir(str(self.ziel), factory=None, create=False)
        ordner = set(kasten.list_folders())
        self.assertIn("Firma.INBOX", ordner)
        nachrichten = list(kasten.get_folder("Firma.INBOX"))
        self.assertEqual(len(nachrichten), 1)
        self.assertEqual(nachrichten[0]["Subject"], "Rechnung")

    def test_zweimal_laufen_schreibt_nicht_doppelt(self):
        """Der Grund, warum dieser Weg vor dem über IMAP kam."""
        erst = self._lauf()
        wieder = self._lauf()

        self.assertEqual(erst.geschrieben, 3)
        self.assertEqual(wieder.geschrieben, 0)
        self.assertEqual(wieder.uebersprungen, 3)

        dateien = [d for d in self.ziel.rglob("*") if d.is_file()]
        self.assertEqual(len(dateien), 3)

    def test_ein_zweiter_lauf_holt_nach_was_dazugekommen_ist(self):
        self._lauf()
        self.archiv.add(_mail("Nachzügler", tag=15), account="Firma",
                        folder="INBOX")

        wieder = self._lauf()

        self.assertEqual(wieder.geschrieben, 1)
        self.assertEqual(wieder.uebersprungen, 3)


class MboxTest(Grundlage):
    """Eine Datei je Ordner – für Thunderbirds lokale Ordner."""

    def test_eine_datei_je_ordner(self):
        bericht = self._lauf(format="mbox")

        self.assertEqual(bericht.geschrieben, 3)
        self.assertTrue((self.ziel / "Firma" / "INBOX.mbox").is_file())
        self.assertTrue((self.ziel / "Firma" / "Projekte" / "2025.mbox").is_file())

    def test_python_liest_das_ergebnis_als_mbox(self):
        self._lauf(format="mbox")

        kasten = mailbox.mbox(str(self.ziel / "Firma" / "INBOX.mbox"),
                              factory=None, create=False)
        self.addCleanup(kasten.close)
        self.assertEqual(len(kasten), 1)
        self.assertEqual(kasten[0]["Subject"], "Rechnung")

    def test_eine_from_zeile_im_text_zerreisst_die_datei_nicht(self):
        """Der Fallstrick des Formats, und der Grund für den Hinweis.

        Steht »From « am Anfang einer Textzeile, gilt sie in einer MBOX
        als Anfang der nächsten Nachricht. Ohne Maskierung wären aus
        einer Mail plötzlich zwei – und die zweite bestünde aus Unsinn.
        """
        self.archiv.add(
            _mail("Verabredung", tag=16,
                  text="From Monday on ist alles anders.\r\nBis dann."),
            account="Firma", folder="INBOX",
        )

        self._lauf(format="mbox")

        kasten = mailbox.mbox(str(self.ziel / "Firma" / "INBOX.mbox"),
                              factory=None, create=False)
        self.addCleanup(kasten.close)
        self.assertEqual(len(kasten), 2)
        betreffe = {n["Subject"] for n in kasten}
        self.assertEqual(betreffe, {"Rechnung", "Verabredung"})

    def test_zweimal_laufen_haengt_nicht_zweimal_an(self):
        erst = self._lauf(format="mbox")
        wieder = self._lauf(format="mbox")

        self.assertEqual(erst.geschrieben, 3)
        self.assertEqual(wieder.geschrieben, 0)

        kasten = mailbox.mbox(str(self.ziel / "Firma" / "INBOX.mbox"),
                              factory=None, create=False)
        self.addCleanup(kasten.close)
        self.assertEqual(len(kasten), 1)

    def test_die_beiakte_liegt_neben_der_datei(self):
        """Ohne sie ließe sich nicht sagen, was schon drinsteht.

        Im MBOX-Format ist kein Platz für eine Kennung, und eine
        hineinzuschreiben hieße, die Mails zu verändern.
        """
        self._lauf(format="mbox")

        beiakte = self.ziel / "Firma" / f"INBOX.mbox{zurueckspielen._Mbox.BEIAKTE}"
        self.assertTrue(beiakte.is_file())
        self.assertEqual(len(beiakte.read_text().split()), 1)


class EmlTest(Grundlage):
    """Eine Datei je Nachricht, zum Hineinziehen ins Mailprogramm."""

    def test_ordner_werden_zu_verzeichnissen(self):
        bericht = self._lauf(format="eml")

        self.assertEqual(bericht.geschrieben, 3)
        self.assertEqual(
            len(list((self.ziel / "Firma" / "Projekte" / "2025").glob("*.eml"))), 1
        )

    def test_bytegenau(self):
        self._lauf(format="eml")

        datei = next((self.ziel / "Privat" / "INBOX").glob("*.eml"))
        self.assertEqual(datei.read_bytes(), _mail("Urlaub", tag=14))

    def test_zweimal_laufen_schreibt_nicht_doppelt(self):
        self._lauf(format="eml")
        wieder = self._lauf(format="eml")

        self.assertEqual(wieder.geschrieben, 0)
        self.assertEqual(wieder.uebersprungen, 3)


class AuswahlTest(Grundlage):
    """Was mitkommt und was nicht."""

    def test_eine_suche_grenzt_ein(self):
        bericht = self._lauf(suche="Rechnung")

        self.assertEqual(bericht.geschrieben, 1)
        self.assertEqual(bericht.gesamt, 1)

    def test_der_trockenlauf_ruehrt_die_platte_nicht_an(self):
        bericht = self._lauf(trockenlauf=True)

        self.assertEqual(bericht.geschrieben, 3)
        self.assertFalse(self.ziel.exists())

    def test_der_trockenlauf_schreibt_auch_nichts_ins_journal(self):
        vorher = len(list(self.archiv.journal.read_all()))
        self._lauf(trockenlauf=True)
        self.assertEqual(len(list(self.archiv.journal.read_all())), vorher)

    def test_der_vorgang_steht_im_journal(self):
        """Aus dem Archiv sind Daten herausgegangen – das gehört notiert."""
        self._lauf()

        eintraege = [e for e in self.archiv.journal.read_all()
                     if e.get("art") == "zurueckgespielt"]
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["nachrichten"], 3)
        self.assertEqual(eintraege[0]["format"], "maildir")

    def test_eine_mail_an_mehreren_orten_wird_einmal_geschrieben(self):
        """Sonst steht die Rundmail hinterher fünfmal da.

        Bei Proton und Gmail ist Mehrfachablage der Normalfall – jedes
        Etikett ist ein weiterer Fundort.
        """
        self.archiv.add(_mail("Rechnung"), account="Firma", folder="Wichtig")

        bericht = self._lauf()

        self.assertEqual(bericht.geschrieben, 3)
        self.assertEqual(bericht.mehrfach, 1)
        dateien = [d for d in self.ziel.rglob("*") if d.is_file()]
        self.assertEqual(len(dateien), 3)


class AbbruchTest(Grundlage):
    """Abgebrochen heißt nicht kaputt."""

    def test_was_geschrieben_ist_bleibt_vollstaendig(self):
        getan = []

        def weiter():
            getan.append(1)
            return len(getan) <= 2

        bericht = self._lauf(weiter=weiter)

        self.assertTrue(bericht.abgebrochen)
        for datei in self.ziel.rglob("*"):
            if datei.is_file():
                self.assertTrue(datei.read_bytes().startswith(b"From:"))

    def test_ein_spaeterer_lauf_setzt_dort_an(self):
        getan = []
        self._lauf(weiter=lambda: (getan.append(1), len(getan) <= 2)[1])
        vorher = len([d for d in self.ziel.rglob("*") if d.is_file()])

        bericht = self._lauf()

        self.assertEqual(bericht.uebersprungen, vorher)
        self.assertEqual(
            len([d for d in self.ziel.rglob("*") if d.is_file()]), 3
        )

    def test_eine_kaputte_mail_beendet_den_lauf_nicht(self):
        """Bei zehntausend Mails klemmt irgendwann eine.

        Wer dann abbricht, hat nichts. Notiert wird jede einzelne.
        """
        echt = self.archiv.store.get
        stolperstein = {"n": 0}

        def gelegentlich_kaputt(digest, bucket):
            stolperstein["n"] += 1
            if stolperstein["n"] == 2:
                raise OSError("Eingabe-/Ausgabefehler")
            return echt(digest, bucket)

        self.archiv.store.get = gelegentlich_kaputt
        try:
            bericht = self._lauf()
        finally:
            self.archiv.store.get = echt

        self.assertEqual(bericht.geschrieben, 2)
        self.assertEqual(len(bericht.fehler), 1)
        self.assertFalse(bericht.vollstaendig)


class NamenTest(unittest.TestCase):
    """Die Umrechnung der Ordnernamen."""

    def test_maildir_namen(self):
        self.assertEqual(
            zurueckspielen.maildir_ordner("Firma", "Projekte/2025"),
            ".Firma.Projekte.2025",
        )
        self.assertEqual(zurueckspielen.maildir_ordner("Firma", ""), ".Firma")

    def test_ein_punkt_im_ordnernamen_macht_keine_neue_ebene(self):
        """Sonst entsteht aus »Rechnungen 2024.alt« eine Ebene, die es nie gab."""
        self.assertEqual(
            zurueckspielen.maildir_ordner("Firma", "Rechnungen 2024.alt"),
            ".Firma.Rechnungen 2024_alt",
        )

    def test_der_weg_hin_und_zurueck(self):
        """Was MailBurg schreibt, muss MailBurg auch wieder einlesen können."""
        from mailburg.sources.local import _maildir_name

        for konto, ordner in (("Firma", "INBOX"), ("Privat", "Projekte/2025")):
            with self.subTest(ordner=ordner):
                geschrieben = zurueckspielen.maildir_ordner(konto, ordner)
                self.assertEqual(
                    _maildir_name(geschrieben), f"{konto}/{ordner}"
                )

    def test_zeichen_die_kein_dateisystem_mag(self):
        name = zurueckspielen.maildir_ordner("Firma", 'Post/"wichtig"?')
        self.assertNotIn('"', name)
        self.assertNotIn("?", name)

    def test_marken_aus_beiden_welten(self):
        self.assertEqual(zurueckspielen._marken("\\Seen \\Answered"), "RS")
        self.assertEqual(zurueckspielen._marken("SR"), "RS")
        self.assertEqual(zurueckspielen._marken(""), "")
        self.assertEqual(zurueckspielen._marken("\\Recent"), "")


class ZielTest(unittest.TestCase):
    """Was vor dem ersten Byte geprüft wird."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wurzel = Path(self.tmp.name)

    def test_eine_datei_als_ziel_ist_ein_fehler(self):
        datei = self.wurzel / "keinordner"
        datei.write_text("belegt")

        with self.assertRaises(zurueckspielen.ZielFehler):
            zurueckspielen.ziel_pruefen(datei, "maildir")

    def test_unbekanntes_format(self):
        with self.assertRaises(zurueckspielen.ZielFehler):
            zurueckspielen.ziel_pruefen(self.wurzel / "neu", "pst")

    def test_ein_voller_ordner_wird_gemeldet_aber_nicht_verweigert(self):
        """Ein zweiter Lauf soll ergänzen – gesagt werden muss es trotzdem."""
        ordner = self.wurzel / "voll"
        ordner.mkdir()
        (ordner / "etwas").write_text("da")

        satz = zurueckspielen.ziel_pruefen(ordner, "maildir")

        self.assertIn("ergänzt", satz)


if __name__ == "__main__":
    unittest.main()


class KommandozeileTest(Grundlage):
    """Der Weg über ``mailburg zurueckspielen``.

    **Warum das eigene Tests braucht:** Der Kern kann fehlerfrei sein und
    die Kommandozeile trotzdem nichts tun – am 2026-08-31 hat genau das
    ein halber Tag gekostet, weil kein Test durch ``main()`` ging.
    """

    def _cli(self, *argumente) -> tuple[int, str]:
        import io
        from contextlib import redirect_stdout
        from unittest import mock

        from mailburg.__main__ import main

        # Das Archiv ist in diesem Test offen; die Kommandozeile öffnet es
        # ein zweites Mal. Beim Schreiben will sie es ausschließlich - das
        # ginge gegen die eigene Sperre.
        self.archiv.index.commit()
        self.archiv.close()
        try:
            with redirect_stdout(io.StringIO()) as ausgabe, \
                    mock.patch("sys.stderr", new=io.StringIO()):
                code = main(["zurueckspielen", str(self.archiv.root), *argumente])
        finally:
            from mailburg.core.archive import Archive
            self.archiv = Archive.open(self.archiv.root, exclusive=False)
        return code, ausgabe.getvalue()

    def test_ohne_wirklich_wird_nur_gezaehlt(self):
        code, text = self._cli(str(self.ziel))

        self.assertEqual(code, 0)
        self.assertIn("Trockenlauf", text)
        self.assertIn("3 Mails", text)
        self.assertFalse(self.ziel.exists())

    def test_mit_wirklich_wird_geschrieben(self):
        code, text = self._cli(str(self.ziel), "--wirklich")

        self.assertEqual(code, 0)
        self.assertIn("3 Mails geschrieben", text)
        self.assertEqual(
            len([d for d in self.ziel.rglob("*") if d.is_file()]), 3
        )

    def test_das_mbox_format_sagt_was_es_veraendert(self):
        """Wer es bytegenau braucht, muss es vorher erfahren, nicht danach."""
        _, text = self._cli(str(self.ziel), "--format", "mbox", "--wirklich")

        self.assertIn("From", text)
        self.assertIn("maildir", text)

    def test_eine_datei_als_ziel_ist_ein_fehler(self):
        datei = self.ziel.parent / "belegt"
        datei.write_text("kein Ordner")

        code, _ = self._cli(str(datei), "--wirklich")

        self.assertEqual(code, 2)

    def test_eine_suche_grenzt_ein(self):
        _, text = self._cli(str(self.ziel), "--suche", "Rechnung")

        self.assertIn("1 Mail,", text)
