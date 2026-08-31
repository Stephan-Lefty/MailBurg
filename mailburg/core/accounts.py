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

**Auf einem Server gibt es keinen Schlüsselbund.** Er hängt an einer
Anmeldesitzung, und ein Dienst läuft ohne. Dort tritt der Tresor an
seine Stelle – eine verschlüsselte Datei, deren Hauptschlüssel woanders
liegt; siehe :mod:`mailburg.core.tresor`. Er greift nur, wenn er
ausdrücklich eingerichtet ist, damit auf einem Arbeitsplatz nichts am
Schlüsselbund vorbei geschrieben wird.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from mailburg.core import werkzeuge

from mailburg import APP_ID
from mailburg.core import paths, tresor

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

    archive: list[str] = field(default_factory=list)
    """In welche Archive dieses Postfach gehört – als Archivkennungen.

    **Ohne dieses Feld holt jeder Abruf jedes Postfach.** Wer zwei
    Archive führt – geschäftlich und privat, wie es die
    Aufbewahrungsfristen nahelegen –, bekam bis dahin in beiden
    denselben Bestand. Am 2026-08-26 an einem echten Aufbau aufgefallen:
    Von 9.866 Mails im Geschäftsarchiv gehörten 176 dorthin.

    Die Kennung ist die ``uuid`` aus ``archive.json``, nicht der Pfad.
    Ein Archiv auf einer externen Platte liegt morgen woanders; seine
    Kennung ändert sich nie.

    **Eine leere Liste heißt »noch nicht zugeordnet«, nicht »überall«.**
    Der Abruf übergeht solche Postfächer und sagt es. Das ist die
    unbequemere Voreinstellung und die einzige vertretbare: Post, die
    fälschlich nicht archiviert wurde, holt der nächste Lauf nach; Post,
    die fälschlich in einem Geschäftsarchiv landet, unterliegt dort zehn
    Jahre lang Aufbewahrungsfristen.
    """

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

    oauth_anbieter: str = ""
    """Bei welchem Anbieter angemeldet wird – ``microsoft``, ``google``.

    Leer heißt: Anmeldung mit Passwort, wie bisher. Das bleibt der
    Regelfall; die meisten Server nehmen weiterhin ein Passwort, und
    OAuth2 bringt dort nur Umstand.

    **Nötig ist es bei Microsoft.** Dort ist die Anmeldung mit
    Benutzername und Passwort abgeschaltet – Exchange Online seit dem
    1. Oktober 2022, private Konten seit dem 16. September 2024 –, und
    auch App-Kennwörter wirken nicht mehr.
    """

    oauth_kennung: str = ""
    """Die Kennung der beim Anbieter registrierten Anwendung.

    **MailBurg bringt keine eigene mit.** Google verlangt für den vollen
    IMAP-Zugriff ein jährlich zu wiederholendes Sicherheitsaudit, das für
    ein quelloffenes Programm ohne Einnahmen nicht tragbar ist. Der
    Anwender registriert deshalb seine eigene Anwendung – bei Microsoft
    kostenlos und ohne Prüfverfahren – und trägt ihre Kennung hier ein.

    Sie ist kein Geheimnis: Bei einem öffentlichen Client mit PKCE ist
    sie nur eine Adresse, kein Schlüssel. Deshalb steht sie in der
    Kontenliste und nicht im Schlüsselbund; die Token dagegen schon.
    """

    @property
    def per_oauth2(self) -> bool:
        """Ob dieses Postfach über OAuth2 angemeldet wird."""
        return bool(self.oauth_anbieter)

    @property
    def token_schluessel(self) -> str:
        """Kennung der Token im Schlüsselbund.

        Getrennt vom Passwortschlüssel: Ein Postfach kann im Lauf seines
        Lebens die Anmeldeart wechseln, und dann sollen sich die beiden
        Einträge nicht überschreiben.
        """
        return f"oauth2:{self.benutzer}@{self.server}"

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

    def finden_nach_postfach(self, benutzer: str, server: str) -> Konto | None:
        """Sucht ein Konto anhand des Postfachs statt des Namens.

        Der Name ist frei gewählt – dasselbe Postfach kann einmal »Firma«
        heißen und beim nächsten Mal »kontakt@example.org«. Wer nur nach
        Namen sucht, richtet es zweimal ein, ruft es zweimal ab und wundert
        sich über doppelte Fundorte im Archiv.

        **Der Server taugt nicht als Merkmal.** Derselbe Rechner ist oft
        unter mehreren Namen erreichbar: ``imap.meinefirma.de`` und
        ``s111.hoster.de`` können dasselbe meinen – bei Massenhostern ist
        das sogar der Regelfall, weil das Zertifikat auf den Namen des
        Anbieters lautet.

        Ist der Benutzername eine Mailadresse, meint er das Postfach
        eindeutig; dann genügt er allein. Nur bei Anmeldenamen ohne ``@``
        – etwa ``p1234567`` – braucht es den Server dazu, weil dieselbe
        Kundennummer bei zwei Anbietern vorkommen kann.
        """
        gesucht = benutzer.casefold()
        for konto in self.konten:
            vorhanden = konto.benutzer.casefold()
            if vorhanden != gesucht:
                continue
            if "@" in gesucht or konto.server.casefold() == server.casefold():
                return konto
        return None

    def aktive(self) -> list[Konto]:
        return [k for k in self.konten if k.aktiv]

    def fuer_archiv(self, kennung: str) -> list[Konto]:
        """Die aktiven Postfächer, die in dieses Archiv gehören.

        Nicht zugeordnete Postfächer sind hier *nicht* dabei. Sie
        gesondert zu erfragen ist Absicht: Der Aufrufer soll sie
        erwähnen können, statt sie stillschweigend zu übergehen.
        """
        return [k for k in self.aktive() if kennung in k.archive]

    def ohne_archiv(self) -> list[Konto]:
        """Die aktiven Postfächer, die noch keinem Archiv zugeordnet sind."""
        return [k for k in self.aktive() if not k.archive]

    def zuordnen(self, name: str, kennung: str) -> bool:
        """Weist ein Postfach einem Archiv zu. Mehrfachnennung ist erlaubt."""
        konto = self.finden(name)
        if konto is None:
            return False
        if kennung not in konto.archive:
            konto.archive.append(kennung)
            self.speichern()
        return True

    def loesen(self, name: str, kennung: str) -> bool:
        """Nimmt ein Postfach aus einem Archiv heraus."""
        konto = self.finden(name)
        if konto is None or kennung not in konto.archive:
            return False
        konto.archive.remove(kennung)
        self.speichern()
        return True

    def __len__(self) -> int:
        return len(self.konten)


# ---------------------------------------------------------------- Passwörter


def schluesselbund_lage() -> tuple[bool, str]:
    """Ob Passwörter gespeichert werden können – und sonst warum nicht.

    **Zwei Gründe, ein Ergebnis, aber völlig verschiedene Abhilfen.**
    Entweder fehlt das Paket ``keyring``, dann hilft eine Installation.
    Oder es ist da, findet auf diesem System aber keinen Speicher – dann
    hilft nur eine andere Arbeitsumgebung oder ein Dienst wie
    ``gnome-keyring``.

    Bis zum 2026-08-28 stand in beiden Fällen »Auf diesem Rechner ist
    kein Schlüsselbund erreichbar«. Im ersten Fall ist das schlicht
    falsch: Der Rechner hat einen, MailBurg wurde nur ohne den passenden
    Zusatz installiert. Wer das liest, sucht am falschen Ende – am
    2026-08-27 unter Windows genau so passiert.
    """
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return False, (
            "Zum Speichern von Passwörtern fehlt das Paket »keyring«. "
            "Das liegt nicht am Rechner, sondern an der Installation: "
            "Nachrüsten mit  pip install \"mailburg[imap]\""
        )

    # keyring liefert einen Platzhalter, wenn nichts Passendes gefunden
    # wurde. Der nimmt zwar Passwörter entgegen, verliert sie aber sofort.
    if isinstance(keyring.get_keyring(), fail.Keyring):
        return False, (
            "Auf diesem Rechner ist kein Schlüsselbund erreichbar. Unter "
            "Linux liefert ihn die Arbeitsumgebung mit – auf einem Server "
            "ohne Oberfläche fehlt er. Die Passwörter werden dann bei "
            "jedem Abruf neu erfragt."
        )
    return True, ""


def schluesselbund_verfuegbar() -> bool:
    """Sagt, ob ein brauchbarer Schlüsselbund erreichbar ist."""
    return schluesselbund_lage()[0]


def schluesselbund_name() -> str:
    """Wie der Schlüsselbund auf diesem Rechner heißt.

    »Der Schlüsselbund Ihres Systems« ist eine Auskunft, mit der niemand
    etwas anfangen kann. Wer wissen will, wo sein Passwort gelandet ist,
    braucht den Namen des Programms, in dem er nachsehen kann.
    """
    if not schluesselbund_verfuegbar():
        return ""

    import keyring

    kennung = type(keyring.get_keyring()).__module__.lower()
    if "windows" in kennung:
        return "Anmeldeinformationsverwaltung"
    if "macos" in kennung or "osx" in kennung:
        return "Schlüsselbund"
    if "kwallet" in kennung:
        return "KDE-Brieftasche"
    if "secretservice" in kennung:
        # Dieselbe Schnittstelle bedienen mehrere. Wer sie gerade
        # bereitstellt, verrät der laufende Dienst - und genau danach
        # sucht der Anwender später in seinem Menü.
        return _secretservice_anbieter()
    return "Schlüsselbund"


def _secretservice_anbieter() -> str:
    """Fragt nach, welches Programm org.freedesktop.secrets bedient."""
    import shutil
    import subprocess

    if shutil.which("busctl"):
        try:
            ergebnis = subprocess.run(
                ["busctl", "--user", "list", "--no-legend"],
                capture_output=True, text=True, timeout=5,
                **werkzeuge.konsolenkodierung(),
                **werkzeuge.lautlos(),
            )
            for zeile in ergebnis.stdout.splitlines():
                if zeile.startswith("org.freedesktop.secrets"):
                    dienst = zeile.split()[2] if len(zeile.split()) > 2 else ""
                    if "ksecret" in dienst or "kwallet" in dienst:
                        return "KDE-Brieftasche"
                    if "gnome" in dienst:
                        return "GNOME-Schlüsselbund"
        except (OSError, subprocess.TimeoutExpired, IndexError):
            pass
    return "Schlüsselbund"


def passwort_holen(konto: Konto) -> str | None:
    """Holt das Passwort – aus dem Tresor oder dem Schlüsselbund."""
    if tresor.verfuegbar():
        return tresor.holen(konto.schluessel)

    if not schluesselbund_verfuegbar():
        return None
    import keyring

    try:
        return keyring.get_password(APP_ID, konto.schluessel)
    except Exception:  # noqa: BLE001 – ein gesperrter Schlüsselbund wirft
        return None


def token_holen(konto: Konto):
    """Holt die OAuth2-Token aus dem Schlüsselbund.

    Gibt ``None`` zurück, wenn keine hinterlegt sind oder der
    Schlüsselbund nicht zu erreichen ist – der Aufrufer muss dann zur
    Anmeldung auffordern.
    """
    from mailburg.core.oauth2 import Token

    if tresor.verfuegbar():
        roh = tresor.holen(konto.token_schluessel)
        return Token.aus_json(roh) if roh else None

    if not schluesselbund_verfuegbar():
        return None
    import keyring

    try:
        roh = keyring.get_password(APP_ID, konto.token_schluessel)
    except Exception:  # noqa: BLE001 – ein gesperrter Schlüsselbund wirft
        return None
    return Token.aus_json(roh) if roh else None


def token_setzen(konto: Konto, token) -> bool:
    """Legt die OAuth2-Token im Schlüsselbund ab.

    **Nie unverschlüsselt in eine Datei.** Ein Erneuerungs-Token ist auf
    Monate hinaus ein Vollzugang zum Postfach – es ist mehr wert als das
    Passwort, weil es die Zwei-Faktor-Anmeldung bereits hinter sich hat.
    Auf einem Server ohne Schlüsselbund kommt es deshalb in den Tresor,
    nicht daneben.
    """
    if tresor.verfuegbar():
        tresor.setzen(konto.token_schluessel, token.als_json())
        return True

    if not schluesselbund_verfuegbar():
        return False
    import keyring

    try:
        keyring.set_password(APP_ID, konto.token_schluessel, token.als_json())
        return True
    except Exception:  # noqa: BLE001
        return False


def token_loeschen(konto: Konto) -> None:
    """Nimmt die Token zurück – beim Abmelden oder Entfernen des Kontos."""
    if tresor.verfuegbar():
        tresor.loeschen(konto.token_schluessel)
        return

    if not schluesselbund_verfuegbar():
        return
    import keyring

    try:
        keyring.delete_password(APP_ID, konto.token_schluessel)
    except Exception:  # noqa: BLE001 – nicht vorhanden ist kein Fehler
        pass


def passwort_setzen(konto: Konto, passwort: str) -> bool:
    """Legt das Passwort ab. Gibt zurück, ob es geklappt hat."""
    if tresor.verfuegbar():
        tresor.setzen(konto.schluessel, passwort)
        return True

    if not schluesselbund_verfuegbar():
        return False
    import keyring

    try:
        keyring.set_password(APP_ID, konto.schluessel, passwort)
        return True
    except Exception:  # noqa: BLE001
        return False


def passwort_loeschen(konto: Konto) -> None:
    """Entfernt das Passwort."""
    if tresor.verfuegbar():
        tresor.loeschen(konto.schluessel)
        return

    if not schluesselbund_verfuegbar():
        return
    import keyring

    try:
        keyring.delete_password(APP_ID, konto.schluessel)
    except Exception:  # noqa: BLE001 – war vielleicht nie da
        pass
