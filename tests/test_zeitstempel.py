"""Zeitstempel nach RFC 3161.

**Geprüft wird gegen ``openssl``, nicht gegen die eigenen Annahmen.**
Das ist hier der Punkt: Eine selbstgebaute ASN.1-Kodierung, die nur der
eigene Leser versteht, sieht richtig aus und ist wertlos – der Stempel
soll ja gerade von einem Fremden ausgestellt und von einem Fremden
geprüft werden.

Wo ``openssl`` fehlt, werden diese Tests übersprungen. Der Rest prüft,
was ohne es geht: die Kodierung, das Lesen einer Antwort und das
Verhalten, wenn ein Dienst ablehnt oder nicht antwortet.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from datetime import timezone
from pathlib import Path

from mailburg.core import der, zeitstempel
from mailburg.core.zeitstempel import ZeitstempelFehler

HAT_OPENSSL = shutil.which("openssl") is not None


def _tsa_aufsetzen(ordner: Path) -> None:
    """Eine kleine Zeitstempelstelle aus Bordmitteln von openssl."""
    def lauf(*befehl: str) -> None:
        ergebnis = subprocess.run(
            befehl, cwd=ordner, capture_output=True, text=True
        )
        if ergebnis.returncode != 0:  # pragma: no cover
            raise RuntimeError(f"{befehl}: {ergebnis.stderr[:400]}")

    lauf("openssl", "req", "-x509", "-newkey", "rsa:2048", "-keyout",
         "ca.key", "-out", "ca.pem", "-days", "2", "-nodes",
         "-subj", "/CN=Test-CA")
    lauf("openssl", "req", "-newkey", "rsa:2048", "-keyout", "tsa.key",
         "-out", "tsa.csr", "-nodes", "-subj", "/CN=Test-TSA")
    (ordner / "ext.cnf").write_text(
        "extendedKeyUsage=critical,timeStamping\n", encoding="ascii"
    )
    lauf("openssl", "x509", "-req", "-in", "tsa.csr", "-CA", "ca.pem",
         "-CAkey", "ca.key", "-out", "tsa.pem", "-days", "2",
         "-extfile", "ext.cnf", "-CAcreateserial")

    (ordner / "tsa.cnf").write_text(
        "[tsa]\ndefault_tsa = tsa_config\n[tsa_config]\n"
        "serial = ./serial\ncrypto_device = builtin\n"
        "signer_cert = ./tsa.pem\ncerts = ./ca.pem\nsigner_key = ./tsa.key\n"
        "signer_digest = sha256\ndefault_policy = 1.2.3.4.1\n"
        "digests = sha256, sha512\naccuracy = secs:1\nordering = yes\n"
        "tsa_name = yes\ness_cert_id_chain = no\ness_cert_id_alg = sha256\n",
        encoding="ascii",
    )
    (ordner / "serial").write_text("01\n", encoding="ascii")


def _stempeln(ordner: Path, anfrage: bytes) -> bytes:
    """Lässt die Test-TSA eine Anfrage beantworten."""
    (ordner / "req.tsq").write_bytes(anfrage)
    ergebnis = subprocess.run(
        ["openssl", "ts", "-reply", "-config", "tsa.cnf",
         "-queryfile", "req.tsq", "-out", "resp.tsr"],
        cwd=ordner, capture_output=True, text=True,
    )
    if ergebnis.returncode != 0:  # pragma: no cover
        raise RuntimeError(ergebnis.stderr[:400])
    return (ordner / "resp.tsr").read_bytes()


class DerTest(unittest.TestCase):
    """Die Kodierung für sich – ohne sie ist alles Weitere sinnlos."""

    def test_kurze_und_lange_laengen(self):
        kurz = der.wert(der.OCTETSTRING, b"x" * 10)
        lang = der.wert(der.OCTETSTRING, b"x" * 300)

        self.assertEqual(kurz[1], 10)
        # 0x82 heißt: zwei Längenbytes folgen.
        self.assertEqual(lang[1], 0x82)
        self.assertEqual(int.from_bytes(lang[2:4], "big"), 300)

    def test_hin_und_zurueck(self):
        roh = der.folge(der.ganzzahl(1), der.oktette(b"abc"))

        element = der.lesen(roh)
        teile = element.teile()

        self.assertEqual(teile[0].als_zahl(), 1)
        self.assertEqual(teile[1].inhalt, b"abc")

    def test_grosse_zahlen_bekommen_ihr_nullbyte(self):
        """Sonst gälte jede zweite Nonce als negativ.

        DER schreibt Zahlen mit Vorzeichen: Ein erstes Byte ab 0x80 wäre
        negativ. Eine Nonce ist Zufall, das trifft also die Hälfte aller
        Fälle – und die Anfrage wäre kaputt.
        """
        roh = der.ganzzahl(0xFF)

        self.assertEqual(roh, bytes([der.INTEGER, 2, 0x00, 0xFF]))
        self.assertEqual(der.lesen(roh).als_zahl(), 0xFF)

    def test_null_ist_ein_byte(self):
        self.assertEqual(der.lesen(der.ganzzahl(0)).als_zahl(), 0)

    def test_objektbezeichner(self):
        """SHA-256, nachgerechnet: 2.16.840.1.101.3.4.2.1."""
        roh = der.oid("2.16.840.1.101.3.4.2.1")

        self.assertEqual(
            roh, bytes.fromhex("0609608648016503040201")
        )

    def test_abgeschnittenes_wird_gemeldet_statt_geraten(self):
        roh = der.wert(der.OCTETSTRING, b"x" * 10)

        with self.assertRaises(der.DerFehler):
            der.lesen(roh[:-3])

    def test_suchen_geht_in_die_tiefe(self):
        innen = der.oktette(b"gefunden")
        aussen = der.folge(der.folge(der.ganzzahl(1), innen))

        treffer = der.suchen(aussen, der.OCTETSTRING)

        self.assertIsNotNone(treffer)
        self.assertEqual(treffer.inhalt, b"gefunden")


class AnfrageTest(unittest.TestCase):
    def test_sie_traegt_hash_und_nonce(self):
        roh, nonce = zeitstempel.anfrage(b"\x01" * 32, nonce=42)

        teile = der.lesen(roh).teile()
        self.assertEqual(teile[0].als_zahl(), 1)  # version
        self.assertEqual(teile[2].als_zahl(), 42)

    def test_ohne_vorgabe_ist_die_nonce_zufall(self):
        werte = {zeitstempel.anfrage(b"\x01" * 32)[1] for _ in range(20)}

        self.assertEqual(len(werte), 20)

    def test_ein_falsch_langer_hash_wird_abgewiesen(self):
        """Ein SHA-1 hätte 20 Byte – der Dienst wüsste nicht, was gilt."""
        with self.assertRaises(ZeitstempelFehler):
            zeitstempel.anfrage(b"\x01" * 20)


@unittest.skipUnless(HAT_OPENSSL, "openssl fehlt")
class GegenOpensslTest(unittest.TestCase):
    """Der eigentliche Beweis: Ein Fremder versteht, was wir schreiben."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.ordner = Path(cls._tmp.name)
        _tsa_aufsetzen(cls.ordner)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_openssl_liest_unsere_anfrage(self):
        roh, nonce = zeitstempel.anfrage(b"\x02" * 32, nonce=0x8899AABBCCDDEEFF)
        (self.ordner / "lesbar.tsq").write_bytes(roh)

        ergebnis = subprocess.run(
            ["openssl", "ts", "-query", "-in", "lesbar.tsq", "-text"],
            cwd=self.ordner, capture_output=True, text=True,
        )

        self.assertEqual(ergebnis.returncode, 0, ergebnis.stderr)
        self.assertIn("sha256", ergebnis.stdout)
        self.assertIn("8899AABBCCDDEEFF", ergebnis.stdout.upper())

    def test_wir_lesen_was_openssl_schreibt(self):
        digest = b"\x03" * 32
        roh, nonce = zeitstempel.anfrage(digest)

        antwort = _stempeln(self.ordner, roh)
        zeitstempel._status_lesen(antwort)
        token = zeitstempel._token(antwort)
        befund = zeitstempel.pruefen(token, digest)

        self.assertTrue(befund.passt)
        self.assertIsNotNone(befund.zeit)
        self.assertEqual(befund.zeit.tzinfo, timezone.utc)
        self.assertEqual(befund.nonce, nonce)

    def test_ein_stempel_fuer_etwas_anderes_faellt_durch(self):
        """Die eine Frage, die MailBurg selbst beantworten kann."""
        roh, _ = zeitstempel.anfrage(b"\x04" * 32)
        token = zeitstempel._token(_stempeln(self.ordner, roh))

        befund = zeitstempel.pruefen(token, b"\x05" * 32)

        self.assertFalse(befund.passt)

    def test_openssl_prueft_was_wir_ablegen(self):
        """Der Weg aus der Anleitung, Schritt für Schritt nachgegangen.

        Das ist der Test, auf den es ankommt: Ein Stempel, den nur
        MailBurg lesen kann, wäre vor Gericht wertlos.
        """
        stand = "a" * 64
        digest = zeitstempel.digest_fuer(stand)
        roh, _ = zeitstempel.anfrage(digest)
        token = zeitstempel._token(_stempeln(self.ordner, roh))

        # Genau so, wie »mailburg siegel --ausgeben« es herausschreibt.
        (self.ordner / "stand.txt").write_bytes(stand.encode("ascii"))
        (self.ordner / "stempel.tst").write_bytes(token)

        ergebnis = subprocess.run(
            ["openssl", "ts", "-verify", "-data", "stand.txt",
             "-in", "stempel.tst", "-token_in",
             "-CAfile", "ca.pem", "-untrusted", "tsa.pem"],
            cwd=self.ordner, capture_output=True, text=True,
        )

        self.assertIn("Verification: OK", ergebnis.stdout + ergebnis.stderr)


class AblehnungTest(unittest.TestCase):
    """Was ein Dienst antwortet, wenn er nicht mitspielt."""

    def _abgelehnt(self, status: int, text: str = "") -> bytes:
        felder = [der.ganzzahl(status)]
        if text:
            felder.append(
                der.wert(der.SEQUENCE, der.wert(der.UTF8STRING, text.encode()))
            )
        return der.folge(der.folge(*felder))

    def test_eine_ablehnung_wird_zum_fehler(self):
        with self.assertRaises(ZeitstempelFehler) as gefangen:
            zeitstempel._status_lesen(self._abgelehnt(2))

        self.assertIn("abgelehnt", str(gefangen.exception))

    def test_der_grund_steht_in_der_meldung(self):
        """»Status 2« hilft niemandem weiter."""
        with self.assertRaises(ZeitstempelFehler) as gefangen:
            zeitstempel._status_lesen(
                self._abgelehnt(2, "Verfahren nicht unterstuetzt")
            )

        self.assertIn("Verfahren nicht unterstuetzt", str(gefangen.exception))

    def test_granted_und_granted_with_mods_gehen_durch(self):
        for status in (0, 1):
            with self.subTest(status=status):
                zeitstempel._status_lesen(self._abgelehnt(status))

    def test_ohne_token_ist_es_kein_stempel(self):
        with self.assertRaises(ZeitstempelFehler):
            zeitstempel._token(self._abgelehnt(0))


class UnerreichbarTest(unittest.TestCase):
    def test_die_meldung_beruhigt_wegen_des_archivs(self):
        """Wer keinen Stempel bekommt, soll nicht ums Archiv fürchten."""
        # Port 9 ist »discard« und nimmt keine Verbindungen an.
        with self.assertRaises(ZeitstempelFehler) as gefangen:
            zeitstempel.holen(b"\x01" * 32, "http://127.0.0.1:9/", zeitgrenze=2)

        text = str(gefangen.exception)
        self.assertIn("nicht erreichbar", text)
        self.assertIn("Siegel selbst ist davon nicht betroffen", text)


class UnlesbaresTokenTest(unittest.TestCase):
    def test_es_gilt_nicht_als_falsch_sondern_als_ungeprueft(self):
        """Ein Aufbau, den MailBurg nicht kennt, ist noch kein Fehler."""
        befund = zeitstempel.pruefen(b"kein DER", b"\x01" * 32)

        self.assertFalse(befund.passt)
        self.assertIn("openssl", befund.hinweis)


class GestempeltWirdTest(unittest.TestCase):
    def test_der_stand_wird_als_text_gehasht(self):
        """Damit von außen nachrechenbar ist, was gestempelt wurde."""
        import hashlib

        stand = "b" * 64

        self.assertEqual(
            zeitstempel.digest_fuer(stand),
            hashlib.sha256(stand.encode("ascii")).digest(),
        )


if __name__ == "__main__":
    unittest.main()
