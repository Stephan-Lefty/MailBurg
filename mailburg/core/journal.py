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

**Mit Schlüssel wird jede Zeile einzeln verschlüsselt.** Nicht die Datei
als Ganzes: Angehängt wird laufend, und eine Datei, die bei jedem Eintrag
komplett neu verschlüsselt werden müsste, wäre bei 700.000 Mails
unbenutzbar.

Die Hash-Kette bleibt davon unberührt. Sie rechnet über den Klartext des
Eintrags, genau wie vorher – ``verify()`` funktioniert also unverändert,
sobald der Schlüssel da ist. Das Verschlüsseln kommt erst danach, beim
Hinschreiben. Und weil AES-GCM jede Zeile mit einer Prüfsumme versieht,
fällt eine veränderte Journaldatei jetzt doppelt auf.

**Das Journal ist nicht Beiwerk, sondern die Wahrheit** – deshalb gehört
es mit unter die Verschlüsselung. In ihm stehen Absender, Betreff,
Postfach und Ordner jeder Mail. Ein verschlüsseltes ``mail/`` neben
einem lesbaren ``meta/`` wäre ein verschlossener Schrank mit einem
Inhaltsverzeichnis an der Tür.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from base64 import b64decode, b64encode
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
#: Die zulässigen Vorgänge. Eine geschlossene Liste, damit ein
#: Tippfehler nicht stillschweigend eine neue Vorgangsart erfindet, nach
#: der später niemand sucht.
#:
#: ``rules`` kam am 2026-08-30 dazu: Welche Einstufungsregeln wann
#: galten, gehört zur Verfahrensdokumentation. Wer erklären muss, warum
#: eine Mail nicht der Aufbewahrung unterlag, zeigt auf diesen Eintrag –
#: und er hängt in der Hash-Kette, lässt sich also nicht nachträglich
#: glattziehen.
#: ``kette`` ist der jüngste Vorgang und der ungewöhnlichste: ein
#: Vermerk über eine Bruchstelle in der Kette selbst.
#:
#: **Er heilt nichts.** Die Kette bleibt gerissen, und die Prüfung sagt
#: das weiterhin – nur nennt sie die Stelle dann als *erklärt* statt als
#: unbekannt. Das ist der einzige vertretbare Umgang damit: Eine
#: gerissene Kette glattzuziehen wäre genau das, was sie verhindern
#: soll, und ein Befund, der ungeklärt stehen bleibt, wird nach der
#: dritten Prüfung überlesen.
#:
#: Der Vermerk hängt selbst in der Kette, mit Zeitpunkt und Urheber.
#: Wer ihn schreibt, dokumentiert – er verwischt nicht.
OPERATIONS = frozenset({
    "create", "add", "delete", "classify", "seal", "note", "rules",
    "users", "kette",
})


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


class JournalBeschaedigt(RuntimeError):
    """Das Protokoll lässt sich nicht einmal mehr lesen.

    Nicht zu verwechseln mit einer gerissenen Kette: Die meldet
    :meth:`Journal.verify` als Befund, und das Archiv bleibt benutzbar.
    Hier geht schon das Öffnen nicht – und dann ist eine verständliche
    Ansage nötig, kein Traceback über eine JSON-Zeile.
    """


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

    bekannt: tuple[ChainError, ...] = ()
    """Bruchstellen, zu denen ein Vermerk in der Kette steht.

    **Sie sind nicht weg, sie sind erklärt.** Jeder Aufrufer, der
    Befunde anzeigt, muss auch diese nennen – sonst verschwindet eine
    gerissene Kette aus der Wahrnehmung, und das wäre schlimmer als ein
    Befund, den man stehen lässt.
    """

    @property
    def ok(self) -> bool:
        """Ob es *unerklärte* Bruchstellen gibt.

        Vermerkte zählen hier nicht mit. Andernfalls bliebe die Prüfung
        für immer rot, und eine Meldung, die immer rot ist, sagt nichts
        mehr – auch nicht, wenn morgen etwas Echtes dazukommt.
        """
        return not self.errors


class Journal:
    """Liest und schreibt das Protokoll eines Archivs.

    Nicht nebenläufigkeitssicher. Das Archiv selbst hält eine Sperre, solange
    es geöffnet ist – siehe :mod:`mailburg.core.archive`.
    """

    def __init__(self, meta_dir: Path, schluessel=None) -> None:
        self.meta_dir = meta_dir
        self.schluessel = schluessel
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self._last_seq = 0
        self._last_hash = GENESIS_PREV
        self._dirty = False
        #: Name und Größe der offenen Datei, als dieser Zugriff den Stand
        #: zuletzt gelesen hat. Daran erkennt er, dass inzwischen jemand
        #: anders geschrieben hat – siehe :meth:`_fremdes_schreiben`.
        self._gesehen: tuple[str, int] = ("", 0)
        self._scan_tail()
        self._stand_merken()

    # ------------------------------------------------- Stand zweier Schreiber

    def _stand_merken(self) -> None:
        """Hält fest, wie die offene Datei gerade aussieht."""
        offen = [p for p in self.segments() if p.suffix == ".jsonl"]
        if not offen:
            self._gesehen = ("", 0)
            return
        self._gesehen = (offen[-1].name, offen[-1].stat().st_size)

    def _fremdes_schreiben(self) -> bool:
        """Ob seit dem letzten Blick jemand anders angehängt hat.

        **Verglichen werden Name und Größe, nicht der Inhalt.** Ein
        ``stat()`` kostet nichts; das Journal noch einmal zu lesen
        dagegen schon – und genau das wäre bei hunderttausend Mails am
        Stück der Flaschenhals, vor dem :meth:`flush` ausdrücklich
        warnt. Schreibt nur dieser Prozess, stimmt die gemerkte Größe
        immer, und es wird nie nachgelesen.
        """
        offen = [p for p in self.segments() if p.suffix == ".jsonl"]
        if not offen:
            return self._gesehen != ("", 0)
        return self._gesehen != (offen[-1].name, offen[-1].stat().st_size)

    # --------------------------------------------------------- Eine Zeile

    def _zeile_schreiben(self, entry: dict[str, Any]) -> bytes:
        """Aus einem Eintrag wird die Zeile, die in der Datei landet."""
        klartext = canonical(entry)
        if self.schluessel is None:
            return klartext
        return b64encode(self.schluessel.verschluesseln(klartext))

    def _zeile_lesen(self, zeile: bytes) -> dict[str, Any]:
        """Und zurück. Wirft dieselben Fehler wie vorher ``json.loads``.

        **Ein falscher Schlüssel muss wie eine kaputte Datei aussehen**,
        jedenfalls für die Kettenprüfung: Sie fängt ``JSONDecodeError``
        und ``UnicodeDecodeError``, und wenn hier etwas anderes flöge,
        bräche ``verify()`` mit einem Traceback ab, statt die Stelle zu
        melden. Wer sich am Passwort vertippt hat, erfährt das ohnehin
        schon beim Öffnen des Archivs.
        """
        if self.schluessel is None:
            return json.loads(zeile)
        from mailburg.core.krypto import KryptoFehler

        try:
            klartext = self.schluessel.entschluesseln(b64decode(zeile))
        except (KryptoFehler, ValueError, TypeError) as fehler:
            raise json.JSONDecodeError(
                f"Zeile nicht entschlüsselbar: {fehler}", "", 0
            ) from fehler
        return json.loads(klartext)

    # ---------------------------------------------------------------- Lesen

    def segments(self) -> list[Path]:
        """Alle Journaldateien in ihrer Reihenfolge."""
        found = []
        for path in self.meta_dir.iterdir():
            match = _SEGMENT_RE.match(path.name)
            if match:
                found.append((int(match.group(1)), path))
        return [path for _, path in sorted(found)]

    def _rohzeilen(self, path: Path) -> list[bytes]:
        """Die nicht leeren Zeilen einer Journaldatei, gepackt oder nicht."""
        from mailburg.core import compress

        raw = path.read_bytes()
        for suffix in compress.KNOWN_SUFFIXES:
            if path.name.endswith(suffix):
                raw = compress.decompress(raw, suffix)
                break
        return [zeile.strip() for zeile in raw.splitlines() if zeile.strip()]

    def _read_segment(self, path: Path) -> Iterator[dict[str, Any]]:
        """Gibt die Einträge einer Journaldatei aus, gepackt oder nicht."""
        for zeile in self._rohzeilen(path):
            yield self._zeile_lesen(zeile)

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

        **Nur die letzte.** Bis zum 2026-08-31 stand das zwar so im Text,
        im Code aber nicht: Eine unvollständige Zeile ließ ``json.loads``
        werfen, und das Archiv war überhaupt nicht mehr zu öffnen – nach
        einem Stromausfall mitten im Abruf. Aufgefallen ist es erst beim
        verschlüsselten Journal, weil dort jede veränderte Zeile
        unlesbar wird.

        Die Toleranz gilt bewusst nur der letzten Zeile. Ein Absturz kann
        keine frühere zerstören; ist dort etwas kaputt, hat es einen
        anderen Grund, und dann soll es krachen statt still zu
        überspringen. Denn was hier übersprungen wird, zählt beim
        Fortschreiben nicht mehr mit – und eine Folgenummer, die
        zurückspringt, zerreißt die Kette dauerhaft.
        """
        segments = self.segments()
        if not segments:
            return
        zeilen = self._rohzeilen(segments[-1])
        gut: list[bytes] = []
        for nummer, zeile in enumerate(zeilen, 1):
            try:
                entry = self._zeile_lesen(zeile)
            except (json.JSONDecodeError, UnicodeDecodeError) as fehler:
                if nummer == len(zeilen):
                    self._rest_abschneiden(segments[-1], gut)
                    break
                raise JournalBeschaedigt(
                    f"Zeile {nummer} von {len(zeilen)} in "
                    f"{segments[-1].name} lässt sich nicht lesen.\n\n"
                    f"Das kann kein abgebrochener Schreibvorgang sein – "
                    f"der träfe nur die letzte Zeile. Entweder wurde die "
                    f"Datei verändert, oder der Datenträger hat einen "
                    f"Fehler.\n\n"
                    f"Ihre Mails liegen davon unberührt in mail/. Holen "
                    f"Sie meta/ aus einer Sicherung zurück und prüfen Sie "
                    f"anschließend mit »mailburg pruefen«.\n\n"
                    f"Im Einzelnen: {fehler}"
                ) from fehler
            gut.append(zeile)
            self._last_seq = entry.get("seq", self._last_seq)
            self._last_hash = entry.get("self", self._last_hash)

    def _rest_abschneiden(self, segment: Path, gut: list[bytes]) -> None:
        """Entfernt die angefangene letzte Zeile aus der offenen Datei.

        **Ohne das wäre die Nachsicht von oben eine Falle.** Eine
        abgebrochene Zeile endet nicht auf einem Zeilenumbruch – der kam
        ja nicht mehr dazu. Der nächste Eintrag würde direkt an sie
        angehängt und verschmölze mit ihr zu einer einzigen unlesbaren
        Zeile. Aus einem verlorenen Eintrag würden zwei, und der zweite
        wäre einer, den MailBurg gerade für geschrieben hält.

        Angefasst wird nur die *offene* Datei. Ein gepacktes Segment ist
        abgeschlossen und ändert sich nie wieder; steht dort etwas nicht
        recht, gehört das gemeldet und nicht stillschweigend begradigt.
        """
        if segment.suffix != ".jsonl":
            return
        segment.write_bytes(b"".join(zeile + b"\n" for zeile in gut))

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

        # **Erst nachsehen, ob der eigene Stand noch gilt.**
        #
        # Gezählt wird von dem, was *dieser* Zugriff beim Öffnen gelesen
        # hat. Wer das Archiv lange offen hält – das Hauptfenster –
        # bekommt davon nichts mit, wenn nebenher ein Abruf schreibt.
        #
        # **Am 2026-09-21 an einem echten Geschäftsarchiv gefunden.** Am
        # 12.09. um 07:57 schrieb der Zeitplan in einem eigenen Prozess
        # die Nummern 488 bis 493; eine halbe Minute später stufte
        # jemand im offenen Fenster sechs Mails ein – und das Fenster
        # zählte ab 488 noch einmal. Die Hash-Kette war damit gerissen,
        # ohne dass eine einzige Mail fehlte.
        #
        # Die Sperrdatei hilft hier nicht: Sie verhindert zwei
        # *schreibend* geöffnete Archive. Das Fenster öffnet lesend und
        # schreibt trotzdem, sobald jemand einstuft, löscht oder Regeln
        # anwendet.
        if self._fremdes_schreiben():
            self._scan_tail()
            self._stand_merken()

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
            handle.write(self._zeile_schreiben(entry) + b"\n")

        self._last_seq = entry["seq"]
        self._last_hash = entry["self"]
        self._stand_merken()
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

        **Vermerkte Stellen werden getrennt ausgewiesen.** Steht zu
        einer Bruchstelle ein ``kette``-Eintrag im Journal, wandert der
        Befund nach :attr:`VerifyResult.bekannt` statt nach ``errors``.
        Verschwiegen wird er nicht – siehe die Begründung dort.
        """
        vermerkt = self._vermerkte_stellen()
        errors: list[ChainError] = []
        bekannt: list[ChainError] = []
        expected_prev = GENESIS_PREV
        expected_seq = 1
        count = 0
        last_hash = GENESIS_PREV

        def melden(fund: ChainError) -> None:
            # **Ein Vermerk erklärt einen Bruch, nie eine Veränderung.**
            #
            # Dass die Kette an einer Stelle nicht aufgeht, kann ein
            # Betriebsunfall sein – zwei Zugriffe, die gleichzeitig
            # schreiben. Dass der Inhalt eines Eintrags nicht mehr zu
            # seinem Eigenhash passt, kann das nicht: Dort hat jemand
            # etwas geändert.
            #
            # Ließe sich auch das vermerken, wäre der Vermerk genau das
            # Werkzeug, vor dem die Hash-Kette schützen soll. Deshalb
            # geht ein Eigenhash-Befund immer in ``errors``, auch wenn
            # für die Stelle ein Vermerk vorliegt.
            erklaerbar = "Eigenhash" not in fund.problem
            if erklaerbar and (fund.segment, fund.seq) in vermerkt:
                bekannt.append(fund)
            else:
                errors.append(fund)

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
                    melden(
                        ChainError(seq, segment.name, "Inhalt passt nicht zum Eigenhash")
                    )
                if entry.get("prev") != expected_prev:
                    melden(
                        ChainError(seq, segment.name, "Kette gerissen: prev zeigt ins Leere")
                    )
                if seq != expected_seq:
                    melden(
                        ChainError(seq, segment.name, f"Folgenummer erwartet: {expected_seq}")
                    )

                expected_prev = entry.get("self", "")
                last_hash = expected_prev
                expected_seq = seq + 1

        return VerifyResult(
            entries=count,
            errors=tuple(errors),
            last_hash=last_hash,
            bekannt=tuple(bekannt),
        )

    def _vermerkte_stellen(self) -> set[tuple[str, int]]:
        """Welche Bruchstellen einen Vermerk in der Kette haben.

        **Nur was ausdrücklich benannt ist.** Ein Vermerk gilt für genau
        ein Segment und genau eine Folgenummer – nicht für »alles
        davor«. Sonst entschuldigte ein einziger Eintrag rückwirkend
        jede Veränderung, und die Prüfung wäre wertlos.

        Unlesbare Segmente werden hier übergangen: Sie melden sich in
        :meth:`verify` selbst, und ein Vermerk, den niemand lesen kann,
        ist keiner.
        """
        gefunden: set[tuple[str, int]] = set()
        for segment in self.segments():
            try:
                entries = list(self._read_segment(segment))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            for entry in entries:
                if entry.get("op") != "kette":
                    continue
                stelle = entry.get("stelle")
                nummer = entry.get("nummer")
                if isinstance(stelle, str) and isinstance(nummer, int):
                    gefunden.add((stelle, nummer))
        return gefunden

    def vermerk_kette(self, stelle: str, nummer: int, grund: str,
                      actor: str = "") -> dict[str, Any]:
        """Hält fest, dass an dieser Stelle ein bekannter Bruch liegt.

        **Die Kette wird dabei nicht angefasst.** Der Vermerk hängt sich
        hinten an und erklärt, was weiter vorn steht – mit Zeitpunkt,
        Urheber und Begründung, und selbst gegen Veränderung gesichert,
        weil er Teil derselben Kette ist.

        Wer das benutzt, muss wissen: Eine spätere Prüfung sieht
        weiterhin den Bruch *und* den Vermerk. Das ist der Zweck. Wer
        eine saubere Kette braucht, legt ein neues Archiv an und spielt
        den Bestand hinein.
        """
        if not grund.strip():
            raise ValueError(
                "Ein Vermerk ohne Begründung wäre wertlos – er soll ja "
                "gerade erklären, was an der Stelle geschehen ist."
            )
        return self.append(
            "kette", stelle=stelle, nummer=int(nummer),
            grund=grund.strip(), actor=actor,
        )

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
