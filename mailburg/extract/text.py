"""Entscheidet, womit ein Anhang gelesen wird, und tut es.

Diese Schicht kennt die Formate nur so weit, dass sie den richtigen
Extraktor auswählt. Sie hat eine einzige harte Regel: **Sie wirft nie.**
Ein Anhang, der sich nicht lesen lässt, liefert leeren Text – die Mail wird
trotzdem archiviert. Alles andere wäre die falsche Prioritätensetzung: Post
sichern ist wichtiger als sie durchsuchbar zu machen.

Die Auswahl richtet sich nach der Dateiendung, nicht nach dem
MIME-Typ. Der ist in E-Mails notorisch falsch – ``application/octet-stream``
für alles ist eher die Regel als die Ausnahme.
"""

from __future__ import annotations

from dataclasses import dataclass

from mailburg.extract import office, pdf

#: Anhänge über dieser Größe werden übergangen. Bei solchen Dateien handelt
#: es sich fast immer um Videos oder Abbilder, aus denen ohnehin kein Text
#: zu holen ist - der Versuch kostet nur Zeit.
MAX_ANHANG_BYTES = 80 * 1024 * 1024

#: Gesamttext je Mail. Newsletter mit zwanzig angehängten Prospekten sollen
#: den Index nicht dominieren.
MAX_JE_MAIL = 600_000

#: Endungen, aus denen sich unmittelbar Text lesen lässt.
NUR_TEXT = frozenset({"txt", "text", "log", "csv", "md", "asc", "vcf", "ics", "json", "xml"})

#: Endungen, bei denen wir gar nicht erst nachsehen. Ohne Texterkennung ist
#: aus Bildern nichts zu holen, aus Archiven und Programmen ebenso wenig.
OHNE_TEXT = frozenset({
    "png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff", "webp", "heic", "svg", "ico",
    "zip", "rar", "7z", "gz", "bz2", "xz", "tar",
    "exe", "dll", "so", "dmg", "msi", "deb", "rpm", "bin",
    "mp3", "mp4", "avi", "mov", "mkv", "wav", "ogg", "webm", "m4a",
    "p7s", "p7m", "asc", "sig", "pgp", "key", "pkpass",
})


@dataclass(frozen=True)
class Ergebnis:
    """Was beim Lesen eines Anhangs herauskam."""

    text: str
    art: str
    """``pdf``, ``office``, ``rtf``, ``text``, ``html``, ``uebergangen`` oder ``leer``."""

    hinweis: str = ""
    """Kurze Notiz, falls etwas auffiel – etwa ein vermutlich gescanntes PDF."""

    @property
    def hat_text(self) -> bool:
        return bool(self.text.strip())


def _endung(dateiname: str) -> str:
    _, _, endung = dateiname.rpartition(".")
    return endung.lower() if endung and endung != dateiname else ""


def aus_anhang(dateiname: str, mime_type: str, daten: bytes) -> Ergebnis:
    """Liest den Text eines einzelnen Anhangs."""
    if not daten:
        return Ergebnis("", "leer")
    if len(daten) > MAX_ANHANG_BYTES:
        return Ergebnis("", "uebergangen", f"größer als {MAX_ANHANG_BYTES // 1048576} MB")

    endung = _endung(dateiname)

    if endung in OHNE_TEXT:
        return Ergebnis("", "uebergangen")

    if endung == "pdf" or daten.startswith(b"%PDF"):
        text = pdf.text_aus_pdf(daten)
        if not text.strip() and pdf.ist_wohl_gescannt(daten, text):
            # Eingescannte Dokumente bräuchten Texterkennung. Wir merken uns
            # den Fall, damit später nachgerüstet werden kann.
            return Ergebnis("", "pdf", "vermutlich eingescannt, keine Texterkennung")
        return Ergebnis(text, "pdf")

    if endung in office.ENDUNGEN or daten.startswith(b"PK\x03\x04"):
        text = office.text_aus_zip_dokument(daten, endung)
        if text:
            return Ergebnis(text, "office")

    if endung == "rtf" or daten.startswith(b"{\\rt"):
        return Ergebnis(office.text_aus_rtf(daten), "rtf")

    if endung in ("html", "htm"):
        from mailburg.extract.message import html_to_text

        return Ergebnis(html_to_text(_als_text(daten)), "html")

    if endung in NUR_TEXT:
        return Ergebnis(_als_text(daten), "text")

    # Unbekannte Endung: Wenn es wie Text aussieht, nehmen wir es als Text.
    # Viele Anhänge kommen ohne brauchbaren Namen an.
    if _sieht_nach_text_aus(daten):
        return Ergebnis(_als_text(daten), "text")

    return Ergebnis("", "uebergangen")


def _als_text(daten: bytes) -> str:
    """Dekodiert Rohdaten als Text, notfalls mit Ersatzzeichen."""
    for kodierung in ("utf-8", "cp1252", "latin-1"):
        try:
            return daten.decode(kodierung)
        except UnicodeDecodeError:
            continue
    return daten.decode("utf-8", errors="replace")


def _sieht_nach_text_aus(daten: bytes, probe: int = 2048) -> bool:
    """Schätzt, ob Rohdaten lesbarer Text sind.

    Nullbytes kommen in Text nicht vor, in Binärdateien ständig. Das ist
    dieselbe Faustregel, nach der auch ``file`` und ``git`` entscheiden.
    """
    anfang = daten[:probe]
    if b"\x00" in anfang:
        return False
    druckbar = sum(1 for b in anfang if 32 <= b < 127 or b in (9, 10, 13) or b >= 160)
    return druckbar / max(len(anfang), 1) > 0.85


def aus_mail(parsed) -> tuple[str, dict[str, int]]:
    """Liest den Text aller Anhänge einer Mail.

    Erwartet eine mit ``with_payloads=True`` zerlegte Nachricht. Gibt den
    zusammengefassten Text und eine Zählung nach Art zurück – letztere für
    das Protokoll, damit man hinterher weiß, wie viel eingescanntes Material
    im Archiv liegt.

    Nebenbei wird an jedem Anhang vermerkt, wie viel Text aus *ihm* kam.
    Die Anhangsliste der Nachricht wird dafür ersetzt; die Anhänge selbst
    sind unveränderlich. Ohne diesen Vermerk ließe sich später nicht mehr
    sagen, *welcher* Anhang einer Mail die Texterkennung braucht.
    """
    from dataclasses import replace

    teile: list[str] = []
    zaehlung: dict[str, int] = {}
    vermerkt: list = []
    laenge = 0
    abgebrochen = False

    for anhang in parsed.attachments:
        if abgebrochen:
            # Über der Obergrenze wird nicht mehr gelesen – dann bleibt der
            # Anhang auch ohne Vermerk, statt fälschlich als leer zu gelten.
            vermerkt.append(anhang)
            continue

        ergebnis = aus_anhang(anhang.filename, anhang.mime_type, anhang.payload)
        schluessel = ergebnis.art if not ergebnis.hinweis else f"{ergebnis.art}:eingescannt"
        zaehlung[schluessel] = zaehlung.get(schluessel, 0) + 1
        vermerkt.append(replace(anhang, text_zeichen=len(ergebnis.text)))

        if ergebnis.hat_text:
            # Der Dateiname wandert mit in den Text: Wer nach "Rechnung
            # 2025" sucht, meint oft den Namen und nicht den Inhalt.
            teile.append(f"{anhang.filename}\n{ergebnis.text}")
            laenge += len(ergebnis.text)
            if laenge > MAX_JE_MAIL:
                abgebrochen = True

    parsed.attachments = vermerkt
    return "\n\n".join(teile)[:MAX_JE_MAIL], zaehlung
