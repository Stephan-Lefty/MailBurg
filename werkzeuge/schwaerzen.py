"""Schwärzt persönliche Angaben in Bildschirmfotos.

Für Fehlerberichte und Anleitungen. Ein Bildschirmfoto aus dem
laufenden Betrieb zeigt echte Mailadressen, echte Mailserver und
gelegentlich den Betreff einer Nachricht, die niemanden etwas angeht –
und wandert trotzdem in ein öffentliches Repository, weil der Fehler
darauf so schön zu sehen ist.

**Balken, kein Weichzeichner.** Weichgezeichnete Schrift lässt sich
zurückrechnen; für kurze, formathafte Zeichenfolgen wie eine
Mailadresse ist das keine Theorie, sondern ein Werkzeug von der Stange.
Was hier gemalt wird, ist deckend.

**Und das Wichtigste vorweg: Dieses Werkzeug ist keine Freigabe.** Es
findet, wonach es sucht – Mailadressen, Servernamen, Telefonnummern,
IBAN. Es findet *nicht*, dass im Betreff »Kündigung Müller« steht oder
dass auf dem Bild ein Aktenzeichen liegt. Am Ende steht deshalb nicht
»sauber«, sondern eine Liste des Gefundenen und der ausdrückliche
Hinweis, dass ein Mensch das Bild danach noch einmal ansehen muss.

Das ist dieselbe Regel, die für `lesbarkeit.py` gilt: Was ein
Prüfwerkzeug auslässt, muss es sagen – sonst liest sich sein Schweigen
wie eine Unbedenklichkeitsbescheinigung.

Aufruf:

    python3 werkzeuge/schwaerzen.py bild.png
    python3 werkzeuge/schwaerzen.py bild.png --ziel sauber.png
    python3 werkzeuge/schwaerzen.py bild.png --auch "Rösner" "Naturlust"

Ohne `--ziel` entsteht `bild-geschwaerzt.png` daneben. Das Original
bleibt unangetastet – wer sein einziges Belegstück überschreibt, hat
den Fehler hinterher nicht mehr.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import subprocess
import sys
from pathlib import Path

#: Was ohne weiteres Zutun geschwärzt wird.
#:
#: Bewusst grob: Lieber ein Wort zu viel als eines zu wenig. Ein zu
#: breiter Balken kostet nichts, eine übersehene Adresse schon.
MUSTER: list[tuple[str, str]] = [
    ("Mailadresse", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    # Server- und Domainnamen. Die Beispiel-Domains nach RFC 2606 sind
    # ausdrücklich dafür da, öffentlich zu sein - sie bleiben stehen.
    ("Server", r"\b(?:imap|smtp|pop|mail|webmail)\.[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("Telefonnummer", r"(?:\+\d{1,3}[ /-]?)?(?:0\d{2,5}[ /-]?)\d{3,}[\d ]*"),
    ("IBAN", r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,}\b"),
    ("Steuernummer", r"\b(?:IdNr\.?|Steuernummer|St\.-Nr\.?)[: ]*[\d /]{8,}"),
    ("Aktenzeichen", r"\bAktenzeichen[: ]*[\w/.-]+"),
]

#: Diese Domains dürfen stehen bleiben - sie sind für Beispiele
#: reserviert (RFC 2606) und stehen so auch im Repository.
HARMLOS = re.compile(r"\.(example|invalid|test|localhost)(\.|$)|@example\.")

#: Die Farbe der Balken. Ein mittleres Grau - deckend wie Schwarz, aber
#: es liest sich auf einem hellen Bildschirmfoto als Auslassung und
#: nicht als Fehler im Bild.
#:
#: **Deckend ist der Punkt, nicht die Farbe.** Ein Balken mit
#: Durchsichtigkeit oder ein Weichzeichner lässt die Schrift
#: zurückrechnen; bei etwas so Formathaftem wie einer Mailadresse ist
#: das keine Theorie. Wer hier die Farbe ändert, darf alles tun außer
#: den Alphakanal anfassen.
BALKEN = (128, 128, 128)


def _woerter(bild: Path) -> list[dict]:
    """Was Tesseract sieht, mit Kästchen – eine Zeile je Wort."""
    fertig = subprocess.run(
        ["tesseract", str(bild), "-", "-l", "deu+eng", "tsv"],
        capture_output=True, text=True, check=False,
    )
    if fertig.returncode != 0:
        raise SystemExit(
            f"Tesseract kam nicht durch:\n{fertig.stderr.strip()}"
        )
    leser = csv.DictReader(io.StringIO(fertig.stdout), delimiter="\t",
                           quoting=csv.QUOTE_NONE)
    treffer = []
    for zeile in leser:
        text = (zeile.get("text") or "").strip()
        if not text:
            continue
        try:
            kasten = {k: int(zeile[k]) for k in ("left", "top", "width", "height")}
        except (KeyError, TypeError, ValueError):
            continue
        kasten["text"] = text
        kasten["zeile"] = (zeile.get("block_num"), zeile.get("par_num"),
                           zeile.get("line_num"))
        treffer.append(kasten)
    return treffer


def _zu_schwaerzen(woerter: list[dict], zusatz: list[str]) -> list[tuple[dict, str]]:
    """Welche Wörter unter einen Balken gehören, und warum.

    Geprüft wird Wort für Wort **und** zeilenweise: Tesseract zerlegt
    eine Mailadresse gelegentlich an Punkt oder @-Zeichen, und dann
    passt auf kein einzelnes Bruchstück ein Muster. Wer nur Wörter
    prüft, übersieht genau die Adressen, um die es geht.
    """
    gefunden: list[tuple[dict, str]] = []
    eigene = [re.escape(s) for s in zusatz if s]
    muster = MUSTER + ([("eigene Angabe", "|".join(eigene))] if eigene else [])

    for wort in woerter:
        for name, regel in muster:
            if re.search(regel, wort["text"], re.IGNORECASE):
                if HARMLOS.search(wort["text"]):
                    continue
                gefunden.append((wort, name))
                break

    # Zweiter Durchgang über ganze Zeilen, für alles, was zerrissen wurde.
    zeilen: dict[tuple, list[dict]] = {}
    for wort in woerter:
        zeilen.setdefault(wort["zeile"], []).append(wort)
    bereits = {id(w) for w, _ in gefunden}
    for teile in zeilen.values():
        text = " ".join(t["text"] for t in teile)
        ohne = text.replace(" ", "")
        for name, regel in muster:
            for quelle in (text, ohne):
                if re.search(regel, quelle, re.IGNORECASE) and not HARMLOS.search(quelle):
                    for t in teile:
                        if id(t) not in bereits:
                            gefunden.append((t, f"{name} (über die Zeile erkannt)"))
                            bereits.add(id(t))
                    break
    return gefunden


def schwaerzen(bild: Path, ziel: Path, zusatz: list[str]) -> int:
    from PIL import Image, ImageDraw

    woerter = _woerter(bild)
    if not woerter:
        print("Tesseract hat keinen Text gefunden. Ist das wirklich ein "
              "Bildschirmfoto?", file=sys.stderr)

    treffer = _zu_schwaerzen(woerter, zusatz)

    with Image.open(bild) as offen:
        bearbeitet = offen.convert("RGB")
        stift = ImageDraw.Draw(bearbeitet)
        for wort, _grund in treffer:
            # Zwei Pixel Zugabe: Tesseracts Kästchen sitzen knapp, und
            # ein herausragender Buchstabenrest verrät mehr, als man
            # denkt - besonders bei einem @.
            stift.rectangle(
                [wort["left"] - 2, wort["top"] - 2,
                 wort["left"] + wort["width"] + 2,
                 wort["top"] + wort["height"] + 2],
                fill=BALKEN,
            )
        bearbeitet.save(ziel)

    print(f"{bild.name} → {ziel.name}")
    if treffer:
        print(f"\n{len(treffer)} Stellen geschwärzt:")
        gesehen = set()
        for wort, grund in treffer:
            schluessel = (wort["text"], grund)
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            # Der gefundene Text wird **nicht** ausgegeben - er ist ja
            # genau das, was nicht in ein Protokoll soll. Nur die Art.
            print(f"  · {grund}")
    else:
        print("\nNichts gefunden, wonach dieses Werkzeug sucht.")

    print(
        "\nDas ist keine Freigabe. Gesucht wurde nach Mailadressen,\n"
        "Servernamen, Telefonnummern, IBAN, Steuer- und Aktenzeichen.\n"
        "Ein Name im Betreff, ein Firmenlogo oder ein Dateipfad fallen\n"
        "nicht darunter. Sehen Sie sich das Ergebnis an, bevor Sie es\n"
        "weitergeben."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Schwärzt persönliche Angaben in einem Bildschirmfoto.",
        epilog="Das Original bleibt unangetastet.",
    )
    p.add_argument("bild", type=Path)
    p.add_argument("--ziel", type=Path, help="Zieldatei (sonst -geschwaerzt daneben)")
    p.add_argument(
        "--auch", nargs="*", default=[], metavar="WORT",
        help="weitere Wörter, die verschwinden sollen – Namen, Firma, Ort",
    )
    args = p.parse_args(argv)

    if not args.bild.is_file():
        raise SystemExit(f"{args.bild} gibt es nicht.")

    ziel = args.ziel or args.bild.with_name(
        f"{args.bild.stem}-geschwaerzt{args.bild.suffix or '.png'}"
    )
    if ziel.resolve() == args.bild.resolve():
        raise SystemExit(
            "Ziel und Quelle sind dieselbe Datei. Das Original bleibt stehen."
        )
    return schwaerzen(args.bild, ziel, args.auch)


if __name__ == "__main__":
    raise SystemExit(main())
