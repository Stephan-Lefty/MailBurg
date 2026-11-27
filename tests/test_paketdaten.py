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

    def test_sie_nennt_ihr_paket(self):
        """**Ohne ``pkgname`` gibt es nichts zu deinstallieren.**

        Die Software-Verwaltung muss wissen, welches Paket zu dieser
        Anwendung gehört – sonst zeigt sie MailBurg gar nicht erst
        unter den installierten Programmen an. Bei Paketen aus einer
        Distributionsquelle ergänzt das der AppStream-Generator der
        Distribution; bei einem von Hand installierten ``.deb`` tut
        es niemand.

        Gemeldet von Stephan am 2026-11-25 auf einem frischen
        GuideOS: »MailBurg erscheint nicht unter Software, um es zu
        deinstallieren.«
        """
        wurzel = ET.parse(
            _paketdaten() / "de.stephanlefty.MailBurg.metainfo.xml"
        ).getroot()

        self.assertEqual(wurzel.findtext("pkgname"), "mailburg")

    def test_sie_haelt_der_pruefung_von_appstream_stand(self):
        """**Gegen das Werkzeug der Sache, nicht gegen meine Annahme.**

        ``appstreamcli`` kennt die Spezifikation; ich kenne sie
        ungefähr. Wo es fehlt – etwa auf dem Bauserver –, wird der
        Test übersprungen statt grün zu melden.

        **Mit ``--no-net``, und das ist kein Nachlassen.** Ohne den
        Schalter ruft das Werkzeug jede ``<url>`` in der Datei ab und
        wertet einen Fehler als Beanstandung. Am 2026-11-27 war der
        Test deshalb rot, weil GitHub für die README-Adresse ein 503
        lieferte – eine Minute später wäre er grün gewesen.

        Geprüft werden soll die Datei, nicht die Erreichbarkeit eines
        fremden Servers. *Ein Test, der ohne eigenes Zutun rot wird,
        gewöhnt einem das Hinsehen ab* – und dann übersieht man den
        Lauf, der zu Recht rot ist.
        """
        import shutil
        import subprocess

        werkzeug = shutil.which("appstreamcli")
        if not werkzeug:
            self.skipTest("appstreamcli ist hier nicht installiert")

        datei = _paketdaten() / "de.stephanlefty.MailBurg.metainfo.xml"
        lauf = subprocess.run(
            [werkzeug, "validate", "--no-net", str(datei)],
            capture_output=True, text=True, check=False,
        )

        self.assertEqual(
            lauf.returncode, 0,
            f"appstreamcli beanstandet die Datei:\n{lauf.stdout}{lauf.stderr}",
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

    def test_das_debian_paket_legt_sie_auch_hin(self):
        """**Der zweite Installationsweg, und er tat es nicht.**

        ``install.sh`` kopiert die Datei seit jeher nach
        ``~/.local/share/metainfo``. Das Debian-Paket nahm sie nur als
        Python-Paketdatei unter ``dist-packages/mailburg/paketdaten/``
        mit – ein Ort, an dem keine Software-Verwaltung sucht. In
        GNOME Software, KDE Discover und Cinnamons
        Anwendungsverwaltung gab es MailBurg damit nicht: weder zum
        Nachsehen noch zum Entfernen.

        *Zwei Wege, einer nachgezogen, der andere nicht* – zum
        wiederholten Mal in diesem Projekt.

        Aufgefallen am 2026-11-24, als klar wurde, dass MailBurg
        Bestandteil von GuideOS wird. Dort ist das Paket der einzige
        Installationsweg, und die Anwendungsverwaltung die Stelle, an
        der man ein Programm sucht, das man nicht selbst installiert
        hat.

        **Geprüft wird ``debian/rules``, und das war es hier bis zum
        2026-11-27 nicht.** Der Test las ``werkzeuge/deb_bauen.py`` –
        aus dieser Datei wird seit dem 06.11. kein ausgeliefertes
        Paket mehr gebaut, die CI nimmt ``dpkg-buildpackage``. Er war
        grün und sagte nichts über das Paket, das beim Anwender
        ankommt.

        *Eine Prüfung, die die fragliche Umgebung nicht nachstellt,
        misst etwas anderes* – hier zum wiederholten Mal, und diesmal
        an einer Datei, die es noch gibt und die nur nichts mehr tut.
        """
        rules = (Path(__file__).resolve().parent.parent
                 / "debian" / "rules").read_text(encoding="utf-8")

        self.assertIn("usr/share/metainfo", rules,
                      "Das Paket legt die Datei nicht an ihren Ort")
        self.assertIn("metainfo.xml", rules,
                      "Das Paket holt sie nicht aus dem Python-Paket")


if __name__ == "__main__":
    unittest.main()
