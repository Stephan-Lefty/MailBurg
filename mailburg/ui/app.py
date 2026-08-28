"""Der Einstieg in die grafische Oberfläche.

Beim ersten Start gibt es weder Archiv noch Konten – dann führt der
Assistent durch die Einrichtung. Danach merkt sich MailBurg, welches Archiv
zuletzt offen war, und öffnet es gleich wieder. Wer beim Start jedes Mal
gefragt würde, wo denn sein Archiv liege, würde sich zu Recht wundern.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mailburg import APP_NAME, __version__
from mailburg.core import paths


def _datei() -> Path:
    return paths.config_dir() / "oberflaeche.json"


def gemerktes() -> dict:
    """Alles, was sich die Oberfläche von Sitzung zu Sitzung merkt."""
    try:
        inhalt = json.loads(_datei().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return inhalt if isinstance(inhalt, dict) else {}


def merken_unter(schluessel: str, wert) -> None:
    """Ändert einen Eintrag, ohne die übrigen zu verlieren.

    Die frühere Fassung schrieb die Datei jedes Mal komplett neu. Damit
    hätte das Merken des Archivs die gemerkte Fenstergröße gelöscht – ein
    Fehler, der erst Wochen später als »das Fenster vergisst wieder alles«
    aufgefallen wäre.
    """
    stand = gemerktes()
    stand[schluessel] = wert
    try:
        _datei().write_text(
            json.dumps(stand, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        # Sich etwas nicht merken zu können ist ärgerlich, aber kein
        # Grund, das Programm nicht zu starten.
        pass


def zuletzt_gemerkt() -> Path | None:
    """Das Archiv, das zuletzt offen war."""
    pfad = gemerktes().get("archiv")
    if not pfad:
        return None
    ort = Path(pfad)
    # Nur wenn dort auch heute noch ein Archiv liegt: Eine externe Platte
    # kann abgezogen sein, ein Ordner umbenannt.
    return ort if (ort / "archive.json").exists() else None


#: So viele Archive stehen im Menü. Wenige genug, dass die Liste nicht
#: selbst zur Suche wird.
ZULETZT = 6


def merken(pfad: Path) -> None:
    merken_unter("archiv", str(pfad))

    # Die zuletzt benutzten obenauf, ohne Doppelungen. Wer zwei Archive
    # führt - ein geschäftliches und ein privates -, wechselt ständig
    # zwischen ihnen und soll dafür keinen Dateidialog brauchen.
    liste = [str(pfad)] + [p for p in zuletzt_benutzte_pfade() if p != str(pfad)]
    merken_unter("zuletzt", liste[:ZULETZT])


def zuletzt_benutzte_pfade() -> list[str]:
    """Die zuletzt geöffneten Archive, ungeprüft."""
    liste = gemerktes().get("zuletzt", [])
    return [p for p in liste if isinstance(p, str)]


def zuletzt_benutzte() -> list[Path]:
    """Die zuletzt geöffneten Archive, die es auch heute noch gibt.

    Eine externe Platte kann abgezogen, ein Ordner umbenannt sein. Ein
    Menüeintrag, der ins Leere führt, ist ärgerlicher als ein fehlender.
    """
    return [Path(p) for p in zuletzt_benutzte_pfade()
            if (Path(p) / "archive.json").exists()]


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

    symbol = _symbol()
    if symbol is not None:
        anwendung.setWindowIcon(symbol)

    # Ein Archiv als Argument geht allem vor - damit lässt sich MailBurg
    # aus dem Dateimanager heraus mit einem bestimmten Archiv öffnen.
    archiv = Path(argv[1]) if len(argv) > 1 and not argv[1].startswith("-") else None
    if archiv is None:
        archiv = zuletzt_gemerkt()

    if archiv is None:
        from mailburg.ui.assistent import Einrichtungsassistent

        assistent = Einrichtungsassistent()
        if not assistent.exec():
            return 0
        archiv = assistent.archiv_pfad
        if archiv is None:
            return 0

    from mailburg.ui.hauptfenster import Hauptfenster

    fenster = Hauptfenster(archiv)
    if fenster.archiv is None:
        return 1

    merken(archiv)
    fenster.show()
    return anwendung.exec()


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
    from PySide6.QtCore import QLibraryInfo, QTranslator

    uebersetzer = QTranslator()
    ort = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    if uebersetzer.load("qtbase_de", ort):
        anwendung.installTranslator(uebersetzer)
        return uebersetzer
    return None


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
