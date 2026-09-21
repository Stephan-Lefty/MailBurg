"""Der Einlesedialog schlägt dieselben Orte vor, die der Kern kennt.

**Der Anlass ist eine Rückmeldung vom 2026-09-21.** Ein Anwender mit
Evolution aus Flatpak bekam im Dialog *Lokale Mailordner einlesen …*
nichts vorgeschlagen, obwohl seine Post unter
``~/.var/app/org.gnome.Evolution/data/evolution/mail/local`` lag.

Der Grund war nicht ein vergessener Pfad, sondern eine zweite Liste:
Der Dialog führte seine eigene, und sie war eine andere als die, nach
der MailBurg sonst sucht. Thunderbird stand darin mit seinem
Flatpak-Ordner, Evolution nur mit dem klassischen, und Thunderbirds
Snap-Ordner fehlte ganz – obwohl ``local.thunderbird_profile_dirs()``
ihn seit jeher kennt.

**Zwei Listen über dieselbe Sache laufen auseinander**, und zwar immer
zu Lasten der zweiten: Wer einen Pfad ergänzt, tut das dort, wo er
gerade arbeitet. Diese Tests halten sie zusammen.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from mailburg.sources import local

try:
    from PySide6.QtWidgets import QApplication  # noqa: F401

    QT_DA = True
except ImportError:  # pragma: no cover – ohne Oberfläche
    QT_DA = False


class EvolutionOrte(unittest.TestCase):
    """Die Pfade im Kern – ohne Oberfläche prüfbar."""

    def test_klassisch_und_flatpak(self) -> None:
        orte = local.evolution_mailordner()
        enden = {"/".join(o.parts[-5:]) for o in orte}

        self.assertIn("share/evolution/mail/local", "/".join(orte[0].parts))
        self.assertTrue(
            any("org.gnome.Evolution" in str(o) for o in orte),
            f"Der Flatpak-Ordner fehlt: {orte}",
        )
        self.assertEqual(len(enden), len(orte), "Zwei Einträge zeigen auf dasselbe")

    def test_alle_enden_auf_mail_local(self) -> None:
        """Jeder Kandidat ist eine Maildir++-Wurzel, kein Elternordner.

        Ein Pfad auf ``…/evolution`` sähe richtig aus und enthielte
        Adressbücher und Kalender – der Einlesedialog böte ihn an, und
        das Ergebnis wäre eine Fehlermeldung statt eines Vorschlags.
        """
        for ort in local.evolution_mailordner():
            self.assertEqual(ort.parts[-2:], ("mail", "local"), str(ort))

    def test_unter_dem_benutzerverzeichnis(self) -> None:
        heim = Path.home()
        for ort in local.evolution_mailordner():
            self.assertTrue(ort.is_relative_to(heim), str(ort))


@unittest.skipUnless(QT_DA, "PySide6 fehlt")
class DialogKenntDieselbenOrte(unittest.TestCase):
    """Der Wächter: Was der Kern kennt, muss der Dialog anbieten."""

    def kandidaten(self) -> list[Path]:
        from mailburg.ui import einlesen

        return [ort for _, ort in einlesen._kandidaten()]

    def test_evolution_vollstaendig(self) -> None:
        for ort in local.evolution_mailordner():
            self.assertIn(ort, self.kandidaten(),
                          f"{ort} kennt der Kern, der Dialog nicht")

    def test_thunderbird_vollstaendig(self) -> None:
        """Deckt Flatpak *und* Snap ab – beide kennt der Kern."""
        for ort in local.thunderbird_profile_dirs():
            self.assertIn(ort, self.kandidaten(),
                          f"{ort} kennt der Kern, der Dialog nicht")

    def test_keine_doppelten_pfade(self) -> None:
        pfade = self.kandidaten()
        self.assertEqual(len(pfade), len(set(pfade)))


@unittest.skipUnless(QT_DA, "PySide6 fehlt")
class GleichnamigeWerdenUnterschieden(unittest.TestCase):
    """Zweimal »Evolution« im Vorschlag wäre nicht zu unterscheiden.

    Wer von der klassischen Installation auf Flatpak wechselt, hat beide
    Verzeichnisse. Ein Tooltip »Auch gefunden: Evolution« beantwortet
    dann genau nichts.
    """

    def test_pfad_dahinter_wenn_name_doppelt(self) -> None:
        from mailburg.ui import einlesen

        heim = Path.home()
        doppelt = [
            ("Evolution – lokale Ordner", heim / "a"),
            ("Evolution – lokale Ordner", heim / "b"),
            ("Thunderbird", heim / "c"),
        ]
        echte = einlesen._kandidaten
        einlesen._kandidaten = lambda: doppelt
        try:
            # ``exists()`` filtert sonst alles weg – hier zählt die
            # Beschriftung, nicht das Dateisystem.
            namen = dict(self._ohne_dateisystempruefung(einlesen))
        finally:
            einlesen._kandidaten = echte

        beschriftungen = list(namen)
        self.assertEqual(len(beschriftungen), 3)
        self.assertEqual(
            sum(1 for b in beschriftungen if b == "Thunderbird"), 1,
            "Ein eindeutiger Name bekommt keinen Pfad angehängt",
        )
        self.assertTrue(
            all(str(heim / "a") in b or str(heim / "b") in b or b == "Thunderbird"
                for b in beschriftungen),
            f"Gleichnamige ohne Pfad: {beschriftungen}",
        )

    @staticmethod
    def _ohne_dateisystempruefung(modul):
        """``_bekannte_orte`` mit einem ``exists()``, das immer Ja sagt."""
        echte_exists = Path.exists
        Path.exists = lambda self: True  # type: ignore[assignment]
        try:
            return modul._bekannte_orte()
        finally:
            Path.exists = echte_exists  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
