"""Mails auseinandernehmen.

Was hier ankommt, ist über Jahrzehnte gewachsener Wildwuchs: Kopfzeilen in
sechs verschiedenen Kodierungen, angebliches UTF-8, das keines ist,
Anhänge ohne Namen, Datumsangaben, die kein Parser der Welt versteht. Dieses
Modul hat deshalb eine einzige Regel – **es wirft nichts weg und es gibt
niemals auf**. Lieber ein leerer Betreff als eine Mail, die beim Einlesen
durchfällt.

Der Rohtext bleibt davon unberührt. Was hier entsteht, wandert nur in den
Suchindex; die Mail selbst liegt unverändert in der Ablage.
"""

from __future__ import annotations

import email
import email.header
import email.policy
import email.utils
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage, Message
from html.parser import HTMLParser

#: Mehr Text als das nehmen wir aus einem einzelnen Mailteil nicht in den
#: Index auf. Newsletter mit eingebettetem Bildmüll blähen ihn sonst auf,
#: ohne dass die Suche dadurch besser würde.
MAX_BODY_CHARS = 1_000_000


@dataclass(frozen=True)
class Attachment:
    """Ein Anhang, so wie er in der Mail steckt."""

    filename: str
    mime_type: str
    size: int
    payload: bytes = field(repr=False, default=b"")

    @property
    def extension(self) -> str:
        """Endung in Kleinbuchstaben, ohne Punkt – für die Suche nach ``typ:pdf``."""
        _, _, ext = self.filename.rpartition(".")
        return ext.lower() if ext and ext != self.filename else ""


@dataclass
class ParsedMessage:
    """Das, was der Suchindex von einer Mail wissen muss."""

    subject: str = ""
    from_addr: str = ""
    from_name: str = ""
    to_addrs: list[str] = field(default_factory=list)
    cc_addrs: list[str] = field(default_factory=list)
    date: datetime | None = None
    message_id: str = ""
    body: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    defects: list[str] = field(default_factory=list)
    """Was beim Einlesen auffiel. Wandert ins Journal, nicht in den Müll."""

    @property
    def has_attachments(self) -> bool:
        return bool(self.attachments)

    @property
    def all_recipients(self) -> str:
        """Alle Empfänger als ein durchsuchbarer Text."""
        return " ".join(self.to_addrs + self.cc_addrs)


class _TextFromHTML(HTMLParser):
    """Holt den sichtbaren Text aus HTML.

    Kein vollwertiger Umwandler – für die Suche genügt der Fließtext ohne
    Auszeichnung. Skript- und Stilblöcke bleiben draußen, sonst landet
    CSS im Index und verfälscht jede Trefferliste.
    """

    _SKIP = {"script", "style", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._depth:
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._depth:
            self._parts.append(data)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._parts)).strip()


def html_to_text(html: str) -> str:
    """Reduziert HTML auf seinen sichtbaren Text."""
    parser = _TextFromHTML()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 – kaputtes HTML ist die Regel, nicht die Ausnahme
        pass
    return parser.text


def _decode_part(part: Message) -> str:
    """Holt den Text eines Mailteils, notfalls mit Gewalt.

    Die angegebene Kodierung ist erfahrungsgemäß oft gelogen. Wir versuchen
    sie zuerst, dann die üblichen Verdächtigen, und ersetzen am Ende, was
    sich nicht deuten lässt – ein Text mit ein paar Fragezeichen ist immer
    noch besser als gar keiner.
    """
    try:
        payload = part.get_payload(decode=True)
    except Exception:  # noqa: BLE001
        return ""
    if not payload:
        return ""

    charsets = [part.get_content_charset(), "utf-8", "cp1252", "latin-1"]
    for charset in charsets:
        if not charset:
            continue
        try:
            return payload.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="replace")


def _header(message: Message, name: str) -> str:
    """Liest eine Kopfzeile und macht aus RFC-2047-Kauderwelsch lesbaren Text."""
    raw = message.get(name)
    if raw is None:
        return ""
    if isinstance(raw, str) and not raw.startswith("=?"):
        return raw.strip()
    try:
        parts = email.header.decode_header(str(raw))
    except Exception:  # noqa: BLE001
        return str(raw).strip()

    pieces: list[str] = []
    for text, charset in parts:
        if isinstance(text, bytes):
            try:
                pieces.append(text.decode(charset or "utf-8", errors="replace"))
            except LookupError:
                pieces.append(text.decode("utf-8", errors="replace"))
        else:
            pieces.append(text)
    return "".join(pieces).strip()


def _addresses(message: Message, name: str) -> list[str]:
    """Sammelt die Adressen einer Empfängerzeile."""
    raw = _header(message, name)
    if not raw:
        return []
    return [addr for _, addr in email.utils.getaddresses([raw]) if addr]


def _parse_date(message: Message, defects: list[str]) -> datetime | None:
    """Ermittelt den Zeitpunkt der Mail.

    Zuerst ``Date:``. Fehlt oder taugt sie nichts, hilft die jüngste
    ``Received:``-Zeile weiter – die stammt vom eigenen Server und ist damit
    oft verlässlicher als das, was der Absender behauptet.
    """
    raw = message.get("Date")
    if raw:
        try:
            parsed = email.utils.parsedate_to_datetime(str(raw))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (TypeError, ValueError):
            defects.append(f"Datum unlesbar: {str(raw)[:60]}")

    received = message.get_all("Received")
    if received:
        _, _, tail = str(received[0]).rpartition(";")
        try:
            parsed = email.utils.parsedate_to_datetime(tail.strip())
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (TypeError, ValueError):
            pass

    defects.append("Kein brauchbares Datum gefunden")
    return None


def parse(raw: bytes, *, with_payloads: bool = False) -> ParsedMessage:
    """Zerlegt eine Mail.

    ``with_payloads`` behält die Anhangsdaten im Speicher – nötig, wenn
    anschließend deren Text herausgezogen werden soll, sonst
    Verschwendung.
    """
    defects: list[str] = []

    # Die strenge Auslegung liefert die besseren Ergebnisse, verschluckt sich
    # aber an manchen alten Mails. Dann die nachsichtige von 1999.
    message: Message
    try:
        message = email.message_from_bytes(raw, policy=email.policy.default)
    except Exception as exc:  # noqa: BLE001
        defects.append(f"Strenge Auslegung fehlgeschlagen: {exc}")
        message = email.message_from_bytes(raw, policy=email.policy.compat32)

    result = ParsedMessage(
        subject=_header(message, "Subject"),
        message_id=_header(message, "Message-ID"),
        to_addrs=_addresses(message, "To"),
        cc_addrs=_addresses(message, "Cc"),
        defects=defects,
    )

    sender = _header(message, "From")
    if sender:
        name, addr = email.utils.parseaddr(sender)
        result.from_name = name
        result.from_addr = addr

    result.date = _parse_date(message, defects)

    body_parts: list[str] = []
    html_parts: list[str] = []

    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_maintype() == "multipart":
            continue

        disposition = str(part.get("Content-Disposition", "")).lower()
        filename = part.get_filename()
        is_attachment = "attachment" in disposition or bool(filename)

        if is_attachment:
            try:
                payload = part.get_payload(decode=True) or b""
            except Exception:  # noqa: BLE001
                payload = b""
                defects.append("Anhang ließ sich nicht dekodieren")

            if filename:
                filename = _header_value_or(filename)
            else:
                # Namenlose Anhänge kommen häufiger vor, als man denkt.
                # Wir geben ihnen einen, damit sie in der Oberfläche
                # überhaupt anklickbar sind.
                ext = (part.get_content_subtype() or "dat").lower()
                filename = f"unbenannt.{ext}"

            result.attachments.append(
                Attachment(
                    filename=filename,
                    mime_type=part.get_content_type(),
                    size=len(payload),
                    payload=payload if with_payloads else b"",
                )
            )
            continue

        subtype = part.get_content_subtype()
        if subtype == "plain":
            body_parts.append(_decode_part(part))
        elif subtype == "html":
            html_parts.append(_decode_part(part))

    # Nur-HTML-Mails sind der Normalfall bei Newslettern; dann muss der
    # umgewandelte Text herhalten.
    text = "\n".join(p for p in body_parts if p).strip()
    if not text and html_parts:
        text = html_to_text("\n".join(html_parts))

    result.body = text[:MAX_BODY_CHARS]
    return result


def _header_value_or(value: object) -> str:
    """Macht aus einem Kopfzeilenwert einen einfachen String."""
    text = str(value)
    if text.startswith("=?"):
        try:
            parts = email.header.decode_header(text)
            return "".join(
                p.decode(c or "utf-8", errors="replace") if isinstance(p, bytes) else p
                for p, c in parts
            )
        except Exception:  # noqa: BLE001
            return text
    return text
