#!/usr/bin/env python3
"""Legt ein Archiv mit erfundener Post an – zum Vorführen und Aufnehmen.

**Wozu.** Wer MailBurg in einem Video oder vor Publikum zeigt, zeigt
sonst seine eigene Post: Absender, Betreffs, Adressen, Geschäftspartner.
Ein einziges unscharfes Standbild genügt, und was einmal veröffentlicht
ist, holt niemand zurück.

``werkzeuge/screenshots.py`` löst dasselbe Problem für die Bilder der
Anleitung, taugt aber nicht zum Vorführen: Es rendert die Fenster ins
Nichts und räumt sein Archiv danach wieder weg. Hier bleibt es stehen,
damit man darin klicken, suchen und lesen kann.

    python werkzeuge/vorfuehrarchiv.py
    python werkzeuge/vorfuehrarchiv.py ~/Woanders --neu

Danach öffnet ``mailburg-gui <Ordner>`` das Archiv.

**Alle Adressen enden auf ``.example``.** Diese Endung ist nach RFC 2606
für Beispiele reserviert und wird nie jemandem gehören. Stünde in einer
Vorführung eine echte Domain, bekäme deren Inhaber Post von allen, die
das Beispiel nachspielen.

**Die Post reicht über mehrere Jahre**, sonst findet ``jahr:2023`` nichts
und die Vorführung der Suche fällt in sich zusammen. Aus demselben Grund
liegen die Mails in mehreren Ordnern und auf zwei Postfächern: Ein
Postfachbaum mit einem einzigen Eintrag zeigt nicht, wozu er da ist.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

#: Das Postfach, dem die Vorführung gehört.
ICH = "martha@mailburg.example"
ZWEITES = "buero@mailburg.example"

#: Erfundene Post: Absender, Adresse, Ordner, Betreff, Alter in Tagen,
#: Anhang ja/nein. Die Betreffs sind so gewählt, dass sie zeigen, wonach
#: man in einem Archiv Jahre später wirklich sucht – Rechnungen,
#: Verträge, Behördenpost –, und dass sich daran jede Suchfunktion
#: vorführen lässt: mehrere »Rechnung«, mehrere Jahre, mit und ohne
#: Anhang, ein Absender mit mehreren Nachrichten.
POST = [
    # Das laufende Jahr – hier spielt die Vorführung der Trefferliste.
    ("Muster Energie AG", "rechnung@muster-energie.example", "INBOX",
     "Ihre Jahresabrechnung", 3, True),
    ("Steuerbüro Krämer", "kanzlei@kraemer-steuern.example", "INBOX",
     "Unterlagen für die Umsatzsteuervoranmeldung", 8, True),
    ("Steuerbüro Krämer", "kanzlei@kraemer-steuern.example", "INBOX",
     "Rückfrage zu Ihrer Aufstellung", 12, False),
    ("Bauhof Nordwest GmbH", "buchhaltung@bauhof-nordwest.example", "INBOX",
     "Rechnung 0417 – Lieferung vom 12.03.", 14, True),
    ("Telefon & Netz eG", "service@telefon-netz.example", "INBOX",
     "Ihre Rechnung für März", 21, True),
    ("Amt für Gewerbe", "post@amt-gewerbe.example", "INBOX/Behörden",
     "Eingangsbestätigung Ihrer Anmeldung", 30, False),
    ("Versicherung Nordstern", "vertrag@nordstern.example", "INBOX/Verträge",
     "Ihre Police – Änderung zum 01.04.", 45, True),
    ("Anna Feldmann", "a.feldmann@partner-firma.example", "INBOX",
     "Re: Angebot für das Frühjahrsprojekt", 2, False),
    ("Anna Feldmann", "a.feldmann@partner-firma.example", "Gesendet",
     "Angebot für das Frühjahrsprojekt", 4, True),
    ("Hausverwaltung Lindenhof", "verwaltung@lindenhof.example", "INBOX",
     "Nebenkostenabrechnung", 60, True),
    ("Werkzeughandel Süd", "info@werkzeughandel-sued.example", "INBOX",
     "Lieferschein zu Ihrer Bestellung", 11, True),
    ("Redaktion Fachblatt", "redaktion@fachblatt.example", "INBOX/Newsletter",
     "Die neue Ausgabe ist erschienen", 7, False),
    ("Bank am Markt", "postfach@bank-am-markt.example", "INBOX",
     "Ihr Kontoauszug steht bereit", 5, False),

    # Vorjahr – damit sich »jahr:« und der Zeitraum vorführen lassen.
    ("Muster Energie AG", "rechnung@muster-energie.example", "INBOX",
     "Ihre Jahresabrechnung", 370, True),
    ("Bauhof Nordwest GmbH", "buchhaltung@bauhof-nordwest.example", "INBOX",
     "Rechnung 0288 – Lieferung vom 04.09.", 400, True),
    ("Amt für Gewerbe", "post@amt-gewerbe.example", "INBOX/Behörden",
     "Ihr Antrag vom Vormonat", 420, True),
    ("Versicherung Nordstern", "vertrag@nordstern.example", "INBOX/Verträge",
     "Beitragsanpassung zum Jahreswechsel", 450, True),
    ("Redaktion Fachblatt", "redaktion@fachblatt.example", "INBOX/Newsletter",
     "Jahresrückblick", 480, False),

    # Weiter zurück – für »was ist älter als …« und die Fristen.
    ("Hausverwaltung Lindenhof", "verwaltung@lindenhof.example", "INBOX",
     "Nebenkostenabrechnung", 740, True),
    ("Telefon & Netz eG", "service@telefon-netz.example", "INBOX",
     "Ihre Rechnung", 800, True),
    ("Bank am Markt", "postfach@bank-am-markt.example", "INBOX",
     "Änderung Ihrer Kontoführung", 1_100, False),

    # Private Post im Geschäftsarchiv – der Anlass für die
    # Einstufungsregeln. Ohne sie ließe sich »Post → Beim Aufnehmen
    # einstufen« nicht vorführen.
    ("Turnverein Eichenau", "vorstand@verein.example", "INBOX",
     "Einladung zum Sommerfest", 9, False),
    ("Turnverein Eichenau", "kasse@verein.example", "INBOX",
     "Ihre Beitragsquittung", 40, True),
    ("Turnverein Eichenau", "vorstand@verein.example", "INBOX",
     "Protokoll der Mitgliederversammlung", 380, True),
]

#: Post im zweiten Postfach. Weniger, aber genug, damit der Baum links
#: zwei Zweige hat und sich das Eingrenzen per Klick zeigen lässt.
ZWEITE_POST = [
    ("Muster GmbH", "info@muster.example", "INBOX",
     "Terminbestätigung", 6, False),
    ("Muster GmbH", "info@muster.example", "INBOX",
     "Ihre Bestellung ist unterwegs", 90, False),
    ("Konferenzbüro", "anmeldung@konferenz.example", "INBOX",
     "Ihre Anmeldung ist eingegangen", 200, True),
]


def _mail(absender: str, adresse: str, an: str, betreff: str, tage: int,
          anhang: bool) -> bytes:
    """Eine vollständige Mail als Bytes, wie sie vom Server käme."""
    wann = datetime.now(timezone.utc) - timedelta(days=tage)
    # Die Kennung muss eindeutig sein: Zwei Mails mit gleichem Betreff –
    # »Ihre Jahresabrechnung« gibt es hier dreimal – wären sonst für den
    # Abgleich dieselbe Nachricht.
    kennung = f"{abs(hash((betreff, tage, adresse)))}@mailburg.example"
    kopf = (
        f"From: {absender} <{adresse}>\r\n"
        f"To: Martha Muster <{an}>\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: {wann.strftime('%a, %d %b %Y %H:%M:%S +0000')}\r\n"
        f"Message-ID: <{kennung}>\r\n"
    )
    if not anhang:
        return (
            kopf + "Content-Type: text/plain; charset=utf-8\r\n\r\n"
            "Guten Tag,\r\n\r\n"
            "vielen Dank für Ihre Nachricht. Wir melden uns in Kürze.\r\n\r\n"
            "Mit freundlichen Grüßen\r\n"
        ).encode()

    grenze = "----vorfuehrung"
    return (
        kopf
        + f'Content-Type: multipart/mixed; boundary="{grenze}"\r\n\r\n'
        f"--{grenze}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n\r\n"
        "Guten Tag,\r\n\r\n"
        "anbei erhalten Sie die angekündigten Unterlagen als PDF.\r\n\r\n"
        "Mit freundlichen Grüßen\r\n\r\n"
        f"--{grenze}\r\n"
        "Content-Type: application/pdf\r\n"
        f'Content-Disposition: attachment; filename="Unterlagen.pdf"\r\n\r\n'
        "%PDF-1.4 Beispiel\r\n"
        f"--{grenze}--\r\n"
    ).encode()


def anlegen(wo: Path, *, geschaeftlich: bool = True) -> int:
    """Baut das Archiv auf und gibt die Zahl der Mails zurück."""
    from mailburg.core.archive import Archive, Mode

    # **Mit ``with``, nicht ohne.** Journal und Index schreiben ihren
    # letzten Stand erst beim Schließen weg. Ohne das steht zwar die Post
    # auf der Platte, die Suche findet aber nichts – und ausgerechnet die
    # soll vorgeführt werden.
    with Archive.create(
        wo,
        name="Vorführarchiv",
        # Geschäftsarchiv als Vorgabe: Nur dort gibt es Journal,
        # Einstufung, Fristen und Auskunft – also gerade das, was eine
        # Vorführung zeigen soll. Wer das Privatarchiv vorführt, nimmt
        # --privat.
        mode=Mode.GESCHAEFTLICH if geschaeftlich else Mode.PRIVAT,
    ) as archiv:
        for absender, adresse, ordner, betreff, tage, anhang in POST:
            archiv.add(
                _mail(absender, adresse, ICH, betreff, tage, anhang),
                account=ICH,
                folder=ordner,
            )
        for absender, adresse, ordner, betreff, tage, anhang in ZWEITE_POST:
            archiv.add(
                _mail(absender, adresse, ZWEITES, betreff, tage, anhang),
                account=ZWEITES,
                folder=ordner,
            )

    return len(POST) + len(ZWEITE_POST)


def main(argumente: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Legt ein Archiv mit erfundener Post zum Vorführen an.",
    )
    zerleger.add_argument(
        "ordner", nargs="?", default=str(Path.home() / "MailBurg-Vorfuehrung"),
        help="Wohin das Archiv soll (Vorgabe: ~/MailBurg-Vorfuehrung)",
    )
    zerleger.add_argument(
        "--neu", action="store_true",
        help="Einen vorhandenen Ordner vorher löschen",
    )
    zerleger.add_argument(
        "--privat", action="store_true",
        help="Privatarchiv statt Geschäftsarchiv anlegen",
    )
    gewaehlt = zerleger.parse_args(argumente)

    ziel = Path(gewaehlt.ordner).expanduser()

    if ziel.exists():
        if not gewaehlt.neu:
            print(
                f"»{ziel}« gibt es schon.\n"
                "Mit --neu wird der Ordner vorher gelöscht.",
                file=sys.stderr,
            )
            return 1
        # **Nur, was hier auch angelegt wurde.** Ein vertipptes Ziel darf
        # nicht das Archiv von jemandem mitnehmen, der --neu aus einem
        # anderen Aufruf übernommen hat.
        if not (ziel / "archive.json").is_file():
            print(
                f"»{ziel}« ist kein Archiv – ich lösche dort nichts.",
                file=sys.stderr,
            )
            return 1
        shutil.rmtree(ziel)

    anzahl = anlegen(ziel, geschaeftlich=not gewaehlt.privat)

    art = "Privatarchiv" if gewaehlt.privat else "Geschäftsarchiv"
    print(f"{art} mit {anzahl} erfundenen Mails angelegt:\n  {ziel}\n")
    print("Zum Vorführen öffnen mit:")
    print(f'  mailburg-gui "{ziel}"\n')
    print("Alle Absender enden auf .example – es steht keine echte Post darin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
