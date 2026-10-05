"""Text aus PDF-Dateien holen.

PDF ist der wichtigste Fall: Rechnungen, Verträge, Bescheide – alles, was
man später wiederfinden will, kommt als PDF. In einem Beispielarchiv machen
PDF zwar nur ein Fünftel der Anhänge aus, aber die Hälfte des Umfangs.

**Zwei Wege, in dieser Reihenfolge:**

1. ``pdftotext`` aus poppler, falls vorhanden. Deutlich schneller als alles
   in Python, weil in C geschrieben, und robuster gegenüber den vielen
   PDF-Dateien, die sich nicht an die Spezifikation halten.
2. ``pypdf``, falls installiert. Langsamer, aber ohne Fremdprogramm.

Ist keines von beidem da, bleibt der Text leer – die Mail wird trotzdem
archiviert, nur eben ohne durchsuchbaren Anhangsinhalt. Ein fehlendes
Hilfsprogramm darf niemals dazu führen, dass Post nicht gesichert wird.

**Nicht PyMuPDF**, obwohl es das schnellste wäre: Es steht unter der AGPL
und würde dieses MIT-Projekt anstecken, sobald es mitgeliefert wird.
"""

from __future__ import annotations

import contextlib
import logging
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from mailburg.core import werkzeuge

#: Mehr Text nehmen wir aus einem einzelnen Dokument nicht auf. Ein
#: tausendseitiges Handbuch macht die Suche nicht besser, den Index aber
#: deutlich größer.
MAX_ZEICHEN = 400_000

#: Nach dieser Zeit brechen wir ab. Es gibt PDF-Dateien, an denen sich jeder
#: Parser festbeißt – ein einziges davon darf keinen Archivlauf aufhalten.
ZEITGRENZE = 30


def verfuegbar() -> str | None:
    """Sagt, womit PDF gelesen werden können: ``poppler``, ``pypdf`` oder nichts."""
    if shutil.which("pdftotext"):
        return "poppler"
    try:
        import pypdf  # noqa: F401

        return "pypdf"
    except ImportError:
        return None


def _mit_poppler(daten: bytes) -> str:
    """Ruft ``pdftotext`` auf und liest das Ergebnis von der Standardausgabe."""
    # Über eine temporäre Datei, weil pdftotext auf der Standardeingabe
    # nicht springen kann - PDF wird aber von hinten nach vorn gelesen.
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(daten)
        tmp.flush()
        ergebnis = subprocess.run(
            ["pdftotext", "-q", "-enc", "UTF-8", "-nopgbrk", tmp.name, "-"],
            capture_output=True,
            timeout=ZEITGRENZE,
            **werkzeuge.lautlos(),
        )
    # Auch bei Rückgabewert ungleich null kann brauchbarer Text dabei sein:
    # poppler meldet Fehler für einzelne Seiten, liefert die übrigen aber.
    return ergebnis.stdout.decode("utf-8", errors="replace")


#: Der Logger, über den pypdf seine Befunde meldet. Nicht
#: ``pypdf._reader``, obwohl die EOF-Meldung von dort kommt: Die
#: Unterlogger reichen nach oben durch, und am Elternlogger hängen auch
#: die Meldungen der übrigen Teile.
_PYPDF_LOGGER = "pypdf"

#: Platzhalter in einer ``logging``-Formatzeichenkette: ``%(name)s``
#: ebenso wie das alte ``%s``. Beide werden durch ein Auslassungszeichen
#: ersetzt, damit zwei Meldungen desselben Wortlauts zusammenfallen.
_PLATZHALTER = re.compile(r"%\(\w+\)[-+ #0-9.]*[a-zA-Z]|%[-+ #0-9.]*[a-zA-Z]")

#: Woran die Meldung zu erkennen ist, auf die es eine Antwort gibt.
#: pypdf kommt ohne ``fonttools`` an die Zeichentabelle mancher
#: eingebetteter Schriften nicht heran – ein Paket nachlegen, und der
#: Text aus diesen Anhängen landet im Index.
_FONTTOOLS_MELDUNG = "fontTools is required"


def _muster(satz: logging.LogRecord) -> str:
    """Der Wortlaut einer Meldung **ohne** die eingesetzten Werte.

    **Hier lag der Fehler, den der erste echte Lauf gezeigt hat.**
    Gezählt wurde die fertige Meldung (``getMessage()``), und pypdf
    setzt in fast jede Zahlen oder ganze Datenstrukturen ein:
    ``Ignoring wrong pointing object 8 0 (offset 0)`` oder, am
    schlimmsten, das vollständige Schriftverzeichnis einer PDF-Seite.
    Damit war jede Meldung ihr eigener Eintrag – gebündelt wurde nur,
    was ohnehin wortgleich war (``EOF marker not found``), und genau der
    Lärm, dessentwegen das hier gebaut wurde, lief weiter durch.

    Der Wortlaut vor dem Einsetzen (``satz.msg``) ist dagegen konstant.
    Ersetzt werden die Platzhalter, damit in der Ausgabe nicht
    ``%(offset)d`` steht. Schickt ein Aufrufer eine fertige Zeichenkette
    ohne Argumente – ältere pypdf-Fassungen taten das –, bleibt sie
    unverändert; ein einzelnes Prozentzeichen im Text darf nicht
    verschwinden.
    """
    text = str(satz.msg)
    if not satz.args:
        return text
    return _PLATZHALTER.sub("…", text)


@contextlib.contextmanager
def meldungen_buendeln():
    """Sammelt pypdfs Meldungen, statt sie zeilenweise durchzulassen.

    **Wozu.** pypdf meldet jede Unregelmäßigkeit über ``logging`` –
    allen voran ``EOF marker not found`` bei PDF, deren letzte Zeile
    fehlt. Das ist bei abgeschnittenen Anhängen der Normalfall und
    gelegentlich auch bei tadellosen Dateien aus betagten Programmen.
    Hat niemand das Protokoll eingerichtet, landet jede dieser Meldungen
    über Pythons ``lastResort`` auf der Fehlerausgabe.

    Bei einem einzelnen Anhang ist das eine Zeile. Beim Neuaufbau über
    70.000 Mails sind es hunderte, und dazwischen geht unter, was
    wirklich gemeldet werden wollte. **Eine Meldung, die in Lärm
    untergeht, ist keine, die angekommen ist** – derselbe Grund, aus dem
    der Windows-Dienst sein Protokoll umhängt statt es abzuschalten.

    Nicht unterdrückt, sondern gezählt: Der Aufrufer bekommt einen
    ``Counter`` und kann am Ende sagen, was wie oft vorkam. Gezählt wird
    der **Wortlaut** der Meldung, nicht die Meldung mit ihren Werten –
    warum, steht bei :func:`_muster`.

    **Nur dieser Logger, und der alte Zustand kommt zurück.** Wer
    MailBurg als Bibliothek benutzt, hat vielleicht ein eigenes
    Protokoll eingerichtet; das darf ein Aufruf hier nicht dauerhaft
    verstellen.

    Betrifft nur den Weg über pypdf. ``pdftotext`` schreibt auf seine
    eigene Fehlerausgabe, die ``_mit_poppler`` ohnehin einfängt.
    """
    gezaehlt: Counter[str] = Counter()

    class _Sammler(logging.Handler):
        def emit(self, satz: logging.LogRecord) -> None:
            try:
                gezaehlt[_muster(satz)] += 1
            except Exception:  # noqa: BLE001
                # Ein Protokollhandler, der wirft, reißt den Lauf mit,
                # den er beschreiben soll. ``handleError`` ist der dafür
                # vorgesehene Weg – dieselbe Überlegung wie im
                # Ereignisprotokoll des Windows-Dienstes.
                self.handleError(satz)

    logger = logging.getLogger(_PYPDF_LOGGER)
    vorher_handler = logger.handlers[:]
    vorher_weiter = logger.propagate
    vorher_stufe = logger.level
    logger.handlers = [_Sammler()]
    logger.propagate = False
    logger.setLevel(logging.WARNING)
    try:
        yield gezaehlt
    finally:
        logger.handlers = vorher_handler
        logger.propagate = vorher_weiter
        logger.setLevel(vorher_stufe)


def rat_zu_meldungen(gezaehlt) -> str | None:
    """Sagt, was sich an den gesammelten Meldungen noch bessern lässt.

    Bisher gibt es genau einen Rat, und der ist ein Paketname. Ohne
    ``fonttools`` kommt pypdf an die Zeichentabelle eingebetteter
    Schriften nicht heran und meldet das – je Schrift, je Datei. Beim
    ersten Lauf an 70.000 echten Mails war das die mit Abstand
    häufigste Meldung.

    **Ein Hinweis ohne Handlung ist keiner.** Deshalb steht hier der
    Befehl und nicht die Beobachtung. Mitgeliefert wird das Paket
    nicht: Es wiegt ein paar Megabyte, und wer poppler hat, braucht
    diesen Weg gar nicht.
    """
    if any(_FONTTOOLS_MELDUNG in text for text in gezaehlt):
        return (
            "Die häufigste davon lässt sich abstellen – dann wird auch der\n"
            "Text aus diesen Anhängen gelesen:\n"
            "\n"
            "    python3 -m pip install fonttools\n"
            "\n"
            "Unter Windows heißt der Befehl py statt python3."
        )
    return None


def _mit_pypdf(daten: bytes) -> str:
    import io

    from pypdf import PdfReader

    leser = PdfReader(io.BytesIO(daten))
    teile = []
    for seite in leser.pages:
        try:
            teile.append(seite.extract_text() or "")
        except Exception:  # noqa: BLE001 – eine kaputte Seite kostet nicht das Dokument
            continue
        if sum(len(t) for t in teile) > MAX_ZEICHEN:
            break
    return "\n".join(teile)


def text_aus_pdf(daten: bytes) -> str:
    """Holt den Text aus einer PDF-Datei. Gibt bei Misserfolg leeren Text zurück."""
    if not daten.startswith(b"%PDF"):
        return ""

    weg = verfuegbar()
    try:
        if weg == "poppler":
            text = _mit_poppler(daten)
        elif weg == "pypdf":
            text = _mit_pypdf(daten)
        else:
            return ""
    except (subprocess.TimeoutExpired, OSError, Exception):  # noqa: BLE001
        return ""

    return text[:MAX_ZEICHEN]


def ist_wohl_gescannt(daten: bytes, text: str) -> bool:
    """Schätzt, ob ein PDF nur eingescannte Seiten enthält.

    Ein umfangreiches Dokument, aus dem kaum Text herauskommt, besteht
    vermutlich aus Bildern. Solche Dateien bräuchten Texterkennung, um
    durchsuchbar zu werden – dafür ist noch nichts eingebaut, aber es lohnt,
    sie zu erkennen und zu zählen.
    """
    return len(daten) > 100_000 and len(text.strip()) < 200
