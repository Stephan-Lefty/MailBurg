"""Passwörter auf einem Rechner ohne Schlüsselbund.

**Das Problem.** MailBurg legt Postfach-Passwörter im Schlüsselbund des
Betriebssystems ab. Der hängt an einer Anmeldesitzung – unter Linux an
gnome-keyring oder ksecretd, die ein angemeldeter Benutzer startet. Auf
einem Debian-Server ohne Desktop gibt es keinen, und genau das ist der
Betriebszustand, den ein Dienst braucht: laufen, ohne dass jemand
angemeldet ist.

Ohne diese Datei läuft der Server zwar, holt aber keine Post.

**Was der Tresor ist.** Eine Datei mit verschlüsselten Passwörtern,
deren Hauptschlüssel woanders liegt – in einer Umgebungsvariablen oder
einer eigenen Datei.

**Wogegen das schützt, und wogegen nicht.** Es gehört ausgesprochen,
sonst wiegt sich jemand in falscher Sicherheit:

*Es schützt* gegen Sicherungskopien des Konfigurationsordners, gegen
versehentlich weitergegebene Ordner und gegen jeden, der an die Datei
kommt, aber nicht an den Schlüssel. Das ist der häufige Fall: Ein
Backup-Band, ein kopiertes Verzeichnis, ein falsch eingestelltes
Cloud-Verzeichnis.

*Es schützt nicht* gegen jemanden, der als der Dienstbenutzer Programme
ausführen kann. Der hat beides – die Datei und den Schlüssel –, denn
der Dienst braucht beides, um sich beim Mailserver anzumelden. Ein
Passwort, mit dem sich ein Programm ohne Zutun anmelden soll, lässt
sich nicht vor diesem Programm verstecken.

**Der Vorrang ist ausdrücklich.** Der Tresor greift nur, wenn ein
Hauptschlüssel eingerichtet ist. Sonst gilt der Schlüsselbund wie
bisher – auf einem Arbeitsplatz soll nichts an ihm vorbei geschrieben
werden, nur weil eine Datei existiert.

**Und ohne ``cryptography`` gibt es keinen Rückfall auf Klartext.**
Lieber eine klare Ansage als eine Datei, von der jemand annimmt, sie
sei geschützt. Das Paket kommt mit ``mailburg[server]``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mailburg.core import paths

#: Die Datei mit den verschlüsselten Werten.
DATEI = "tresor.json"

#: Der Hauptschlüssel als Umgebungsvariable – für systemd
#: (``Environment=`` oder besser ``LoadCredential=``) und für Container.
UMGEBUNG = "MAILBURG_SCHLUESSEL"

#: Oder der Pfad zu einer Datei, die ihn enthält. Der bessere Weg auf
#: einem Server: Eine Umgebungsvariable steht in der Prozessliste
#: mancher Systeme und in Fehlerberichten, eine Datei nicht.
UMGEBUNG_DATEI = "MAILBURG_SCHLUESSELDATEI"


class TresorFehler(RuntimeError):
    """Der Tresor lässt sich nicht öffnen oder nicht beschreiben."""


def _datei() -> Path:
    return paths.config_dir() / DATEI


def schluessel_erzeugen() -> str:
    """Ein neuer Hauptschlüssel, zum Aufbewahren an sicherer Stelle."""
    _fernet_klasse()  # wirft, wenn cryptography fehlt
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode("ascii")


def hauptschluessel() -> str | None:
    """Der eingerichtete Hauptschlüssel – oder nichts.

    Erst die Datei, dann die Umgebungsvariable: Wer beides gesetzt hat,
    meint vermutlich die Datei, denn sie einzurichten ist der Umweg.
    """
    ort = os.environ.get(UMGEBUNG_DATEI, "").strip()
    if ort:
        try:
            inhalt = Path(ort).read_text(encoding="utf-8").strip()
        except OSError as fehler:
            raise TresorFehler(
                f"Die Schlüsseldatei »{ort}« ließ sich nicht lesen: {fehler}"
            ) from fehler
        if inhalt:
            return inhalt

    aus_umgebung = os.environ.get(UMGEBUNG, "").strip()
    return aus_umgebung or None


def verfuegbar() -> bool:
    """Ob ein Tresor eingerichtet ist."""
    try:
        return hauptschluessel() is not None
    except TresorFehler:
        # Ein Schlüsselpfad, der ins Leere zeigt, ist eine Einrichtung -
        # nur eine kaputte. Das soll auffallen, nicht stillschweigend auf
        # den Schlüsselbund zurückfallen.
        return True


def _fernet_klasse():
    try:
        from cryptography.fernet import Fernet
    except ImportError as fehler:
        raise TresorFehler(
            "Für den Tresor fehlt das Paket »cryptography«. "
            "Nachrüsten mit:  pip install 'mailburg[server]'\n\n"
            "Ohne es werden keine Passwörter abgelegt – eine Datei im "
            "Klartext, die aussieht wie ein Tresor, wäre schlimmer als "
            "gar keine."
        ) from fehler
    return Fernet


def _schloss():
    Fernet = _fernet_klasse()
    schluessel = hauptschluessel()
    if not schluessel:
        raise TresorFehler(
            f"Es ist kein Hauptschlüssel eingerichtet. Setzen Sie "
            f"»{UMGEBUNG_DATEI}« auf eine Datei mit dem Schlüssel oder "
            f"»{UMGEBUNG}« auf den Schlüssel selbst."
        )
    try:
        return Fernet(schluessel.encode("ascii"))
    except (ValueError, TypeError) as fehler:
        raise TresorFehler(
            "Der Hauptschlüssel ist unbrauchbar. Er muss der Wert sein, "
            "den »mailburg tresor schluessel« ausgegeben hat."
        ) from fehler


def _inhalt() -> dict[str, str]:
    try:
        daten = json.loads(_datei().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return daten if isinstance(daten, dict) else {}


def _schreiben(daten: dict[str, str]) -> None:
    """Über eine Zwischendatei, mit ``0600``."""
    ziel = _datei()
    neben = ziel.with_suffix(".json.neu")
    neben.write_text(json.dumps(daten, indent=2), encoding="utf-8")
    if os.name != "nt":
        neben.chmod(0o600)
    neben.replace(ziel)


def holen(schluessel: str) -> str | None:
    """Holt einen Wert. Gibt nichts zurück, wenn er fehlt.

    **Ein falscher Hauptschlüssel wirft.** Er darf nicht als »kein
    Passwort hinterlegt« durchgehen: Sonst fragte der Dienst bei jedem
    Abruf nach einem Passwort, das längst da ist, und niemand käme
    darauf, dass nur der Schlüssel nicht stimmt.
    """
    roh = _inhalt().get(schluessel)
    if roh is None:
        return None

    from cryptography.fernet import InvalidToken

    try:
        return _schloss().decrypt(roh.encode("ascii")).decode("utf-8")
    except InvalidToken as fehler:
        raise TresorFehler(
            f"Der Eintrag »{schluessel}« lässt sich mit diesem "
            f"Hauptschlüssel nicht entschlüsseln. Entweder ist es der "
            f"falsche Schlüssel, oder die Datei stammt von einem anderen "
            f"Rechner."
        ) from fehler


def setzen(schluessel: str, wert: str) -> None:
    """Legt einen Wert verschlüsselt ab."""
    daten = _inhalt()
    daten[schluessel] = _schloss().encrypt(wert.encode("utf-8")).decode("ascii")
    _schreiben(daten)


def loeschen(schluessel: str) -> None:
    """Nimmt einen Wert heraus. Nicht vorhanden ist kein Fehler."""
    daten = _inhalt()
    if daten.pop(schluessel, None) is not None:
        _schreiben(daten)


def eintraege() -> list[str]:
    """Welche Schlüssel hinterlegt sind – ohne sie zu entschlüsseln.

    Für die Auskunft »was liegt hier eigentlich«, die auch dann noch
    gehen muss, wenn der Hauptschlüssel nicht stimmt.
    """
    return sorted(_inhalt())
