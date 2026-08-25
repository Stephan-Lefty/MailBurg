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
        if self.art == "pop3":
            return (
                "POP3 holt die Mails auf den Rechner; auf dem Server bleibt "
                "nichts zum Abrufen. Stattdessen 'mailburg importieren' mit "
                "dem Profilpfad – das liest die lokalen Dateien."
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
