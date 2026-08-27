"""Tests für die Texterkennung – vor allem für das, was sie *nicht* tut.

Der teuerste Fehler der Texterkennung ist doppelte Arbeit. Ein Vertrag,
der einmal weitergeleitet und dreimal beantwortet wurde, hängt an fünf
Mails. Fünf verschiedene Mails – aber ein einziges Dokument, Byte für
Byte dasselbe. Wer das nicht bemerkt, lässt tesseract fünfmal über
dieselben zwanzig Seiten laufen und bekommt fünfmal denselben Text.

Aufgefallen ist es am 2026-08-26 an einem echten Geschäftsarchiv: Von
222 erkannten Dokumenten mit 986 Seiten waren 153 Dokumente mit 691
Seiten Abschriften bereits gelesener Anhänge. Siebzig Prozent der
Rechenzeit – eine Stunde, von der vierzig Minuten überflüssig waren.

Die Erkennung selbst wird hier nicht ausgeführt. tesseract ist auf einem
Testrechner nicht vorauszusetzen, und was es ausrechnet, ist auch nicht
Gegenstand dieser Tests. Ersetzt wird es durch einen Zähler: Die Frage
ist nicht, *was* gelesen wurde, sondern *wie oft*.
"""

from __future__ import annotations

import base64
import email.utils
import hashlib
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


class ErkennungsTestFall(unittest.TestCase):
    """Gemeinsame Grundlage: ein eigener Textspeicher je Test.

    Der Textspeicher gehört keinem Archiv – das ist seine Stärke im
    Betrieb und seine Tücke im Test. Ohne Trennung erbt ein Test den
    Vorrat seiner Vorgänger und bekommt »schon erkannt« zu sehen, wo er
    »frisch erkannt« prüfen wollte. Das ist beim Schreiben dieser Datei
    einmal passiert und sah aus wie ein Fehler im Programm.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        # Über addCleanup, nicht über tearDown: Die Archive müssen zuerst
        # geschlossen werden, und Cleanups laufen in umgekehrter Folge.
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name)
        self.gelesen: list[bytes] = []

        flicken = mock.patch.object(
            erkennung.paths, "data_dir", return_value=self.wo / "textspeicher"
        )
        flicken.start()
        self.addCleanup(flicken.stop)

    # ------------------------------------------------------------- Werkzeug

    def _archiv(self, name: str, mails: list[bytes]):
        archiv = Archive.create(self.wo / name, name=name)
        self.addCleanup(archiv.close)
        for nr, roh in enumerate(mails):
            archiv.add(roh, account="probe", folder=f"INBOX/{nr}")
        # Die Anhänge als »ohne Textebene« markieren. Im Betrieb macht
        # das die Extraktion beim Archivieren; hier wären es Attrappen,
        # aus denen poppler nie Text holen könnte.
        archiv.index.db.execute("UPDATE attachments SET text_zeichen = 0")
        archiv.index.commit()
        return archiv

    def _lauf(self, archiv, *, gleichzeitig: int = 1,
              text: str = "Erkannt: Vollmacht", seiten: int = 3):
        """Ein vollständiger Durchlauf, mit einem Zähler statt tesseract."""
        def gefaelscht(nutzlast, **_):
            self.gelesen.append(nutzlast)
            ergebnis = ocr.Ergebnis()
            ergebnis.text = text
            ergebnis.seiten = seiten
            return ergebnis

        with mock.patch.object(ocr, "bereit", return_value=(True, "")), \
                mock.patch.object(ocr, "text_aus_pdf", side_effect=gefaelscht):
            return erkennung.durchlauf(
                archiv, budget_sekunden=0, budget_dokumente=0,
                gleichzeitig=gleichzeitig,
            )


class TestDoppelteAnhaenge(ErkennungsTestFall):
    """Derselbe Anhang an mehreren Mails wird nur einmal gelesen."""

    def test_derselbe_anhang_wird_nur_einmal_gelesen(self) -> None:
        gleich = b"%PDF-Vollmacht" + b"x" * GROSS
        archiv = self._archiv("A", [
            mail_mit_anhang("Vollmacht", "Vollmacht.pdf", gleich, tag=1),
            mail_mit_anhang("Fwd: Vollmacht", "Vollmacht.pdf", gleich, tag=2),
            mail_mit_anhang("Re: Vollmacht", "Vollmacht.pdf", gleich, tag=3),
        ])

        stat = self._lauf(archiv)

        self.assertEqual(len(self.gelesen), 1, "tesseract lief mehr als einmal")
        self.assertEqual(stat.gelesen, 3, "nicht alle drei Mails gelten als erledigt")
        self.assertEqual(stat.doppelt, 2)
        self.assertEqual(stat.seiten, 3, "Seiten doppelt gezählt")
        self.assertEqual(stat.offen_danach, 0)

    def test_greift_auch_innerhalb_eines_buendels(self) -> None:
        """Die Dubletten liegen nach der Größensortierung nebeneinander.

        Damit landen sie im selben Bündel – wo ein Zwischenspeicher, der
        erst nach dem Bündel gefüllt wird, zu spät käme. Genau dieser
        Fall ist in der Praxis der Regelfall.
        """
        gleich = b"%PDF-Zeugnismappe" + b"y" * GROSS
        archiv = self._archiv("A", [
            mail_mit_anhang(f"Mappe {i}", "Zeugnismappe.pdf", gleich, tag=i)
            for i in range(1, 5)
        ])

        stat = self._lauf(archiv, gleichzeitig=4)

        self.assertEqual(len(self.gelesen), 1)
        self.assertEqual(stat.gelesen, 4)
        self.assertEqual(stat.doppelt, 3)

    def test_verschiedene_anhaenge_werden_einzeln_gelesen(self) -> None:
        """Der gleiche Dateiname macht noch keine Dublette."""
        archiv = self._archiv("A", [
            mail_mit_anhang("Rechnung März", "Rechnung.pdf",
                            b"%PDF-A" + b"a" * GROSS, tag=1),
            mail_mit_anhang("Rechnung April", "Rechnung.pdf",
                            b"%PDF-B" + b"b" * GROSS, tag=2),
        ])

        stat = self._lauf(archiv, gleichzeitig=2)

        self.assertEqual(len(self.gelesen), 2)
        self.assertEqual(stat.gelesen, 2)
        self.assertEqual(stat.doppelt, 0)
        self.assertEqual(stat.seiten, 6)

    def test_jede_mail_wird_einzeln_durchsuchbar(self) -> None:
        """Der Sinn der Sache: Auch die Abschriften muss man finden.

        Gespart wird die Erkennung, nicht der Eintrag im Suchindex. Der
        hängt an der Mail – wer nach dem Inhalt sucht, soll beide Mails
        finden, nicht nur die zuerst gelesene.
        """
        gleich = b"%PDF-Kuendigung" + b"z" * GROSS
        archiv = self._archiv("A", [
            mail_mit_anhang("Kündigung", "K.pdf", gleich, tag=1),
            mail_mit_anhang("Fwd: Kündigung", "K.pdf", gleich, tag=2),
        ])

        self._lauf(archiv, gleichzeitig=2, text="Erkannt: hiermit kündige ich")

        self.assertEqual(
            len(archiv.index.search("kündige")), 2,
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
        archiv = self._archiv("A", [
            mail_mit_anhang("Kaputt", "K.pdf", gleich, tag=1),
            mail_mit_anhang("Fwd: Kaputt", "K.pdf", gleich, tag=2),
        ])

        stat = self._lauf(archiv, gleichzeitig=2, text="", seiten=0)

        self.assertEqual(stat.gescheitert, 2)
        self.assertEqual(len(self.gelesen), 1, "die Abschrift wurde erneut gelesen")
        self.assertEqual(stat.offen_danach, 0)


class TestUeberLaeufeHinweg(ErkennungsTestFall):
    """Was einmal erkannt ist, wird nie wieder erkannt.

    Der Textspeicher liegt neben dem Index und überlebt beides: den
    Neuaufbau des Index und das Ende des Programms. Er gehört auch
    keinem einzelnen Archiv. Damit gilt die Ersparnis über Läufe *und*
    über Archive hinweg – wer denselben Vertrag im Geschäfts- und im
    Privatarchiv liegen hat, zahlt ihn einmal.
    """

    def test_ein_zweiter_lauf_liest_nicht_noch_einmal(self) -> None:
        gleich = b"%PDF-Vollmacht" + b"v" * GROSS
        archiv = self._archiv("A", [
            mail_mit_anhang("Vollmacht", "V.pdf", gleich, tag=1),
        ])

        self._lauf(archiv)
        # Den Vermerk löschen, als wäre das Dokument nie erledigt worden –
        # so entsteht dieselbe Lage wie bei einem neu aufgebauten Index.
        archiv.index.db.execute("DELETE FROM ocr_vermerk")
        archiv.index.commit()
        stat = self._lauf(archiv)

        self.assertEqual(len(self.gelesen), 1, "der zweite Lauf hat neu erkannt")
        self.assertEqual(stat.gelesen, 1)
        self.assertEqual(stat.doppelt, 1)

    def test_ein_zweites_archiv_zahlt_nicht_noch_einmal(self) -> None:
        """Derselbe Vertrag im Geschäfts- und im Privatarchiv."""
        gleich = b"%PDF-Vertrag" + b"w" * GROSS
        geschaeft = self._archiv("Geschaeft", [
            mail_mit_anhang("Vertrag", "V.pdf", gleich, tag=1),
        ])
        privat = self._archiv("Privat", [
            mail_mit_anhang("Fwd: Vertrag", "V.pdf", gleich, tag=2),
        ])

        self._lauf(geschaeft, text="Erkannt: Mietvertrag")
        stat = self._lauf(privat, text="Erkannt: Mietvertrag")

        self.assertEqual(len(self.gelesen), 1)
        self.assertEqual(stat.gelesen, 1)
        # Und der Text ist im zweiten Archiv wirklich durchsuchbar.
        self.assertEqual(len(privat.index.search("Mietvertrag")), 1)


class TestVorratNachtraeglich(ErkennungsTestFall):
    """Wer die Texterkennung vor der Dublettenprüfung laufen ließ.

    Der Text ist da, aber unter dem Schlüssel der Mail. Unter dem des
    Dokuments – dem einzigen, unter dem ein späterer Lauf ihn suchen
    würde – steht nichts. ``vorrat_aufbauen`` holt das nach, ohne
    irgendetwas neu zu erkennen.
    """

    ANHANG = b"%PDF-Generalvollmacht" + b"g" * GROSS

    def _alten_zustand_herstellen(self) -> str:
        """Entfernt den Eintrag unter dem Fingerabdruck des Dokuments.

        So sah der Textspeicher aus, bevor es diesen zweiten Schlüssel
        gab: Der Text ist vorhanden, aber nicht auffindbar.
        """
        finger = hashlib.sha256(self.ANHANG).hexdigest()
        erkennung.Textspeicher()._pfad(finger).unlink()
        return finger

    def test_der_vorrat_entsteht_ohne_neue_erkennung(self) -> None:
        archiv = self._archiv("A", [
            mail_mit_anhang("Vollmacht", "V.pdf", self.ANHANG, tag=1),
        ])
        self._lauf(archiv)
        finger = self._alten_zustand_herstellen()
        self.assertFalse(erkennung.Textspeicher().hat(finger))

        abgelegt, ohne = erkennung.vorrat_aufbauen(archiv)

        self.assertEqual(abgelegt, 1)
        self.assertEqual(ohne, 0)
        self.assertTrue(erkennung.Textspeicher().hat(finger))
        self.assertEqual(len(self.gelesen), 1, "es wurde neu erkannt")

    def test_danach_zahlt_ein_zweites_archiv_nicht_mehr(self) -> None:
        """Der Zweck der Übung – nachgewiesen am zweiten Archiv."""
        erstes = self._archiv("Geschaeft", [
            mail_mit_anhang("Vollmacht", "V.pdf", self.ANHANG, tag=1),
        ])
        self._lauf(erstes, text="Erkannt: Generalvollmacht")
        self._alten_zustand_herstellen()

        erkennung.vorrat_aufbauen(erstes)

        zweites = self._archiv("Privat", [
            mail_mit_anhang("Fwd: Vollmacht", "V.pdf", self.ANHANG, tag=2),
        ])
        stat = self._lauf(zweites, text="Erkannt: Generalvollmacht")

        self.assertEqual(len(self.gelesen), 1, "das zweite Archiv hat neu erkannt")
        self.assertEqual(stat.gelesen, 1)
        self.assertEqual(len(zweites.index.search("Generalvollmacht")), 1)

    def test_ein_verwaister_vermerk_stoert_nicht(self) -> None:
        """Zu einer gelöschten Mail gibt es nichts mehr zuzuordnen."""
        archiv = self._archiv("A", [
            mail_mit_anhang("Vollmacht", "V.pdf", self.ANHANG, tag=1),
        ])
        self._lauf(archiv)
        archiv.index.db.execute(
            "INSERT INTO ocr_vermerk (hash, dateiname, zustand, seiten) "
            "SELECT hash, 'weg.pdf', 'erledigt', 3 FROM messages LIMIT 1"
        )
        archiv.index.commit()

        abgelegt, ohne = erkennung.vorrat_aufbauen(archiv)

        self.assertEqual(ohne, 1)
        self.assertEqual(abgelegt, 0, "der vorhandene lag schon im Vorrat")


class TestReihenfolge(ErkennungsTestFall):
    """Die kleinsten Dokumente zuerst."""

    def test_kleine_vor_grossen(self) -> None:
        """Wer abbricht, soll möglichst viel erledigt haben.

        Ein 20-MB-Scan kann eine Viertelstunde dauern. Steht er vorn,
        passiert in dieser Viertelstunde sichtbar nichts.
        """
        archiv = self._archiv("A", [
            mail_mit_anhang(name, f"{name}.pdf", b"%PDF" + b"x" * groesse)
            for name, groesse in (("gross", GROSS * 4), ("klein", GROSS),
                                  ("mittel", GROSS * 2))
        ])

        offen = erkennung.Warteschlange(archiv.index).offen(grenze=10)

        self.assertEqual(
            [n for _, _, n in offen],
            ["klein.pdf", "mittel.pdf", "gross.pdf"],
        )


if __name__ == "__main__":
    unittest.main()


class TestGescheiterteFreigeben(ErkennungsTestFall):
    """Ein Fehlschlag ist ein Vermerk, kein Urteil für immer.

    Er verhindert, dass die Warteschlange bei jedem Lauf über dieselben
    unlesbaren Dateien stolpert – richtig im Alltag, falsch, sobald die
    Texterkennung selbst besser geworden ist. Bis zum 2026-08-27
    scheiterten Scans aus der iPhone-Kamera-App an ihrer Seitengröße;
    ohne diesen Weg lägen sie für immer da, obwohl sie lesbar sind.
    """

    def test_aufgegebene_stehen_wieder_an(self) -> None:
        gleich = b"%PDF-Unlesbar" + b"u" * GROSS
        archiv = self._archiv("A", [
            mail_mit_anhang("Scan", "S.pdf", gleich, tag=1),
        ])
        self._lauf(archiv, text="", seiten=0)
        self.assertEqual(erkennung.Warteschlange(archiv.index).anzahl(), 0)

        frei = erkennung.gescheiterte_zuruecksetzen(archiv)

        self.assertEqual(frei, 1)
        self.assertEqual(erkennung.Warteschlange(archiv.index).anzahl(), 1)

    def test_erledigte_bleiben_erledigt(self) -> None:
        """Nur die Fehlschläge – sonst liefe alles noch einmal durch."""
        archiv = self._archiv("A", [
            mail_mit_anhang("Gut", "G.pdf", b"%PDF-Gut" + b"g" * GROSS, tag=1),
            mail_mit_anhang("Schlecht", "S.pdf", b"%PDF-Bad" + b"b" * GROSS, tag=2),
        ])
        # Erst der gute Lauf, dann ein gescheiterter für das zweite.
        with mock.patch.object(ocr, "bereit", return_value=(True, "")), \
                mock.patch.object(
                    ocr, "text_aus_pdf",
                    side_effect=lambda n, **_: _ergebnis(
                        "Erkannt" if b"Gut" in n else "", 2
                    )):
            erkennung.durchlauf(archiv, budget_sekunden=0, budget_dokumente=0)

        frei = erkennung.gescheiterte_zuruecksetzen(archiv)

        self.assertEqual(frei, 1)
        self.assertEqual(erkennung.Warteschlange(archiv.index).anzahl(), 1)


class TestDuenneErgebnisse(ErkennungsTestFall):
    """Erledigt heißt nicht gelesen.

    Eine eingescannte Briefseite ergibt tausend bis dreitausend Zeichen.
    Kommen zwölf heraus, hat tesseract vielleicht den Briefkopf
    erwischt, während der Rest Rauschen blieb. Das Dokument gilt danach
    als erledigt und wird nie wieder angefasst – und niemand erfährt es,
    weil ja etwas im Index steht.

    Genau die stille Lücke, die dieses Programm sonst überall vermeidet.
    """

    def test_wenig_text_wird_gemeldet(self) -> None:
        archiv = self._archiv("A", [
            mail_mit_anhang("Schlechter Scan", "S.pdf",
                            b"%PDF-Schlecht" + b"s" * GROSS, tag=1),
        ])

        stat = self._lauf(archiv, text="Rausch", seiten=3)

        self.assertEqual(len(stat.duenn), 1)
        name, seiten, zeichen = stat.duenn[0]
        self.assertEqual(name, "S.pdf")
        self.assertEqual(seiten, 3)
        self.assertEqual(zeichen, 6)
        # Erledigt bleibt es trotzdem - gemeldet, nicht wiederholt.
        self.assertEqual(stat.gelesen, 1)
        self.assertEqual(stat.offen_danach, 0)

    def test_ein_ordentliches_ergebnis_wird_nicht_gemeldet(self) -> None:
        archiv = self._archiv("A", [
            mail_mit_anhang("Guter Scan", "G.pdf",
                            b"%PDF-Gut" + b"g" * GROSS, tag=1),
        ])

        stat = self._lauf(archiv, text="X" * 3000, seiten=2)

        self.assertEqual(stat.duenn, [])

    def test_abschriften_werden_nicht_doppelt_gemeldet(self) -> None:
        """Sonst stünde dasselbe Dokument fünfmal in der Liste."""
        gleich = b"%PDF-Dublette" + b"d" * GROSS
        archiv = self._archiv("A", [
            mail_mit_anhang(f"Scan {i}", "S.pdf", gleich, tag=i)
            for i in range(1, 4)
        ])

        stat = self._lauf(archiv, text="kurz", seiten=2, gleichzeitig=3)

        self.assertEqual(len(stat.duenn), 1)
        self.assertEqual(stat.doppelt, 2)

    def test_die_zeichenzahl_bleibt_im_vermerk(self) -> None:
        """Damit sich später fragen lässt, welche Dokumente dürftig sind."""
        archiv = self._archiv("A", [
            mail_mit_anhang("Scan", "S.pdf", b"%PDF-Z" + b"z" * GROSS, tag=1),
        ])

        self._lauf(archiv, text="Zwölf Zeichen", seiten=1)

        zeichen = archiv.index.db.execute(
            "SELECT zeichen FROM ocr_vermerk"
        ).fetchone()[0]
        self.assertEqual(zeichen, len("Zwölf Zeichen"))

    def test_die_zeichenzahl_laesst_sich_nachtragen(self) -> None:
        """Ohne die Erkennung zu wiederholen.

        Der Text liegt im Nebenspeicher; nachzuschlagen ist er dort in
        Millisekunden. Ein zweiter Durchlauf durch tesseract wären
        Stunden – für eine Zahl, die schon feststeht.
        """
        archiv = self._archiv("A", [
            mail_mit_anhang("Scan", "S.pdf", b"%PDF-N" + b"n" * GROSS, tag=1),
        ])
        self._lauf(archiv, text="knapp", seiten=4)
        # Zurück auf »nicht erhoben« – so sehen ältere Vermerke aus.
        archiv.index.db.execute("UPDATE ocr_vermerk SET zeichen = -1")
        archiv.index.commit()

        ergaenzt, duenn = erkennung.zeichen_nachtragen(archiv)

        self.assertEqual(ergaenzt, 1)
        self.assertEqual(duenn, 1)
        self.assertEqual(
            archiv.index.db.execute(
                "SELECT zeichen FROM ocr_vermerk").fetchone()[0],
            len("knapp"),
        )

    def test_duenne_ueber_den_ganzen_bestand(self) -> None:
        archiv = self._archiv("A", [
            mail_mit_anhang("Gut", "G.pdf", b"%PDF-G" + b"g" * GROSS, tag=1),
            mail_mit_anhang("Schlecht", "S.pdf", b"%PDF-S" + b"s" * GROSS, tag=2),
        ])
        with mock.patch.object(ocr, "bereit", return_value=(True, "")), \
                mock.patch.object(
                    ocr, "text_aus_pdf",
                    side_effect=lambda n, **_: _ergebnis(
                        "X" * 3000 if b"%PDF-G" in n else "kurz", 2)):
            erkennung.durchlauf(archiv, budget_sekunden=0, budget_dokumente=0)

        liste = erkennung.duenne(archiv)

        self.assertEqual([n for n, _, _ in liste], ["S.pdf"])


def _ergebnis(text: str, seiten: int):
    fertig = ocr.Ergebnis()
    fertig.text = text
    fertig.seiten = seiten
    return fertig


class TestSchemaWirdHergerichtet(ErkennungsTestFall):
    """Wer die Vermerktabelle abfragt, muss sie auch anlegen lassen.

    Nur an echten Archiven aufgefallen: Im Test lief immer erst ein
    Durchlauf, der die Warteschlange erzeugt – und mit ihr die Tabelle.
    Ein Archiv, in dem die Texterkennung noch nie lief, hat sie nicht,
    und die Abfrage scheiterte an einer Spalte, die es nicht gab.
    """

    def test_auswertung_auf_einem_unberuehrten_archiv(self) -> None:
        archiv = self._archiv("A", [
            mail_mit_anhang("Ohne", "O.pdf", b"%PDF-O" + b"o" * GROSS, tag=1),
        ])

        # Kein Durchlauf davor - genau so sieht ein frisches Archiv aus.
        self.assertEqual(erkennung.zeichen_nachtragen(archiv), (0, 0))
        self.assertEqual(erkennung.duenne(archiv), [])
        self.assertEqual(erkennung.gescheiterte_zuruecksetzen(archiv), 0)
