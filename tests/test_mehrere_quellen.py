"""Mehrere Verzeichnisse unter einem Kontonamen einlesen.

**Der Anlass ist Stephans Lage vom 2026-10-06.** In MailStore liegen
zweiunddreißig Archive – siebzehn Postfächer plus fünfzehn
Benutzerarchive –, die zu etwa zwanzig Menschen gehören. Eine Person
hat oft drei Quellen: ein altes Postfach, ein neues und ein eigenes
Benutzerarchiv. Seine Frage, wörtlich: *»dann könnte ich mehrere
Verzeichnisse mit eml Dateien einen sinnvollen Namen zuordnen.«*

Vorher ging das nur als Folge einzelner Läufe, jeder mit demselben
Namen von Hand getippt. **Zweiunddreißig Gelegenheiten, sich zu
vertippen** – und ein Tippfehler ist hier nicht reparabel: Es gibt
keinen Befehl, der ein Konto umbenennt.

**Die Entscheidung, die dieser Umbau sichtbar macht:** Gleichnamige
Ordner aus verschiedenen Quellen verschmelzen in der Vorgabe (aus zwei
Posteingängen wird einer). Das ist meistens gewollt. Wer die Herkunft
behalten will, bekommt sie als Oberordner – die Mails selbst behalten
in beiden Fällen alles, denn die Kopfzeilen bleiben Byte für Byte
erhalten.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mailburg.core.archive import Archive
from mailburg.core.importer import Statistik
from mailburg.sources.local import MitHerkunft, open_path

MAIL = (
    b"From: partner@example.org\r\nTo: wer@example.net\r\n"
    b"Subject: Rechnung {nr}\r\nMessage-ID: <{nr}@example.org>\r\n"
    b"Date: Tue, 6 Oct 2026 09:00:00 +0200\r\n\r\nInhalt {nr}.\r\n"
)

try:
    import PySide6  # noqa: F401
except ImportError:  # pragma: no cover – der CI-Lauf ohne Oberfläche
    _QT_FEHLT = True
else:
    _QT_FEHLT = False


def _export(wurzel: Path, name: str, ordner: dict[str, list[int]]) -> Path:
    """Baut ein Verzeichnis, wie MailStore es herausschreibt."""
    for unterordner, nummern in ordner.items():
        (wurzel / name / unterordner).mkdir(parents=True, exist_ok=True)
        for nr in nummern:
            (wurzel / name / unterordner / f"{nr}.eml").write_bytes(
                MAIL.replace(b"{nr}", str(nr).encode())
            )
    return wurzel / name


class HuelleTest(unittest.TestCase):
    """``MitHerkunft`` stellt jedem Fundort seinen Ursprung voran."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.basis = Path(self._tmp.name)

    def test_die_ordner_bekommen_einen_oberordner(self):
        ort = _export(self.basis, "alt", {"INBOX": [1], "Gesendet": [2]})

        quelle = MitHerkunft(open_path(ort, "Wer"), "roesner@alt.example")
        self.addCleanup(quelle.close)

        self.assertEqual(
            sorted(quelle.folders()),
            ["roesner@alt.example/Gesendet", "roesner@alt.example/INBOX"],
        )

    def test_auch_die_mails_selbst(self):
        """Die Ordnerliste allein genügt nicht – gezählt wird, was im
        Archiv landet, und das steht an der Nachricht."""
        ort = _export(self.basis, "alt", {"INBOX": [1]})

        quelle = MitHerkunft(open_path(ort, "Wer"), "alt")
        self.addCleanup(quelle.close)

        self.assertEqual(
            [n.folder for n in quelle.iter_messages()], ["alt/INBOX"]
        )

    def test_eine_lose_mail_wird_nicht_verdoppelt(self):
        """**Liegt eine Mail unmittelbar im Verzeichnis**, trägt sie den
        Kontonamen als Fundort. Daraus »Herkunft/Kontoname« zu machen
        wäre eine Verdopplung, die niemand so geschrieben hätte."""
        (self.basis / "lose").mkdir()
        (self.basis / "lose" / "a.eml").write_bytes(
            MAIL.replace(b"{nr}", b"1")
        )

        quelle = MitHerkunft(open_path(self.basis / "lose", "Wer"), "alt")
        self.addCleanup(quelle.close)

        self.assertEqual([n.folder for n in quelle.iter_messages()], ["alt"])

    def test_ohne_herkunft_aendert_sie_nichts(self):
        """Damit der Aufrufer nicht zwischen zwei Wegen unterscheiden
        muss."""
        ort = _export(self.basis, "alt", {"INBOX": [1]})

        quelle = MitHerkunft(open_path(ort, "Wer"), "   ")
        self.addCleanup(quelle.close)

        self.assertEqual(quelle.folders(), ["INBOX"])

    def test_sie_verschluckt_nicht_was_uebergangen_wurde(self):
        """**Sonst macht sie aus einer genannten Auslassung eine
        stille.** Darunter liegt eine ``OhnePapierkorb``, die sich
        merkt, welche Ordner draußen blieben; der Dialog zeigt das an.
        """
        ort = _export(self.basis, "alt", {"INBOX": [1], "Junk": [2]})

        quelle = MitHerkunft(open_path(ort, "Wer"), "alt")
        self.addCleanup(quelle.close)
        list(quelle.iter_messages())

        self.assertEqual(sorted(quelle.uebergangen), ["Junk"])


class BilanzTest(unittest.TestCase):
    """``Statistik`` lässt sich zusammenzählen."""

    def test_zahlen_werden_addiert(self):
        a = Statistik(gelesen=10, neu=8, vorhanden=2)
        b = Statistik(gelesen=5, neu=5)

        self.assertEqual((a + b).gelesen, 15)
        self.assertEqual((a + b).neu, 13)
        self.assertEqual((a + b).vorhanden, 2)

    def test_auch_die_anhangszaehlung(self):
        a = Statistik(anhaenge={"pdf:eingescannt": 3, "docx": 1})
        b = Statistik(anhaenge={"pdf:eingescannt": 2})

        self.assertEqual(
            (a + b).anhaenge, {"pdf:eingescannt": 5, "docx": 1}
        )
        self.assertEqual((a + b).eingescannt, 5)

    def test_summe_ueber_eine_liste(self):
        """``sum()`` beginnt bei ``0`` – ohne ``__radd__`` ginge das nicht."""
        teile = [Statistik(neu=1), Statistik(neu=2), Statistik(neu=3)]

        self.assertEqual(sum(teile).neu, 6)

    def test_jedes_feld_wird_mitgezaehlt(self):
        """**Der Wächter gegen eine abgeschriebene Feldliste.**

        Würden die Felder aufgezählt statt durchlaufen, veraltete die
        Liste beim nächsten neuen Zähler – und zwar still: Die Summe
        wäre einfach zu klein, ohne dass etwas rot wird.
        """
        from dataclasses import fields

        zahlen = [f.name for f in fields(Statistik)
                  if f.name != "anhaenge"]
        a = Statistik(**{name: 1 for name in zahlen})

        summe = a + a
        for name in zahlen:
            with self.subTest(feld=name):
                self.assertEqual(getattr(summe, name), 2)

    def test_etwas_anderes_wird_nicht_addiert(self):
        with self.assertRaises(TypeError):
            Statistik() + 5


class MehrfachEinlesenTest(unittest.TestCase):
    """Der Lauf über mehrere Quellen – Stephans eigentlicher Fall.

    **Ohne Qt.** Was hier geprüft wird, ist Kernlogik; sie darf nicht
    daran hängen, dass eine Oberfläche installiert ist.
    """

    def setUp(self) -> None:
        import os
        from unittest import mock

        from mailburg.core import paths

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.basis = Path(self._tmp.name)
        for name in ("data_dir", "config_dir"):
            patcher = mock.patch.object(
                paths, name, return_value=self.basis / name
            )
            patcher.start()
            self.addCleanup(patcher.stop)
            (self.basis / name).mkdir(parents=True, exist_ok=True)
        self.wurzel = self.basis / "Archiv"
        Archive.create(self.wurzel, name="P").close()

        # Drei Quellen wie bei MailStore: zwei Adressen derselben Person
        # und ihr Benutzerarchiv. Mail 1 und 2 liegen in zweien davon.
        self.quellen = [
            _export(self.basis, "roesner@alt.example",
                    {"INBOX": [1, 2, 3], "Gesendet": [20]}),
            _export(self.basis, "roesner@neu.example",
                    {"INBOX": [4, 5], "Gesendet": [21]}),
            _export(self.basis, "Archiv von roesner", {"INBOX": [1, 2]}),
        ]

    def _einlesen(self, pfade=None, **zusatz):
        """Derselbe Weg, den Fenster und Kommandozeile gehen.

        **Geprüft wird der Kern, nicht die Oberfläche.** Bis zum
        06.10.2026 stand die Schleife in ``ui/arbeit.py``, und diese
        Tests holten sie von dort – im CI-Lauf *ohne* PySide6 brachen
        damit acht Tests, die mit Qt nicht das Geringste zu tun haben.
        Dieselbe Klasse wie am 31.08.: Der erste Job installiert
        bewusst nichts außer dem Kern, und hier liegt alles da.
        """
        from mailburg.core.importer import importiere_alle
        from mailburg.sources import local

        quellen = local.quellen_oeffnen(
            self.quellen if pfade is None else pfade,
            "Stephan Rösner", **zusatz,
        )
        try:
            with Archive.open(self.wurzel) as archiv:
                return importiere_alle(
                    archiv, quellen, mit_anhangstext=False
                )
        finally:
            for quelle in quellen:
                quelle.close()

    def test_alles_landet_unter_einem_namen(self):
        """**Der Punkt des Ganzen.**"""
        stat = self._einlesen()

        with Archive.open(self.wurzel) as archiv:
            konten = {k for k, _, _ in archiv.index.accounts()}
        self.assertEqual(konten, {"Stephan Rösner"})
        self.assertEqual(stat.gelesen, 9)

    def test_die_bilanz_zaehlt_alle_quellen_zusammen(self):
        """Nicht die der letzten Quelle – sonst meldet ein Lauf über
        zweiunddreißig Ordner die Zahlen des zweiunddreißigsten."""
        stat = self._einlesen()

        self.assertEqual(stat.neu, 7)
        # Mail 1 und 2 liegen in zwei Quellen; beim zweiten Mal sind sie
        # schon da. Die Bytes sind gleich, also entscheidet der Hash.
        self.assertEqual(stat.vorhanden, 2)

    def test_in_der_vorgabe_behaelt_jede_quelle_ihre_struktur(self):
        """**Stephans Urteil vom 2026-10-06**, wörtlich: »eigentlich
        wäre es sinnvoll, wenn jedes Verzeichnis auch wie in MailStore
        eine eigene Struktur hat.«

        Wer aus einem anderen Archivprogramm kommt, erkennt seinen Baum
        wieder – und das Zusammenlegen ist dann die Entscheidung, die
        man bewusst trifft, nicht das, was von selbst passiert.
        """
        self._einlesen()

        with Archive.open(self.wurzel) as archiv:
            ordner = {o for _, o, _ in archiv.index.accounts()}
        self.assertIn("roesner@alt.example/INBOX", ordner)
        self.assertIn("Archiv von roesner/INBOX", ordner)
        self.assertNotIn("INBOX", ordner)

    def test_zusammenlegen_verschmilzt_gleichnamige_ordner(self):
        """Der andere Weg: ein Posteingang je Person."""
        self._einlesen(zusammenlegen=True)

        with Archive.open(self.wurzel) as archiv:
            ordner = {o for _, o, _ in archiv.index.accounts()}
        self.assertEqual(ordner, {"INBOX", "Gesendet"})

    def test_bei_einer_quelle_gibt_es_keinen_oberordner(self):
        """Er hieße genauso wie das gewählte Verzeichnis – eine
        Verschachtelung ohne jeden Nutzen."""
        self._einlesen([self.quellen[0]])

        with Archive.open(self.wurzel) as archiv:
            ordner = {o for _, o, _ in archiv.index.accounts()}
        self.assertEqual(ordner, {"INBOX", "Gesendet"})

    def test_das_archiv_wird_nur_einmal_geoeffnet(self):
        """**Sonst nähme der Lauf die Sperre zweiunddreißigmal** – und
        zwischen zwei Quellen stünde das Archiv einen Augenblick offen
        für jeden anderen Vorgang. Genau daran ist am 21.09.2026 eine
        Hash-Kette gerissen.
        """
        from unittest import mock

        echt = Archive.open
        with mock.patch.object(
            Archive, "open", side_effect=echt, autospec=False
        ) as spion:
            self._einlesen()

        self.assertEqual(spion.call_count, 1)

    def test_ein_abbruch_vor_der_ersten_quelle_nimmt_nichts_auf(self):
        """Ein Thunderbird-Profil kann Jahrzehnte enthalten; wer den
        Lauf versehentlich startet, muss ihn beenden können."""
        from mailburg.core.importer import importiere_alle
        from mailburg.sources import local

        quellen = local.quellen_oeffnen(self.quellen, "Stephan Rösner")
        self.addCleanup(lambda: [q.close() for q in quellen])

        with Archive.open(self.wurzel) as archiv:
            stat = importiere_alle(
                archiv, quellen, mit_anhangstext=False, weiter=lambda: False
            )

        self.assertEqual(stat.gelesen, 0)
        with Archive.open(self.wurzel) as archiv:
            self.assertEqual(archiv.index.count(), 0)


@unittest.skipIf(_QT_FEHLT, "PySide6 ist nicht installiert")
class EinleselaufTest(unittest.TestCase):
    """Der Qt-Auftrag benutzt denselben Kern.

    **Was hier geprüft wird, ist die Naht, nicht die Mechanik.** Die
    Schleife über mehrere Quellen liegt seit dem 06.10.2026 im Kern
    (``importer.importiere_alle``) – vorher stand sie hier, und der
    CI-Lauf *ohne* PySide6 ließ acht Tests brechen, die mit Qt nichts
    zu tun hatten. Nur was wirklich Qt braucht, steht in dieser Klasse.
    """

    def setUp(self) -> None:
        from unittest import mock

        from mailburg.core import paths

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.basis = Path(self._tmp.name)
        for name in ("data_dir", "config_dir"):
            patcher = mock.patch.object(
                paths, name, return_value=self.basis / name
            )
            patcher.start()
            self.addCleanup(patcher.stop)
            (self.basis / name).mkdir(parents=True, exist_ok=True)
        self.wurzel = self.basis / "Archiv"
        Archive.create(self.wurzel, name="P").close()
        self.quellen = [
            _export(self.basis, "alt", {"INBOX": [1, 2, 3]}),
            _export(self.basis, "neu", {"INBOX": [4, 5]}),
        ]

    def test_ein_einzelner_pfad_geht_weiterhin(self):
        """**Die Aufrufer von vorher laufen unverändert weiter.** Ein
        Umbau, der jeden Aufrufer anfassen muss, vergisst einen."""
        from mailburg.ui.arbeit import Einleselauf

        lauf = Einleselauf(
            self.wurzel, self.quellen[0], "Einer", mit_anhangstext=False
        )
        stat = lauf.ausfuehren()

        self.assertEqual(stat.neu, 3)
        self.assertEqual(lauf.quellpfad, self.quellen[0])

    def test_mehrere_pfade_landen_unter_einem_namen(self):
        from mailburg.ui.arbeit import Einleselauf

        stat = Einleselauf(
            self.wurzel, self.quellen, "Beide", mit_anhangstext=False
        ).ausfuehren()

        self.assertEqual(stat.neu, 5)
        with Archive.open(self.wurzel) as archiv:
            konten = {k for k, _, _ in archiv.index.accounts()}
            ordner = {o for _, o, _ in archiv.index.accounts()}
        self.assertEqual(konten, {"Beide"})
        self.assertEqual(ordner, {"alt/INBOX", "neu/INBOX"})

    def test_ein_abbruch_laesst_das_bisherige_stehen(self):
        from mailburg.ui.arbeit import Einleselauf

        lauf = Einleselauf(
            self.wurzel, self.quellen, "Beide", mit_anhangstext=False
        )
        lauf.abbrechen()
        stat = lauf.ausfuehren()

        self.assertEqual(stat.gelesen, 0)
        with Archive.open(self.wurzel) as archiv:
            self.assertEqual(archiv.index.count(), 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
