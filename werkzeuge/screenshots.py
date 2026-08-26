#!/usr/bin/env python3
"""Erzeugt die Bilder für die Anleitungen – aus erfundenen Daten.

Screenshots von Hand zu knipsen hat zwei Nachteile, und beide wiegen
schwer: Sie veralten still, sobald sich die Oberfläche ändert, und sie
zeigen die Mails dessen, der sie gemacht hat. Ein Archivprogramm, dessen
Anleitung die Postfächer seines Autors ausstellt, wirbt schlecht für
sich.

Deshalb dieses Skript. Es baut ein kleines Archiv mit erfundener Post,
rendert die Fenster ins Nichts (``QT_QPA_PLATFORM=offscreen``) und legt
die Bilder in ``docs/bilder`` ab.

    python werkzeuge/screenshots.py

Als Postfach der Anleitung dient ``martha@mailburg.example`` – die Domain
des Projekts. Alle übrigen Absender tragen die Endung ``.example``, die
per RFC 2606 für genau diesen Zweck reserviert ist und nie jemandem
gehören wird. Das ist keine Pedanterie: Stünde in der Anleitung eines
öffentlichen Programms eine fremde Domain, bekäme deren Inhaber Post
von allen, die das Beispiel ausprobieren.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
BILDER = WURZEL / "docs" / "bilder"

#: Erfundene Post. Die Betreffs sind so gewählt, dass sie den Zweck des
#: Programms zeigen: Rechnungen, Verträge, Behördenpost – das, wonach
#: man in einem Archiv Jahre später sucht.
POST = [
    ("Muster Energie AG", "rechnung@muster-energie.example", "INBOX",
     "Ihre Jahresabrechnung 2025", 3, True),
    ("Steuerbüro Krämer", "kanzlei@kraemer-steuern.example", "INBOX",
     "Unterlagen für die Umsatzsteuervoranmeldung", 8, True),
    ("Bauhof Nordwest GmbH", "buchhaltung@bauhof-nordwest.example", "INBOX",
     "Rechnung 2025-0417 – Lieferung vom 12.03.", 14, True),
    ("Telefon & Netz eG", "service@telefon-netz.example", "INBOX",
     "Ihre Rechnung für März 2025", 21, True),
    ("Amt für Gewerbe", "post@amt-gewerbe.example", "INBOX/Behörden",
     "Eingangsbestätigung Ihrer Anmeldung", 30, False),
    ("Versicherung Nordstern", "vertrag@nordstern.example", "INBOX/Verträge",
     "Ihre Police – Änderung zum 01.04.", 45, True),
    ("Anna Feldmann", "a.feldmann@partner-firma.example", "INBOX",
     "Re: Angebot für das Frühjahrsprojekt", 2, False),
    ("Anna Feldmann", "a.feldmann@partner-firma.example", "Gesendet",
     "Angebot für das Frühjahrsprojekt", 4, True),
    ("Hausverwaltung Lindenhof", "verwaltung@lindenhof.example", "INBOX",
     "Nebenkostenabrechnung 2024", 60, True),
    ("Werkzeughandel Süd", "info@werkzeughandel-sued.example", "INBOX",
     "Lieferschein zu Ihrer Bestellung", 11, True),
    ("Redaktion Fachblatt", "redaktion@fachblatt.example", "INBOX/Newsletter",
     "Ausgabe 3/2025 ist erschienen", 7, False),
    ("Bank am Markt", "postfach@bank-am-markt.example", "INBOX",
     "Ihr Kontoauszug steht bereit", 5, False),
]


def _mail(absender: str, adresse: str, betreff: str, tage: int,
          anhang: bool) -> bytes:
    wann = datetime.now(timezone.utc) - timedelta(days=tage)
    kopf = (
        f"From: {absender} <{adresse}>\r\n"
        f"To: Martha Muster <martha@mailburg.example>\r\n"
        f"Subject: {betreff}\r\n"
        f"Date: {wann.strftime('%a, %d %b %Y %H:%M:%S +0000')}\r\n"
        f"Message-ID: <{abs(hash(betreff))}@example.org>\r\n"
    )
    if not anhang:
        return (
            kopf + "Content-Type: text/plain; charset=utf-8\r\n\r\n"
            "Guten Tag,\r\n\r\n"
            "vielen Dank für Ihre Nachricht. Die Unterlagen liegen bei.\r\n\r\n"
            "Mit freundlichen Grüßen\r\n"
        ).encode()

    grenze = "----muster"
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
        'Content-Disposition: attachment; filename="Unterlagen.pdf"\r\n\r\n'
        "%PDF-1.4 Beispiel\r\n"
        f"--{grenze}--\r\n"
    ).encode()


def beispielarchiv(wo: Path):
    """Legt ein kleines Archiv mit erfundener Post an."""
    from mailburg.core.archive import Archive

    archiv = Archive.create(wo, name="Geschäftsarchiv")
    for absender, adresse, ordner, betreff, tage, anhang in POST:
        archiv.add(
            _mail(absender, adresse, betreff, tage, anhang),
            account="martha@mailburg.example",
            folder=ordner,
        )
    for betreff in ("Terminbestätigung", "Ihre Bestellung ist unterwegs"):
        archiv.add(
            _mail("Muster GmbH", "info@muster.example", betreff, 90, False),
            account="buero@mailburg.example",
            folder="INBOX",
        )
    return archiv


def ablegen(widget, name: str) -> None:
    """Speichert ein Fenster als Bild."""
    from PySide6.QtWidgets import QApplication

    QApplication.processEvents()
    ziel = BILDER / f"{name}.png"
    widget.grab().save(str(ziel))
    print(f"  {ziel.relative_to(WURZEL)}")


def _assistent_bilder() -> None:
    """Die Seiten der Ersteinrichtung – der erste Eindruck zählt doppelt.

    Vorbelegt wird mit erfundenen Postfächern statt mit denen des
    Rechners, auf dem das Skript läuft. Sonst stünden in der Anleitung
    fremde Adressen, und das ausgerechnet an der Stelle, an der ein
    Anwender Vertrauen fasst.
    """
    from unittest import mock

    from mailburg.core.accounts import Konto
    from mailburg.ui import assistent as modul

    konten = [
        Konto(name="martha@mailburg.example", server="imap.mailburg.example",
              benutzer="martha@mailburg.example", port=993, ssl=True),
        Konto(name="buero@mailburg.example", server="imap.mailburg.example",
              benutzer="buero@mailburg.example", port=993, ssl=True),
        Konto(name="martha@web-anbieter.example", server="imap.web-anbieter.example",
              benutzer="martha@web-anbieter.example", port=143, ssl=False),
    ]

    def erfundene(selbst):
        selbst.herkunft.setText(
            "<p><b>3 Postfächer aus Thunderbird übernommen.</b> Server, "
            "Benutzername und Verschlüsselung sind bereits eingetragen – "
            "ergänzen Sie bitte nur noch die Passwörter.</p>"
            "<p><b>Warum müssen Sie die Passwörter noch einmal eingeben?</b> "
            "Weil MailBurg sie aus Thunderbird nicht ausliest. Technisch "
            "ginge das – aber ein Programm, das die Passwörter anderer "
            "Programme abgreift, verhält sich wie Schadsoftware.</p>"
        )
        for konto in konten:
            selbst._zeile_anlegen(konto)

    with mock.patch.object(modul.KontenSeite, "_aus_thunderbird_laden", erfundene):
        assistent = modul.Einrichtungsassistent()
        assistent.resize(900, 720)
        for nummer, kennung in enumerate(assistent.pageIds()):
            assistent.setStartId(kennung)
            assistent.restart()
            assistent.show()
            ablegen(assistent, f"einrichtung-{nummer + 1}")
        assistent.close()


def main() -> int:
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QApplication

    BILDER.mkdir(parents=True, exist_ok=True)
    anwendung = QApplication(sys.argv)
    anwendung.setStyle("Fusion")
    QLocale.setDefault(QLocale("de_DE"))

    zwischen = Path(tempfile.mkdtemp(prefix="mailburg-bilder-"))
    try:
        ort = zwischen / "Geschaeftsarchiv"
        # Anlegen, füllen, schließen: Das Hauptfenster öffnet es gleich
        # selbst, und zwei offene Handles auf denselben Index gehen nicht
        # gut aus.
        beispielarchiv(ort).close()

        _assistent_bilder()

        from mailburg.ui.hauptfenster import Hauptfenster

        fenster = Hauptfenster(ort)
        archiv = fenster.archiv
        # Aufgeklappt zeigt der Baum, wie die Ordner unter einem
        # Postfach hängen - genau das, was eine Anleitung erklären soll.
        fenster.baum.expandAll()
        fenster.resize(1180, 760)
        fenster.suchfeld.setText("rechnung")
        fenster._suchen()
        fenster.tabelle.selectRow(0)
        fenster.show()
        ablegen(fenster, "hauptfenster")

        fenster.suchfeld.setText("")
        fenster._suchen()
        ablegen(fenster, "uebersicht")

        from mailburg.ui.suchmaske import Suchmaske

        maske = Suchmaske(archiv, eltern=fenster)
        maske.resize(980, 780)
        maske.begriff.setText("rechnung")
        maske.von.setText("energie")
        maske.show()
        ablegen(maske, "suchmaske")

        from mailburg.ui.hilfe import Hilfefenster

        handbuch = Hilfefenster(beginnen_bei="ueberblick")
        handbuch.resize(880, 620)
        handbuch.show()
        ablegen(handbuch, "handbuch")

        from mailburg.ui.zeitplan import Zeitplandialog

        automatik = Zeitplandialog(archiv=ort)
        automatik.resize(660, 580)
        automatik.show()
        ablegen(automatik, "automatisierung")

        from mailburg.ui.texterkennung import Texterkennungsdialog

        ocr = Texterkennungsdialog(archiv)
        ocr.resize(640, 300)
        ocr.show()
        ablegen(ocr, "texterkennung")

        from mailburg.ui.sichern import Sicherungsdialog

        sichern = Sicherungsdialog(archiv)
        sichern.resize(660, 340)
        sichern.show()
        ablegen(sichern, "sichern")

        treffer = archiv.index.search("", limit=1)[0]
        roh = archiv.store.get(treffer.hash, treffer.bucket)

        from mailburg.ui.lesefenster import Lesefenster

        lesen = Lesefenster(treffer, archiv)
        lesen.resize(820, 560)
        lesen.show()
        ablegen(lesen, "lesefenster")

        from mailburg.ui.zurueck import Zurueckdialog

        zurueck = Zurueckdialog(roh, treffer.subject)
        zurueck.resize(620, 340)
        zurueck.show()
        ablegen(zurueck, "wiederherstellen")

        from mailburg.ui.konten import Kontenverwaltung

        konten = Kontenverwaltung(fenster)
        konten.resize(760, 420)
        konten.show()
        ablegen(konten, "postfaecher")

        fenster.close()
    finally:
        shutil.rmtree(zwischen, ignore_errors=True)

    print(f"\nFertig. Alle Namen und Adressen erfunden ({len(POST)} Beispielmails).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
