"""Die Schlüssel eines verschlüsselten Archivs.

Dieses Modul kennt nur Schlüssel und Bytes. Was damit verschlüsselt wird
– Mails, Journalzeilen –, entscheiden :mod:`~mailburg.core.store` und
:mod:`~mailburg.core.journal`.

**Zwei Ebenen, und das ist der Kern des Entwurfs.** Die Daten hängen an
einem zufälligen *Archivschlüssel*, der nie das Archiv verlässt. Dieser
Archivschlüssel liegt in ``archive.json``, eingewickelt in andere
Schlüssel – einen aus dem Passwort und einen aus dem Notschlüssel.

Der Umweg ist kein Selbstzweck. Hinge die Verschlüsselung direkt am
Passwort, müsste ein Passwortwechsel jede einzelne Datei neu
verschlüsseln: bei 700.000 Mails Stunden, mitten darin ein Archiv, das
halb dem alten und halb dem neuen Passwort gehört. So wird beim Wechsel
nur eine Hülle neu geschrieben, ein paar hundert Byte.

**Zwei Wege hinein.** Neben dem Passwort gibt es den Notschlüssel: 32
zufällige Byte, beim Anlegen einmal ausgegeben, zum Ausdrucken. Ein
Langzeitarchiv überlebt das Gedächtnis seines Besitzers – wer nach
sieben Jahren eine Rechnung braucht, hat das Passwort von damals
womöglich nicht mehr. Ohne einen zweiten Weg wäre das Archiv dann
endgültig verloren, und zwar restlos: Es gibt keine Hintertür, keinen
Hersteller, der helfen könnte.

**Warum scrypt und nicht Argon2id.** Der ursprüngliche Entwurf sah
Argon2id vor. Dagegen spricht nur eines, das aber schwer: ``scrypt``
steckt in ``hashlib``, Argon2id nicht. Ein Archivprogramm, das seine
Daten in zwanzig Jahren noch aufbekommen soll, sollte für die
Schlüsselableitung nichts brauchen, was man erst installieren muss.
Beide sind speicherhart, beide sind für diesen Zweck geeignet.

**Was hier bewusst nicht geschützt wird.** Der Suchindex. Er liegt
außerhalb des Archivs, enthält Betreff, Absender und Volltext im
Klartext und ist damit die offene Flanke – das gehört ausgesprochen,
und es steht in :func:`hinweis_suchindex`.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from base64 import b64decode, b64encode
from dataclasses import dataclass
from typing import Any

#: Wie der Schlüssel aus dem Passwort entsteht. ``n`` bestimmt Aufwand
#: und Speicherbedarf: 2^17 mit r=8 sind rund 134 MB und einige Zehntel
#: Sekunden – einmal beim Öffnen, nicht je Mail. Wer das erhöht, sperrt
#: bestehende Archive aus; die Werte stehen deshalb in ``archive.json``
#: und werden von dort gelesen, nicht von hier.
SCRYPT_N = 2 ** 17
SCRYPT_R = 8
SCRYPT_P = 1

#: OpenSSL bricht sonst mit »memory limit exceeded« ab: Der Vorgabewert
#: liegt bei 32 MB, und schon 2^16 überschreitet ihn. Ohne diese Zeile
#: scheitert die Ableitung auf jedem System, statt langsam zu sein.
SCRYPT_MAXMEM = 512 * 1024 * 1024

#: Länge aller Schlüssel in Byte. 32 = AES-256.
SCHLUESSELLAENGE = 32

#: Länge des Zufallswerts vor jedem Chiffrat. 12 Byte sind für AES-GCM
#: die vorgesehene Länge; andere Längen sind zulässig, aber langsamer und
#: ohne Vorteil.
NONCE_LAENGE = 12

#: Das Salz für die Passwortableitung, je Archiv einmal gewürfelt.
SALZ_LAENGE = 16


class KryptoFehler(RuntimeError):
    """Ein Schlüssel passt nicht, oder es fehlt etwas zum Entschlüsseln."""


class FalschesPasswort(KryptoFehler):
    """Passwort oder Notschlüssel öffnen dieses Archiv nicht.

    Eigene Klasse, weil der Aufrufer darauf anders reagieren muss als auf
    »Datei beschädigt«: noch einmal fragen statt eine Warnung ausgeben.
    """


def _aesgcm():
    """Die AES-GCM-Klasse – erst hier importiert, mit klarer Ansage.

    Der Kern von MailBurg kommt ohne Fremdpakete aus, und das soll er
    auch bleiben: Ein unverschlüsseltes Archiv braucht nichts davon.
    Wer verschlüsselt, braucht ``cryptography``.
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as fehler:
        raise KryptoFehler(
            "Für ein verschlüsseltes Archiv fehlt das Paket "
            "»cryptography«. Nachrüsten mit:\n"
            "    pip install 'mailburg[verschluesselung]'\n\n"
            "Ihre Mails sind davon nicht betroffen – sie liegen "
            "unversehrt im Archiv und warten auf das Paket."
        ) from fehler
    return AESGCM


# --------------------------------------------------------------- Ableiten


def aus_passwort(passwort: str, salz: bytes, *, n: int = SCRYPT_N,
                 r: int = SCRYPT_R, p: int = SCRYPT_P) -> bytes:
    """Macht aus einem Passwort einen Schlüssel.

    Die Kennwerte kommen von außen, nicht aus den Konstanten dieses
    Moduls: Ein Archiv von 2026 muss sich 2046 noch öffnen lassen, auch
    wenn der Aufwand bis dahin dreimal erhöht wurde.
    """
    if not passwort:
        raise KryptoFehler("Ein leeres Passwort verschlüsselt nichts.")
    return hashlib.scrypt(
        passwort.encode("utf-8"),
        salt=salz,
        n=n,
        r=r,
        p=p,
        dklen=SCHLUESSELLAENGE,
        maxmem=SCRYPT_MAXMEM,
    )


def _ableiten(archivschluessel: bytes, zweck: bytes) -> bytes:
    """Ein Unterschlüssel je Aufgabe – HKDF-Expand über HMAC-SHA256.

    **Ein Schlüssel, eine Aufgabe.** Denselben Schlüssel zum
    Verschlüsseln der Inhalte und zum Berechnen der Dateinamen zu
    nehmen, wäre bequem und schlechte Praxis: Sobald eine der beiden
    Verwendungen etwas über den Schlüssel verrät, ist auch die andere
    betroffen.
    """
    return hmac.new(archivschluessel, zweck, hashlib.sha256).digest()


# ------------------------------------------------------------ Ein Archiv


@dataclass(frozen=True)
class Schluessel:
    """Die entpackten Schlüssel eines geöffneten Archivs.

    Lebt nur im Arbeitsspeicher. Was auf die Platte kommt, ist die
    :class:`Huelle`.
    """

    archiv: bytes
    """Der Schlüssel, an dem alles hängt."""

    @property
    def inhalt(self) -> bytes:
        """Womit Mails und Journalzeilen verschlüsselt werden."""
        return _ableiten(self.archiv, b"mailburg/inhalt/v1")

    @property
    def namen(self) -> bytes:
        """Womit aus dem Hash einer Mail ihr Dateiname wird."""
        return _ableiten(self.archiv, b"mailburg/namen/v1")

    def dateiname(self, digest: str) -> str:
        """Der verdeckte Name einer Mail in der Ablage.

        **Warum der Klartext-Hash nicht taugt.** Er ist der SHA-256 der
        Mail, und den kann jeder ausrechnen, der die Mail hat. Wer
        wissen will, ob eine bestimmte Nachricht im Archiv liegt –
        etwa ein Rundschreiben, das er selbst bekommen hat –, müsste
        sonst nur im Verzeichnis nachsehen. Der Inhalt wäre
        verschlüsselt und die Frage trotzdem beantwortet.

        Das Ergebnis ist wieder 64 Hexzeichen, damit die Ablage
        dieselbe Form behält.
        """
        return hmac.new(
            self.namen, digest.encode("ascii"), hashlib.sha256
        ).hexdigest()

    # ---------------------------------------------------- Ver- und Entpacken

    def verschluesseln(self, klartext: bytes, *, bindung: bytes = b"") -> bytes:
        """Verschlüsselt einen Happen. Der Zufallswert steht vorn.

        ``bindung`` wandert in die Prüfsumme, ohne selbst verschlüsselt
        zu werden. Die Ablage bindet damit jede Mail an ihren Hash: Zwei
        Dateien zu vertauschen fällt dann beim Entschlüsseln auf und
        nicht erst später beim Lesen.
        """
        AESGCM = _aesgcm()
        nonce = os.urandom(NONCE_LAENGE)
        chiffrat = AESGCM(self.inhalt).encrypt(nonce, klartext, bindung or None)
        return nonce + chiffrat

    def entschluesseln(self, paket: bytes, *, bindung: bytes = b"") -> bytes:
        """Die Gegenrichtung. Wirft, wenn etwas nicht stimmt."""
        AESGCM = _aesgcm()
        if len(paket) <= NONCE_LAENGE:
            raise KryptoFehler("Der Happen ist zu kurz, um verschlüsselt zu sein.")
        nonce, chiffrat = paket[:NONCE_LAENGE], paket[NONCE_LAENGE:]
        try:
            return AESGCM(self.inhalt).decrypt(nonce, chiffrat, bindung or None)
        except Exception as fehler:  # InvalidTag und Verwandte
            raise KryptoFehler(
                "Der Inhalt ließ sich nicht entschlüsseln. Entweder gehört "
                "er zu einem anderen Archiv, oder er wurde verändert."
            ) from fehler


# ------------------------------------------------------------- Die Hülle


@dataclass(frozen=True)
class Huelle:
    """Was in ``archive.json`` steht: der Archivschlüssel, eingewickelt.

    Enthält keinen Schlüssel im Klartext – nur Chiffrate und die
    Kennwerte, mit denen sich aus einem Passwort wieder einer machen
    lässt.
    """

    salz: bytes
    n: int
    r: int
    p: int
    huellen: dict[str, bytes]
    """Je Weg hinein eine Hülle: ``passwort``, ``notschluessel``."""

    verfahren: str = "aes-256-gcm"
    ableitung: str = "scrypt"

    # ------------------------------------------------------------ Anlegen

    @classmethod
    def anlegen(cls, passwort: str) -> tuple[Huelle, Schluessel, str]:
        """Legt einen neuen Archivschlüssel an und wickelt ihn zweimal ein.

        Gibt die Hülle, die entpackten Schlüssel und den Notschlüssel
        zurück – Letzteren genau dieses eine Mal. Danach steht er
        nirgends mehr, auch nicht im Archiv.
        """
        _aesgcm()  # lieber jetzt scheitern als nach dem halben Anlegen
        archivschluessel = os.urandom(SCHLUESSELLAENGE)
        salz = os.urandom(SALZ_LAENGE)
        notschluessel = notschluessel_erzeugen()

        huelle = cls(salz=salz, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, huellen={})
        # **Die Kennwerte aus der Hülle, nicht aus dem Modul.** Sonst
        # entsteht der Schlüssel mit den Vorgabewerten von ``aus_passwort``
        # - die stehen als Vorgabeargumente fest, seit das Modul geladen
        # wurde - während in die Datei die aktuellen geschrieben werden.
        # Beim nächsten Öffnen leitet MailBurg dann nach den notierten
        # Werten ab und bekommt einen anderen Schlüssel: ein Archiv, das
        # sich mit dem richtigen Passwort nicht mehr öffnen lässt.
        huelle.huellen["passwort"] = _einwickeln(
            aus_passwort(passwort, salz, n=huelle.n, r=huelle.r, p=huelle.p),
            archivschluessel,
        )
        huelle.huellen["notschluessel"] = _einwickeln(
            _aus_notschluessel(notschluessel), archivschluessel
        )
        return huelle, Schluessel(archiv=archivschluessel), notschluessel

    # ------------------------------------------------------------- Öffnen

    def oeffnen(self, geheimnis: str) -> Schluessel:
        """Probiert Passwort *und* Notschlüssel – der Anwender weiß es besser.

        **Warum nicht getrennt fragen.** Wer einen Notschlüssel
        eintippt, hat gerade sein Passwort vergessen; ihn dann erst
        noch das richtige Feld suchen zu lassen, ist Schikane. Die
        beiden Formen sind nicht zu verwechseln, und ein Fehlversuch
        kostet nichts als Rechenzeit.
        """
        versuche: list[tuple[str, bytes]] = []
        if "passwort" in self.huellen:
            versuche.append(("passwort", aus_passwort(
                geheimnis, self.salz, n=self.n, r=self.r, p=self.p
            )))
        if notschluessel_lesen(geheimnis) and "notschluessel" in self.huellen:
            versuche.append(("notschluessel", _aus_notschluessel(geheimnis)))

        for name, schluessel in versuche:
            entpackt = _auswickeln(schluessel, self.huellen[name])
            if entpackt is not None:
                return Schluessel(archiv=entpackt)

        raise FalschesPasswort(
            "Das Passwort öffnet dieses Archiv nicht.\n\n"
            "Falls Sie es nicht mehr wissen: Beim Anlegen wurde ein "
            "Notschlüssel ausgegeben – 64 Zeichen in acht Gruppen. Er "
            "steht hier ebenso zur Verfügung wie das Passwort.\n\n"
            "Ohne eines von beidem kommt niemand an dieses Archiv, auch "
            "der Hersteller nicht."
        )

    def passwort_wechseln(self, schluessel: Schluessel, neues: str) -> Huelle:
        """Schreibt nur die Hülle neu, nicht das Archiv.

        Der Notschlüssel bleibt dabei gültig. Er hängt an einer eigenen
        Hülle und weiß vom Passwort nichts.
        """
        salz = os.urandom(SALZ_LAENGE)
        huellen = dict(self.huellen)
        huellen["passwort"] = _einwickeln(
            aus_passwort(neues, salz, n=self.n, r=self.r, p=self.p),
            schluessel.archiv,
        )
        # Das Salz gehört zum Passwort, also wird es mit ihm getauscht.
        # Der Notschlüssel braucht keines - er ist selbst schon Zufall.
        return Huelle(
            salz=salz, n=self.n, r=self.r, p=self.p, huellen=huellen,
            verfahren=self.verfahren, ableitung=self.ableitung,
        )

    # -------------------------------------------------------- Auf die Platte

    def als_json(self) -> dict[str, Any]:
        return {
            "verfahren": self.verfahren,
            "ableitung": {
                "art": self.ableitung,
                "n": self.n,
                "r": self.r,
                "p": self.p,
                "salz": b64encode(self.salz).decode("ascii"),
            },
            "huellen": {
                name: b64encode(wert).decode("ascii")
                for name, wert in sorted(self.huellen.items())
            },
        }

    @classmethod
    def aus_json(cls, daten: dict[str, Any]) -> Huelle:
        try:
            ableitung = daten["ableitung"]
            return cls(
                salz=b64decode(ableitung["salz"]),
                n=int(ableitung["n"]),
                r=int(ableitung["r"]),
                p=int(ableitung["p"]),
                huellen={
                    name: b64decode(wert)
                    for name, wert in daten["huellen"].items()
                },
                verfahren=daten.get("verfahren", "aes-256-gcm"),
                ableitung=ableitung.get("art", "scrypt"),
            )
        except (KeyError, TypeError, ValueError) as fehler:
            raise KryptoFehler(
                "Die Schlüsselangaben in archive.json sind unbrauchbar. "
                "Ohne sie lässt sich das Archiv nicht öffnen – holen Sie "
                "die Datei aus einer Sicherung zurück."
            ) from fehler


def _einwickeln(schluessel: bytes, geheim: bytes) -> bytes:
    AESGCM = _aesgcm()
    nonce = os.urandom(NONCE_LAENGE)
    return nonce + AESGCM(schluessel).encrypt(nonce, geheim, b"mailburg/huelle/v1")


def _auswickeln(schluessel: bytes, paket: bytes) -> bytes | None:
    """Gibt den Archivschlüssel zurück – oder nichts, wenn es nicht passt."""
    AESGCM = _aesgcm()
    if len(paket) <= NONCE_LAENGE:
        return None
    try:
        return AESGCM(schluessel).decrypt(
            paket[:NONCE_LAENGE], paket[NONCE_LAENGE:], b"mailburg/huelle/v1"
        )
    except Exception:  # noqa: BLE001 – ein falscher Schlüssel ist kein Fehler
        return None


# ------------------------------------------------------- Der Notschlüssel

#: Ohne ``I``, ``O``, ``0`` und ``1``. Der Notschlüssel wird ausgedruckt
#: und abgetippt, oft Jahre später und womöglich von jemand anderem;
#: die vier sind auf Papier nicht sicher zu unterscheiden.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

#: Acht Gruppen zu vier Zeichen – 32 Zeichen à 5 Bit sind 160 Bit.
GRUPPEN = 8
GRUPPENLAENGE = 4


def notschluessel_erzeugen() -> str:
    """Ein neuer Notschlüssel, in Gruppen zum Abschreiben.

    ``VXTM-9K4P-…`` – 160 Bit Zufall. Das ist weniger als die 256 Bit
    des Archivschlüssels und trotzdem weit jenseits dessen, was sich
    durchprobieren lässt.
    """
    zeichen = [
        secrets.choice(ALPHABET) for _ in range(GRUPPEN * GRUPPENLAENGE)
    ]
    return "-".join(
        "".join(zeichen[i:i + GRUPPENLAENGE])
        for i in range(0, len(zeichen), GRUPPENLAENGE)
    )


def notschluessel_lesen(eingabe: str) -> str | None:
    """Räumt eine Eingabe auf und sagt, ob sie ein Notschlüssel sein kann.

    Bindestriche, Leerzeichen und Kleinschreibung sind egal – wer 32
    Zeichen von einem Zettel abtippt, soll nicht an der Form scheitern.
    """
    gesaeubert = "".join(
        zeichen for zeichen in eingabe.upper()
        if zeichen not in "- \t\n\r"
    )
    if len(gesaeubert) != GRUPPEN * GRUPPENLAENGE:
        return None
    if any(zeichen not in ALPHABET for zeichen in gesaeubert):
        return None
    return gesaeubert


def _aus_notschluessel(eingabe: str) -> bytes:
    gesaeubert = notschluessel_lesen(eingabe)
    if gesaeubert is None:
        raise KryptoFehler("Das ist kein Notschlüssel.")
    # Kein scrypt: Der Wert ist bereits gleichverteilter Zufall, da
    # bringt eine teure Ableitung nichts. Gehasht wird er trotzden, um
    # aus 32 Zeichen 32 Byte zu machen.
    return hashlib.sha256(
        b"mailburg/notschluessel/v1" + gesaeubert.encode("ascii")
    ).digest()


# ------------------------------------------------------------- Ehrlichkeit


def hinweis_suchindex() -> str:
    """Was die Verschlüsselung *nicht* abdeckt – wörtlich, überall gleich.

    Steht als Funktion hier und nicht dreimal getippt in Assistent,
    Kommandozeile und Anleitung. Ein Sicherheitshinweis, der an drei
    Stellen leicht verschieden lautet, wird an mindestens zwei davon
    irgendwann falsch.
    """
    return (
        "Verschlüsselt werden die Mails und das Journal – also alles, "
        "was im Archivordner liegt und was in eine Sicherung wandert.\n\n"
        "Der Suchindex gehört nicht dazu. Er liegt außerhalb des "
        "Archivs im Benutzerverzeichnis, nur für Sie lesbar, und "
        "enthält Betreff, Absender und Text im Klartext – anders "
        "könnte er nicht suchen.\n\n"
        "Für den häufigen Fall genügt das: Eine Sicherung in der "
        "Cloud, eine verlorene externe Platte oder ein weitergegebener "
        "Ordner enthalten den Index nicht. Wer dagegen den ganzen "
        "Rechner absichern will, verschlüsselt die Platte – dafür "
        "bringt jedes Betriebssystem etwas mit."
    )
