"""Erzeugt die Versionsangabe, die Windows im Dateidialog anzeigt.

Windows liest sie aus einer Ressource in der ``.exe`` – Rechtsklick,
Eigenschaften, Reiter »Details«. Ohne sie steht dort nichts, und ein
Programm ohne Herkunftsangabe wirkt bei einer Datei, die ohnehin schon
eine SmartScheck-Warnung auslöst, noch zweifelhafter.

**Die Nummer wird abgeleitet, nicht abgeschrieben.** Genau daran ist es
schon einmal gescheitert: ``pyproject.toml`` trug 0.1.0, während das
Programm längst 0.9.0 meldete, und pip installierte eine Fassung, die es
nicht mehr gab (2026-08-27). Eine dritte Stelle mit derselben Zahl wäre
die dritte Gelegenheit, dass sie auseinanderläuft.

Aufruf::

    python werkzeuge/fassung_erzeugen.py werkzeuge/fassung.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mailburg import __version__  # noqa: E402

VORLAGE = """\
# Von werkzeuge/fassung_erzeugen.py erzeugt - nicht von Hand ändern.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({zahlen}),
    prodvers=({zahlen}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040704B0',
        [StringStruct('CompanyName', 'Stephan Rösner'),
         StringStruct('FileDescription', 'MailBurg – E-Mails. Sicher bewahrt.'),
         StringStruct('FileVersion', '{fassung}'),
         StringStruct('InternalName', 'MailBurg'),
         StringStruct('LegalCopyright', 'Stephan Rösner. MIT-Lizenz.'),
         StringStruct('OriginalFilename', 'MailBurg.exe'),
         StringStruct('ProductName', 'MailBurg'),
         StringStruct('ProductVersion', '{fassung}')])
    ]),
    # 1031 ist Deutsch, 1200 der Zeichensatz Unicode.
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
"""


def zahlenfolge(fassung: str) -> str:
    """Macht aus »0.9.0« die vier Zahlen, die Windows verlangt.

    Windows kennt nur vier Ganzzahlen. Ein Zusatz wie ``0.9.0rc1`` wird
    dabei stillschweigend abgeschnitten – die Ressource ist eine Anzeige,
    kein Vertrag, und die maßgebliche Nummer steht ohnehin im Programm.
    """
    teile = []
    for stueck in fassung.split(".")[:3]:
        ziffern = ""
        for zeichen in stueck:
            if not zeichen.isdigit():
                break
            ziffern += zeichen
        teile.append(int(ziffern or 0))
    while len(teile) < 4:
        teile.append(0)
    return ", ".join(str(z) for z in teile)


def main() -> int:
    ziel = Path(sys.argv[1] if len(sys.argv) > 1 else "werkzeuge/fassung.txt")
    ziel.write_text(
        VORLAGE.format(zahlen=zahlenfolge(__version__), fassung=__version__),
        encoding="utf-8",
    )
    print(f"{ziel}: MailBurg {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
