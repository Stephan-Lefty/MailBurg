"""Mails direkt aus dem Postfach holen.

Der Weg über IMAP ist der, den ein laufendes Archiv braucht: Er kommt an
das heran, was gerade angekommen ist, und er kommt an Postfächer heran, die
auf diesem Rechner nie eingerichtet waren.

**Es wird nur gelesen.** Der Ordner wird mit ``EXAMINE`` geöffnet, nicht mit
``SELECT``, und der Inhalt mit ``BODY.PEEK[]`` geholt, nicht mit ``BODY[]``.
Beides bewirkt dasselbe: Das Postfach sieht hinterher aus wie vorher. Ein
Archivprogramm, das ungelesene Post als gelesen markiert, macht sich
unbrauchbar – der Anwender merkt es erst, wenn er etwas übersehen hat.

**Ordnernamen sind nicht einfach Text.** IMAP überträgt sie in einem
abgewandelten UTF-7 (RFC 3501, Abschnitt 5.1.3): Aus »Entwürfe« wird
``Entw&APw-rfe``. Angezeigt und archiviert wird der lesbare Name, angefordert
wird beim Server der rohe – ein Hin- und Herrechnen könnte scheitern, und
dann fände der Server den Ordner nicht mehr.

**Was übergangen wird.** Papierkorb, Spamverdacht und Entwürfe stehen in der
Ausschlussliste des Kontos. Zusätzlich werden die Sonderordner nach RFC 6154
ausgewertet, denn die sind verlässlicher als Namen in wechselnden Sprachen.
Der wichtigste Fall ist Gmail: »Alle Nachrichten« (``\\All``) enthält
sämtliche Mails ein zweites Mal. Wer den Ordner mitnimmt, archiviert alles
doppelt – nicht als doppelte Datei, aber als doppelten Fundort im Journal.
"""

from __future__ import annotations

import imaplib
import re
import socket
import ssl
from base64 import b64decode
from collections.abc import Callable, Iterator

from mailburg.core.accounts import Konto
from mailburg.core.sync import Abrufzustand
from mailburg.sources.base import RawMessage, Source

#: So lange wird auf den Server gewartet, bevor der Abruf aufgibt. Ohne
#: Grenze bleibt ein Lauf an einem stummen Server bis in alle Ewigkeit
#: hängen – gern über Nacht in einer Zeitsteuerung.
ZEITGRENZE = 60

#: Beim Prüfen in der Oberfläche wartet dagegen ein Mensch. Eine Minute
#: vor einem Fenster, das sich nicht rührt, hält niemand aus – dann wird
#: lieber abgebrochen und noch einmal versucht.
ZEITGRENZE_PRUEFEN = 15

#: Höchstens so viele Mails auf einmal anfordern. Jeder Umlauf kostet, aber
#: eine zu große Anforderung landet vollständig im Arbeitsspeicher.
BLOCK_MAILS = 50

#: … und höchstens so viele Bytes je Block. Fünfzig Mails mit je dreißig
#: Megabyte Anhang wären anderthalb Gigabyte auf einmal.
BLOCK_BYTES = 32 * 1024 * 1024

#: IMAP begrenzt die Zeile. Eine Anforderung mit Tausenden einzelner UIDs
#: läuft bei manchen Servern in einen Fehler, deshalb werden sie in
#: Häppchen dieser Größe gestellt.
BLOCK_SUCHE = 500

#: Sonderordner nach RFC 6154, die nicht ins Archiv gehören. ``\All`` ist
#: der Gmail-Fall: Dieser Ordner enthält alles noch einmal.
SONDERORDNER_AUS = {"\\all", "\\trash", "\\junk", "\\drafts"}

_UID = re.compile(rb"UID\s+(\d+)")
_FLAGS = re.compile(rb"FLAGS\s+\(([^)]*)\)")
_SIZE = re.compile(rb"RFC822\.SIZE\s+(\d+)")
_LIST = re.compile(rb'\((?P<attrs>[^)]*)\)\s+(?P<sep>"[^"]*"|NIL)\s+(?P<name>.*)')


#: Was das Betriebssystem meldet – und was es für den Anwender bedeutet.
#:
#: Am 2026-08-28 in der Windows-Fassung aufgefallen: Beim Einrichten
#: stand dort »[Errno 11001] getaddrinfo failed«. Das ist die häufigste
#: Meldung überhaupt, weil sie bei jedem Tippfehler im Servernamen
#: erscheint – und sie sagt niemandem etwas.
#:
#: MailBurg vermeidet sonst überall Fachjargon. Ausgerechnet an der
#: Stelle, an der jemand nicht weiterkommt, stand eine Fehlernummer.
_UEBERSETZUNG = (
    # Der Name lässt sich nicht auflösen. Unter Windows Errno 11001,
    # unter Linux -2 oder -3, je nach Auflöser.
    (("getaddrinfo failed", "name or service not known",
      "nodename nor servname", "temporary failure in name resolution"),
     "Diesen Servernamen gibt es nicht. Meist ist es ein Tippfehler – "
     "IMAP schreibt sich mit vier Buchstaben."),

    # Der Rechner antwortet, aber auf diesem Anschluss lauscht nichts.
    (("connection refused", "actively refused"),
     "Der Rechner ist erreichbar, aber auf diesem Anschluss antwortet "
     "kein Mailserver. Stimmt die Portnummer?"),

    (("timed out", "timeout"),
     "Der Server antwortet nicht. Das kann an einer Firewall liegen, an "
     "einer falschen Portnummer – oder der Server ist gerade nicht da."),

    (("authenticationfailed", "invalid credentials", "login failed",
      "authentication failed"),
     "Benutzername oder Passwort stimmt nicht."),

    (("no route to host", "network is unreachable"),
     "Der Rechner ist nicht erreichbar. Besteht die Netzwerkverbindung?"),
)


def _verstaendlich(fehler: Exception) -> str:
    """Übersetzt die üblichen Netzwerkfehler in einen brauchbaren Satz.

    Was nicht in der Liste steht, wird unverändert durchgereicht: Eine
    unbekannte Meldung im Original ist immer noch besser als eine
    erfundene Erklärung, die in die Irre führt.
    """
    roh = str(fehler)
    klein = roh.lower()
    for muster, klartext in _UEBERSETZUNG:
        if any(m in klein for m in muster):
            return klartext
    return roh


class ImapFehler(RuntimeError):
    """Der Server war nicht erreichbar oder hat die Anmeldung abgelehnt."""


# ------------------------------------------------------- Ordnernamen lesen


def utf7_dekodieren(roh: str) -> str:
    """Übersetzt einen IMAP-Ordnernamen in lesbaren Text.

    Das Verfahren steht in RFC 3501, Abschnitt 5.1.3, und ist kein
    gewöhnliches UTF-7: Statt ``+`` leitet ``&`` eine Umschreibung ein,
    ``&-`` steht für ein einzelnes ``&``, und im Base64-Teil vertritt ``,``
    das ``/``. Python bringt dafür nichts mit.
    """
    if "&" not in roh:
        return roh

    ergebnis: list[str] = []
    rest = roh
    while rest:
        vor, trenner, nach = rest.partition("&")
        ergebnis.append(vor)
        if not trenner:
            break
        kodiert, _, rest = nach.partition("-")
        if not kodiert:
            ergebnis.append("&")
            continue
        try:
            # Base64 ohne Füllzeichen, deshalb wird auf ein Vielfaches von
            # vier aufgefüllt. Der Inhalt ist UTF-16 mit hohem Byte zuerst.
            gefuellt = kodiert.replace(",", "/")
            gefuellt += "=" * (-len(gefuellt) % 4)
            ergebnis.append(b64decode(gefuellt).decode("utf-16-be"))
        except (ValueError, UnicodeDecodeError):
            # Kein gültiger Umschreibungsblock – dann war das ``&`` wohl
            # wörtlich gemeint. Lieber ein schiefer Name als ein Abbruch.
            ergebnis.append("&" + kodiert + "-")
    return "".join(ergebnis)


def _antwort_text(teil) -> bytes:
    """Holt die Bytes aus einem Eintrag der Serverantwort."""
    if isinstance(teil, tuple):
        return teil[0] or b""
    return teil or b""


def _ordner_zerlegen(zeile: bytes) -> tuple[list[str], str, str] | None:
    """Zerlegt eine Zeile der LIST-Antwort in Merkmale, Trennzeichen, Name."""
    treffer = _LIST.match(zeile.strip())
    if not treffer:
        return None

    merkmale = [m.decode("ascii", "replace").lower() for m in treffer.group("attrs").split()]
    trenner = treffer.group("sep").decode("ascii", "replace").strip('"')
    if trenner == "NIL":
        trenner = ""

    name = treffer.group("name").strip()
    if name.startswith(b'"') and name.endswith(b'"'):
        name = name[1:-1]
    # Ordnernamen sind nach RFC 3501 reines ASCII – alles darüber steckt in
    # der UTF-7-Umschreibung. Ein Server, der sich nicht daran hält, soll
    # den Lauf trotzdem nicht aufhalten.
    return merkmale, trenner, name.decode("ascii", "replace")


class ImapSource(Source):
    """Ein IMAP-Postfach als Mailquelle.

    ``hoechststand`` sagt für einen Ordner, bis zu welcher UID schon
    archiviert wurde; ohne die Angabe wird alles geholt. ``zustand`` hält
    den UIDVALIDITY-Wert und vorgemerkte Nachzügler – warum beides getrennt
    ist, steht in :mod:`mailburg.core.sync`.

    ``verbindung`` nimmt ein fertiges ``imaplib``-Objekt entgegen. Nur so
    lässt sich der Abruf ohne echten Server prüfen.
    """

    def __init__(
        self,
        konto: Konto,
        passwort: str = "",
        *,
        hoechststand: Callable[[str], int] | None = None,
        zustand: Abrufzustand | None = None,
        ordner: list[str] | None = None,
        voll: bool = False,
        verbindung=None,
        zeitgrenze: int = ZEITGRENZE,
    ) -> None:
        self.konto = konto
        self.account = konto.name
        self.zustand = zustand
        self.voll = voll
        self.nur_ordner = ordner
        self._hoechststand = hoechststand or (lambda _ordner: 0)
        self._zeitgrenze = zeitgrenze
        #: Ordner, die der Server nicht hergab. Kein Abbruchgrund, aber der
        #: Anwender soll davon erfahren.
        self.warnungen: list[str] = []
        self._verbindung = verbindung
        self._eigene_verbindung = verbindung is None
        if verbindung is None:
            self._verbinden(passwort)

    # ------------------------------------------------------------ Anmelden

    def _tls_kontext(self) -> ssl.SSLContext:
        """Die TLS-Einstellungen für dieses Konto.

        Im Regelfall die Vorgaben des Systems: Zertifikat prüfen, Namen
        prüfen. Für ein Brückenprogramm auf dem eigenen Rechner geht das
        nicht – für ``127.0.0.1`` kann es kein beglaubigtes Zertifikat
        geben, weil keine Zertifizierungsstelle den eigenen Rechner
        beglaubigt. Warum das hier vertretbar ist, steht bei
        ``Konto.bruecke``.
        """
        kontext = ssl.create_default_context()
        if self.konto.ist_lokale_bruecke:
            kontext.check_hostname = False
            kontext.verify_mode = ssl.CERT_NONE
        return kontext

    def _zertifikat_erklaeren(self, exc: ssl.SSLCertVerificationError) -> str:
        """Macht aus einem abgelehnten Zertifikat eine brauchbare Auskunft.

        Bei einem Namensfehler wird nachgesehen, für welchen Namen das
        Zertifikat gilt, und der passende vorgeschlagen. Das ist der
        häufigste Fall bei eigenen Domains und führt sonst in eine
        Sackgasse, aus der nur das Abschalten der Prüfung herausführt –
        genau das soll niemand tun müssen.
        """
        from mailburg.core import tlsdiagnose

        kopf = (
            f"Das Zertifikat von {self.konto.server}:{self.konto.port} wurde "
            f"abgelehnt – {exc}"
        )

        if "Hostname mismatch" in str(exc) or "doesn't match" in str(exc):
            befund = tlsdiagnose.untersuchen(
                self.konto.server, self.konto.port, starttls=not self.konto.ssl
            )
            erklaerung = tlsdiagnose.erklaerung(self.konto.server, befund)
            if erklaerung:
                return f"{kopf}\n\n{erklaerung}"

        if self.konto.server in ("127.0.0.1", "::1", "localhost"):
            return (
                f"{kopf}\n\nDort läuft offenbar ein Brückenprogramm wie die "
                f"Proton Mail Bridge. Solche weisen sich selbstsigniert aus – "
                f"das Konto gehört mit --bruecke eingerichtet."
            )
        return kopf

    def _verbinden(self, passwort: str) -> None:
        if not passwort:
            raise ImapFehler(
                f"Für '{self.konto.name}' liegt kein Passwort vor. Es steht "
                f"weder im Schlüsselbund noch wurde eines angegeben."
            )
        kontext = self._tls_kontext()
        try:
            if self.konto.ssl:
                self._verbindung = imaplib.IMAP4_SSL(
                    self.konto.server,
                    self.konto.port,
                    ssl_context=kontext,
                    timeout=self._zeitgrenze,
                )
            else:
                self._verbindung = imaplib.IMAP4(
                    self.konto.server, self.konto.port, timeout=self._zeitgrenze
                )
                # Ohne STARTTLS ginge das Passwort im Klartext über die
                # Leitung. Schlägt es fehl, wird abgebrochen statt
                # heimlich unverschlüsselt weiterzumachen.
                self._verbindung.starttls(kontext)
        except ssl.SSLCertVerificationError as exc:
            # Beim Zertifikatsfehler steht die TCP-Verbindung schon; nur der
            # Handshake darüber scheiterte. Wer sie hier nicht schließt,
            # lässt sie für die Lebensdauer des Programms offen stehen -
            # gemessen: drei abgelehnte Anmeldungen, drei tote Verbindungen
            # zum Server, die erst mit dem Programm verschwanden.
            self._verbindung_wegwerfen()
            raise ImapFehler(self._zertifikat_erklaeren(exc)) from exc
        except (OSError, socket.timeout, ssl.SSLError, imaplib.IMAP4.error) as exc:
            self._verbindung_wegwerfen()
            hinweis = ""
            if self.konto.ist_lokale_bruecke:
                hinweis = (
                    "\nBrückenprogramme laufen nur, solange sie gestartet sind. "
                    "Läuft die Brücke gerade?"
                )
            raise ImapFehler(
                f"Keine Verbindung zu {self.konto.server}:{self.konto.port} – "
                f"{_verstaendlich(exc)}{hinweis}"
            ) from exc

        try:
            self._verbindung.login(self.konto.benutzer, passwort)
        except imaplib.IMAP4.error as exc:
            self._verbindung_wegwerfen()
            raise ImapFehler(
                f"Anmeldung als {self.konto.benutzer} abgelehnt – "
                f"{_verstaendlich(exc)}\n"
                f"Bei Gmail, GMX, Web.de und Outlook verlangt der Zugriff von "
                f"außen ein eigenes App-Passwort; das Kennwort der Weboberfläche "
                f"genügt dort nicht."
            ) from exc

    def _verbindung_wegwerfen(self) -> None:
        """Schließt eine halbfertige Verbindung, ohne noch einmal zu stören.

        Kein ``LOGOUT``: Der Server ist entweder nie so weit gekommen oder
        hat gerade abgelehnt. Hier zählt nur, dass das Betriebssystem den
        Anschluss zurückbekommt.
        """
        verbindung, self._verbindung = self._verbindung, None
        if verbindung is None:
            return
        try:
            verbindung.shutdown()
        except (OSError, imaplib.IMAP4.error, AttributeError):
            pass
        try:
            if getattr(verbindung, "sock", None) is not None:
                verbindung.sock.close()
        except OSError:
            pass

    def _befehl(self, *teile: str) -> list:
        """Setzt einen UID-Befehl ab und gibt die Nutzdaten zurück."""
        status, daten = self._verbindung.uid(*teile)
        if status != "OK":
            raise ImapFehler(f"Der Server lehnte '{teile[0]}' ab: {daten}")
        return [d for d in daten if d]

    # ------------------------------------------------------------- Ordner

    def _alle_ordner(self) -> list[tuple[str, str]]:
        """Alle archivierbaren Ordner als Paar aus rohem und lesbarem Namen."""
        status, daten = self._verbindung.list()
        if status != "OK":
            raise ImapFehler(f"Die Ordnerliste war nicht zu bekommen: {daten}")

        gefunden: list[tuple[str, str]] = []
        for eintrag in daten:
            zerlegt = _ordner_zerlegen(_antwort_text(eintrag))
            if zerlegt is None:
                continue
            merkmale, trenner, roh = zerlegt

            # \Noselect ist kein Ordner, sondern nur ein Ast im Baum.
            if "\\noselect" in merkmale or "\\nonexistent" in merkmale:
                continue
            if any(m in SONDERORDNER_AUS for m in merkmale):
                continue

            anzeige = utf7_dekodieren(roh)
            if trenner and trenner != "/":
                anzeige = anzeige.replace(trenner, "/")
            if self._ausgeschlossen(anzeige):
                continue
            if self.nur_ordner is not None and anzeige not in self.nur_ordner:
                continue
            gefunden.append((roh, anzeige))

        return sorted(gefunden, key=lambda paar: paar[1])

    def _ausgeschlossen(self, anzeige: str) -> bool:
        """Prüft jeden Bestandteil des Pfades gegen die Ausschlussliste.

        Damit trifft »Trash« auch ``INBOX/Trash`` und alles darunter – ein
        Unterordner des Papierkorbs ist genauso wenig archivierungswürdig
        wie dieser selbst.
        """
        aus = {name.casefold() for name in self.konto.ausschluss}
        return any(teil.casefold() in aus for teil in anzeige.split("/"))

    def folders(self) -> list[str]:
        return [anzeige for _, anzeige in self._alle_ordner()]

    # ------------------------------------------------------------- Abrufen

    def iter_messages(self) -> Iterator[RawMessage]:
        for roh, anzeige in self._alle_ordner():
            try:
                yield from self._ordner_lesen(roh, anzeige)
            except (ImapFehler, imaplib.IMAP4.error, OSError) as exc:
                # Ein Ordner, den der Server nicht hergibt, darf die
                # übrigen neunundzwanzig nicht kosten.
                self._melden(f"Ordner '{anzeige}' übersprungen: {exc}")

    def _ordner_lesen(self, roh: str, anzeige: str) -> Iterator[RawMessage]:
        status, daten = self._verbindung.select(f'"{roh}"', readonly=True)
        if status != "OK":
            raise ImapFehler(f"{daten}")

        anzahl = int(_antwort_text(daten[0]) or 0) if daten else 0
        if anzahl == 0:
            return

        uids = self._zu_holen(anzeige)
        if not uids:
            return

        for block in self._bloecke(uids):
            yield from self._block_holen(block, anzeige)

    def _zu_holen(self, anzeige: str) -> list[int]:
        """Ermittelt, welche UIDs dieser Lauf anfordern muss."""
        neu_lesen = self.voll
        if self.zustand is not None:
            gueltigkeit = self._uidvalidity()
            if gueltigkeit is not None and self.zustand.ordner_gesehen(
                self.account, anzeige, gueltigkeit
            ):
                # Der Server hat die UIDs neu vergeben. Alles, was wir über
                # diesen Ordner zu wissen glaubten, ist wertlos.
                neu_lesen = True

        seit = 0 if neu_lesen else self._hoechststand(anzeige)

        gefunden = set(self._suchen(f"UID {seit + 1}:*"))
        # ``n:*`` liefert nach RFC 3501 immer mindestens die höchste UID –
        # auch wenn die kleiner als n ist. Ohne diesen Filter holte jeder
        # Lauf die zuletzt archivierte Mail noch einmal.
        gefunden = {uid for uid in gefunden if uid > seit}

        if self.zustand is not None and not neu_lesen:
            gefunden |= self._nachzuegler_pruefen(anzeige)

        return sorted(gefunden)

    def _uidvalidity(self) -> int | None:
        antwort = self._verbindung.response("UIDVALIDITY")[1]
        for teil in antwort:
            rohtext = _antwort_text(teil).strip()
            if rohtext.isdigit():
                return int(rohtext)
        return None

    def _nachzuegler_pruefen(self, anzeige: str) -> set[int]:
        """Sieht nach, welche vorgemerkten UIDs es überhaupt noch gibt.

        Die Vormerkung wird dabei vollständig gelöscht, und zwar für beide
        Fälle zu Recht: Was der Anwender inzwischen gelöscht hat, braucht
        niemand mehr anzufordern, und der Rest wird ja gerade jetzt geholt.
        Scheitert eine dieser Mails erneut, merkt der Aufrufer sie im selben
        Lauf wieder vor. So bleibt die Liste kurz, statt Nummern
        mitzuschleppen, die längst im Archiv liegen.
        """
        offen = self.zustand.nachzuegler(self.account, anzeige)
        if not offen:
            return set()

        vorhanden: set[int] = set()
        for anfang in range(0, len(offen), BLOCK_SUCHE):
            teil = offen[anfang : anfang + BLOCK_SUCHE]
            vorhanden.update(self._suchen("UID " + ",".join(str(u) for u in teil)))

        for uid in offen:
            self.zustand.erledigt(self.account, anzeige, uid)
        return vorhanden

    def _suchen(self, ausdruck: str) -> list[int]:
        daten = self._befehl("SEARCH", None, ausdruck)
        return [int(teil) for teil in b" ".join(daten).split() if teil.isdigit()]

    def _bloecke(self, uids: list[int]) -> Iterator[list[int]]:
        """Teilt die UIDs in Anforderungen auf, die in den Speicher passen.

        Die Größen sind vorher bekannt, weil ``RFC822.SIZE`` sie ohne den
        Inhalt liefert. Ein Umlauf mehr je Ordner, dafür sprengt kein
        Ordner voller Bildanhänge den Arbeitsspeicher.
        """
        groessen = self._groessen(uids)
        block: list[int] = []
        summe = 0
        for uid in uids:
            groesse = groessen.get(uid, 0)
            if block and (len(block) >= BLOCK_MAILS or summe + groesse > BLOCK_BYTES):
                yield block
                block, summe = [], 0
            block.append(uid)
            summe += groesse
        if block:
            yield block

    def _groessen(self, uids: list[int]) -> dict[int, int]:
        groessen: dict[int, int] = {}
        for anfang in range(0, len(uids), BLOCK_SUCHE):
            teil = uids[anfang : anfang + BLOCK_SUCHE]
            daten = self._befehl(
                "FETCH", ",".join(str(u) for u in teil), "(UID RFC822.SIZE)"
            )
            for eintrag in daten:
                zeile = _antwort_text(eintrag)
                kennung, groesse = _UID.search(zeile), _SIZE.search(zeile)
                if kennung and groesse:
                    groessen[int(kennung.group(1))] = int(groesse.group(1))
        return groessen

    def _block_holen(self, uids: list[int], anzeige: str) -> Iterator[RawMessage]:
        bereich = ",".join(str(u) for u in uids)
        # BODY.PEEK[] statt BODY[]: Sonst setzt der Server \Seen, und
        # ungelesene Post gilt nach dem Archivieren als gelesen.
        daten = self._befehl("FETCH", bereich, "(UID FLAGS BODY.PEEK[])")

        geliefert: set[int] = set()
        for eintrag in daten:
            if not isinstance(eintrag, tuple) or len(eintrag) < 2:
                continue
            kopf, inhalt = eintrag[0], eintrag[1]
            treffer = _UID.search(kopf or b"")
            if treffer is None or not inhalt:
                continue
            uid = int(treffer.group(1))
            geliefert.add(uid)

            marken = _FLAGS.search(kopf or b"")
            yield RawMessage(
                raw=bytes(inhalt),
                folder=anzeige,
                uid=uid,
                flags=marken.group(1).decode("ascii", "replace") if marken else "",
            )

        # Was angefordert, aber nicht geliefert wurde, ist in der Zeit
        # zwischen Suche und Abruf gelöscht worden – oder der Server hat
        # sich verschluckt. Beim nächsten Lauf noch einmal versuchen.
        if self.zustand is not None:
            for uid in set(uids) - geliefert:
                self.zustand.vormerken(self.account, anzeige, uid)

    # -------------------------------------------------------------- Sonstiges

    def uids_vor(self, stichtag) -> Iterator[tuple[str, set[int]]]:
        """Sagt je Ordner, welche Mails älter als der Stichtag sind.

        Für den Abgleich vor dem Aufräumen im Mailclient. Gefragt wird nach
        ``BEFORE``, und das bezieht sich auf den Zeitpunkt, zu dem die Mail
        beim Server ankam – nicht auf das ``Date:`` im Kopf. Das ist auch
        die richtige Bezugsgröße: Aufräumregeln in Mailprogrammen rechnen
        genauso, und ein gefälschtes Absendedatum soll hier nichts
        verschieben.
        """
        # IMAP will den Monat englisch abgekürzt, unabhängig von der
        # Spracheinstellung des Rechners - deshalb die feste Liste statt
        # strftime, das sich nach der Umgebung richtet.
        monate = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        datum = f"{stichtag.day:02d}-{monate[stichtag.month - 1]}-{stichtag.year}"

        for roh, anzeige in self._alle_ordner():
            status, daten = self._verbindung.select(f'"{roh}"', readonly=True)
            if status != "OK":
                self._melden(f"Ordner '{anzeige}' übersprungen: {daten}")
                continue
            try:
                yield anzeige, set(self._suchen(f"BEFORE {datum}"))
            except (ImapFehler, imaplib.IMAP4.error, OSError) as exc:
                self._melden(f"Ordner '{anzeige}' übersprungen: {exc}")

    def _melden(self, text: str) -> None:
        """Sammelt Warnungen, die kein Abbruch sind."""
        self.warnungen.append(text)

    def describe(self) -> str:
        return f"IMAP {self.konto.beschreibung()}"

    def close(self) -> None:
        if self._verbindung is None or not self._eigene_verbindung:
            return
        try:
            self._verbindung.logout()
        except (imaplib.IMAP4.error, OSError):
            # Beim Abmelden schiefgegangene Dinge sind gleichgültig – die
            # Mails liegen längst im Archiv.
            pass
        finally:
            self._verbindung = None
