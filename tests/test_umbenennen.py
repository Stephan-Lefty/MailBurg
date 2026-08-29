"""Was geschieht, wenn ein IMAP-Ordner umbenannt wird.

**Der Fall.** MailBurg merkt sich den Fundort unter dem angezeigten
Namen. Wird aus »Kunden« ein »Kunden 2025«, ist der Höchststand für den
neuen Namen null: Der ganze Ordner wird erneut durchlaufen, jede Mail
bekommt einen zweiten Fundort, und im Ordnerbaum steht der alte Name als
Geist weiter.

Verloren geht dabei nichts – die Ablage ist inhaltsadressiert, doppelt
liegt keine einzige Datei. Aber das Journal wächst ohne Not: Bei einem
Ordner mit fünftausend Mails sind das fünftausend überflüssige Einträge.

Am 2026-08-29 nachgestellt und behoben. Vorher: zwei Fundorte, sechs
Journaleinträge für drei Mails. Nachher: einer und drei.
"""

from __future__ import annotations

import pathlib
import tempfile
import unittest
from unittest import mock

from mailburg.core import paths
from mailburg.core.accounts import Konto
from mailburg.core.archive import Archive
from mailburg.core.importer import importieren
from mailburg.core.sync import Abrufzustand
from mailburg.sources.imap import ImapSource
from tests.fake_imap import FakeImap, FakeOrdner, mail


class UmbenennenTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.basis = pathlib.Path(self._tmp.name)

        flicken = mock.patch.object(
            paths, "data_dir", return_value=self.basis / "daten"
        )
        flicken.start()
        self.addCleanup(flicken.stop)

        self.archiv = Archive.create(self.basis / "archiv", name="Test")
        self.addCleanup(self._abbauen)

        self.konto = Konto(name="Firma", server="imap.example.org",
                           benutzer="post@example.org")
        self.zustand = Abrufzustand("test", datei=self.basis / "abruf.json")

    def _abbauen(self) -> None:
        try:
            self.archiv.close()
        except Exception:  # noqa: BLE001
            pass
        self._tmp.cleanup()

    def _abrufen(self, *ordner: FakeOrdner):
        quelle = ImapSource(
            self.konto,
            verbindung=FakeImap(list(ordner)),
            zustand=self.zustand,
            hoechststand=lambda o: self.archiv.index.max_uid("Firma", o),
        )
        return importieren(self.archiv, quelle, mit_anhangstext=False)

    def _ordner(self, name: str, kennzahl: int = 4711, anzahl: int = 3):
        return FakeOrdner(
            name,
            {n: mail(f"Nachricht {n}") for n in range(1, anzahl + 1)},
            uidvalidity=kennzahl,
        )

    def _fundorte(self) -> dict[str, int]:
        zeilen = self.archiv.index.db.execute(
            "SELECT folder, COUNT(*) FROM locations GROUP BY folder"
        ).fetchall()
        return {z[0]: z[1] for z in zeilen}

    def _journal(self, vorgang: str) -> list:
        return [v for v in self.archiv.journal.read_all()
                if v.get("op") == vorgang]

    # ------------------------------------------------------------ Der Fall

    def test_der_ordner_wird_nicht_zweimal_gefuehrt(self) -> None:
        self._abrufen(self._ordner("Kunden"))
        self._abrufen(self._ordner("Kunden 2025"))

        self.assertEqual(self._fundorte(), {"Kunden 2025": 3})

    def test_das_journal_waechst_nicht(self) -> None:
        """Bei fünftausend Mails wären es fünftausend Einträge."""
        self._abrufen(self._ordner("Kunden"))
        self._abrufen(self._ordner("Kunden 2025"))

        self.assertEqual(len(self._journal("add")), 3)

    def test_der_vorgang_steht_im_journal(self) -> None:
        """Beim Neuaufbau des Index muss nachvollziehbar sein, warum die
        Mails jetzt woanders liegen."""
        self._abrufen(self._ordner("Kunden"))
        self._abrufen(self._ordner("Kunden 2025"))

        vermerke = [v for v in self._journal("note")
                    if v.get("art") == "ordner_umbenannt"]
        self.assertEqual(len(vermerke), 1)
        self.assertEqual(vermerke[0]["alt"], "Kunden")
        self.assertEqual(vermerke[0]["neu"], "Kunden 2025")
        self.assertEqual(vermerke[0]["fundorte"], 3)

    def test_der_abrufzustand_zieht_mit(self) -> None:
        """Sonst hielte der nächste Lauf den Ordner für frisch."""
        self._abrufen(self._ordner("Kunden"))
        self._abrufen(self._ordner("Kunden 2025"))

        self.assertIsNone(self.zustand.uidvalidity("Firma", "Kunden"))
        self.assertEqual(self.zustand.uidvalidity("Firma", "Kunden 2025"), 4711)

    def test_danach_wird_nichts_mehr_geholt(self) -> None:
        """Der Beweis, dass der Höchststand mitgezogen ist."""
        self._abrufen(self._ordner("Kunden"))
        self._abrufen(self._ordner("Kunden 2025"))
        stat = self._abrufen(self._ordner("Kunden 2025"))

        self.assertEqual(stat.neu, 0)

    # -------------------------------------------------- Wo nicht zugeordnet

    def test_eine_andere_kennzahl_ist_ein_anderer_ordner(self) -> None:
        """UIDVALIDITY ändert sich beim Umbenennen nicht.

        Tut sie es doch, hat der Server die UIDs neu vergeben – dann ist
        es entweder ein anderer Ordner oder ein Fall, in dem ohnehin
        alles neu gelesen werden muss.
        """
        self._abrufen(self._ordner("Kunden", kennzahl=4711))
        self._abrufen(self._ordner("Andere", kennzahl=9999))

        self.assertIn("Kunden", self._fundorte())
        self.assertIn("Andere", self._fundorte())

    def test_bei_zwei_verschwundenen_geschieht_nichts(self) -> None:
        """Im Zweifel lieber doppelt lesen als falsch zusammenführen.

        Zwei Ordner können dieselbe UIDVALIDITY tragen – der Standard
        verlangt Eindeutigkeit nur innerhalb eines Ordners über die Zeit.
        Ein falsch zusammengeführter Ordner wäre deutlich schlimmer als
        ein doppelt gelesener.
        """
        self._abrufen(self._ordner("A"), self._ordner("B", kennzahl=4711))
        self._abrufen(self._ordner("C", kennzahl=4711))

        # Nichts wurde zugeordnet: A und B stehen noch da.
        self.assertIn("A", self._fundorte())
        self.assertIn("C", self._fundorte())

    def test_ein_geloeschter_ordner_wird_nicht_umbenannt(self) -> None:
        """Verschwindet einer ersatzlos, gibt es nichts zuzuordnen."""
        self._abrufen(self._ordner("Kunden"), self._ordner("Rest", kennzahl=1))
        self._abrufen(self._ordner("Rest", kennzahl=1))

        self.assertIn("Kunden", self._fundorte())
        self.assertEqual(len(self._journal("note")), 0)

    def test_beim_ersten_lauf_geschieht_nichts(self) -> None:
        """Ohne bekannte Ordner gibt es keine Umbenennung."""
        self._abrufen(self._ordner("Kunden"))

        self.assertEqual(self._fundorte(), {"Kunden": 3})
        self.assertEqual(len(self._journal("note")), 0)


class QuellenTest(unittest.TestCase):
    """Nur Quellen, die es können, werden gefragt.

    Ein Thunderbird-Profil hat keine ``UIDVALIDITY``, und ein Ordner
    heißt dort, wie er heißt.
    """

    def test_eine_quelle_ohne_zustand_wird_uebergangen(self) -> None:
        from mailburg.core.importer import _umbenennungen_nachziehen

        class Ohne:
            account = "x"

        # Darf nicht werfen.
        _umbenennungen_nachziehen(None, Ohne())

    def test_ein_fehler_bei_der_erkennung_kostet_nicht_den_abruf(self) -> None:
        """Im schlimmsten Fall wird doppelt gelesen, wie bisher."""
        from mailburg.core.importer import _umbenennungen_nachziehen

        class Zustand:
            def bekannte_ordner(self, _konto):
                return {"Kunden"}

        class Kaputt:
            account = "x"
            zustand = Zustand()

            def umbenennungen(self, _bekannte):
                raise RuntimeError("Server weg")

        _umbenennungen_nachziehen(None, Kaputt())


if __name__ == "__main__":
    unittest.main()
