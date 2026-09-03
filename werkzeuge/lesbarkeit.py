"""Sucht Stellen, an denen die Oberfläche Text abschneidet.

**Warum es dafür ein Werkzeug braucht.** Abgeschnittener Text fällt beim
Bauen nie auf: Der Entwickler kennt den Satz, der dort steht, und liest
ihn im Quelltext. Er sieht »Nötig ist nur, dass Sie angemeldet sind: Die
Passwörter liegen im Schlüsselbund, und der öffnet sich« und weiß, wie es
weitergeht. Der Anwender sieht einen Satz, der mitten im Wort aufhört.

Am 2026-08-31 hat Stephan zwei solche Stellen im selben Fenster gemeldet
– ein Auswahlfeld, in dem der längste Eintrag nicht las bar war, und
darunter zwei Absätze, die unten wegliefen. Beides in einem Dialog, den
es seit Wochen gibt.

Geprüft wird dreierlei:

*Auswahlfelder* – ist die Box breit genug für ihren längsten Eintrag?

*Beschriftungen mit Umbruch* – reicht die Höhe für den umgebrochenen
Text? ``heightForWidth`` sagt, wie hoch er bei dieser Breite würde.

*Fenster* – passt der Inhalt überhaupt hinein, oder ist das Fenster
kleiner als das, was es zeigen soll?

Aufruf::

    QT_QPA_PLATFORM=offscreen python3 werkzeuge/lesbarkeit.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

#: Wie viele Pixel Unterschied noch als »passt« gelten. Schriftmaße
#: schwanken zwischen Systemen um ein, zwei Pixel; darunter wäre jede
#: Meldung Rauschen.
TOLERANZ = 4


def _befunde(fenster, name: str) -> list[str]:
    from PySide6.QtWidgets import QComboBox, QLabel

    gefunden: list[str] = []

    for box in fenster.findChildren(QComboBox):
        if not box.count():
            continue
        gebraucht = box.sizeHint().width()
        vorhanden = box.width()
        if vorhanden and gebraucht - vorhanden > TOLERANZ:
            laengster = max(
                (box.itemText(i) for i in range(box.count())), key=len
            )
            gefunden.append(
                f"{name}: Auswahlfeld »{box.accessibleName() or box.objectName()}« "
                f"ist {vorhanden} px breit, braucht {gebraucht} px "
                f"(längster Eintrag: »{laengster}«)"
            )

    for schild in fenster.findChildren(QLabel):
        if not schild.wordWrap() or not schild.text().strip():
            continue
        breite = schild.width()
        if breite <= 0:
            continue
        gebraucht = schild.heightForWidth(breite)
        vorhanden = schild.height()
        if gebraucht - vorhanden > TOLERANZ:
            anfang = " ".join(schild.text().split())[:60]
            gefunden.append(
                f"{name}: Text abgeschnitten – {vorhanden} px hoch, "
                f"braucht {gebraucht} px: »{anfang}…«"
            )

    # **In der Standardgröße muss alles ohne Rollen lesbar sein.**
    # Stephans Regel vom 2026-08-31, und sie ist richtig: Ein Fenster,
    # in dem man scrollen muss, um eine Erklärung zu Ende zu lesen, ist
    # ein schlechtes Fenster. Der Rollbereich ist die Rückfalllinie für
    # kleine Bildschirme, nicht der Normalzustand.
    #
    # Gemeldet wird deshalb, wenn ein Rollbalken schon beim Öffnen etwas
    # zu rollen hat – und zwar nur dann, wenn der Bildschirm überhaupt
    # Platz gehabt hätte.
    from PySide6.QtWidgets import QApplication, QScrollArea

    rollbereiche = fenster.findChildren(QScrollArea)
    for bereich in rollbereiche:
        balken = bereich.verticalScrollBar()
        if balken is None or balken.maximum() <= TOLERANZ:
            continue
        # **Am Fenster messen, nicht am Bauteil.** Eine
        # Assistentenseite ist kein Fenster; ihre Höhe ist die des
        # Assistenten minus Kopfzeile und Knopfleiste. Wer sie gegen die
        # Bildschirmhöhe hält, bekommt immer »da wäre noch Platz« –
        # auch wenn der Assistent längst so groß ist, wie er werden
        # kann.
        echtes = fenster.window()
        schirm = QApplication.primaryScreen()
        platz = schirm.availableGeometry().height() if schirm else 0
        if platz and echtes.height() < platz - 150:
            gefunden.append(
                f"{name}: rollt schon beim Öffnen ({balken.maximum()} px), "
                f"obwohl der Bildschirm noch "
                f"{platz - fenster.height()} px Platz hätte"
            )

    if rollbereiche:
        return gefunden

    inhalt = fenster.sizeHint()
    if inhalt.height() - fenster.height() > TOLERANZ:
        gefunden.append(
            f"{name}: Fenster ist {fenster.height()} px hoch, der Inhalt "
            f"braucht {inhalt.height()} px"
        )
    if inhalt.width() - fenster.width() > TOLERANZ:
        gefunden.append(
            f"{name}: Fenster ist {fenster.width()} px breit, der Inhalt "
            f"braucht {inhalt.width()} px"
        )
    return gefunden


def _zeigen(fenster, anwendung, breite=0, hoehe=0):
    """Zeigt ein Fenster so, wie es beim Anwender aufgeht."""
    if breite and hoehe:
        fenster.resize(breite, hoehe)
    fenster.show()
    anwendung.processEvents()
    return fenster


def pruefen() -> list[str]:
    """Geht die Fenster durch und sammelt, was nicht hineinpasst."""
    from unittest import mock

    from PySide6.QtWidgets import QApplication

    from mailburg.ui import farben

    anwendung = QApplication.instance() or QApplication([])
    anwendung.setStyle("Fusion")
    farben.auswahlfelder_verbreitern(anwendung)

    befunde: list[str] = []
    import tempfile

    from mailburg.core import paths
    from mailburg.core.archive import Archive, Mode

    with tempfile.TemporaryDirectory() as ordner:
        basis = Path(ordner)
        with mock.patch.object(paths, "data_dir", return_value=basis / "daten"):
            (basis / "daten").mkdir(parents=True, exist_ok=True)
            archiv = Archive.create(
                basis / "Archiv", mode=Mode.GESCHAEFTLICH, name="Probe"
            )
            try:
                befunde += _dialoge(anwendung, archiv)
            finally:
                archiv.close()

    return befunde


def _dialoge(anwendung, archiv) -> list[str]:
    """Jeden Dialog einmal aufmachen und nachmessen."""
    befunde: list[str] = []

    from mailburg.ui.zeitplan import Zeitplandialog

    fenster = _zeigen(Zeitplandialog(archiv=archiv.root), anwendung)
    befunde += _befunde(fenster, "Zeitplan »Was von selbst laufen soll«")
    fenster.close()

    from mailburg.ui.assistent import Einrichtungsassistent

    # Keine erfundene Größe: Der Assistent bemisst sich seit dem
    # 2026-08-31 selbst am Bildschirm. Ihn hier zu verkleinern hieße,
    # etwas anderes zu prüfen, als der Anwender zu sehen bekommt.
    assistent = Einrichtungsassistent()
    assistent.show()
    anwendung.processEvents()
    for kennung in assistent.pageIds():
        assistent.setStartId(kennung)
        assistent.restart()
        anwendung.processEvents()
        seite = assistent.page(kennung)
        befunde += _befunde(seite, f"Assistent, Seite »{seite.title()}«")
    assistent.close()

    from mailburg.ui.suchmaske import Suchmaske

    fenster = _zeigen(Suchmaske(archiv), anwendung)
    befunde += _befunde(fenster, "Suchmaske")
    fenster.close()

    from mailburg.ui.regeln import Regeldialog

    fenster = _zeigen(Regeldialog(archiv=archiv), anwendung)
    befunde += _befunde(fenster, "Einstufungsregeln")
    fenster.close()

    from mailburg.ui.sichern import Sicherungsdialog

    fenster = _zeigen(Sicherungsdialog(archiv), anwendung)
    befunde += _befunde(fenster, "Sichern")
    fenster.close()

    from mailburg.ui.einlesen import Einlesedialog

    fenster = _zeigen(Einlesedialog(archiv), anwendung)
    befunde += _befunde(fenster, "Lokale Mailordner einlesen")
    fenster.close()

    from mailburg.ui.zurueckspielen import Rueckspieldialog

    fenster = _zeigen(Rueckspieldialog(archiv), anwendung)
    befunde += _befunde(fenster, "Ins Dateisystem zurückspielen")
    fenster.close()

    from mailburg.ui.zugaenge import Zugangsdialog

    fenster = _zeigen(Zugangsdialog(archiv=archiv), anwendung)
    befunde += _befunde(fenster, "Zugänge")
    fenster.close()

    from mailburg.ui.archivpasswort import NeuesPasswortFragen, PasswortFragen

    fenster = _zeigen(NeuesPasswortFragen(), anwendung)
    befunde += _befunde(fenster, "Archiv verschlüsseln")
    fenster.close()

    fenster = _zeigen(PasswortFragen(archivname="Probe"), anwendung)
    befunde += _befunde(fenster, "Archiv öffnen")
    fenster.close()

    return befunde


def main() -> int:
    befunde = pruefen()
    if not befunde:
        print("Nichts abgeschnitten – alle geprüften Fenster sind lesbar.")
        return 0

    print(f"{len(befunde)} Stellen, an denen Text nicht hineinpasst:\n")
    for zeile in befunde:
        print(f"  {zeile}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
