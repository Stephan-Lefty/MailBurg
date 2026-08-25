"""Die Oberfläche, soweit sie sich ohne Bildschirm prüfen lässt.

Zwei Regeln, aus Schaden gelernt:

**Seiten einzeln aufbauen, nie den Assistenten durchschalten.** Ein
``next()`` ruft die Prüfroutine der Seite auf – und die legt ein Archiv an
oder öffnet einen Dialog, auf den in einem Testlauf niemand antwortet. Beim
ersten Versuch entstand so ein Archiv im Benutzerverzeichnis, beim zweiten
hing der Lauf zwei Minuten an einem modalen Fenster.

**Nichts prüfen, was Qt selbst schon prüft.** Ob ein Knopf einen Rahmen
hat, ist Qts Sache. Interessant ist, was MailBurg daraus macht: welche
Konten in der Liste landen, was mit Passwörtern geschieht, ob die
Nebenläufigkeit hält.
"""

from __future__ import annotations

import os
import unittest

# Ohne Bildschirm - läuft auch in der CI und öffnet nie ein Fenster.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 ist nicht installiert")
class OberflaechenTest(unittest.TestCase):
    """Grundgerüst mit einer einzigen QApplication für alle Tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class AssistentTest(OberflaechenTest):
    def test_assistent_hat_vier_schritte(self):
        from mailburg.ui.assistent import Einrichtungsassistent

        assistent = Einrichtungsassistent()
        self.assertEqual(len(assistent.pageIds()), 4)

    def test_archivseite_schlaegt_einen_ort_vor(self):
        # Ein leeres Feld wäre die schlechteste Vorgabe - der Anwender soll
        # bestätigen können, nicht erfinden müssen.
        from mailburg.ui.assistent import ArchivSeite

        seite = ArchivSeite()
        self.assertTrue(seite.pfad.text())

    def test_betriebsart_ist_im_zweifel_privat(self):
        from mailburg.core.archive import Mode
        from mailburg.ui.assistent import ArchivSeite

        seite = ArchivSeite()
        self.assertEqual(seite.betriebsart, Mode.PRIVAT)
        seite.geschaeftlich.setChecked(True)
        self.assertEqual(seite.betriebsart, Mode.GESCHAEFTLICH)

    def test_fristen_nur_beim_geschaeftsarchiv(self):
        from mailburg.ui.assistent import ArchivSeite

        seite = ArchivSeite()
        self.assertFalse(seite.rechtsraum.isEnabled())
        seite.geschaeftlich.setChecked(True)
        self.assertTrue(seite.rechtsraum.isEnabled())

    def test_passwortfeld_zeigt_nichts_an(self):
        from mailburg.core.accounts import Konto
        from mailburg.ui.assistent import KontoZeile
        from PySide6.QtWidgets import QGridLayout, QLineEdit, QWidget

        # Der Halter muss am Leben bleiben - ohne Referenz räumt Python
        # ihn sofort weg, und Qt nimmt das Layout gleich mit.
        halter = QWidget()
        gitter = QGridLayout(halter)
        zeile = KontoZeile(
            Konto(name="A", server="imap.example.org", benutzer="post"), gitter, 0
        )
        self.assertEqual(zeile.passwort.echoMode(), QLineEdit.Password)

    def test_bruecke_wird_in_der_zeile_benannt(self):
        from mailburg.core.accounts import Konto
        from mailburg.ui.assistent import KontoZeile
        from PySide6.QtWidgets import QGridLayout, QWidget

        halter = QWidget()
        gitter = QGridLayout(halter)
        konto = Konto(
            name="Proton", server="127.0.0.1", benutzer="post@proton.me",
            port=1143, ssl=False, bruecke=True,
        )
        zeile = KontoZeile(konto, gitter, 0)
        self.assertIn("Brücke", zeile.beschreibung.text())


class KontoDialogTest(OberflaechenTest):
    def test_port_folgt_der_verschluesselung(self):
        # Wer STARTTLS wählt, meint fast immer 143 - den Port dann von Hand
        # ändern zu müssen, ist eine unnötige Fehlerquelle.
        from mailburg.ui.assistent import KontoDialog

        dialog = KontoDialog()
        self.assertEqual(dialog.port.value(), 993)
        dialog.verschluesselung.setCurrentIndex(1)
        self.assertEqual(dialog.port.value(), 143)

    def test_lokaler_server_gilt_als_bruecke(self):
        from mailburg.ui.assistent import KontoDialog

        dialog = KontoDialog()
        dialog.benutzer.setText("post@proton.me")
        dialog.server.setText("127.0.0.1")
        dialog.verschluesselung.setCurrentIndex(1)
        konto = dialog.konto()
        self.assertTrue(konto.bruecke)
        self.assertTrue(konto.ist_lokale_bruecke)

    def test_fremder_server_gilt_nicht_als_bruecke(self):
        from mailburg.ui.assistent import KontoDialog

        dialog = KontoDialog()
        dialog.server.setText("imap.example.org")
        self.assertFalse(dialog.konto().bruecke)

    def test_ohne_namen_dient_die_adresse(self):
        from mailburg.ui.assistent import KontoDialog

        dialog = KontoDialog()
        dialog.benutzer.setText("post@example.org")
        dialog.server.setText("imap.example.org")
        self.assertEqual(dialog.konto().name, "post@example.org")


class ArbeitTest(OberflaechenTest):
    """Die Nebenläufigkeit – der Teil, der ein Fenster einfrieren lässt."""

    def test_auftrag_meldet_sein_ergebnis(self):
        from mailburg.ui.arbeit import Auftrag, Läufer

        class Rechnen(Auftrag):
            def ausfuehren(self):
                return 6 * 7

        empfangen = []
        auftrag = Rechnen()
        auftrag.fertig.connect(empfangen.append)
        laeufer = Läufer(auftrag)
        laeufer.starten()
        laeufer.faden.wait(3000)
        self.app.processEvents()

        self.assertEqual(empfangen, [42])

    def test_ein_fehler_toetet_den_faden_nicht_stumm(self):
        # Ohne das Abfangen stürbe der Faden lautlos, und die Oberfläche
        # wartete ewig auf ein Ergebnis, das nie kommt.
        from mailburg.ui.arbeit import Auftrag, Läufer

        class Scheitern(Auftrag):
            def ausfuehren(self):
                raise RuntimeError("so nicht")

        fehler = []
        auftrag = Scheitern()
        auftrag.gescheitert.connect(fehler.append)
        laeufer = Läufer(auftrag)
        laeufer.starten()
        laeufer.faden.wait(3000)
        self.app.processEvents()

        self.assertEqual(fehler, ["so nicht"])

    def test_abbruch_kommt_beim_auftrag_an(self):
        from mailburg.ui.arbeit import Auftrag

        auftrag = Auftrag()
        self.assertFalse(auftrag.abgebrochen)
        auftrag.abbrechen()
        self.assertTrue(auftrag.abgebrochen)


if __name__ == "__main__":
    unittest.main()


class TrefferlisteTest(OberflaechenTest):
    """Das Datenmodell hinter der Trefferliste."""

    def modell(self, anzahl: int = 0):
        from mailburg.ui.modelle import Trefferliste

        class GefaelschterIndex:
            def __init__(self, gesamt):
                self.gesamt = gesamt
                self.abfragen = 0

            def count(self, ausdruck):
                return self.gesamt

            def search(self, ausdruck, limit=200, offset=0):
                self.abfragen += 1
                from mailburg.core.index import Hit

                return [
                    Hit(hash=f"h{i}", bucket="b", subject=f"Betreff {i}",
                        from_addr="a@example.org", from_name="Absender",
                        date="2026-08-25T10:00:00", size=1024,
                        has_attachments=bool(i % 2))
                    for i in range(offset, min(offset + limit, self.gesamt))
                ]

        return Trefferliste(GefaelschterIndex(anzahl))

    def test_attribut_verdeckt_nicht_qts_index(self):
        # Der Fehler, der mich Zeit gekostet hat: index() ist eine
        # Kernmethode von QAbstractItemModel. Ein gleichnamiges Attribut
        # legt jede Anzeige lahm - und zwar erst zur Laufzeit, tief in Qt.
        modell = self.modell(3)
        modell.suchen("")
        self.assertTrue(callable(modell.index))
        self.assertTrue(modell.index(0, 0).isValid())

    def test_erster_block_wird_geladen(self):
        from mailburg.ui.modelle import BLOCK

        modell = self.modell(1000)
        modell.suchen("")
        self.assertEqual(modell.gesamt, 1000)
        self.assertEqual(modell.rowCount(), BLOCK)

    def test_nachladen_beim_rollen(self):
        from mailburg.ui.modelle import BLOCK

        modell = self.modell(1000)
        modell.suchen("")
        self.assertTrue(modell.canFetchMore())
        modell.fetchMore()
        self.assertEqual(modell.rowCount(), 2 * BLOCK)

    def test_am_ende_wird_nicht_weiter_gefragt(self):
        modell = self.modell(5)
        modell.suchen("")
        self.assertFalse(modell.canFetchMore())

    def test_anhangszeichen_nur_bei_anhang(self):
        from PySide6.QtCore import Qt

        modell = self.modell(2)
        modell.suchen("")
        self.assertEqual(modell.data(modell.index(0, 0), Qt.DisplayRole), "")
        self.assertEqual(modell.data(modell.index(1, 0), Qt.DisplayRole), "📎")

    def test_ohne_betreff_steht_ein_hinweis(self):
        from PySide6.QtCore import Qt
        from mailburg.core.index import Hit

        modell = self.modell(1)
        modell.suchen("")
        modell.treffer[0] = Hit(
            hash="h", bucket="b", subject="", from_addr="a@example.org",
            from_name="", date=None, size=0, has_attachments=False,
        )
        self.assertEqual(
            modell.data(modell.index(0, 3), Qt.DisplayRole), "(kein Betreff)"
        )


class VorschauTest(OberflaechenTest):
    def test_auszeichnung_im_betreff_wird_entschaerft(self):
        # Ein Betreff mit spitzen Klammern darf die Anzeige nicht
        # durcheinanderbringen - und schon gar nicht formatieren.
        from mailburg.ui.vorschau import _sicher

        self.assertEqual(_sicher("<b>Angebot</b>"), "&lt;b&gt;Angebot&lt;/b&gt;")
        self.assertEqual(_sicher("Meier & Söhne"), "Meier &amp; Söhne")

    def test_leere_vorschau_bleibt_ansprechbar(self):
        from mailburg.ui.vorschau import Mailvorschau

        vorschau = Mailvorschau()
        vorschau.leeren()
        self.assertIn("aus", vorschau.text.toPlainText())

    def test_anhang_ohne_bild_bekommt_keine_vorschau(self):
        from mailburg.extract.message import Attachment
        from mailburg.ui.vorschau import Anhangszeile

        zeile = Anhangszeile(
            Attachment(filename="brief.pdf", mime_type="application/pdf",
                       size=9, payload=b"%PDF-1.4\n")
        )
        self.assertIsNone(zeile._bild())

    def test_pfadanteile_im_dateinamen_werden_abgeschnitten(self):
        # Ein Anhang namens "../../.bashrc" darf beim Öffnen nirgendwo
        # landen außer im Wegwerfordner.
        from mailburg.extract.message import Attachment
        from mailburg.ui.vorschau import Anhangszeile

        zeile = Anhangszeile(
            Attachment(filename="../../.bashrc", mime_type="text/plain",
                       size=4, payload="böse".encode("utf-8"))
        )
        ziel = zeile._ablegen()
        self.assertEqual(ziel.name, ".bashrc")
        self.assertNotIn("..", str(ziel))


class OrteTest(unittest.TestCase):
    """Welche Ablageorte vorgeschlagen werden."""

    def test_benutzerordner_ist_immer_dabei(self):
        from mailburg.core import orte

        vorschlaege = orte.vorschlagen()
        self.assertTrue(vorschlaege)
        self.assertEqual(vorschlaege[0].art, "benutzer")

    def test_jeder_ort_kennt_seinen_platz(self):
        from mailburg.core import orte

        for ort in orte.vorschlagen():
            with self.subTest(ort=ort.beschriftung):
                self.assertGreater(ort.gesamt, 0)
                self.assertIn("frei", ort.freier_platz)

    def test_archivordner_wird_angehaengt(self):
        # Der Anwender wählt einen Ort, kein Verzeichnis - das Archiv soll
        # nicht lose in seinem Benutzerordner liegen.
        from mailburg.core import orte

        for ort in orte.vorschlagen():
            with self.subTest(ort=ort.beschriftung):
                self.assertEqual(ort.pfad.name, orte.VORGABENAME)

    def test_knapper_platz_wird_erkannt(self):
        from mailburg.core.orte import Ort

        eng = Ort("Test", __import__("pathlib").Path("/x"), "laufwerk",
                  frei=500 * 1024**2, gesamt=10 * 1024**3)
        weit = Ort("Test", __import__("pathlib").Path("/x"), "laufwerk",
                   frei=50 * 1024**3, gesamt=100 * 1024**3)
        self.assertTrue(eng.eng)
        self.assertFalse(weit.eng)


class PasswortSichtbarkeitTest(OberflaechenTest):
    """Die Umschaltung zwischen Punkten und Klartext."""

    def feld(self):
        from PySide6.QtWidgets import QLineEdit
        from mailburg.ui.assistent import sichtbarkeit_anbieten

        feld = QLineEdit()
        feld.setEchoMode(QLineEdit.Password)
        sichtbarkeit_anbieten(feld)
        return feld

    def test_beginnt_versteckt(self):
        from PySide6.QtWidgets import QLineEdit

        self.assertEqual(self.feld().echoMode(), QLineEdit.Password)

    def test_umschalten_und_zurueck(self):
        from PySide6.QtWidgets import QLineEdit

        feld = self.feld()
        aktion = feld.actions()[0]

        aktion.trigger()
        self.assertEqual(feld.echoMode(), QLineEdit.Normal)
        self.assertIn("verbergen", aktion.toolTip().lower())

        aktion.trigger()
        self.assertEqual(feld.echoMode(), QLineEdit.Password)
        self.assertIn("anzeigen", aktion.toolTip().lower())

    def test_der_inhalt_bleibt_erhalten(self):
        feld = self.feld()
        feld.setText("geheim123")
        feld.actions()[0].trigger()
        self.assertEqual(feld.text(), "geheim123")

    def test_kontozeile_hat_die_umschaltung(self):
        from PySide6.QtWidgets import QGridLayout, QWidget
        from mailburg.core.accounts import Konto
        from mailburg.ui.assistent import KontoZeile

        halter = QWidget()
        zeile = KontoZeile(
            Konto(name="A", server="imap.example.org", benutzer="post"),
            QGridLayout(halter), 0,
        )
        self.assertTrue(zeile.passwort.actions())


class PasswortNachfrageTest(OberflaechenTest):
    """Was bei einer gescheiterten Anmeldung angeboten wird."""

    def konto(self, **abweichend):
        from mailburg.core.accounts import Konto

        werte = {"name": "Firma", "server": "imap.example.org", "benutzer": "post"}
        werte.update(abweichend)
        return Konto(**werte)

    def test_bietet_ein_passwortfeld_an(self):
        # Der Kern: nicht nur melden, sondern gleich richtigstellen lassen.
        from PySide6.QtWidgets import QLineEdit
        from mailburg.ui.assistent import PasswortNachfrage

        dialog = PasswortNachfrage(self.konto(), "Anmeldung abgelehnt")
        self.assertEqual(dialog.passwort.echoMode(), QLineEdit.Password)
        self.assertTrue(dialog.passwort.actions(), "Klartext muss umschaltbar sein")

    def test_rat_bei_grossen_anbietern(self):
        from mailburg.ui.assistent import PasswortNachfrage

        rat = PasswortNachfrage._rat(
            self.konto(server="imap.gmail.com"), "Anmeldung abgelehnt"
        )
        self.assertIn("App-Passwort", rat)

    def test_rat_bei_einer_bruecke(self):
        from mailburg.ui.assistent import PasswortNachfrage

        rat = PasswortNachfrage._rat(
            self.konto(server="127.0.0.1", bruecke=True, ssl=False, port=1143),
            "Anmeldung abgelehnt",
        )
        self.assertIn("Brücke", rat)

    def test_rat_bei_fehlender_verbindung(self):
        from mailburg.ui.assistent import PasswortNachfrage

        rat = PasswortNachfrage._rat(self.konto(), "Keine Verbindung zu …")
        self.assertIn("erreichbar", rat)

    def test_zertifikatsfehler_ist_kein_passwortproblem(self):
        from mailburg.ui.assistent import PasswortNachfrage

        rat = PasswortNachfrage._rat(
            self.konto(), "Das Zertifikat gilt nicht für imap.example.org"
        )
        self.assertIn("kein Passwortproblem", rat)

    def test_ohne_erkannten_grund_kein_geschwaetz(self):
        from mailburg.ui.assistent import PasswortNachfrage

        self.assertEqual(PasswortNachfrage._rat(self.konto(), ""), "")


class FehleranzeigeTest(unittest.TestCase):
    """Die Oberfläche darf nicht stumm verschwinden."""

    def test_haken_wird_gesetzt(self):
        import sys

        from mailburg.ui.app import _fehler_zeigen_statt_sterben

        vorher = sys.excepthook
        try:
            _fehler_zeigen_statt_sterben()
            self.assertIsNot(sys.excepthook, vorher)
        finally:
            sys.excepthook = vorher

    def test_abbruch_durch_den_anwender_bleibt_unangetastet(self):
        # Strg+C soll weiterhin einfach beenden, ohne Fehlerfenster.
        import sys

        from mailburg.ui.app import _fehler_zeigen_statt_sterben

        vorher = sys.excepthook
        try:
            _fehler_zeigen_statt_sterben()
            gerufen = []
            sys.__excepthook__ = lambda *a: gerufen.append(a)
            sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
            self.assertTrue(gerufen)
        finally:
            sys.excepthook = vorher
