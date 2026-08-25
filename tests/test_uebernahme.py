"""Kontoeinstellungen aus einem Thunderbird-Profil übernehmen."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mailburg.core.uebernahme import aus_thunderbird, namen_entzerren


def prefs(*zeilen: str) -> str:
    kopf = '# Mozilla User Preferences\n\n'
    return kopf + "\n".join(zeilen) + "\n"


def server(nummer: int, **felder) -> list[str]:
    return [
        f'user_pref("mail.server.server{nummer}.{feld}", {wert});'
        for feld, wert in felder.items()
    ]


class UebernahmeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.profil = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def schreiben(self, inhalt: str) -> Path:
        (self.profil / "prefs.js").write_text(inhalt, encoding="utf-8")
        return self.profil

    def test_ohne_profil_ein_klarer_fehler(self):
        with self.assertRaises(FileNotFoundError):
            aus_thunderbird(self.profil)

    def test_imap_konto_vollstaendig(self):
        self.schreiben(prefs(*server(
            2,
            type='"imap"',
            hostname='"imap.example.org"',
            userName='"post@example.org"',
            port=993,
            socketType=3,
            name='"Firma"',
        )))
        funde = aus_thunderbird(self.profil)
        self.assertEqual(len(funde), 1)

        konto = funde[0].konto
        self.assertEqual(konto.name, "Firma")
        self.assertEqual(konto.server, "imap.example.org")
        self.assertEqual(konto.benutzer, "post@example.org")
        self.assertEqual(konto.port, 993)
        self.assertTrue(konto.ssl)
        self.assertTrue(funde[0].brauchbar)

    def test_starttls_wird_erkannt(self):
        # socketType 2 heißt: im Klartext beginnen, dann auf TLS hochstufen.
        self.schreiben(prefs(*server(
            2, type='"imap"', hostname='"mail.example.org"',
            userName='"post"', port=143, socketType=2,
        )))
        konto = aus_thunderbird(self.profil)[0].konto
        self.assertFalse(konto.ssl)
        self.assertEqual(konto.port, 143)

    def test_fehlender_port_wird_ergaenzt(self):
        self.schreiben(prefs(*server(
            2, type='"imap"', hostname='"imap.example.org"',
            userName='"post"', socketType=3,
        )))
        self.assertEqual(aus_thunderbird(self.profil)[0].konto.port, 993)

    def test_pop3_wird_gemeldet_aber_nicht_empfohlen(self):
        # Nicht verschweigen: Der Anwender soll erfahren, warum sein Konto
        # nicht dabei ist.
        self.schreiben(prefs(*server(
            1, type='"pop3"', hostname='"pop.example.org"', userName='"post"',
        )))
        funde = aus_thunderbird(self.profil)
        self.assertEqual(len(funde), 1)
        self.assertFalse(funde[0].brauchbar)
        self.assertEqual(funde[0].art, "pop3")

    def test_lokale_ordner_und_feeds_fallen_weg(self):
        self.schreiben(prefs(
            *server(1, type='"none"', hostname='"Local Folders"'),
            *server(2, type='"rss"', hostname='"Feeds"'),
            *server(3, type='"imap"', hostname='"imap.example.org"', userName='"post"'),
        ))
        funde = aus_thunderbird(self.profil)
        self.assertEqual([f.konto.server for f in funde], ["imap.example.org"])

    def test_konto_ohne_hostnamen_faellt_weg(self):
        self.schreiben(prefs(*server(1, type='"imap"', userName='"post"')))
        self.assertEqual(aus_thunderbird(self.profil), [])

    def test_ohne_anzeigenamen_hilft_der_benutzername(self):
        self.schreiben(prefs(*server(
            2, type='"imap"', hostname='"imap.example.org"',
            userName='"stephan@example.org"',
        )))
        self.assertEqual(aus_thunderbird(self.profil)[0].konto.name, "stephan")

    def test_mehrere_konten_in_der_reihenfolge_der_kennung(self):
        self.schreiben(prefs(
            *server(10, type='"imap"', hostname='"zehn.example.org"', userName='"a"'),
            *server(2, type='"imap"', hostname='"zwei.example.org"', userName='"b"'),
        ))
        # Nach Zahl, nicht nach Text - sonst käme server10 vor server2.
        self.assertEqual(
            [f.quelle for f in aus_thunderbird(self.profil)], ["server2", "server10"]
        )

    def test_umlaute_und_maskierte_zeichen(self):
        self.schreiben(prefs(*server(
            2, type='"imap"', hostname='"imap.example.org"',
            userName='"post"', name='"Meier \\" Söhne"',
        )))
        self.assertEqual(aus_thunderbird(self.profil)[0].konto.name, 'Meier " Söhne')

    def test_kaputte_zeilen_stoeren_nicht(self):
        self.schreiben(prefs(
            "das ist keine Einstellung",
            'user_pref("mail.server.server2.type", "imap");',
            'user_pref("mail.server.server2.hostname", "imap.example.org");',
            'user_pref("mail.server.server2.userName", "post");',
            "user_pref(kaputt",
        ))
        self.assertEqual(len(aus_thunderbird(self.profil)), 1)

    def test_passwortdateien_werden_nicht_angefasst(self):
        # Die Zusicherung des Moduls, festgehalten als Test: Gelesen wird
        # ausschließlich prefs.js. logins.json und key4.db rührt MailBurg
        # nicht an, auch wenn sie danebenliegen.
        self.schreiben(prefs(*server(
            2, type='"imap"', hostname='"imap.example.org"', userName='"post"',
        )))
        (self.profil / "logins.json").write_text("{}", encoding="utf-8")
        (self.profil / "key4.db").write_bytes(b"\x00")

        gelesen: list[str] = []
        echtes_read = Path.read_text
        echtes_bytes = Path.read_bytes

        def merken_text(selbst, *rest, **schluessel):
            gelesen.append(selbst.name)
            return echtes_read(selbst, *rest, **schluessel)

        def merken_bytes(selbst, *rest, **schluessel):
            gelesen.append(selbst.name)
            return echtes_bytes(selbst, *rest, **schluessel)

        Path.read_text, Path.read_bytes = merken_text, merken_bytes
        try:
            aus_thunderbird(self.profil)
        finally:
            Path.read_text, Path.read_bytes = echtes_read, echtes_bytes

        self.assertEqual(gelesen, ["prefs.js"])


class NamenTest(unittest.TestCase):
    def funde(self, *namen):
        self.schreiben = None
        from mailburg.core.accounts import Konto
        from mailburg.core.uebernahme import Fund

        return [
            Fund(
                konto=Konto(name=n, server=f"imap{i}.example.org", benutzer="post"),
                quelle=f"server{i}",
                art="imap",
            )
            for i, n in enumerate(namen, 1)
        ]

    def test_doppelte_namen_werden_unterscheidbar(self):
        # Der Kontoname ordnet im Archiv jede Mail ihrem Postfach zu. Zwei
        # Konten mit demselben Namen wären dort nicht mehr zu trennen.
        funde = self.funde("Post", "Post")
        namen_entzerren(funde, set())
        self.assertEqual(funde[0].konto.name, "Post")
        self.assertEqual(funde[1].konto.name, "Post (imap2.example.org)")

    def test_ruecksicht_auf_schon_vergebene_namen(self):
        funde = self.funde("Firma")
        namen_entzerren(funde, {"Firma"})
        self.assertNotEqual(funde[0].konto.name, "Firma")

    def test_auch_der_ausweichname_kann_belegt_sein(self):
        funde = self.funde("Post")
        namen_entzerren(funde, {"Post", "Post (imap1.example.org)"})
        self.assertEqual(funde[0].konto.name, "Post (imap1.example.org) 2")


if __name__ == "__main__":
    unittest.main()
