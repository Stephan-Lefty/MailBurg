"""Kontoeinstellungen aus einem vorhandenen Mailprogramm übernehmen.

Wer dreißig Postfächer in Thunderbird eingerichtet hat, will sie nicht ein
zweites Mal von Hand eintippen. Server, Port, Benutzername und
Verschlüsselungsart stehen dort in ``prefs.js`` – einer gewöhnlichen
Textdatei im Profil des Anwenders. Sie zu lesen ist dasselbe, wie sie mit
einem Editor zu öffnen.

**Passwörter werden ausdrücklich nicht übernommen.** Thunderbird legt sie in
``logins.json`` ab, verschlüsselt mit einem Schlüssel aus ``key4.db``. Ohne
Hauptpasswort ließe sich das aufbrechen – und genau deshalb tut MailBurg es
nicht:

* Code, der Passwörter aus dem Profil eines *anderen* Programms herausholt,
  ist das, was Schadsoftware tut. Jeder Virenscanner würde MailBurg dafür
  anschlagen, zu Recht. Auf einem fremden Rechner ausgeführt wäre dieselbe
  Funktion ein Diebstahlwerkzeug.
* Einem Archivprogramm vertraut man jahrzehntealte Geschäftspost an. Dieses
  Vertrauen ist mehr wert als die gesparte Tipparbeit.
* Es nützte oft nicht einmal etwas: Bei Gmail und Outlook liegt in
  Thunderbird ein OAuth-Token, kein Passwort, und für MailBurg braucht es
  dort ohnehin ein eigenes App-Passwort.

Das Passwort fragt MailBurg deshalb einmal je Konto ab. Alles andere kommt
von hier.
"""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass
from pathlib import Path

from mailburg.core.accounts import LOKALE_ADRESSEN, Konto

#: Zeilen in prefs.js sehen aus wie
#: user_pref("mail.server.server2.hostname", "imap.example.org");
_EINSTELLUNG = re.compile(r'user_pref\(\s*"([^"]+)"\s*,\s*(.+?)\s*\)\s*;')

#: Thunderbirds Verschlüsselungsarten. 3 heißt durchgehend verschlüsselt
#: (IMAPS), 2 heißt im Klartext beginnen und auf TLS hochstufen (STARTTLS).
#: 0 und 1 stehen für gar keine Verschlüsselung – solche Konten übernehmen
#: wir zwar, aber mit STARTTLS, weil MailBurg unverschlüsselt nicht anbietet.
_SSL_DIREKT = 3


@dataclass
class Fund:
    """Ein in Thunderbird eingerichtetes Postfach."""

    konto: Konto
    quelle: str
    """Woher es stammt – für die Anzeige, etwa ``server2``."""

    art: str
    """``imap``, ``pop3`` oder was sonst dort stand."""

    @property
    def brauchbar(self) -> bool:
        """Nur IMAP lässt sich abrufen."""
        return self.art == "imap"

    @property
    def begruendung(self) -> str:
        """Warum dieses Konto nicht abgerufen werden kann.

        Wortlos zu übergehen, dass ein Postfach fehlt, wäre die schlechteste
        Auskunft – der Anwender soll wissen, welcher Weg stattdessen
        offensteht.
        """
        # Thunderbird schreibt »pop3«, Evolution »pop« – gemeint ist
        # dasselbe.
        if self.art in ("pop3", "pop"):
            return (
                "POP3 holt die Mails auf den Rechner; auf dem Server bleibt "
                "nichts zum Abrufen. Stattdessen »Post → Lokale Mailordner "
                "einlesen …« mit dem Profilordner – das liest die Dateien "
                "auf der Platte."
            )
        if self.art == "ews":
            return (
                "Exchange Web Services spricht kein IMAP. Für dasselbe "
                "Postfach lässt sich bei Exchange und Microsoft 365 fast "
                "immer zusätzlich IMAP freischalten; danach hier erneut "
                "übernehmen."
            )
        return f"Kontoart '{self.art}' kann MailBurg nicht abrufen."



def _werte_lesen(text: str) -> dict[str, object]:
    """Zieht alle ``user_pref``-Zeilen aus einer Thunderbird-Einstellungsdatei."""
    werte: dict[str, object] = {}
    for schluessel, roh in _EINSTELLUNG.findall(text):
        roh = roh.strip()
        if roh.startswith('"') and roh.endswith('"'):
            # Thunderbird schreibt Sonderzeichen als \" und \\ – mehr an
            # Maskierung kommt in diesen Werten nicht vor.
            werte[schluessel] = roh[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        elif roh in ("true", "false"):
            werte[schluessel] = roh == "true"
        else:
            try:
                werte[schluessel] = int(roh)
            except ValueError:
                werte[schluessel] = roh
    return werte


def aus_thunderbird(profil: Path) -> list[Fund]:
    """Liest die eingerichteten Postfächer aus einem Thunderbird-Profil.

    Gibt auch die POP3-Konten zurück, damit der Aufrufer sagen kann, warum
    sie nicht in Frage kommen – wortlos zu verschweigen, dass ein Konto
    übergangen wurde, wäre die schlechtere Auskunft.
    """
    datei = Path(profil).expanduser() / "prefs.js"
    if not datei.is_file():
        raise FileNotFoundError(
            f"In {profil} liegt keine prefs.js – das ist kein Thunderbird-Profil."
        )

    werte = _werte_lesen(datei.read_text(encoding="utf-8", errors="replace"))

    # Alle Kennungen einsammeln, die überhaupt vorkommen: mail.server.serverN.*
    kennungen = sorted(
        {
            schluessel.split(".")[2]
            for schluessel in werte
            if schluessel.startswith("mail.server.server") and schluessel.count(".") >= 3
        },
        key=lambda k: int(k[6:]) if k[6:].isdigit() else 0,
    )

    gefunden: list[Fund] = []
    for kennung in kennungen:
        def wert(feld: str, vorgabe=None):
            return werte.get(f"mail.server.{kennung}.{feld}", vorgabe)

        art = str(wert("type", "")).lower()
        server = str(wert("hostname", "") or "")
        benutzer = str(wert("userName", "") or "")

        # "Lokale Ordner" und Nachrichtenkonten haben keinen Server. Ohne
        # Hostnamen ist auch nichts abzurufen.
        if not server or art in ("none", "rss", "nntp"):
            continue

        ssl = int(wert("socketType", _SSL_DIREKT) or 0) == _SSL_DIREKT
        port = int(wert("port", 0) or 0) or (993 if ssl else 143)

        name = str(wert("name", "") or "").strip()
        if not name:
            # Ohne Anzeigenamen der Benutzername, sonst der Server. Ein
            # Konto ohne Namen wäre in der Trefferliste nicht zuzuordnen.
            name = benutzer.split("@")[0] if benutzer else server

        # Ein Postfach auf dem eigenen Rechner kann nur ein
        # Brückenprogramm sein – Proton Mail Bridge, Tuta Desktop und
        # ähnliche. Die weisen sich zwangsläufig selbstsigniert aus.
        bruecke = server.lower() in LOKALE_ADRESSEN

        gefunden.append(
            Fund(
                konto=Konto(
                    name=name,
                    server=server,
                    benutzer=benutzer or name,
                    port=port,
                    ssl=ssl,
                    bruecke=bruecke,
                ),
                quelle=kennung,
                art=art,
            )
        )

    return gefunden


def namen_entzerren(funde: list[Fund], vergeben: set[str]) -> None:
    """Sorgt dafür, dass jeder Kurzname nur einmal vorkommt.

    Thunderbird lässt zwei Konten denselben Anzeigenamen tragen, MailBurg
    nicht – der Name ist im Archiv die Zuordnung einer Mail zu ihrem
    Postfach. Doppelte bekommen den Server angehängt, und wenn das nicht
    reicht, eine Nummer.
    """
    for fund in funde:
        if fund.konto.name not in vergeben:
            vergeben.add(fund.konto.name)
            continue

        kandidat = f"{fund.konto.name} ({fund.konto.server})"
        zaehler = 2
        while kandidat in vergeben:
            kandidat = f"{fund.konto.name} ({fund.konto.server}) {zaehler}"
            zaehler += 1
        fund.konto.name = kandidat
        vergeben.add(kandidat)


# --------------------------------------------------------------- Evolution
#
# **Warum Evolution überhaupt dazukam.** Ein Anwender ist unter GNOME
# von Thunderbird auf Evolution umgestiegen und schrieb am 2026-09-03:
# »Wünschenswert für die Zukunft wäre also auch ein Import der Konten aus
# Evolution.« Bis dahin las MailBurg nur Thunderbird – wer Evolution
# benutzt, tippte alles von Hand.
#
# Evolution legt jedes Konto als eigene Datei unter
# ``~/.config/evolution/sources/`` ab, im Format von GKeyFile: gewöhnliche
# INI-Abschnitte. Was MailBurg braucht, steht in dreien davon –
# ``[Data Source]`` für den Namen, ``[Mail Account]`` für die Kontoart und
# ``[Authentication]`` für Server, Port und Benutzer.

#: Evolutions Name für IMAP. ``imapx`` ist die neuere Umsetzung; ``imap``
#: kommt in älteren Profilen vor.
_EVOLUTION_IMAP = {"imapx", "imap"}

#: Was in ``[Security] Method`` steht, wenn die Verbindung von Anfang an
#: verschlüsselt ist. ``starttls`` heißt: im Klartext beginnen und
#: hochstufen; ``none`` heißt gar nicht – das bietet MailBurg nicht an,
#: solche Konten kommen deshalb mit STARTTLS herein.
_EVOLUTION_SSL = {"tls", "ssl"}


def evolution_verzeichnisse() -> list[Path]:
    """Wo Evolution seine Kontodateien ablegen könnte."""
    heim = Path.home()
    return [
        heim / ".config" / "evolution" / "sources",
        # Flatpak sperrt die Anwendung in ein eigenes Verzeichnis.
        heim / ".var" / "app" / "org.gnome.Evolution" / "config"
        / "evolution" / "sources",
    ]


def evolution_gefunden() -> Path | None:
    """Das erste vorhandene Kontoverzeichnis – oder nichts."""
    for ort in evolution_verzeichnisse():
        if ort.is_dir():
            return ort
    return None


def aus_evolution(ordner: Path) -> list[Fund]:
    """Liest die eingerichteten Postfächer aus Evolutions Kontodateien.

    Wie bei Thunderbird gilt: **Passwörter bleiben, wo sie sind.**
    Evolution legt sie im Schlüsselbund von GNOME ab; sie von dort zu
    holen wäre genau das, was Schadsoftware tut. Die Begründung steht
    ausführlich oben im Modul und gilt hier unverändert.

    Zurückgegeben werden auch POP3- und Exchange-Konten, damit der
    Aufrufer sagen kann, warum sie nicht in Frage kommen.
    """
    ordner = Path(ordner).expanduser()
    if not ordner.is_dir():
        raise FileNotFoundError(
            f"{ordner} gibt es nicht – dort legt Evolution seine Konten ab."
        )

    dateien = sorted(ordner.glob("*.source"))
    if not dateien:
        raise FileNotFoundError(
            f"In {ordner} liegt keine einzige .source-Datei – das sieht "
            f"nicht nach Evolutions Kontoverzeichnis aus."
        )

    gefunden: list[Fund] = []
    for datei in dateien:
        fund = _evolution_datei(datei)
        if fund is not None:
            gefunden.append(fund)
    return gefunden


def _evolution_datei(datei: Path) -> Fund | None:
    """Wertet eine einzelne ``.source``-Datei aus, oder gibt nichts."""
    lese = configparser.ConfigParser(interpolation=None)
    # **Ohne das macht configparser alle Schlüssel klein.** Evolution
    # schreibt sie in Großschreibung (``Host``, ``User``), und dann fände
    # man nichts wieder.
    lese.optionxform = str
    try:
        lese.read(datei, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError, OSError):
        # Eine unlesbare Datei darf die übrigen nicht kosten – in diesem
        # Verzeichnis liegen auch Adressbücher und Kalender.
        return None

    if not lese.has_section("Mail Account"):
        return None

    art = lese.get("Mail Account", "BackendName", fallback="").strip().lower()
    if not art or art == "none":
        # »Auf diesem Rechner« – die lokalen Ordner. Die kommen über
        # »Lokale Mailordner einlesen« herein, nicht als Postfach.
        return None

    anmeldung = "Authentication"
    server = lese.get(anmeldung, "Host", fallback="").strip()
    if not server:
        return None

    benutzer = lese.get(anmeldung, "User", fallback="").strip()
    name = lese.get("Data Source", "DisplayName", fallback="").strip()
    if not name:
        name = benutzer.split("@")[0] if benutzer else server

    sicherheit = lese.get("Security", "Method", fallback="tls").strip().lower()
    ssl = sicherheit in _EVOLUTION_SSL

    try:
        port = int(lese.get(anmeldung, "Port", fallback="0") or 0)
    except ValueError:
        port = 0
    port = port or (993 if ssl else 143)

    return Fund(
        konto=Konto(
            name=name,
            server=server,
            benutzer=benutzer or name,
            port=port,
            ssl=ssl,
            bruecke=server.lower() in LOKALE_ADRESSEN,
        ),
        quelle=datei.stem,
        art="imap" if art in _EVOLUTION_IMAP else art,
    )


@dataclass
class Quelle:
    """Ein Mailprogramm, aus dem sich Konten übernehmen lassen."""

    programm: str
    """Wie es heißt – für die Anzeige."""

    ort: Path
    """Profil oder Kontoverzeichnis."""

    lesen: object
    """Die Funktion, die daraus Funde macht."""

    def funde(self) -> list[Fund]:
        return self.lesen(self.ort)


def alle_quellen() -> list[Quelle]:
    """Sucht alle Mailprogramme, aus denen sich übernehmen lässt.

    **Eine Stelle, die weiß, welche Programme es gibt.** Vorher kannte
    jeder Aufrufer nur Thunderbird und nannte es beim Namen – die
    Kommandozeile, der Assistent, der Kontendialog. Evolution
    hinzuzufügen hieße sonst, dieselbe Ergänzung dreimal zu machen und
    beim vierten Aufrufer zu vergessen.

    Dasselbe Muster wie ``sources.quelle_fuer()`` beim Abrufweg, und aus
    demselben Grund: Es funktioniert an drei Stellen und an der vierten
    nicht – das Merkwürdigste, was ein Programm tun kann.
    """
    from mailburg.sources import local

    gefunden: list[Quelle] = []
    for profil in local.find_thunderbird_profiles():
        gefunden.append(Quelle("Thunderbird", profil, aus_thunderbird))

    ort = evolution_gefunden()
    if ort is not None:
        gefunden.append(Quelle("Evolution", ort, aus_evolution))

    return gefunden
