"""Sucht Stellen, an denen die Oberfläche Text abschneidet.

**Warum es dafür ein Werkzeug braucht.** Abgeschnittener Text fällt beim
Bauen nie auf: Der Entwickler kennt den Satz, der dort steht, und liest
ihn im Quelltext. Er sieht »Nötig ist nur, dass Sie angemeldet sind: Die
Passwörter liegen im Schlüsselbund, und der öffnet sich« und weiß, wie es
weitergeht. Der Anwender sieht einen Satz, der mitten im Wort aufhört.

Am 2026-08-31 hat Stephan zwei solche Stellen im selben Fenster gemeldet
– ein Auswahlfeld, in dem der längste Eintrag nicht las bar war, und
darunter zwei Absätze, die unten wegliefen. Beides in einem Dialog, den
es seit Wochen gibt.

Geprüft wird dreierlei:

*Auswahlfelder* – ist die Box breit genug für ihren längsten Eintrag?

*Beschriftungen mit Umbruch* – reicht die Höhe für den umgebrochenen
Text? ``heightForWidth`` sagt, wie hoch er bei dieser Breite würde.

*Fenster* – passt der Inhalt überhaupt hinein, oder ist das Fenster
kleiner als das, was es zeigen soll?

Aufruf::

    QT_QPA_PLATFORM=offscreen python3 werkzeuge/lesbarkeit.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

#: Wie viele Pixel Unterschied noch als »passt« gelten. Schriftmaße
#: schwanken zwischen Systemen um ein, zwei Pixel; darunter wäre jede
#: Meldung Rauschen.
TOLERANZ = 4

#: Felder, die beim Öffnen versteckt sind und deshalb nicht gemessen
#: werden. **Sie fallen nicht still weg**, sondern stehen am Ende des
#: Berichts: Was ein Prüfwerkzeug auslässt, muss es sagen, sonst liest
#: sich »nichts abgeschnitten« wie »alles geprüft«.
UEBERSPRUNGEN: list[str] = []


def _bezeichner(bauteil) -> str:
    """Woran ein Feld im Bericht zu erkennen ist."""
    return bauteil.accessibleName() or bauteil.objectName() or "ohne Namen"


def _befunde(fenster, name: str) -> list[str]:
    from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit

    from mailburg.ui import farben

    gefunden: list[str] = []

    for box in fenster.findChildren(QComboBox):
        if not box.count():
            continue
        # **Ein verstecktes Feld hat noch keine Breite, die etwas
        # bedeutet.** Es trägt die, die das Layout ihm zugeteilt hat,
        # während sein Platz von einem anderen Bauteil belegt war. Beim
        # Einblenden wächst es auf seinen Inhalt, und das Fenster wächst
        # mit – nachgemessen am 2026-09-06 am Rückspieldialog: 324 px
        # Fensterbreite vorher, 834 px nachher, das Feld passt.
        #
        # **Gemessen wäre es trotzdem zu schmal gewesen**, und das ist
        # die eigentliche Gefahr: Ein Werkzeug, das etwas meldet, was im
        # Betrieb nicht auftritt, entwertet seine übrigen Befunde. Wer
        # zweimal umsonst gesucht hat, sieht beim dritten Mal nicht mehr
        # nach.
        if box.isHidden():
            UEBERSPRUNGEN.append(f"{name}: »{_bezeichner(box)}«")
            continue
        gebraucht = box.sizeHint().width()
        vorhanden = box.width()
        if vorhanden and gebraucht - vorhanden > TOLERANZ:
            laengster = max(
                (box.itemText(i) for i in range(box.count())), key=len
            )
            gefunden.append(
                f"{name}: Auswahlfeld »{box.accessibleName() or box.objectName()}« "
                f"ist {vorhanden} px breit, braucht {gebraucht} px "
                f"(längster Eintrag: »{laengster}«)"
            )

    # **Eingabefelder wurden bis zum 2026-09-07 gar nicht gemessen** –
    # und genau darin saßen die zwei Fenster, die Stephan gemeldet hat:
    # Das Pfadfeld war 108 px breit und zeigte »erbird« statt
    # ``/home/…/.thunderbird``. Ein Prüfwerkzeug mit einer Lücke ist
    # gefährlicher als keines: Es sagt »alles lesbar« und meint »alles,
    # wonach ich gesucht habe«.
    #
    # Gemessen wird gegen den Inhalt, ersatzweise gegen den
    # Platzhaltertext. Der steht ja gerade dann da, wenn der Anwender
    # das Feld zum ersten Mal sieht.
    for feld in fenster.findChildren(QLineEdit):
        if feld.isHidden():
            UEBERSPRUNGEN.append(f"{name}: Eingabefeld »{_bezeichner(feld)}«")
            continue
        text = feld.text() or feld.placeholderText()
        if not text:
            continue
        # **Dieselbe Zahl wie die Oberfläche, nicht eine zweite.**
        # ``farben.feldbreite`` deckelt bei 45 Zeichen – ein Pfadfeld
        # darf nicht so breit werden wie der längste denkbare Pfad. Wer
        # hier den vollen Text verlangt, meldet als Fehler, was Absicht
        # ist: Am 2026-09-07 stand die CI deswegen auf Rot, mit neun
        # Befunden, von denen keiner einer war.
        gebraucht = farben.feldbreite(feld.fontMetrics(), text)
        vorhanden = feld.width()
        if vorhanden and gebraucht - vorhanden > TOLERANZ:
            gefunden.append(
                f"{name}: Eingabefeld »{_bezeichner(feld)}« ist "
                f"{vorhanden} px breit, braucht {gebraucht} px "
                f"(Inhalt: »{text[:50]}«)"
            )

    for schild in fenster.findChildren(QLabel):
        if not schild.wordWrap() or not schild.text().strip():
            continue
        # **Auch Beschriftungen können versteckt sein**, und dann gilt
        # für sie dasselbe wie für Auswahl- und Eingabefelder: Ihre Maße
        # stammen aus einer Zuteilung, die ihr Platz gar nicht hatte. Der
        # Auskunftsdialog blendet seinen Vorbehalt erst nach der Suche
        # ein; gemessen meldete er am 2026-09-12 einen Befund, den beim
        # Anwender niemand sieht.
        #
        # Bis dahin prüfte das Werkzeug hier ohne diese Frage – die
        # beiden anderen Messungen stellten sie seit dem 2026-09-06.
        # **Eine Regel, die nur an zwei von drei Stellen gilt, ist keine
        # Regel, sondern ein Zufall.**
        if schild.isHidden():
            UEBERSPRUNGEN.append(f"{name}: Beschriftung »{_bezeichner(schild)}«")
            continue
        breite = schild.width()
        if breite <= 0:
            continue
        gebraucht = schild.heightForWidth(breite)
        vorhanden = schild.height()
        if gebraucht - vorhanden > TOLERANZ:
            anfang = " ".join(schild.text().split())[:60]
            gefunden.append(
                f"{name}: Text abgeschnitten – {vorhanden} px hoch, "
                f"braucht {gebraucht} px: »{anfang}…«"
            )

    # **In der Standardgröße muss alles ohne Rollen lesbar sein.**
    # Stephans Regel vom 2026-08-31, und sie ist richtig: Ein Fenster,
    # in dem man scrollen muss, um eine Erklärung zu Ende zu lesen, ist
    # ein schlechtes Fenster. Der Rollbereich ist die Rückfalllinie für
    # kleine Bildschirme, nicht der Normalzustand.
    #
    # Gemeldet wird deshalb, wenn ein Rollbalken schon beim Öffnen etwas
    # zu rollen hat – und zwar nur dann, wenn der Bildschirm überhaupt
    # Platz gehabt hätte.
    from PySide6.QtWidgets import QApplication, QScrollArea

    rollbereiche = fenster.findChildren(QScrollArea)
    for bereich in rollbereiche:
        balken = bereich.verticalScrollBar()
        if balken is None or balken.maximum() <= TOLERANZ:
            continue
        # **Am Fenster messen, nicht am Bauteil.** Eine
        # Assistentenseite ist kein Fenster; ihre Höhe ist die des
        # Assistenten minus Kopfzeile und Knopfleiste. Wer sie gegen die
        # Bildschirmhöhe hält, bekommt immer »da wäre noch Platz« –
        # auch wenn der Assistent längst so groß ist, wie er werden
        # kann.
        echtes = fenster.window()
        schirm = QApplication.primaryScreen()
        platz = schirm.availableGeometry().height() if schirm else 0
        if platz and echtes.height() < platz - 150:
            gefunden.append(
                f"{name}: rollt schon beim Öffnen ({balken.maximum()} px), "
                f"obwohl der Bildschirm noch "
                f"{platz - fenster.height()} px Platz hätte"
            )

    if rollbereiche:
        return gefunden

    inhalt = fenster.sizeHint()
    if inhalt.height() - fenster.height() > TOLERANZ:
        gefunden.append(
            f"{name}: Fenster ist {fenster.height()} px hoch, der Inhalt "
            f"braucht {inhalt.height()} px"
        )
    if inhalt.width() - fenster.width() > TOLERANZ:
        gefunden.append(
            f"{name}: Fenster ist {fenster.width()} px breit, der Inhalt "
            f"braucht {inhalt.width()} px"
        )

    gefunden += _viel_zu_gross(fenster, name)
    return gefunden


#: Ab wie viel Leerraum ein Fenster nicht mehr großzügig, sondern kaputt
#: aussieht. Das Doppelte heißt: Die Hälfte des Fensters ist leer.
LEERRAUM = 2.0


def _viel_zu_gross(fenster, name: str) -> list[str]:
    """Fenster, die viel höher aufgehen, als ihr Inhalt braucht.

    **Ein halbleeres Fenster liest sich wie ein kaputtes.** Am
    2026-09-12 fragte Stephan zum Infofenster: »War hier nicht eine
    Grafik vorher drin?« Es war nie eine drin. Der Text stand nur mitten
    in einer großen leeren Fläche, und das sieht aus, als wäre etwas
    nicht geladen worden.

    Bis dahin prüfte das Werkzeug nur die eine Richtung: ob ein Fenster
    zu **klein** für seinen Inhalt ist. Die andere fiel niemandem auf,
    weil dabei kein Text verlorengeht – es sieht bloß falsch aus, und
    »sieht falsch aus« meldet kein Messwerkzeug von selbst.

    Gemessen wird gegen die Höhe, die der Inhalt bei der **tatsächlichen
    Breite** braucht. Nicht gegen ``sizeHint()``: Der rechnet mit
    irgendeiner angenommenen Breite und gab beim Infofenster 718 px für
    ein Fenster aus, in das 172 px Text gehören.

    Fenster mit Rollbereich bleiben außen vor – die sind mit Absicht so
    hoch, wie der Bildschirm hergibt.
    """
    from PySide6.QtWidgets import QMainWindow, QScrollArea

    if isinstance(fenster, QMainWindow) or fenster.findChildren(QScrollArea):
        return []

    aufbau = fenster.layout()
    if aufbau is None:
        return []
    gebraucht = aufbau.heightForWidth(fenster.width())
    if gebraucht <= 0:
        gebraucht = aufbau.sizeHint().height()
    if gebraucht <= 0 or fenster.height() <= 0:
        return []

    if fenster.height() < gebraucht * LEERRAUM:
        return []
    return [
        f"{name}: Fenster ist {fenster.height()} px hoch, der Inhalt "
        f"braucht nur {gebraucht} px – die Hälfte steht leer"
    ]


def _zeigen(fenster, anwendung, breite=0, hoehe=0):
    """Zeigt ein Fenster so, wie es beim Anwender aufgeht."""
    if breite and hoehe:
        fenster.resize(breite, hoehe)
    fenster.show()
    anwendung.processEvents()
    return fenster


def _wegnehmen(fenster) -> None:
    """Nimmt ein gemessenes Fenster weg – **ohne es zu schließen.**

    Hier stand ``fenster.close()``, und daran blieb der Lauf am
    2026-09-12 hängen: Der Notschlüsseldialog beantwortet das Schließen
    mit einer Rückfrage (»Erst sichern«), weil der Schlüssel danach weg
    ist. Beim Anwender ist das richtig. Ein Werkzeug, das nur nachmisst,
    wartet dann ewig auf eine Antwort, die niemand gibt.

    **Ein Messwerkzeug soll ein Fenster ansehen, nicht bedienen.**
    Schließen ist eine Bedienhandlung, und ein Fenster darf sich
    weigern. Verstecken kann es nicht ablehnen – ``hide()`` löst kein
    ``closeEvent`` aus.
    """
    fenster.hide()
    fenster.deleteLater()


def pruefen() -> list[str]:
    """Geht die Fenster durch und sammelt, was nicht hineinpasst."""
    from unittest import mock

    from PySide6.QtWidgets import QApplication

    from mailburg.ui import farben

    anwendung = QApplication.instance() or QApplication([])
    anwendung.setStyle("Fusion")
    farben.auswahlfelder_verbreitern(anwendung)

    befunde: list[str] = []
    import tempfile

    from mailburg.core import paths
    from mailburg.core.archive import Archive, Mode

    with tempfile.TemporaryDirectory() as ordner:
        basis = Path(ordner)
        # **Auch die Einstellungen umlenken, nicht nur die Daten.** Die
        # Kontenliste liegt unter ``config_dir()``; ohne diesen Patch
        # zeigten die Dialoge die *echten* Postfächer dieses Rechners –
        # und ihre Adressen standen samt Mailserver im Bericht. Der ist
        # genau das, was man in einen Fehlerbericht kopiert.
        #
        # Am 2026-09-06 aufgefallen, als eine echte Firmenadresse in der
        # Ausgabe stand.
        with mock.patch.object(paths, "data_dir", return_value=basis / "daten"), \
                mock.patch.object(
                    paths, "config_dir", return_value=basis / "einstellungen"
                ):
            (basis / "daten").mkdir(parents=True, exist_ok=True)
            _konten_erfinden(basis / "einstellungen" / "konten.json")
            archiv = Archive.create(
                basis / "Archiv", mode=Mode.GESCHAEFTLICH, name="Probe"
            )
            try:
                befunde += _dialoge(anwendung, archiv)
            finally:
                archiv.close()

    return befunde


#: Erfundene Postfächer für die Messung. **Der längste Name ist
#: Absicht:** Gemessen wird, ob ein Auswahlfeld seinen längsten Eintrag
#: zeigen kann – mit drei kurzen Namen bewiese der Lauf nichts. Alle
#: Adressen enden auf ``.example``; das ist nach RFC 2606 dafür
#: reserviert und kann niemandem gehören.
PROBEKONTEN = [
    {"name": "Firma", "server": "imap.firma.example",
     "benutzer": "post@firma.example"},
    {"name": "Buchhaltung", "server": "mail.ein-langer-anbietername.example",
     "benutzer": "buchhaltung@ein-langer-anbietername.example"},
    {"name": "Privat", "server": "imap.privat.example",
     "benutzer": "ich@privat.example"},
]


def _konten_erfinden(datei: Path) -> None:
    """Legt die Postfächer an, die in den Auswahlfeldern stehen sollen.

    **Das Ziel wird übergeben, nicht erfragt.** Ein ``Kontenliste()``
    ohne Pfad nähme ``config_dir()`` – und wenn der Patch darüber je
    wegfiele, überschriebe dieses Werkzeug die echte Kontenliste des
    Rechners. Ein Messwerkzeug darf messen, nicht ändern.
    """
    from mailburg.core.accounts import Konto, Kontenliste

    liste = Kontenliste(datei)
    liste.konten = [Konto(**angaben) for angaben in PROBEKONTEN]
    liste.speichern()


#: **Die Liste aller Fenster, die geprüft werden – der Prüfauftrag.**
#:
#: Bis zum 2026-09-12 stand hier eine Reihe handgeschriebener Aufrufe.
#: Wer ein Fenster baute und es nicht eintrug, hatte ein ungeprüftes
#: Fenster, und es fiel niemandem auf: Das Werkzeug meldete »nichts
#: abgeschnitten« und meinte damit die zehn, die es kannte. Von
#: einunddreißig.
#:
#: Deshalb ist die Liste jetzt eine Tabelle und kein Programm. Ein
#: Wächtertest liest sie, sucht alle Fensterklassen in ``mailburg/ui``
#: und vergleicht: **Ein neues Fenster ohne Eintrag macht den Test rot.**
#: Nicht Jahre später einen Anwender mit einem Bildschirmfoto.
#:
#: Die Klasse steht als Pfad da, nicht als Import – so lässt sich die
#: Tabelle lesen, ohne Qt zu starten. Die Bauanleitung bekommt die Klasse
#: und die Werkstatt (Archiv, Treffer, Probekonto).
BAUPLAENE: list[tuple[str, str, object]] = [
    ("mailburg.ui.zeitplan.Zeitplandialog",
     "Zeitplan »Was von selbst laufen soll«",
     lambda K, w: K(archiv=w.archiv.root)),
    ("mailburg.ui.suchmaske.Suchmaske",
     "Suchmaske",
     lambda K, w: K(w.archiv)),
    ("mailburg.ui.regeln.Regeldialog",
     "Einstufungsregeln",
     lambda K, w: K(archiv=w.archiv)),
    ("mailburg.ui.sichern.Sicherungsdialog",
     "Sichern",
     lambda K, w: K(w.archiv)),
    ("mailburg.ui.sichern.Rueckholdialog",
     "Sicherung zurückholen",
     lambda K, w: K()),
    ("mailburg.ui.sichern.Uebernahmedialog",
     "Sicherung übernehmen",
     lambda K, w: K(w.archiv)),
    ("mailburg.ui.einlesen.Einlesedialog",
     "Lokale Mailordner einlesen",
     lambda K, w: K(w.archiv)),
    ("mailburg.ui.zurueckspielen.Rueckspieldialog",
     "Ins Dateisystem zurückspielen",
     lambda K, w: K(w.archiv)),
    ("mailburg.ui.zurueck.Zurueckdialog",
     "Ins Postfach zurückgeben",
     lambda K, w: K(w.rohdaten, "Rechnung 2026-0815 vom 14. Januar")),
    ("mailburg.ui.zugaenge.Zugangsdialog",
     "Zugänge",
     lambda K, w: K(archiv=w.archiv)),
    ("mailburg.ui.konten.Kontenverwaltung",
     "Postfächer verwalten",
     lambda K, w: K()),
    ("mailburg.ui.konten.ArchivZuordnung",
     "Postfach einem Archiv zuordnen",
     lambda K, w: K(w.konto)),
    ("mailburg.ui.anmelden.Anmeldedialog",
     "Anmelden (OAuth2)",
     lambda K, w: K(w.konto)),
    ("mailburg.ui.archivpasswort.NeuesPasswortFragen",
     "Archiv verschlüsseln",
     lambda K, w: K()),
    ("mailburg.ui.archivpasswort.PasswortFragen",
     "Archiv öffnen",
     lambda K, w: K(archivname="Probe")),
    ("mailburg.ui.archivpasswort.NotschluesselZeigen",
     "Notschlüssel zeigen",
     lambda K, w: K(NOTSCHLUESSEL)),
    ("mailburg.ui.fristen.Fristendialog",
     "Aufbewahrungsfristen",
     lambda K, w: K(w.archiv, w.treffer)),
    ("mailburg.ui.einstufen.Einstufungsdialog",
     "Einstufen",
     lambda K, w: K(w.archiv, "rechnung", w.treffer)),
    ("mailburg.ui.texterkennung.Texterkennungsdialog",
     "Texterkennung",
     lambda K, w: K(w.archiv)),
    ("mailburg.ui.auskunft.Auskunftsdialog",
     "Auskunft nach DSGVO",
     lambda K, w: K(w.archiv)),
    ("mailburg.ui.info.Infofenster",
     "Über MailBurg",
     lambda K, w: K()),
    ("mailburg.ui.hilfe.Hilfefenster",
     "Hilfe",
     lambda K, w: K()),
    ("mailburg.ui.assistent.KontoDialog",
     "Postfach anlegen (Assistent)",
     lambda K, w: K()),
    ("mailburg.ui.assistent.PasswortNachfrage",
     "Passwort nachfragen (Assistent)",
     lambda K, w: K(w.konto, "Der Schlüsselbund hat es nicht hergegeben.")),
    ("mailburg.ui.lesefenster.Lesefenster",
     "Mail lesen",
     lambda K, w: K(w.treffer[0], w.archiv)),
]

#: Ein Notschlüssel ist so lang wie jeder andere, und **erfunden**: Er
#: steht im Bericht, den man in einen Fehlerbericht kopiert.
NOTSCHLUESSEL = "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH"

#: Fenster mit eigenem Messweg – sie stehen weiter unten als Funktion,
#: weil ein Aufmachen und Nachmessen bei ihnen nicht reicht.
SONDERFAELLE: dict[str, str] = {
    "mailburg.ui.assistent.Einrichtungsassistent":
        "Jede Seite einzeln, siehe _assistent()",
    "mailburg.ui.hauptfenster.Hauptfenster":
        "Mit Suchtreffern, Statuszeile und Spaltenköpfen, siehe "
        "_hauptfenster()",
}

#: **Was nicht geprüft wird, und warum.** Eine Ausnahme braucht einen
#: Grund, der hier steht – sonst ist sie keine Entscheidung, sondern
#: eine Lücke, die niemand mehr sieht.
AUSGENOMMEN: dict[str, str] = {
    "mailburg.ui.assistent.WillkommenSeite":
        "Seite des Assistenten, dort gemessen",
    "mailburg.ui.assistent.ArchivSeite":
        "Seite des Assistenten, dort gemessen",
    "mailburg.ui.assistent.KontenSeite":
        "Seite des Assistenten, dort gemessen",
    "mailburg.ui.assistent.AbschlussSeite":
        "Seite des Assistenten, dort gemessen",
}


def _klasse(pfad: str):
    """Holt eine Klasse aus ihrem Pfad, ohne sie vorher zu kennen."""
    import importlib

    modul, _, name = pfad.rpartition(".")
    return getattr(importlib.import_module(modul), name)


class _Werkstatt:
    """Was die Fenster zum Aufmachen brauchen, an einer Stelle."""

    def __init__(self, archiv, treffer, konto, rohdaten) -> None:
        self.archiv = archiv
        self.treffer = treffer
        self.konto = konto
        self.rohdaten = rohdaten


def _dialoge(anwendung, archiv) -> list[str]:
    """Jedes Fenster einmal aufmachen und nachmessen."""
    befunde: list[str] = []
    werkstatt = _werkstatt_einrichten(archiv)

    for pfad, name, bauen in BAUPLAENE:
        try:
            fenster = _zeigen(bauen(_klasse(pfad), werkstatt), anwendung)
        except Exception as fehler:
            # **Kein stilles Überspringen.** Ein Fenster, das sich hier
            # nicht aufmachen lässt, ist ein Befund und keine Fußnote:
            # Sonst meldet das Werkzeug »nichts abgeschnitten« über ein
            # Fenster, das es nie gesehen hat.
            befunde.append(f"{name}: lässt sich nicht öffnen – {fehler}")
            continue
        befunde += _befunde(fenster, name)
        befunde += _einzeiler(fenster, name)
        befunde += _spaltenkoepfe(fenster, name)
        _wegnehmen(fenster)

    befunde += _assistent(anwendung)
    befunde += _hauptfenster(anwendung, archiv)

    return befunde


def _werkstatt_einrichten(archiv) -> _Werkstatt:
    """Legt eine Mail ins Archiv, damit die Fenster etwas zu zeigen haben.

    **Ein leeres Archiv prüft die halbe Wahrheit.** Fenster, die Treffer
    aufzählen, sind bei null Treffern schmal und kurz; abgeschnitten wird
    Text erst, wenn welcher da ist. Betreff und Absender sind deshalb so
    lang, wie sie im Alltag werden – und erfunden.
    """
    from mailburg.core.accounts import Konto

    roh = (
        "From: Rechnungsstelle der Lieferanten GmbH "
        "<rechnungen@ein-langer-anbietername.example>\r\n"
        "To: buchhaltung@firma.example\r\n"
        "Subject: Rechnung 2026-0815 vom 14. Januar, "
        "Zahlungsziel 30 Tage netto\r\n"
        "Date: Tue, 14 Jan 2014 09:00:00 +0100\r\n"
        "Message-ID: <probe@ein-langer-anbietername.example>\r\n"
        "\r\n"
        "Sehr geehrte Damen und Herren,\r\n\r\n"
        "anbei die Rechnung zum Vorgang.\r\n"
    ).encode()
    # Das Datum liegt bewusst weit zurück: Nur dann hat die Mail ihre
    # Aufbewahrungsfrist hinter sich, und nur dann hat der Fristendialog
    # etwas aufzuzählen.
    archiv.add(roh, account="Buchhaltung", folder="INBOX")
    treffer = archiv.index.search("", limit=10)

    return _Werkstatt(
        archiv=archiv,
        treffer=treffer,
        konto=Konto(**PROBEKONTEN[1]),
        rohdaten=roh,
    )


def _assistent(anwendung) -> list[str]:
    """Der Einrichtungsassistent, Seite für Seite."""
    from mailburg.ui.assistent import Einrichtungsassistent

    befunde: list[str] = []
    # Keine erfundene Größe: Der Assistent bemisst sich seit dem
    # 2026-08-31 selbst am Bildschirm. Ihn hier zu verkleinern hieße,
    # etwas anderes zu prüfen, als der Anwender zu sehen bekommt.
    assistent = Einrichtungsassistent()
    assistent.show()
    anwendung.processEvents()
    for kennung in assistent.pageIds():
        assistent.setStartId(kennung)
        assistent.restart()
        anwendung.processEvents()
        seite = assistent.page(kennung)
        name = f"Assistent, Seite »{seite.title()}«"
        befunde += _befunde(seite, name)
        befunde += _einzeiler(seite, name)
        befunde += _spaltenkoepfe(seite, name)
    _wegnehmen(assistent)
    return befunde


def _hauptfenster(anwendung, archiv) -> list[str]:
    """Das Fenster, in dem der Anwender die meiste Zeit verbringt.

    **Bis zum 2026-09-10 sah es hier niemand nach.** Geprüft wurden die
    Dialoge und der Assistent – ausgerechnet das Fenster, das den ganzen
    Tag offensteht, war ausgenommen. Der Grund war ein schlechter: Es
    lässt sich offscreen schwerer bemessen als ein Dialog. Das ist ein
    Grund, es zu versuchen, kein Grund, es zu lassen.

    Gemessen wird an einer Größe, die ein kleiner Bildschirm hergibt –
    1280×800. Wer mehr hat, hat es leichter; wer weniger hat, sieht es
    zuerst.
    """
    from unittest import mock

    from mailburg.ui.hauptfenster import Hauptfenster

    befunde: list[str] = []
    # **Die Fristenprüfung beim Start wird hier stillgelegt.** Sie macht
    # einen modalen Dialog auf, sobald eine Mail ihre Aufbewahrungsfrist
    # hinter sich hat – und die Probemail ist von 2014, damit der
    # Fristendialog überhaupt etwas aufzuzählen hat. Modal heißt: Das
    # Werkzeug wartet auf einen Klick, den niemand tut.
    #
    # Das ist kein Wegsehen: Der Fristendialog steht als eigener Eintrag
    # in den Bauplänen und wird dort gemessen. Stillgelegt wird nur, dass
    # er sich *ungefragt* vor das Fenster stellt, das gerade dran ist.
    with mock.patch.object(Hauptfenster, "_fristen_pruefen"):
        fenster = _zeigen(Hauptfenster(archiv.root), anwendung, 1280, 800)

    # Eine Suche mit Treffern: Erst dann steht in der Statuszeile und in
    # der Trefferliste etwas, das zu breit sein könnte.
    fenster.suchfeld.setText("rechnung")
    anwendung.processEvents()

    befunde += _befunde(fenster, "Hauptfenster")
    befunde += _einzeiler(fenster, "Hauptfenster")
    befunde += _spaltenkoepfe(fenster, "Hauptfenster")
    _wegnehmen(fenster)
    return befunde


def _einzeiler(fenster, name: str) -> list[str]:
    """Beschriftungen ohne Umbruch, deren Text nicht hineinpasst.

    **Die Lücke, die das Werkzeug bis zum 2026-09-10 hatte.** Geprüft
    wurden umbrechende Texte auf ihre Höhe und Eingabefelder auf ihre
    Breite – ein einzeiliges ``QLabel`` fiel durch beides. Genau so eines
    trägt aber die Statuszeile: »67.793 Mails im Archiv · zuletzt
    abgerufen: heute 10:31«.

    **Elidierte Beschriftungen zählen nicht.** Wer ``ElideRight`` setzt,
    hat sich für drei Punkte statt eines Abschnitts entschieden; das ist
    kein Versehen.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    gefunden: list[str] = []
    for schild in fenster.findChildren(QLabel):
        text = schild.text().strip()
        if not text or schild.wordWrap() or schild.isHidden():
            continue
        if schild.textFormat() == Qt.RichText or "<" in text:
            # Ausgezeichneter Text lässt sich nicht mit fontMetrics
            # messen - dort stecken Tags, keine Buchstaben.
            continue
        gebraucht = schild.fontMetrics().horizontalAdvance(text)
        vorhanden = schild.width()
        if vorhanden and gebraucht - vorhanden > TOLERANZ:
            gefunden.append(
                f"{name}: Beschriftung ist {vorhanden} px breit, braucht "
                f"{gebraucht} px: »{text[:60]}«"
            )
    return gefunden


def _spaltenkoepfe(fenster, name: str) -> list[str]:
    """Spaltenüberschriften, die ihren eigenen Text abschneiden.

    Eine Spalte darf schmaler sein als ihr Inhalt – dafür gibt es die
    Maus. Ihre **Überschrift** aber ist das, woran man die Spalte
    erkennt: Steht dort »Abse…«, weiß niemand, wonach er sortiert.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHeaderView

    gefunden: list[str] = []
    for kopf in fenster.findChildren(QHeaderView):
        if kopf.isHidden() or kopf.orientation() != Qt.Horizontal:
            continue
        modell = kopf.model()
        if modell is None:
            continue
        for spalte in range(kopf.count()):
            if kopf.isSectionHidden(spalte):
                continue
            text = str(
                modell.headerData(spalte, Qt.Horizontal, Qt.DisplayRole) or ""
            ).strip()
            if not text:
                continue
            # **Eine gedehnte Spalte bekommt den Rest, nicht ein Maß.**
            # Ihre Breite ist das, was nach allen anderen übrig bleibt.
            # Wird sie schmal, liegt das am Platz im Fenster und nicht an
            # dieser Spalte – ein Befund hier zeigte auf sie und meinte
            # etwas anderes. So aufgelaufen am 2026-09-12: In der CI
            # (breitere Schrift als hier) meldete »Betreff ⇅« bei 24 pt
            # zu wenig Platz, bei mir dieselbe Fassung nichts.
            #
            # Dass der Platz bei sehr großer Schrift und schmalem Fenster
            # wirklich knapp wird, steht als offener Punkt in der TODO.
            # Es verschwindet also nicht, es wird nur nicht hier gemeldet.
            if kopf.sectionResizeMode(spalte) == QHeaderView.Stretch:
                UEBERSPRUNGEN.append(
                    f"{name}: gedehnte Spalte »{text}«"
                )
                continue
            # **Qt fragen, nicht schätzen.** Hier stand
            # ``horizontalAdvance(text) + 24`` – eine geratene Zugabe für
            # Rand und Sortierpfeil. Am 2026-09-12 meldete sie zwanzig
            # Befunde, von denen keiner einer war: »Wenn« passte in seine
            # 39 px, die Rechnung verlangte 57.
            #
            # ``sectionSizeHint`` ist die Breite, die Qt selbst für nötig
            # hält – mit dem Rand und dem Pfeil, die dieser Stil wirklich
            # zeichnet. Wer danach fragt, misst dasselbe, was der
            # Anwender sieht.
            #
            # Dieselbe Lehre wie am 2026-09-07 bei den Eingabefeldern:
            # **Ein Prüfwerkzeug, das anders rechnet als die Oberfläche,
            # meldet seine eigene Rechnung als Fehler.** Und wer zweimal
            # umsonst gesucht hat, sieht beim dritten Mal nicht mehr nach.
            gebraucht = kopf.sectionSizeHint(spalte)
            vorhanden = kopf.sectionSize(spalte)
            if vorhanden and gebraucht - vorhanden > TOLERANZ:
                gefunden.append(
                    f"{name}: Spaltenkopf »{text}« ist {vorhanden} px breit, "
                    f"braucht {gebraucht} px"
                )
    return gefunden


def _ausgelassenes_melden() -> None:
    """Sagt, was nicht gemessen wurde – und warum das in Ordnung ist.

    **Zwei Gründe, zwei Überschriften.** Bis zum 2026-09-12 stand über
    allem »weil beim Öffnen versteckt«. Als die gedehnten Spalten
    dazukamen, hätte derselbe Satz über ihnen gestanden – und etwas
    behauptet, das für sie nicht zutrifft. Ein Bericht, der eine
    Auslassung mit dem falschen Grund erklärt, ist schlechter als einer,
    der sie verschweigt: Man kann ihn nicht einmal nachprüfen.
    """
    if not UEBERSPRUNGEN:
        return
    # Bei fünf Schriftgrößen steht sonst jedes Feld fünfmal da.
    UEBERSPRUNGEN[:] = sorted(set(UEBERSPRUNGEN))

    gedehnt = [z for z in UEBERSPRUNGEN if "gedehnte Spalte" in z]
    versteckt = [z for z in UEBERSPRUNGEN if "gedehnte Spalte" not in z]

    if versteckt:
        print(
            f"\nNicht gemessen, weil beim Öffnen versteckt "
            f"({len(versteckt)}):"
        )
        for zeile in versteckt:
            print(f"  {zeile}")
        print(
            "  Solche Felder wachsen beim Einblenden auf ihren Inhalt, das\n"
            "  Fenster wächst mit. Gemessen wäre ihre Breite falsch."
        )

    if gedehnt:
        print(f"\nNicht gemessen, weil gedehnt ({len(gedehnt)}):")
        for zeile in gedehnt:
            print(f"  {zeile}")
        print(
            "  Eine gedehnte Spalte bekommt, was übrig bleibt. Ist das\n"
            "  wenig, liegt es am Platz im Fenster und nicht an ihr."
        )


#: Bei welchen Schriftgrößen geprüft wird. **Eine Größe genügt nicht:**
#: Ein Fenster, das bei 9 pt sitzt, kann bei 16 pt auseinanderfallen –
#: und die Schriftgröße lässt sich in MailBurg einstellen, gerade von
#: denen, die sonst schlecht lesen. Genau bei ihnen darf die Oberfläche
#: nicht schlechter werden.
#:
#: 9 ist die Vorgabe von Breeze, 24 das Ende der Fahnenstange in den
#: Einstellungen.
SCHRIFTGROESSEN = (9, 12, 16, 20, 24)


def alle_groessen() -> list[str]:
    """Prüft jede Fenstergröße bei jeder einstellbaren Schriftgröße."""
    from PySide6.QtWidgets import QApplication

    anwendung = QApplication.instance() or QApplication([])
    ursprung = anwendung.font().pointSize()

    gesammelt: list[str] = []
    try:
        for punkte in SCHRIFTGROESSEN:
            schrift = anwendung.font()
            schrift.setPointSize(punkte)
            anwendung.setFont(schrift)
            gesammelt += [f"{punkte} pt – {zeile}" for zeile in pruefen()]
    finally:
        schrift = anwendung.font()
        schrift.setPointSize(ursprung)
        anwendung.setFont(schrift)
    return gesammelt


def main() -> int:
    befunde = alle_groessen()
    if not befunde:
        print(
            f"Nichts abgeschnitten – alle geprüften Fenster sind lesbar, "
            f"bei {SCHRIFTGROESSEN[0]} bis {SCHRIFTGROESSEN[-1]} pt."
        )
        _ausgelassenes_melden()
        return 0

    print(f"{len(befunde)} Stellen, an denen Text nicht hineinpasst:\n")
    for zeile in befunde:
        print(f"  {zeile}")
    _ausgelassenes_melden()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
