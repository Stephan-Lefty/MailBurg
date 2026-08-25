"""Kontenverwaltung.

Die Zugangsdaten für bis zu dreißig Postfächer wollen irgendwo hin. Wohin
sie **nicht** gehören, ist eine Konfigurationsdatei: Wer die kopiert – oder
versehentlich in eine Sicherung packt –, hat alle Postfächer.

Deshalb liegen die Passwörter im Schlüsselbund des Betriebssystems: GNOME
Keyring beziehungsweise KWallet unter Linux, Anmeldeinformationsverwaltung
unter Windows, Schlüsselbund unter macOS. Dort sind sie an das
Benutzerkonto gebunden und im Ruhezustand verschlüsselt.

Das dafür nötige Paket ``keyring`` ist die einzige Ausnahme von der Regel,
möglichst ohne Fremdbibliotheken auszukommen – Passwortverwaltung selbst zu
schreiben wäre die schlechtere Wahl. Fehlt es, läuft das Programm trotzdem,
fragt das Passwort dann aber bei jedem Abruf neu ab.

In der Konfigurationsdatei steht nur, **wo** ein Postfach liegt und **wie**
es heißt, nie, womit man hineinkommt.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from mailburg import APP_ID
from mailburg.core import paths

#: Ordner, die standardmäßig nicht archiviert werden. Papierkorb und
#: Spamverdacht sind schon vom Benutzer aussortiert worden - sie ins Archiv
#: zu holen, würde diese Entscheidung rückgängig machen und das Archiv
#: unnötig aufblähen.
#: Adressen, die diesen Rechner selbst meinen. Nur bei ihnen darf die
#: Zertifikatsprüfung entfallen – siehe ``Konto.bruecke``.
LOKALE_ADRESSEN = frozenset({"127.0.0.1", "::1", "localhost"})

#: Brückenprogramme und ihre üblichen Ports. Dient nur dazu, ein
#: übernommenes Konto von selbst richtig einzustufen.
BRUECKEN_PORTS = frozenset({1143, 1025, 1100})

STANDARD_AUSSCHLUSS = (
    "Trash", "Papierkorb", "Deleted Items", "Gelöschte Elemente", "Deleted Messages",
    "Junk", "Spam", "Junk E-Mail", "Bulk Mail", "Werbung",
    "Drafts", "Entwürfe",
)


@dataclass
class Konto:
    """Ein Postfach, aus dem archiviert wird."""

    name: str
    """Kurzname. Unter ihm erscheinen die Mails im Archiv."""

    server: str
    benutzer: str
    port: int = 993
    ssl: bool = True
    """Verschlüsselte Verbindung von Anfang an (IMAPS). Sonst STARTTLS."""

    ausschluss: list[str] = field(default_factory=lambda: list(STANDARD_AUSSCHLUSS))
    """Ordner, die übergangen werden."""

    aktiv: bool = True

    bruecke: bool = False
    """Dahinter läuft ein Brückenprogramm auf diesem Rechner.

    Proton Mail und Tuta verschlüsseln Ende zu Ende und bieten deshalb kein
    IMAP im Netz an. Wer trotzdem mit einem Mailprogramm daran will, lässt
    ein Brückenprogramm laufen, das auf ``127.0.0.1`` ein IMAP-Postfach
    bereitstellt und die Entschlüsselung übernimmt.

    Solche Brücken weisen sich mit einem selbstsignierten Zertifikat aus –
    für ``127.0.0.1`` kann es gar kein anderes geben, denn keine
    Zertifizierungsstelle beglaubigt den eigenen Rechner. Ist dieses Feld
    gesetzt, sieht MailBurg deshalb von der Prüfung ab. Das ist vertretbar,
    **weil die Verbindung den Rechner nicht verlässt**: Wer sie belauschen
    wollte, säße bereits darauf, und dann wäre ohnehin alles verloren.

    Damit daraus kein Scheunentor wird, wirkt das Feld ausschließlich bei
    den Adressen in :data:`LOKALE_ADRESSEN`. Bei jedem anderen Server bleibt
    es folgenlos.
    """

    @property
    def ist_lokale_bruecke(self) -> bool:
        """Ob die Nachsicht beim Zertifikat wirklich greifen darf."""
        return self.bruecke and self.server.lower() in LOKALE_ADRESSEN

    @property
    def schluessel(self) -> str:
        """Kennung im Schlüsselbund – Server und Benutzer zusammen."""
        return f"{self.benutzer}@{self.server}"

    def beschreibung(self) -> str:
        return f"{self.name} ({self.benutzer} auf {self.server}:{self.port})"


class Kontenliste:
    """Alle eingerichteten Postfächer."""

    def __init__(self, datei: Path | None = None) -> None:
        self.datei = datei or (paths.config_dir() / "konten.json")
        self.konten: list[Konto] = []
        if self.datei.exists():
            self.laden()

    def laden(self) -> None:
        try:
            daten = json.loads(self.datei.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.konten = []
            return
        self.konten = [Konto(**eintrag) for eintrag in daten.get("konten", [])]

    def speichern(self) -> None:
        self.datei.parent.mkdir(parents=True, exist_ok=True)
        inhalt = {"konten": [asdict(k) for k in self.konten]}
        # Erst daneben schreiben, dann umbenennen - sonst steht bei einem
        # Absturz eine halbe Kontenliste auf der Platte.
        vorlaeufig = self.datei.with_suffix(".neu")
        vorlaeufig.write_text(
            json.dumps(inhalt, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        vorlaeufig.replace(self.datei)
        # Nur der Benutzer selbst soll die Datei lesen können. Passwörter
        # stehen zwar nicht darin, aber die Liste der eigenen Postfächer
        # geht ebenfalls niemanden etwas an.
        try:
            self.datei.chmod(0o600)
        except OSError:
            pass

    def hinzufuegen(self, konto: Konto) -> None:
        if self.finden(konto.name):
            raise ValueError(f"Ein Konto namens '{konto.name}' gibt es schon.")
        self.konten.append(konto)
        self.speichern()

    def entfernen(self, name: str) -> bool:
        vorher = len(self.konten)
        self.konten = [k for k in self.konten if k.name != name]
        if len(self.konten) != vorher:
            self.speichern()
            return True
        return False

    def finden(self, name: str) -> Konto | None:
        return next((k for k in self.konten if k.name == name), None)

    def aktive(self) -> list[Konto]:
        return [k for k in self.konten if k.aktiv]

    def __len__(self) -> int:
        return len(self.konten)


# ---------------------------------------------------------------- Passwörter


def schluesselbund_verfuegbar() -> bool:
    """Sagt, ob ein brauchbarer Schlüsselbund erreichbar ist."""
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return False
    # keyring liefert einen Platzhalter, wenn nichts Passendes gefunden
    # wurde. Der nimmt zwar Passwörter entgegen, verliert sie aber sofort.
    return not isinstance(keyring.get_keyring(), fail.Keyring)


def passwort_holen(konto: Konto) -> str | None:
    """Holt das Passwort aus dem Schlüsselbund."""
    if not schluesselbund_verfuegbar():
        return None
    import keyring

    try:
        return keyring.get_password(APP_ID, konto.schluessel)
    except Exception:  # noqa: BLE001 – ein gesperrter Schlüsselbund wirft
        return None


def passwort_setzen(konto: Konto, passwort: str) -> bool:
    """Legt das Passwort im Schlüsselbund ab. Gibt zurück, ob es geklappt hat."""
    if not schluesselbund_verfuegbar():
        return False
    import keyring

    try:
        keyring.set_password(APP_ID, konto.schluessel, passwort)
        return True
    except Exception:  # noqa: BLE001
        return False


def passwort_loeschen(konto: Konto) -> None:
    """Entfernt das Passwort aus dem Schlüsselbund."""
    if not schluesselbund_verfuegbar():
        return
    import keyring

    try:
        keyring.delete_password(APP_ID, konto.schluessel)
    except Exception:  # noqa: BLE001 – war vielleicht nie da
        pass
