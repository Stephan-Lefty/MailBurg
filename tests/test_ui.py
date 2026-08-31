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
import pathlib
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

            def search(self, ausdruck, limit=200, offset=0,
                       sortierung="datum", absteigend=True):
                self.abfragen += 1
                self.zuletzt_sortiert = (sortierung, absteigend)
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


class SchluesselbundStattNachfrageTest(OberflaechenTest):
    """Nach einem Passwort fragen, das schon im Schlüsselbund liegt, geht nicht."""

    def test_eingerichtetes_postfach_wird_nicht_erneut_gefragt(self):
        from unittest import mock

        from PySide6.QtWidgets import QGridLayout, QWidget

        from mailburg.core.accounts import Konto
        from mailburg.ui import assistent as modul
        from mailburg.ui.assistent import Einrichtungsassistent, KontoZeile

        assistent = Einrichtungsassistent()
        seite = assistent.page(assistent.pageIds()[2])
        halter = QWidget()
        gitter = QGridLayout(halter)

        konto = Konto(name="a@example.org", server="imap.example.org",
                      benutzer="a@example.org", port=143, ssl=False)
        zeile = KontoZeile(konto, gitter, 0)
        zeile.ankreuz.setChecked(True)
        zeile.bereits_da = True
        # Das Feld bleibt leer - genau so, wie die Oberfläche es anzeigt.
        self.assertEqual(zeile.passwort.text(), "")
        seite.zeilen.append(zeile)

        gefragt = []
        with mock.patch.object(modul.accounts, "passwort_holen",
                               lambda k: "aus dem Schlüsselbund"), \
             mock.patch.object(modul, "PasswortNachfrage",
                               lambda *a, **k: gefragt.append(1)), \
             mock.patch.object(seite, "_pruefen", lambda z: gefragt.append(1)), \
             mock.patch.object(seite, "_speichern", lambda: None):
            weiter = seite.validatePage()

        self.assertEqual(gefragt, [],
                         "weder Nachfrage noch erneute Anmeldung nötig")
        self.assertTrue(weiter, "es geht weiter")


class ZeitplanTest(unittest.TestCase):
    """Der Hintergrundabruf muss sich aus der Oberfläche einrichten lassen.

    Bisher stand am Ende der Einrichtung der Rat, dafür ins Terminal zu
    wechseln und ./install.sh --zeitsteuerung aufzurufen - ein Skript, das
    im Quellverzeichnis liegt und das niemand zur Hand hat, der MailBurg
    installiert hat.
    """

    def setUp(self):
        import tempfile

        from mailburg.core import zeitplan

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.archiv = pathlib.Path(self.ordner.name) / "Archiv"
        self.archiv.mkdir()
        (self.archiv / "archive.json").write_text("{}", encoding="utf-8")

        self.dienste = pathlib.Path(self.ordner.name) / "systemd"
        self.aufrufe = []
        self.zeitplan = zeitplan

        import unittest.mock as mock

        for flicken in (
            mock.patch.object(zeitplan, "DIENSTE", self.dienste),
            mock.patch.object(zeitplan, "_systemctl",
                              lambda *a: self.aufrufe.append(a) or
                              __import__("subprocess").CompletedProcess(a, 0, "", "")),
            mock.patch.object(zeitplan, "moeglich", lambda: (True, "")),
        ):
            flicken.start()
            self.addCleanup(flicken.stop)

    def _einheit(self):
        """Der Name enthält das Archiv – eine eigene Einheit je Archiv.

        Mit einer festen Einheit überschrieb der zweite Zeitplan den
        ersten. Wer geschäftlich und privat trennt, hätte am Ende nur
        ein beliefertes Archiv gehabt und es nicht bemerkt.
        """
        return self.zeitplan._abrufeinheit(self.archiv)

    def test_zeitplan_wird_angelegt_und_eingeschaltet(self):
        geklappt, text = self.zeitplan.einrichten(self.archiv, 30)

        self.assertTrue(geklappt, text)
        einheit = self._einheit()
        self.assertIn(self.archiv.name.lower(), einheit)
        dienst = (self.dienste / f"{einheit}.service").read_text(encoding="utf-8")
        uhr = (self.dienste / f"{einheit}.timer").read_text(encoding="utf-8")

        self.assertIn(str(self.archiv), dienst)
        self.assertIn("OnUnitActiveSec=30min", uhr)
        # Ohne vollen Pfad liefe der Abruf nie: Ein Dienst startet ohne die
        # PATH-Ergänzungen einer Anmeldesitzung.
        self.assertIn("/", dienst.split("ExecStart=")[1].split()[0])
        self.assertIn(("enable", "--now", f"{einheit}.timer"), self.aufrufe)

    def test_abschalten_raeumt_die_dateien_weg(self):
        self.zeitplan.einrichten(self.archiv, 30)
        geklappt, _ = self.zeitplan.abschalten(self.archiv)

        self.assertTrue(geklappt)
        self.assertFalse((self.dienste / f"{self._einheit()}.timer").exists())
        self.assertFalse((self.dienste / f"{self._einheit()}.service").exists())

    def test_zwei_archive_bekommen_zwei_zeitplaene(self):
        """Der Fehler, der lange unbemerkt geblieben wäre.

        Mit einer festen Einheit überschrieb das Einrichten des zweiten
        Zeitplans den ersten. Danach wurde nur noch ein Archiv beliefert –
        und weil das andere ja weiterhin dalag, fiel es niemandem auf.
        """
        zweites = pathlib.Path(self.ordner.name) / "Zweitarchiv"
        zweites.mkdir()
        (zweites / "archive.json").write_text("{}", encoding="utf-8")

        self.zeitplan.einrichten(self.archiv, 30)
        self.zeitplan.einrichten(zweites, 60)

        uhren = sorted(p.name for p in self.dienste.glob("*.timer"))
        self.assertEqual(len(uhren), 2, uhren)
        # Und jeder zeigt auf sein eigenes Archiv.
        for pfad in (self.archiv, zweites):
            dienst = (self.dienste / f"{self.zeitplan._abrufeinheit(pfad)}.service")
            self.assertIn(str(pfad), dienst.read_text(encoding="utf-8"))

    def test_ohne_archiv_wird_nichts_angelegt(self):
        leer = pathlib.Path(self.ordner.name) / "leer"
        leer.mkdir()
        geklappt, text = self.zeitplan.einrichten(leer, 30)

        self.assertFalse(geklappt)
        self.assertIn("kein Archiv", text)
        self.assertFalse(self.dienste.exists())

    def test_takt_wird_wieder_ausgelesen(self):
        self.zeitplan.einrichten(self.archiv, 240)
        stand = self.zeitplan.zustand(self.archiv)

        self.assertEqual(stand.takt, 240)
        self.assertEqual(stand.archiv, str(self.archiv))


class KeineFremdenPostfaecherTest(OberflaechenTest):
    """Nicht abrufbare Postfächer werden gar nicht erst erwähnt.

    Der Hinweis "Nicht dabei:" zählte sie auf, samt Mailadresse. Das ist
    eine Zeile, die man versehentlich mit einem Bildschirmfoto weitergibt -
    und was Thunderbird kennt, gehört nicht zwangsläufig hierher: In
    Stephans Profil standen dort Testkonten einer ganz anderen Anwendung.
    """

    def test_uebergangene_postfaecher_tauchen_nirgends_auf(self):
        from unittest import mock

        from mailburg.core import uebernahme
        from mailburg.core.accounts import Konto
        from mailburg.sources import local
        from mailburg.ui.assistent import KontenSeite

        def fund(adresse, brauchbar):
            eintrag = mock.Mock()
            eintrag.konto = Konto(name=adresse, server="s", benutzer=adresse,
                                  port=143, ssl=False)
            eintrag.brauchbar = brauchbar
            eintrag.art = "ews"
            return eintrag

        with mock.patch.object(local, "find_thunderbird_profiles",
                               return_value=["/irgendwo"]), \
             mock.patch.object(uebernahme, "aus_thunderbird", return_value=[
                 fund("gut@example.org", True),
                 fund("testprofil@fremde-app.example", False),
             ]):
            seite = KontenSeite()
            seite.initializePage()

        text = seite.herkunft.text()
        self.assertNotIn("testprofil@fremde-app.example", text)
        self.assertNotIn("Nicht dabei", text)
        self.assertEqual(len(seite.zeilen), 1, "nur das abrufbare Postfach")


class MailadresseInDerUebersichtTest(OberflaechenTest):
    """Der Name allein genügt nicht, wenn mehrere Postfächer gleich heißen.

    "Kontakt" sagt bei drei Postfächern auf demselben Server nichts -
    kontakt@example.org lässt keinen Zweifel.
    """

    def test_postfachbaum_zeigt_die_adresse(self):
        import tempfile
        from unittest import mock

        from PySide6.QtCore import Qt

        from mailburg.core.accounts import Konto
        from mailburg.ui import hauptfenster as modul

        konto = Konto(name="Kontakt", server="s111.example", port=143,
                      benutzer="kontakt@example.org", ssl=False)

        with tempfile.TemporaryDirectory() as ordner:
            from mailburg.core.archive import Archive

            archiv = Archive.create(pathlib.Path(ordner) / "A")
            with mock.patch.object(modul, "Kontenliste",
                                   lambda: mock.Mock(konten=[konto])), \
                 mock.patch.object(type(archiv.index), "accounts",
                                   lambda self: [("Kontakt", "INBOX", 3)]):
                fenster = modul.Hauptfenster(archiv.root)
                self.addCleanup(fenster.close)
                fenster._baum_fuellen()

            beschriftungen = [
                fenster.baum.topLevelItem(i).text(0)
                for i in range(fenster.baum.topLevelItemCount())
            ]
            self.assertIn("kontakt@example.org", beschriftungen)
            self.assertNotIn("Kontakt", beschriftungen)

            # Gesucht wird weiterhin über den Namen - der steht so im Archiv.
            eintrag = next(
                fenster.baum.topLevelItem(i)
                for i in range(fenster.baum.topLevelItemCount())
                if fenster.baum.topLevelItem(i).text(0) == "kontakt@example.org"
            )
            self.assertIn("Kontakt", eintrag.data(0, Qt.UserRole))
            archiv.close()

    def test_ohne_eintrag_in_der_kontenliste_bleibt_der_name(self):
        # Fällt ein Postfach später aus der Liste, bleiben seine Mails im
        # Archiv - dann ist der Name alles, was es noch gibt.
        import tempfile
        from unittest import mock

        from mailburg.ui import hauptfenster as modul

        with tempfile.TemporaryDirectory() as ordner:
            from mailburg.core.archive import Archive

            archiv = Archive.create(pathlib.Path(ordner) / "A")
            with mock.patch.object(modul, "Kontenliste",
                                   lambda: mock.Mock(konten=[])), \
                 mock.patch.object(type(archiv.index), "accounts",
                                   lambda self: [("Weggefallen", "INBOX", 1)]):
                fenster = modul.Hauptfenster(archiv.root)
                self.addCleanup(fenster.close)
                fenster._baum_fuellen()

            beschriftungen = [
                fenster.baum.topLevelItem(i).text(0)
                for i in range(fenster.baum.topLevelItemCount())
            ]
            self.assertIn("Weggefallen", beschriftungen)
            archiv.close()


class FenstergroesseTest(OberflaechenTest):
    """Beim ersten Start großzügig, danach so, wie der Anwender es einstellte."""

    def setUp(self):
        import tempfile
        from unittest import mock

        from mailburg.core import paths

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        flicken = mock.patch.object(
            paths, "config_dir", lambda: pathlib.Path(self.ordner.name)
        )
        flicken.start()
        self.addCleanup(flicken.stop)

    def _fenster(self):
        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster

        ort = pathlib.Path(self.ordner.name) / "Archiv"
        if not (ort / "archive.json").exists():
            Archive.create(ort).close()
        fenster = Hauptfenster(ort)
        self.addCleanup(fenster.close)
        return fenster

    def test_beim_ersten_start_grosszuegig(self):
        fenster = self._fenster()
        flaeche = fenster.screen().availableGeometry()

        self.assertGreaterEqual(
            fenster.width(), min(1600, int(flaeche.width() * 0.9)) - 1,
            "ein knappes Fenster zwingt zum Ziehen, bevor man etwas erkennt",
        )

    def test_die_eingestellte_groesse_ueberlebt_den_neustart(self):
        # Klein genug, dass es auch auf den 800x600 des Testbildschirms
        # passt - sonst stutzt der Fenstermanager, und der Test misst ihn
        # statt uns.
        fenster = self._fenster()
        fenster.resize(640, 480)
        fenster._ansicht_speichern()

        zweites = self._fenster()
        self.assertEqual((zweites.width(), zweites.height()), (640, 480))

    def test_archiv_merken_loescht_die_groesse_nicht(self):
        # Die frühere Fassung schrieb die Datei komplett neu. Das Merken
        # des Archivs hätte die Fenstergröße gelöscht - ein Fehler, der
        # erst als "das Fenster vergisst wieder alles" aufgefallen wäre.
        from mailburg.core.einstellungen import gemerktes, merken

        fenster = self._fenster()
        fenster.resize(1111, 700)
        fenster._groesse_merken()

        merken(pathlib.Path(self.ordner.name) / "Archiv")

        stand = gemerktes()
        self.assertEqual(stand["breite"], 1111)
        self.assertIn("archiv", stand)


class StandardansichtTest(FenstergroesseTest):
    """Zurück zur Vorgabe, wenn man sich die Ansicht verstellt hat."""

    def test_zuruecksetzen_stellt_die_verhaeltnisse_wieder_her(self):
        fenster = self._fenster()
        fenster.waagerecht.setSizes([900, 100])  # Baum absurd breit gezogen

        fenster._standardansicht()

        links, rechts = fenster.waagerecht.sizes()
        anteil = links / (links + rechts)
        # Kein fester Wert: Auf einem schmalen Bildschirm setzt die
        # Mindestbreite des Baums die Untergrenze, nicht der Anteil.
        # Geprüft wird, was zählt - die Trefferliste bekommt den Platz.
        self.assertLess(anteil, 0.4, "der Baum nimmt immer noch zu viel ein")
        self.assertGreater(anteil, 0.1, "der Baum ist zum Streifen geschrumpft")

    def test_zuruecksetzen_ruehrt_die_eigene_ansicht_nicht_an(self):
        # "Auf Standard" ist eine Ansicht für jetzt, kein Löschbefehl.
        # Wer sich eine eigene Ansicht abgelegt hat, soll sie über
        # "Eigene Ansicht laden" zurückbekommen.
        from mailburg.core.einstellungen import gemerktes

        fenster = self._fenster()
        fenster.resize(640, 480)
        fenster._ansicht_speichern()

        fenster._standardansicht()

        self.assertEqual(gemerktes()["breite"], 640)

    def test_aus_dem_vollbild_heraus_zuruecksetzen(self):
        # Ohne showNormal bliebe das Fenster maximiert, und resize liefe
        # ins Leere - man klickte auf "Standard" und nichts geschähe.
        fenster = self._fenster()
        fenster.showMaximized()

        fenster._standardansicht()

        self.assertFalse(fenster.isMaximized())


class BestandsanzeigeTest(OberflaechenTest):
    """Ist mein Archiv auf dem Stand? Das muss man sehen, nicht glauben."""

    def test_zeitpunkt_wird_lesbar(self):
        """»heute«, »gestern«, sonst das Datum – deutsch geschrieben.

        Das Format kam bis zum 2026-08-31 aus ``QLocale`` und damit aus
        den Systemeinstellungen: auf einem englischen Rechner
        »8/24/2026«, auf einem Bauserver ohne Spracheinstellung
        »24 08 2026«. Seitdem ist es fest deutsch, wie der Rest des
        Programms – deshalb dürfen hier wieder Punkte erwartet werden.
        """
        from datetime import datetime, timedelta

        from mailburg.ui.hauptfenster import _abrufzeit

        jetzt = datetime.now().astimezone()
        self.assertIn("heute", _abrufzeit(jetzt.isoformat()))
        self.assertIn("gestern", _abrufzeit((jetzt - timedelta(days=1)).isoformat()))

        vorwoche = jetzt - timedelta(days=7)
        gezeigt = _abrufzeit(vorwoche.isoformat())
        self.assertIn(f"{vorwoche:%d.%m.%Y}", gezeigt)
        self.assertIn(f"{vorwoche:%H:%M}", gezeigt)

    def test_ohne_abruf_wird_das_gesagt(self):
        from mailburg.ui.hauptfenster import _abrufzeit

        # Kein Datum zu erfinden: "noch nicht abgerufen" ist die ehrliche
        # Auskunft. Ein leeres Feld sähe aus wie ein Anzeigefehler.
        self.assertEqual(_abrufzeit(""), "noch nicht abgerufen")
        self.assertIn("unbekannt", _abrufzeit("kein Datum"))

    def test_nur_ein_beendeter_lauf_zaehlt(self):
        # Ein Abruf, der an einem stummen Server scheitert, darf das
        # Archiv nicht als aktuell ausweisen - genau darauf schaut der
        # Anwender, bevor er sein Postfach aufräumen lässt.
        import tempfile

        from mailburg.core.sync import Abrufzustand

        with tempfile.TemporaryDirectory() as ordner:
            datei = pathlib.Path(ordner) / "zustand.json"
            zustand = Abrufzustand("egal", datei=datei)
            zustand.ordner_gesehen("Konto", "INBOX", 1)
            zustand.speichern()

            self.assertEqual(Abrufzustand("egal", datei=datei).zuletzt, "")

            zustand.lauf_beendet()
            zustand.speichern()
            self.assertTrue(Abrufzustand("egal", datei=datei).zuletzt)


class DatumsformatTest(OberflaechenTest):
    """Datumsangaben folgen der Systemsprache, nicht dem Speicherformat."""

    def setUp(self):
        from PySide6.QtCore import QLocale

        self.addCleanup(QLocale.setDefault, QLocale())

    def _mit(self, sprache, was):
        from PySide6.QtCore import QLocale

        from mailburg.ui import datum

        QLocale.setDefault(QLocale(sprache))
        return getattr(datum, was)("2026-08-26T21:14:03+02:00")

    def test_die_schreibweise_bleibt_deutsch(self):
        """Am 2026-08-31 gedreht: vorher folgte sie der Systemsprache.

        Das stand im Widerspruch zum übrigen Programm, das Qts eigene
        Beschriftungen **fest** auf Deutsch stellt – heraus kam »Weiter«
        neben »8/26/2026«. Mit Stephan entschieden: alles auf Deutsch.

        Der Test steht auf dem Kopf, was er vorher prüfte, und das ist
        der Punkt: Er hielt die alte Entscheidung fest, jetzt hält er
        die neue.
        """
        for sprache in ("de_DE", "en_US", "en_GB", "fr_FR", "C"):
            with self.subTest(sprache=sprache):
                self.assertEqual(self._mit(sprache, "tag"), "26.08.2026")

    def test_jahreszahlen_bleiben_vierstellig(self):
        # Qts Kurzformat kürzte auf zwei Stellen. In einem Mailarchiv ist
        # das ein handfestes Problem: Post von 1998 und Post von 2098
        # stünden beide als "98" da. Seit der festen Schreibweise kann
        # das nicht mehr passieren - geprüft wird es trotzdem.
        for sprache in ("de_DE", "en_US", "en_GB", "fr_FR", "it_IT"):
            with self.subTest(sprache=sprache):
                self.assertIn("2026", self._mit(sprache, "tag"))

    def test_kaputte_datumsangaben_stuerzen_nicht_ab(self):
        # Kopfzeilen aus zwanzig Jahren Mailverkehr enthalten alles.
        from mailburg.ui import datum

        for unsinn in ("", None, "kaputt", "0000-00-00", "26. August"):
            with self.subTest(wert=unsinn):
                self.assertEqual(datum.tag(unsinn), "")

    def test_datum_ohne_uhrzeit_geht_auch(self):
        from PySide6.QtCore import QLocale

        from mailburg.ui import datum

        QLocale.setDefault(QLocale("de_DE"))
        self.assertEqual(datum.tag("2026-08-26"), "26.08.2026")


class AbrufmeldungTest(OberflaechenTest):
    """»Alle Mails sind im Archiv« darf nur dastehen, wenn es stimmt."""

    def _fenster(self):
        import tempfile

        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ort = pathlib.Path(ordner.name) / "Archiv"
        Archive.create(ort).close()
        fenster = Hauptfenster(ort)
        self.addCleanup(fenster.close)
        return fenster

    def _melden(self, ergebnisse):
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        gesagt = []
        fenster = self._fenster()
        with mock.patch.object(QMessageBox, "information",
                               lambda *a, **k: gesagt.append(("gut", a[2]))), \
             mock.patch.object(QMessageBox, "warning",
                               lambda *a, **k: gesagt.append(("warnung", a[2]))):
            fenster._abruf_fertig(ergebnisse)
        return gesagt

    def test_nach_gelungenem_abruf_kommt_die_entwarnung(self):
        class Stat:
            neu = 12

        gesagt = self._melden({"a@example.org": Stat()})

        self.assertEqual(len(gesagt), 1)
        art, text = gesagt[0]
        self.assertEqual(art, "gut")
        self.assertIn("Alle Mails sind im Archiv", text)
        self.assertIn("12", text)

    def test_bei_einem_gescheiterten_postfach_keine_entwarnung(self):
        # Die falsche Entwarnung ist in einem Archivprogramm der teuerste
        # Fehler: Wer sie glaubt, räumt sein Postfach auf - und dann fehlt
        # die Post an beiden Stellen.
        class Stat:
            neu = 3

        gesagt = self._melden({
            "a@example.org": Stat(),
            "b@example.org": OSError("Server antwortet nicht"),
        })

        self.assertEqual(len(gesagt), 1)
        art, text = gesagt[0]
        self.assertEqual(art, "warnung")
        self.assertNotIn("Alle Mails sind im Archiv", text)
        self.assertIn("b@example.org", text)
        self.assertIn("noch nicht auf", text)

    def test_ohne_neues_wird_das_auch_gesagt(self):
        class Stat:
            neu = 0

        art, text = self._melden({"a@example.org": Stat()})[0]

        self.assertEqual(art, "gut")
        self.assertIn("nichts Neues", text)


class StandardTrotzTraegemFensterTest(FenstergroesseTest):
    """Die Aufteilung darf nicht davon abhängen, wann resize wirkt.

    resize() setzt die Größe nicht sofort - unter Wayland bestätigt der
    Compositor sie erst. Wer direkt danach self.width() liest, rechnet
    mit der alten Breite, und "Fenster auf Standard" tut sichtbar nicht,
    was es verspricht.
    """

    def test_verhaeltnis_stimmt_auch_ohne_wirksames_resize(self):
        from unittest import mock

        fenster = self._fenster()
        fenster.waagerecht.setSizes([900, 100])

        # Ein Fenster, das seine Größe hartnäckig nicht ändert.
        with mock.patch.object(type(fenster), "resize", lambda *a: None):
            fenster._standardansicht()

        links, rechts = fenster.waagerecht.sizes()
        self.assertLess(links / (links + rechts), 0.4)


class SpaltenAufStandardTest(FenstergroesseTest):
    """»Auf Standard« muss auch verzogene Spalten wieder geraderücken."""

    def test_spaltenbreiten_kommen_zurueck(self):
        fenster = self._fenster()
        vorher = fenster.tabelle.columnWidth(1)
        fenster.tabelle.setColumnWidth(1, vorher + 300)

        fenster._standardansicht()

        self.assertEqual(fenster.tabelle.columnWidth(1), vorher)


class SummenImBaumTest(OberflaechenTest):
    """Die Gesamtzahl je Postfach steht neben dem Postfach."""

    def _baum(self, eintraege):
        import tempfile
        from unittest import mock

        from mailburg.core.accounts import Konto
        from mailburg.core.archive import Archive
        from mailburg.ui import hauptfenster as modul

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        archiv = Archive.create(pathlib.Path(ordner.name) / "A")
        konto = Konto(name="Kontakt", server="s", port=143,
                      benutzer="kontakt@example.org", ssl=False)

        gesamt = sum(n for _, _, n in eintraege)
        with mock.patch.object(modul, "Kontenliste",
                               lambda: mock.Mock(konten=[konto])), \
             mock.patch.object(type(archiv.index), "accounts",
                               lambda self: eintraege), \
             mock.patch.object(type(archiv.index), "account_totals",
                               lambda self: {"Kontakt": gesamt}), \
             mock.patch.object(type(archiv.index), "count",
                               lambda self, ausdruck="": gesamt):
            fenster = modul.Hauptfenster(archiv.root)
            self.addCleanup(fenster.close)
            fenster._baum_fuellen()
        archiv.close()
        return fenster.baum

    def test_postfach_zeigt_die_summe_seiner_ordner(self):
        baum = self._baum([
            ("Kontakt", "INBOX", 9),
            ("Kontakt", "INBOX/DialOS-Mobil", 14),
            ("Kontakt", "Sent", 14),
        ])

        postfach = baum.topLevelItem(1)
        self.assertEqual(postfach.text(0), "kontakt@example.org")
        self.assertEqual(postfach.text(1), "37")

    def test_alle_postfaecher_zeigt_die_gesamtsumme(self):
        baum = self._baum([
            ("Kontakt", "INBOX", 1000),
            ("Kontakt", "Sent", 500),
        ])

        # Mit Tausenderpunkt: 1500 liest sich schlechter als 1.500, und
        # in einem Archiv stehen dort schnell sechsstellige Zahlen.
        self.assertEqual(baum.topLevelItem(0).text(1), "1.500")


class FarbkontrastTest(OberflaechenTest):
    """Zustandsfarben müssen in beiden Themen lesbar bleiben."""

    @staticmethod
    def _kontrast(vordergrund: str, hintergrund: str) -> float:
        def linear(anteil: float) -> float:
            return anteil / 12.92 if anteil <= 0.03928 else (
                ((anteil + 0.055) / 1.055) ** 2.4
            )

        def helligkeit(farbe: str) -> float:
            r, g, b = (int(farbe[i:i + 2], 16) / 255 for i in (1, 3, 5))
            return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)

        a, b = helligkeit(vordergrund), helligkeit(hintergrund)
        return (max(a, b) + 0.05) / (min(a, b) + 0.05)

    def test_beide_farbsaetze_erfuellen_wcag_aa(self):
        # 4,5:1 ist die Schwelle für gewöhnlichen Text. Ausgerechnet
        # "Anmeldung gescheitert" wäre sonst die am schlechtesten lesbare
        # Zeile im Fenster - die Meldung, auf die es ankommt.
        from mailburg.ui.farben import _DUNKEL, _HELL

        for satz, grund, wie in ((_HELL, "#ffffff", "hell"),
                                 (_DUNKEL, "#232629", "dunkel")):
            for rolle, farbe in satz.items():
                with self.subTest(thema=wie, rolle=rolle):
                    self.assertGreaterEqual(
                        self._kontrast(farbe, grund), 4.5,
                        f"{farbe} auf {grund} ist zu schwach",
                    )

    def test_ohne_aussage_bleibt_die_schrift_frei(self):
        from mailburg.ui import farben

        # Kein "color:" - dann gilt wieder die Farbe des Themas.
        self.assertEqual(farben.stil(None), "")

    def test_das_thema_entscheidet(self):
        from unittest import mock

        from mailburg.ui import farben

        with mock.patch.object(farben, "dunkles_thema", lambda: True):
            dunkel = farben.schlecht()
        with mock.patch.object(farben, "dunkles_thema", lambda: False):
            hell = farben.schlecht()

        self.assertNotEqual(dunkel, hell)


class EigeneAnsichtTest(FenstergroesseTest):
    """Die eingestellte Größe muss den Neustart überleben – auch unter Wayland."""

    def test_groesse_wird_als_zahl_gemerkt(self):
        # Nicht als saveGeometry(): Unter Wayland darf ein Fenster seine
        # Position nicht kennen, Qt schreibt dort Platzhalter, und
        # restoreGeometry() stellt anschließend gehorsam 720x720 an
        # Position 40,40 her. Die eingestellte Größe war nie gespeichert.
        from mailburg.core.einstellungen import gemerktes

        fenster = self._fenster()
        fenster.resize(640, 480)
        fenster._ansicht_speichern()

        stand = gemerktes()
        self.assertEqual(stand["breite"], 640)
        self.assertEqual(stand["hoehe"], 480)
        self.assertNotIn("fenster", stand)

    def test_gespeicherte_ansicht_kommt_beim_neustart_zurueck(self):
        fenster = self._fenster()
        fenster.resize(640, 480)
        fenster._ansicht_speichern()

        zweites = self._fenster()
        self.assertEqual((zweites.width(), zweites.height()), (640, 480))

    def test_laden_holt_die_eigene_ansicht_zurueck(self):
        fenster = self._fenster()
        fenster.resize(640, 480)
        fenster._ansicht_speichern()
        fenster._standardansicht()

        fenster._ansicht_laden()

        self.assertEqual((fenster.width(), fenster.height()), (640, 480))

    def test_ohne_gespeicherte_ansicht_wird_erklaert_statt_nichts_zu_tun(self):
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        fenster = self._fenster()
        gesagt = []
        with mock.patch.object(QMessageBox, "information",
                               lambda *a, **k: gesagt.append(a[2])):
            fenster._ansicht_laden()

        self.assertEqual(len(gesagt), 1)
        self.assertIn("Eigene Ansicht speichern", gesagt[0])


class SuchmeldungTest(OberflaechenTest):
    """Das Suchergebnis muss man sehen, ohne danach zu suchen."""

    def _fenster_mit(self, treffer):
        import tempfile

        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ort = pathlib.Path(ordner.name) / "Archiv"
        Archive.create(ort).close()
        fenster = Hauptfenster(ort)
        self.addCleanup(fenster.close)

        # Am Objekt statt an der Klasse: gesamt ist ein Instanzattribut,
        # und ein globales patch.stopall risse den übrigen Tests die
        # eigenen Flicken weg.
        def suchen(ausdruck, _t=treffer):
            fenster.modell.gesamt = _t

        fenster.modell.suchen = suchen
        return fenster

    def _text(self, fenster):
        import re

        return re.sub("<[^>]+>", "", fenster.suchmeldung.text())

    def test_treffer_werden_gemeldet(self):
        fenster = self._fenster_mit(191)
        fenster.suchfeld.setText("rechnung")
        fenster._suchen()

        self.assertEqual(self._text(fenster), "MailBurg hat 191 Treffer.")

    def test_ohne_treffer_steht_das_da(self):
        # Sonst sucht jemand weiter in einer Liste, die noch von der
        # vorigen Suche stammt.
        fenster = self._fenster_mit(0)
        fenster.suchfeld.setText("gibtsnicht")
        fenster._suchen()

        self.assertIn("nichts gefunden", self._text(fenster))
        self.assertIn("color:", fenster.suchmeldung.text())

    def test_waehrend_der_suche_steht_es_auch_da(self):
        fenster = self._fenster_mit(5)
        fenster.suchfeld.setText("rechnung")
        fenster._tippen()

        self.assertEqual(self._text(fenster), "MailBurg sucht …")

    def test_ohne_suchausdruck_wird_nichts_behauptet(self):
        # Wer nichts gesucht hat, bekommt kein Suchergebnis.
        fenster = self._fenster_mit(2078)
        fenster.suchfeld.setText("")
        fenster._suchen()

        self.assertEqual(fenster.suchmeldung.text(), "")

    def test_ein_falscher_ausdruck_wird_erklaert(self):
        from mailburg.search.query import QueryError

        fenster = self._fenster_mit(0)

        def stolpern(ausdruck):
            raise QueryError("'neulich' ist keine Jahreszahl")

        fenster.modell.suchen = stolpern
        fenster.suchfeld.setText("jahr:neulich")
        fenster._suchen()

        self.assertIn("stimmt nicht", self._text(fenster))


class PostfachreihenfolgeTest(OberflaechenTest):
    """Postfächer lassen sich anordnen – mit der Maus und ohne."""

    def setUp(self):
        import tempfile
        from unittest import mock

        from mailburg.core import paths

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        flicken = mock.patch.object(
            paths, "config_dir", lambda: pathlib.Path(self.ordner.name)
        )
        flicken.start()
        self.addCleanup(flicken.stop)

    def _fenster(self, konten=("a@example.org", "b@example.org", "c@example.org")):
        from unittest import mock

        from mailburg.core.accounts import Konto
        from mailburg.core.archive import Archive
        from mailburg.ui import hauptfenster as modul

        ort = pathlib.Path(self.ordner.name) / "Archiv"
        if not (ort / "archive.json").exists():
            Archive.create(ort).close()
        archiv = Archive.open(ort, exclusive=False)
        liste = [Konto(name=k, server="s", port=143, benutzer=k, ssl=False)
                 for k in konten]

        with mock.patch.object(modul, "Kontenliste",
                               lambda: mock.Mock(konten=liste)), \
             mock.patch.object(type(archiv.index), "accounts",
                               lambda self: [(k, "INBOX", 1) for k in konten]), \
             mock.patch.object(type(archiv.index), "account_totals",
                               lambda self: {k: 1 for k in konten}), \
             mock.patch.object(type(archiv.index), "count",
                               lambda self, a="": len(konten)):
            fenster = modul.Hauptfenster(ort)
            self.addCleanup(fenster.close)
            fenster._baum_fuellen()
        archiv.close()
        return fenster

    def _namen(self, fenster):
        return [fenster.baum.topLevelItem(i).text(0)
                for i in range(1, fenster.baum.topLevelItemCount())]

    def test_verschieben_ohne_maus(self):
        # Wer mit der Tastatur arbeitet oder eine Sprachsteuerung nutzt,
        # kommt ans Ziehen nicht heran. Eine Anordnung, die sich nur
        # ziehen lässt, ist deshalb keine.
        fenster = self._fenster()
        fenster.baum.setCurrentItem(fenster.baum.topLevelItem(3))

        fenster.baum.verschieben(-1)

        self.assertEqual(self._namen(fenster),
                         ["a@example.org", "c@example.org", "b@example.org"])

    def test_reihenfolge_ueberlebt_den_neustart(self):
        fenster = self._fenster()
        fenster.baum.setCurrentItem(fenster.baum.topLevelItem(3))
        fenster.baum.verschieben(-1)

        zweites = self._fenster()
        self.assertEqual(self._namen(zweites),
                         ["a@example.org", "c@example.org", "b@example.org"])

    def test_alle_postfaecher_bleibt_oben(self):
        fenster = self._fenster()
        fenster.baum.setCurrentItem(fenster.baum.topLevelItem(1))

        fenster.baum.verschieben(-1)

        self.assertEqual(fenster.baum.topLevelItem(0).text(0), "Alle Postfächer")

    def test_neues_postfach_verschwindet_nicht(self):
        # Es steht noch nicht in der gemerkten Reihenfolge - dahinter
        # gehört es, nicht ins Nichts.
        fenster = self._fenster()
        fenster.baum.setCurrentItem(fenster.baum.topLevelItem(3))
        fenster.baum.verschieben(-1)

        zweites = self._fenster(
            ("a@example.org", "b@example.org", "c@example.org", "neu@example.org")
        )
        self.assertIn("neu@example.org", self._namen(zweites))
        self.assertEqual(self._namen(zweites)[-1], "neu@example.org")


class HandbuchTest(OberflaechenTest):
    """Das Handbuch muss verständlich sein, ehrlich – und vollständig."""

    def _text(self, kennung):
        from mailburg.ui.hilfe import kapitel

        return next(k.text for k in kapitel() if k.kennung == kennung)

    def test_jeder_menuepunkt_ist_erklaert(self):
        # Aus dem echten Menü gelesen, nicht aus einer abgeschriebenen
        # Liste: Sonst laufen Menü und Handbuch auseinander, ohne dass es
        # auffällt. Genau das war schon passiert - das Handbuch erklärte
        # ein "Archiv schließen", das es nicht gibt, und kannte das
        # umbenannte "Archiv wechseln" nicht.
        import tempfile

        from PySide6.QtGui import QAction

        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster
        from mailburg.ui.hilfe import kapitel

        with tempfile.TemporaryDirectory() as ordner:
            ort = pathlib.Path(ordner) / "Archiv"
            Archive.create(ort).close()
            fenster = Hauptfenster(ort)
            self.addCleanup(fenster.close)
            punkte = [
                a.text().replace("&", "").removesuffix(" …").strip()
                for menue in fenster.menuBar().actions()
                for a in menue.menu().actions()
                if isinstance(a, QAction) and a.text() and not a.isSeparator()
            ]

        alles = " ".join(k.text for k in kapitel())
        for punkt in punkte:
            with self.subTest(menuepunkt=punkt):
                self.assertIn(punkt, alles,
                              f"»{punkt}« steht im Menü, aber nicht im Handbuch")

    def test_journalkapitel_ohne_fachwoerter(self):
        text = self._text("journal")

        for fachwort in ("SHA-256", "Hash", "Blockchain"):
            self.assertNotIn(fachwort, text)
        self.assertIn("Fingerabdruck", text)

    def test_journalkapitel_sagt_auch_was_es_nicht_leistet(self):
        # Eine halbe Zusage ist in Rechtsfragen schlimmer als keine.
        text = self._text("journal")

        self.assertIn("nicht leistet", text)
        self.assertIn("unterstützt", text)
        self.assertNotIn("GoBD-konform", text)

    def test_aufraeumen_warnt_vor_der_falschen_reihenfolge(self):
        text = self._text("aufraeumen")

        self.assertIn("abgleich", text)
        self.assertIn("nicht auf", text)

    def test_fristenkapitel_erhebt_keinen_rechtsanspruch(self):
        text = self._text("fristen")

        self.assertIn("Kein Rechtsrat", text)
        self.assertNotIn("rechtssicher", text.lower())

    def test_querverweise_zeigen_auf_vorhandene_kapitel(self):
        import re

        from mailburg.ui.hilfe import kapitel

        stuecke = kapitel()
        vorhanden = {k.kennung for k in stuecke}
        for stueck in stuecke:
            for ziel in re.findall(r'href="#([^"]+)"', stueck.text):
                with self.subTest(kapitel=stueck.kennung, ziel=ziel):
                    self.assertIn(ziel, vorhanden)

    def test_sprung_ins_kapitel(self):
        from mailburg.ui.hilfe import Hilfefenster

        fenster = Hilfefenster(beginnen_bei="journal")
        self.addCleanup(fenster.close)

        self.assertEqual(fenster.liste.currentItem().text(), "Das Journal")


class SortierungTest(OberflaechenTest):
    """Klick auf den Spaltenkopf sortiert – im Index, nicht in der Liste."""

    def modell(self):
        from mailburg.ui.modelle import Trefferliste

        class GefaelschterIndex:
            def __init__(self):
                self.zuletzt = None

            def count(self, ausdruck):
                return 3

            def search(self, ausdruck, limit=200, offset=0,
                       sortierung="datum", absteigend=True):
                from mailburg.core.index import Hit

                self.zuletzt = (sortierung, absteigend)
                return [
                    Hit(hash=f"h{i}", bucket="b", subject=f"Betreff {i}",
                        from_addr="a@example.org", from_name="Absender",
                        date="2026-08-25T10:00:00", size=1024,
                        has_attachments=False)
                    for i in range(3)
                ]

        suchindex = GefaelschterIndex()
        return Trefferliste(suchindex), suchindex

    def test_klick_auf_den_kopf_sortiert_nach_diesem_feld(self):
        from PySide6.QtCore import Qt

        modell, suchindex = self.modell()
        modell.suchen("")

        modell.sort(2, Qt.AscendingOrder)  # Absender

        self.assertEqual(suchindex.zuletzt, ("absender", False))

    def test_nochmal_klicken_dreht_die_richtung_um(self):
        from PySide6.QtCore import Qt

        modell, suchindex = self.modell()
        modell.sort(3, Qt.AscendingOrder)
        self.assertEqual(suchindex.zuletzt, ("betreff", False))

        modell.sort(3, Qt.DescendingOrder)
        self.assertEqual(suchindex.zuletzt, ("betreff", True))

    def test_nachladen_behaelt_die_sortierung(self):
        # Sonst kämen die nachgeladenen Treffer in einer anderen Ordnung
        # als die schon sichtbaren - und die Liste wäre in der Mitte
        # anders sortiert als oben.
        from PySide6.QtCore import Qt

        modell, suchindex = self.modell()
        modell.sort(4, Qt.AscendingOrder)  # Größe
        modell.gesamt = 500
        modell.fetchMore()

        self.assertEqual(suchindex.zuletzt, ("groesse", False))

    def test_unbekannte_spalte_aendert_nichts(self):
        from PySide6.QtCore import Qt

        modell, _ = self.modell()
        modell.sort(99, Qt.AscendingOrder)

        self.assertEqual(modell.sortierung, "datum")


class SpaltenkopfTest(OberflaechenTest):
    """Auch die schmale Anhangspalte braucht einen Namen."""

    def test_anhangspalte_ist_benannt(self):
        from PySide6.QtCore import Qt

        from mailburg.ui.modelle import Trefferliste

        modell = Trefferliste()
        # Ein Spaltenkopf ohne Text ist für einen Screenreader eine
        # namenlose Spalte - und mit der Maus weiß auch niemand, was
        # dort steht.
        self.assertIn(
            "Anhang", modell.headerData(0, Qt.Horizontal, Qt.ToolTipRole))
        self.assertEqual(
            modell.headerData(0, Qt.Horizontal, Qt.AccessibleTextRole), "Anhang")
        self.assertTrue(modell.headerData(0, Qt.Horizontal, Qt.DisplayRole))

    def test_alle_spalten_haben_einen_namen(self):
        from mailburg.ui.modelle import Trefferliste

        self.assertEqual(len(Trefferliste.SPALTENNAMEN),
                         len(Trefferliste.SPALTEN))
        self.assertTrue(all(Trefferliste.SPALTENNAMEN))


class ArchivwechselTest(OberflaechenTest):
    """Zwischen zwei Archiven wechselt man oft – das darf nicht mühsam sein."""

    def setUp(self):
        import tempfile
        from unittest import mock

        from mailburg.core import paths

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        flicken = mock.patch.object(
            paths, "config_dir", lambda: pathlib.Path(self.ordner.name)
        )
        flicken.start()
        self.addCleanup(flicken.stop)

    def _archiv(self, name, anzeigename):
        from mailburg.core.archive import Archive

        ort = pathlib.Path(self.ordner.name) / name
        Archive.create(ort, name=anzeigename).close()
        return ort

    def test_zuletzt_benutzte_stehen_im_menue(self):
        from mailburg.core.einstellungen import merken, zuletzt_benutzte

        geschaeftlich = self._archiv("G", "Geschäftsarchiv")
        privat = self._archiv("P", "Privatarchiv Familie")
        merken(geschaeftlich)
        merken(privat)

        self.assertEqual([p.name for p in zuletzt_benutzte()], ["P", "G"])

    def test_verschwundene_archive_stehen_nicht_im_menue(self):
        # Eine externe Platte kann abgezogen sein. Ein Menüeintrag, der
        # ins Leere führt, ist ärgerlicher als ein fehlender.
        import shutil

        from mailburg.core.einstellungen import merken, zuletzt_benutzte

        weg = self._archiv("W", "Weg")
        merken(weg)
        shutil.rmtree(weg)

        self.assertEqual(zuletzt_benutzte(), [])

    def test_dasselbe_archiv_steht_nur_einmal_da(self):
        from mailburg.core.einstellungen import merken, zuletzt_benutzte

        eins = self._archiv("E", "Eins")
        merken(eins)
        merken(eins)

        self.assertEqual(len(zuletzt_benutzte()), 1)

    def test_der_anzeigename_steht_im_menue_nicht_der_pfad(self):
        from mailburg.ui.hauptfenster import _archivname

        privat = self._archiv("P", "Privatarchiv Familie")

        # "Privatarchiv Familie" sagt mehr als
        # /mnt/usb-Hersteller_Portable_XXXXXXXX-0:0-part2.
        self.assertEqual(_archivname(privat), "Privatarchiv Familie")

    def test_ohne_lesbare_kennzeichnung_hilft_der_ordnername(self):
        from mailburg.ui.hauptfenster import _archivname

        kaputt = pathlib.Path(self.ordner.name) / "Kaputt"
        kaputt.mkdir()
        (kaputt / "archive.json").write_text("kein JSON", encoding="utf-8")

        self.assertEqual(_archivname(kaputt), "Kaputt")


class ZeitraumInDerSuchmaskeTest(OberflaechenTest):
    """Ein Zeitraum wird im Kalender gewählt, nicht getippt."""

    def maske(self):
        from mailburg.ui.suchmaske import Suchmaske

        maske = Suchmaske()
        self.addCleanup(maske.close)
        return maske

    def test_kalender_klappt_auf(self):
        maske = self.maske()

        for feld in (maske.datum_von, maske.datum_bis):
            self.assertTrue(feld.calendarPopup())

    def test_zeitraum_wird_zu_seit_und_bis(self):
        from PySide6.QtCore import QDate

        maske = self.maske()
        maske.zeitraum_an.setChecked(True)
        maske.datum_von.setDate(QDate(2026, 3, 1))
        maske.datum_bis.setDate(QDate(2026, 3, 31))

        self.assertEqual(maske.ausdruck(), "seit:01.03.2026 bis:31.03.2026")

    def test_verdrehte_eingabe_wird_geradegerueckt(self):
        # Wer zuerst das Ende einstellt und dann den Anfang, bekäme sonst
        # einen Zeitraum, der nie etwas findet.
        from PySide6.QtCore import QDate

        maske = self.maske()
        maske.zeitraum_an.setChecked(True)
        maske.datum_von.setDate(QDate(2026, 3, 31))
        maske.datum_bis.setDate(QDate(2026, 3, 1))

        self.assertEqual(maske.ausdruck(), "seit:01.03.2026 bis:31.03.2026")

    def test_ohne_haekchen_kein_zeitraum(self):
        maske = self.maske()
        maske.zeitraum_an.setChecked(False)

        self.assertEqual(maske.ausdruck(), "")

    def test_jahreszahl_bleibt_vierstellig(self):
        maske = self.maske()

        self.assertIn("yyyy", maske.datum_von.displayFormat())


class ArchiviertMitDeutschemDatumTest(unittest.TestCase):
    """Auch der Archiv-Zeitpunkt darf deutsch geschrieben werden."""

    def test_beide_schreibweisen(self):
        from mailburg.search.query import build

        _, deutsch = build("archiviert:26.08.2026")
        _, iso = build("archiviert:2026-08-25")

        self.assertEqual(deutsch, ["2026-08-26%"])
        self.assertEqual(iso, ["2026-08-25%"])

    def test_teilangaben_bleiben_iso(self):
        # "2026-08" trifft den ganzen Monat. Ein halbes deutsches Datum
        # wie "08.2026" bliebe mehrdeutig - Raten hat bei einer Suche im
        # eigenen Archiv nichts zu suchen.
        from mailburg.search.query import build

        _, werte = build("archiviert:2026-08")
        self.assertEqual(werte, ["2026-08%"])


class SortierhinweisTest(OberflaechenTest):
    """Dass sich sortieren lässt, muss man sehen können."""

    def modell(self):
        from mailburg.ui.modelle import Trefferliste

        return Trefferliste()

    def test_sortierbare_spalten_tragen_ein_zeichen(self):
        from PySide6.QtCore import Qt

        from mailburg.ui.modelle import Trefferliste

        modell = self.modell()
        # Wer nicht auf die Idee kommt, versuchsweise draufzuklicken,
        # sortiert sonst nie.
        betreff = modell.headerData(3, Qt.Horizontal, Qt.DisplayRole)
        self.assertIn(Trefferliste.SORTIERBAR.strip(), betreff)

    def test_die_aktive_spalte_traegt_es_nicht(self):
        from PySide6.QtCore import Qt

        from mailburg.ui.modelle import Trefferliste

        modell = self.modell()  # sortiert von Haus aus nach Datum
        datum = modell.headerData(1, Qt.Horizontal, Qt.DisplayRole)

        # Dort zeichnet Qt seinen eigenen Pfeil; zwei nebeneinander sagen
        # weniger als einer.
        self.assertNotIn(Trefferliste.SORTIERBAR.strip(), datum)
        self.assertEqual(datum, "Datum")

    def test_das_zeichen_wandert_beim_umsortieren(self):
        from PySide6.QtCore import Qt

        from mailburg.ui.modelle import Trefferliste

        modell = self.modell()
        modell.sort(3, Qt.AscendingOrder)  # nach Betreff

        self.assertEqual(
            modell.headerData(3, Qt.Horizontal, Qt.DisplayRole), "Betreff")
        self.assertIn(
            Trefferliste.SORTIERBAR.strip(),
            modell.headerData(1, Qt.Horizontal, Qt.DisplayRole))

    def test_der_tooltip_sagt_es_in_worten(self):
        from PySide6.QtCore import Qt

        modell = self.modell()

        self.assertEqual(
            modell.headerData(0, Qt.Horizontal, Qt.ToolTipRole),
            "Anhang – klicken zum Sortieren")

    def test_vorlesetext_bleibt_der_reine_name(self):
        # Ein Screenreader soll "Anhang" sagen, nicht "Anhang Pfeil
        # aufwärts abwärts klicken zum Sortieren".
        from PySide6.QtCore import Qt

        modell = self.modell()

        self.assertEqual(
            modell.headerData(2, Qt.Horizontal, Qt.AccessibleTextRole),
            "Absender")


class ZweiZeitpunkteTest(OberflaechenTest):
    """Versanddatum und Archivdatum dürfen nicht zu verwechseln sein.

    Eine Mail von 2016 kann heute ins Archiv gekommen sein. Wer nach dem
    einen sucht und das andere bekommt, hält das Ergebnis für
    vollständig - und es ist das falsche.
    """

    def test_die_maske_benennt_beide_getrennt(self):
        from PySide6.QtWidgets import QLabel

        from mailburg.ui.suchmaske import Suchmaske

        maske = Suchmaske()
        self.addCleanup(maske.close)
        beschriftungen = [w.text() for w in maske.findChildren(QLabel) if w.text()]

        self.assertTrue(any("Verschickt oder empfangen" in b
                            for b in beschriftungen))
        self.assertTrue(any("Ins Archiv aufgenommen" in b
                            for b in beschriftungen))

    def test_der_zeitraum_sucht_nach_dem_versand(self):
        from PySide6.QtCore import QDate

        from mailburg.ui.suchmaske import Suchmaske

        maske = Suchmaske()
        self.addCleanup(maske.close)
        maske.zeitraum_an.setChecked(True)
        maske.datum_von.setDate(QDate(2016, 1, 1))
        maske.datum_bis.setDate(QDate(2016, 12, 31))

        # seit:/bis: gehen auf das Versanddatum, archiviert: auf die
        # Aufnahme. Hier ist der Versand gemeint.
        self.assertIn("seit:", maske.ausdruck())
        self.assertNotIn("archiviert:", maske.ausdruck())

    def test_die_suchhilfe_sagt_worauf_sich_zeiten_beziehen(self):
        from mailburg.search.query import describe_syntax

        text = describe_syntax()
        self.assertIn("beziehen sich auf den Versand", text)

    def test_beide_filter_meinen_verschiedene_spalten(self):
        from mailburg.search.query import build

        versand, _ = build("am:26.08.2026")
        aufnahme, _ = build("archiviert:26.08.2026")

        self.assertIn("m.date", versand)
        self.assertIn("m.archiviert", aufnahme)


class WiederherstellenTest(OberflaechenTest):
    """Der Weg zurück ins Postfach."""

    def dialog(self, konten=("a@example.org", "b@example.org")):
        from unittest import mock

        from mailburg.core.accounts import Konto
        from mailburg.ui import zurueck as modul

        liste = [Konto(name=k, server="s", port=143, benutzer=k, ssl=False)
                 for k in konten]
        with mock.patch.object(modul, "Kontenliste",
                               lambda: mock.Mock(konten=liste)):
            fenster = modul.Zurueckdialog(b"Subject: Test\r\n\r\nText", "Rechnung")
        self.addCleanup(fenster.close)
        return fenster

    def test_alle_eingerichteten_postfaecher_stehen_zur_wahl(self):
        # Auch die, aus denen die Mail nicht stammt: Post überlebt
        # Anbieter und Adressen, das Konto von damals gibt es vielleicht
        # gar nicht mehr.
        dialog = self.dialog()

        self.assertEqual(dialog.konten.count(), 2)

    def test_ziel_ist_immer_der_posteingang(self):
        from mailburg.ui.zurueck import POSTEINGANG

        # IMAP schreibt diesen Namen vor - er ist auf jedem Server
        # derselbe, auch auf deutschsprachigen.
        self.assertEqual(POSTEINGANG, "INBOX")

    def test_ohne_postfach_wird_erklaert_statt_gesperrt(self):
        from PySide6.QtWidgets import QDialogButtonBox

        dialog = self.dialog(konten=())

        self.assertFalse(
            dialog.knoepfe.button(QDialogButtonBox.Ok).isEnabled())
        self.assertIn("kein Postfach eingerichtet", dialog.stand.text())
        self.assertIn("als Datei", dialog.stand.text())

    def test_anhaenge_kommen_mit(self):
        # Zurückgespielt wird die Nachricht Byte für Byte - Anhänge sind
        # Teil der Nachricht und damit automatisch dabei. Der Test hält
        # fest, dass niemand auf die Idee kommt, sie unterwegs zu
        # zerlegen.
        from mailburg.core.rueckgabe import als_datei

        roh = (b"Subject: Mit Anhang\r\n"
               b"Content-Type: multipart/mixed; boundary=xyz\r\n\r\n"
               b"--xyz\r\nContent-Type: text/plain\r\n\r\nText\r\n"
               b"--xyz\r\nContent-Disposition: attachment; "
               b"filename=rechnung.pdf\r\n\r\n%PDF-1.4\r\n--xyz--\r\n")

        import tempfile

        with tempfile.TemporaryDirectory() as ordner:
            abgelegt = als_datei(roh, pathlib.Path(ordner) / "m.eml")
            self.assertEqual(abgelegt.read_bytes(), roh)
            self.assertIn(b"rechnung.pdf", abgelegt.read_bytes())

    def test_doppelklick_ist_verdrahtet(self):
        import tempfile

        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster

        with tempfile.TemporaryDirectory() as ordner:
            ort = pathlib.Path(ordner) / "A"
            Archive.create(ort).close()
            fenster = Hauptfenster(ort)
            self.addCleanup(fenster.close)

            # Nicht jeder denkt bei einer Liste an die rechte Maustaste.
            # Ein Doppelklick auf eine leere Liste darf dabei nichts tun
            # und schon gar nicht stolpern.
            gerufen = []
            fenster._zuruecklegen = lambda *a: gerufen.append(1)
            fenster.tabelle.doubleClicked.disconnect()
            fenster.tabelle.doubleClicked.connect(fenster._zuruecklegen)
            fenster.tabelle.doubleClicked.emit(fenster.modell.index(0, 0))

            self.assertEqual(gerufen, [1])


class LesefensterTest(OberflaechenTest):
    """Doppelklick öffnet die Nachricht zum Lesen."""

    def _archiv_mit_mail(self):
        import tempfile

        from mailburg.core.archive import Archive

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        archiv = Archive.create(pathlib.Path(ordner.name) / "A")
        self.addCleanup(archiv.close)
        archiv.add(
            b"Subject: Rechnung 2016\r\nFrom: a@example.org\r\n"
            b"Date: Tue, 15 Mar 2016 09:12:00 +0100\r\n\r\nText",
            account="a", folder="INBOX",
        )
        return archiv

    def test_fenster_traegt_den_betreff(self):
        from mailburg.ui.lesefenster import oeffnen

        archiv = self._archiv_mit_mail()
        treffer = archiv.index.search("", limit=1)[0]

        fenster = oeffnen(treffer, archiv)
        self.addCleanup(fenster.close)

        self.assertEqual(fenster.windowTitle(), "Rechnung 2016")

    def test_mehrere_fenster_gleichzeitig(self):
        # Wer zwei Rechnungen vergleicht, braucht beide nebeneinander.
        from mailburg.ui.lesefenster import _OFFEN, oeffnen

        archiv = self._archiv_mit_mail()
        treffer = archiv.index.search("", limit=1)[0]

        erstes = oeffnen(treffer, archiv)
        zweites = oeffnen(treffer, archiv)
        self.addCleanup(erstes.close)
        self.addCleanup(zweites.close)

        self.assertEqual(len({erstes, zweites} & _OFFEN), 2)

    def test_geschlossene_fenster_werden_abgemeldet(self):
        # Sonst wächst die Liste mit jedem Blick in eine Mail.
        from mailburg.ui.lesefenster import _OFFEN, oeffnen

        archiv = self._archiv_mit_mail()
        treffer = archiv.index.search("", limit=1)[0]

        fenster = oeffnen(treffer, archiv)
        fenster.close()

        self.assertNotIn(fenster, _OFFEN)


class HtmlMitAbsaetzenTest(unittest.TestCase):
    """Eine Mail, die nur als HTML vorliegt, darf keine Textwurst werden."""

    def test_absaetze_bleiben_fuer_die_anzeige(self):
        # Bei Proton der Regelfall: Die Nachricht hat gar keinen
        # Klartextteil, und ohne Umbrüche lief sie zu einem Block
        # zusammen.
        from mailburg.extract.message import parse

        roh = (b"Subject: Rechnung\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
               b"<p>Sehr geehrter Herr M\xc3\xbcller,</p>"
               b"<p>anbei die Rechnung.</p>"
               b"<p>Mit freundlichen Gr\xc3\xbc\xc3\x9fen<br>Beispiel GmbH</p>")

        zerlegt = parse(roh)

        self.assertGreater(len(zerlegt.body.splitlines()), 3)
        self.assertIn("Sehr geehrter Herr Müller,", zerlegt.body)
        self.assertTrue(zerlegt.body.startswith("Sehr geehrter"))

    def test_hoechstens_eine_leerzeile_am_stueck(self):
        # HTML-Mails aus Newslettern bringen sonst zwanzig davon mit.
        from mailburg.extract.message import html_to_text

        text = html_to_text("<p>A</p><div><br></div><div><br></div><p>B</p>",
                            absaetze=True)

        self.assertNotIn("\n\n\n", text)

    def test_fuer_den_index_bleibt_es_eine_wortfolge(self):
        from mailburg.extract.message import html_to_text

        self.assertEqual(html_to_text("<p>Eins</p><p>Zwei</p>"), "Eins Zwei")


class TexterkennungDialogTest(OberflaechenTest):
    """Der Weg zur Texterkennung darf nicht durchs Terminal führen."""

    def _dialog(self, offen):
        import tempfile
        from unittest import mock

        from mailburg.core import erkennung
        from mailburg.core.archive import Archive
        from mailburg.ui.texterkennung import Texterkennungsdialog

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        archiv = Archive.create(pathlib.Path(ordner.name) / "A")
        self.addCleanup(archiv.close)

        with mock.patch.object(erkennung.Warteschlange, "anzahl",
                               lambda self: offen):
            dialog = Texterkennungsdialog(archiv)
        self.addCleanup(dialog.close)
        return dialog

    def test_sagt_wie_viele_warten_und_warum_das_zaehlt(self):
        dialog = self._dialog(36)
        text = dialog.erklaerung.text()

        self.assertIn("36", text)
        # Der Grund gehört dazu: Ein eingescanntes PDF meldet sich nicht,
        # es schweigt. Wer nicht weiß, dass ein Teil seines Archivs
        # unauffindbar ist, sucht diesen Menüpunkt nie.
        self.assertIn("weißes Blatt", text)
        self.assertIn("unangetastet", text)

    def test_keine_dauer_wird_versprochen(self):
        """Eine Schätzung, die nicht zu halten ist, richtet Schaden an.

        Vorher stand hier »Das dauert grob 7 Minuten«, hochgerechnet aus
        zwölf Sekunden je Dokument. Die Rechenzeit hängt aber an der
        Seitenzahl, und die sieht man einem PDF von außen nicht an: Ein
        Zweiseiter und eine sechzigseitige Zeugnismappe sind in der
        Warteschlange nicht zu unterscheiden. In der Praxis lag die
        Angabe um ein Vielfaches daneben – und legte dem Anwender nahe,
        es laufe etwas falsch, sobald es länger dauerte.

        Der Fortschrittsbalken zählt echte Dokumente. Daran sieht man
        nach einer Minute mehr als an jeder Vorhersage.
        """
        text = self._dialog(36).erklaerung.text()

        self.assertNotIn("Minute", text)
        self.assertNotIn("dauert", text)
        # Was stattdessen die Sorge nimmt: Es ist jederzeit abbrechbar
        # und läuft im Hintergrund weiter.
        self.assertIn("abbrechen", text)

    def test_ohne_wartende_gibt_es_nichts_zu_tun(self):
        from PySide6.QtWidgets import QDialogButtonBox

        dialog = self._dialog(0)

        self.assertFalse(
            dialog.knoepfe.button(QDialogButtonBox.Ok).isEnabled())
        self.assertIn("keine eingescannten PDF", dialog.erklaerung.text())

    def test_abbruch_verwirft_nichts(self):
        # Was gelesen ist, steht schon im Index - der Lauf schreibt nach
        # jedem Dokument. Abbrechen heißt aufhören, nicht zurücknehmen.
        from mailburg.core import erkennung

        quelltext = pathlib.Path(
            erkennung.__file__).read_text(encoding="utf-8")
        self.assertIn("if weiter is not None and not weiter():", quelltext)
        # Zwischen zwei Dokumenten, nicht mitten in einem.
        self.assertIn("archiv.index.commit()", quelltext)


class ErkennungsdialogLayoutTest(TexterkennungDialogTest):
    """Der erklärende Text darf nicht wegfallen, wenn der Balken kommt."""

    def test_das_fenster_richtet_sich_nach_dem_text(self):
        from PySide6.QtWidgets import QLayout

        dialog = self._dialog(57)

        # Notwendig, aber nicht hinreichend: Diese Vorgabe zwingt das
        # Fenster auf die gemeldete Mindestgröße - und die war beim
        # umbrechenden Absatz gerade die falsche Zahl. Deshalb rechnet
        # `Fliesstext` sie selbst aus.
        self.assertEqual(dialog.layout().sizeConstraint(),
                         QLayout.SetMinimumSize)

    def test_der_erklaerende_absatz_kennt_seine_hoehe(self):
        """Der eigentliche Fehler: Text, der beim Start verschwindet.

        Das Layout nimmt sich den Platz für den Fortschrittsbalken beim
        Absatz darüber – weil ein umbrechendes ``QLabel`` eine Höhe
        meldet, die für eine andere Breite gilt als die, die es
        tatsächlich hat. Der Text war dann nicht abgeschnitten, sondern
        fehlte; wer das Fenster zum ersten Mal sah, hielt den Rest für
        das Ganze.
        """
        from mailburg.ui.fliesstext import Fliesstext

        dialog = self._dialog(57)

        self.assertIsInstance(dialog.erklaerung, Fliesstext)
        self.assertTrue(dialog.erklaerung.sizePolicy().hasHeightForWidth())

    def test_der_balken_zeigt_zahlen_nicht_prozent(self):
        dialog = self._dialog(57)

        # "7 von 57" sagt mehr als "12%".
        self.assertIn("%v", dialog.balken.format())
        self.assertIn("%m", dialog.balken.format())


class ErkennungImHintergrundTest(TexterkennungDialogTest):
    """Fenster zu heißt nicht Arbeit weg."""

    def test_beim_schliessen_wird_gefragt(self):
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        dialog = self._dialog(57)
        # Ein Lauf, der noch nicht durch ist.
        dialog._laeufer = mock.Mock()
        dialog._laeufer.auftrag.abgebrochen = False
        dialog.balken.setRange(0, 57)
        dialog.balken.setValue(15)

        gefragt = []
        with mock.patch.object(QMessageBox, "question",
                               lambda *a, **k: gefragt.append(a[2])
                               or QMessageBox.Yes):
            dialog._abbrechen()

        self.assertEqual(len(gefragt), 1)
        self.assertIn("im Hintergrund", gefragt[0])
        # Anhalten ist die seltenere Absicht - deshalb nicht abgebrochen.
        dialog._laeufer_geprueft = True

    def test_weiterlaufen_reicht_den_laeufer_weiter(self):
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        dialog = self._dialog(57)
        laeufer = mock.Mock()
        laeufer.auftrag.abgebrochen = False
        dialog._laeufer = laeufer
        dialog.balken.setRange(0, 57)
        dialog.balken.setValue(15)

        weitergereicht = []
        dialog.weiterlaufen.connect(weitergereicht.append)
        with mock.patch.object(QMessageBox, "question",
                               lambda *a, **k: QMessageBox.Yes):
            dialog._abbrechen()

        self.assertEqual(weitergereicht, [laeufer])
        laeufer.auftrag.abbrechen.assert_not_called()

    def test_anhalten_bricht_wirklich_ab(self):
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        dialog = self._dialog(57)
        laeufer = mock.Mock()
        laeufer.auftrag.abgebrochen = False
        dialog._laeufer = laeufer
        dialog.balken.setRange(0, 57)
        dialog.balken.setValue(15)

        with mock.patch.object(QMessageBox, "question",
                               lambda *a, **k: QMessageBox.No):
            dialog._abbrechen()

        laeufer.auftrag.abbrechen.assert_called_once()

    def test_nach_dem_ende_wird_nicht_mehr_gefragt(self):
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        dialog = self._dialog(57)
        laeufer = mock.Mock()
        laeufer.auftrag.abgebrochen = False
        dialog._laeufer = laeufer
        dialog.balken.setRange(0, 57)
        dialog.balken.setValue(57)  # durch

        gefragt = []
        with mock.patch.object(QMessageBox, "question",
                               lambda *a, **k: gefragt.append(1)):
            dialog._abbrechen()

        self.assertEqual(gefragt, [])


class HintergrundhinweisTest(OberflaechenTest):
    """Was im Hintergrund läuft, gehört ins Blickfeld."""

    def _fenster(self):
        import tempfile

        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ort = pathlib.Path(ordner.name) / "A"
        Archive.create(ort).close()
        fenster = Hauptfenster(ort)
        self.addCleanup(fenster.close)
        return fenster

    def test_hinweis_steht_neben_der_trefferzahl(self):
        import re

        fenster = self._fenster()
        fenster._ocr_hinweis_setzen(15, 57)

        text = re.sub("<[^>]+>", "", fenster.ocr_hinweis.text())
        self.assertIn("15 von 57", text)
        self.assertIn("Hintergrund", text)
        # Farbig, damit man es beim Suchen bemerkt.
        self.assertIn("color:", fenster.ocr_hinweis.text())

    def test_nach_dem_ende_verschwindet_er(self):
        fenster = self._fenster()
        fenster._ocr_hinweis_setzen(15, 57)

        fenster._erkennung_fertig()

        self.assertEqual(fenster.ocr_hinweis.text(), "")

    def test_die_suchmeldung_bleibt_daneben_bestehen(self):
        # Beides gleichzeitig: Wer sucht, während gelesen wird, soll sein
        # Suchergebnis nicht verlieren.
        fenster = self._fenster()
        fenster._suchmeldung_setzen("MailBurg hat 191 Treffer.", True)
        fenster._ocr_hinweis_setzen(15, 57)

        self.assertIn("191", fenster.suchmeldung.text())
        self.assertIn("15 von 57", fenster.ocr_hinweis.text())


class TippsTest(OberflaechenTest):
    """Das Tipps-Kapitel sagt, was man nur aus dem Betrieb lernt."""

    def _text(self):
        from mailburg.ui.hilfe import kapitel

        return next(k.text for k in kapitel() if k.kennung == "tipps")

    def test_der_unterschied_zwischen_archiv_und_backup_steht_drin(self):
        text = self._text()

        # Der wichtigste Satz überhaupt: Ein Archiv auf einer Platte ist
        # keine Sicherung. Wer das verwechselt, schaltet sein bisheriges
        # Backup ab und steht mit einer einzigen Kopie da.
        self.assertIn("kein Backup", text)
        self.assertIn("zweiten", text)

    def test_der_index_muss_nicht_mitgesichert_werden(self):
        text = self._text()

        self.assertIn("Suchindex", text)
        self.assertIn("neu aufbauen", text)

    def test_nach_dem_zurueckholen_pruefen(self):
        # Eine Cloud-Synchronisation lässt schon einmal eine Datei aus,
        # und bei einem Archiv merkt man das erst Jahre später.
        text = self._text()

        self.assertIn("Journal prüfen", text)

    def test_das_kapitel_steht_im_verzeichnis(self):
        from mailburg.ui.hilfe import kapitel

        self.assertIn("Tipps", [k.titel for k in kapitel()])


class WeiterlesenNachRestTest(TexterkennungDialogTest):
    """Ein Lauf endet auch mit Rest – dann muss man weitermachen können."""

    def test_knopf_geht_wieder_an(self):
        from PySide6.QtWidgets import QDialogButtonBox

        class Stat:
            gelesen = 39
            gescheitert = 1
            offen_danach = 4
            fehler = []

        dialog = self._dialog(57)
        dialog.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)

        dialog._fertig(Stat())

        # Wer nach einem Lauf mit Rest nicht erneut starten kann, kommt
        # nie ans Ende seiner eingescannten PDF.
        self.assertTrue(dialog.knoepfe.button(QDialogButtonBox.Ok).isEnabled())
        self.assertEqual(
            dialog.knoepfe.button(QDialogButtonBox.Ok).text(), "Weiterlesen")
        self.assertIn("4 warten noch", dialog.stand.text())

    def test_ohne_rest_bleibt_er_aus(self):
        from PySide6.QtWidgets import QDialogButtonBox

        class Stat:
            gelesen = 57
            gescheitert = 0
            offen_danach = 0
            fehler = []

        dialog = self._dialog(57)
        dialog.knoepfe.button(QDialogButtonBox.Ok).setEnabled(False)

        dialog._fertig(Stat())

        self.assertFalse(dialog.knoepfe.button(QDialogButtonBox.Ok).isEnabled())


class EinzahlTest(TexterkennungDialogTest):
    """»1 eingescannte PDF warten« liest sich, als hätte niemand hingesehen."""

    def test_eine_wartet_im_singular(self):
        text = self._dialog(1).erklaerung.text()

        self.assertIn("1 eingescanntes PDF wartet", text)

    def test_mehrere_im_plural(self):
        self.assertIn("57 eingescannte PDF warten", self._dialog(57).erklaerung.text())


class SicherungsplanTest(OberflaechenTest):
    """Ein Backup, an das jemand denken muss, ist irgendwann keines."""

    def setUp(self):
        import subprocess
        import tempfile
        from unittest import mock

        from mailburg.core import zeitplan

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = pathlib.Path(self.ordner.name)
        self.aufrufe = []

        for flicken in (
            mock.patch.object(zeitplan, "DIENSTE", self.wo / "systemd"),
            mock.patch.object(zeitplan, "moeglich", lambda: (True, "")),
            mock.patch.object(
                zeitplan, "_systemctl",
                lambda *a: self.aufrufe.append(a)
                or subprocess.CompletedProcess(a, 0, "", ""),
            ),
        ):
            flicken.start()
            self.addCleanup(flicken.stop)

        self.archiv = self.wo / "Archiv"
        self.archiv.mkdir()
        (self.archiv / "archive.json").write_text("{}", encoding="utf-8")

    def test_zeitplan_wird_angelegt(self):
        from mailburg.core import zeitplan

        geklappt, text = zeitplan.sicherung_einrichten(
            self.archiv, self.wo / "Cloud", "täglich", 7
        )

        self.assertTrue(geklappt, text)
        dienst = (self.wo / "systemd" / "mailburg-sicherung-archiv.service").read_text(
            encoding="utf-8")
        self.assertIn("sichern", dienst)
        self.assertIn("--behalten 7", dienst)
        uhr = (self.wo / "systemd" / "mailburg-sicherung-archiv.timer").read_text(
            encoding="utf-8")
        self.assertIn("OnCalendar=daily", uhr)

    def test_nicht_ins_archiv_selbst(self):
        # Eine Sicherung neben dem Original geht mit ihm zusammen
        # verloren - dann ist sie keine.
        from mailburg.core import zeitplan

        geklappt, text = zeitplan.sicherung_einrichten(
            self.archiv, self.archiv / "Sicherungen"
        )

        self.assertFalse(geklappt)
        self.assertIn("nicht im Archiv selbst", text)

    def test_gestreut_statt_schlag_mitternacht(self):
        # Wenn alle Zeitpläne zugleich anlaufen, steht der Rechner.
        from mailburg.core import zeitplan

        zeitplan.sicherung_einrichten(self.archiv, self.wo / "Cloud")
        uhr = (self.wo / "systemd" / "mailburg-sicherung-archiv.timer").read_text(
            encoding="utf-8")

        self.assertIn("RandomizedDelaySec", uhr)
        self.assertIn("Persistent=true", uhr)

    def test_alte_staende_werden_weggeraeumt(self):
        # Ohne Grenze läuft die Platte voll, und dann scheitert
        # ausgerechnet die Sicherung, auf die es ankäme.
        import time

        from mailburg.__main__ import _alte_sicherungen_entfernen

        ordner = self.wo / "Cloud"
        ordner.mkdir()
        for n in range(5):
            datei = ordner / f"Archiv-2026-08-{20 + n}.tar.zst"
            datei.write_bytes(b"x")
            import os
            os.utime(datei, (time.time() - (5 - n) * 86400,) * 2)

        entfernt = _alte_sicherungen_entfernen(ordner, 3)

        self.assertEqual(len(entfernt), 2)
        uebrig = sorted(p.name for p in ordner.glob("*.tar.zst"))
        self.assertEqual(len(uebrig), 3)
        # Die jüngsten bleiben.
        self.assertIn("Archiv-2026-08-24.tar.zst", uebrig)

    def test_fremde_dateien_bleiben_liegen(self):
        # Gelöscht wird ausschließlich, was aussieht wie eine von uns
        # angelegte Sicherung.
        from mailburg.__main__ import _alte_sicherungen_entfernen

        ordner = self.wo / "Cloud"
        ordner.mkdir()
        (ordner / "wichtig.pdf").write_bytes(b"x")
        (ordner / "Archiv-2026-08-20.tar.zst").write_bytes(b"x")

        _alte_sicherungen_entfernen(ordner, 0)

        self.assertTrue((ordner / "wichtig.pdf").exists())


class ErsetzenStattSammelnTest(SicherungsplanTest):
    """Für die Cloud: eine Datei, die ersetzt wird."""

    def test_ohne_grenze_wird_ersetzt(self):
        # Nextcloud führt die Versionen ohnehin selbst; eine wachsende
        # Sammlung wäre dort doppelt gemoppelt und kostet Platz auf
        # einer Storage Box.
        from mailburg.core import zeitplan

        zeitplan.sicherung_einrichten(self.archiv, self.wo / "Cloud",
                                      "wöchentlich", behalten=0)
        dienst = (self.wo / "systemd" / "mailburg-sicherung-archiv.service").read_text(
            encoding="utf-8")

        self.assertIn("--ersetzen", dienst)
        self.assertNotIn("--behalten", dienst)

    def test_mit_grenze_wird_gesammelt(self):
        from mailburg.core import zeitplan

        zeitplan.sicherung_einrichten(self.archiv, self.wo / "Cloud",
                                      "täglich", behalten=7)
        dienst = (self.wo / "systemd" / "mailburg-sicherung-archiv.service").read_text(
            encoding="utf-8")

        self.assertIn("--behalten 7", dienst)
        self.assertNotIn("--ersetzen", dienst)

    def test_woechentlich_kommt_im_zeitplan_an(self):
        from mailburg.core import zeitplan

        zeitplan.sicherung_einrichten(self.archiv, self.wo / "Cloud",
                                      "wöchentlich")
        uhr = (self.wo / "systemd" / "mailburg-sicherung-archiv.timer").read_text(
            encoding="utf-8")

        self.assertIn("OnCalendar=weekly", uhr)


class EinPlanJeArchivTest(SicherungsplanTest):
    """Zwei Archive brauchen zwei Zeitpläne."""

    def test_getrennte_einheiten(self):
        # Mit einer festen Einheit überschriebe das Einrichten des
        # zweiten Archivs den ersten Plan - und nur eines von beiden
        # würde je gesichert. Bemerkt hätte das niemand: Es liegt ja
        # eine Sicherung da.
        from mailburg.core import zeitplan

        zweites = self.wo / "Privat"
        zweites.mkdir()
        (zweites / "archive.json").write_text("{}", encoding="utf-8")

        zeitplan.sicherung_einrichten(self.archiv, self.wo / "Cloud")
        zeitplan.sicherung_einrichten(zweites, self.wo / "Cloud")

        angelegt = sorted(p.name for p in (self.wo / "systemd").glob("*.timer"))
        self.assertEqual(len(angelegt), 2, angelegt)
        self.assertIn("mailburg-sicherung-archiv.timer", angelegt)
        self.assertIn("mailburg-sicherung-privat.timer", angelegt)

    def test_abschalten_trifft_nur_das_eigene(self):
        from mailburg.core import zeitplan

        zweites = self.wo / "Privat"
        zweites.mkdir()
        (zweites / "archive.json").write_text("{}", encoding="utf-8")
        zeitplan.sicherung_einrichten(self.archiv, self.wo / "Cloud")
        zeitplan.sicherung_einrichten(zweites, self.wo / "Cloud")

        zeitplan.sicherung_abschalten(zweites)

        uebrig = sorted(p.name for p in (self.wo / "systemd").glob("*.timer"))
        self.assertEqual(uebrig, ["mailburg-sicherung-archiv.timer"])

    def test_der_dateiname_wird_durchgereicht(self):
        # Sonst heißt die wöchentliche Sicherung wieder nach dem
        # Archivnamen statt nach dem, was der Anwender wollte.
        from mailburg.core import zeitplan

        zeitplan.sicherung_einrichten(
            self.archiv, self.wo / "Cloud", name="Geschaeftsarchiv"
        )
        dienst = (self.wo / "systemd" / "mailburg-sicherung-archiv.service"
                  ).read_text(encoding="utf-8")

        self.assertIn('--name "Geschaeftsarchiv"', dienst)


class MenuereihenfolgeTest(OberflaechenTest):
    """Was man täglich braucht, steht links."""

    def test_die_ordnung_stimmt(self):
        import tempfile

        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster

        with tempfile.TemporaryDirectory() as ordner:
            ort = pathlib.Path(ordner) / "A"
            Archive.create(ort).close()
            fenster = Hauptfenster(ort)
            self.addCleanup(fenster.close)

            menues = [
                m.text().replace("&", "") for m in fenster.menuBar().actions()
            ]

        self.assertEqual(
            menues,
            ["Archiv", "Post", "Suchen", "Ansicht", "Einstellungen", "Hilfe"],
        )


class FehlenderIndexTest(OberflaechenTest):
    """Ein leerer Index sieht aus wie ein verlorenes Archiv."""

    def _archiv_mit_mails(self, ordner):
        from mailburg.core.archive import Archive

        ort = pathlib.Path(ordner) / "A"
        archiv = Archive.create(ort)
        for n in range(3):
            archiv.add(
                f"Subject: Mail {n}\r\nFrom: a@example.org\r\n\r\nText".encode(),
                account="a", folder="INBOX",
            )
        archiv.close()
        return ort

    def test_bei_leerem_index_wird_gefragt(self):
        # Für den Anwender ist "0 Mails im Archiv" der Anblick eines
        # Datenverlusts - dabei liegen seine Mails unversehrt daneben.
        import tempfile
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        from mailburg.ui.hauptfenster import Hauptfenster

        with tempfile.TemporaryDirectory() as ordner:
            ort = self._archiv_mit_mails(ordner)
            # Index leeren, Journal behalten - genau die Lage nach einem
            # gelöschten Indexverzeichnis.
            from mailburg.core.archive import Archive

            with Archive.open(ort) as archiv:
                archiv.index.db.execute("DELETE FROM messages")
                archiv.index.commit()

            gefragt = []
            with mock.patch.object(QMessageBox, "question",
                                   lambda *a, **k: gefragt.append(a[2])
                                   or QMessageBox.No):
                fenster = Hauptfenster(ort)
                self.addCleanup(fenster.close)

        self.assertEqual(len(gefragt), 1)
        self.assertIn("Ihre Mails sind da", gefragt[0])
        self.assertIn("Minuten", gefragt[0])

    def test_bei_wirklich_leerem_archiv_keine_frage(self):
        # Ein frisch angelegtes Archiv ist zu Recht leer.
        import tempfile
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster

        with tempfile.TemporaryDirectory() as ordner:
            ort = pathlib.Path(ordner) / "Leer"
            Archive.create(ort).close()

            gefragt = []
            with mock.patch.object(QMessageBox, "question",
                                   lambda *a, **k: gefragt.append(1)):
                fenster = Hauptfenster(ort)
                self.addCleanup(fenster.close)

        self.assertEqual(gefragt, [])

    def test_bei_gefuelltem_index_keine_frage(self):
        import tempfile
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        from mailburg.ui.hauptfenster import Hauptfenster

        with tempfile.TemporaryDirectory() as ordner:
            ort = self._archiv_mit_mails(ordner)

            gefragt = []
            with mock.patch.object(QMessageBox, "question",
                                   lambda *a, **k: gefragt.append(1)):
                fenster = Hauptfenster(ort)
                self.addCleanup(fenster.close)

        self.assertEqual(gefragt, [])


class VerweisfarbeTest(OberflaechenTest):
    """Ein Link, den man nur findet, wenn man weiß, dass er da ist."""

    @staticmethod
    def _kontrast(vordergrund: str, hintergrund: str) -> float:
        def linear(anteil: float) -> float:
            return anteil / 12.92 if anteil <= 0.03928 else (
                ((anteil + 0.055) / 1.055) ** 2.4
            )

        def helligkeit(farbe: str) -> float:
            r, g, b = (int(farbe[i:i + 2], 16) / 255 for i in (1, 3, 5))
            return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)

        a, b = helligkeit(vordergrund), helligkeit(hintergrund)
        return (max(a, b) + 0.05) / (min(a, b) + 0.05)

    def test_beide_linkfarben_sind_lesbar(self):
        # Qts Standardblau erreicht auf dunklem Grund 1,8 - gefordert
        # sind 4,5 für gewöhnlichen Text.
        from mailburg.ui.farben import _LINK_DUNKEL, _LINK_HELL

        self.assertGreaterEqual(self._kontrast(_LINK_HELL, "#ffffff"), 4.5)
        self.assertGreaterEqual(self._kontrast(_LINK_DUNKEL, "#232629"), 4.5)

    def test_verweis_traegt_seine_farbe_mit(self):
        from mailburg.ui import farben

        html = farben.verweis("https://example.org", "Quelltext")

        self.assertIn("https://example.org", html)
        self.assertIn("color:", html)
        self.assertIn("Quelltext", html)

    def test_keine_farblosen_verweise_mehr(self):
        # Ein <a href> ohne Farbangabe erbt Qts Standardblau. Im
        # Handbuch übernimmt das ein Stylesheet für alle Verweise auf
        # einmal; überall sonst muss die Farbe am Verweis stehen.
        import re

        wurzel = pathlib.Path(__file__).resolve().parent.parent / "mailburg" / "ui"
        for datei in wurzel.glob("*.py"):
            if datei.name == "hilfe.py":
                continue
            text = datei.read_text(encoding="utf-8")
            for treffer in re.findall(r"<a href=[^>]*>", text):
                with self.subTest(datei=datei.name, verweis=treffer):
                    self.assertIn("color", treffer)

    def test_das_handbuch_faerbt_seine_verweise_geschlossen(self):
        from mailburg.ui.hilfe import Hilfefenster

        fenster = Hilfefenster()
        self.addCleanup(fenster.close)

        self.assertIn("a {", fenster.text.document().defaultStyleSheet())
        self.assertIn("color", fenster.text.document().defaultStyleSheet())


class HaeppchenNachDemAbrufTest(OberflaechenTest):
    """Was der Zeitplan tut, muss die Oberfläche auch tun."""

    def test_der_abruflauf_liest_eingescannte_pdf(self):
        # Sonst bleiben eingescannte PDF für alle unlesbar, die MailBurg
        # nur über die Oberfläche bedienen - und gerade die erfahren am
        # wenigsten davon, dass etwas fehlt.
        import inspect

        from mailburg.ui.arbeit import Abruflauf

        quelle = inspect.getsource(Abruflauf)
        self.assertIn("_anhaenge_lesen", quelle)
        self.assertIn("erkennung.durchlauf", quelle)

    def test_es_bleibt_ein_haeppchen(self):
        # Wer auf "Jetzt abrufen" klickt, wartet auf seine Post, nicht
        # auf Bilderkennung. Also kein budget_sekunden=0.
        import inspect

        from mailburg.ui.arbeit import Abruflauf

        quelle = inspect.getsource(Abruflauf._anhaenge_lesen)
        self.assertNotIn("budget_sekunden=0", quelle)
        self.assertNotIn("budget_dokumente=0", quelle)

    def test_abbruch_wirkt_auch_dort(self):
        import inspect

        from mailburg.ui.arbeit import Abruflauf

        self.assertIn("weiter=lambda: not self.abgebrochen",
                      inspect.getsource(Abruflauf._anhaenge_lesen))


class KernzahlTest(TexterkennungDialogTest):
    """Wer nebenher arbeitet, will nicht alle Kerne hergeben."""

    def test_voreinstellung_laesst_kerne_frei(self):
        import os

        from mailburg.core.erkennung import GLEICHZEITIG

        dialog = self._dialog(50)

        self.assertEqual(dialog.kerne.value(), GLEICHZEITIG)
        self.assertLess(GLEICHZEITIG, os.cpu_count() or 2,
                        "die Oberfläche braucht auch Rechenzeit")

    def test_bis_zur_vollen_ausschoepfung_waehlbar(self):
        import os

        dialog = self._dialog(50)

        self.assertEqual(dialog.kerne.maximum(), os.cpu_count() or 2)
        self.assertEqual(dialog.kerne.minimum(), 1)

    def test_die_wahl_kommt_beim_lauf_an(self):
        from mailburg.ui.texterkennung import Erkennungslauf

        auftrag = Erkennungslauf("/irgendwo", 3)

        self.assertEqual(auftrag.gleichzeitig, 3)

    def test_der_kern_nimmt_die_zahl_entgegen(self):
        import inspect

        from mailburg.core import erkennung

        self.assertIn("gleichzeitig",
                      inspect.signature(erkennung.durchlauf).parameters)


class FliesstextTest(OberflaechenTest):
    """Ein umbrechender Absatz muss dem Layout die *richtige* Höhe melden.

    Qt meldet sie nicht. Ein ``QLabel`` mit ``setWordWrap(True)`` gibt
    in ``minimumSizeHint()`` eine Höhe zurück, die für irgendeine
    angenommene Breite gilt – nicht für die tatsächliche. Solange nichts
    anderes um Platz konkurriert, fällt das nicht auf. Sobald ein
    Fortschrittsbalken dazukommt, nimmt sich das Layout den Platz beim
    Absatz, und dort steht eine Zeile weniger als geschrieben.
    """

    LANG = (
        "<p>Das sind Dokumente ohne Textebene – ein Foto einer Seite. Für "
        "die Suche sind sie bisher ein weißes Blatt: Der Dateiname ist zu "
        "finden, der Inhalt nicht.</p><p>Die Texterkennung liest sie und "
        "legt das Ergebnis in den Suchindex. Das Archiv selbst bleibt "
        "unangetastet – die PDF werden nicht verändert.</p>"
    )

    def _etikett(self, breite):
        from mailburg.ui.fliesstext import Fliesstext

        etikett = Fliesstext(self.LANG)
        etikett.resize(breite, 10)
        return etikett

    def test_schmaler_heisst_hoeher(self):
        schmal = self._etikett(300).minimumSizeHint().height()
        breit = self._etikett(900).minimumSizeHint().height()

        self.assertGreater(
            schmal, breit,
            "die gemeldete Höhe hängt gar nicht an der Breite",
        )

    def test_die_gemeldete_hoehe_reicht_fuer_den_text(self):
        for breite in (300, 500, 900):
            with self.subTest(breite=breite):
                etikett = self._etikett(breite)

                self.assertGreaterEqual(
                    etikett.minimumSizeHint().height(),
                    etikett.heightForWidth(breite),
                )

    def test_ein_gewoehnliches_qlabel_kann_das_nicht(self):
        """Der Beleg, dass die eigene Klasse nötig ist.

        Fiele dieser Test eines Tages um, weil Qt es selbst richtig
        macht, wäre ``Fliesstext`` entbehrlich – dann darf er weg.
        """
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLabel

        hoehen = []
        for breite in (300, 900):
            etikett = QLabel(self.LANG)
            etikett.setWordWrap(True)
            etikett.setTextFormat(Qt.RichText)
            etikett.resize(breite, 10)
            hoehen.append(etikett.minimumSizeHint().height())

        self.assertEqual(
            hoehen[0], hoehen[1],
            "Qt meldet die Höhe inzwischen breitenabhängig – "
            "Fliesstext wird nicht mehr gebraucht",
        )

    def test_vor_dem_anzeigen_wird_nicht_geraten(self):
        """Ohne Breite gibt es noch nichts zu rechnen – aber auch keine Null.

        Eine gemeldete Höhe von 0 wäre der schlimmste Fall: Das Layout
        gäbe dem Absatz gar keinen Platz, und beim ersten Anzeigen wäre
        das Fenster leer.
        """
        from mailburg.ui.fliesstext import Fliesstext

        etikett = Fliesstext(self.LANG)

        self.assertGreater(etikett.minimumSizeHint().height(), 0)


class SicherungseinheitTest(OberflaechenTest):
    """Geschrieben und eingeschaltet muss dieselbe Einheit sein.

    Die Sicherungsdatei entstand unter dem archiveigenen Namen, das
    Einschalten nannte die feste Sammelbezeichnung. systemd meldete
    daraufhin »Unit mailburg-sicherung.timer does not exist« – und der
    Zeitplan lag als Datei da, ohne je zu laufen. Der unangenehmste
    Fehler bei einer Sicherung: Sie sieht eingerichtet aus.
    """

    def test_eingeschaltet_wird_die_archiveigene_einheit(self):
        import subprocess
        import tempfile
        from unittest import mock

        from mailburg.core import zeitplan

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        wo = pathlib.Path(ordner.name)
        archiv = wo / "Privatarchiv"
        archiv.mkdir()
        (archiv / "archive.json").write_text("{}", encoding="utf-8")
        aufrufe = []

        def merken(*args, **kw):
            aufrufe.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")

        with mock.patch.object(zeitplan, "DIENSTE", wo / "systemd"), \
                mock.patch.object(zeitplan, "_systemctl", merken), \
                mock.patch.object(zeitplan, "moeglich", lambda: (True, "")):
            zeitplan.sicherung_einrichten(archiv, wo / "ziel")

            erwartet = f"{zeitplan._einheitsname(archiv)}.timer"
            self.assertTrue(
                (wo / "systemd" / erwartet).is_file(),
                "die Einheit wurde unter anderem Namen geschrieben",
            )
            self.assertIn(
                ("enable", "--now", erwartet), aufrufe,
                f"eingeschaltet wurde etwas anderes: {aufrufe}",
            )


class NeuesteZuerstTest(OberflaechenTest):
    """Beim Öffnen eines Archivs steht die jüngste Nachricht oben.

    Breiten und Reihenfolge der Spalten sind Geschmackssache und werden
    gemerkt – die Sortierung nicht. Wer einmal nach Absender sortiert
    hat, um etwas zu suchen, fände sonst Wochen später immer noch diese
    Ordnung vor und übersähe, dass neue Post angekommen ist.

    Und es gilt für jedes Archiv gleich: Wer zwischen geschäftlich und
    privat wechselt, soll nicht die Sortierung des anderen erben.
    """

    def setUp(self):
        import tempfile
        from unittest import mock

        from mailburg.core import paths

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        flicken = mock.patch.object(
            paths, "config_dir", lambda: pathlib.Path(self.ordner.name)
        )
        flicken.start()
        self.addCleanup(flicken.stop)

    def _fenster(self):
        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster

        ort = pathlib.Path(self.ordner.name) / "Archiv"
        if not (ort / "archive.json").exists():
            Archive.create(ort).close()
        fenster = Hauptfenster(ort)
        self.addCleanup(fenster.close)
        return fenster

    def test_die_voreinstellung_ist_datum_absteigend(self):
        from PySide6.QtCore import Qt

        from mailburg.ui.hauptfenster import SPALTE_DATUM

        kopf = self._fenster().tabelle.horizontalHeader()

        self.assertEqual(kopf.sortIndicatorSection(), SPALTE_DATUM)
        self.assertEqual(kopf.sortIndicatorOrder(), Qt.DescendingOrder)

    def test_eine_andere_sortierung_wird_zurueckgesetzt(self):
        """Genau der Fall, der im Alltag stört."""
        from PySide6.QtCore import Qt

        from mailburg.ui.hauptfenster import SPALTE_DATUM

        fenster = self._fenster()
        kopf = fenster.tabelle.horizontalHeader()
        kopf.setSortIndicator(2, Qt.AscendingOrder)  # nach Absender

        fenster._neueste_zuerst()

        self.assertEqual(kopf.sortIndicatorSection(), SPALTE_DATUM)
        self.assertEqual(kopf.sortIndicatorOrder(), Qt.DescendingOrder)

    def test_das_modell_sortiert_wirklich_mit(self):
        """Der Pfeil allein genügt nicht – die Liste muss sich drehen."""
        fenster = self._fenster()
        fenster.tabelle.model().sortierung = "absender"
        fenster.tabelle.model().absteigend = False

        fenster._neueste_zuerst()

        self.assertEqual(fenster.tabelle.model().sortierung, "datum")
        self.assertTrue(fenster.tabelle.model().absteigend)


class InfofensterTest(OberflaechenTest):
    """Wer das Programm gemacht hat – und wohin mit Fehlern und Ideen.

    Ein Archivprogramm bekommt man selten zu Gesicht; es läuft im
    Hintergrund, und man sucht darin, wenn etwas fehlt. Gerade dann will
    man wissen, wem man es anvertraut hat.
    """

    def _text(self):
        from mailburg.ui.info import text

        return text()

    def test_der_urheber_wird_genannt(self):
        text = self._text()

        self.assertIn("Stephan Rösner", text)
        self.assertIn("Claude", text)

    def test_beide_wege_zur_meldung_stehen_drin(self):
        from mailburg.ui.info import FEHLER_URL, KONTAKT

        text = self._text()

        self.assertIn(FEHLER_URL, text)
        self.assertIn(KONTAKT, text)
        # Als anklickbarer Verweis, nicht zum Abtippen. Wer einen Fehler
        # melden will, gibt nach dem dritten Zeichen auf.
        self.assertIn(f'href=\'mailto:{KONTAKT}\'', text)

    def test_die_fassung_steht_dabei(self):
        """Ohne sie ist eine Fehlermeldung halb so viel wert."""
        from mailburg import __version__

        self.assertIn(__version__, self._text())

    def test_die_verweise_sind_auch_im_dunklen_lesbar(self):
        """Qts Standardblau hat auf dunklem Grund ein Verhältnis von 2,4."""
        from mailburg.ui import farben

        self.assertIn(farben.link(), self._text())

    def test_das_fenster_baut_sich_auf(self):
        from mailburg.ui.info import Infofenster

        fenster = Infofenster()
        self.addCleanup(fenster.close)

        self.assertIn("Stephan Rösner", fenster.inhalt.text())
        self.assertTrue(fenster.inhalt.openExternalLinks())

    def test_der_menuepunkt_ist_da(self):
        """Sonst findet ihn niemand – ein Dialog ohne Weg dorthin."""
        import tempfile

        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ort = pathlib.Path(ordner.name) / "Archiv"
        Archive.create(ort).close()
        fenster = Hauptfenster(ort)
        self.addCleanup(fenster.close)

        hilfe = next(
            m for m in fenster.menuBar().actions() if "Hilfe" in m.text()
        )
        beschriftungen = [a.text() for a in hilfe.menu().actions()]

        self.assertIn("Info …", beschriftungen)


class BereichskantenTest(OberflaechenTest):
    """Das dunkle Thema hat kein Farbproblem, sondern ein Kantenproblem.

    Nachgemessen am 2026-08-27: Zwischen ``Window`` und ``Base`` – also
    zwischen Fensterhintergrund und Inhaltsbereich – liegt ein
    Kontrastverhältnis von 1,15. Das liest kein Auge als Grenze, in
    keinem Thema. Im hellen fällt es nicht auf, weil Gewohnheit und
    Bildschirmrand helfen; auf einem 14-Zoll-Gerät im Dunkeln fehlt
    beides, und die drei Bereiche verschwimmen zu einer Fläche.
    """

    def test_die_kantenfarbe_kommt_aus_der_palette(self):
        """Eigene Farben brächen Hochkontrast-Themen.

        Und träfen damit ausgerechnet die Anwender, für die solche
        Themen gemacht sind. ``Mid`` liefert jedes Thema mit – und jedes
        Hochkontrast-Thema setzt sie kräftig.
        """
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QApplication

        from mailburg.ui import farben

        erwartet = QApplication.instance().palette().color(QPalette.Mid)

        self.assertEqual(farben.kante(), erwartet.name())

    def test_das_stylesheet_faerbt_keine_flaechen_und_keine_schrift(self):
        """Alles andere bleibt beim Thema des Systems.

        Gesetzt werden ausschließlich Linien: Rahmen um die
        Inhaltsbereiche und die Farbe waagerechter Trennstriche. Bei
        einem ``QFrame`` mit ``HLine`` *ist* ``color`` die Linienfarbe –
        deshalb steht sie hier, und nur dort.

        Hintergründe oder Schriftfarben zu setzen wäre etwas anderes:
        Damit bräche man Hochkontrast-Themen und träfe ausgerechnet die
        Anwender, für die solche Themen gemacht sind.
        """
        from mailburg.ui import farben

        regel = farben.bereichsrahmen()

        self.assertIn("border", regel)
        for verboten in ("background", "font", "text-decoration"):
            with self.subTest(eigenschaft=verboten):
                self.assertNotIn(verboten, regel)

        # "color:" nur in der QFrame-Regel, nirgends sonst.
        fuer_flaechen = [
            zeile for zeile in regel.splitlines()
            if "color:" in zeile and "QFrame" not in zeile
        ]
        self.assertEqual(fuer_flaechen, [], "hier wird Schrift eingefärbt")

    def test_die_gruppen_der_einrichtung_bekommen_einen_rahmen(self):
        """Der erste Eindruck wiegt am schwersten.

        In der Ersteinrichtung entscheidet sich, ob jemand dem Programm
        seine Post anvertraut – und dort standen die Gruppen im dunklen
        Thema ohne sichtbare Grenze nebeneinander.
        """
        from mailburg.ui import farben

        self.assertIn("QGroupBox", farben.bereichsrahmen())

    def test_die_kanten_gelten_fuer_alle_fenster(self):
        """Nicht nur fürs Hauptfenster – sonst bliebe der Assistent kahl."""
        import inspect

        from mailburg.ui import app

        quelle = inspect.getsource(app.main)

        self.assertIn("setStyleSheet", quelle)
        self.assertIn("bereichsrahmen", quelle)

    def test_die_teiler_sind_zu_fassen(self):
        """Ein Teiler, den man nicht sieht, wird nicht gezogen."""
        import tempfile

        from PySide6.QtWidgets import QSplitter

        from mailburg.core.archive import Archive
        from mailburg.ui.hauptfenster import Hauptfenster

        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ort = pathlib.Path(ordner.name) / "Archiv"
        Archive.create(ort).close()
        fenster = Hauptfenster(ort)
        self.addCleanup(fenster.close)

        teiler = fenster.findChildren(QSplitter)
        self.assertTrue(teiler)
        for t in teiler:
            with self.subTest(teiler=t.objectName() or "unbenannt"):
                self.assertGreaterEqual(t.handleWidth(), 4)


class PlatzhalterTest(OberflaechenTest):
    """Platzhaltertexte im dunklen Thema lesbar halten.

    Qt setzt sie auf die Textfarbe mit halber Deckkraft. Auf hellem
    Grund geht das auf – Schwarz auf Weiß mit 50 % ergibt ein mittleres
    Grau. Auf dunklem nicht: Hellgrau auf Fast-Schwarz mit 50 % ergibt
    ein dunkles Grau, das im selben Dunkel verschwindet. Ausgerechnet
    der Hinweis, der beim ersten Öffnen erklärt, wofür das Feld da ist.
    """

    def _mit_thema(self, dunkel: bool):
        from PySide6.QtGui import QColor, QPalette
        from PySide6.QtWidgets import QApplication

        from mailburg.ui import farben

        app = QApplication.instance()
        vorher = QPalette(app.palette())
        self.addCleanup(app.setPalette, vorher)

        palette = QPalette(vorher)
        palette.setColor(QPalette.Window, QColor("#232629" if dunkel else "#efefef"))
        palette.setColor(QPalette.Text, QColor("#eff0f1" if dunkel else "#000000"))
        app.setPalette(palette)

        farben.platzhalter_aufhellen(app)
        return app.palette().color(QPalette.PlaceholderText)

    def test_im_dunklen_wird_aufgehellt(self):
        farbe = self._mit_thema(dunkel=True)

        # Deutlich über Qts halber Deckkraft, aber nicht voll: Ein
        # Platzhalter, der aussieht wie Inhalt, ist auch ein Fehler.
        self.assertGreater(farbe.alphaF(), 0.6)
        self.assertLess(farbe.alphaF(), 0.85)

    def test_im_hellen_bleibt_alles_wie_es_war(self):
        """Dort stimmt Qts Rechnung – ungefragt einzugreifen wäre falsch."""
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QApplication

        vorher = QApplication.instance().palette().color(QPalette.PlaceholderText)

        self.assertEqual(self._mit_thema(dunkel=False), vorher)

    def test_die_farbe_stammt_aus_dem_thema(self):
        """Ein fester Grauton säße bei Hochkontrast falsch."""
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QApplication

        farbe = self._mit_thema(dunkel=True)
        text = QApplication.instance().palette().color(QPalette.Text)

        self.assertEqual(farbe.rgb() & 0xFFFFFF, text.rgb() & 0xFFFFFF)


class OrdnerhinweisTest(OberflaechenTest):
    """Warum »Weiter« grau ist, muss dastehen.

    Das Archiv soll bewusst platziert werden, deshalb legt MailBurg
    keinen Ordner von sich aus an – wer zwanzig Jahre Post irgendwohin
    legt, soll diesen Ort ausgewählt haben. Nur sah man dem toten Knopf
    das nicht an: Im Feld stand ein Pfad, der Knopf blieb grau, und der
    naheliegende Schluss war »das Programm ist kaputt«.

    Am 2026-08-27 unter Windows aufgefallen, wo der vorgeschlagene
    Ordner regelmäßig noch nicht existiert.
    """

    def _seite(self):
        import tempfile

        from mailburg.ui.assistent import ArchivSeite

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        seite = ArchivSeite()
        self.addCleanup(seite.deleteLater)
        return seite

    def test_ein_fehlender_ordner_wird_benannt(self):
        seite = self._seite()

        seite.pfad.setText(str(pathlib.Path(self.ordner.name) / "gibtsnicht"))

        self.assertTrue(seite.ordnerhinweis.isVisibleTo(seite))
        text = seite.ordnerhinweis.text()
        self.assertIn("gibt es noch nicht", text)
        # Und der Weg dorthin, nicht nur die Feststellung.
        self.assertIn("Auswählen", text)

    def test_bei_einem_vorhandenen_ordner_schweigt_er(self):
        seite = self._seite()

        seite.pfad.setText(self.ordner.name)

        self.assertFalse(seite.ordnerhinweis.isVisibleTo(seite))

    def test_ein_leeres_feld_wird_nicht_bemaengelt(self):
        """Wer noch nichts eingetragen hat, macht nichts falsch."""
        seite = self._seite()

        seite.pfad.setText("")

        self.assertFalse(seite.ordnerhinweis.isVisibleTo(seite))


class AssistentZuordnungTest(OberflaechenTest):
    """Die Einrichtung muss die Postfächer dem Archiv zuordnen.

    Seit dem 2026-08-26 gehört jedes Postfach ausdrücklich in ein
    Archiv – sonst landet geschäftliche Post im Privatarchiv. Umgestellt
    wurden damals Abruf, Zeitplan und Hauptfenster; der
    Einrichtungsassistent nicht.

    Folge: Wer MailBurg neu einrichtete, hatte danach ein Postfach, das
    nirgends zugeordnet war, und stand vor der Meldung »Diesem Archiv
    ist kein Postfach zugeordnet«. Die Einrichtung führte in eine
    Sackgasse. Aufgefallen am 2026-08-27 beim ersten Windows-Durchlauf –
    wer neu einrichtet, merkt so etwas sofort; wer das Programm gebaut
    hat, nie.
    """

    def test_die_kennung_wird_gemerkt(self):
        """Die Kennung, nicht der Pfad – Platten wandern."""
        import inspect

        from mailburg.ui import assistent

        quelle = inspect.getsource(assistent)

        self.assertIn("archiv_kennung", quelle)
        self.assertIn("archiv.uuid", quelle)

    def test_beim_speichern_wird_zugeordnet(self):
        import inspect

        from mailburg.ui.assistent import KontenSeite

        quelle = inspect.getsource(KontenSeite._speichern)

        self.assertIn("zuordnen", quelle)
        self.assertIn("archiv_kennung", quelle)

    def test_nur_gewaehlte_postfaecher(self):
        """Wer ein Postfach abwählt, will es auch nicht zugeordnet haben."""
        import inspect

        from mailburg.ui.assistent import KontenSeite

        quelle = inspect.getsource(KontenSeite._speichern)
        # Die Zuordnung steht in einer Schleife, die auf die Auswahl
        # prüft - sonst bekäme auch ein abgewähltes Postfach sie.
        nach_kennung = quelle.split("archiv_kennung", 1)[1]
        self.assertIn("zeile.gewaehlt", nach_kennung)
        self.assertLess(
            nach_kennung.index("zeile.gewaehlt"),
            nach_kennung.index("zuordnen"),
            "zugeordnet wird, bevor die Auswahl geprüft ist",
        )


class KontenZuordnungTest(OberflaechenTest):
    """Die Meldung schickte an eine Stelle, an der es nichts gab.

    »Diesem Archiv ist kein Postfach zugeordnet … Zuordnen unter
    Einstellungen → Postfächer« – dort ließ sich aber gar nichts
    zuordnen. Eine Sackgasse mit Wegweiser, aufgefallen am 2026-08-28
    beim ersten Abruf aus der gepackten Windows-Fassung.
    """

    def _verwaltung(self):
        import tempfile
        from unittest import mock

        from mailburg.core import accounts, paths
        from mailburg.core.accounts import Konto, Kontenliste
        from mailburg.ui.konten import Kontenverwaltung

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        flicken = mock.patch.object(
            paths, "config_dir", lambda: pathlib.Path(self.ordner.name)
        )
        flicken.start()
        self.addCleanup(flicken.stop)
        # Kein Zugriff auf den echten Schlüsselbund im Test.
        holen = mock.patch.object(accounts, "passwort_holen", lambda k: "")
        holen.start()
        self.addCleanup(holen.stop)

        liste = Kontenliste(pathlib.Path(self.ordner.name) / "konten.json")
        liste.hinzufuegen(Konto(
            name="Privat", server="imap.example.com", benutzer="p@example.com"
        ))

        verwaltung = Kontenverwaltung()
        self.addCleanup(verwaltung.close)
        return verwaltung

    def test_es_gibt_einen_weg_zur_zuordnung(self):
        """Sonst führt die Meldung im Hauptfenster ins Leere."""
        verwaltung = self._verwaltung()

        self.assertTrue(hasattr(verwaltung, "zuordnen"))
        self.assertIn("Archiv", verwaltung.zuordnen.text())

    def test_die_spalte_zeigt_die_archive(self):
        verwaltung = self._verwaltung()

        kopf = [
            verwaltung.baum.headerItem().text(i)
            for i in range(verwaltung.baum.columnCount())
        ]

        self.assertIn("Archive", kopf)

    def test_ohne_zuordnung_steht_es_da(self):
        """Ein leeres Feld sähe aus wie »noch nicht geladen«."""
        verwaltung = self._verwaltung()
        konto = verwaltung.liste.finden("Privat")

        text = verwaltung._archivnamen(konto)

        self.assertIn("übergangen", text)

    def test_kennungen_werden_zu_namen(self):
        """»220b2cd0-f3b1-…« sagt niemandem etwas."""
        import json
        import tempfile
        from unittest import mock

        from mailburg.ui import konten

        with tempfile.TemporaryDirectory() as ordner:
            wo = pathlib.Path(ordner)
            (wo / "archive.json").write_text(
                json.dumps({"uuid": "abc-123", "name": "Privatarchiv"}),
                encoding="utf-8",
            )
            with mock.patch(
                "mailburg.core.einstellungen.zuletzt_benutzte_pfade", lambda: [str(wo)]
            ):
                from mailburg.core.archive import archivnamen

                name = archivnamen().get("abc-123", "abc-123"[:8] + "…")

        self.assertEqual(name, "Privatarchiv")

    def test_eine_unbekannte_kennung_bleibt_sichtbar(self):
        """Liegt die Platte gerade nicht an, wird nichts verschwiegen.

        Seit dem 2026-08-29 löst ``core.archive.archivnamen`` das an
        einer Stelle für beide Wege auf; was dort fehlt, bleibt als
        gekürzte Kennung stehen. Ein Archiv auf einer abgezogenen Platte
        hat trotzdem Postfächer.
        """
        from unittest import mock

        from mailburg.core.archive import archivnamen

        with mock.patch("mailburg.core.einstellungen.zuletzt_benutzte_pfade", lambda: []):
            kennung = "220b2cd0-f3b1-49ea"
            name = archivnamen().get(kennung, kennung[:8] + "…")

        self.assertTrue(name.startswith("220b2cd0"))


class RollbalkenTest(OberflaechenTest):
    """Wenn ein Text nicht auf die Seite passt, muss man das sehen.

    Auf 1280 × 800 – keine seltene Größe, viele ältere Notebooks haben
    sie – passt die Willkommensseite nicht auf einen Bildschirm. Qt
    blendet den Rollbalken dann zwar ein, aber so zurückhaltend, dass
    man ihn übersieht: Der Text wirkt zu Ende, und wer nicht scrollt,
    erfährt nie, dass MailBurg nichts nach Hause meldet und die
    Passwörter im Schlüsselbund liegen.

    Gekürzt wird der Text nicht – die Ausführlichkeit ist Absicht und
    Stephans ausdrückliche Vorgabe. Also muss sichtbar sein, dass es
    weitergeht (2026-08-28).
    """

    def _seiten_mit_rollbereich(self):
        from PySide6.QtWidgets import QScrollArea

        from mailburg.ui.assistent import ArchivSeite, WillkommenSeite

        gefunden = []
        for klasse in (WillkommenSeite, ArchivSeite):
            seite = klasse()
            self.addCleanup(seite.deleteLater)
            for bereich in seite.findChildren(QScrollArea):
                gefunden.append((klasse.__name__, bereich))
        return gefunden

    def test_der_rollbalken_bleibt_sichtbar(self):
        from PySide6.QtCore import Qt

        bereiche = self._seiten_mit_rollbereich()

        self.assertTrue(bereiche, "keine Rollbereiche gefunden")
        for name, bereich in bereiche:
            with self.subTest(seite=name):
                self.assertEqual(
                    bereich.verticalScrollBarPolicy(),
                    Qt.ScrollBarAlwaysOn,
                    "der Rollbalken versteckt sich – dann übersieht man ihn",
                )

    def test_waagerecht_wird_nicht_gerollt(self):
        """Ein Text, der zur Seite läuft, wäre ein Fehler im Umbruch."""
        from PySide6.QtCore import Qt

        for name, bereich in self._seiten_mit_rollbereich():
            with self.subTest(seite=name):
                self.assertNotEqual(
                    bereich.horizontalScrollBarPolicy(), Qt.ScrollBarAlwaysOn
                )


class KontozeileLayoutTest(OberflaechenTest):
    """Der freie Platz gehört nach unten, nicht zwischen die Zeilen.

    Ohne Dehnung am Ende verteilt QGridLayout ihn gleichmäßig auf alle
    Zeilen. Bei einem einzigen Postfach stand der Name dann oben und
    seine Beschreibung in der Mitte des Fensters, mit einer Handbreit
    Leere dazwischen – als hätte jemand vergessen, sie zusammenzurücken.
    """

    def test_unter_der_letzten_zeile_wird_gedehnt(self):
        from PySide6.QtWidgets import QGridLayout

        from mailburg.core.accounts import Konto
        from mailburg.ui.assistent import KontoZeile

        gitter = QGridLayout()
        KontoZeile(
            Konto(name="Privat", server="imap.example.org",
                  benutzer="post@example.org"),
            gitter, 0,
        )

        # Zeile 0 und 1 gehören dem Postfach, ab 2 kommt der Leerraum.
        self.assertEqual(gitter.rowStretch(0), 0)
        self.assertEqual(gitter.rowStretch(1), 0)
        self.assertGreater(gitter.rowStretch(2), 0)

    def test_bei_mehreren_postfaechern_ebenso(self):
        """Die Dehnung wandert mit – sonst klafft es wieder mittendrin."""
        from PySide6.QtWidgets import QGridLayout

        from mailburg.core.accounts import Konto
        from mailburg.ui.assistent import KontoZeile

        gitter = QGridLayout()
        for nr in range(3):
            KontoZeile(
                Konto(name=f"Konto {nr}", server="imap.example.org",
                      benutzer=f"post{nr}@example.org"),
                gitter, nr,
            )

        for zeile in range(6):
            with self.subTest(zeile=zeile):
                self.assertEqual(gitter.rowStretch(zeile), 0)
        self.assertGreater(gitter.rowStretch(6), 0)


class ErsterAbrufTest(OberflaechenTest):
    """Das Häkchen »Jetzt den ersten Abruf starten« muss auch greifen.

    Am 2026-08-28 unter Windows aufgefallen: Es stand angekreuzt auf der
    Abschlussseite, und nichts geschah – erst F5 holte die Post. Der
    Grund war, dass ``main`` den Assistenten zwar aufrief, sein
    ``soll_abrufen`` aber nie abfragte.

    Bitter daran: Über *Archiv → Neues Archiv* funktionierte es die ganze
    Zeit. Nur der Weg beim allerersten Start – der einzige, den ein neuer
    Anwender überhaupt geht – war der ungeprüfte.
    """

    def test_main_fragt_den_wunsch_ab(self):
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "ui" / "app.py"
        ).read_text(encoding="utf-8")

        self.assertIn("soll_abrufen", quelle)

    def test_der_abruf_wartet_auf_die_ereignisschleife(self):
        """Sonst hätte er kein Fenster, an dem seine Meldungen hängen."""
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "ui" / "app.py"
        ).read_text(encoding="utf-8")

        self.assertIn("QTimer.singleShot", quelle)
        # Und zwar nach dem Anzeigen des Fensters, nicht davor.
        self.assertLess(
            quelle.index("fenster.show()"),
            quelle.index("QTimer.singleShot"),
        )

    def test_beide_wege_benutzen_denselben_namen(self):
        """``soll_abrufen`` heißt an beiden Stellen gleich – sonst wieder still.

        ``getattr(..., False)`` verzeiht einen Tippfehler klaglos: Der
        Abruf bliebe aus, und niemand bekäme eine Fehlermeldung.
        """
        from mailburg.ui.assistent import Einrichtungsassistent

        assistent = Einrichtungsassistent()
        self.assertTrue(hasattr(assistent, "soll_abrufen"))
        # Frisch angelegt ist das Häkchen gesetzt.
        self.assertTrue(assistent.soll_abrufen)


class LeereKopfzeileTest(OberflaechenTest):
    """Ein leeres Label verschwindet nicht von selbst.

    Solange keine Nachricht gewählt war, klaffte zwischen Trefferliste
    und Vorschau ein Streifen von gut fünfzig Pixeln – die Zeilenhöhe
    und die Ränder der leeren Kopfzeile. Das sah aus, als sei das
    Fenster falsch aufgeteilt, und der erste Verdacht fiel prompt auf
    den Splitter.
    """

    def test_ohne_auswahl_bleibt_kein_loch(self):
        from mailburg.ui.vorschau import Mailvorschau

        vorschau = Mailvorschau()
        self.assertFalse(vorschau.kopf.isVisibleTo(vorschau))

    def test_mit_nachricht_steht_sie_wieder_da(self):
        from mailburg.ui.vorschau import Mailvorschau

        vorschau = Mailvorschau()
        vorschau._kopf_setzen("Von: post@example.org")
        self.assertTrue(vorschau.kopf.isVisibleTo(vorschau))
        self.assertIn("example.org", vorschau.kopf.text())

    def test_und_verschwindet_beim_leeren_wieder(self):
        from mailburg.ui.vorschau import Mailvorschau

        vorschau = Mailvorschau()
        vorschau._kopf_setzen("Von: post@example.org")
        vorschau.leeren()
        self.assertFalse(vorschau.kopf.isVisibleTo(vorschau))

    def test_der_text_wird_nur_an_einer_stelle_gesetzt(self):
        """Sonst vergisst die nächste Stelle das Ausblenden wieder."""
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "ui" / "vorschau.py"
        ).read_text(encoding="utf-8")

        # Einmal in _kopf_setzen selbst, sonst nirgends.
        self.assertEqual(quelle.count("self.kopf.setText("), 1)


class ArchivOhnePostfachTest(OberflaechenTest):
    """Ein Archiv nur zum Importieren muss anlegbar sein.

    »Ohne Postfach gibt es nichts zu archivieren« stimmt nicht: Wer ein
    Thunderbird-Profil oder eine Sicherung einlesen will, braucht keins.
    Bis zum 2026-08-29 kam er im Assistenten nicht weiter – aufgefallen,
    als für die Windows-Anleitung ein Beispielarchiv angelegt werden
    sollte.
    """

    def test_es_wird_gefragt_statt_verboten(self):
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "ui" / "assistent.py"
        ).read_text(encoding="utf-8")

        # Der Aufruf steht *vor* dem Titel, die Erklärung dahinter.
        mitte = quelle.index('"Kein Postfach gewählt"')
        stelle = quelle[mitte - 200:mitte + 800]

        self.assertIn("QMessageBox.question", stelle)
        self.assertIn("fortfahren?", stelle)

    def test_die_vorgabe_ist_nein(self):
        """Wer versehentlich keins gewählt hat, soll nicht durchrutschen."""
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "ui" / "assistent.py"
        ).read_text(encoding="utf-8")

        stelle = quelle[quelle.index('"Kein Postfach gewählt"'):]
        self.assertIn("QMessageBox.No,", stelle[:900])

    def test_der_weg_zurueck_steht_dabei(self):
        """Sonst hält man es für endgültig."""
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "ui" / "assistent.py"
        ).read_text(encoding="utf-8")

        stelle = quelle[quelle.index('"Kein Postfach gewählt"'):][:800]
        self.assertIn("nachtragen", stelle)


class OhnePruefungKnopfTest(OberflaechenTest):
    """»Ohne Prüfung übernehmen« erst nach einem Versuch.

    Solange »Übernehmen« ausgegraut ist, wäre er der einzige anklickbare
    Weg nach vorn – und damit läge der ungeprüfte Weg näher als der
    geprüfte. Stephan am 2026-08-29 unter Windows: »Ohne Prüfung
    durchkommen kommt jetzt schon, vor dem Verbindungstest.«

    Wer den Test nicht bestehen *kann* – ohne Netz, Brücke noch nicht
    gestartet –, drückt einmal auf »Verbindung testen«, sieht das
    Scheitern und bekommt ihn dann angeboten.
    """

    def _dialog(self):
        from mailburg.ui.assistent import KontoDialog

        dialog = KontoDialog()
        dialog.name.setText("Probe")
        dialog.server.setText("imap.example.org")
        dialog.benutzer.setText("post@example.org")
        self._offen = getattr(self, "_offen", [])
        self._offen.append(dialog)
        return dialog

    def test_er_ist_zu_beginn_nicht_da(self):
        """``isVisible`` ist ohne ``show`` immer falsch – geprüft wird
        die ausdrückliche Einstellung."""
        self.assertTrue(self._dialog().ungeprueft_knopf.isHidden())

    def test_nach_dem_scheitern_erscheint_er(self):
        dialog = self._dialog()
        dialog._misslungen("Diesen Servernamen gibt es nicht.")

        self.assertFalse(dialog.ungeprueft_knopf.isHidden())

    def test_eine_aenderung_verbirgt_ihn_wieder(self):
        """Wer den Servernamen ändert, hat einen neuen Versuch verdient."""
        dialog = self._dialog()
        dialog._misslungen("Fehler")
        dialog.server.setText("imap.example.net")

        self.assertTrue(dialog.ungeprueft_knopf.isHidden())

    def test_nach_erfolg_bleibt_er_fort(self):
        """Wer durchgekommen ist, braucht den Umweg nicht."""
        dialog = self._dialog()
        dialog._geglueckt(["INBOX", "Gesendet"])

        self.assertTrue(dialog.ungeprueft_knopf.isHidden())
        self.assertTrue(dialog.uebernehmen_knopf.isEnabled())


class PasswortAusDemDialogTest(OberflaechenTest):
    """Das im Dialog eingetippte Passwort muss in der Liste ankommen.

    **Wie daraus eine Sackgasse wurde.** Ohne diese Übernahme blieb das
    Feld in der Postfachliste leer. Beim Weitergehen kam »Für dieses
    Postfach fehlt noch das Passwort« mit den Knöpfen *Erneut versuchen*
    und *Dieses Postfach auslassen*. Wer auslassen wählte, bekam »Kein
    Postfach gewählt« und kam ebenfalls nicht weiter – und wer es
    ankreuzte, landete wieder bei der Passwortfrage.

    Am 2026-08-29 unter Windows gelandet, beim Anlegen eines
    Beispielarchivs für die Anleitung. Der Weg war seit vier Tagen so
    und niemandem aufgefallen, weil beim Durchspielen immer ein echtes
    Postfach mit echtem Passwort eingetragen wurde.
    """

    def _seite_mit_dialog(self, passwort: str):
        from unittest import mock

        from mailburg.core.accounts import Konto
        from mailburg.ui.assistent import KontenSeite, KontoDialog

        seite = KontenSeite()
        dialog = KontoDialog()
        dialog.name.setText("Beispiel")
        dialog.server.setText("imap.example.org")
        dialog.benutzer.setText("post@example.org")
        dialog.passwort.setText(passwort)

        self._offen = getattr(self, "_offen", [])
        self._offen += [seite, dialog]

        with mock.patch.object(KontoDialog, "exec", return_value=True):
            with mock.patch("mailburg.ui.assistent.KontoDialog",
                            return_value=dialog):
                seite._von_hand()
        return seite

    def test_es_kommt_in_der_zeile_an(self):
        seite = self._seite_mit_dialog("geheim")

        self.assertEqual(len(seite.zeilen), 1)
        self.assertEqual(seite.zeilen[0].passwort.text(), "geheim")

    def test_ohne_passwort_bleibt_das_feld_leer(self):
        """Wer keins eingibt, soll auch keins vorgesetzt bekommen."""
        seite = self._seite_mit_dialog("")

        self.assertEqual(seite.zeilen[0].passwort.text(), "")

    def test_die_zeile_wird_zurueckgegeben(self):
        """Sonst kann der Aufrufer nichts damit machen – genau daran lag es."""
        from mailburg.core.accounts import Konto
        from mailburg.ui.assistent import KontenSeite

        seite = KontenSeite()
        self._offen = getattr(self, "_offen", [])
        self._offen.append(seite)

        zeile = seite._zeile_anlegen(
            Konto(name="X", server="imap.example.org",
                  benutzer="post@example.org")
        )
        self.assertIsNotNone(zeile)
        self.assertTrue(hasattr(zeile, "passwort"))


class ZahlwortTest(OberflaechenTest):
    """»1 Mails im Archiv« stand in der Statuszeile.

    Ein winziger Fehler, aber einer, den jeder sofort sieht – und er
    stand ausgerechnet dort, wo ein neuer Anwender zum ersten Mal
    nachsieht, ob sein Archiv etwas enthält. Bei einem frisch
    angelegten Archiv mit einer Mail also immer.

    Am 2026-08-29 auf einem Windows-Bild für die Anleitung aufgefallen.
    """

    def test_einzahl_und_mehrzahl(self):
        from mailburg.core.sprache import mails

        self.assertEqual(mails(0), "0 Mails")
        self.assertEqual(mails(1), "1 Mail")
        self.assertEqual(mails(2), "2 Mails")

    def test_mit_tausenderpunkt(self):
        from mailburg.core.sprache import mails

        self.assertEqual(mails(16367), "16.367 Mails")

    def test_auch_die_unregelmaessigen(self):
        """»Datei« wird nicht zu »Dateis«."""
        from mailburg.core.sprache import dateien, nachrichten

        self.assertEqual(dateien(1), "1 Datei")
        self.assertEqual(dateien(3), "3 Dateien")
        self.assertEqual(nachrichten(1), "1 Nachricht")
        self.assertEqual(nachrichten(3), "3 Nachrichten")

    def test_die_statuszeile_benutzt_es(self):
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "ui" / "hauptfenster.py"
        ).read_text(encoding="utf-8")

        self.assertIn("from mailburg.core.sprache import mails", quelle)
        self.assertNotIn('} Mails im Archiv', quelle)

    def test_keine_scheinbare_fallunterscheidung(self):
        """Es stand einmal »Treffer« if … else »Treffer« da."""
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "ui" / "hauptfenster.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn('"Treffer" if', quelle)


class AbschlussSeiteTest(OberflaechenTest):
    """»Das Archiv liegt in None, 0 Postfächer sind eingerichtet«.

    So stand es auf einem Bild in der Anleitung – ein durchgereichtes
    Python-``None`` auf der letzten Seite des Assistenten, an der Stelle,
    an der ein Anwender nachliest, wo seine Post künftig liegt.

    ``archiv_pfad`` ist ausdrücklich ``Path | None``. Am 2026-08-29 beim
    Durchsehen der Bilder gefunden.
    """

    def _seite(self, pfad, konten):
        from mailburg.ui.assistent import AbschlussSeite, Einrichtungsassistent

        assistent = Einrichtungsassistent()
        assistent.archiv_pfad = pfad
        assistent.konten = konten
        seite = assistent.abschluss
        seite.initializePage()
        return seite.text.text()

    def test_ohne_pfad_kein_python(self):
        text = self._seite(None, [])

        self.assertNotIn("None", text)
        self.assertNotIn("Das Archiv liegt in", text)

    def test_mit_pfad_steht_der_pfad_da(self):
        text = self._seite(pathlib.Path("/home/martha/Mailarchiv"), [])

        self.assertIn("/home/martha/Mailarchiv", text)

    def test_ein_postfach_ist_kein_postfaecher(self):
        text = self._seite(pathlib.Path("/home/martha/Mailarchiv"), [object()])

        self.assertIn("1 Postfach ist eingerichtet", text)
        self.assertNotIn("1 Postfächer", text)

    def test_mehrere_postfaecher_sind(self):
        text = self._seite(
            pathlib.Path("/home/martha/Mailarchiv"), [object(), object()]
        )

        self.assertIn("2 Postfächer sind eingerichtet", text)

    def test_satzanfang_wird_gross_wenn_der_pfad_fehlt(self):
        """Ohne Pfad beginnt der Satz mit der Zahl – nicht mit »0 …« klein."""
        text = self._seite(None, [object()])

        self.assertIn("<p>1 Postfach ist eingerichtet", text)


class PfadanzeigeTest(OberflaechenTest):
    """»C:/Users/test/Documents« stand im Sicherungsdialog.

    Qt gibt Pfade immer mit Schrägstrich zurück, auch unter Windows.
    Wer dort über »Auswählen …« einen Ordner heraussuchte, bekam ihn in
    einer Schreibweise zu sehen, die Windows selbst nirgends verwendet.

    Von Stephan am 2026-08-29 in der Windows-VM entdeckt – und zwar
    dadurch, dass er den Ordner heraussuchte, statt ihn zu tippen.
    """

    def test_schraegstriche_werden_zu_dem_was_das_system_schreibt(self):
        from mailburg.ui.zeitplan import _wie_das_system_schreibt

        # Unter Linux bleibt der Schrägstrich – das ist hier die
        # richtige Antwort. Geprüft wird, dass überhaupt umgesetzt wird.
        self.assertEqual(
            _wie_das_system_schreibt("/home/martha/Sicherung"),
            str(pathlib.Path("/home/martha/Sicherung")),
        )

    def test_leerer_pfad_bleibt_leer(self):
        """Sonst stünde ein einzelner Punkt im Feld: str(Path("")) == "."."""
        from mailburg.ui.zeitplan import _wie_das_system_schreibt

        self.assertEqual(_wie_das_system_schreibt(""), "")
        self.assertEqual(_wie_das_system_schreibt(None), "")

    def test_windows_bekaeme_backslashes(self):
        """Was unter Windows herauskäme – hier über PureWindowsPath."""
        self.assertEqual(
            str(pathlib.PureWindowsPath("C:/Users/test/Documents")),
            r"C:\Users\test\Documents",
        )

    def test_das_feld_geht_durch_die_umsetzung(self):
        quelle = (
            pathlib.Path(__file__).resolve().parent.parent
            / "mailburg" / "ui" / "zeitplan.py"
        ).read_text(encoding="utf-8")

        # Beide Wege ins Feld: der gespeicherte Zustand und die Auswahl.
        self.assertIn(
            "QLineEdit(_wie_das_system_schreibt(stand.archiv))", quelle
        )
        self.assertIn(
            "self.ziel.setText(_wie_das_system_schreibt(gewaehlt))", quelle
        )


class OhneDatumTest(OberflaechenTest):
    """»Aus diesen Jahren: 2026 (12), ? (2)«.

    Das Fragezeichen stand für Mails, deren Datum sich nicht lesen ließ.
    Wer es sieht, weiß nicht, ob das Programm etwas nicht konnte oder ob
    es ein Jahr gibt, das so heißt.

    Am 2026-08-29 auf dem Bild `fristen.png` aufgefallen.
    """

    def _dialog(self, daten):
        from unittest.mock import MagicMock

        from mailburg.ui.fristen import Fristendialog

        dialog = Fristendialog.__new__(Fristendialog)
        dialog.treffer = [MagicMock(date=d) for d in daten]
        return dialog

    def test_ohne_datum_wird_ausgeschrieben(self):
        text = self._dialog(["2019-04-01", None, "2019-08-02"])._nach_jahr()

        self.assertIn("ohne Datum (1)", text)
        self.assertNotIn("?", text)

    def test_ohne_datum_steht_hinten(self):
        """Sonst sortierte es sich zwischen die Jahre."""
        text = self._dialog([None, "2019-04-01", "2021-01-01"])._nach_jahr()

        self.assertTrue(
            text.index("2019") < text.index("2021") < text.index("ohne Datum"),
            text,
        )

    def test_ohne_fund_bleibt_es_leer(self):
        self.assertEqual(self._dialog([])._nach_jahr(), "")

    def test_die_jahre_werden_gezaehlt(self):
        text = self._dialog(
            ["2019-04-01", "2019-08-02", "2021-01-01"]
        )._nach_jahr()

        self.assertIn("2019 (2)", text)
        self.assertIn("2021 (1)", text)


class SicherungsvorschlagTest(OberflaechenTest):
    """Das Häkchen setzen und sofort eine Fehlermeldung bekommen.

    So war es: »Das Archiv regelmäßig in eine Datei sichern« ankreuzen,
    auf Übernehmen – und dann »Bitte einen Ordner für die Sicherungen
    wählen«, für einen leeren Zustand, den der Dialog selbst hergestellt
    hatte. Am 2026-08-29 auf den Windows-Bildern zu sehen.
    """

    def _wahl(self, vorschlag):
        """Die Patches müssen über den ganzen Test laufen.

        Beim ersten Wurf endeten sie mit dem Konstruktor – das Ankreuzen
        danach fragte dann das echte System und schlug einen Ordner vor,
        den es auf dem Entwicklungsrechner tatsächlich gibt.
        """
        from unittest import mock

        from mailburg.core import zeitplan as kern
        from mailburg.ui import zeitplan as modul

        for patch in (
            mock.patch.object(
                modul.orte, "sicherungsort_vorschlagen",
                lambda archiv=None: vorschlag,
            ),
            mock.patch.object(
                kern, "sicherung_zustand",
                lambda archiv=None: kern.Zustand(moeglich=True),
            ),
        ):
            patch.start()
            self.addCleanup(patch.stop)

        return modul.Sicherungswahl(archiv="/home/martha/Mailarchiv")

    def test_ankreuzen_schlaegt_einen_ordner_vor(self):
        wahl = self._wahl(pathlib.Path("/media/martha/Platte/MailBurg-Sicherung"))
        self.assertEqual(wahl.ziel.text(), "")

        wahl.an.setChecked(True)

        self.assertEqual(
            wahl.ziel.text(),
            str(pathlib.Path("/media/martha/Platte/MailBurg-Sicherung")),
        )

    def test_eine_getroffene_wahl_wird_nicht_ueberschrieben(self):
        wahl = self._wahl(pathlib.Path("/media/martha/Platte/MailBurg-Sicherung"))
        wahl.ziel.setText("/home/martha/Woanders")

        wahl.an.setChecked(True)

        self.assertEqual(wahl.ziel.text(), "/home/martha/Woanders")

    def test_ohne_geeigneten_ort_bleibt_das_feld_leer(self):
        """Lieber nichts als ein Ordner neben dem Original."""
        wahl = self._wahl(None)

        wahl.an.setChecked(True)

        self.assertEqual(wahl.ziel.text(), "")

    def test_abkreuzen_loescht_nichts(self):
        wahl = self._wahl(pathlib.Path("/media/martha/Platte/MailBurg-Sicherung"))
        wahl.an.setChecked(True)
        vorher = wahl.ziel.text()

        wahl.an.setChecked(False)

        self.assertEqual(wahl.ziel.text(), vorher)


class SicherungszustandImDialogTest(OberflaechenTest):
    """Was eingerichtet ist, muss im Dialog stehen.

    Sonst überschreibt ein Übernehmen die eigene Einstellung – aus
    »monatlich mit zwei Ständen« würde wieder »täglich, dieselbe Datei«.
    """

    def _wahl(self, **stand):
        from unittest import mock

        from mailburg.core import zeitplan as kern
        from mailburg.ui import zeitplan as modul

        vorgesetzt = kern.Zustand(moeglich=True, laeuft=True, **stand)
        for patch in (
            mock.patch.object(
                kern, "sicherung_zustand", lambda archiv=None: vorgesetzt
            ),
            mock.patch.object(
                modul.orte, "sicherungsort_vorschlagen", lambda archiv=None: None
            ),
        ):
            patch.start()
            self.addCleanup(patch.stop)

        return modul.Sicherungswahl(archiv="/home/martha/Archiv")

    def test_monatlich_steht_auch_da(self):
        wahl = self._wahl(takt_sicherung="monatlich", behalten=2)

        self.assertEqual(wahl.takt.currentData(), "monatlich")
        self.assertEqual(wahl.behalten.currentData(), 2)

    def test_ersetzen_bleibt_ersetzen(self):
        wahl = self._wahl(takt_sicherung="täglich", behalten=0)

        self.assertEqual(wahl.behalten.currentData(), 0)

    def test_eine_zahl_ausserhalb_der_liste_kommt_hinzu(self):
        """Von Hand auf 4 gestellt: nicht stillschweigend auf 0 fallen."""
        wahl = self._wahl(takt_sicherung="täglich", behalten=4)

        self.assertEqual(wahl.behalten.currentData(), 4)
        self.assertIn("4", wahl.behalten.currentText())

    def test_ohne_eingerichteten_zeitplan_die_vorgabe(self):
        wahl = self._wahl()

        self.assertEqual(wahl.behalten.currentData(), 0)


class RegeldialogTest(OberflaechenTest):
    """Die Verwaltung der Einstufungsregeln.

    Der Kern dieser Ansicht ist die Reihenfolge: Es gilt die erste
    passende Regel. Wer das nicht sieht, legt eine Ausnahme an, die nie
    greift – deshalb sind die Regeln nummeriert und verschiebbar.
    """

    def _dialog(self, *regeln):
        from unittest import mock

        from mailburg.core.regeln import Regel, Regelwerk
        from mailburg.ui.regeln import Regeldialog

        archiv = mock.Mock()
        archiv.regeln = Regelwerk(list(regeln))
        return Regeldialog(archiv=archiv), archiv

    def _regel(self, muster="*@verein.example", feld="von"):
        from mailburg.core.regeln import Regel

        return Regel(feld=feld, muster=muster)

    def test_die_regeln_stehen_in_der_tabelle(self):
        dialog, _ = self._dialog(self._regel(), self._regel("INBOX/Privat", "ordner"))

        self.assertEqual(dialog.tabelle.rowCount(), 2)
        self.assertEqual(dialog.tabelle.item(0, 1).text(), "*@verein.example")
        self.assertEqual(dialog.tabelle.item(1, 1).text(), "INBOX/Privat")

    def test_eine_regel_anlegen(self):
        dialog, _ = self._dialog()
        dialog.muster.setText("*@familie.example")

        dialog._anlegen()

        self.assertEqual(len(dialog.werk), 1)
        self.assertEqual(dialog.werk.regeln[0].muster, "*@familie.example")
        self.assertEqual(dialog.muster.text(), "", "Feld sollte leer sein")

    def test_ohne_muster_wird_nichts_angelegt(self):
        from unittest import mock

        dialog, _ = self._dialog()
        dialog.muster.setText("   ")

        with mock.patch(
            "mailburg.ui.regeln.QMessageBox.information"
        ) as gemeldet:
            dialog._anlegen()

        gemeldet.assert_called_once()
        self.assertEqual(len(dialog.werk), 0)

    def test_nach_oben_schieben(self):
        """Eine Ausnahme muss vor die allgemeinere Regel."""
        dialog, _ = self._dialog(
            self._regel("*@verein.example"),
            self._regel("kasse@verein.example"),
        )
        dialog.tabelle.setCurrentCell(1, 0)

        dialog._schieben(-1)

        self.assertEqual(dialog.werk.regeln[0].muster, "kasse@verein.example")
        self.assertEqual(dialog.tabelle.currentRow(), 0)

    def test_am_rand_wird_nicht_geschoben(self):
        dialog, _ = self._dialog(self._regel())
        dialog.tabelle.setCurrentCell(0, 0)

        dialog._schieben(-1)

        self.assertEqual(len(dialog.werk), 1)

    def test_die_knoepfe_richten_sich_nach_der_auswahl(self):
        dialog, _ = self._dialog(self._regel("a*"), self._regel("b*"))

        dialog.tabelle.setCurrentCell(0, 0)
        self.assertFalse(dialog.hoch.isEnabled(), "oben gibt es kein Höher")
        self.assertTrue(dialog.runter.isEnabled())

        dialog.tabelle.setCurrentCell(1, 0)
        self.assertTrue(dialog.hoch.isEnabled())
        self.assertFalse(dialog.runter.isEnabled())

    def test_entfernen_fragt_nach(self):
        from unittest import mock

        from PySide6.QtWidgets import QMessageBox

        dialog, _ = self._dialog(self._regel())
        dialog.tabelle.setCurrentCell(0, 0)

        with mock.patch(
            "mailburg.ui.regeln.QMessageBox.question",
            return_value=QMessageBox.No,
        ):
            dialog._entfernen()

        self.assertEqual(len(dialog.werk), 1, "Nein muss Nein heißen")

    def test_speichern_reicht_die_regeln_durch(self):
        dialog, archiv = self._dialog(self._regel())

        dialog._speichern()

        archiv.regeln_setzen.assert_called_once_with(dialog.werk)

    def test_unbestimmt_steht_nicht_zur_wahl(self):
        """Eine Regel, die nichts entscheidet, ist keine Regel."""
        dialog, _ = self._dialog()

        # Category ist ein StrEnum – Qt gibt die Werte als Zeichenkette
        # zurück, nicht als Aufzählungsglied.
        stufen = [
            str(dialog.stufe.itemData(i))
            for i in range(dialog.stufe.count())
        ]

        self.assertNotIn("unbestimmt", stufen)
        self.assertIn("privat", stufen)
