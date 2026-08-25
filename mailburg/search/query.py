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

    return None, []


def describe_syntax() -> str:
    """Kurze Hilfe für die Oberfläche und die Kommandozeile."""
    return """Suchbegriffe werden mit UND verknüpft.

  rechnung                  irgendwo in Text, Betreff oder Anhang
  von:müller                Absender enthält "müller"
  an:info@example.com       Empfänger
  betreff:"offene posten"   mehrere Wörter in Anführungszeichen
  text:vertrag              nur im Mailtext
  inhalt:vertrag            nur im Text der Anhänge
  anhang:vertrag.pdf        Dateiname eines Anhangs
  hat:anhang                nur Mails mit Anhang
  typ:pdf                   Anhang mit dieser Endung
  jahr:2025 · jahr:2020-2025
  konto:firma · ordner:Gesendet
  -werbung                  schließt Treffer aus"""
