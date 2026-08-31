"""Wer wen anfassen darf.

MailBurg hat drei Frontends – Kommandozeile, Desktop-Fenster und
(demnächst) den Server – auf einem gemeinsamen Kern. Damit das trägt,
muss die Richtung stimmen: **Frontends kennen den Kern, der Kern kennt
keine Frontends.**

Das ist keine Formsache. Ein Serverdienst, der beim Start ein Modul
namens ``ui`` einlädt, holt sich früher oder später eine
Qt-Abhängigkeit auf eine Maschine ohne Bildschirm – und merkt es an dem
Tag, an dem jemand ihn neu aufsetzt.

Geprüft wird an den Importen im Quelltext, nicht durch Ausführen: So
schlägt der Test auch dann an, wenn der Import tief in einer Funktion
steht und im Betrieb selten erreicht wird.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent

#: Die Schichten des Kerns. Sie dürfen von jedem Frontend benutzt
#: werden und selbst keines kennen.
KERN = ("core", "search", "sources", "extract")

#: **Hier standen einmal Ausnahmen.** ``core/archive.py`` und
#: ``core/nachfrage.py`` holten sich aus ``ui/app.py``, was der Anwender
#: zuletzt geöffnet hatte. Am 2026-08-31 aufgelöst: Das Gemerkte liegt
#: jetzt in ``core/einstellungen.py``, wohin es gehört – es ist Zustand
#: des Programms, nicht der Oberfläche.
#:
#: Die Liste bleibt leer stehen, mitsamt dem Test darunter. Wer je wieder
#: eine Ausnahme braucht, trägt sie hier ein und muss sie benennen; und
#: der Test sorgt dafür, dass sie nicht liegen bleibt, wenn ihr Grund
#: wegfällt.
GEDULDET: dict[str, str] = {}


def _importe(datei: Path) -> set[str]:
    """Alle importierten Modulnamen einer Datei – auch die in Funktionen."""
    baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
    gefunden: set[str] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            gefunden.update(teil.name for teil in knoten.names)
        elif isinstance(knoten, ast.ImportFrom) and knoten.module:
            gefunden.add(knoten.module)
    return gefunden


def _dateien(*teile: str) -> list[Path]:
    ordner = WURZEL / "mailburg"
    return [
        pfad
        for teil in teile
        for pfad in (ordner / teil).rglob("*.py")
        if "__pycache__" not in pfad.parts
    ]


class KernTest(unittest.TestCase):
    """Der Kern kennt keine Oberfläche."""

    def test_kein_qt_im_kern(self):
        """Sonst läuft die Kommandozeile nicht ohne 150 MB PySide6."""
        for datei in _dateien(*KERN):
            with self.subTest(datei=datei.name):
                self.assertFalse(
                    any(m.startswith("PySide6") for m in _importe(datei)),
                    f"{datei.relative_to(WURZEL)} importiert PySide6",
                )

    def test_der_kern_kennt_die_oberflaeche_nicht(self):
        for datei in _dateien(*KERN):
            kurz = str(datei.relative_to(WURZEL / "mailburg"))
            if kurz in GEDULDET:
                continue
            with self.subTest(datei=kurz):
                self.assertFalse(
                    any(m.startswith("mailburg.ui") for m in _importe(datei)),
                    f"{kurz} importiert aus mailburg.ui",
                )

    def test_die_geduldeten_stellen_gibt_es_noch(self):
        """Sonst steht hier eine Ausnahme für etwas Erledigtes.

        Ein Testfall, der eine Regel lockert, muss selbst überwacht
        werden – sonst bleibt die Lücke offen, nachdem der Grund
        weggefallen ist.
        """
        for kurz in GEDULDET:
            with self.subTest(datei=kurz):
                datei = WURZEL / "mailburg" / kurz
                self.assertTrue(datei.is_file(), f"{kurz} gibt es nicht mehr")
                self.assertTrue(
                    any(m.startswith("mailburg.ui") for m in _importe(datei)),
                    f"{kurz} braucht die Ausnahme nicht mehr – hier streichen",
                )


class ServerTest(unittest.TestCase):
    """Die Trennung, bevor es etwas zu trennen gibt.

    Am 2026-08-31 mit Stephan verabredet: Die Server Edition bekommt
    **kein eigenes Repository**, sondern ein eigenes Verzeichnis. Der
    Grund ist derselbe, aus dem man sie sonst trennen würde – Sauberkeit:
    Ein zweites Repo hieße ein zweiter Kern, und zwei Archivformate, die
    auseinanderlaufen, merkt niemand, bis ein Archiv nicht mehr lesbar
    ist.

    Getrennt wird deshalb hier, mit einer Regel, die vor der ersten
    Zeile Code steht: Server und Oberfläche fassen einander nicht an.
    Beide dürfen den Kern benutzen, sonst nichts voneinander.
    """

    def test_der_server_kennt_die_oberflaeche_nicht(self):
        for datei in _dateien("server"):
            with self.subTest(datei=datei.name):
                self.assertFalse(
                    any(m.startswith("mailburg.ui") for m in _importe(datei)),
                    f"{datei.relative_to(WURZEL)} importiert aus mailburg.ui",
                )

    def test_kein_qt_im_server(self):
        """Ein Dienst läuft auf einer Maschine ohne Bildschirm."""
        for datei in _dateien("server"):
            with self.subTest(datei=datei.name):
                self.assertFalse(
                    any(m.startswith("PySide6") for m in _importe(datei)),
                    f"{datei.relative_to(WURZEL)} importiert PySide6",
                )

    def test_die_oberflaeche_kennt_den_server_nicht(self):
        for datei in _dateien("ui"):
            with self.subTest(datei=datei.name):
                self.assertFalse(
                    any(m.startswith("mailburg.server") for m in _importe(datei)),
                    f"{datei.relative_to(WURZEL)} importiert aus mailburg.server",
                )


if __name__ == "__main__":
    unittest.main()
