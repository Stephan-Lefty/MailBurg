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


class SuchmaskeTest(OberflaechenTest):
    """Was die Maske zusammenstellt, muss die Suchsprache verstehen.

    Das ist der Grund, warum die Maske nichts kann, was die Sprache nicht
    kann: Sonst entstünden zwei Wege, von denen einer irgendwann
    hinterherhinkt – und die Kommandozeile wäre der schwächere.
    """

    def maske(self):
        from mailburg.ui.suchmaske import Suchmaske

        return Suchmaske()

    def test_leere_maske_ergibt_leeren_ausdruck(self):
        self.assertEqual(self.maske().ausdruck(), "")

    def test_jedes_feld_landet_im_ausdruck(self):
        m = self.maske()
        m.begriff.setText("rechnung")
        m.von.setText("müller")
        m.betreff.setText("mahnung")
        m.datei.setText("*.pdf")
        m.mit_anhang.setChecked(True)

        ausdruck = m.ausdruck()
        for teil in ("rechnung", "von:müller", "betreff:mahnung",
                     "datei:*.pdf", "hat:anhang"):
            with self.subTest(teil=teil):
                self.assertIn(teil, ausdruck)

    def test_mehrere_woerter_werden_zusammengehalten(self):
        # Ohne Anführungszeichen suchte "von:müller gmbh" nach zwei Dingen.
        m = self.maske()
        m.von.setText("müller gmbh")
        self.assertIn('von:"müller gmbh"', m.ausdruck())

    def test_jahresbereich(self):
        m = self.maske()
        m.jahr_von.setValue(2020)
        m.jahr_bis.setValue(2025)
        self.assertIn("jahr:2020-2025", m.ausdruck())

    def test_ein_einzelnes_jahr(self):
        m = self.maske()
        m.jahr_von.setValue(2025)
        self.assertIn("jahr:2025", m.ausdruck())

    def test_verdrehte_jahre_werden_gerichtet(self):
        m = self.maske()
        m.jahr_von.setValue(2026)
        m.jahr_bis.setValue(2020)
        self.assertIn("jahr:2020-2026", m.ausdruck())

    def test_ausschluesse_einzeln(self):
        m = self.maske()
        m.ohne.setText("werbung newsletter")
        ausdruck = m.ausdruck()
        self.assertIn("-werbung", ausdruck)
        self.assertIn("-newsletter", ausdruck)

    def test_groesse_nur_mit_wert(self):
        m = self.maske()
        m.groesse_art.setCurrentIndex(1)
        self.assertNotIn("groesse", m.ausdruck())
        m.groesse_wert.setText("5MB")
        self.assertIn("groesse:>5MB", m.ausdruck())

    def test_punkt_vor_der_endung_stoert_nicht(self):
        m = self.maske()
        m.typ.setText(".pdf")
        self.assertIn("typ:pdf", m.ausdruck())

    def test_die_vorschau_zeigt_denselben_ausdruck(self):
        m = self.maske()
        m.begriff.setText("vertrag")
        self.assertEqual(m.vorschau.text(), m.ausdruck())

    def test_das_ergebnis_ist_eine_gueltige_suche(self):
        # Der eigentliche Punkt: Die Sprache muss verstehen, was hier
        # herauskommt - sonst baut die Maske Ausdrücke ins Leere.
        from mailburg.search.query import build

        m = self.maske()
        m.begriff.setText("rechnung")
        m.von.setText("müller gmbh")
        m.betreff.setText("offene posten")
        m.datei.setText("*.pdf")
        m.archiviert.setText("2026-08")
        m.mit_anhang.setChecked(True)
        m.typ.setText("pdf")
        m.jahr_von.setValue(2024)
        m.jahr_bis.setValue(2026)
        m.groesse_art.setCurrentIndex(1)
        m.groesse_wert.setText("1MB")
        m.wichtigkeit.setCurrentIndex(1)
        m.ohne.setText("werbung")

        klausel, parameter = build(m.ausdruck())
        self.assertNotEqual(klausel, "1=1", "der Ausdruck darf nicht leer wirken")
        for erwartet in ("GLOB", "m.size", "m.wichtigkeit", "m.year", "m.archiviert"):
            with self.subTest(erwartet=erwartet):
                self.assertIn(erwartet, klausel)

    def test_das_ergebnis_laeuft_auch_wirklich(self):
        # Gültig gebaut heißt noch nicht, dass SQLite es ausführt.
        import sqlite3
        import tempfile
        from pathlib import Path

        from mailburg.core.index import Index
        from mailburg.search.query import build

        with tempfile.TemporaryDirectory() as ordner:
            index = Index(Path(ordner) / "test.db")
            m = self.maske()
            m.begriff.setText("rechnung")
            m.datei.setText("*.pdf")
            m.groesse_art.setCurrentIndex(2)
            m.groesse_wert.setText("10MB")
            m.wichtigkeit.setCurrentIndex(1)

            klausel, parameter = build(m.ausdruck())
            try:
                index.db.execute(
                    f"SELECT COUNT(*) FROM messages m WHERE {klausel}", parameter
                ).fetchone()
            except sqlite3.Error as fehler:
                self.fail(f"SQLite lehnt den Ausdruck ab: {fehler}")
            finally:
                index.close()


class SystemplatteTest(unittest.TestCase):
    """Der Hinweis, dass ein Plattendefekt beides auf einmal trifft."""

    def test_benutzerordner_gilt_als_systemplatte(self):
        from mailburg.core import orte

        erster = orte.vorschlagen()[0]
        self.assertEqual(erster.art, "benutzer")
        self.assertTrue(erster.auf_systemplatte)

    def test_eigene_datentraeger_werden_unterschieden(self):
        # Wenn alles als Systemplatte gälte, wäre der Hinweis wertlos -
        # dann käme er überall und niemand läse ihn.
        from mailburg.core import orte

        vorschlaege = orte.vorschlagen()
        if len(vorschlaege) < 2:
            self.skipTest("nur ein Ablageort auf diesem Rechner")
        self.assertFalse(
            all(o.auf_systemplatte for o in vorschlaege),
            "es muss auch Orte abseits der Systemplatte geben",
        )


class FadenLebensdauerTest(OberflaechenTest):
    """Der Absturz, der die Oberfläche zweimal kommentarlos beendet hat.

    Läuft ein Faden noch, während niemand mehr auf ihn zeigt, räumt Python
    ihn weg – und Qt beendet daraufhin das gesamte Programm. Das ist keine
    Python-Ausnahme und deshalb mit keinem try/except zu fangen.
    """

    def auftrag(self, dauer: float = 0.3):
        from mailburg.ui.arbeit import Auftrag

        class Langsam(Auftrag):
            def ausfuehren(self):
                import time

                time.sleep(dauer)
                return "fertig"

        return Langsam()

    def test_verlorene_referenz_haelt_den_faden_trotzdem(self):
        import gc

        from mailburg.ui import arbeit
        from mailburg.ui.arbeit import Läufer

        def starten_und_vergessen():
            Läufer(self.auftrag()).starten()

        starten_und_vergessen()
        gc.collect()
        self.assertEqual(len(arbeit._LAUFENDE), 1, "der Faden muss gehalten werden")
        arbeit.alle_beenden(3000)

    def test_nach_getaner_arbeit_wird_wieder_aufgeräumt(self):
        # Die Liste darf nicht endlos wachsen - sonst hielte sie jeden
        # Faden einer langen Sitzung fest.
        from mailburg.ui import arbeit
        from mailburg.ui.arbeit import Läufer

        laeufer = Läufer(self.auftrag(0.05))
        laeufer.starten()
        laeufer.faden.wait(3000)
        self.app.processEvents()
        self.assertNotIn(laeufer, arbeit._LAUFENDE)

    def test_alle_beenden_wartet_wirklich(self):
        from mailburg.ui import arbeit
        from mailburg.ui.arbeit import Läufer

        laeufer = Läufer(self.auftrag(0.2))
        laeufer.starten()
        arbeit.alle_beenden(3000)
        self.assertFalse(laeufer.faden.isRunning())
        self.assertEqual(len(arbeit._LAUFENDE), 0)

    def test_dialog_schliesst_sofort_und_ohne_absturz(self):
        # Genau der Weg, auf dem es zweimal geknallt hat: Prüfung läuft,
        # Fenster geht zu. Es darf weder abstürzen noch hängen - warten
        # würde die Oberfläche einfrieren, und zwar ausgerechnet dann,
        # wenn jemand abbrechen will, weil etwas klemmt.
        import time

        from mailburg.ui import arbeit
        from mailburg.ui.assistent import KontoDialog

        dialog = KontoDialog()
        laeufer = arbeit.Läufer(self.auftrag(0.4))
        laeufer.starten()

        beginn = time.monotonic()
        dialog.reject()
        gebraucht = time.monotonic() - beginn

        self.assertLess(gebraucht, 0.2, "das Schließen darf nicht blockieren")
        self.assertTrue(laeufer.auftrag.abgebrochen)
        # Der Faden lebt weiter, wird aber gehalten - kein Absturz.
        laeufer.faden.wait(3000)
        self.app.processEvents()

    def test_beenden_wartet_dagegen_sehr_wohl(self):
        # Beim Abbau der Anwendung ist es umgekehrt: Laufen dann noch
        # Fäden, stürzt Qt beim Aufräumen ab.
        from mailburg.ui import arbeit

        laeufer = arbeit.Läufer(self.auftrag(0.2))
        laeufer.starten()
        arbeit.alle_beenden(3000)
        self.assertFalse(laeufer.faden.isRunning())


class FenstergroesseTest(OberflaechenTest):
    """Der Assistent soll bei jedem Schritt gleich groß bleiben."""

    def test_alle_schritte_gleich_gross(self):
        # Ein Fenster, das bei jedem "Weiter" springt, wirkt unfertig -
        # und man verliert die Stelle, an der man gerade gelesen hat.
        from mailburg.ui.assistent import Einrichtungsassistent

        assistent = Einrichtungsassistent()
        assistent.show()
        self.app.processEvents()

        groessen = set()
        for kennung in assistent.pageIds():
            assistent.setStartId(kennung)
            assistent.restart()
            self.app.processEvents()
            groessen.add((assistent.width(), assistent.height()))

        self.assertEqual(len(groessen), 1, f"unterschiedliche Größen: {groessen}")

    def test_archivseite_rollt_statt_abzuschneiden(self):
        from PySide6.QtWidgets import QScrollArea

        from mailburg.ui.assistent import ArchivSeite

        seite = ArchivSeite()
        self.assertIsNotNone(
            seite.findChild(QScrollArea),
            "die Seite braucht einen Rollbereich, sonst fehlt unten die Fundstelle",
        )


class MehrfachRueckfragenTest(OberflaechenTest):
    """Mehrere gescheiterte Postfächer dürfen die Oberfläche nicht festfahren."""

    def seite_mit(self, *konten):
        from PySide6.QtWidgets import QGridLayout, QWidget

        from mailburg.ui.assistent import KontenSeite, KontoZeile

        seite = KontenSeite()
        self._halter = QWidget()
        gitter = QGridLayout(self._halter)
        for n, konto in enumerate(konten):
            zeile = KontoZeile(konto, gitter, n)
            zeile.passwort.setText("geheim")
            seite.zeilen.append(zeile)
        return seite

    def konto(self, adresse, server):
        from mailburg.core.accounts import Konto

        return Konto(name=adresse, server=server, benutzer=adresse, port=143, ssl=False)

    def test_kein_dialog_aus_dem_signalempfaenger(self):
        # Scheitern drei Postfächer fast gleichzeitig, kämen sonst drei
        # modale Dialoge ineinander - verschachtelte Ereignisschleifen,
        # und die Oberfläche steht. Genau das ist passiert.
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        seite = self.seite_mit(
            self.konto("a@example.org", "imap.example.org"),
            self.konto("b@example.org", "imap.example.org"),
        )
        seite._offen = 2

        gefragt = []
        with mock.patch.object(QMessageBox, "question",
                               lambda *a, **k: gefragt.append(1)):
            seite._misslungen(seite.zeilen[0], "Das Zertifikat gilt nicht für …")
            # Nach dem ersten von zwei darf noch nichts gefragt worden sein.
            self.assertEqual(gefragt, [], "erst fragen, wenn alle Prüfungen durch sind")

    def test_zertifikatsfaelle_kommen_vor_der_passwortfrage(self):
        # Wer beim Zertifikatsfehler nach dem Passwort gefragt würde, gäbe
        # dasselbe noch einmal ein - und es scheiterte wieder.
        from unittest import mock

        from mailburg.core import tlsdiagnose
        from PySide6.QtWidgets import QMessageBox

        seite = self.seite_mit(self.konto("a@example.org", "imap.example.org"))
        seite._offen = 1

        befund = tlsdiagnose.Befund(
            namen=["*.hoster.example"], rueckwaerts="s1.hoster.example",
            vorschlag="s1.hoster.example",
        )
        passwortfragen = []

        with mock.patch.object(tlsdiagnose, "untersuchen", return_value=befund), \
             mock.patch.object(QMessageBox, "question",
                               lambda *a, **k: QMessageBox.Yes), \
             mock.patch.object(seite, "_pruefen", lambda z: None), \
             mock.patch("mailburg.ui.assistent.PasswortNachfrage",
                        lambda *a, **k: passwortfragen.append(1)):
            seite._misslungen(seite.zeilen[0], "Das Zertifikat gilt nicht für …")

        self.assertEqual(passwortfragen, [], "hier ist nicht das Passwort schuld")
        self.assertEqual(seite.zeilen[0].konto.server, "s1.hoster.example")


class FadengrenzeTest(OberflaechenTest):
    """Rückmeldungen aus dem Hintergrund müssen im Faden der Oberfläche ankommen.

    Daran hing die Einrichtung fest: Die Antworten waren über Lambdas
    verbunden, denen Qt keinen Faden zuordnen kann. Also rief es sie
    sofort auf - im Arbeitsfaden -, und die Zeilen darunter fassten
    Widgets an. Das Fenster reagierte danach auf nichts mehr.
    """

    def test_empfaenger_laufen_im_faden_der_oberflaeche(self):
        import time

        from PySide6.QtCore import QCoreApplication, QObject, QThread

        from mailburg.ui.arbeit import Auftrag, Läufer

        class Rechnen(Auftrag):
            def ausfuehren(self):
                return QThread.currentThread()

        gesehen = {}

        class Empfaenger(QObject):
            def angekommen(self, arbeitsfaden):
                gesehen["arbeit"] = arbeitsfaden
                gesehen["empfang"] = QThread.currentThread()

        empfaenger = Empfaenger()
        auftrag = Rechnen()
        laeufer = Läufer(auftrag)
        auftrag.fertig.connect(empfaenger.angekommen)
        laeufer.starten()

        # Ereignisse abarbeiten, bis die Antwort da ist. Ein ``exec()``
        # wäre hier falsch: Der Test liefe dann in einer zweiten
        # Ereignisschleife und käme bei einem Fehler nie zurück.
        frist = time.monotonic() + 5
        while "empfang" not in gesehen and time.monotonic() < frist:
            QCoreApplication.processEvents()
            time.sleep(0.01)
        laeufer.warten(2000)

        self.assertIn("empfang", gesehen, "keine Antwort erhalten")
        self.assertIs(gesehen["empfang"], QThread.currentThread(),
                      "die Antwort kam im falschen Faden an")
        self.assertIsNot(gesehen["arbeit"], QThread.currentThread(),
                         "die Arbeit lief gar nicht nebenher")

    def test_keine_lambdas_an_hintergrundsignalen(self):
        # Die Regel steht in ui/arbeit.py. Sie hält nur, wenn sie geprüft
        # wird - ein Lambda ist schnell wieder hingeschrieben.
        import pathlib
        import re

        wurzel = pathlib.Path(__file__).resolve().parent.parent / "mailburg" / "ui"
        muster = re.compile(
            r"\.(fertig|gescheitert|meldung|fortschritt|konto_beginnt|"
            r"konto_fertig)\.connect\(\s*(lambda|functools\.partial|partial)"
        )
        for datei in wurzel.glob("*.py"):
            for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(muster.search(zeile),
                                  f"{datei.name}:{nr} verbindet ein Hintergrund"
                                  f"signal mit einem Lambda - das läuft im "
                                  f"Arbeitsfaden und friert die Oberfläche ein")


class KeinePruefschleifeTest(OberflaechenTest):
    """validatePage darf sich nicht selbst wieder anwerfen.

    Die Seite prüft nebenläufig, sagt deshalb erst Nein und schickt sich
    selbst weiter, sobald alle Antworten da sind. Dieses Weiterschicken
    ruft validatePage erneut auf - und ohne Merker prüft sie wieder.
    Beobachtet wurde: eine flackernde Zustandsspalte und ein Mailserver,
    der pro Umlauf drei neue Anmeldungen bekam.
    """

    def test_weiterschicken_prueft_nicht_noch_einmal(self):
        from unittest import mock

        from PySide6.QtWidgets import QGridLayout, QWidget, QWizard

        from mailburg.core.accounts import Konto
        from mailburg.ui.assistent import Einrichtungsassistent, KontoZeile

        assistent = Einrichtungsassistent()
        seite = assistent.page(assistent.pageIds()[2])
        halter = QWidget()
        gitter = QGridLayout(halter)
        zeile = KontoZeile(
            Konto(name="a@example.org", server="imap.example.org",
                  benutzer="a@example.org", port=143, ssl=False),
            gitter, 0,
        )
        zeile.passwort.setText("geheim")
        seite.zeilen.append(zeile)

        gepruefte = []
        with mock.patch.object(seite, "_pruefen", gepruefte.append), \
             mock.patch.object(seite, "_speichern", lambda: None), \
             mock.patch.object(QWizard, "next", lambda w: seite.validatePage()):
            self.assertFalse(seite.validatePage(), "prüft nebenläufig, also erst Nein")
            self.assertEqual(len(gepruefte), 1)

            # Antwort vom Server: alles in Ordnung. Die Seite schickt sich
            # weiter, und dabei darf sie nicht erneut prüfen.
            seite._geklappt(zeile, ["INBOX"])

        self.assertEqual(len(gepruefte), 1,
                         "die Prüfung lief ein zweites Mal - das ist die Schleife")


class TeilweiseEingerichtetTest(OberflaechenTest):
    """Wer einen Teil seiner Postfächer bewusst auslässt, muss weiterkommen."""

    def test_ein_eingerichtetes_postfach_genuegt_zum_weitergehen(self):
        from unittest import mock

        from PySide6.QtWidgets import QGridLayout, QMessageBox, QWidget

        from mailburg.core.accounts import Konto
        from mailburg.ui.assistent import Einrichtungsassistent, KontoZeile

        assistent = Einrichtungsassistent()
        seite = assistent.page(assistent.pageIds()[2])
        halter = QWidget()
        gitter = QGridLayout(halter)

        # Sechs eingerichtet, zwei absichtlich ausgelassen - Stephans Lage
        # mit Proton und einem Konto, das er später einrichten wollte.
        for n, (adresse, fertig) in enumerate([
            ("a@example.org", True), ("b@example.org", True),
            ("proton@example.com", False), ("spaeter@example.net", False),
        ]):
            zeile = KontoZeile(
                Konto(name=adresse, server="imap.example.org",
                      benutzer=adresse, port=143, ssl=False),
                gitter, n,
            )
            zeile.ankreuz.setChecked(False)
            zeile.bereits_da = fertig
            seite.zeilen.append(zeile)

        ermahnt = []
        with mock.patch.object(QMessageBox, "information",
                               lambda *a, **k: ermahnt.append(1)):
            weiter = seite.validatePage()

        self.assertTrue(weiter, "die eingerichteten Postfächer genügen")
        self.assertEqual(ermahnt, [], "hier ist nichts zu ermahnen")
        self.assertEqual([k.name for k in assistent.konten],
                         ["a@example.org", "b@example.org"])
