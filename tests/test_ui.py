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
