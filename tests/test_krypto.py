"""Die Schlüssel eines verschlüsselten Archivs.

Hier hängt mehr dran als anderswo: Ein Fehler in diesem Modul ist nicht
ein falsches Ergebnis, sondern ein Archiv, das niemand mehr aufbekommt.
Deshalb steht hier auch das, was selbstverständlich aussieht.
"""

from __future__ import annotations

import json
import unittest
import unittest.mock

from mailburg.core import krypto
from mailburg.core.krypto import FalschesPasswort, Huelle, KryptoFehler

try:
    import cryptography  # noqa: F401

    HAT_KRYPTO = True
except ImportError:  # pragma: no cover – der Kern kommt ohne aus
    HAT_KRYPTO = False



def _huelle(passwort: str = "sehr geheim"):
    """Legt eine Hülle mit kleinen Kennwerten an – Tests sollen schnell sein.

    Die echten Werte (2^17) brauchen je Ableitung ein Zehntel einer
    Sekunde und 134 MB. Bei achtzig Tests wäre das eine Minute Wartezeit
    für nichts: Geprüft wird hier die Mechanik, nicht die Härte.
    """
    original = krypto.SCRYPT_N
    krypto.SCRYPT_N = 2 ** 8
    try:
        return Huelle.anlegen(passwort)
    finally:
        krypto.SCRYPT_N = original


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class NotschluesselTest(unittest.TestCase):
    """Er wird ausgedruckt und abgetippt – daran hängt die Form."""

    def test_die_form_ist_zum_abschreiben(self):
        wert = krypto.notschluessel_erzeugen()

        self.assertEqual(len(wert.split("-")), 8)
        for gruppe in wert.split("-"):
            self.assertEqual(len(gruppe), 4)

    def test_keine_verwechselbaren_zeichen(self):
        """I, O, 0 und 1 sind auf Papier nicht zu unterscheiden."""
        for _ in range(50):
            wert = krypto.notschluessel_erzeugen().replace("-", "")
            for verboten in "IO01":
                self.assertNotIn(verboten, wert)

    def test_zweimal_erzeugt_ist_zweimal_verschieden(self):
        werte = {krypto.notschluessel_erzeugen() for _ in range(100)}
        self.assertEqual(len(werte), 100)

    def test_beim_abtippen_ist_die_form_egal(self):
        """Wer von einem Zettel abschreibt, soll nicht an Bindestrichen scheitern."""
        wert = krypto.notschluessel_erzeugen()
        erwartet = krypto.notschluessel_lesen(wert)

        for variante in (
            wert.lower(),
            wert.replace("-", ""),
            wert.replace("-", " "),
            f"  {wert}\n",
            wert.replace("-", "").lower(),
        ):
            with self.subTest(variante=variante):
                self.assertEqual(krypto.notschluessel_lesen(variante), erwartet)

    def test_was_keiner_ist_wird_auch_nicht_dafuer_gehalten(self):
        for eingabe in ("", "geheim", "ABCD-EFGH", "A" * 33, "ABC0-" + "A" * 27):
            with self.subTest(eingabe=eingabe):
                self.assertIsNone(krypto.notschluessel_lesen(eingabe))


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class HuelleTest(unittest.TestCase):
    def test_beide_wege_fuehren_zum_selben_schluessel(self):
        huelle, schluessel, notschluessel = _huelle()

        self.assertEqual(huelle.oeffnen("sehr geheim").archiv, schluessel.archiv)
        self.assertEqual(huelle.oeffnen(notschluessel).archiv, schluessel.archiv)

    def test_ein_falsches_passwort_wirft_seinen_eigenen_fehler(self):
        """Der Aufrufer muss »nochmal fragen« von »kaputt« unterscheiden können."""
        huelle, _, _ = _huelle()

        with self.assertRaises(FalschesPasswort):
            huelle.oeffnen("daneben")

    def test_die_meldung_erinnert_an_den_notschluessel(self):
        """In dem Moment, in dem man ihn braucht, hat man ihn vergessen."""
        huelle, _, _ = _huelle()

        with self.assertRaises(FalschesPasswort) as gefangen:
            huelle.oeffnen("daneben")

        text = str(gefangen.exception)
        self.assertIn("Notschlüssel", text)
        # Und die Wahrheit, die niemand gern hört.
        self.assertIn("auch der Hersteller nicht", text)

    def test_kein_schluessel_steht_im_klartext_auf_der_platte(self):
        """Das Wichtigste überhaupt an dieser Datei."""
        huelle, schluessel, notschluessel = _huelle()
        geschrieben = json.dumps(huelle.als_json())

        self.assertNotIn(schluessel.archiv.hex(), geschrieben)
        self.assertNotIn(notschluessel, geschrieben)
        self.assertNotIn("sehr geheim", geschrieben)

    def test_ueber_json_und_zurueck(self):
        huelle, schluessel, _ = _huelle()

        wieder = Huelle.aus_json(json.loads(json.dumps(huelle.als_json())))

        self.assertEqual(wieder.oeffnen("sehr geheim").archiv, schluessel.archiv)

    def test_die_kennwerte_stehen_in_der_datei_nicht_im_programm(self):
        """Sonst ließe sich der Aufwand nie erhöhen, ohne alte Archive auszusperren."""
        huelle, schluessel, _ = _huelle()
        daten = huelle.als_json()

        # Ein Programm mit anderen Vorgabewerten muss dasselbe Archiv öffnen.
        original = krypto.SCRYPT_N
        krypto.SCRYPT_N = 2 ** 20
        try:
            wieder = Huelle.aus_json(daten)
            self.assertEqual(wieder.oeffnen("sehr geheim").archiv, schluessel.archiv)
        finally:
            krypto.SCRYPT_N = original

    def test_kaputte_angaben_sagen_was_zu_tun_ist(self):
        with self.assertRaises(KryptoFehler) as gefangen:
            Huelle.aus_json({"huellen": {}})

        self.assertIn("Sicherung", str(gefangen.exception))


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class PasswortWechselTest(unittest.TestCase):
    def test_das_neue_gilt_und_das_alte_nicht_mehr(self):
        huelle, schluessel, _ = _huelle("altes")

        neue = huelle.passwort_wechseln(schluessel, "neues")

        self.assertEqual(neue.oeffnen("neues").archiv, schluessel.archiv)
        with self.assertRaises(FalschesPasswort):
            neue.oeffnen("altes")

    def test_der_notschluessel_ueberlebt_den_wechsel(self):
        """Er hängt an einer eigenen Hülle und weiß vom Passwort nichts."""
        huelle, schluessel, notschluessel = _huelle("altes")

        neue = huelle.passwort_wechseln(schluessel, "neues")

        self.assertEqual(neue.oeffnen(notschluessel).archiv, schluessel.archiv)

    def test_der_archivschluessel_bleibt_derselbe(self):
        """Sonst müsste ein Passwortwechsel 700.000 Dateien neu schreiben."""
        huelle, schluessel, _ = _huelle("altes")

        neue = huelle.passwort_wechseln(schluessel, "neues")

        self.assertEqual(neue.oeffnen("neues").archiv, schluessel.archiv)

    def test_ein_neues_salz_bei_jedem_wechsel(self):
        huelle, schluessel, _ = _huelle("altes")

        neue = huelle.passwort_wechseln(schluessel, "neues")

        self.assertNotEqual(neue.salz, huelle.salz)


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class InhaltTest(unittest.TestCase):
    def test_hin_und_zurueck(self):
        _, schluessel, _ = _huelle()

        paket = schluessel.verschluesseln(b"Betreff: Rechnung")

        self.assertEqual(schluessel.entschluesseln(paket), b"Betreff: Rechnung")

    def test_der_klartext_steht_nicht_im_paket(self):
        _, schluessel, _ = _huelle()

        paket = schluessel.verschluesseln(b"Betreff: Rechnung")

        self.assertNotIn(b"Rechnung", paket)

    def test_zweimal_dasselbe_ergibt_zweierlei(self):
        """Sonst verriete schon die Gleichheit zweier Dateien ihren Inhalt."""
        _, schluessel, _ = _huelle()

        eins = schluessel.verschluesseln(b"gleich")
        zwei = schluessel.verschluesseln(b"gleich")

        self.assertNotEqual(eins, zwei)
        self.assertEqual(schluessel.entschluesseln(eins), b"gleich")
        self.assertEqual(schluessel.entschluesseln(zwei), b"gleich")

    def test_ein_veraendertes_byte_faellt_auf(self):
        """Kein stiller Datenverlust – das ist der Sinn von GCM."""
        _, schluessel, _ = _huelle()
        paket = bytearray(schluessel.verschluesseln(b"Betreff: Rechnung"))
        paket[-1] ^= 0x01

        with self.assertRaises(KryptoFehler):
            schluessel.entschluesseln(bytes(paket))

    def test_ein_fremdes_archiv_kommt_nicht_heran(self):
        _, meiner, _ = _huelle()
        _, fremder, _ = _huelle()

        paket = meiner.verschluesseln(b"geheim")

        with self.assertRaises(KryptoFehler):
            fremder.entschluesseln(paket)

    def test_die_bindung_verhindert_vertauschte_dateien(self):
        """Zwei Mails zu tauschen soll auffallen, nicht später Verwirrung stiften."""
        _, schluessel, _ = _huelle()

        paket = schluessel.verschluesseln(b"Mail A", bindung=b"a" * 64)

        self.assertEqual(schluessel.entschluesseln(paket, bindung=b"a" * 64), b"Mail A")
        with self.assertRaises(KryptoFehler):
            schluessel.entschluesseln(paket, bindung=b"b" * 64)

    def test_zu_kurzes_wird_nicht_als_paket_gelesen(self):
        _, schluessel, _ = _huelle()

        with self.assertRaises(KryptoFehler):
            schluessel.entschluesseln(b"kurz")


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class DateinamenTest(unittest.TestCase):
    def test_der_name_verraet_den_hash_nicht(self):
        """Sonst wäre die Frage »liegt diese Mail hier?« beantwortet."""
        _, schluessel, _ = _huelle()
        digest = "a" * 64

        self.assertNotEqual(schluessel.dateiname(digest), digest)

    def test_die_form_bleibt_dieselbe(self):
        """64 Hexzeichen – damit die Ablage ihre Struktur behält."""
        _, schluessel, _ = _huelle()

        name = schluessel.dateiname("a" * 64)

        self.assertEqual(len(name), 64)
        self.assertTrue(all(zeichen in "0123456789abcdef" for zeichen in name))

    def test_derselbe_hash_ergibt_immer_denselben_namen(self):
        """Sonst fände niemand seine Mails wieder."""
        _, schluessel, _ = _huelle()

        self.assertEqual(
            schluessel.dateiname("a" * 64), schluessel.dateiname("a" * 64)
        )

    def test_zwei_archive_benennen_dieselbe_mail_verschieden(self):
        """Der Name hängt am Schlüssel, nicht nur am Inhalt."""
        _, eins, _ = _huelle()
        _, zwei, _ = _huelle()

        self.assertNotEqual(eins.dateiname("a" * 64), zwei.dateiname("a" * 64))


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class SchluesseltrennungTest(unittest.TestCase):
    """Ein Schlüssel, eine Aufgabe."""

    def test_inhalt_und_namen_sind_verschieden(self):
        _, schluessel, _ = _huelle()

        self.assertNotEqual(schluessel.inhalt, schluessel.namen)

    def test_keiner_von_beiden_ist_der_archivschluessel(self):
        _, schluessel, _ = _huelle()

        self.assertNotEqual(schluessel.inhalt, schluessel.archiv)
        self.assertNotEqual(schluessel.namen, schluessel.archiv)


class OhneDasPaketTest(unittest.TestCase):
    """Der Kern muss ohne ``cryptography`` laufen – das ist eine Zusage.

    Nicht mit ``skipUnless`` versehen: Dieser Test gilt gerade dann,
    wenn das Paket fehlt, und muss auch dann etwas Sinnvolles prüfen,
    wenn es da ist.
    """

    def test_die_meldung_sagt_was_zu_installieren_ist(self):
        import builtins

        echt = builtins.__import__

        def ohne(name, *rest):
            if name.startswith("cryptography"):
                raise ImportError("nicht da")
            return echt(name, *rest)

        with unittest.mock.patch.object(builtins, "__import__", ohne):
            with self.assertRaises(KryptoFehler) as gefangen:
                krypto._aesgcm()

        text = str(gefangen.exception)
        self.assertIn("mailburg[verschluesselung]", text)
        # Und der Satz, auf den es ankommt.
        self.assertIn("Ihre Mails sind davon nicht betroffen", text)

    def test_ein_unverschluesseltes_archiv_merkt_nichts_davon(self):
        """Der häufige Fall darf nie an einem fehlenden Paket scheitern."""
        import builtins
        import tempfile
        from pathlib import Path
        from unittest import mock as _mock

        from mailburg.core import paths
        from mailburg.core.archive import Archive

        echt = builtins.__import__

        def ohne(name, *rest):
            if name.startswith("cryptography"):
                raise ImportError("nicht da")
            return echt(name, *rest)

        with tempfile.TemporaryDirectory() as ordner:
            basis = Path(ordner)
            with _mock.patch.object(paths, "data_dir", return_value=basis / "d"):
                (basis / "d").mkdir()
                with _mock.patch.object(builtins, "__import__", ohne):
                    with Archive.create(basis / "a", name="Offen") as archiv:
                        archiv.add(
                            b"From: a@example.org\r\nSubject: Test\r\n\r\nHallo\r\n",
                            account="privat", folder="INBOX",
                        )
                        archiv.index.commit()
                        self.assertEqual(archiv.index.count(), 1)


@unittest.skipUnless(HAT_KRYPTO, "cryptography fehlt")
class EhrlichkeitTest(unittest.TestCase):
    def test_der_hinweis_nennt_den_suchindex_beim_namen(self):
        """Eine Verschlüsselung, die eine offene Flanke hat, muss sie nennen."""
        text = krypto.hinweis_suchindex()

        self.assertIn("Suchindex", text)
        self.assertIn("Klartext", text)
        # Und sagen, was man dagegen tun kann.
        self.assertIn("verschlüsselt die Platte", text)

    def test_der_hinweis_auf_das_neue_steht_wo_man_sich_entscheidet(self):
        """Nicht nur im README – dort liest ihn niemand vor dem Klick.

        Zu streichen, sobald jemand mit der Verschlüsselung im Alltag
        gearbeitet hat. Dann muss dieser Test mitgehen; ein Hinweis, der
        stehen bleibt, nachdem er nicht mehr stimmt, ist schlimmer als
        keiner.
        """
        from pathlib import Path

        wurzel = Path(__file__).resolve().parent.parent

        # Entweder wörtlich oder über ``hinweis_neu()`` – Hauptsache, er
        # kommt an der Stelle an, an der geklickt wird.
        for datei in (
            "mailburg/ui/assistent.py",
            "mailburg/ui/archivpasswort.py",
            "mailburg/__main__.py",
            "mailburg/ui/hilfe.py",
            "docs/verschluesselung.md",
        ):
            quelle = (wurzel / datei).read_text(encoding="utf-8")
            with self.subTest(datei=datei):
                self.assertTrue(
                    "noch nicht erprobt" in quelle or "hinweis_neu" in quelle,
                    f"{datei} sagt nicht, dass die Verschlüsselung neu ist",
                )


if __name__ == "__main__":
    unittest.main()
