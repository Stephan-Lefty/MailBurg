"""Kontoeinstellungen aus einem Thunderbird-Profil übernehmen."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mailburg.core.uebernahme import (
    aus_evolution,
    aus_thunderbird,
    namen_entzerren,
)


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


class EvolutionTest(unittest.TestCase):
    """Kontoeinstellungen aus Evolution übernehmen.

    **Von einem Anwender am 2026-09-03 gewünscht:** Er ist unter GNOME
    von Thunderbird auf Evolution umgestiegen – »Wünschenswert für die
    Zukunft wäre also auch ein Import der Konten aus Evolution.« Bis
    dahin las MailBurg nur Thunderbird; wer Evolution benutzt, tippte
    alles von Hand.

    Evolution legt jedes Konto als eigene ``.source``-Datei ab, im
    Format von GKeyFile. In demselben Verzeichnis liegen aber auch
    Adressbücher, Kalender und Aufgabenlisten – die dürfen nicht als
    Postfach durchgehen.
    """

    def setUp(self) -> None:
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wo = Path(self.ordner.name)

    def _quelle(self, name: str, inhalt: str) -> None:
        (self.wo / f"{name}.source").write_text(inhalt, encoding="utf-8")

    def _imap(self, name="Firma", host="imap.example.org", user="post@example.org",
              port="993", sicherheit="tls", backend="imapx", datei="1234abcd"):
        self._quelle(datei, f"""[Data Source]
DisplayName={name}
Enabled=true
Parent=

[Mail Account]
BackendName={backend}
IdentityUid=abcd1234

[Authentication]
Host={host}
Method=PLAIN
Port={port}
User={user}
RememberPassword=true

[Security]
Method={sicherheit}
""")

    def test_ein_imap_konto_kommt_vollstaendig_an(self):
        self._imap()

        [fund] = aus_evolution(self.wo)

        self.assertTrue(fund.brauchbar)
        self.assertEqual(fund.konto.name, "Firma")
        self.assertEqual(fund.konto.server, "imap.example.org")
        self.assertEqual(fund.konto.benutzer, "post@example.org")
        self.assertEqual(fund.konto.port, 993)
        self.assertTrue(fund.konto.ssl)

    def test_starttls_wird_erkannt(self):
        self._imap(port="143", sicherheit="starttls")

        [fund] = aus_evolution(self.wo)

        self.assertFalse(fund.konto.ssl)
        self.assertEqual(fund.konto.port, 143)

    def test_grossgeschriebene_schluessel_gehen_nicht_verloren(self):
        # configparser macht Schlüssel standardmäßig klein; Evolution
        # schreibt "Host" und "User" gross. Ohne optionxform fände man
        # gar nichts.
        self._imap(host="mail.example.net")

        [fund] = aus_evolution(self.wo)

        self.assertEqual(fund.konto.server, "mail.example.net")

    def test_ein_adressbuch_ist_kein_postfach(self):
        # Im selben Verzeichnis liegen Adressbücher, Kalender und
        # Aufgabenlisten.
        self._quelle("adressbuch", """[Data Source]
DisplayName=Persönlich
Enabled=true

[Address Book]
Order=0
""")
        self._quelle("kalender", """[Data Source]
DisplayName=Termine

[Calendar]
Color=#becedd
""")
        self._imap()

        funde = aus_evolution(self.wo)

        self.assertEqual(len(funde), 1)
        self.assertEqual(funde[0].konto.name, "Firma")

    def test_die_lokalen_ordner_sind_kein_postfach(self):
        # "Auf diesem Rechner" hat keinen Server - die kommen über
        # "Lokale Mailordner einlesen" herein.
        self._quelle("local", """[Data Source]
DisplayName=Auf diesem Rechner

[Mail Account]
BackendName=none
""")

        self.assertEqual(aus_evolution(self.wo), [])

    def test_pop3_wird_gemeldet_statt_verschwiegen(self):
        # Evolution schreibt "pop", Thunderbird "pop3" - gemeint ist
        # dasselbe, und der Anwender soll den anderen Weg erfahren.
        self._imap(name="Alt", backend="pop", port="995")

        [fund] = aus_evolution(self.wo)

        self.assertFalse(fund.brauchbar)
        self.assertIn("POP3", fund.begruendung)
        self.assertIn("Lokale Mailordner einlesen", fund.begruendung)

    def test_exchange_wird_gemeldet(self):
        self._imap(name="Arbeit", backend="ews")

        [fund] = aus_evolution(self.wo)

        self.assertFalse(fund.brauchbar)
        self.assertIn("IMAP", fund.begruendung)

    def test_ohne_anzeigenamen_tritt_der_benutzer_ein(self):
        self._imap(name="", user="martha@example.org")

        [fund] = aus_evolution(self.wo)

        self.assertEqual(fund.konto.name, "martha")

    def test_eine_kaputte_datei_kostet_die_uebrigen_nicht(self):
        (self.wo / "kaputt.source").write_text(
            "das ist kein INI = = =\n[[[", encoding="utf-8"
        )
        self._imap()

        funde = aus_evolution(self.wo)

        self.assertEqual(len(funde), 1)

    def test_eine_bruecke_auf_dem_eigenen_rechner_wird_erkannt(self):
        # Proton Bridge und Ähnliches weisen sich zwangsläufig
        # selbstsigniert aus.
        self._imap(host="127.0.0.1", port="1143", sicherheit="starttls")

        [fund] = aus_evolution(self.wo)

        self.assertTrue(fund.konto.bruecke)

    def test_ein_verzeichnis_ohne_quellen_sagt_das(self):
        with self.assertRaises(FileNotFoundError) as fall:
            aus_evolution(self.wo)

        self.assertIn("source", str(fall.exception))

    def test_ein_verzeichnis_das_es_nicht_gibt(self):
        with self.assertRaises(FileNotFoundError):
            aus_evolution(self.wo / "gibtesnicht")

    def test_zwei_konten_mit_gleichem_namen_werden_entzerrt(self):
        # Derselbe Weg wie bei Thunderbird: Der Name ist im Archiv die
        # Zuordnung einer Mail zu ihrem Postfach.
        self._imap(name="Post", host="imap.example.org", datei="eins")
        self._imap(name="Post", host="imap.example.net", datei="zwei")

        funde = aus_evolution(self.wo)
        namen_entzerren(funde, set())

        self.assertEqual(len({f.konto.name for f in funde}), 2)
