"""Das Archiv – hält Ablage, Journal und Index zusammen.

Ein Archiv ist ein Verzeichnis. Wo es liegt, entscheidet der Benutzer:
interne Platte, USB-Platte, ein von Nextcloud synchronisierter Ordner. Nach
außen sieht es überall gleich aus::

    MeinArchiv/
    ├── archive.json     Kennung, Betriebsart, Fristenregel
    ├── mail/            die Mails selbst
    └── meta/            das Journal mit der Hash-Kette

**Zwei Betriebsarten.** Im *Privatarchiv* darf gelöscht werden wie in jedem
Ordner; es gibt keine Fristen und keine Kette zu wahren. Das entspricht der
Rechtslage: Wer ausschließlich eigene Mails archiviert, fällt unter die
Haushaltsausnahme des Art. 2 Abs. 2 lit. c DSGVO und unterliegt der
Verordnung gar nicht.

Im *Geschäftsarchiv* gilt das Gegenteil. Jeder Vorgang wandert in die
Hash-Kette, gelöscht wird nur über Grabsteine, und Aufbewahrungsfristen
schützen vor zu frühem Entfernen. Das Programm unterstützt damit einen
revisionssicheren Betrieb – es *stellt ihn nicht her*. Dazu gehören
Verfahrensdokumentation und Organisation beim Anwender; eine Software allein
kann das nicht leisten, und niemand sollte etwas anderes behaupten.
"""

from __future__ import annotations

import json
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from mailburg import FORMAT_VERSION, __version__
from mailburg.core import paths
from mailburg.core.index import Index
from mailburg.core.journal import Journal
from mailburg.core.retention import Category, Jurisdiction, Policy
from mailburg.core.store import Store

ARCHIVE_FILE = "archive.json"
LOCK_FILE = ".mailburg-lock"


def _angemeldeter_benutzer() -> str:
    """Wer gerade am Rechner sitzt – für den Grabstein einer Löschung.

    Über ``getpass``, nicht über ``$USER``: Diese Variable gibt es unter
    Windows nicht, sie heißt dort ``USERNAME``. Ein Grabstein, in dem
    „unbekannt" steht, wäre in einem Geschäftsarchiv der halbe Zweck der
    Übung – wer gelöscht hat, gehört ins Protokoll.
    """
    import getpass

    try:
        return getpass.getuser()
    except (OSError, KeyError, ImportError):
        # Kommt vor, wenn kein Benutzerkonto zu ermitteln ist – etwa in
        # einem Container ohne Eintrag in /etc/passwd.
        return "unbekannt"


class Mode(StrEnum):
    """Betriebsart eines Archivs."""

    PRIVAT = "privat"
    GESCHAEFTLICH = "geschaeftlich"

    @property
    def is_business(self) -> bool:
        return self is Mode.GESCHAEFTLICH


def _laeuft_noch(held: dict) -> bool | None:
    """Läuft der Prozess, der die Sperre hält, auf diesem Rechner noch?

    ``None`` heißt: nicht zu beantworten – die Sperre stammt von einem
    anderen Rechner. Über dessen Prozesse lässt sich von hier aus nichts
    sagen, und Raten wäre hier schlimmer als Schweigen.
    """
    if held.get("host") != socket.gethostname():
        return None
    pid = held.get("pid")
    if not isinstance(pid, int):
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Es gibt ihn, er gehört nur jemand anderem.
        return True
    except OSError:
        return None
    return True


def _sperre_erklaeren(lock: "Path", held: dict) -> str:
    """Sagt, was wirklich los ist – und rät nur dann zum Löschen.

    Die frühere Fassung riet in jedem Fall dazu, die Sperrdatei von Hand
    zu entfernen. Das ist gefährlich: Meistens hält sie kein Absturz,
    sondern der Abruf im Hintergrund, der planmäßig alle halbe Stunde
    läuft. Wer dann löscht, hat zwei Läufe gleichzeitig am selben Journal
    – genau das, was die Sperre verhindern soll.
    """
    host = held.get("host", "unbekannt")
    since = held.get("since", "unbekannt")
    laeuft = _laeuft_noch(held)

    if laeuft is True:
        # Kein Wort über Sperrdateien, Prozesse oder Journale. Das ist
        # kein Fehler, den jemand beheben müsste, sondern der normale
        # Betrieb - und wer in diesem Moment eine Anleitung zum Löschen
        # von Dateien bekäme, richtete damit Schaden an.
        return (
            "Es werden gerade neue Mails abgerufen.\n"
            "Bitte haben Sie einen Augenblick Geduld."
        )
    if laeuft is False:
        return (
            f"Das Archiv ist seit {since} als geöffnet vermerkt, aber der "
            f"Vorgang, der es hielt, läuft nicht mehr – vermutlich ein "
            f"Überbleibsel eines Absturzes.\n"
            f"Die Datei {lock} kann gelöscht werden."
        )
    return (
        f"Das Archiv ist seit {since} auf '{host}' geöffnet.\n"
        f"Läuft dort noch MailBurg, bitte dort erst schließen. Ist der "
        f"Rechner längst aus, kann die Datei {lock} von Hand gelöscht "
        f"werden."
    )


class ArchiveLocked(RuntimeError):
    """Ein anderer Rechner oder Vorgang hat das Archiv gerade offen."""


class ArchiveError(RuntimeError):
    """Das Archiv lässt sich nicht öffnen oder ist beschädigt."""


@dataclass
class AddResult:
    """Was beim Aufnehmen einer Mail geschah."""

    hash: str
    bucket: str
    stored: bool
    """``False``, wenn die Mail schon in der Ablage war."""

    indexed: bool
    """``False``, wenn sie nur einen weiteren Fundort bekam."""


#: Ab wann eine Mail in einem Privatarchiv als »alt« gilt.
#:
#: Bewusst nicht sechs Jahre – das ist die Handelsbrieffrist und hat in
#: einem Privatarchiv nichts zu suchen. Am 2026-08-28 mit Stephan
#: besprochen und an seinem Bestand nachgerechnet.
ALT_AB_JAHREN = 10


def archivname(pfad) -> str:
    """Der Anzeigename eines Archivs, ohne es dafür zu öffnen.

    Ein Archiv zu öffnen setzt eine Sperrdatei und baut den Index auf.
    Für einen Menüeintrag ist das zu viel; hier genügt ein Blick in
    ``archive.json``.

    Lässt sie sich nicht lesen – abgezogene Platte, verhunzte Datei –,
    bleibt der Ordnername. Der ist immer noch besser als nichts.
    """
    import json

    pfad = Path(pfad)
    try:
        meta = json.loads(
            (pfad / "archive.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return pfad.name
    return meta.get("name") or pfad.name


def archivnamen() -> dict[str, str]:
    """Kennung -> Name, für alle Archive, die MailBurg schon einmal sah.

    **Warum das hier steht und nicht zweimal woanders.** Die
    Kontenlisten kennen nur Kennungen wie
    ``c89fdf58-7ec8-4804-af89-915b71440b7b``; der Name steht im Archiv
    selbst. Sowohl die Kommandozeile als auch die Postfachverwaltung
    müssen ihn nachschlagen – und hatten dafür bis zum 2026-08-29 je
    eine eigene Fassung. Zwei Stellen, die dasselbe tun, laufen
    irgendwann auseinander.

    Gelesen wird **einmal je Archiv**, nicht einmal je Kennung. Die
    frühere Fassung in der Oberfläche ging für jedes Postfach erneut
    durch alle Archivdateien; bei acht Postfächern und zwei Archiven
    waren das sechzehn Durchläufe für zwei Antworten.

    Was sich nicht auflösen lässt – etwa weil die Platte gerade nicht
    angeschlossen ist –, fehlt im Ergebnis. Der Aufrufer entscheidet,
    was er dann anzeigt; die Kennung wegzulassen wäre falsch, denn ein
    Archiv auf einer abgezogenen Platte hat trotzdem Postfächer.
    """
    import json

    from mailburg.core.einstellungen import zuletzt_benutzte_pfade

    namen: dict[str, str] = {}
    for roh in zuletzt_benutzte_pfade():
        pfad = Path(roh)
        try:
            daten = json.loads(
                (pfad / "archive.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue
        kennung = daten.get("uuid")
        if kennung:
            namen[kennung] = daten.get("name") or pfad.name
    return namen





class Archive:
    """Ein geöffnetes Archiv."""

    def __init__(self, root: Path, meta: dict[str, Any], *, exclusive: bool = True) -> None:
        self.root = root
        self.meta = meta
        self._lock_held = False

        if exclusive:
            self._acquire_lock()

        self.store = Store(root / "mail")
        self.journal = Journal(root / "meta")
        self.index = Index(paths.index_path(self.uuid))

    # ------------------------------------------------------------- Anlegen

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        mode: Mode = Mode.PRIVAT,
        jurisdiction: Jurisdiction = Jurisdiction.DE,
        name: str = "",
        bafin_supervised: bool = False,
    ) -> Archive:
        """Legt ein neues Archiv an."""
        root = Path(root).expanduser().resolve()
        if (root / ARCHIVE_FILE).exists():
            raise ArchiveError(f"In {root} liegt bereits ein Archiv.")
        root.mkdir(parents=True, exist_ok=True)

        meta = {
            "format_version": FORMAT_VERSION,
            "uuid": str(uuid.uuid4()),
            "name": name or root.name,
            "mode": str(mode),
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "created_by": f"MailBurg {__version__}",
            "retention": {
                "jurisdiction": str(jurisdiction),
                "bafin_supervised": bafin_supervised,
            },
            "encryption": None,
        }
        (root / ARCHIVE_FILE).write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        archive = cls(root, meta)
        # Der erste Eintrag verankert die Kette. Ohne ihn ließe sich später
        # nicht belegen, wann das Archiv entstand und mit welchen Vorgaben.
        archive.journal.append(
            "create",
            uuid=meta["uuid"],
            name=meta["name"],
            mode=str(mode),
            jurisdiction=str(jurisdiction),
            format_version=FORMAT_VERSION,
            program=meta["created_by"],
        )
        archive.journal.flush()
        return archive

    @classmethod
    def open(cls, root: Path, *, exclusive: bool = True) -> Archive:
        """Öffnet ein vorhandenes Archiv."""
        root = Path(root).expanduser().resolve()
        marker = root / ARCHIVE_FILE
        if not marker.exists():
            raise ArchiveError(f"In {root} liegt kein MailBurg-Archiv.")

        try:
            meta = json.loads(marker.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ArchiveError(f"{ARCHIVE_FILE} ist beschädigt: {exc}") from exc

        version = meta.get("format_version", 0)
        if version > FORMAT_VERSION:
            raise ArchiveError(
                f"Das Archiv wurde mit einer neueren Programmfassung angelegt "
                f"(Format {version}, dieses Programm kann {FORMAT_VERSION}). "
                f"Bitte MailBurg aktualisieren."
            )
        return cls(root, meta, exclusive=exclusive)

    # -------------------------------------------------------------- Sperren

    def _acquire_lock(self) -> None:
        """Verhindert, dass zwei Rechner gleichzeitig hineinschreiben.

        Beim Archiv in der Cloud ist das keine Theorie: Läuft MailBurg auf
        dem Rechner in der Firma und dem zu Hause gleichzeitig, schreiben
        beide ans Journal, und Nextcloud macht daraus einen Konflikt, den
        niemand mehr auflösen kann.
        """
        lock = self.root / LOCK_FILE
        payload = json.dumps(
            {
                "host": socket.gethostname(),
                "pid": os.getpid(),
                "since": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
        )
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                held = json.loads(lock.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                held = {}
            raise ArchiveLocked(_sperre_erklaeren(lock, held)) from None
        # Gelesen wird oben ausdrücklich als UTF-8, also muss auch so
        # geschrieben werden. Ohne die Angabe nimmt Python die Kodierung des
        # Systems – cp1252 unter Windows, ASCII bei LC_ALL=C. Ein Rechnername
        # mit Umlaut machte die Sperrdatei damit unlesbar, und der Hinweis,
        # wo das Archiv gerade offen ist, wäre verloren.
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        self._lock_held = True

    def _release_lock(self) -> None:
        if self._lock_held:
            (self.root / LOCK_FILE).unlink(missing_ok=True)
            self._lock_held = False

    # ------------------------------------------------------------ Aufnehmen

    def add(
        self,
        raw: bytes,
        *,
        account: str,
        folder: str,
        uid: int | None = None,
        flags: str = "",
        parsed=None,
        attachment_text: str = "",
    ) -> AddResult:
        """Nimmt eine Mail auf: Ablage, Journal und Index in einem Zug.

        Die Reihenfolge ist nicht beliebig. Erst muss die Mail sicher auf
        der Platte liegen, dann darf das Journal behaupten, dass es sie
        gibt. Andersherum entstünde bei einem Absturz ein Eintrag ohne
        Inhalt – und damit eine Lücke, die wie eine Manipulation aussieht.
        """
        from mailburg.extract import message as message_module

        if parsed is None:
            parsed = message_module.parse(raw)

        result = self.store.put(raw, parsed.date)

        # Protokolliert wird jeder *Fundort*, nicht jede Datei. Dieselbe
        # Rundmail in zwei Postfächern ist zweimal archiviert worden, auch
        # wenn sie nur einmal auf der Platte liegt – und beide Vorgänge
        # müssen im Journal stehen. Sonst wäre es nicht mehr die
        # vollständige Wahrheit, und beim Neuaufbau des Index ginge der
        # zweite Ordner verloren.
        if not self.index.has_location(result.hash, account, folder):
            self.journal.append(
                "add",
                hash=result.hash,
                bucket=result.bucket,
                account=account,
                folder=folder,
                uid=uid,
                size=len(raw),
                date=parsed.date.isoformat() if parsed.date else None,
                subject=parsed.subject[:200],
                sender=parsed.from_addr,
                attachments=len(parsed.attachments),
                stored=result.stored,
            )

        indexed = self.index.add(
            digest=result.hash,
            bucket=result.bucket,
            parsed=parsed,
            size=len(raw),
            account=account,
            folder=folder,
            uid=uid,
            flags=flags,
            attachment_text=attachment_text,
        )

        # **Regeln greifen nur bei neu aufgenommener Post.** Eine Mail,
        # die schon im Archiv liegt und von Hand eingestuft wurde, darf
        # eine später angelegte Regel nicht überfahren – sonst wäre eine
        # bewusste Entscheidung des Anwenders weniger wert als ein
        # Suchmuster. Wer bestehende Post nachstufen will, tut das
        # ausdrücklich über »Regeln anwenden«.
        if indexed:
            self._regel_anwenden(result.hash, folder=folder, parsed=parsed)

        return AddResult(
            hash=result.hash, bucket=result.bucket, stored=result.stored, indexed=indexed
        )

    def _regel_anwenden(self, digest: str, *, folder: str, parsed) -> None:
        """Stuft eine frisch aufgenommene Mail ein, falls eine Regel greift.

        Der Journaleintrag nennt die Regel als Urheber, nicht den
        angemeldeten Benutzer. Wer später liest, wer diese Mail für
        privat erklärt hat, soll nicht fälschlich einen Menschen dort
        finden.
        """
        regelwerk = self.regeln
        if not len(regelwerk):
            return

        befund = regelwerk.einstufung(
            ordner=folder,
            von=parsed.from_addr or "",
            an=" ".join(getattr(parsed, "to_addrs", None) or []),
        )
        if befund is None:
            return

        kategorie, begruendung = befund
        self.classify(
            digest, kategorie, actor="Regel", note=begruendung
        )

    # -------------------------------------------------------------- Löschen

    def delete(
        self,
        digest: str,
        bucket: str,
        *,
        reason: str,
        actor: str = "",
        note: str = "",
        override_retention: bool = False,
    ) -> None:
        """Entfernt eine Mail und hinterlässt einen Grabstein.

        Der Inhalt verschwindet, der Vorgang bleibt. Damit lassen sich das
        Löschverlangen nach Art. 17 DSGVO und die Unveränderbarkeit
        zugleich erfüllen: Was gelöscht wurde, ist weg – dass gelöscht
        wurde, bleibt belegbar.

        ``reason`` sollte benennen, warum: ``dsgvo_art17``,
        ``frist_abgelaufen``, ``irrtuemlich_archiviert``, ``privat``.
        """
        if self.mode.is_business and not override_retention:
            self._check_retention(digest)

        removed = self.store.remove(digest, bucket)
        self.journal.append(
            "delete",
            hash=digest,
            bucket=bucket,
            reason=reason,
            actor=actor or _angemeldeter_benutzer(),
            note=note,
            file_existed=removed,
        )
        self.index.remove(digest)
        self.journal.flush()
        self.index.commit()

    def classify(
        self,
        digest: str,
        category: "Category | str",
        *,
        actor: str = "",
        note: str = "",
    ) -> "Category":
        """Stuft eine Mail aufbewahrungsrechtlich ein.

        Handelsbrief, Buchungsbeleg oder privat – davon hängt ab, wie
        lange MailBurg das Löschen bremst. Sechs, acht oder zehn Jahre
        sind ein Unterschied, und ``unbestimmt`` wird sicherheitshalber
        wie die längste Pflicht behandelt.

        **Der Vorgang wandert ins Journal.** Nicht aus Ordnungsliebe: Für
        ein Geschäftsarchiv ist »wer hat wann was wozu erklärt« Teil der
        Verfahrensdokumentation. Wer später begründen muss, warum eine
        Mail nach sechs statt acht Jahren gelöscht wurde, will auf einen
        Eintrag zeigen können – und der Eintrag hängt in der Hash-Kette,
        lässt sich also nicht nachträglich glattziehen.

        Zurückgegeben wird die vorherige Einstufung. Das ist mehr als
        Höflichkeit: Wer versehentlich hundert Mails umstellt, soll sie
        zurückstellen können.
        """
        ziel = Category(category)

        row = self.index.db.execute(
            "SELECT category FROM messages WHERE hash = ?", (digest,)
        ).fetchone()
        if row is None:
            raise ArchiveError(f"Diese Mail liegt nicht im Archiv: {digest}")
        vorher = Category(row["category"] or Category.UNBESTIMMT)

        if vorher == ziel:
            return vorher

        self.journal.append(
            "classify",
            hash=digest,
            category=ziel.value,
            previous=vorher.value,
            actor=actor or _angemeldeter_benutzer(),
            note=note,
        )
        self.index.set_category(digest, ziel.value)
        self.journal.flush()
        self.index.commit()
        return vorher

    def faellige(self, today=None) -> list:
        """Mails, deren Aufbewahrungsfrist abgelaufen ist.

        **Die andere Richtung derselben Rechnung.** Fristen schützen vor
        zu frühem Löschen – aber nach ihrem Ablauf verlangt die DSGVO,
        dass personenbezogene Daten auch wieder verschwinden. Ein Archiv,
        das nur aufbewahrt, erfüllt die eine Hälfte und verletzt die
        andere.

        Gerechnet wird je Kategorie eine Jahresgrenze, nicht Mail für
        Mail: Bei sechzehntausend Nachrichten wäre das sonst spürbar. Wer
        etwa in Deutschland Handelsbriefe sechs Jahre hält, sucht 2026
        alles aus 2019 und früher.

        Gibt nur Auskunft. Gelöscht wird ausschließlich auf
        ausdrückliche Bestätigung – ein Programm, das eigenmächtig
        Geschäftsunterlagen entfernt, richtet mehr Schaden an als jede zu
        lange aufbewahrte Mail.
        """
        from datetime import date as _date

        heute = today or _date.today()
        treffer = []
        for kategorie in Category:
            jahre = self.policy.years(kategorie)
            if jahre is None:
                # Privat: keine Frist, also nichts fällig. Wer solche
                # Post loswerden will, löscht sie ohnehin ungebremst.
                continue
            # Eine Mail aus dem Jahr J ist bis Ende J+jahre zu halten.
            # Fällig ist also alles aus Jahren, für die J + jahre < heute.
            juengstes = heute.year - jahre - 1
            if juengstes < 1900:
                continue
            treffer.extend(
                self.index.search(
                    f"kategorie:{kategorie.value} jahr:1900-{juengstes}",
                    limit=1_000_000,
                )
            )
        treffer.sort(key=lambda t: t.date or "")
        return treffer

    def alte(self, jahre: int = ALT_AB_JAHREN, today=None) -> list:
        """Mails, die älter als ``jahre`` Jahre sind.

        **Für Privatarchive, wo es keine Fristen gibt.** Dort ist Alter
        kein Grund zum Löschen, sondern nur ein Anhaltspunkt beim
        Aufräumen – die Mail vom verstorbenen Vater aus 2012 ist mehr
        wert als die von gestern. Deshalb heißt die Methode ``alte`` und
        nicht ``faellige``: Es ist eine Auskunft, keine Aufforderung.

        **Zehn Jahre als Vorgabe, nicht sechs.** Sechs ist die
        Handelsbrieffrist – bei privater Post gibt es keinen Grund, sich
        daran zu orientieren. Und Post von vor sechs Jahren ist oft noch
        in Gebrauch: Versicherungspolicen, Garantien, Kaufbelege für
        langlebige Geräte, Mietverträge. Was zehn Jahre alt ist, ist
        unstrittig alt.

        Der Aufrufer entscheidet, wie er das nennt. MailBurg zählt nur.
        """
        from datetime import date as _date

        heute = today or _date.today()
        grenze = heute.year - max(1, int(jahre))
        treffer = self.index.search(
            f"jahr:1900-{grenze}", limit=1_000_000
        )
        treffer.sort(key=lambda t: t.date or "")
        return treffer

    def _check_retention(self, digest: str) -> None:
        """Bremst das Löschen, solange eine Aufbewahrungsfrist läuft."""
        row = self.index.db.execute(
            "SELECT date, category FROM messages WHERE hash = ?", (digest,)
        ).fetchone()
        if row is None or not row["date"]:
            return

        try:
            reference = datetime.fromisoformat(row["date"]).date()
        except ValueError:
            return

        category = Category(row["category"])
        if self.policy.is_locked(category, reference):
            end = self.policy.expires_end_of(category, reference)
            raise RetentionLocked(
                f"Diese Mail unterliegt noch der Aufbewahrungspflicht "
                f"({category.value}, bis Ende {end}). Löschen ist erst danach "
                f"zulässig – oder ausdrücklich unter Angabe eines Grundes."
            )

    # --------------------------------------------------------------- Prüfen

    def seal(self, timestamp_token: str | None = None) -> dict[str, Any]:
        """Setzt ein Siegel über den bisherigen Stand.

        Das Siegel hält fest, wie viele Einträge das Journal zu diesem
        Zeitpunkt hatte und welchen Hash der letzte trug. Ein späterer
        Eingriff irgendwo davor lässt sich damit auf den Abschnitt zwischen
        zwei Siegeln eingrenzen.

        ``timestamp_token`` nimmt einen Zeitstempel nach RFC 3161 auf. Die
        Kette beweist von sich aus nur die *Reihenfolge* der Einträge, nicht
        den Zeitpunkt – erst ein Stempel von dritter Seite belegt, dass der
        Stand zu einer bestimmten Zeit schon so vorlag.
        """
        self.journal.flush()
        entry = self.journal.append(
            "seal",
            count=self.journal.count,
            covers=self.journal.last_hash,
            tsa=timestamp_token,
        )
        self.journal.flush()
        return entry

    def verify(self) -> dict[str, Any]:
        """Prüft Kette und Ablage gegeneinander.

        Drei Fragen: Ist die Hash-Kette unversehrt? Liegt zu jedem
        ``add``-Eintrag ohne späteren Grabstein auch eine Datei? Und gibt es
        Dateien, die im Journal gar nicht vorkommen?

        Die letzte Frage ist die interessanteste – eine Mail, die jemand von
        Hand in ``mail/`` gelegt hat, ist nicht archiviert, sondern
        untergeschoben.
        """
        chain = self.journal.verify()

        expected: dict[str, str] = {}
        for entry in self.journal.read_all():
            if entry.get("op") == "add":
                expected[entry["hash"]] = entry["bucket"]
            elif entry.get("op") == "delete":
                expected.pop(entry.get("hash", ""), None)

        on_disk = dict(self.store.iter_all())
        missing = sorted(set(expected) - set(on_disk))
        unexpected = sorted(set(on_disk) - set(expected))

        return {
            "chain_ok": chain.ok,
            "chain_entries": chain.entries,
            "chain_errors": [str(e) for e in chain.errors],
            "expected": len(expected),
            "on_disk": len(on_disk),
            "missing": missing,
            "unexpected": unexpected,
            "ok": chain.ok and not missing and not unexpected,
        }

    def rebuild_index(self, *, progress=None, mit_anhangstext: bool = True) -> int:
        """Baut den Suchindex vollständig aus Ablage und Journal neu.

        Das ist der Grund, warum der Index nicht gesichert werden muss:
        Solange ``mail/`` und ``meta/`` da sind, ist er in Minuten wieder da.

        Der Text der Anhänge wird dabei erneut ausgelesen. Das dauert
        länger, ist aber notwendig – sonst wäre der neu gebaute Index
        weniger wert als der alte, und die Zusicherung, dass er sich
        vollständig aus dem Archiv ergibt, wäre gebrochen.
        """
        from mailburg.extract import message as message_module
        from mailburg.extract import text as text_module

        self.index.close()
        index_file = paths.index_path(self.uuid)
        index_file.unlink(missing_ok=True)
        for extra in ("-wal", "-shm"):
            index_file.with_name(index_file.name + extra).unlink(missing_ok=True)
        self.index = Index(index_file)

        # Fundorte stehen im Journal, nicht in der Mail. Wir sammeln sie
        # zuerst, damit jede Mail gleich mit allen ihren Ordnern hineingeht.
        locations: dict[str, list[dict[str, Any]]] = {}
        deleted: set[str] = set()
        for entry in self.journal.read_all():
            op = entry.get("op")
            if op == "add":
                locations.setdefault(entry["hash"], []).append(entry)
            elif op == "delete":
                deleted.add(entry.get("hash", ""))

        count = 0
        for digest, entries in locations.items():
            if digest in deleted:
                continue
            bucket = entries[0]["bucket"]
            try:
                raw = self.store.get(digest, bucket)
            except (FileNotFoundError, ValueError):
                continue

            parsed = message_module.parse(raw, with_payloads=mit_anhangstext)
            anhangstext = ""
            if mit_anhangstext and parsed.attachments:
                anhangstext, _ = text_module.aus_mail(parsed)

            for entry in entries:
                self.index.add(
                    digest=digest,
                    bucket=bucket,
                    parsed=parsed,
                    size=len(raw),
                    account=entry.get("account", ""),
                    folder=entry.get("folder", ""),
                    uid=entry.get("uid"),
                    attachment_text=anhangstext,
                    # Aus dem Journal, nicht von der Uhr: Sonst stünde nach
                    # einem Neuaufbau überall der heutige Tag, und die
                    # Auskunft "wann kam das ins Archiv" wäre gefälscht -
                    # ausgerechnet die, die eine Verfahrensdokumentation
                    # braucht.
                    archiviert=entry.get("ts"),
                )
            count += 1
            if progress and count % 500 == 0:
                progress(count, len(locations))
                self.index.commit()

        self.index.commit()
        self.index.optimize()
        return count

    # ------------------------------------------------------------ Merkmale

    @property
    def uuid(self) -> str:
        return self.meta["uuid"]

    @property
    def name(self) -> str:
        return self.meta.get("name", self.root.name)

    @property
    def mode(self) -> Mode:
        return Mode(self.meta.get("mode", Mode.PRIVAT))

    @property
    def policy(self) -> Policy:
        settings = self.meta.get("retention", {})
        return Policy(
            jurisdiction=Jurisdiction(settings.get("jurisdiction", "de")),
            bafin_supervised=bool(settings.get("bafin_supervised", False)),
        )

    @property
    def regeln(self):
        """Die Einstufungsregeln dieses Archivs.

        Wird bei jedem Zugriff neu gebaut statt zwischengespeichert: Der
        Aufwand ist eine Handvoll Zeichenketten, und eine zweite Sitzung
        kann die Regeln inzwischen geändert haben.
        """
        from mailburg.core.regeln import Regelwerk

        return Regelwerk.aus_daten(self.meta.get("regeln", []))

    def regeln_setzen(self, regelwerk, *, actor: str = "") -> None:
        """Ersetzt die Regeln – und schreibt den Vorgang ins Journal.

        **Erst das Journal, dann die Datei.** Bricht etwas dazwischen ab,
        steht im Protokoll eine Änderung, die nicht wirksam wurde – das
        ist nachvollziehbar. Andersherum wäre eine wirksame Änderung
        ohne Eintrag entstanden, und die sieht aus wie eine Manipulation.

        Welche Regeln wann galten, gehört zur Verfahrensdokumentation:
        Wer erklären muss, warum eine Mail nicht der Aufbewahrung
        unterlag, zeigt auf diesen Eintrag.
        """
        vorher = self.meta.get("regeln", [])
        nachher = regelwerk.als_daten()
        if vorher == nachher:
            return

        self.journal.append(
            "rules",
            rules=nachher,
            previous=vorher,
            actor=actor or _angemeldeter_benutzer(),
        )
        self.journal.flush()

        self.meta["regeln"] = nachher
        self._meta_schreiben()

    @property
    def benutzer(self):
        """Die Zugänge dieses Archivs.

        Wie bei den Regeln bei jedem Zugriff frisch gelesen: Eine zweite
        Sitzung – oder der Verwalter am Server – kann sie inzwischen
        geändert haben, und ein zwischengespeicherter Stand hieße hier,
        dass ein entzogenes Recht noch eine Weile gilt.
        """
        from mailburg.core.benutzer import Benutzerliste

        return Benutzerliste.lesen(self.root)

    def benutzer_setzen(self, liste, *, actor: str = "") -> None:
        """Ersetzt die Zugänge – und schreibt den Vorgang ins Journal.

        **Ohne Prüfwerte im Protokoll.** Ins Journal kommt, wer angelegt,
        geändert oder stillgelegt wurde und welche Rechte er hat – nicht
        aber der Prüfwert seines Passworts. Ein Protokoll, das nicht
        verändert werden darf, ist der denkbar schlechteste Ort für ein
        Geheimnis: Es lässt sich nachträglich nicht mehr herausnehmen.

        Erst das Journal, dann die Datei – aus demselben Grund wie bei
        den Regeln.
        """
        vorher = _ohne_pruefwerte(self.benutzer.als_daten())
        nachher = _ohne_pruefwerte(liste.als_daten())

        if vorher != nachher:
            self.journal.append(
                "users",
                users=nachher,
                previous=vorher,
                actor=actor or _angemeldeter_benutzer(),
            )
            self.journal.flush()

        liste.schreiben(self.root)

    def _meta_schreiben(self) -> None:
        """Schreibt ``archive.json`` – über eine Zwischendatei.

        Ein abgebrochenes Schreiben mitten in der Datei hinterließe ein
        Archiv, das sich nicht mehr öffnen lässt. Deshalb erst
        vollständig danebenschreiben, dann umbenennen: Das ist auf jedem
        gängigen Dateisystem unteilbar.
        """
        ziel = self.root / ARCHIVE_FILE
        neben = ziel.with_suffix(".json.neu")
        neben.write_text(
            json.dumps(self.meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        neben.replace(ziel)

    def close(self) -> None:
        try:
            self.journal.close()
            self.index.close()
        finally:
            self._release_lock()

    def __enter__(self) -> Archive:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class RetentionLocked(RuntimeError):
    """Die Mail darf wegen einer laufenden Aufbewahrungsfrist noch nicht weg."""


def _ohne_pruefwerte(daten: dict) -> dict:
    """Dieselben Angaben, aber ohne die Prüfwerte der Passwörter.

    Für das Journal. Was dort einmal steht, steht dort für immer – ein
    Prüfwert, der sich als angreifbar herausstellt, ließe sich später
    nicht mehr entfernen, ohne die Hash-Kette zu zerreißen.
    """
    return {
        **daten,
        "benutzer": [
            {schluessel: wert for schluessel, wert in eintrag.items()
             if schluessel != "pruefwert"}
            for eintrag in daten.get("benutzer", [])
        ],
    }
