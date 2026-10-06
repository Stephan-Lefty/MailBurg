"""Das Einrichtungsfenster geht so hoch auf, wie sein Inhalt ist.

**Stephans Regel vom 31.08.2026:** In der Vorgabegröße wird nicht
gerollt. Der Rollbereich ist die Rückfalllinie für kleine Bildschirme,
nicht der Normalzustand.

**Der Anlass ist ein eigener Fehler vom 06.10.2026.** Das Fenster
bekam einen Rollbereich, weil siebzehn Prüfzeilen, ein Wartungskasten
und ein Protokoll auf einem kleinen Serverbildschirm nicht mehr
hineinpassten. Danach stand als Anfangsgröße weiter ``self.sizeHint()``
– und ein Rollbereich meldet nach außen nur, dass er rollen *kann*,
nicht, wie hoch sein Inhalt ist. Das Fenster ging 691 px hoch auf,
während der Bildschirm noch 392 px frei hatte, und rollte vom ersten
Augenblick an.

**Der Kommentar darüber sagte dabei das Richtige** (»Die Anfangsgröße
kommt aus dem Inhalt«) – nur der Code tat es nicht. Dritte Instanz
derselben Klasse an einem Tag: Ein Kommentar, der eine Zusage macht,
schuldet einen Test dazu.

Gefunden hat es nicht dieser Test, sondern ``werkzeuge/lesbarkeit.py``
in der CI. Dieser hier hält es fest, damit es nicht beim nächsten Umbau
des Fensters wieder verlorengeht.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QScrollArea
except ImportError:  # pragma: no cover
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 ist nicht installiert")
class AnfangsgroesseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _fenster(self):
        from mailburg.ui.servereinrichtung import Einrichtungsfenster

        fenster = Einrichtungsfenster()
        self.addCleanup(fenster.deleteLater)
        return fenster

    def test_das_fenster_nutzt_den_platz_aus(self):
        """**Der Befund, um den es geht – und er ist überall prüfbar.**

        Ein erster Anlauf verglich die Fensterhöhe mit der Höhe des
        Inhalts und übersprang sich selbst, wenn der Bildschirm
        kleiner ist. Gemessen auf dem Prüfbildschirm: Der Inhalt
        braucht 1073 px, der Bildschirm hat 800 – der Test lief
        **nie**. Ein Test, der sich stillschweigend überspringt, ist
        keiner; das ist dieselbe Klasse wie ein Auffangnetz, das eine
        Auskunft erfindet.

        Verlangt wird deshalb nicht »es rollt nicht«, sondern die
        Regel, aus der das folgt: **Das Fenster nimmt sich so viel
        Höhe, wie der Inhalt braucht – und wenn der Bildschirm kleiner
        ist, dessen ganze Höhe.** Auf einem großen Bildschirm heißt das
        »nichts rollt«, auf einem kleinen »der Rollbalken fängt erst an,
        wo der Platz endet«.

        Mit ``self.sizeHint()`` war die Fensterhöhe 408 px bei 800 px
        Platz – dieser Test wird dadurch rot.
        """
        fenster = self._fenster()
        rollen = fenster.centralWidget()

        self.assertIsInstance(
            rollen, QScrollArea, "Ohne Rollbereich prüft dieser Test nichts."
        )
        noetig = rollen.widget().sizeHint().height()
        schirm = fenster.screen()
        platz = schirm.availableGeometry().height() if schirm else noetig

        self.assertGreaterEqual(
            fenster.height(),
            min(noetig, platz),
            f"Das Fenster geht {fenster.height()} px hoch auf. Der Inhalt "
            f"braucht {noetig} px, der Bildschirm bietet {platz} px – es "
            f"rollt also früher als nötig.",
        )

    def test_es_bleibt_auf_dem_bildschirm(self):
        """Die andere Richtung, und sie ist der Grund für den
        Rollbereich: Lieber ein Rollbalken als Knöpfe, an die niemand
        herankommt."""
        fenster = self._fenster()
        schirm = fenster.screen()
        if schirm is None:  # pragma: no cover
            self.skipTest("Kein Bildschirm gemeldet.")

        self.assertLessEqual(
            fenster.height(), schirm.availableGeometry().height()
        )

    def test_auch_bei_grosser_schrift(self):
        """**Geratene Maße sitzen falsch, sobald jemand die Schrift
        ändert** – und in MailBurg lässt sie sich einstellen. Dieser
        Test ist der Grund, warum die Höhe gerechnet und nicht
        hingeschrieben wird.
        """
        schrift = self.app.font()
        gross = type(schrift)(schrift)
        gross.setPointSize(20)
        self.app.setFont(gross)
        self.addCleanup(self.app.setFont, schrift)

        fenster = self._fenster()
        rollen = fenster.centralWidget()
        noetig = rollen.widget().sizeHint().height()
        schirm = fenster.screen()
        platz = schirm.availableGeometry().height() if schirm else noetig

        # Bei 20 pt kann der Inhalt den Bildschirm überschreiten. Dann
        # ist die Antwort nicht »größer werden«, sondern »rollen« – und
        # genau das wird hier verlangt.
        self.assertGreaterEqual(fenster.height(), min(noetig, platz))
