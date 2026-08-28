"""Der Suchindex.

Eine SQLite-Datenbank mit FTS5. Sie liegt bewusst **nicht** im Archiv,
sondern im Anwendungsverzeichnis des jeweiligen Rechners. Zwei Gründe:

1. SQLite auf einem synchronisierten Netzlaufwerk geht früher oder später
   kaputt. Die Sperren, auf die sich die Datenbank verlässt, funktionieren
   über Nextcloud oder SMB schlicht nicht. Das ist der häufigste Weg, wie
   sich Leute ihr Archiv zerschießen.
2. Der Index ist ohnehin entbehrlich – aus ``mail/`` und ``meta/`` lässt er
   sich jederzeit vollständig neu erzeugen. Was wegwerfbar ist, gehört nicht
   in den Datenbestand, der gesichert werden muss.

**Zwei Indizes, mit Absicht.** Der Haupt-Index zerlegt in Wörter und kann
Präfixe – ``rechn*`` findet ``Rechnung``. Was er nicht kann: mitten in ein
Wort greifen. Genau das braucht man im Deutschen aber ständig, weil wir
zusammenschreiben: Wer ``rechnung`` sucht, will auch ``Schlussrechnung``
und ``Rechnungskorrektur`` finden. Dafür gibt es den zweiten Index mit
Dreizeichengruppen.

Der läuft allerdings nur über **Betreff, Absender, Empfänger und
Anhangsnamen** – kurze Felder. Ihn auch über den Fließtext zu legen, würde
den Index bei einem großen Archiv um etliche Gigabyte aufblähen, ohne dass
der Gewinn dafürsteht.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

#: Schemafassung. Steigt sie, wird der Index verworfen und neu gebaut –
#: was gefahrlos ist, weil er sich vollständig aus dem Archiv ergibt.
SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY,
    hash            TEXT    NOT NULL UNIQUE,
    bucket          TEXT    NOT NULL,
    date            TEXT,
    year            INTEGER,
    from_addr       TEXT,
    from_name       TEXT,
    subject         TEXT,
    size            INTEGER NOT NULL DEFAULT 0,
    has_attachments INTEGER NOT NULL DEFAULT 0,
    category        TEXT    NOT NULL DEFAULT 'unbestimmt',
    message_id      TEXT,
    -- Wann die Mail ins Archiv kam, nicht wann sie geschrieben wurde.
    -- "Was ist diese Woche hereingekommen?" ist die Frage nach jedem
    -- Abruf - und für eine Verfahrensdokumentation gehört sie
    -- beantwortbar. Steht im Journal, hier für die Suche.
    archiviert      TEXT,
    -- hoch, normal oder niedrig; aus Importance, X-Priority oder Priority.
    wichtigkeit     TEXT NOT NULL DEFAULT 'normal'
);

CREATE INDEX IF NOT EXISTS idx_messages_date  ON messages(date);
CREATE INDEX IF NOT EXISTS idx_messages_year  ON messages(year);
CREATE INDEX IF NOT EXISTS idx_messages_from  ON messages(from_addr);
CREATE INDEX IF NOT EXISTS idx_messages_msgid ON messages(message_id);
CREATE INDEX IF NOT EXISTS idx_messages_arch  ON messages(archiviert);

-- Empfänger einzeln, nach Art getrennt. Der Volltextindex wirft An und
-- Kopie in ein Feld; wer wissen will, ob er direkt angeschrieben war oder
-- nur im Verteiler stand, kann das dort nicht unterscheiden.
CREATE TABLE IF NOT EXISTS recipients (
    msg_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    addr   TEXT    NOT NULL,
    art    TEXT    NOT NULL          -- to, cc oder bcc
);

CREATE INDEX IF NOT EXISTS idx_recipients_msg  ON recipients(msg_id);
CREATE INDEX IF NOT EXISTS idx_recipients_addr ON recipients(addr, art);

-- Wo dieselbe Mail überall lag. Eine Mail kann in mehreren Konten und
-- Ordnern stecken, deshalb eine eigene Tabelle statt Spalten in messages.
CREATE TABLE IF NOT EXISTS locations (
    id         INTEGER PRIMARY KEY,
    msg_id     INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    account    TEXT    NOT NULL,
    folder     TEXT    NOT NULL,
    uid        INTEGER,
    flags      TEXT,
    UNIQUE(msg_id, account, folder)
);

CREATE INDEX IF NOT EXISTS idx_locations_account ON locations(account, folder);

CREATE TABLE IF NOT EXISTS attachments (
    id        INTEGER PRIMARY KEY,
    msg_id    INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    filename  TEXT    NOT NULL,
    extension TEXT,
    mime_type TEXT,
    size      INTEGER NOT NULL DEFAULT 0,
    -- Wie viele Zeichen Text aus diesem Anhang kamen. -1 heißt: nicht
    -- nachgesehen (so stehen alte Indizes da). Ein umfangreiches PDF mit 0
    -- ist ein Scan und braucht Texterkennung.
    text_zeichen INTEGER NOT NULL DEFAULT -1,
    -- Gehört zur Darstellung statt zur Sendung: Signaturlogos und
    -- Ähnliches. Wird archiviert, gilt aber nicht als Anhang.
    inline INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_attachments_msg ON attachments(msg_id);
CREATE INDEX IF NOT EXISTS idx_attachments_ext ON attachments(extension);

-- Volltext über alles. Der Inhalt wird hier mitgespeichert, nicht nur der
-- Index: nur so liefert snippet() Fundstellen mit Umgebung, und der Platz
-- ist verschmerzbar, weil diese Datei jederzeit neu entstehen kann.
CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(
    subject,
    sender,
    recipients,
    body,
    attachment_names,
    attachment_text,
    tokenize = "unicode61 remove_diacritics 2",
    prefix = '2 3 4'
);

-- Dreizeichengruppen für die Suche mitten im Wort. Nur kurze Felder,
-- siehe Modulbeschreibung.
-- remove_diacritics, damit "muller" auch "Müller" findet. Wer den Umlaut
-- auf der Tastatur nicht trifft oder ihn aus einer fremden Quelle kopiert
-- hat, soll trotzdem etwas finden. Die Umschreibung "mueller" deckt das
-- allerdings nicht ab – das kann SQLite nicht, das müsste die Suchanfrage
-- selbst auffächern.
CREATE VIRTUAL TABLE IF NOT EXISTS search_tri USING fts5(
    subject,
    sender,
    recipients,
    attachment_names,
    tokenize = 'trigram remove_diacritics 1'
);
"""


@dataclass(frozen=True)
class Hit:
    """Ein Suchtreffer."""

    hash: str
    bucket: str
    subject: str
    from_addr: str
    from_name: str
    date: str | None
    size: int
    has_attachments: bool
    snippet: str = ""

    category: str = "unbestimmt"
    """Wozu die Mail aufbewahrungsrechtlich zählt.

    Mitgeführt, damit ein Aufrufer nicht für jeden Treffer einzeln
    nachfragen muss – »was ist hier noch nicht eingestuft?« ist die
    häufigste Frage an eine Trefferliste in einem Geschäftsarchiv.
    """

    @property
    def sender_display(self) -> str:
        """Absender so, wie man ihn einer Liste zeigt."""
        return f"{self.from_name} <{self.from_addr}>" if self.from_name else self.from_addr


class Index:
    """Der Suchindex eines Archivs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self._configure()
        self._ensure_schema()

    def _configure(self) -> None:
        # WAL macht Lesen und Schreiben gleichzeitig möglich – die
        # Oberfläche kann also suchen, während im Hintergrund archiviert
        # wird. Zulässig nur, weil diese Datei lokal liegt.
        self.db.execute("PRAGMA journal_mode = WAL")
        # NORMAL statt FULL: Bei einem Stromausfall verlieren wir
        # schlimmstenfalls die letzten Indexeinträge. Das Archiv selbst ist
        # davon nicht betroffen, und der Index lässt sich neu bauen.
        self.db.execute("PRAGMA synchronous = NORMAL")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA temp_store = MEMORY")
        self.db.execute("PRAGMA cache_size = -64000")  # 64 MB

    def _ensure_schema(self) -> None:
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version and version != SCHEMA_VERSION:
            raise IndexOutdated(
                f"Der Suchindex stammt aus Fassung {version}, gebraucht wird "
                f"{SCHEMA_VERSION}. Er muss neu aufgebaut werden – die Mails "
                f"sind davon nicht betroffen."
            )
        # Erst nachrüsten, dann das Schema anwenden: Zum Schema gehören auch
        # Indizes über die neuen Spalten, und die ließen sich sonst nicht
        # anlegen. Bei einer noch leeren Datenbank tut das Nachrüsten
        # nichts – dort entstehen die Tabellen gleich vollständig.
        self._spalten_ergaenzen()
        self.db.executescript(_SCHEMA)
        self.db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self.db.commit()

    def _spalten_ergaenzen(self) -> None:
        """Rüstet Spalten nach, die es in älteren Indizes noch nicht gab.

        ``CREATE TABLE IF NOT EXISTS`` lässt eine vorhandene Tabelle in
        Ruhe – auch wenn ihr Spalten fehlen. Ohne das Nachrüsten liefe
        jedes Einfügen in einen älteren Index auf einen Fehler, und ein
        gewachsenes Archiv wäre nach einer Programmaktualisierung nicht
        mehr zu benutzen.

        Den Index einfach zu verwerfen wäre die Alternative – er ist ja
        wegwerfbar. Aber sein Neuaufbau dauert bei zehntausend Mails
        Minuten und bei einer halben Million Stunden; dafür sind zwei
        Spalten kein Anlass. Neue Zeilen bekommen den richtigen Wert, alte
        stehen auf dem Vorgabewert, und wer das genauer braucht, baut den
        Index bei Gelegenheit neu.
        """
        nachzuruesten = {
            "attachments": {
                "text_zeichen": "INTEGER NOT NULL DEFAULT -1",
                "inline": "INTEGER NOT NULL DEFAULT 0",
            },
            "messages": {
                "archiviert": "TEXT",
                "wichtigkeit": "TEXT NOT NULL DEFAULT 'normal'",
            },
        }
        for tabelle, spalten in nachzuruesten.items():
            vorhanden = {
                zeile[1]
                for zeile in self.db.execute(f"PRAGMA table_info({tabelle})")
            }
            if not vorhanden:
                # Die Tabelle gibt es noch gar nicht – gleich darauf legt
                # das Schema sie vollständig an. Hier nachrüsten zu wollen
                # hieße, in eine leere Datenbank hineinzuändern.
                continue
            for name, art in spalten.items():
                if name not in vorhanden:
                    self.db.execute(
                        f"ALTER TABLE {tabelle} ADD COLUMN {name} {art}"
                    )

    # --------------------------------------------------------------- Füllen

    def add(
        self,
        *,
        digest: str,
        bucket: str,
        parsed,  # mailburg.extract.message.ParsedMessage
        size: int,
        account: str,
        folder: str,
        uid: int | None = None,
        flags: str = "",
        attachment_text: str = "",
        archiviert: str | None = None,
    ) -> bool:
        """Nimmt eine Mail in den Index auf.

        Gibt ``False`` zurück, wenn sie schon drin war – dann wird nur der
        neue Fundort ergänzt. Das ist der Fall, wenn dieselbe Mail in einem
        zweiten Konto oder Ordner auftaucht.
        """
        existing = self.db.execute(
            "SELECT id FROM messages WHERE hash = ?", (digest,)
        ).fetchone()

        if existing is not None:
            self._add_location(existing["id"], account, folder, uid, flags)
            return False

        cursor = self.db.execute(
            """INSERT INTO messages
               (hash, bucket, date, year, from_addr, from_name, subject,
                size, has_attachments, message_id, archiviert, wichtigkeit)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                digest,
                bucket,
                parsed.date.isoformat() if parsed.date else None,
                parsed.date.year if parsed.date else None,
                parsed.from_addr,
                parsed.from_name,
                parsed.subject,
                size,
                int(parsed.has_attachments),
                parsed.message_id,
                # Ohne Angabe der Zeitpunkt jetzt. Beim Neuaufbau reicht der
                # Aufrufer den Zeitpunkt aus dem Journal nach - sonst stünde
                # dort der Tag des Neuaufbaus, und die Auskunft "wann kam
                # das ins Archiv" wäre falsch.
                archiviert or datetime.now().astimezone().isoformat(timespec="seconds"),
                getattr(parsed, "wichtigkeit", "normal"),
            ),
        )
        msg_id = cursor.lastrowid
        self._add_location(msg_id, account, folder, uid, flags)

        for art, adressen in (
            ("to", parsed.to_addrs),
            ("cc", parsed.cc_addrs),
            ("bcc", getattr(parsed, "bcc_addrs", [])),
        ):
            for adresse in adressen:
                self.db.execute(
                    "INSERT INTO recipients (msg_id, addr, art) VALUES (?, ?, ?)",
                    (msg_id, adresse.lower(), art),
                )

        names = []
        for att in parsed.attachments:
            self.db.execute(
                """INSERT INTO attachments
                       (msg_id, filename, extension, mime_type, size,
                        text_zeichen, inline)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (msg_id, att.filename, att.extension, att.mime_type, att.size,
                 getattr(att, "text_zeichen", -1),
                 int(getattr(att, "inline", False))),
            )
            if getattr(att, "ist_nutzanhang", True):
                names.append(att.filename)

        sender = f"{parsed.from_name} {parsed.from_addr}".strip()
        joined_names = " ".join(names)

        # Beide Volltexttabellen bekommen dieselbe Zeilennummer wie
        # messages, damit sich Treffer ohne Umweg zuordnen lassen.
        self.db.execute(
            """INSERT INTO search
               (rowid, subject, sender, recipients, body, attachment_names, attachment_text)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                msg_id,
                parsed.subject,
                sender,
                parsed.all_recipients,
                parsed.body,
                joined_names,
                attachment_text,
            ),
        )
        self.db.execute(
            """INSERT INTO search_tri (rowid, subject, sender, recipients, attachment_names)
               VALUES (?, ?, ?, ?, ?)""",
            (msg_id, parsed.subject, sender, parsed.all_recipients, joined_names),
        )
        return True

    def has_location(self, digest: str, account: str, folder: str) -> bool:
        """Sagt, ob diese Mail aus diesem Ordner schon aufgenommen wurde.

        Damit beim wiederholten Einlesen derselben Quelle nicht jedes Mal
        ein neuer Journaleintrag entsteht – archiviert wurde sie ja bereits,
        und zwar genau von dort.
        """
        return (
            self.db.execute(
                """SELECT 1 FROM locations l
                   JOIN messages m ON m.id = l.msg_id
                   WHERE m.hash = ? AND l.account = ? AND l.folder = ?""",
                (digest, account, folder),
            ).fetchone()
            is not None
        )

    def _add_location(
        self, msg_id: int, account: str, folder: str, uid: int | None, flags: str
    ) -> None:
        self.db.execute(
            """INSERT OR IGNORE INTO locations (msg_id, account, folder, uid, flags)
               VALUES (?, ?, ?, ?, ?)""",
            (msg_id, account, folder, uid, flags),
        )

    def remove(self, digest: str) -> bool:
        """Wirft eine Mail aus dem Index – etwa nachdem sie gelöscht wurde."""
        row = self.db.execute("SELECT id FROM messages WHERE hash = ?", (digest,)).fetchone()
        if row is None:
            return False
        msg_id = row["id"]
        self.db.execute("DELETE FROM search WHERE rowid = ?", (msg_id,))
        self.db.execute("DELETE FROM search_tri WHERE rowid = ?", (msg_id,))
        self.db.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
        return True

    def set_category(self, digest: str, category: str) -> None:
        """Setzt die Aufbewahrungskategorie einer Mail."""
        self.db.execute(
            "UPDATE messages SET category = ? WHERE hash = ?", (category, digest)
        )

    def commit(self) -> None:
        self.db.commit()

    # --------------------------------------------------------------- Suchen

    #: Wonach sich sortieren lässt, und die Spalte dahinter. Als feste
    #: Zuordnung und nicht als durchgereichter Text: Ein Sortierfeld
    #: landet ungeschützt im SQL, weil es sich nicht als Parameter binden
    #: lässt. Was hier nicht steht, kommt nicht in die Abfrage.
    SORTIERFELDER = {
        "datum": "m.date",
        "absender": "lower(coalesce(nullif(m.from_name, ''), m.from_addr))",
        "betreff": "lower(m.subject)",
        "groesse": "m.size",
        "anhang": "m.has_attachments",
    }

    def search(self, expression: str, limit: int = 200, offset: int = 0,
               sortierung: str = "datum", absteigend: bool = True) -> list[Hit]:
        """Führt eine vorbereitete Suchanfrage aus.

        Erwartet den fertigen SQL-Baustein aus
        :mod:`mailburg.search.query` – hier wird nicht mehr geparst.
        """
        from mailburg.search.query import build

        where, params = build(expression)
        feld = self.SORTIERFELDER.get(sortierung, self.SORTIERFELDER["datum"])
        richtung = "DESC" if absteigend else "ASC"
        # Das Datum als zweiter Schlüssel: Bei gleichem Absender oder
        # gleicher Größe wäre die Reihenfolge sonst beliebig und änderte
        # sich beim Nachladen - die Liste sprünge dem Anwender weg.
        rows = self.db.execute(
            f"""SELECT m.hash, m.bucket, m.subject, m.from_addr, m.from_name,
                       m.date, m.size, m.has_attachments, m.category
                FROM messages m
                WHERE {where}
                ORDER BY {feld} {richtung}, m.date DESC
                LIMIT ? OFFSET ?""",
            (*params, limit, offset),
        ).fetchall()

        return [
            Hit(
                hash=row["hash"],
                bucket=row["bucket"],
                subject=row["subject"] or "(ohne Betreff)",
                from_addr=row["from_addr"] or "",
                from_name=row["from_name"] or "",
                date=row["date"],
                size=row["size"],
                has_attachments=bool(row["has_attachments"]),
                category=row["category"] or "unbestimmt",
            )
            for row in rows
        ]

    def count(self, expression: str = "") -> int:
        """Zählt, wie viele Mails auf eine Anfrage passen."""
        from mailburg.search.query import build

        where, params = build(expression)
        return self.db.execute(
            f"SELECT COUNT(*) FROM messages m WHERE {where}", params
        ).fetchone()[0]

    def known_hashes(self) -> set[str]:
        """Alle Hashes im Index – für den Abgleich mit der Ablage."""
        return {r[0] for r in self.db.execute("SELECT hash FROM messages")}

    def accounts(self) -> list[tuple[str, str, int]]:
        """Konten und Ordner mit ihrer jeweiligen Anzahl – für den Ordnerbaum."""
        return [
            (r["account"], r["folder"], r["n"])
            for r in self.db.execute(
                """SELECT account, folder, COUNT(*) AS n
                   FROM locations GROUP BY account, folder
                   ORDER BY account, folder"""
            )
        ]

    def account_totals(self) -> dict[str, int]:
        """Je Konto, wie viele *Mails* dort liegen – nicht wie viele Fundorte.

        Der Unterschied ist bei Proton beträchtlich: Dort trägt jede Mail
        neben ihrem Ordner noch Etiketten, und jedes Etikett ist ein
        weiterer Fundort. Wer die Fundorte addiert, kommt auf eine Zahl,
        die es nicht gibt – gemessen 2.877 statt der tatsächlichen 2.078.
        """
        return {
            r["account"]: r["n"]
            for r in self.db.execute(
                """SELECT account, COUNT(DISTINCT msg_id) AS n
                   FROM locations GROUP BY account"""
            )
        }

    def max_uid(self, account: str, folder: str) -> int:
        """Die höchste UID, die aus diesem Ordner tatsächlich im Archiv liegt.

        Der Anhaltspunkt für den nächsten IMAP-Abruf. Bewusst aus dem Index
        und nicht aus einer mitgeschriebenen Zahl – siehe
        ``mailburg.core.sync``.
        """
        row = self.db.execute(
            """SELECT MAX(uid) FROM locations WHERE account = ? AND folder = ?""",
            (account, folder),
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def uids_im_ordner(self, account: str, folder: str) -> set[int]:
        """Alle UIDs, die aus diesem Ordner im Archiv liegen.

        Für den Abgleich mit dem Postfach: Was der Server hat und hier
        fehlt, ist noch nicht archiviert – und darf dort nicht gelöscht
        werden.
        """
        return {
            int(zeile[0])
            for zeile in self.db.execute(
                "SELECT uid FROM locations WHERE account = ? AND folder = ? "
                "AND uid IS NOT NULL",
                (account, folder),
            )
        }

    def statistics(self) -> dict[str, int]:
        """Kennzahlen für die Übersicht."""
        one = lambda sql: self.db.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "mails": one("SELECT COUNT(*) FROM messages"),
            "anhaenge": one("SELECT COUNT(*) FROM attachments"),
            "fundorte": one("SELECT COUNT(*) FROM locations"),
            "bytes": one("SELECT COALESCE(SUM(size), 0) FROM messages"),
        }

    def optimize(self) -> None:
        """Verdichtet die Volltextindizes. Lohnt nach einem großen Durchlauf."""
        self.db.execute("INSERT INTO search(search) VALUES('optimize')")
        self.db.execute("INSERT INTO search_tri(search_tri) VALUES('optimize')")
        self.db.commit()
        self.db.execute("ANALYZE")

    def close(self) -> None:
        self.db.commit()
        self.db.close()

    def __enter__(self) -> Index:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class IndexOutdated(RuntimeError):
    """Der vorhandene Index passt nicht zur Programmfassung."""
