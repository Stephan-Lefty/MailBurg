"""Das Journal – fortgeschriebenes Protokoll mit Hash-Kette.

Das Journal ist die Wahrheit des Archivs. Die Maildateien unter ``mail/``
sind nur Nutzlast; welche Mail wann aus welchem Postfach kam, welcher Ordner
sie enthielt und was später mit ihr geschah, steht ausschließlich hier. Aus
``mail/`` plus ``meta/`` lässt sich der Suchindex jederzeit vollständig neu
bauen – der Index ist deshalb entbehrlich, das Journal nicht.

**Hash-Kette.** Jeder Eintrag trägt in ``prev`` den Hash seines Vorgängers
und in ``self`` seinen eigenen. Wer einen Eintrag nachträglich ändert oder
herausschneidet, zerreißt die Kette an dieser Stelle sichtbar. Das ist der
technische Kern dessen, was die GoBD unter Unveränderbarkeit verstehen, und
es kostet fast nichts.

**Grabsteine statt Löschen.** Eine Mail zu entfernen heißt, einen
``delete``-Eintrag zu schreiben und die Datei zu löschen. Der Vorgang selbst
bleibt damit nachweisbar: wer, wann, aus welchem Grund. So lassen sich das
Recht auf Löschung nach Art. 17 DSGVO und die Unveränderbarkeit gleichzeitig
erfüllen – man löscht den Inhalt, nicht die Tatsache.

**Dateien.** Geschrieben wird immer in die jüngste ``.jsonl``-Datei. Wird sie
zu groß, schließt sie das Journal ab, packt sie und fängt eine neue an.
Abgeschlossene Dateien ändern sich nie wieder, was Nextcloud sehr entgegen
kommt.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Der Vorgänger des allerersten Eintrags. Es gibt keinen, also Nullen.
GENESIS_PREV = "0" * 64

#: Ab dieser Größe der offenen Journaldatei fangen wir eine neue an.
ROLL_SIZE = 8 * 1024 * 1024

_SEGMENT_RE = re.compile(r"^(\d{6})\.jsonl(\.zst|\.xz)?$")

#: Vorgänge, die im Journal vorkommen dürfen.
#:
#: ``create``    Archiv angelegt (immer der erste Eintrag)
#: ``add``       Mail aufgenommen
#: ``delete``    Mail entfernt – Grabstein, siehe Modulbeschreibung
#: ``classify``  Aufbewahrungskategorie einer Mail gesetzt oder geändert
#: ``seal``      Siegel über den bisherigen Stand, optional mit Zeitstempel
#: ``note``      Protokollnotiz, etwa eine geänderte Einstellung
OPERATIONS = frozenset({"create", "add", "delete", "classify", "seal", "note"})


def canonical(entry: dict[str, Any]) -> bytes:
    """Serialisiert einen Eintrag eindeutig und wiederholbar.

    Zwei Rechner müssen für denselben Eintrag Byte für Byte dasselbe
    erzeugen, sonst stimmen die Hashes nicht überein. Sortierte Schlüssel,
    keine Leerzeichen, UTF-8 ohne Ausweichen auf ``\\uXXXX``.
    """
    return json.dumps(
        entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def entry_hash(entry: dict[str, Any]) -> str:
    """Berechnet den Hash eines Eintrags – ohne dessen eigenes ``self``-Feld."""
    without_self = {k: v for k, v in entry.items() if k != "self"}
    return hashlib.sha256(canonical(without_self)).hexdigest()


@dataclass(frozen=True)
class ChainError:
    """Eine Fundstelle, an der die Kette nicht stimmt."""

    seq: int
    segment: str
    problem: str

    def __str__(self) -> str:
        return f"Eintrag {self.seq} in {self.segment}: {self.problem}"


@dataclass(frozen=True)
class VerifyResult:
    """Ergebnis einer Kettenprüfung."""

    entries: int
    errors: tuple[ChainError, ...]
    last_hash: str

    @property
    def ok(self) -> bool:
        return not self.errors


class Journal:
    """Liest und schreibt das Protokoll eines Archivs.

    Nicht nebenläufigkeitssicher. Das Archiv selbst hält eine Sperre, solange
    es geöffnet ist – siehe :mod:`mailburg.core.archive`.
    """

    def __init__(self, meta_dir: Path) -> None:
        self.meta_dir = meta_dir
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self._last_seq = 0
        self._last_hash = GENESIS_PREV
        self._dirty = False
        self._scan_tail()

    # ---------------------------------------------------------------- Lesen

    def segments(self) -> list[Path]:
        """Alle Journaldateien in ihrer Reihenfolge."""
        found = []
        for path in self.meta_dir.iterdir():
            match = _SEGMENT_RE.match(path.name)
            if match:
                found.append((int(match.group(1)), path))
        return [path for _, path in sorted(found)]

    def _read_segment(self, path: Path) -> Iterator[dict[str, Any]]:
        """Gibt die Einträge einer Journaldatei aus, gepackt oder nicht."""
        from mailburg.core import compress

        raw = path.read_bytes()
        for suffix in compress.KNOWN_SUFFIXES:
            if path.name.endswith(suffix):
                raw = compress.decompress(raw, suffix)
                break
        for line in raw.decode("utf-8").splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)

    def read_all(self) -> Iterator[dict[str, Any]]:
        """Gibt sämtliche Einträge des Journals der Reihe nach aus."""
        for segment in self.segments():
            yield from self._read_segment(segment)

    def _scan_tail(self) -> None:
        """Ermittelt beim Öffnen die letzte Folgenummer und den letzten Hash.

        Ein Absturz mitten im Schreiben kann eine angefangene letzte Zeile
        hinterlassen. Die überspringen wir hier stillschweigend – der Eintrag
        war nie vollständig, gilt also als nicht geschrieben. Beim Prüfen der
        Kette fällt so etwas trotzdem auf, weil dort jede Zeile gelesen wird.
        """
        segments = self.segments()
        if not segments:
            return
        for entry in self._read_segment(segments[-1]):
            self._last_seq = entry.get("seq", self._last_seq)
            self._last_hash = entry.get("self", self._last_hash)

    # -------------------------------------------------------------- Schreiben

    def _open_segment(self) -> Path:
        """Liefert die Datei, in die gerade geschrieben wird."""
        open_files = [p for p in self.segments() if p.suffix == ".jsonl"]
        if open_files:
            current = open_files[-1]
            if current.stat().st_size < ROLL_SIZE:
                return current
            self._close_segment(current)
        numbers = [int(_SEGMENT_RE.match(p.name).group(1)) for p in self.segments()]
        return self.meta_dir / f"{max(numbers, default=0) + 1:06d}.jsonl"

    def _close_segment(self, path: Path) -> None:
        """Packt eine volle Journaldatei; danach ändert sie sich nie wieder."""
        from mailburg.core import compress

        payload, suffix = compress.compress(path.read_bytes())
        packed = path.with_name(path.name + suffix)
        # Erst vollständig danebenschreiben, dann an den Platz rücken, dann
        # das Original entfernen. Bricht der Strom mittendrin ab, ist immer
        # noch eine der beiden Fassungen vollständig da.
        temporary = packed.with_name(packed.name + ".neu")
        temporary.write_bytes(payload)
        os.replace(temporary, packed)
        path.unlink()

    def append(self, op: str, **fields: Any) -> dict[str, Any]:
        """Hängt einen Eintrag an und schließt ihn an die Kette an.

        Gibt den vollständigen Eintrag zurück, samt ``seq``, ``ts``, ``prev``
        und ``self``.
        """
        if op not in OPERATIONS:
            raise ValueError(f"Unbekannter Vorgang: {op!r}")

        entry: dict[str, Any] = {
            "seq": self._last_seq + 1,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "op": op,
            "prev": self._last_hash,
            **fields,
        }
        entry["self"] = entry_hash(entry)

        target = self._open_segment()
        with target.open("ab") as handle:
            handle.write(canonical(entry) + b"\n")

        self._last_seq = entry["seq"]
        self._last_hash = entry["self"]
        self._dirty = True
        return entry

    def flush(self) -> None:
        """Zwingt das Betriebssystem, das Journal wirklich auf die Platte zu schreiben.

        Wir rufen das nicht nach jedem Eintrag auf – bei hunderttausend Mails
        am Stück wäre das der Flaschenhals. Stattdessen am Ende eines
        Durchlaufs und vor jedem Siegel.
        """
        if not self._dirty:
            return
        open_files = [p for p in self.segments() if p.suffix == ".jsonl"]
        if open_files:
            # Zum Anhängen geöffnet, obwohl nichts angehängt wird: Windows
            # verweigert fsync auf einem nur lesend geöffneten Deskriptor mit
            # »Bad file descriptor«, POSIX erlaubt es. Schreibrecht ist die
            # einzige Fassung, die auf beiden Seiten funktioniert – und weil
            # schon das Anlegen eines Archivs hier vorbeikommt, war unter
            # Windows sonst kein einziger Durchlauf möglich.
            with open(open_files[-1], "ab") as handle:
                os.fsync(handle.fileno())
        self._dirty = False

    # ---------------------------------------------------------------- Prüfen

    def verify(self) -> VerifyResult:
        """Läuft die gesamte Kette ab und meldet jede Bruchstelle.

        Geprüft wird dreierlei: dass der Eigenhash eines Eintrags zu seinem
        Inhalt passt, dass sein ``prev`` auf den Vorgänger zeigt, und dass die
        Folgenummern lückenlos aufsteigen. Zusammen schließt das sowohl
        Änderungen an einzelnen Einträgen als auch das Entfernen ganzer
        Abschnitte aus.
        """
        errors: list[ChainError] = []
        expected_prev = GENESIS_PREV
        expected_seq = 1
        count = 0
        last_hash = GENESIS_PREV

        for segment in self.segments():
            try:
                entries = list(self._read_segment(segment))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                errors.append(ChainError(expected_seq, segment.name, f"unlesbar: {exc}"))
                continue

            for entry in entries:
                count += 1
                seq = entry.get("seq", -1)

                if entry.get("self") != entry_hash(entry):
                    errors.append(
                        ChainError(seq, segment.name, "Inhalt passt nicht zum Eigenhash")
                    )
                if entry.get("prev") != expected_prev:
                    errors.append(
                        ChainError(seq, segment.name, "Kette gerissen: prev zeigt ins Leere")
                    )
                if seq != expected_seq:
                    errors.append(
                        ChainError(seq, segment.name, f"Folgenummer erwartet: {expected_seq}")
                    )

                expected_prev = entry.get("self", "")
                last_hash = expected_prev
                expected_seq = seq + 1

        return VerifyResult(entries=count, errors=tuple(errors), last_hash=last_hash)

    # -------------------------------------------------------------- Zustand

    @property
    def last_hash(self) -> str:
        """Hash des jüngsten Eintrags – der Stand, den ein Siegel festhält."""
        return self._last_hash

    @property
    def count(self) -> int:
        """Anzahl der bisher geschriebenen Einträge."""
        return self._last_seq

    def close(self) -> None:
        self.flush()
