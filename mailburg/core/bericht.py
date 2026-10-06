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
        """
        return bool(self.an and self.smtp and self.von)

    @classmethod
    def aus_umgebung(cls) -> Lage:
        smtp, anschluss = _server_lesen(os.environ.get(SMTP, ""))
        return cls(
            an=os.environ.get(AN, "").strip(),
            zeit=zeit_lesen(os.environ.get(UHR, "")) or STANDARDZEIT,
            smtp=smtp,
            anschluss=anschluss,
            von=os.environ.get(VON, "").strip(),
            benutzer=os.environ.get(BENUTZER, "").strip(),
        )


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
    """Ist die Berichtszeit seit dem letzten Bericht vorbeigekommen?

    **Nicht »ist es genau sieben Uhr«.** Der Dienst sieht alle paar
    Minuten nach; eine Uhrzeit auf die Sekunde zu treffen wäre Zufall.
    Und wer den Server um acht einschaltet, soll den Bericht trotzdem
    bekommen und nicht einen Tag warten.
    """
    if not lage.eingerichtet:
        return False
    heute = datetime.combine(jetzt.date(), lage.zeit)
    if jetzt < heute:
        return False
    return stand.zuletzt is None or stand.zuletzt < heute


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
    nachricht["To"] = lage.an
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
