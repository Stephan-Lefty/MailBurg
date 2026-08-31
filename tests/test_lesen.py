"""Der lesende Zugriff über den Browser.

Zwei Menschen, ein Archiv, verschiedene Rechte – und die Frage, ob sich
das über HTTP genauso hält wie im Kern. Geprüft wird deshalb wieder
vor allem, was **nicht** geht: eine fremde Nachricht über ihre Kennung,
eine Trefferzahl, die zu viel verspricht, eine Sitzung, die ein
entzogenes Recht überdauert.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mailburg.core.archive import Archive, Mode
from mailburg.core.benutzer import Benutzer
from mailburg.server.einstellungen import Serverlage

try:
    import starlette  # noqa: F401

    HAT_STARLETTE = True
except ImportError:  # pragma: no cover
    HAT_STARLETTE = False


class Kunde:
    """Ein schlanker Browser für die Tests.

    **Warum nicht starlettes TestClient.** Der verlangt httpx – eine
    Testabhängigkeit, die nur für diese Tests im Repo läge und in jeder
    CI mitinstalliert werden müsste. ASGI ist ein überschaubares
    Protokoll: ein Wörterbuch hinein, ein paar Nachrichten heraus. Das
    lohnt keine Bibliothek.

    Kann, was hier gebraucht wird: GET, POST mit Formulardaten, Cookies
    behalten, Weiterleitungen *nicht* verfolgen (die sind hier oft das
    Ergebnis, das geprüft wird).
    """

    def __init__(self, anwendung):
        self.anwendung = anwendung
        self.kekse: dict[str, str] = {}

    def get(self, pfad: str):
        return self._ruf("GET", pfad, b"")

    def post(self, pfad: str, felder: dict[str, str]):
        from urllib.parse import urlencode

        return self._ruf(
            "POST", pfad, urlencode(felder).encode("utf-8"),
            {"content-type": "application/x-www-form-urlencoded"},
        )

    def _ruf(self, art: str, pfad: str, koerper: bytes, zusatz=None):
        import asyncio
        from http.cookies import SimpleCookie
        from urllib.parse import urlsplit

        teile = urlsplit(pfad)
        kopfzeilen = [(b"host", b"testserver")]
        if self.kekse:
            keks = "; ".join(f"{k}={v}" for k, v in self.kekse.items())
            kopfzeilen.append((b"cookie", keks.encode("latin-1")))
        for name, wert in (zusatz or {}).items():
            kopfzeilen.append((name.encode(), wert.encode()))

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": art, "scheme": "http", "path": teile.path,
            "raw_path": teile.path.encode(), "query_string": teile.query.encode(),
            "root_path": "", "headers": kopfzeilen,
            "client": ("127.0.0.1", 1234), "server": ("testserver", 80),
        }

        gesendet: list[dict] = []

        async def empfangen():
            return {"type": "http.request", "body": koerper, "more_body": False}

        async def senden(nachricht):
            gesendet.append(nachricht)

        asyncio.run(self.anwendung(scope, empfangen, senden))

        anfang = next(n for n in gesendet if n["type"] == "http.response.start")
        rumpf = b"".join(
            n.get("body", b"") for n in gesendet
            if n["type"] == "http.response.body"
        )
        kopf = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in anfang["headers"]
        }

        # Cookies merken - auch das Löschen beim Abmelden.
        for k, v in anfang["headers"]:
            if k.decode("latin-1").lower() == "set-cookie":
                gebacken = SimpleCookie()
                gebacken.load(v.decode("latin-1"))
                for name, stueck in gebacken.items():
                    if stueck.value:
                        self.kekse[name] = stueck.value
                    else:
                        self.kekse.pop(name, None)

        return Antwort(anfang["status"], kopf, rumpf)


class Antwort:
    def __init__(self, status: int, kopf: dict[str, str], rumpf: bytes):
        self.status_code = status
        self.headers = kopf
        self.content = rumpf

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")

    def json(self):
        import json

        return json.loads(self.content)


def _mail(betreff: str) -> bytes:
    return (
        f"From: Wer Auch Immer <wer@example.org>\r\n"
        f"To: martha@mailburg.example\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: Mon, 12 May 2025 09:14:00 +0000\r\n"
        f"Message-ID: <{abs(hash(betreff))}@example.org>\r\n"
        f"\r\n"
        f"Der Text von {betreff}.\r\n"
    ).encode()


@unittest.skipUnless(HAT_STARLETTE, "starlette fehlt")
class WebTest(unittest.TestCase):
    """Ein Archiv mit zwei Postfächern und zwei Zugängen."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name) / "Archiv"

        with Archive.create(self.wo, name="Probe", mode=Mode.GESCHAEFTLICH) as a:
            for betreff in ("Rechnung Mai", "Rechnung Juni"):
                a.add(_mail(betreff), account="buchhaltung", folder="INBOX")
            a.add(_mail("Vertraulich"), account="chefsache", folder="INBOX")

            liste = a.benutzer
            chef = Benutzer("chef", verwalter=True, alle_postfaecher=True)
            chef.passwort_setzen("ein-langes-passwort")
            anna = Benutzer("anna", anzeigename="Anna Feldmann",
                            postfaecher=["buchhaltung"])
            anna.passwort_setzen("ein-anderes-langes")
            liste.hinzufuegen(chef)
            liste.hinzufuegen(anna)
            a.benutzer_setzen(liste, actor="chef")

        from mailburg.server.dienst import anwendung

        self.anwendung = anwendung(Serverlage(archiv=self.wo))

    def _als(self, name: str, passwort: str) -> Kunde:
        kunde = Kunde(self.anwendung)
        antwort = kunde.post(
            "/anmelden", {"name": name, "passwort": passwort})
        self.assertEqual(antwort.status_code, 303, "Anmeldung fehlgeschlagen")
        return kunde

    def _kennungen(self, kunde: Kunde, ausdruck: str = "") -> list[str]:
        import re

        seite = kunde.get(f"/?q={ausdruck}").text
        return re.findall(r'/nachricht/([a-f0-9]{64})"', seite)

    # -- Anmeldung ---------------------------------------------------------

    def test_ohne_anmeldung_geht_es_zur_anmeldung(self):
        kunde = Kunde(self.anwendung)

        for adresse in ("/", "/nachricht/egal", "/nachricht/egal/datei"):
            with self.subTest(adresse=adresse):
                antwort = kunde.get(adresse)
                self.assertEqual(antwort.status_code, 303)
                self.assertEqual(antwort.headers["location"], "/anmelden")

    def test_falsches_passwort(self):
        kunde = Kunde(self.anwendung)

        antwort = kunde.post(
            "/anmelden", {"name": "anna", "passwort": "daneben"})

        self.assertEqual(antwort.status_code, 401)

    def test_die_fehlermeldung_verraet_nicht_ob_es_den_namen_gibt(self):
        """Sonst ließe sich die Liste der Anmeldenamen abfragen."""
        kunde = Kunde(self.anwendung)

        bekannt = kunde.post(
            "/anmelden", {"name": "anna", "passwort": "daneben"})
        unbekannt = kunde.post(
            "/anmelden", {"name": "niemand", "passwort": "daneben"})

        self.assertEqual(bekannt.status_code, unbekannt.status_code)
        self.assertEqual(bekannt.text, unbekannt.text)

    def test_zu_viele_fehlversuche_werden_gebremst(self):
        kunde = Kunde(self.anwendung)

        for _ in range(6):
            antwort = kunde.post(
                "/anmelden", {"name": "anna", "passwort": "daneben"})

        self.assertEqual(antwort.status_code, 429)

    def test_das_sitzungscookie_ist_gegen_javascript_geschuetzt(self):
        kunde = Kunde(self.anwendung)
        antwort = kunde.post(
            "/anmelden", {"name": "anna", "passwort": "ein-anderes-langes"})

        keks = antwort.headers["set-cookie"].lower()
        # HttpOnly: kein Zugriff aus JavaScript. SameSite: wird bei
        # Anfragen von fremden Seiten nicht mitgeschickt.
        self.assertIn("httponly", keks)
        self.assertIn("samesite=lax", keks)

    def test_abmelden_nimmt_das_cookie_zurueck(self):
        kunde = self._als("anna", "ein-anderes-langes")

        kunde.get("/abmelden")

        antwort = kunde.get("/")
        self.assertEqual(antwort.status_code, 303)

    # -- Was jeder sieht ---------------------------------------------------

    def test_zwei_anmeldungen_zwei_trefferzahlen(self):
        """Wofür die Rechte gebaut sind – hier wird es sichtbar."""
        anna = self._als("anna", "ein-anderes-langes")
        chef = self._als("chef", "ein-langes-passwort")

        self.assertIn("2 Treffer", anna.get("/").text)
        self.assertIn("3 Treffer", chef.get("/").text)

    def test_der_betreff_einer_fremden_mail_steht_nicht_in_der_liste(self):
        anna = self._als("anna", "ein-anderes-langes")

        self.assertNotIn("Vertraulich", anna.get("/").text)

    def test_auch_nicht_ueber_die_suche_danach(self):
        anna = self._als("anna", "ein-anderes-langes")

        seite = anna.get("/?q=vertraulich").text
        self.assertNotIn("Vertraulich", seite)
        self.assertIn("nichts gefunden", seite)

    # -- Die eigentliche Probe --------------------------------------------

    def test_eine_fremde_nachricht_ueber_ihre_kennung(self):
        """Der Weg, auf dem eine Rechteprüfung am ehesten fehlt.

        Wer eine Kennung errät, aus einer weitergeleiteten Adresse
        kennt oder im Verlauf eines Kollegen findet, darf damit nicht an
        eine Mail kommen, die er sonst nicht sieht.
        """
        chef = self._als("chef", "ein-langes-passwort")
        fremd = self._kennungen(chef, "vertraulich")
        self.assertEqual(len(fremd), 1, "Testdaten stimmen nicht")

        anna = self._als("anna", "ein-anderes-langes")

        self.assertEqual(anna.get(f"/nachricht/{fremd[0]}").status_code, 404)
        self.assertEqual(
            anna.get(f"/nachricht/{fremd[0]}/datei").status_code, 404
        )

    def test_die_eigene_nachricht_geht(self):
        anna = self._als("anna", "ein-anderes-langes")
        eigen = self._kennungen(anna)

        seite = anna.get(f"/nachricht/{eigen[0]}")
        self.assertEqual(seite.status_code, 200)
        self.assertIn("Rechnung", seite.text)

    def test_der_download_liefert_die_mail_bytegenau(self):
        anna = self._als("anna", "ein-anderes-langes")
        eigen = self._kennungen(anna)

        antwort = anna.get(f"/nachricht/{eigen[0]}/datei")

        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.content.startswith(b"From: Wer Auch Immer"))
        self.assertIn("attachment", antwort.headers["content-disposition"])

    def test_eine_erfundene_kennung(self):
        anna = self._als("anna", "ein-anderes-langes")

        self.assertEqual(anna.get("/nachricht/" + "a" * 64).status_code, 404)

    # -- Rechte, die sich ändern ------------------------------------------

    def test_ein_entzogenes_recht_wirkt_sofort(self):
        """Nicht erst nach der nächsten Anmeldung.

        Deshalb steht im Cookie nur der Name, nicht die Rechte.
        """
        anna = self._als("anna", "ein-anderes-langes")
        self.assertIn("2 Treffer", anna.get("/").text)

        with Archive.open(self.wo) as archiv:
            liste = archiv.benutzer
            liste.finden("anna").postfaecher = []
            archiv.benutzer_setzen(liste, actor="chef")

        self.assertNotIn("2 Treffer", anna.get("/").text)

    def test_ein_stillgelegter_zugang_kommt_nicht_mehr_hinein(self):
        anna = self._als("anna", "ein-anderes-langes")

        with Archive.open(self.wo) as archiv:
            liste = archiv.benutzer
            liste.finden("anna").aktiv = False
            archiv.benutzer_setzen(liste, actor="chef")

        antwort = anna.get("/")
        self.assertEqual(antwort.status_code, 303)

    # -- Anzeige -----------------------------------------------------------

    def test_ein_betreff_wird_maskiert(self):
        """Ein Betreff ist Text, den ein Fremder geschrieben hat."""
        with Archive.open(self.wo) as archiv:
            archiv.add(
                _mail("<script>alarm()</script>"),
                account="buchhaltung", folder="INBOX",
            )

        anna = self._als("anna", "ein-anderes-langes")
        seite = anna.get("/").text

        self.assertNotIn("<script>alarm", seite)
        self.assertIn("&lt;script&gt;", seite)

    def test_die_seite_holt_nichts_von_fremden_servern(self):
        """Sonst verriete das Archiv jedem dort, wer wann darin liest."""
        anna = self._als("anna", "ein-anderes-langes")

        for seite in (anna.get("/").text,
                      Kunde(self.anwendung).get("/anmelden").text):
            with self.subTest():
                self.assertNotIn("http://", seite.replace("http://www.w3.org", ""))
                self.assertNotIn("https://", seite)
                self.assertNotIn("<script", seite)

    def test_der_zustand_liegt_nicht_mehr_auf_der_startseite(self):
        """Dort steht die Suche – der Zustand ist für Verwalter."""
        kunde = Kunde(self.anwendung)

        self.assertEqual(kunde.get("/zustand").status_code, 200)
        self.assertEqual(kunde.get("/lebt").json(), {"lebt": True})


if __name__ == "__main__":
    unittest.main()
