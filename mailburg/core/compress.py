"""Kompression mit Rückfallebene.

Zstandard packt Mailtext deutlich besser und schneller als alles, was sonst
in der Standardbibliothek steckt. Ab Python 3.14 ist es als
``compression.zstd`` dabei (PEP 784), davor braucht es das Paket
``zstandard``. Ist beides nicht da, weichen wir auf LZMA aus – langsamer,
aber überall vorhanden.

Welches Verfahren eine Datei benutzt, steht in ihrer Endung. Ein Archiv darf
also gemischt sein: was auf einem Rechner mit Zstandard geschrieben wurde,
liest ein Rechner ohne Zstandard trotzdem nicht – deshalb prüft
:func:`ensure_readable` beim Öffnen eines Archivs, ob alles Nötige da ist.
"""

from __future__ import annotations

import lzma

# Wir versuchen die Varianten in der Reihenfolge ihrer Güte.
_ZSTD_KIND: str | None
try:
    from compression import zstd as _zstd_mod  # Python 3.14+

    _ZSTD_KIND = "stdlib"
except ImportError:  # pragma: no cover – hängt von der Python-Fassung ab
    try:
        import zstandard as _zstd_mod  # type: ignore[no-redef]

        _ZSTD_KIND = "pip"
    except ImportError:
        _zstd_mod = None  # type: ignore[assignment]
        _ZSTD_KIND = None

#: Endung des bevorzugten Verfahrens, inklusive Punkt.
PREFERRED_SUFFIX = ".zst" if _ZSTD_KIND else ".xz"

#: Alle Endungen, die wir lesen können, unabhängig vom Verfahren.
KNOWN_SUFFIXES = (".zst", ".xz")

# Stufe 10 ist der Punkt, an dem Zstandard bei Mailtext noch schnell ist,
# aber schon fast so gut packt wie auf den teuren Stufen.
_ZSTD_LEVEL = 10


def compress(data: bytes) -> tuple[bytes, str]:
    """Packt ``data`` und gibt die Nutzdaten samt passender Endung zurück."""
    if _ZSTD_KIND == "stdlib":
        return _zstd_mod.compress(data, level=_ZSTD_LEVEL), ".zst"
    if _ZSTD_KIND == "pip":
        return _zstd_mod.ZstdCompressor(level=_ZSTD_LEVEL).compress(data), ".zst"
    return lzma.compress(data, preset=6), ".xz"


def _wie_nachruesten() -> str:
    """Sagt, welches Paket zu installieren ist – mit dem richtigen Namen.

    **Der Name hängt davon ab, wie MailBurg installiert wurde.** Bis zum
    2026-09-22 stand hier nur »das Paket 'zstandard' installieren«. Das
    ist der Name bei pip; in einer Distribution heißt dasselbe
    ``python3-zstandard``, und ``apt install zstandard`` findet nichts.

    Gemeldet von einer Anwenderin, die daraufhin ``zstd`` installierte –
    das Kommandozeilenwerkzeug, nicht die Anbindung an Python – und
    schrieb: »Python ist aktuell und Zstandard auch.« Beides stimmte,
    und trotzdem lief es nicht.

    Erkannt wird es am Ort: Liegt MailBurg unter ``dist-packages``,
    stammt es aus einem Distributionspaket.
    """
    from pathlib import Path

    if "dist-packages" in str(Path(__file__).resolve()):
        return (
            "Abhilfe unter Debian, Ubuntu und GuideOS:\n"
            "    sudo apt install python3-zstandard\n\n"
            "Unter Fedora heißt das Paket python3-zstd, unter Arch "
            "python-zstandard.\n\n"
            "Achtung: »zstd« allein genügt nicht – das ist das "
            "Kommandozeilenwerkzeug, nicht die Anbindung an Python."
        )
    return (
        "Abhilfe:\n"
        "    pip install zstandard\n\n"
        "Oder Python 3.14 oder neuer benutzen – dort ist es eingebaut."
    )


def ensure_readable(root) -> None:
    """Prüft beim Öffnen, ob sich dieses Archiv überhaupt lesen lässt.

    **Sonst fällt es erst auf, wenn jemand eine Mail anklickt.** Genau
    das ist am 2026-09-22 einer Anwenderin passiert: In ihrem Archiv
    liegen Nachrichten, die mit Zstandard gepackt sind, auf ihrem
    Rechner fehlte die Unterstützung – und statt einer Erklärung beim
    Öffnen bekam sie einen Traceback beim ersten Klick.

    Der Modulkopf behauptete diese Prüfung seit jeher. **Die Funktion
    gab es nie.** Vierte Fundstelle desselben Musters an einem Tag: ein
    Kommentar, der eine Zusage macht, die der Code nicht einlöst.

    Gesucht wird nur bis zur ersten ``.zst``-Datei – bei einem
    gewachsenen Archiv wäre ein vollständiger Durchlauf beim Öffnen zu
    teuer.
    """
    if _ZSTD_KIND is not None:
        return

    from pathlib import Path

    ablage = Path(root) / "mail"
    if not ablage.is_dir():
        return
    for _pfad in ablage.rglob("*.zst"):
        raise RuntimeError(
            "In diesem Archiv liegen Nachrichten, die mit Zstandard "
            "gepackt sind. Auf diesem Rechner fehlt die Unterstützung "
            "dafür – MailBurg könnte sie weder anzeigen noch "
            "zurückgeben.\n\n" + _wie_nachruesten()
        )


def decompress(data: bytes, suffix: str) -> bytes:
    """Entpackt ``data``; ``suffix`` benennt das verwendete Verfahren."""
    if suffix == ".zst":
        if _ZSTD_KIND is None:
            raise RuntimeError(
                "Diese Nachricht ist mit Zstandard gepackt, auf diesem "
                "Rechner fehlt die Unterstützung dafür.\n\n"
                + _wie_nachruesten()
            )
        if _ZSTD_KIND == "stdlib":
            return _zstd_mod.decompress(data)
        return _zstd_mod.ZstdDecompressor().decompress(data)
    if suffix == ".xz":
        return lzma.decompress(data)
    raise ValueError(f"Unbekanntes Kompressionsverfahren: {suffix!r}")


def zstd_available() -> bool:
    """Sagt, ob auf diesem Rechner Zstandard gelesen und geschrieben werden kann."""
    return _ZSTD_KIND is not None
