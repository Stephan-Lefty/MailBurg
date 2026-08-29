"""Anmeldung per OAuth2.

**Warum das sein muss.** Microsoft hat die Anmeldung mit Passwort
abgeschaltet – Exchange Online am 1. Oktober 2022, private Konten am
16. September 2024. Auch App-Kennwörter wirken dort nicht mehr; ohne
OAuth2 kann MailBurg Microsoft-Postfächer überhaupt nicht abrufen.

**Was hier nicht geprüft werden kann.** Ob echte Anbieter die Anfragen
so annehmen, wie MailBurg sie stellt. Dafür bräuchte es ein Konto bei
Microsoft oder Google und eine registrierte Anwendung. Geprüft wird
deshalb gegen einen nachgebauten Anbieter, der auf dem eigenen Rechner
läuft – und gegen die Rechenvorschriften, die in den Normen stehen:
PKCE nach RFC 7636, das XOAUTH2-Format nach der Beschreibung beider
Anbieter.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import threading
import time
import unittest
import urllib.parse
import urllib.request

from mailburg.core import oauth2


class PkceTest(unittest.TestCase):
    """Der Ersatz für ein Geheimnis, das ein Desktop-Programm nicht hat.

    Ein Programm auf fremden Rechnern kann nichts geheim halten – wer
    die Datei hat, hat auch das Geheimnis. Statt eines dauerhaften wird
    für jede Anmeldung ein neuer Zufallswert erzeugt und vorab nur sein
    Fingerabdruck geschickt.
    """

    def test_der_fingerabdruck_folgt_der_norm(self) -> None:
        """RFC 7636: SHA-256, base64url, ohne Auffüllzeichen."""
        pruefer = oauth2.Pruefer()

        roh = hashlib.sha256(pruefer.verifizierer.encode("ascii")).digest()
        erwartet = base64.urlsafe_b64encode(roh).decode("ascii").rstrip("=")

        self.assertEqual(pruefer.fingerabdruck, erwartet)
        self.assertNotIn("=", pruefer.fingerabdruck)

    def test_die_laenge_liegt_im_erlaubten_bereich(self) -> None:
        """RFC 7636 verlangt 43 bis 128 Zeichen."""
        for _ in range(20):
            laenge = len(oauth2.Pruefer().verifizierer)
            self.assertGreaterEqual(laenge, 43)
            self.assertLessEqual(laenge, 128)

    def test_jede_anmeldung_bekommt_einen_eigenen(self) -> None:
        werte = {oauth2.Pruefer().verifizierer for _ in range(50)}
        self.assertEqual(len(werte), 50)


class AdresseTest(unittest.TestCase):
    def _felder(self, anbieter) -> dict:
        adresse = oauth2.anmeldeadresse(
            anbieter, "kennung", "http://localhost:1234",
            oauth2.Pruefer(), "zustand",
        )
        return {
            k: v[0] for k, v in
            urllib.parse.parse_qs(urllib.parse.urlparse(adresse).query).items()
        }

    def test_pkce_steht_drin(self) -> None:
        felder = self._felder(oauth2.MICROSOFT)

        self.assertEqual(felder["code_challenge_method"], "S256")
        self.assertTrue(felder["code_challenge"])

    def test_kein_geheimnis_in_der_adresse(self) -> None:
        """Öffentlicher Client: Es gibt keins, also darf keins auftauchen."""
        felder = self._felder(oauth2.MICROSOFT)
        self.assertNotIn("client_secret", felder)

    def test_microsoft_bittet_um_erneuerung(self) -> None:
        """Ohne offline_access müsste man sich stündlich neu anmelden."""
        self.assertIn("offline_access", self._felder(oauth2.MICROSOFT)["scope"])

    def test_google_braucht_zwei_zusaetze(self) -> None:
        """Sonst gibt Google beim zweiten Mal kein Erneuerungs-Token mehr.

        Und dann stünde der Zeitplan nach einer Stunde still.
        """
        felder = self._felder(oauth2.GOOGLE)

        self.assertEqual(felder["access_type"], "offline")
        self.assertEqual(felder["prompt"], "consent")


class TokenTest(unittest.TestCase):
    def test_mit_vorlauf_erneuern(self) -> None:
        """Nicht erst beim Ablauf: Dazwischen liegt der Verbindungsaufbau.

        Ein Abruf, der mitten im Lauf an einem abgelaufenen Token
        scheitert, ist ärgerlicher als eine Erneuerung, die eine Minute
        zu früh kam.
        """
        jetzt = time.time()
        token = oauth2.Token(zugriff="x", gueltig_bis=jetzt + 3600)

        self.assertFalse(token.abgelaufen(jetzt))
        self.assertTrue(token.abgelaufen(jetzt + 3600 - oauth2.VORLAUF + 1))

    def test_hin_und_zurueck(self) -> None:
        token = oauth2.Token("zugriff", "erneuerung", 123.5)
        wieder = oauth2.Token.aus_json(token.als_json())

        self.assertEqual(wieder.zugriff, "zugriff")
        self.assertEqual(wieder.erneuerung, "erneuerung")
        self.assertEqual(wieder.gueltig_bis, 123.5)

    def test_verhunztes_bleibt_folgenlos(self) -> None:
        """Ein kaputter Eintrag im Schlüsselbund darf nichts aufhalten."""
        for unsinn in ("", "{", "null", '{"foo": 1}'):
            with self.subTest(inhalt=unsinn):
                self.assertIsNone(oauth2.Token.aus_json(unsinn))


class XoauthFormatTest(unittest.TestCase):
    """Das Format steht in der Beschreibung beider Anbieter.

    Die Steuerzeichen gehören dazu, sie sind keine Zierde – und ein
    fehlendes davon führt zu einer Ablehnung, die den Grund nicht nennt.
    """

    def test_der_satz_stimmt(self) -> None:
        satz = oauth2.xoauth2_zeichenkette("post@example.org", "TOKEN")
        self.assertEqual(satz, "user=post@example.org\x01auth=Bearer TOKEN\x01\x01")


class FehlerTest(unittest.TestCase):
    """Die Kennungen der Anbieter sind für Menschen unbrauchbar.

    »invalid_grant« ist die häufigste und sagt nichts. Sie heißt fast
    immer, dass die gespeicherte Anmeldung nicht mehr gilt.
    """

    def test_invalid_grant_wird_erklaert(self) -> None:
        text = oauth2._verstaendlich('{"error":"invalid_grant"}', 400)

        self.assertIn("gilt nicht mehr", text)
        self.assertIn("neu an", text)

    def test_und_der_haeufigste_grund_dafuer(self) -> None:
        """Sieben Tage im Google-Testmodus – das trifft jeden Zeitplan."""
        text = oauth2._verstaendlich('{"error":"invalid_grant"}', 400)
        self.assertIn("sieben Tage", text)

    def test_falsches_umleitungsziel(self) -> None:
        text = oauth2._verstaendlich('{"error":"redirect_uri_mismatch"}', 400)
        self.assertIn("localhost", text)

    def test_unbekanntes_wird_durchgereicht(self) -> None:
        """Eine unbekannte Meldung im Original schlägt eine erfundene."""
        text = oauth2._verstaendlich('{"error":"gibtsnicht"}', 418)
        self.assertIn("gibtsnicht", text)


class _Tokendienst(http.server.BaseHTTPRequestHandler):
    """Ein Anbieter zum Nachspielen."""

    empfangen: dict = {}
    antwort: dict = {}

    def do_POST(self) -> None:  # noqa: N802
        laenge = int(self.headers["Content-Length"])
        felder = urllib.parse.parse_qs(self.rfile.read(laenge).decode())
        type(self).empfangen = {k: v[0] for k, v in felder.items()}
        roh = json.dumps(type(self).antwort).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def log_message(self, *_args) -> None:
        pass


class AblaufTest(unittest.TestCase):
    """Der ganze Weg, gegen einen nachgebauten Anbieter.

    Weiter reicht die Prüfung ohne echtes Konto nicht – aber sie zeigt,
    dass MailBurg die Anfragen so stellt, wie die Normen es vorsehen.
    """

    def setUp(self) -> None:
        _Tokendienst.antwort = {
            "access_token": "zugriff",
            "refresh_token": "erneuerung",
            "expires_in": 3600,
        }
        self.dienst = http.server.HTTPServer(("127.0.0.1", 0), _Tokendienst)
        threading.Thread(target=self.dienst.serve_forever, daemon=True).start()
        self.addCleanup(self.dienst.shutdown)

        self.anbieter = oauth2.Anbieter(
            kennung="probe", name="Probe",
            autorisierung="http://127.0.0.1:1/auth",
            token=f"http://127.0.0.1:{self.dienst.server_address[1]}/token",
            bereich="test",
        )

    def _browser_ersatz(self, code="der-code", zustand=None):
        """Statt eines Browsers ruft der »Anbieter« die Umleitung auf."""
        def oeffnen(adresse):
            felder = urllib.parse.parse_qs(
                urllib.parse.urlparse(adresse).query
            )
            ziel = felder["redirect_uri"][0]
            echt = zustand if zustand is not None else felder["state"][0]
            oeffnen.fingerabdruck = felder["code_challenge"][0]

            def spaeter():
                time.sleep(0.15)
                try:
                    urllib.request.urlopen(
                        f"{ziel}/?code={code}&state={echt}", timeout=5
                    ).read()
                except Exception:  # noqa: BLE001
                    pass

            threading.Thread(target=spaeter, daemon=True).start()
        return oeffnen

    def test_die_anmeldung_laeuft_durch(self) -> None:
        from mailburg.core.oauth2_anmelden import anmelden

        token = anmelden(
            self.anbieter, "kennung",
            oeffnen=self._browser_ersatz(), wartezeit=10,
        )

        self.assertEqual(token.zugriff, "zugriff")
        self.assertEqual(token.erneuerung, "erneuerung")
        self.assertGreater(token.gueltig_bis, time.time())

    def test_der_verifizierer_passt_zum_fingerabdruck(self) -> None:
        """Der Kern von PKCE: Wer die Umleitung abfängt, kann nichts damit
        anfangen – ihm fehlt das Geheimnis dieses einen Vorgangs."""
        from mailburg.core.oauth2_anmelden import anmelden

        oeffnen = self._browser_ersatz()
        anmelden(self.anbieter, "kennung", oeffnen=oeffnen, wartezeit=10)

        verifizierer = _Tokendienst.empfangen["code_verifier"]
        roh = hashlib.sha256(verifizierer.encode()).digest()
        gerechnet = base64.urlsafe_b64encode(roh).decode().rstrip("=")

        self.assertEqual(gerechnet, oeffnen.fingerabdruck)

    def test_eine_fremde_antwort_wird_abgewiesen(self) -> None:
        """Der ``state``-Wert schützt vor eingeschleusten Anfragen.

        Wer von außen einen Code unterschieben wollte, müsste den
        Zufallswert kennen, den nur dieser Vorgang kennt.
        """
        from mailburg.core.oauth2_anmelden import anmelden

        with self.assertRaises(oauth2.OAuthFehler) as fehler:
            anmelden(
                self.anbieter, "kennung",
                oeffnen=self._browser_ersatz(zustand="fremder-wert"),
                wartezeit=10,
            )

        self.assertIn("nicht zu dieser Anmeldung", str(fehler.exception))

    def test_erneuern_behaelt_das_alte_erneuerungstoken(self) -> None:
        """Google gibt bei der Erneuerung keins heraus – ginge das alte
        dabei verloren, müsste man sich stündlich neu anmelden."""
        _Tokendienst.antwort = {"access_token": "frisch", "expires_in": 3600}

        alt = oauth2.Token("alt", "das-alte", 0)
        neu = oauth2.erneuern(self.anbieter, "kennung", alt)

        self.assertEqual(neu.zugriff, "frisch")
        self.assertEqual(neu.erneuerung, "das-alte")

    def test_ohne_erneuerungstoken_kommt_eine_klare_ansage(self) -> None:
        with self.assertRaises(oauth2.OAuthFehler) as fehler:
            oauth2.erneuern(self.anbieter, "kennung", oauth2.Token("nur-zugriff"))

        self.assertIn("neu an", str(fehler.exception))


class LauschstelleTest(unittest.TestCase):
    """Gelauscht wird nur auf dem eigenen Rechner."""

    def test_nur_localhost(self) -> None:
        quelle = (
            __import__("pathlib").Path(__file__).resolve().parent.parent
            / "mailburg" / "core" / "oauth2_anmelden.py"
        ).read_text(encoding="utf-8")

        self.assertIn('("127.0.0.1", anschluss)', quelle)
        self.assertNotIn('("0.0.0.0"', quelle)

    def test_der_anschluss_wird_gesucht_nicht_geraten(self) -> None:
        """Ein fester wäre auf manchem Rechner belegt – und die Anmeldung
        scheiterte mit einer Meldung, die den Grund nicht nennt."""
        from mailburg.core.oauth2_anmelden import freier_anschluss

        self.assertNotEqual(freier_anschluss(), freier_anschluss())


class KontoTest(unittest.TestCase):
    """Was am Postfach hängt."""

    def test_ohne_anbieter_bleibt_es_beim_passwort(self) -> None:
        from mailburg.core.accounts import Konto

        konto = Konto(name="A", server="imap.example.org",
                      benutzer="post@example.org")
        self.assertFalse(konto.per_oauth2)

    def test_mit_anbieter_nicht(self) -> None:
        from mailburg.core.accounts import Konto

        konto = Konto(name="A", server="outlook.office365.com",
                      benutzer="post@example.org",
                      oauth_anbieter="microsoft", oauth_kennung="abc")
        self.assertTrue(konto.per_oauth2)

    def test_token_und_passwort_liegen_getrennt(self) -> None:
        """Ein Postfach kann die Anmeldeart wechseln – dann sollen sich
        die beiden Einträge nicht überschreiben."""
        from mailburg.core.accounts import Konto

        konto = Konto(name="A", server="imap.example.org",
                      benutzer="post@example.org")
        self.assertNotEqual(konto.schluessel, konto.token_schluessel)


if __name__ == "__main__":
    unittest.main()
