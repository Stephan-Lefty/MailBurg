"""Kein Rat, der auf PyPI zeigt – MailBurg liegt dort nicht.

**Woher dieser Test kommt.** Am 2026-10-01 sollte die Server Edition zum
ersten Mal auf einem echten Windows Server eingerichtet werden. Der Befehl
aus der eigenen Anleitung brach sofort ab::

    pip install "mailburg[server-windows]"
    ERROR: No matching distribution found for mailburg

MailBurg wird nicht über PyPI verteilt, sondern über ``git clone``, das
Debian-Paket, das AppImage und die ``.exe``. Ein ``pip install
"mailburg[…]"`` läuft damit bei **niemandem** – er muss ``pip install
".[…]"`` heißen und im geladenen Verzeichnis aufgerufen werden.

Der falsche Rat stand an sechs Stellen, und eine davon war keine Anleitung,
sondern eine Meldung im Programm: ``accounts.py`` schickte jeden, dem
``keyring`` fehlt, auf diesen Befehl. Dabei macht ``compress.py`` seit dem
2026-09-22 das Richtige und nennt das **Fremdpaket** (``zstandard``). Dort
war die Lehre nur zur Hälfte angekommen – der apt-Zweig stimmte, der
pip-Zweig nicht. Dasselbe Muster wie so oft hier: zwei Wege, einer
nachgezogen, der andere nicht.

**Warum der Test die Zusatznamen aus ``pyproject.toml`` liest** und nicht
nach ``mailburg[`` sucht: Die Warnungen, die vor dem falschen Befehl
warnen, müssen ihn zitieren dürfen. Sie schreiben ``mailburg[…]`` mit
Auslassungszeichen, und genau daran unterscheiden sich Zitat und Rat.

**Ausgenommen sind CHANGELOG.md und TODO.md.** Das sind Protokolle; was
dort steht, hat damals gegolten und soll nicht rückwirkend begradigt
werden.
"""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent

#: Wo gesucht wird. Protokolle stehen bewusst nicht dabei.
ORTE = ("docs", "mailburg", "werkzeuge")
EINZELN = ("README.md", "README.en.md", "RECHTLICHES.md")


def _zusaetze() -> set[str]:
    """Die echten Zusatznamen, wie ``pyproject.toml`` sie kennt."""
    daten = tomllib.loads((WURZEL / "pyproject.toml").read_text("utf-8"))
    return set(daten["project"]["optional-dependencies"])


def _dateien() -> list[Path]:
    gefunden: list[Path] = []
    for ort in ORTE:
        gefunden += sorted((WURZEL / ort).rglob("*.md"))
        gefunden += sorted((WURZEL / ort).rglob("*.py"))
    for name in EINZELN:
        pfad = WURZEL / name
        if pfad.exists():
            gefunden.append(pfad)
    return gefunden


class InstallBefehle(unittest.TestCase):
    def test_kein_rat_auf_pypi(self):
        """Nirgends ``mailburg[zusatz]`` mit einem echten Zusatznamen."""
        zusaetze = _zusaetze()
        muster = re.compile(r"mailburg\[([A-Za-z0-9_,\s-]+)\]")
        befunde: list[str] = []

        for datei in _dateien():
            for nr, zeile in enumerate(
                datei.read_text("utf-8").splitlines(), start=1
            ):
                for treffer in muster.finditer(zeile):
                    genannt = {
                        teil.strip()
                        for teil in treffer.group(1).split(",")
                        if teil.strip()
                    }
                    # Nur echte Zusatznamen sind ein Rat. Ein Zitat
                    # schreibt »mailburg[…]« und fällt hier durch.
                    if genannt and genannt <= zusaetze:
                        befunde.append(
                            f"{datei.relative_to(WURZEL)}:{nr}: "
                            f"{zeile.strip()}"
                        )

        self.assertEqual(
            befunde,
            [],
            "MailBurg liegt nicht auf PyPI – diese Stellen raten zu einem "
            'Befehl, der bei niemandem läuft. Richtig ist pip install ".[…]" '
            "im geladenen Verzeichnis, bei einem Fremdpaket dessen eigener "
            "Name:\n  " + "\n  ".join(befunde),
        )

    def test_die_anleitungen_nennen_den_punkt(self):
        """Wo ein pip-Befehl steht, steht auch, warum der Punkt dort ist.

        Ohne diese Hälfte wäre die Korrektur eine stille Änderung: Wer den
        Befehl aus dem Gedächtnis tippt, tippt ihn wieder falsch.
        """
        for name in ("erste-schritte.md", "server-einrichten.md"):
            doku = (WURZEL / "docs" / name).read_text("utf-8")
            with self.subTest(datei=name):
                self.assertIn('pip install ".', doku)
                self.assertIn("Punkt", doku)
                self.assertIn("PyPI", doku)

    def test_fehlendes_keyring_nennt_das_fremdpaket(self):
        """Die Meldung im Programm selbst – der teuerste der sechs Fälle."""
        quelle = (
            WURZEL / "mailburg" / "core" / "accounts.py"
        ).read_text("utf-8")
        self.assertIn("pip install keyring", quelle)
        self.assertIn("python3-keyring", quelle)


if __name__ == "__main__":
    unittest.main()
