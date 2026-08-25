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


def zuletzt_gemerkt() -> Path | None:
    """Das Archiv, das zuletzt offen war."""
    datei = paths.config_dir() / "oberflaeche.json"
    try:
        pfad = json.loads(datei.read_text(encoding="utf-8")).get("archiv")
    except (OSError, json.JSONDecodeError):
        return None
    if not pfad:
        return None
    ort = Path(pfad)
    # Nur wenn dort auch heute noch ein Archiv liegt: Eine externe Platte
    # kann abgezogen sein, ein Ordner umbenannt.
    return ort if (ort / "archive.json").exists() else None


def merken(pfad: Path) -> None:
    datei = paths.config_dir() / "oberflaeche.json"
    try:
        datei.write_text(
            json.dumps({"archiv": str(pfad)}, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        # Sich das letzte Archiv nicht merken zu können ist ärgerlich,
        # aber kein Grund, das Programm nicht zu starten.
        pass


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
    anwendung.setApplicationName(APP_NAME)
    anwendung.setApplicationDisplayName(APP_NAME)
    anwendung.setApplicationVersion(__version__)
    anwendung.setDesktopFileName("de.stephanlefty.MailBurg")

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
    """Das Programmsymbol, falls es neben dem Quelltext liegt."""
    from PySide6.QtGui import QIcon

    for ort in (
        Path(__file__).resolve().parent.parent.parent / "assets" / "icon.svg",
        Path("/usr/share/icons/hicolor/scalable/apps/mailburg.svg"),
    ):
        if ort.exists():
            return QIcon(str(ort))
    return None


if __name__ == "__main__":
    sys.exit(main())
