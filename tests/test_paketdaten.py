"""Die Angaben für die Software-Verwaltung.

**Ohne sie kennt GNOME Software, Discover oder pamac MailBurg nicht.**
Es erscheint dort weder unter den installierten Programmen noch lässt es
sich von dort entfernen – wer es loswerden will, muss ins Terminal.

Am 2026-11-05 ist genau das bei KALENDERBlick aufgefallen, einem
Schwesterprogramm: Die Datei lag *neben* dem Paket, und damit kam sie
bei keiner Installationsart an. Hier liegt sie von vornherein im Paket,
und dieser Test hält das fest.

Dieselbe Lehre wie beim Wappen am 2026-10-02 (siehe
``tests/test_lesen.py``): **Was ausgeliefert werden soll, gehört ins
Paket** – alles daneben nimmt ``pip install`` nicht mit, und auf einem
Rechner mit Quelltext fällt das nie auf.
"""

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


def _paketdaten() -> Path:
    """Der Ordner im Paket, nicht der im Quellbaum.

    Über ``mailburg.__file__`` gefragt, damit der Test dasselbe sieht
    wie eine Installation beim Anwender.
    """
    import mailburg

    return Path(mailburg.__file__).resolve().parent / "paketdaten"


class PaketdatenTest(unittest.TestCase):
    def test_die_appstream_datei_liegt_im_paket(self):
        """Sonst kommt sie bei ``pip install`` nicht mit."""
        datei = _paketdaten() / "de.stephanlefty.MailBurg.metainfo.xml"

        self.assertTrue(
            datei.is_file(),
            "de.stephanlefty.MailBurg.metainfo.xml fehlt unter "
            "mailburg/paketdaten/ – beim Anwender erschiene MailBurg in "
            "keiner Software-Verwaltung",
        )

    def test_die_datei_ist_wohlgeformt(self):
        """Eine kaputte Datei wird stillschweigend übergangen - die
        Software-Verwaltung zeigt dann schlicht nichts an."""
        datei = _paketdaten() / "de.stephanlefty.MailBurg.metainfo.xml"
        wurzel = ET.parse(datei).getroot()

        self.assertEqual(wurzel.tag, "component")
        self.assertEqual(wurzel.get("type"), "desktop-application")

    def test_kennung_und_menueeintrag_gehoeren_zusammen(self):
        """``<launchable>`` verknüpft beides.

        Zeigt es auf eine andere Datei als die, die ``install.sh``
        anlegt, findet die Software-Verwaltung das Programm nicht -
        sie sucht nach dem Namen aus der Kennung.
        """
        wurzel = ET.parse(
            _paketdaten() / "de.stephanlefty.MailBurg.metainfo.xml"
        ).getroot()

        kennung = wurzel.findtext("id")
        startbar = wurzel.findtext("launchable")

        self.assertEqual(kennung, "de.stephanlefty.MailBurg")
        self.assertEqual(startbar, f"{kennung}.desktop")

        geschrieben = Path(__file__).resolve().parent.parent / "install.sh"
        self.assertIn(
            f"{kennung}.desktop",
            geschrieben.read_text(encoding="utf-8"),
            "install.sh legt einen anders benannten Menüeintrag an",
        )

    def test_die_fassung_stimmt_mit_dem_programm_ueberein(self):
        """Eine veraltete Angabe lässt die Software-Verwaltung eine
        Aktualisierung anbieten, die es nicht gibt."""
        import mailburg

        wurzel = ET.parse(
            _paketdaten() / "de.stephanlefty.MailBurg.metainfo.xml"
        ).getroot()
        fassungen = [e.get("version") for e in wurzel.iter("release")]

        self.assertTrue(fassungen, "keine <release>-Angabe")
        self.assertEqual(
            fassungen[0],
            mailburg.__version__,
            "die neueste genannte Fassung ist nicht die laufende",
        )

    def test_install_richtet_die_datei_ein(self):
        """**Im Paket zu liegen genügt nicht.**

        Die Arbeitsumgebung sucht sie unter ``~/.local/share/metainfo``.
        Wer sie nur mitliefert, hat sie nirgends.
        """
        skript = (Path(__file__).resolve().parent.parent
                  / "install.sh").read_text(encoding="utf-8")

        self.assertIn("metainfo", skript,
                      "install.sh kopiert die Datei nicht an ihren Ort")
        self.assertIn("paketdaten", skript,
                      "install.sh holt sie nicht aus dem Paket")


if __name__ == "__main__":
    unittest.main()
