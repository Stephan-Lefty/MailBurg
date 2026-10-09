"""Der Tagesbericht an den Verwalter.

**Warum ein Archivdienst eine Mail schreibt, obwohl er sonst nur
liest.** Ein Dienst, der still arbeitet, ist von einem Dienst, der still
*nicht* arbeitet, nicht zu unterscheiden. Genau das ist am 2026-10-06
passiert: Der Abruf scheiterte seit Tagen in seiner ersten Zeile, der
Dienst lief weiter, die Statusseite meldete »alle 30 Minuten«, und
gesehen hat es niemand – die Meldung stand im Ereignisprotokoll, wo man
nur nachsieht, wenn man schon etwas ahnt.

Eine Mail dreht das um: Sie kommt dorthin, wo ein Verwalter ohnehin
hinsieht.

**Der Wortlaut ist dabei die halbe Funktion.** »Das Archiv wurde
überprüft und ist in Ordnung« darf nur dastehen, wenn es stimmt – sonst
ist es dieselbe Falle wie »Nichts Neues in 7 Postfächern«, während
sieben Postfächer gescheitert waren. Steht etwas nicht zum Besten,
gehört es nach oben, nicht ans Ende.

**Und das Ausbleiben ist selbst eine Nachricht.** Wer eine tägliche Mail
gewohnt ist, merkt ihr Fehlen. Deshalb ist der tägliche Bericht die
Vorgabe und nicht »nur bei Befund«.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, time as uhrzeit
from pathlib import Path

#: Wohin der Bericht geht. Leer heißt: kein Bericht.
AN = "MAILBURG_BERICHT_AN"

#: Wann, als ``HH:MM``. Ohne Angabe gilt :data:`STANDARDZEIT`.
UHR = "MAILBURG_BERICHT_UHR"
STANDARDZEIT = uhrzeit(7, 0)

#: Wie oft berichtet wird, wenn **alles in Ordnung** ist – in Tagen.
#:
#: **Störungen gehen davon unberührt sofort hinaus.** Der Takt regelt
#: nur die gute Nachricht; die schlechte wartet nie.
#:
#: Täglich ist für einen Firmenserver richtig, für ein Privatarchiv zu
#: viel: Wer dreißig gleichlautende Mails im Monat bekommt, liest keine
#: davon – und dann ist auch die einunddreißigste wertlos, die etwas
#: anderes sagt.
TAKT = "MAILBURG_BERICHT_TAKT"
STANDARDTAKT = 1

#: Was sich einstellen lässt: Beschriftung und Tage.
TAKTE = (
    ("täglich", 1),
    ("alle 7 Tage", 7),
    ("alle 14 Tage", 14),
    ("alle 30 Tage", 30),
)

#: Der Postausgangsserver, als ``name`` oder ``name:port``.
#:
#: **Ausdrücklich nicht eines der archivierten Postfächer.** Wer den
#: Bericht über dasselbe Konto schickt, das archiviert wird, bekommt ihn
#: beim nächsten Abruf ins Archiv zurück – und ein Archiv, das sich mit
#: seinen eigenen Statusmeldungen füllt, ist ein schlechter Scherz.
SMTP = "MAILBURG_BERICHT_SMTP"
STANDARDANSCHLUSS = 587

#: Absenderadresse und Anmeldename am Postausgangsserver.
VON = "MAILBURG_BERICHT_VON"
BENUTZER = "MAILBURG_BERICHT_BENUTZER"

#: Unter diesem Namen liegt das Versandpasswort im Tresor – **nicht** in
#: der Registry. Dieselbe Begründung wie bei den Postfächern: Was ein
#: Dienst ohne Zutun braucht, muss er finden können, und es soll trotzdem
#: nicht im Klartext neben der Konfiguration stehen.
TRESORSCHLUESSEL = "mailburg-bericht-smtp"


@dataclass
class Lage:
    """Wie der Tagesbericht eingestellt ist."""

    an: str = ""
    zeit: uhrzeit = STANDARDZEIT
    takt_tage: int = STANDARDTAKT
    smtp: str = ""
    anschluss: int = STANDARDANSCHLUSS
    von: str = ""
    benutzer: str = ""

    @property
    def eingerichtet(self) -> bool:
        """Ob überhaupt berichtet werden kann.

        **Alle drei oder keines.** Eine Empfängeradresse ohne
        Postausgangsserver sieht eingerichtet aus und verschickt nichts –
        genau die Sorte Halbzustand, die dieses Projekt sonst bei anderen
        findet.

        **Und es muss wirklich eine Adresse herauskommen.** Hier stand
        bis zum 2026-10-09 nur ``bool(self.an …)``, also: steht etwas
        im Feld. Was darin steht, kann aber unbrauchbar sein, und
        Python verwirft dann die **ganze** Liste statt nur des
        kaputten Teils – gemessen auf 3.14:

            'chef@example.org,'  ->  [('', '')]
            'a@example.org;b@example.net'  ->  [('', '')]

        Ein Komma zu viel, und der Bericht ginge an niemanden,
        während das Feld gefüllt aussieht.
        """
        return bool(self.adressen and self.smtp and self.von)

    @property
    def empfaenger(self) -> str:
        """Die Empfängerliste, wie sie ins Mailformat gehört.

        **Semikolon ist der Trenner, den Outlook anzeigt – nicht der,
        den das Mailformat kennt.** Dort gilt das Komma. Wer
        ``a@example.org; b@example.net`` einträgt, bekommt beim
        Zerlegen genau das hier:

            [('', 'a@example.org'), ('', '')]

        Die zweite Adresse ist weg, **ohne Fehlermeldung**. Der Bericht
        geht an den ersten Empfänger; der zweite wartet auf eine
        Warnung, die nie kommt – und merkt es nicht, denn ein
        ausbleibender Bericht sieht aus wie ein Tag ohne Störung.

        **Und die Probe im Einrichtungsfenster bestätigte das sogar.**
        Sie nimmt denselben Weg, der Mailserver nimmt die Nachricht für
        den ersten Empfänger an, nichts wirft – also meldet der Knopf
        Erfolg. Ausgerechnet die Prüfung, die den Fehler aufdecken
        müsste, verdeckte ihn. Am 2026-10-09 aus einer Frage im Betrieb
        gefallen: »Kann ich mehrere Mailadressen mit ; angeben?«

        Deshalb wird das Semikolon angenommen und umgesetzt. **Nur
        außerhalb von Anführungszeichen:** ``"Müller; Hans"
        <h@example.org>`` ist ein einziger Empfänger mit einem
        Semikolon im Namen, und den zu zerreißen wäre derselbe Schaden
        in die andere Richtung.
        """
        heraus = []
        in_anfuehrung = False
        for zeichen in self.an:
            if zeichen == '"':
                in_anfuehrung = not in_anfuehrung
            if zeichen == ";" and not in_anfuehrung:
                heraus.append(",")
            else:
                heraus.append(zeichen)
        return "".join(heraus)

    @property
    def adressen(self) -> list[str]:
        """Wer den Bericht wirklich bekommt – eine Adresse je Eintrag.

        **Damit eine Probe sagen kann, an wen sie ging.** Die Meldung
        im Einrichtungsfenster nannte bis zum 2026-10-09 das
        Eingabefeld im Wortlaut (»ging an a@…; b@… hinaus«) – also
        das, was jemand getippt hatte, und nicht das, was geschehen
        war. Wer zwei Adressen eintippt und zwei bestätigt bekommt,
        prüft nichts nach.

        Leere Einträge fallen heraus: Sie entstehen aus einem Komma zu
        viel und sind keine Empfänger.
        """
        from email.utils import getaddresses

        return [adr for _, adr in getaddresses([self.empfaenger]) if adr]

    @classmethod
    def aus_umgebung(cls) -> Lage:
        smtp, anschluss = _server_lesen(os.environ.get(SMTP, ""))
        return cls(
            an=os.environ.get(AN, "").strip(),
            zeit=zeit_lesen(os.environ.get(UHR, "")) or STANDARDZEIT,
            takt_tage=takt_lesen(os.environ.get(TAKT, "")),
            smtp=smtp,
            anschluss=anschluss,
            von=os.environ.get(VON, "").strip(),
            benutzer=os.environ.get(BENUTZER, "").strip(),
        )


def takt_lesen(roh: str) -> int:
    """Wie viele Tage zwischen zwei guten Nachrichten liegen.

    **Unsinn wird zu »täglich«, nicht zu »nie«.** Ein Tippfehler darf
    den Bericht nicht stillschweigend abschalten – dann wäre sein
    Ausbleiben kein Signal mehr, und darauf beruht die ganze Funktion.
    Zu viele Mails fallen auf, zu wenige nicht.
    """
    roh = roh.strip()
    if not roh.isdigit():
        return STANDARDTAKT
    tage = int(roh)
    return tage if tage >= 1 else STANDARDTAKT


def _server_lesen(roh: str) -> tuple[str, int]:
    """``mail.example.org:587`` in Name und Anschluss zerlegen."""
    roh = roh.strip()
    if not roh:
        return "", STANDARDANSCHLUSS
    if ":" in roh:
        name, _, zahl = roh.rpartition(":")
        if zahl.isdigit():
            return name.strip(), int(zahl)
    return roh, STANDARDANSCHLUSS


def zeit_lesen(roh: str) -> uhrzeit | None:
    """``07:00`` als Uhrzeit – oder nichts, wenn es keine ist.

    **Unsinn schaltet nicht ab, sondern fällt auf die Vorgabe zurück.**
    Ein Tippfehler in der Uhrzeit darf nicht dazu führen, dass der
    Bericht stillschweigend ausbleibt; dann wäre das Ausbleiben kein
    Signal mehr.
    """
    roh = roh.strip()
    if not roh:
        return None
    try:
        stunde, _, minute = roh.partition(":")
        return uhrzeit(int(stunde), int(minute or 0))
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------- Der Stand


@dataclass
class Stand:
    """Was seit dem letzten Bericht geschehen ist.

    Liegt neben dem Abrufzustand, nicht im Archiv: Es ist eine Sache des
    Dienstes, nicht des Bestands. Ein Archiv, das auf einen anderen
    Rechner zieht, soll dort nicht glauben, es habe gestern berichtet.
    """

    zuletzt: datetime | None = None
    mails_zuletzt: int = 0
    stoerung: str = ""
    """Die zuletzt gemeldete Störung, damit sie nicht täglich wiederkommt.

    **Eine Meldung, die sich wiederholt, wird weggefiltert.** Wer
    dreimal dieselbe Zeile bekommt, legt eine Regel an – und bekommt
    danach auch die vierte nicht mehr, die etwas anderes sagt.
    """

    @classmethod
    def lesen(cls, datei: Path) -> Stand:
        try:
            daten = json.loads(datei.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        roh = daten.get("zuletzt")
        try:
            zuletzt = datetime.fromisoformat(roh) if roh else None
        except (TypeError, ValueError):
            zuletzt = None
        return cls(
            zuletzt=zuletzt,
            mails_zuletzt=int(daten.get("mails", 0)),
            stoerung=str(daten.get("stoerung", "")),
        )

    def schreiben(self, datei: Path, *, jetzt: datetime | None = None,
                  mails: int | None = None,
                  stoerung: str | None = None) -> None:
        """Schreibt den Stand – nur das, was angegeben ist.

        Eine Störungsmeldung darf den Zeitpunkt des Tagesberichts nicht
        verstellen; sonst bliebe der Bericht am nächsten Morgen aus,
        weil nachts eine Störung gemeldet wurde.
        """
        if jetzt is not None:
            self.zuletzt = jetzt
        if mails is not None:
            self.mails_zuletzt = mails
        if stoerung is not None:
            self.stoerung = stoerung

        datei.parent.mkdir(parents=True, exist_ok=True)
        neben = datei.with_suffix(".json.neu")
        neben.write_text(
            json.dumps(
                {
                    "zuletzt": (
                        self.zuletzt.isoformat() if self.zuletzt else None
                    ),
                    "mails": self.mails_zuletzt,
                    "stoerung": self.stoerung,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        neben.replace(datei)


# -------------------------------------------------------------- Der Text


def _wann(zeitpunkt: datetime | None) -> str:
    if zeitpunkt is None:
        return "dem ersten Bericht"
    return zeitpunkt.strftime("%d.%m.%Y, %H:%M Uhr")


def bericht_bauen(name: str, dazu: int, gesamt: int,
                  seit: datetime | None, pruefung: tuple[str, bool],
                  abruf: str = "") -> tuple[str, str, bool]:
    """Betreff, Text und ob etwas zu beanstanden ist.

    ``pruefung`` ist das Ergebnis der Archivprüfung: der Text und ob er
    heikel ist.

    **Der Betreff trägt den Befund.** Wer dreißig Tagesmails im Postfach
    hat, liest keine davon – aber einen Betreff, der sich ändert, sieht
    er. Deshalb steht dort »in Ordnung« oder »BITTE NACHSEHEN«, und nicht
    jeden Tag dasselbe.
    """
    text, heikel = pruefung

    zeilen = [
        f"Archiv: {name}",
        "",
        f"Seit {_wann(seit)} wurden {dazu} Mails abgerufen und im Archiv "
        f"verarbeitet.",
        f"Im Archiv liegen jetzt {gesamt} Mails.",
        "",
    ]

    if heikel:
        # **Der Befund zuerst.** Wer die Mail überfliegt, soll ihn nicht
        # suchen müssen.
        zeilen.insert(0, "Das Archiv hat eine Beanstandung:")
        zeilen.insert(1, "")

    zeilen.append(text)

    if abruf:
        zeilen.append("")
        zeilen.append(f"Letzter Abruf: {abruf}")

    zeilen.append("")
    zeilen.append(
        "Diese Nachricht kommt von MailBurg auf Ihrem Server. Bleibt sie "
        "einmal aus, läuft der Dienst nicht mehr – das ist dann selbst "
        "der Befund."
    )

    betreff = (
        f"MailBurg: BITTE NACHSEHEN – {name}" if heikel
        else f"MailBurg: {name} in Ordnung, {dazu} neue Mails"
    )
    return betreff, "\n".join(zeilen), heikel


def stoerung_bauen(name: str, was: str) -> tuple[str, str]:
    """Betreff und Text einer Sofortmeldung.

    **Nicht auf den nächsten Morgen warten.** Ein Abruf, der scheitert,
    kostet mit jeder Stunde mehr – und wer um sieben erfährt, dass seit
    Mitternacht nichts mehr ankommt, hat sieben Stunden verloren.
    """
    text = "\n".join([
        f"Archiv: {name}",
        "",
        "MailBurg meldet eine Störung:",
        "",
        was,
        "",
        "Diese Nachricht kommt sofort und nicht erst zum Tagesbericht. "
        "Sie wird nicht wiederholt, solange die Störung dieselbe bleibt – "
        "und es kommt eine Entwarnung, sobald sie behoben ist.",
    ])
    return f"MailBurg: STÖRUNG – {name}", text


def entwarnung_bauen(name: str, vorher: str) -> tuple[str, str]:
    """Betreff und Text, wenn eine gemeldete Störung vorbei ist.

    **Ohne Entwarnung ist eine Störungsmeldung halb so viel wert.** Wer
    abends eine bekommt und morgens nichts hört, weiß nicht, ob es
    wieder läuft oder ob auch die Meldung nicht mehr durchkommt.
    """
    text = "\n".join([
        f"Archiv: {name}",
        "",
        "Die gemeldete Störung ist behoben. MailBurg arbeitet wieder.",
        "",
        f"Es ging um: {vorher}",
    ])
    return f"MailBurg: wieder in Ordnung – {name}", text


def faellig(lage: Lage, stand: Stand, jetzt: datetime) -> bool:
    """Ist die gute Nachricht wieder dran?

    **Nicht »ist es genau sieben Uhr«.** Der Dienst sieht alle paar
    Minuten nach; eine Uhrzeit auf die Sekunde zu treffen wäre Zufall.
    Und wer den Server um acht einschaltet, soll den Bericht trotzdem
    bekommen und nicht einen Tag warten.

    **Der Takt gilt nur hier.** Eine Störung geht sofort hinaus, ganz
    gleich, ob zuletzt vorgestern berichtet wurde.
    """
    from datetime import timedelta

    if not lage.eingerichtet:
        return False
    heute = datetime.combine(jetzt.date(), lage.zeit)
    if jetzt < heute:
        return False
    if stand.zuletzt is None:
        return True
    schwelle = heute - timedelta(days=max(1, lage.takt_tage) - 1)
    return stand.zuletzt < schwelle


def pruefbericht(bericht: dict) -> tuple[str, bool]:
    """Macht aus ``Archive.verify()`` einen Text für Menschen.

    Gibt den Text zurück und ob er heikel ist – daran entscheidet das
    Fenster, ob es eine Warnung zeigt oder eine Mitteilung.

    **Eigene Funktion und nicht im Fenster.** So lässt sie sich ohne Qt
    prüfen, und zwar für alle Fälle: ein heiles Archiv, eine gerissene
    Kette, fehlende Dateien, untergeschobene Dateien. Genau diese Fälle
    sieht ein Verwalter höchstens einmal – und dann muss der Text
    stimmen.

    **Ein Befund ohne Weg ist nur eine schlechte Nachricht.** Wer liest,
    dass die Hash-Kette beschädigt ist, muss erfahren, was das heißt:
    Die Mails sind da, die Lückenlosigkeit ist es nicht.
    """
    zeilen: list[str] = []
    heikel = False

    if bericht["chain_ok"] and bericht.get("chain_bekannt"):
        zeilen.append(
            f"Hash-Kette: schlüssig bis auf "
            f"{len(bericht['chain_bekannt'])} vermerkte Stelle(n), "
            f"{bericht['chain_entries']} Einträge."
        )
    elif bericht["chain_ok"]:
        zeilen.append(
            f"Hash-Kette: unversehrt, {bericht['chain_entries']} Einträge."
        )
    else:
        heikel = True
        zeilen.append(
            f"Hash-Kette: BESCHÄDIGT an "
            f"{len(bericht['chain_errors'])} Stelle(n)."
        )

    fehlend = bericht.get("missing") or []
    fremd = bericht.get("unexpected") or []
    unvollstaendig = bericht.get("unvollstaendig") or []

    if fehlend:
        heikel = True
        zeilen.append(
            f"{len(fehlend)} Mail(s) stehen im Journal, liegen aber nicht "
            f"mehr auf der Platte."
        )
    if fremd:
        heikel = True
        zeilen.append(
            f"{len(fremd)} Datei(en) liegen im Archiv, ohne im Journal zu "
            f"stehen – sie sind nicht archiviert, sondern untergeschoben."
        )
    if unvollstaendig:
        heikel = True
        zeilen.append(
            f"{len(unvollstaendig)} Journaleintrag/-einträge sagen nicht, "
            f"welche Mail sie meinen."
        )

    if not heikel:
        zeilen.append("Ablage: jede Mail am Platz, nichts Fremdes dabei.")
        zeilen.append("")
        zeilen.append("Das Archiv ist in Ordnung.")
        return "\n".join(zeilen), False

    zeilen.append("")
    zeilen.append(
        "Was das heißt: Die Mails selbst sind davon nicht betroffen – "
        "beanstandet ist die Lückenlosigkeit, also der Nachweis, dass "
        "nichts nachträglich geändert wurde."
    )
    zeilen.append(
        "Was zu tun ist: Nichts überschreiben und nichts aufräumen. "
        "Eine bekannte Ursache lässt sich festhalten "
        "(»mailburg kettenvermerk«), damit sie erklärt ist statt "
        "verschwiegen. Vorher den Grund suchen – ein zweiter Vorgang am "
        "selben Archiv ist der häufigste."
    )
    return "\n".join(zeilen), True


def tresorbericht(eintraege: int, schlecht: list[str], ohne: list[str],
                  konten: int) -> tuple[str, bool]:
    """Reicht der Tresor für die eingerichteten Postfächer?

    Dieselbe Trennung wie bei :func:`pruefbericht` und aus demselben
    Grund: Der Text ist das Eigentliche, und er soll ohne Fenster
    prüfbar sein.

    **Beide Richtungen zählen.** Ein Postfach ohne Eintrag kann der
    Dienst nicht abrufen – und er meldet das nicht als Fehler, er
    überspringt es. Ein Eintrag ohne Postfach ist ein fremdes Passwort
    auf einem Rechner, an dem mehrere Menschen arbeiten.
    """
    zeilen = [f"Im Tresor liegen {eintraege} Einträge."]
    heikel = False

    if schlecht:
        heikel = True
        zeilen.append(
            f"{len(schlecht)} davon lassen sich nicht öffnen – vermutlich "
            f"der falsche Hauptschlüssel, oder die Datei stammt von einem "
            f"anderen Rechner."
        )
    if ohne:
        heikel = True
        zeilen.append("")
        zeilen.append(
            f"Ohne Anmeldung: {', '.join(ohne)} "
            f"({len(ohne)} von {konten} Postfächern)."
        )
        zeilen.append(
            "Von dort holt der Dienst keine Post. Er meldet das nicht als "
            "Fehler – es kommt einfach nichts an."
        )
        zeilen.append(
            "Nachtragen auf dem Rechner, auf dem die Postfächer "
            "eingerichtet sind: mailburg tresor uebernehmen"
        )

    if not heikel:
        zeilen.append(
            f"Alle {konten} eingerichteten Postfächer haben eine Anmeldung."
        )
    return "\n".join(zeilen), heikel


# ------------------------------------------------------------- Der Versand


class VersandFehler(RuntimeError):
    """Die Mail ging nicht hinaus."""


def senden(lage: Lage, betreff: str, text: str, passwort: str = "",
           *, verbinden=None) -> None:
    """Schickt den Bericht über den eingestellten Postausgangsserver.

    ``verbinden`` ist für die Tests da: eine Stelle, an der sich der
    SMTP-Aufbau ersetzen lässt, ohne dass ein Netz nötig wäre.

    **STARTTLS, und ohne geht es nicht weiter.** Ein Bericht über den
    Zustand eines Archivs nennt Zahlen, die niemanden sonst angehen, und
    die Anmeldung ginge im Klartext über die Leitung. Wer einen Server
    ohne TLS hat, bekommt eine Absage statt einer stillen Herabstufung.
    """
    from email.message import EmailMessage

    if not lage.eingerichtet:
        raise VersandFehler(
            "Der Tagesbericht ist nicht vollständig eingerichtet: Es "
            "fehlen Empfänger, Postausgangsserver oder Absender."
        )

    nachricht = EmailMessage()
    nachricht["From"] = lage.von
    # ``empfaenger``, nicht ``an``: Dort wird ein Semikolon zum Komma.
    # Siehe die Begründung an der Eigenschaft – ein Trenner, den das
    # Mailformat nicht kennt, verschluckt stillschweigend alle
    # Empfänger außer dem ersten.
    nachricht["To"] = lage.empfaenger
    nachricht["Subject"] = betreff
    nachricht.set_content(text)

    aufbau = verbinden or _smtp_verbinden
    try:
        with aufbau(lage.smtp, lage.anschluss) as server:
            server.starttls()
            if lage.benutzer and passwort:
                server.login(lage.benutzer, passwort)
            server.send_message(nachricht)
    except VersandFehler:
        raise
    except Exception as fehler:  # noqa: BLE001
        raise VersandFehler(str(fehler)) from fehler


def _smtp_verbinden(server: str, anschluss: int):
    import smtplib

    return smtplib.SMTP(server, anschluss, timeout=30)
