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
            host = held.get("host", "unbekannt")
            since = held.get("since", "unbekannt")
            raise ArchiveLocked(
                f"Das Archiv ist seit {since} auf '{host}' geöffnet.\n"
                f"Ist das ein Überbleibsel eines Absturzes, kann die Datei "
                f"{lock} von Hand gelöscht werden."
            ) from None
        with os.fdopen(fd, "w") as handle:
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
        return AddResult(
            hash=result.hash, bucket=result.bucket, stored=result.stored, indexed=indexed
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
