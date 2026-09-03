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


def _erfundene_konten():
    """Postfächer für alle Fenster, die die echte Kontenliste lesen."""
    from mailburg.core.accounts import Konto

    return [
        Konto(name="martha@mailburg.example", server="imap.mailburg.example",
              benutzer="martha@mailburg.example", port=993, ssl=True),
        Konto(name="buero@mailburg.example", server="imap.mailburg.example",
              benutzer="buero@mailburg.example", port=993, ssl=True),
        Konto(name="martha@web-anbieter.example",
              server="imap.web-anbieter.example",
              benutzer="martha@web-anbieter.example", port=143, ssl=False),
    ]


def _zurueckbild(rohdaten: bytes, betreff: str) -> None:
    """Der Wiederherstellen-Dialog – ebenfalls mit erfundenen Konten.

    Auch er liest die Kontenliste des Rechners. Dieselbe Falle wie bei
    der Postfachverwaltung, an derselben Stelle übersehen.
    """
    from unittest import mock

    from mailburg.ui import zurueck as modul

    konten = _erfundene_konten()

    class Liste:
        konten = None

    Liste.konten = konten
    with mock.patch.object(modul, "Kontenliste", Liste):
        fenster = modul.Zurueckdialog(rohdaten, betreff)
        fenster.resize(620, 360)
        fenster.show()
        ablegen(fenster, "wiederherstellen")
        fenster.close()


def _kontenbild(eltern) -> None:
    """Die Postfachverwaltung – mit erfundenen Konten.

    **Hier lag ein Datenleck.** Die Verwaltung liest die Kontenliste des
    Rechners, auf dem sie läuft, nicht das Beispielarchiv. Ohne diesen
    Umweg zeigte das Bild die echten Postfächer dessen, der die
    Anleitung erzeugt – Mailadressen, Server, alles.

    Die Lehre gilt über dieses Bild hinaus: Jedes Fenster, das seine
    Daten woanders herholt als aus dem Beispielarchiv, braucht eigens
    erfundene Daten. Verlassen kann man sich darauf nur, wenn man jedes
    Bild einmal ansieht.
    """
    from unittest import mock

    from mailburg.core.accounts import Konto
    from mailburg.ui import konten as modul

    erfunden = _erfundene_konten() + [
        Konto(name="alte-firma", server="imap.alte-firma.example",
              benutzer="m.muster@alte-firma.example", port=993, ssl=True,
              aktiv=False),
    ]

    class Liste:
        konten = erfunden

        def finden(self, name):
            return next((k for k in erfunden if k.name == name), None)

    with mock.patch.object(modul, "Kontenliste", Liste), \
         mock.patch.object(modul.accounts, "passwort_holen",
                           lambda konto: "vorhanden"):
        fenster = modul.Kontenverwaltung(eltern)
        # Breit genug für die Spalte »Archive«: Bei 820 brach sie mitten
        # im Wort ab, und gerade sie ist die wichtigste – ohne Zuordnung
        # wird ein Postfach beim Abruf übergangen.
        fenster.resize(1020, 420)
        fenster.show()
        ablegen(fenster, "postfaecher")
        fenster.close()


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

    # Auch die Ortsauswahl braucht erfundene Angaben: Sie zeigt sonst
    # den Benutzernamen und die Namen der angeschlossenen Platten.
    from mailburg.core import orte

    erfundene_orte = [
        orte.Ort("Im Benutzerordner", Path("/home/martha/Mailarchiv"),
                 "benutzer", frei=98 * 10**9, gesamt=233 * 10**9,
                 auf_systemplatte=True),
        orte.Ort('Externe Platte »Sicherung«',
                 Path("/media/martha/Sicherung/Mailarchiv"), "laufwerk",
                 frei=1_900 * 10**9, gesamt=2_000 * 10**9),
        orte.Ort("Cloud-Ordner (Nextcloud)",
                 Path("/home/martha/Nextcloud/Mailarchiv"), "cloud",
                 frei=48 * 10**9, gesamt=100 * 10**9),
    ]

    with mock.patch.object(modul.KontenSeite, "_aus_thunderbird_laden", erfundene), \
         mock.patch.object(modul.orte, "vorschlagen", lambda: erfundene_orte):
        assistent = modul.Einrichtungsassistent()
        # **Hoch genug, dass die Archivseite ganz hineinpasst.** Sie ist
        # die laengste, und seit die Verschluesselung dazukam, stand ihr
        # unterster Teil unter der Kante - auf dem Bild war das Haekchen
        # nicht zu sehen, das die Anleitung daneben erklaerte.
        assistent.resize(900, 980)
        for nummer, kennung in enumerate(assistent.pageIds()):
            assistent.setStartId(kennung)
            assistent.restart()

            # **Die Abschlussseite fasst zusammen, was vorher gewählt
            # wurde.** Hier wird aber jede Seite einzeln aufgerufen statt
            # der Reihe nach durchgeklickt – also steht dort nichts. Auf
            # dem Bild las sich das als »Das Archiv liegt in None, 0
            # Postfächer sind eingerichtet«.
            #
            # Deshalb bekommt sie nachgereicht, was ein Anwender an
            # dieser Stelle hinter sich hätte: den Ort aus Schritt 2 und
            # die drei Postfächer aus Schritt 3.
            seite = assistent.page(kennung)
            if isinstance(seite, modul.AbschlussSeite):
                assistent.archiv_pfad = erfundene_orte[0].pfad
                assistent.konten = konten
                seite.initializePage()

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

    # **Qts eigene Beschriftungen übersetzen.** Ohne das steht auf den
    # Standardknöpfen »Close« und »Cancel« – im echten Programm nicht,
    # denn dort lädt ``ui.app.main`` den Übersetzer. Die Anleitung zeigte
    # damit etwas, das es so nie zu sehen gibt. Am 2026-08-29 auf dem
    # Bild der Postfachverwaltung aufgefallen.
    from mailburg.ui.app import _deutsch

    anwendung._uebersetzer = _deutsch(anwendung)

    # **Dieselbe Aufmachung wie im Betrieb.** Das Werkzeug baute die
    # Bilder bisher ohne das Stylesheet, das ``ui/app.py`` beim Start
    # setzt - die Anleitung zeigte also ein MailBurg ohne Kanten
    # zwischen den Bereichen, ohne abgesetzten Mailkopf und mit
    # Auswahlfeldern, die zu schmal für ihren Inhalt sind.
    #
    # Am 2026-09-01 aufgefallen, als ein Bild belegen sollte, dass die
    # neuen Kanten sitzen. Ein Bilderwerkzeug, das etwas anderes zeigt
    # als das Programm, ist schlimmer als keines: Es belegt Dinge, die
    # so nicht stimmen.
    from mailburg.ui import farben

    anwendung.setStyleSheet(farben.bereichsrahmen())
    farben.platzhalter_aufhellen(anwendung)
    farben.auswahlfelder_verbreitern(anwendung)

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

        def _passend(dialog, breite: int) -> None:
            """Breite vorgeben, Höhe nach Bedarf.

            ``resize`` allein zieht die Absätze auseinander, wenn das
            Fenster höher ist als sein Inhalt – es sieht dann aus, als
            fehle etwas. ``adjustSize`` allein schrumpft es auf
            dreihundert Pixel, und der Text bricht nach jedem zweiten
            Wort um. Beides zusammen trifft es.
            """
            dialog.setMinimumWidth(breite)
            dialog.adjustSize()
            dialog.resize(breite, dialog.sizeHint().height())

        # ---------------------------------------- Aufbewahrung und DSGVO
        #
        # Alles, was seit dem 26.08. dazugekommen ist. Ein Menüpunkt ohne
        # Bild in der Anleitung ist einer, den niemand findet.
        from mailburg.ui.einstufen import Einstufungsdialog

        # Wirklich suchen, nicht bloß behaupten: Stünde über einer Liste
        # aller Mails »gefunden mit von:energie«, wäre die Anleitung an
        # der Stelle unwahr.
        treffer = archiv.index.search("von:energie", limit=50)
        einstufen = Einstufungsdialog(archiv, "von:energie", treffer, fenster)
        _passend(einstufen, 620)
        einstufen.show()
        ablegen(einstufen, "aufbewahrung")
        einstufen.close()

        from mailburg.ui.fristen import Fristendialog

        fristen = Fristendialog(
            archiv, archiv.index.search("", limit=50), fenster
        )
        _passend(fristen, 560)
        fristen.show()
        ablegen(fristen, "fristen")
        fristen.close()

        from mailburg.ui.auskunft import Auskunftsdialog

        auskunft = Auskunftsdialog(archiv, fenster)
        # Eine Adresse, die es im Beispielarchiv wirklich gibt: Ein Bild
        # mit »Nichts gefunden« taugt nicht als Anleitung.
        auskunft.adresse.setText("a.feldmann@partner-firma.example")
        auskunft._suchen()
        # Knapp halten - sonst zieht das Layout die Absätze auseinander
        # und das Fenster sieht aus, als fehle etwas.
        _passend(auskunft, 620)
        auskunft.show()
        ablegen(auskunft, "auskunft")
        auskunft.close()

        from mailburg.core.accounts import Konto
        from mailburg.ui.anmelden import Anmeldedialog

        anmelden = Anmeldedialog(
            Konto(name="Arbeit", server="outlook.office365.com",
                  benutzer="martha@mailburg.example"),
            fenster,
        )
        _passend(anmelden, 620)
        anmelden.show()
        ablegen(anmelden, "anmelden")
        anmelden.close()

        from mailburg.ui.hilfe import Hilfefenster

        handbuch = Hilfefenster(beginnen_bei="ueberblick")
        handbuch.resize(880, 620)
        handbuch.show()
        ablegen(handbuch, "handbuch")

        from mailburg.ui.zeitplan import Zeitplandialog

        # **Dieser Dialog liest den echten Rechner aus.** Alle anderen
        # Fenster hier bekommen das Beispielarchiv vorgesetzt; der
        # Zeitplandialog dagegen fragt das Betriebssystem, was
        # eingerichtet ist – und zeigt den Zielordner der Sicherung an.
        # So kam auf ``automatisierung.png`` der Pfad des Entwicklers ins
        # Bild, mitsamt seinem Namen darin, und lag damit auf GitHub.
        #
        # Deshalb bekommt der Dialog hier einen erfundenen Zustand
        # vorgesetzt, statt zu hoffen, dass gerade nichts eingerichtet
        # ist. Das Bild zeigt ohnehin, wie es aussieht, wenn beides läuft
        # – ein leeres Formular erklärt niemandem etwas.
        from mailburg.core import zeitplan as _zeitplan

        echt_abruf = _zeitplan.zustand
        echt_sicherung = _zeitplan.sicherung_zustand

        def _beispiel_abruf(archiv=None):
            return _zeitplan.Zustand(
                moeglich=True, laeuft=True, takt=30, archiv=str(ort)
            )

        def _beispiel_sicherung(archiv=None):
            return _zeitplan.Zustand(
                moeglich=True, laeuft=True,
                archiv="/home/martha/Nextcloud/MailBurg-Sicherung",
            )

        _zeitplan.zustand = _beispiel_abruf
        _zeitplan.sicherung_zustand = _beispiel_sicherung
        try:
            automatik = Zeitplandialog(archiv=ort)
            automatik.resize(660, 580)
            automatik.show()
            ablegen(automatik, "automatisierung")
        finally:
            _zeitplan.zustand = echt_abruf
            _zeitplan.sicherung_zustand = echt_sicherung

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

        _zurueckbild(roh, treffer.subject)

        _kontenbild(fenster)

        fenster.close()
    finally:
        shutil.rmtree(zwischen, ignore_errors=True)

    print(f"\nFertig. {len(POST)} Beispielmails, alle Namen erfunden.")
    return _nachsehen()


#: Wonach die Selbstkontrolle sucht. Zwei Fenster lasen anfangs die
#: echte Kontenliste des Rechners statt des Beispielarchivs, und beide
#: Bilder lagen schon auf GitHub, bevor es jemandem auffiel. Seitdem
#: liest dieses Skript seine eigenen Bilder noch einmal.
VERRAETERISCH = (
    "@protonmail", "@gmail", "@gmx", "@web.de", "@outlook", "@t-online",
    "@hotmail", "@live.", "@posteo", "@mailbox.org",
    "kasserver", "hostedoffice",
)


def _eigene_spuren() -> list[str]:
    """Der Name dessen, der die Bilder gerade erzeugt.

    Am 2026-08-29 stand auf ``automatisierung.png`` der Zielordner einer
    Sicherung – mit dem Vornamen des Anwenders darin. Die Liste oben
    hatte ihn nicht gefunden, weil sie nach Anbietern sucht und nicht
    nach Pfaden. Auf GitHub lag das Bild da schon monatelang.

    Der Name steht bewusst **nicht** in dieser Datei, sondern wird beim
    Lauf ermittelt: Sonst stünde er im Repo, um ihn aus dem Repo
    herauszuhalten. So greift die Prüfung außerdem bei jedem für seinen
    eigenen Namen.
    """
    import getpass

    spuren = set()
    for wort in (getpass.getuser(), Path.home().name):
        wort = (wort or "").strip().lower()
        # Zu kurze Namen träfen zu oft auf gewöhnliche Wörter.
        if len(wort) >= 4:
            spuren.add(wort)
    return sorted(spuren)

#: **Warum mit Klammeraffe.** Zuerst stand hier bloß »outlook«, und die
#: Prüfung schlug beim Anmeldefenster an: Dort steht »Microsoft
#: (Outlook.com, Hotmail, Exchange)« als Name des Anmeldedienstes. Das
#: ist keine Adresse, sondern die Bezeichnung eines Anbieters – sie
#: *muss* dort stehen, sonst weiß niemand, was er auswählt.
#:
#: Gesucht wird deshalb nach Adressen, nicht nach Produktnamen. Eine
#: Mailadresse bei einem dieser Anbieter wäre ein Fund; ihr Name in
#: einer Auswahlliste ist keiner.
#:
#: (Hier steht bewusst keine vollständige Beispieladresse. Der Test
#: ``test_nur_reservierte_endungen`` verbietet sie in dieser Datei –
#: zu Recht, und er hat sie beim ersten Wurf dieses Kommentars prompt
#: gefunden.)
#:
#: Die beiden ohne Klammeraffe sind Servernamen von Massenhostern – die
#: tauchen nur auf, wenn jemand seine echte Kontenliste abgebildet hat.


def _nachsehen() -> int:
    """Liest die erzeugten Bilder und sucht nach echten Daten.

    Ein Bild ist undurchsichtig: Was darauf steht, sieht man nur, wenn
    man hinsieht – und Anleitungen sieht sich niemand Zeile für Zeile
    an. Deshalb liest tesseract sie hier noch einmal.

    Die Liste kann nicht vollständig sein; sie deckt die großen Anbieter
    ab und die Muster, die im Betrieb aufgefallen sind. Ein Blick auf
    die Bilder ersetzt sie nicht.
    """
    import shutil
    import subprocess

    from mailburg import QUELLTEXT_URL

    if not shutil.which("tesseract"):
        print("Hinweis: Ohne tesseract keine Selbstkontrolle der Bilder.")
        return 0

    # Auch .webp: Die von Hand aufgenommenen Windows-Bilder liegen so,
    # und die Prüfung lief an ihnen jahrelang vorbei, weil hier nur
    # nach *.png gesucht wurde.
    bilder = sorted(
        p for p in BILDER.iterdir()
        if p.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg")
    )
    gesucht = list(VERRAETERISCH) + _eigene_spuren()

    # Die Adresse des Projekts steht auf jedem Bild, das GitHub zeigt –
    # und enthält den Kontonamen. Der ist öffentlich und gehört dorthin;
    # eine Prüfung, die daran jedes Mal anschlägt, wird bald überlesen.
    projekt = QUELLTEXT_URL.lower().removeprefix("https://").rstrip("/")

    beanstandet = []
    for bild in bilder:
        gelesen = subprocess.run(
            ["tesseract", str(bild), "stdout", "-l", "deu+eng"],
            capture_output=True, text=True, check=False,
        ).stdout.lower()
        ohne_projekt = gelesen.replace(projekt, " ")
        treffer = [wort for wort in gesucht if wort in ohne_projekt]
        if treffer:
            beanstandet.append((bild.name, treffer))

    if beanstandet:
        print("\nACHTUNG – möglicherweise echte Daten auf einem Bild:")
        for name, treffer in beanstandet:
            print(f"  {name}: {', '.join(treffer)}")
        return 1
    print("Selbstkontrolle: keine bekannten Anbieternamen auf den Bildern.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
