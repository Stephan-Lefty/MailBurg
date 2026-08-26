"""Suchausdrücke in SQL übersetzen.

Die Suchsprache ist deutsch und soll sich beim Tippen von selbst erklären::

    rechnung                        irgendwo in Text, Betreff oder Anhang
    von:müller rechnung             beides muss zutreffen
    betreff:"offene posten"         mehrere Wörter in Anführungszeichen
    hat:anhang typ:pdf jahr:2025    nur PDF-Anhänge aus 2025
    konto:firma ordner:Gesendet     auf ein Postfach eingegrenzt
    -werbung                        schließt Treffer aus

Bedingungen werden mit UND verknüpft, weil das dem entspricht, was Leute
beim Suchen erwarten: jeder weitere Begriff soll die Trefferliste kleiner
machen, nicht größer.

**Zwei Indizes, je nach Feld.** Freitext läuft über den Wortindex mit
Präfixsuche, ``von:`` und ``betreff:`` über den Dreizeichenindex. Deshalb
findet ``betreff:rechnung`` auch ``Schlussrechnung`` – im Deutschen ist das
kein Sonderwunsch, sondern der Normalfall.
"""

from __future__ import annotations

import time

import re

#: ``feld:wert``, wobei der Wert in Anführungszeichen stehen darf.
_TERM_RE = re.compile(
    r"""(?P<neg>-)?                       # führendes Minus schließt aus
        (?:(?P<field>[a-zäöüß]+):)?       # optionaler Feldname
        (?:"(?P<quoted>[^"]*)"|(?P<bare>\S+))
    """,
    re.VERBOSE | re.IGNORECASE,
)

#: Feldname in der Suche -> Spalte im Dreizeichenindex.
_TRIGRAM_FIELDS = {
    "von": "sender",
    "absender": "sender",
    "an": "recipients",
    "empfaenger": "recipients",
    "empfänger": "recipients",
    "betreff": "subject",
    "anhang": "attachment_names",
    "dateiname": "attachment_names",
}

#: Feldname -> Spalte im Wortindex, für Felder ohne Teilwortsuche.
_FULLTEXT_FIELDS = {
    "text": "body",
    "inhalt": "attachment_text",
}

_YEAR_RANGE_RE = re.compile(r"^(\d{4})\s*-\s*(\d{4})$")


class QueryError(ValueError):
    """Der Suchausdruck ergibt keinen Sinn."""


def _fts_quote(value: str) -> str:
    """Macht aus Benutzereingabe einen gefahrlosen FTS5-Suchbegriff.

    FTS5 kennt eigene Operatoren – ``AND``, ``NOT``, Klammern, Sternchen.
    Wer nach ``AND`` sucht, meint aber das Wort. Alles in Anführungszeichen
    zu setzen macht daraus zuverlässig einen reinen Suchbegriff; innere
    Anführungszeichen werden nach FTS5-Art verdoppelt.
    """
    return '"' + value.replace('"', '""') + '"'


def _datum_lesen(wert: str) -> str:
    """Nimmt ein Datum entgegen – geschrieben, wie man es hier schreibt.

    Zwei Schreibweisen, beide eindeutig: ``26.08.2026`` mit Punkten meint
    Tag zuerst, ``2026-08-26`` mit Bindestrichen ist ISO. Bewusst *nicht*
    mit Schrägstrichen: ``08/09/2026`` ist in Deutschland der 8. September
    und in den USA der 9. August. Bei einer Suche im eigenen Archiv wäre
    das ein Fehler, den niemand bemerkt – man bekäme einfach die falschen
    Mails und hielte sie für alle.

    Dieses Modul kennt Qt nicht: Die Kommandozeile läuft ohne
    Oberfläche, und ein Suchausdruck muss dort dasselbe bedeuten.
    """
    from datetime import date

    text = wert.strip()
    for muster in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return date(*time.strptime(text, muster)[:3]).isoformat()
        except ValueError:
            continue
    raise QueryError(
        f"'{wert}' ist kein Datum. Erwartet: 26.08.2026 oder 2026-08-26."
    )


def _column_match(table: str, column: str, value: str, *, prefix: bool = False) -> str:
    """Baut einen FTS5-Ausdruck, der nur eine Spalte durchsucht."""
    term = _fts_quote(value)
    if prefix:
        term += "*"
    return f"{{{column}}} : {term}"


def build(expression: str) -> tuple[str, list[object]]:
    """Übersetzt einen Suchausdruck in WHERE-Bedingung und Parameter.

    Die Bedingung bezieht sich auf die Tabelle ``messages`` unter dem
    Kürzel ``m``. Ein leerer Ausdruck ergibt ``1=1`` – dann passt alles,
    was für die Gesamtübersicht gebraucht wird.
    """
    expression = (expression or "").strip()
    if not expression:
        return "1=1", []

    clauses: list[str] = []
    params: list[object] = []
    free_terms: list[str] = []
    free_excluded: list[str] = []

    for match in _TERM_RE.finditer(expression):
        value = match.group("quoted")
        if value is None:
            value = match.group("bare") or ""
        value = value.strip()
        if not value:
            continue

        field = (match.group("field") or "").lower()
        negate = bool(match.group("neg"))

        if not field:
            (free_excluded if negate else free_terms).append(value)
            continue

        clause, extra = _field_clause(field, value)
        if clause is None:
            # Unbekanntes Feld – wir behandeln es als Freitext, statt eine
            # Fehlermeldung zu werfen. Wer "kunde:meier" tippt, sucht
            # vermutlich nach beidem und nicht nach einer Belehrung.
            (free_excluded if negate else free_terms).append(f"{field} {value}")
            continue

        clauses.append(f"NOT ({clause})" if negate else clause)
        params.extend(extra)

    if free_terms:
        # Alle freien Begriffe in einer Anfrage, mit UND verknüpft und als
        # Präfix – so wird die Trefferliste schon beim Tippen brauchbar.
        joined = " AND ".join(_fts_quote(t) + "*" for t in free_terms)
        clauses.append("m.id IN (SELECT rowid FROM search WHERE search MATCH ?)")
        params.append(joined)

    for term in free_excluded:
        clauses.append("m.id NOT IN (SELECT rowid FROM search WHERE search MATCH ?)")
        params.append(_fts_quote(term) + "*")

    return (" AND ".join(clauses) if clauses else "1=1"), params


def _field_clause(field: str, value: str) -> tuple[str | None, list[object]]:
    """Baut die Bedingung für ein einzelnes ``feld:wert``."""
    if field in _TRIGRAM_FIELDS:
        column = _TRIGRAM_FIELDS[field]
        # Der Dreizeichenindex braucht mindestens drei Zeichen. Bei kürzerem
        # Suchbegriff weichen wir auf den Wortindex aus, sonst käme nichts
        # zurück – ein "von:ab" soll ja trotzdem etwas finden.
        if len(value) >= 3:
            return (
                "m.id IN (SELECT rowid FROM search_tri WHERE search_tri MATCH ?)",
                [_column_match("search_tri", column, value)],
            )
        return (
            "m.id IN (SELECT rowid FROM search WHERE search MATCH ?)",
            [_column_match("search", column, value, prefix=True)],
        )

    if field in _FULLTEXT_FIELDS:
        return (
            "m.id IN (SELECT rowid FROM search WHERE search MATCH ?)",
            [_column_match("search", _FULLTEXT_FIELDS[field], value, prefix=True)],
        )

    if field in ("hat", "mit"):
        if value.lower() in ("anhang", "anhänge", "anhaenge", "attachment"):
            return "m.has_attachments = 1", []
        return None, []

    if field in ("jahr", "year"):
        range_match = _YEAR_RANGE_RE.match(value)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            return "m.year BETWEEN ? AND ?", [min(start, end), max(start, end)]
        if value.isdigit():
            return "m.year = ?", [int(value)]
        raise QueryError(f"'{value}' ist keine Jahreszahl. Erwartet: jahr:2025 oder jahr:2020-2025")

    if field in ("seit", "ab", "nach", "bis", "vor", "am"):
        tag = _datum_lesen(value)
        if field in ("seit", "ab", "nach"):
            return "m.date >= ?", [f"{tag}T00:00:00"]
        if field in ("bis", "vor"):
            return "m.date <= ?", [f"{tag}T23:59:59"]
        return "m.date >= ? AND m.date <= ?", [f"{tag}T00:00:00", f"{tag}T23:59:59"]

    if field in ("typ", "type", "endung"):
        return (
            "EXISTS (SELECT 1 FROM attachments a WHERE a.msg_id = m.id AND a.extension = ?)",
            [value.lower().lstrip(".")],
        )

    if field in ("konto", "account", "postfach"):
        return (
            "EXISTS (SELECT 1 FROM locations l WHERE l.msg_id = m.id AND l.account = ?)",
            [value],
        )

    if field in ("ordner", "folder"):
        return (
            "EXISTS (SELECT 1 FROM locations l WHERE l.msg_id = m.id AND l.folder LIKE ?)",
            [f"%{value}%"],
        )

    if field in ("kategorie", "category"):
        return "m.category = ?", [value.lower()]

    if field in ("datei", "file"):
        # GLOB statt Volltext: Nur so bedeutet ``*.doc`` wirklich "endet
        # auf .doc" und trifft nicht "dokumentation.pdf". Wer gar keinen
        # Platzhalter tippt, meint erfahrungsgemäß "kommt darin vor".
        muster = value if any(z in value for z in "*?[") else f"*{value}*"
        return (
            "EXISTS (SELECT 1 FROM attachments a WHERE a.msg_id = m.id "
            "AND lower(a.filename) GLOB lower(?))",
            [muster],
        )

    if field in ("groesse", "größe", "size"):
        vergleich, bytes_wert = _groesse_lesen(value)
        return f"m.size {vergleich} ?", [bytes_wert]

    if field in ("wichtigkeit", "prioritaet", "priorität", "priority"):
        stufe = _WICHTIGKEIT.get(value.lower())
        if stufe is None:
            raise QueryError(
                f"'{value}' ist keine Wichtigkeit. Erwartet: hoch, normal oder niedrig."
            )
        return "m.wichtigkeit = ?", [stufe]

    if field in ("archiviert", "aufgenommen"):
        # Präfixvergleich auf der ISO-Schreibweise: "2026" trifft das Jahr,
        # "2026-08" den Monat, "2026-08-25" den Tag. Ein einziger Vergleich
        # für alle drei Fälle.
        #
        # Ein vollständiges Datum darf auch deutsch geschrieben sein -
        # überall sonst geht das, und eine Ausnahme müsste sich jemand
        # merken. Ein halbes Datum wie "08.2026" bleibt außen vor: Es
        # ließe sich nicht vom Tag "08.2026" unterscheiden, den es nicht
        # gibt, und Raten hat bei Suchen nichts zu suchen.
        if "." in value:
            return "m.archiviert LIKE ?", [f"{_datum_lesen(value)}%"]
        return "m.archiviert LIKE ?", [f"{value}%"]

    if field in ("cc", "kopie"):
        return (
            "EXISTS (SELECT 1 FROM recipients r WHERE r.msg_id = m.id "
            "AND r.art = 'cc' AND r.addr LIKE ?)",
            [f"%{value.lower()}%"],
        )

    if field in ("bcc", "blindkopie"):
        return (
            "EXISTS (SELECT 1 FROM recipients r WHERE r.msg_id = m.id "
            "AND r.art = 'bcc' AND r.addr LIKE ?)",
            [f"%{value.lower()}%"],
        )

    if field in ("direkt", "nur-an"):
        # Direkt angeschrieben, nicht bloß in Kopie - die Frage, mit der
        # sich Wichtiges von Mitgelesenem trennen lässt.
        return (
            "EXISTS (SELECT 1 FROM recipients r WHERE r.msg_id = m.id "
            "AND r.art = 'to' AND r.addr LIKE ?)",
            [f"%{value.lower()}%"],
        )

    return None, []


#: Was der Anwender schreiben darf, und was davon im Index steht.
_WICHTIGKEIT = {
    "hoch": "hoch", "high": "hoch", "wichtig": "hoch", "dringend": "hoch",
    "normal": "normal", "mittel": "normal",
    "niedrig": "niedrig", "low": "niedrig", "gering": "niedrig",
}

_EINHEITEN = {"": 1, "b": 1, "k": 1024, "kb": 1024, "m": 1024**2,
              "mb": 1024**2, "g": 1024**3, "gb": 1024**3}

_GROESSE_RE = re.compile(
    r"^(?P<op>>=|<=|>|<)?\s*(?P<zahl>\d+(?:[.,]\d+)?)\s*(?P<einheit>[a-z]*)$",
    re.IGNORECASE,
)


def _groesse_lesen(value: str) -> tuple[str, int]:
    """Übersetzt ``>5MB`` in Vergleich und Bytezahl."""
    treffer = _GROESSE_RE.match(value.strip())
    if not treffer:
        raise QueryError(
            f"'{value}' ist keine Größenangabe. Erwartet: groesse:>5MB, "
            f"groesse:<100KB oder groesse:2GB"
        )

    einheit = treffer.group("einheit").lower()
    if einheit not in _EINHEITEN:
        raise QueryError(
            f"'{einheit}' ist keine bekannte Einheit. Erwartet: B, KB, MB oder GB."
        )

    zahl = float(treffer.group("zahl").replace(",", "."))
    # Ohne Vergleichszeichen "mindestens" - wer groesse:5MB sucht, meint
    # große Mails und nicht solche mit exakt 5242880 Bytes.
    return (treffer.group("op") or ">="), int(zahl * _EINHEITEN[einheit])


def describe_syntax() -> str:
    """Kurze Hilfe für die Oberfläche und die Kommandozeile."""
    return """Suchbegriffe werden mit UND verknüpft.

  rechnung                  irgendwo in Text, Betreff oder Anhang
  von:müller                Absender enthält "müller"
  an:info@example.com       Empfänger (An, Kopie und Blindkopie)
  direkt:info@example.com   nur wer im An-Feld stand, nicht in Kopie
  cc:chef@example.com       nur in Kopie · bcc: für Blindkopie
  betreff:"offene posten"   mehrere Wörter in Anführungszeichen
  text:vertrag              nur im Mailtext
  inhalt:vertrag            nur im Text der Anhänge
  anhang:vertrag.pdf        Dateiname eines Anhangs
  hat:anhang                nur Mails mit Anhang

  datei:*.jpg               Muster auf Dateinamen; * und ? sind Platzhalter
  datei:Müller*.doc         beginnt mit Müller, endet auf .doc
  typ:pdf                   Anhang mit dieser Endung

  jahr:2025 · jahr:2020-2025
  seit:01.01.2026 · bis:31.03.2026 · am:26.08.2026
  archiviert:2026-08        wann die Mail ins Archiv kam
  archiviert:26.08.2026     auch tagesgenau
  groesse:>5MB              auch <100KB, >=2GB; ohne Zeichen: mindestens
  wichtigkeit:hoch          hoch, normal oder niedrig

  konto:firma · ordner:Gesendet
  -werbung                  schließt Treffer aus

Signaturgrafiken und Unterschriftsdateien gelten nicht als Anhang."""
