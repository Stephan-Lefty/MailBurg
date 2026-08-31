"""Der Einstieg in die grafische Oberfläche.

Beim ersten Start gibt es weder Archiv noch Konten – dann führt der
Assistent durch die Einrichtung. Danach merkt sich MailBurg, welches Archiv
zuletzt offen war, und öffnet es gleich wieder. Wer beim Start jedes Mal
gefragt würde, wo denn sein Archiv liege, würde sich zu Recht wundern.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mailburg import APP_NAME, __version__
from mailburg.core.einstellungen import merken, zuletzt_gemerkt


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    if len(argv) > 1 and argv[1] in ("--version", "-V"):
        print(f"{APP_NAME} {__version__}")
        return 0

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "Für die grafische Oberfläche fehlt PySide6.\n"
            "Nachrüsten mit:  pip install 'mailburg[oberflaeche]'\n"
            "Die Kommandozeile läuft auch ohne:  mailburg --help",
            file=sys.stderr,
        )
        return 2

    _fehler_zeigen_statt_sterben()

    anwendung = QApplication(argv)
    # Muss am Objekt hängen bleiben: Ein Übersetzer, auf den niemand mehr
    # zeigt, wird weggeräumt – und die Knöpfe stehen wieder auf Englisch.
    anwendung._uebersetzer = _deutsch(anwendung)
    # **Kein Anzeigename.** Qt hängt ihn jedem Fenstertitel an, und die
    # Fenster nennen das Programm bereits selbst - heraus kam
    # "MailBurg – Mailarchiv - MailBurg". Am 2026-08-28 in der gepackten
    # Windows-Fassung aufgefallen, wo es besonders auffiel.
    anwendung.setApplicationName(APP_NAME)
    anwendung.setApplicationVersion(__version__)
    anwendung.setDesktopFileName("de.stephanlefty.MailBurg")

    # **Kanten für alle Fenster, nicht nur fürs Hauptfenster.** Zwischen
    # Fensterhintergrund und Inhaltsbereich liegt ein Kontrastverhältnis
    # von 1,15 – das liest kein Auge als Grenze. Am schwersten wiegt das
    # in der Ersteinrichtung: Sie ist der erste Eindruck, und dort
    # entscheidet sich, ob jemand dem Programm seine Post anvertraut.
    # Die Farbe kommt aus der Palette des Themas, damit
    # Hochkontrast-Themen unangetastet bleiben.
    from mailburg.ui import farben

    anwendung.setStyleSheet(farben.bereichsrahmen())
    farben.platzhalter_aufhellen(anwendung)
    farben.auswahlfelder_verbreitern(anwendung)

    symbol = _symbol()
    if symbol is not None:
        anwendung.setWindowIcon(symbol)

    # Ein Archiv als Argument geht allem vor - damit lässt sich MailBurg
    # aus dem Dateimanager heraus mit einem bestimmten Archiv öffnen.
    archiv = Path(argv[1]) if len(argv) > 1 and not argv[1].startswith("-") else None
    if archiv is None:
        archiv = zuletzt_gemerkt()

    # **Ob der Assistent lief und ob er abrufen soll.** Beim ersten Start
    # wird beides hier entschieden; das Hauptfenster erfährt es sonst
    # nicht.
    gleich_abrufen = False

    if archiv is None:
        from mailburg.ui.assistent import Einrichtungsassistent

        assistent = Einrichtungsassistent()
        if not assistent.exec():
            return 0
        archiv = assistent.archiv_pfad
        if archiv is None:
            return 0
        gleich_abrufen = getattr(assistent, "soll_abrufen", False)

    from mailburg.ui.hauptfenster import Hauptfenster

    fenster = Hauptfenster(archiv)
    # **Ein laufender Indexaufbau ist kein Fehlschlag.** Während er läuft,
    # ist ``archiv`` absichtlich None: Das eigene Handle muss weg, weil
    # der Aufbau selbst in den Index schreibt. Ohne die zweite Bedingung
    # sah das hier aus wie »Archiv lässt sich nicht öffnen«, und MailBurg
    # beendete sich, kaum dass jemand im Dialog auf »Ja« geklickt hatte.
    #
    # Am 2026-08-31 von Stephan gemeldet: Fenster zu, kein Aufbau, keine
    # Meldung. Nicht in den Tests aufgefallen, sondern beim ersten Start
    # der 1.0 an einem Archiv aus 0.12 – also auf genau dem Weg, den nach
    # einer Aktualisierung jeder geht.
    if fenster.archiv is None and not fenster.baut_auf:
        return 1

    merken(archiv)
    fenster.show()

    if gleich_abrufen:
        # **Erst wenn die Ereignisschleife läuft.** Der Abruf zeigt
        # Meldungen und einen Fortschrittsbalken; direkt hier aufgerufen
        # hätte er kein Fenster, an dem er hängen kann. Der Umweg über
        # den Zeitgeber stellt ihn hinter das erste Zeichnen.
        #
        # Am 2026-08-28 unter Windows aufgefallen: Das Häkchen »Jetzt
        # den ersten Abruf starten« stand auf der Abschlussseite, war
        # angekreuzt - und nichts geschah. Erst F5 holte die Post. Beim
        # zweiten Archiv (Archiv -> Neues Archiv) hatte es immer
        # funktioniert; nur der Weg, den jeder neue Anwender geht, war
        # der ungeprüfte.
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, fenster._abrufen)

    code = anwendung.exec()

    # **Zuletzt aufräumen.** Wer eine Nachricht »In Mailprogramm öffnen«
    # gewählt hat, hinterlässt eine vollständige .eml im Cache. Sie soll
    # nicht bis zum nächsten Start dort liegen bleiben.
    from mailburg.core import rueckgabe

    rueckgabe.aufraeumen_beim_beenden()
    return code


def _fehler_zeigen_statt_sterben() -> None:
    """Sorgt dafür, dass ein Programmfehler sichtbar wird.

    Qt bricht das Programm ab, wenn in einem Signalempfänger eine Ausnahme
    hochkommt – ohne Meldung, ohne Spur. Für den Anwender sieht das aus,
    als sei das Fenster einfach verschwunden. Bei einem Programm, dem er
    seine Post anvertraut, ist das der denkbar schlechteste Eindruck: Er
    weiß nicht, ob dabei etwas kaputtgegangen ist.

    Der Haken hier fängt das ab und zeigt, was passiert ist. Am Archiv
    kann dabei nichts zu Schaden kommen – es wird nur beim Aufnehmen
    beschrieben, und dort sichert die Reihenfolge Ablage-Journal-Index
    ohnehin gegen Abbrüche ab.
    """
    import traceback

    def haken(art, wert, spur):
        if issubclass(art, KeyboardInterrupt):
            sys.__excepthook__(art, wert, spur)
            return

        text = "".join(traceback.format_exception(art, wert, spur))
        print(text, file=sys.stderr)

        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is None:
                return
            fenster = QMessageBox()
            fenster.setIcon(QMessageBox.Critical)
            fenster.setWindowTitle("Da ist etwas schiefgegangen")
            fenster.setText(
                f"In MailBurg ist ein Fehler aufgetreten:\n\n{art.__name__}: {wert}"
            )
            fenster.setInformativeText(
                "Ihr Archiv ist davon nicht betroffen – es wird nur beim "
                "Aufnehmen von Post beschrieben, und dabei ist gegen "
                "Abbrüche vorgesorgt.\n\n"
                "Sie können weiterarbeiten. Wenn der Fehler wiederkehrt, "
                "helfen die Einzelheiten unten beim Beheben."
            )
            fenster.setDetailedText(text)
            fenster.exec()
        except Exception:  # noqa: BLE001 – im Fehlerfall nicht noch mehr Fehler
            pass

    sys.excepthook = haken


def _deutsch(anwendung):
    """Stellt Qts eigene Beschriftungen auf Deutsch.

    »Next«, »Cancel«, »Yes«, »No«, die Dateiauswahl – all das kommt aus Qt
    und wäre sonst englisch, während MailBurg selbst deutsch spricht. Diese
    Mischung ist das Unangenehmste von beidem.

    Fest auf Deutsch und nicht nach Systemsprache: Das Programm ist von
    Grund auf deutsch, seine Meldungen sind es und die Suchsprache auch.
    Englische Knöpfe daneben wären kein Entgegenkommen, sondern ein Bruch.
    """
    from PySide6.QtCore import QTranslator

    uebersetzer = QTranslator()
    for ort in _uebersetzungsorte():
        if uebersetzer.load("qtbase_de", ort):
            anwendung.installTranslator(uebersetzer)
            return uebersetzer
    return None


def _uebersetzungsorte() -> list[str]:
    """Wo ``qtbase_de.qm`` liegen kann – in dieser Reihenfolge.

    ``QLibraryInfo.TranslationsPath`` liefert den Pfad, der beim Bau von
    Qt einkompiliert wurde. In der gepackten ``.exe`` zeigt der ins
    Leere: Dort liegt alles in einem Ordner, den PyInstaller beim Start
    frisch auspackt, und dessen Name bei jedem Lauf ein anderer ist.

    Die Folge war eine halbdeutsche Oberfläche – MailBurg auf Deutsch,
    daneben »Look in«, »Directory« und »Choose« im Ordnerdialog, weil
    der von Qt kommt. Am 2026-08-30 unter Windows aufgefallen. Die
    Übersetzungen waren die ganze Zeit in der .exe enthalten, nur nicht
    an der Stelle, an der gesucht wurde.
    """
    import sys
    from pathlib import Path

    from PySide6.QtCore import QLibraryInfo

    orte = [QLibraryInfo.path(QLibraryInfo.TranslationsPath)]

    # Der Ordner, in den die gepackte Fassung sich auspackt.
    gepackt = getattr(sys, "_MEIPASS", None)
    if gepackt:
        orte.append(str(Path(gepackt) / "PySide6" / "translations"))

    # Und neben dem Modul selbst – so liegt es in einer gewöhnlichen
    # Installation aus dem Paketverzeichnis.
    try:
        import PySide6

        neben = Path(PySide6.__file__).resolve().parent
        orte.append(str(neben / "Qt" / "translations"))
        orte.append(str(neben / "translations"))
    except Exception:  # pragma: no cover – ohne PySide6 kämen wir nicht her
        pass

    return orte


def _symbol():
    """Das Programmsymbol – wo auch immer es diesmal liegt.

    Drei Fälle, und der letzte fehlte lange. Neben dem Quelltext, wenn
    MailBurg aus dem Verzeichnis läuft. Unter ``/usr/share/icons``, wenn
    es als Paket installiert wurde. Und in einem Verzeichnis, das erst
    beim Start entsteht, wenn es eine gepackte Windows-Datei ist:
    PyInstaller entpackt sich in einen temporären Ordner und hinterlegt
    dessen Pfad in ``sys._MEIPASS``.

    Ohne den dritten Fall zeigte das Fenster unter Windows ein leeres
    Blatt – das Symbol steckte zwar in der ``.exe`` und erschien in der
    Dateiliste, aber Qt braucht es zusätzlich für das Fenster selbst.
    Bei einem Programm, das Vertrauen wecken soll, wirkt so etwas
    unnötig schäbig (2026-08-28).
    """
    from PySide6.QtGui import QIcon

    orte = []
    gepackt = getattr(sys, "_MEIPASS", None)
    if gepackt:
        # In der gepackten Fassung liegt das Windows-Symbol dabei; SVG
        # kann Qt dort ohne das Bildmodul nicht immer zeichnen.
        orte.append(Path(gepackt) / "assets" / "mailburg.ico")
        orte.append(Path(gepackt) / "assets" / "icon.svg")
    orte.append(Path(__file__).resolve().parent.parent.parent / "assets" / "icon.svg")
    orte.append(Path("/usr/share/icons/hicolor/scalable/apps/mailburg.svg"))

    for ort in orte:
        if ort.exists():
            return QIcon(str(ort))
    return None


if __name__ == "__main__":
    sys.exit(main())
