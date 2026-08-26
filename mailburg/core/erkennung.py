"""Eingescannte Dokumente nach und nach lesbar machen.

Texterkennung kostet fünf bis dreißig Sekunden je Seite. Bei siebenhundert
Dokumenten sind das Stunden – die kann man niemandem am Stück zumuten, und
schon gar nicht darf man voraussetzen, dass der Rechner nachts durchläuft.

**Deshalb häppchenweise.** Nach jedem Abruf, also alle halbe Stunde, wird ein
kleines Zeitbudget abgearbeitet: zwei Minuten, fünf Dokumente, was zuerst
kommt. Dann ist Schluss bis zum nächsten Mal. Ein Altbestand schmilzt so über
Tage, ohne dass jemand etwas davon merkt; neu ankommende Scans sind sofort
dran, weil ein einzelnes Dokument im Budget immer Platz hat.

**Im selben Lauf wie der Abruf, nicht daneben.** Das ist keine Bequemlichkeit,
sondern nötig: Solange MailBurg schreibend am Archiv ist, liegt eine
Sperrdatei darin. Ein Erkennungsdienst, der nebenher liefe, stünde dem Abruf
regelmäßig im Weg – und dann bliebe Post liegen. Die Rangfolge ist eindeutig:
Archivieren ist Pflicht, Durchsuchbarmachen ist Kür.

**Das Archiv bleibt unangetastet.** Der erkannte Text ist abgeleitete
Information, keine Post. Er wandert in den Suchindex und zusätzlich in einen
Nebenspeicher – beides wegwerfbar, beides jederzeit neu herstellbar. Die Mail
selbst bleibt bytegenau, wie sie ankam. Alles andere würde die Hash-Kette
entwerten.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from mailburg.core import paths

#: Voreinstellung für einen Durchlauf im Anschluss an den Abruf.
BUDGET_SEKUNDEN = 120

#: Und höchstens so viele Dokumente, selbst wenn die Zeit reichen würde.
#: Der Deckel ist bewusst hoch: Führen soll die Zeit, nicht die Stückzahl.
#: An einem echten Bestand gemessen (2026-08-25): gut fünf Sekunden je
#: Seite, knapp siebzehn je Dokument – bei fünf Dokumenten wären von zwei
#: Minuten Budget erst achtzig Sekunden verbraucht gewesen. Der Deckel
#: greift nur noch für den Fall vieler winziger Dokumente.
BUDGET_DOKUMENTE = 30

#: Um so viel wird die eigene Priorität gesenkt. Wer nebenher arbeitet,
#: soll nichts davon merken – die Erkennung nimmt sich, was übrig ist.
NACHRANG = 10

#: Ab so vielen Zeichen gilt der Anhangstext als brauchbar. Darunter ist ein
#: umfangreiches PDF vermutlich ein Scan. Dieselbe Schwelle wie in
#: ``extract/pdf.ist_wohl_gescannt``.
TEXTSCHWELLE = 200

#: Und ab dieser Dateigröße lohnt die Frage überhaupt.
GROESSENSCHWELLE = 100_000

_SCHEMA = """
-- Je Anhang, nicht je Mail. Eine Nachricht mit einem lesbaren Angebot und
-- einem eingescannten Lieferschein gälte sonst als erledigt, und der
-- Lieferschein bliebe für immer unsichtbar. Am echten Bestand gemessen
-- macht das den Unterschied zwischen 138 und rund 700 Dokumenten.
--
-- Als Kennung Hash und Dateiname statt der Zeilennummer aus der
-- Anhangstabelle: Die ändert sich beim Neuaufbau des Index, der Hash nie.
CREATE TABLE IF NOT EXISTS ocr_vermerk (
    hash      TEXT NOT NULL,
    dateiname TEXT NOT NULL,
    zustand   TEXT NOT NULL,
    grund     TEXT,
    seiten    INTEGER NOT NULL DEFAULT 0,
    zeitpunkt TEXT,
    PRIMARY KEY (hash, dateiname)
);
"""


@dataclass
class Statistik:
    """Wie ein Erkennungslauf ausging."""

    gelesen: int = 0
    gescheitert: int = 0
    seiten: int = 0
    sekunden: float = 0.0
    offen_danach: int = 0
    abgebrochen: bool = False
    """Ob das Budget aufgebraucht war – dann ist noch etwas übrig."""

    fehler: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.gelesen and not self.gescheitert:
            return "nichts zu tun"
        teile = [f"{self.gelesen} Dokumente lesbar gemacht ({self.seiten} Seiten)"]
        if self.gescheitert:
            teile.append(f"{self.gescheitert} ohne Ergebnis")
        if self.offen_danach:
            teile.append(f"noch {self.offen_danach} offen")
        return ", ".join(teile)


class Textspeicher:
    """Bewahrt erkannten Text neben dem Index auf.

    Warum nicht nur im Index? Weil der jederzeit neu gebaut werden darf –
    das ist eine Zusicherung des Programms. Läge der erkannte Text nur dort,
    würde aus zehn Minuten Neuaufbau ein Tag Rechnerei. Warum nicht im
    Archiv? Weil dort nur hineingehört, was tatsächlich angekommen ist.

    Also dazwischen: verlierbar, aber nicht bei jeder Gelegenheit.
    """

    def __init__(self, verzeichnis: Path | None = None) -> None:
        self.wurzel = verzeichnis or (paths.data_dir() / "ocr")

    def _pfad(self, digest: str) -> Path:
        # Nach den ersten zwei Zeichen unterteilt, damit kein Verzeichnis
        # mit zehntausend Einträgen entsteht.
        return self.wurzel / digest[:2] / f"{digest}.txt"

    def hat(self, digest: str) -> bool:
        return self._pfad(digest).exists()

    def lesen(self, digest: str) -> str:
        try:
            return self._pfad(digest).read_text(encoding="utf-8")
        except OSError:
            return ""

    def schreiben(self, digest: str, text: str) -> None:
        ziel = self._pfad(digest)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        vorlaeufig = ziel.with_suffix(".neu")
        vorlaeufig.write_text(text, encoding="utf-8")
        vorlaeufig.replace(ziel)

    def alle(self) -> dict[str, str]:
        """Für den Indexneuaufbau: alles, was schon erkannt wurde."""
        gefunden = {}
        if not self.wurzel.exists():
            return gefunden
        for datei in self.wurzel.rglob("*.txt"):
            gefunden[datei.stem] = datei.read_text(encoding="utf-8", errors="replace")
        return gefunden


class Warteschlange:
    """Welche Dokumente noch gelesen werden müssen.

    Die Liste wird nicht gepflegt, sondern jedes Mal erfragt: Welche Mails
    haben ein umfangreiches PDF, aus dem kaum Text kam? Damit erfasst sie
    auch Bestände, die längst im Archiv liegen – und sie heilt sich selbst,
    wenn der Index neu entsteht.
    """

    def __init__(self, index) -> None:
        self.index = index
        self._schema_herrichten()

    def _schema_herrichten(self) -> None:
        """Legt die Vermerktabelle an – und erneuert sie, falls sie alt ist.

        Die erste Fassung merkte sich je Mail statt je Anhang; ihr fehlt
        die Spalte ``dateiname``, und der Primärschlüssel lässt sich nicht
        nachträglich ändern. Nachrüsten geht also nicht.

        Das ist hier aber unbedenklich: Die Tabelle hält nur fest, was
        schon gelesen wurde. Geht sie verloren, werden ein paar Dokumente
        ein zweites Mal erkannt – Rechenzeit, sonst nichts. Der erkannte
        Text liegt ohnehin im Nebenspeicher.
        """
        vorhanden = {
            zeile[1]
            for zeile in self.index.db.execute("PRAGMA table_info(ocr_vermerk)")
        }
        if vorhanden and "dateiname" not in vorhanden:
            self.index.db.execute("DROP TABLE ocr_vermerk")
        self.index.db.executescript(_SCHEMA)

    #: Der gemeinsame Teil beider Abfragen: ein umfangreiches PDF, aus dem
    #: kein Text kam, ohne bereits vorliegenden Vermerk.
    _BEDINGUNG = """
          FROM messages a_m
          JOIN attachments a ON a.msg_id = a_m.id
         WHERE a.extension = 'pdf'
           AND a.size > ?
           AND (a.text_zeichen = 0
                OR (a.text_zeichen < 0 AND NOT EXISTS (
                        SELECT 1 FROM search s
                         WHERE s.rowid = a_m.id
                           AND LENGTH(COALESCE(s.attachment_text, '')) >= ?)))
           AND NOT EXISTS (SELECT 1 FROM ocr_vermerk v
                            WHERE v.hash = a_m.hash AND v.dateiname = a.filename)
    """

    def offen(self, grenze: int = 100) -> list[tuple[str, str, str]]:
        """Die nächsten Kandidaten: Hash, Ablagefach und Dateiname.

        **Die kleinsten zuerst.** Ein einseitiger Scan ist in vier
        Sekunden gelesen, ein zwanzigseitiger Brocken braucht eine halbe
        Stunde. Nach Datum sortiert erwischt man den Brocken irgendwann
        mittendrin – und dann steht die Anzeige minutenlang still, obwohl
        vierzig kleine Dokumente in derselben Zeit fertig geworden wären.
        Bei einem Lauf mit Zeitbudget entscheidet die Reihenfolge sogar,
        wie viel überhaupt geschafft wird.

        Zwei Fälle stecken in der Bedingung. Neue Indizes wissen je Anhang,
        wie viel Text er hergab – dann ist ``text_zeichen = 0`` das klare
        Zeichen. Ältere Indizes wissen das nicht (``-1``); für die bleibt
        nur die alte Schätzung über den Anhangstext der ganzen Mail.
        """
        return [
            (r["hash"], r["bucket"], r["filename"])
            for r in self.index.db.execute(
                f"""SELECT a_m.hash, a_m.bucket, a.filename
                    {self._BEDINGUNG}
                    ORDER BY a.size ASC, a_m.date DESC
                    LIMIT ?""",
                (GROESSENSCHWELLE, TEXTSCHWELLE, grenze),
            )
        ]

    def anzahl(self) -> int:
        """Wie viele Dokumente noch warten."""
        return self.index.db.execute(
            f"SELECT COUNT(*) {self._BEDINGUNG}",
            (GROESSENSCHWELLE, TEXTSCHWELLE),
        ).fetchone()[0]

    def vermerken(self, digest: str, dateiname: str, zustand: str, *,
                  grund: str = "", seiten: int = 0) -> None:
        self.index.db.execute(
            """INSERT OR REPLACE INTO ocr_vermerk
                   (hash, dateiname, zustand, grund, seiten, zeitpunkt)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (digest, dateiname, zustand, grund, seiten,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )

    def vergessen(self, digest: str, dateiname: str | None = None) -> None:
        """Nimmt Vermerke zurück – für einen erneuten Versuch."""
        if dateiname is None:
            self.index.db.execute("DELETE FROM ocr_vermerk WHERE hash = ?", (digest,))
        else:
            self.index.db.execute(
                "DELETE FROM ocr_vermerk WHERE hash = ? AND dateiname = ?",
                (digest, dateiname),
            )

    def gescheiterte(self) -> list[tuple[str, str, str]]:
        return [
            (r["hash"], r["dateiname"], r["grund"] or "")
            for r in self.index.db.execute(
                "SELECT hash, dateiname, grund FROM ocr_vermerk "
                "WHERE zustand = 'gescheitert'"
            )
        ]


def _kennung(dateiname: str) -> str:
    """Macht aus einem Dateinamen etwas, das als Dateiname taugt.

    Anhänge heißen »Rechnung 3/2025.pdf« oder tragen Umlaute; als Teil
    eines Pfades im Nebenspeicher wäre das unbrauchbar. Der Kurz-Hash ist
    eindeutig genug und überall gültig.
    """
    import hashlib

    return hashlib.sha256(dateiname.encode("utf-8")).hexdigest()[:12]


def _nachrang() -> None:
    """Senkt die eigene Priorität, damit die Erkennung nicht stört."""
    try:
        os.nice(NACHRANG)
    except (OSError, AttributeError):
        # Unter Windows gibt es os.nice nicht; dort bliebe nur die
        # Prozessklasse über die WinAPI. Ohne Nachrang läuft es auch,
        # nur spürbarer.
        pass


def durchlauf(
    archiv,
    *,
    budget_sekunden: float = BUDGET_SEKUNDEN,
    budget_dokumente: int = BUDGET_DOKUMENTE,
    fortschritt=None,
    weiter=None,
    je_seite=None,
) -> Statistik:
    """Arbeitet die Warteschlange ab, bis das Budget aufgebraucht ist.

    ``budget_sekunden`` von 0 bedeutet: ohne Zeitgrenze durchlaufen. Das ist
    für den ausdrücklich angestoßenen Lauf gedacht, nicht für den Anschluss
    an einen Abruf.

    ``je_seite`` meldet sich innerhalb eines Dokuments – mit Dateiname,
    Seite und Seitenzahl. Ohne das steht die Oberfläche bei einem
    zwanzigseitigen Scan fast zwei Minuten auf demselben Wert.

    ``weiter`` ist ein Rückruf, der ``False`` liefert, wenn Schluss sein
    soll – für den Abbruchknopf in der Oberfläche. Geprüft wird zwischen
    zwei Dokumenten, nicht mitten in einem: Ein halb gelesenes PDF wäre
    schlimmer als ein ungelesenes, weil es als erledigt gälte.
    """
    from mailburg.extract import message as message_modul
    from mailburg.extract import ocr

    stat = Statistik()
    warteschlange = Warteschlange(archiv.index)
    speicher = Textspeicher()

    bereit, hinweis = ocr.bereit()
    if not bereit:
        stat.fehler.append(hinweis)
        stat.offen_danach = warteschlange.anzahl()
        return stat

    _nachrang()
    beginn = time.monotonic()

    def zeit_um() -> bool:
        return bool(budget_sekunden) and (time.monotonic() - beginn) >= budget_sekunden

    # Die Rohdaten einer Mail werden nur einmal geholt und zerlegt, auch
    # wenn mehrere ihrer Anhänge in der Warteschlange stehen.
    zwischenspeicher: dict[str, object] = {}

    for digest, bucket, dateiname in warteschlange.offen(
        grenze=max(budget_dokumente * 4, 40)
    ):
        if zeit_um() or (
            budget_dokumente and stat.gelesen + stat.gescheitert >= budget_dokumente
        ):
            stat.abgebrochen = True
            break

        if digest not in zwischenspeicher:
            try:
                roh = archiv.store.get(digest, bucket)
                zwischenspeicher = {
                    digest: message_modul.parse(roh, with_payloads=True)
                }
            except (FileNotFoundError, ValueError, OSError) as exc:
                warteschlange.vermerken(
                    digest, dateiname, "gescheitert", grund=f"nicht lesbar: {exc}"
                )
                stat.gescheitert += 1
                continue

        zerlegt = zwischenspeicher[digest]
        anhang = next(
            (a for a in zerlegt.attachments if a.filename == dateiname and a.payload),
            None,
        )
        if anhang is None:
            warteschlange.vermerken(
                digest, dateiname, "gescheitert", grund="Anhang nicht gefunden"
            )
            stat.gescheitert += 1
            continue

        ergebnis = ocr.text_aus_pdf(
            anhang.payload,
            abbruch=zeit_um,
            je_seite=(
                (lambda nr, von, name=dateiname: je_seite(name, nr, von))
                if je_seite else None
            ),
        )

        if ergebnis.abgebrochen and not ergebnis.text:
            # Nichts geschafft – ohne Vermerk, damit es beim nächsten Mal
            # von vorn versucht wird.
            stat.abgebrochen = True
            break

        if ergebnis.text:
            speicher.schreiben(f"{digest}-{_kennung(dateiname)}", ergebnis.text)
            _in_index_schreiben(
                archiv.index, digest, f"{dateiname}\n{ergebnis.text}"
            )
            warteschlange.vermerken(
                digest, dateiname, "erledigt", seiten=ergebnis.seiten
            )
            stat.gelesen += 1
            stat.seiten += ergebnis.seiten
        else:
            warteschlange.vermerken(
                digest, dateiname, "gescheitert",
                grund=ergebnis.fehler or "kein Text erkannt",
                seiten=ergebnis.seiten,
            )
            stat.gescheitert += 1

        archiv.index.commit()
        if fortschritt:
            fortschritt(stat)

        if weiter is not None and not weiter():
            stat.abgebrochen = True
            break

        if ergebnis.abgebrochen:
            stat.abgebrochen = True
            break

    archiv.index.commit()
    stat.sekunden = time.monotonic() - beginn
    stat.offen_danach = warteschlange.anzahl()
    return stat


def _in_index_schreiben(index, digest: str, text: str) -> None:
    """Hängt den erkannten Text an den Suchindex der Mail an.

    Angehängt, nicht ersetzt: Im Anhangstext können schon Dateinamen oder
    Text aus anderen Anhängen derselben Mail stehen, und der soll nicht
    verlorengehen.
    """
    zeile = index.db.execute(
        "SELECT id FROM messages WHERE hash = ?", (digest,)
    ).fetchone()
    if zeile is None:
        return
    msg_id = zeile["id"]

    vorhanden = index.db.execute(
        "SELECT attachment_text FROM search WHERE rowid = ?", (msg_id,)
    ).fetchone()
    bisher = (vorhanden["attachment_text"] if vorhanden else "") or ""

    index.db.execute(
        "UPDATE search SET attachment_text = ? WHERE rowid = ?",
        (f"{bisher}\n{text}".strip(), msg_id),
    )
