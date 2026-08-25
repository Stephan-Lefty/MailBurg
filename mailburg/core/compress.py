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


def decompress(data: bytes, suffix: str) -> bytes:
    """Entpackt ``data``; ``suffix`` benennt das verwendete Verfahren."""
    if suffix == ".zst":
        if _ZSTD_KIND is None:
            raise RuntimeError(
                "Dieses Archiv ist mit Zstandard gepackt, auf diesem Rechner "
                "fehlt die Unterstützung dafür. Abhilfe: Python 3.14 oder "
                "neuer benutzen oder das Paket 'zstandard' installieren."
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
