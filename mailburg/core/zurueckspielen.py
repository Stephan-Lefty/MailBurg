"""Viele Mails auf einmal aus dem Archiv auf die Platte zurück.

``core/rueckgabe.py`` holt **eine** Nachricht heraus – in ein Postfach
oder als ``.eml``. Das genügt, wenn man eine alte Rechnung wiederhaben
will. Es genügt nicht für den Fall, den ein Anwender am 2026-09-03
beschrieben hat: vom Mailserver sichern und den ganzen Bestand später in
Thunderbird zurückspielen.

**Warum zuerst auf die Platte und nicht per IMAP.** Über IMAP legt
``APPEND`` jedes Mal eine neue Kopie an. Wer zweimal in dasselbe Postfach
zurückspielt, hat alles doppelt, und der Server vergibt neue UIDs, an
denen sich nichts wiedererkennen lässt. Auf der Platte schreibt MailBurg
die Zieldateien selbst – und kann deshalb vorher nachsehen, was schon da
ist. Derselbe Lauf zweimal hintereinander ändert nichts am Ergebnis.

**Drei Formate, und die Wahl ist keine Geschmacksfrage:**

``maildir``
    Eine Datei je Nachricht, Ordner als ``.Konto.Unterordner``. Bytegenau,
    der Lesezustand kommt mit, beliebig groß. Das ist das Format für
    alles, was wieder ein Postfach werden soll.
``mbox``
    Eine Datei je Ordner. Thunderbirds lokale Ordner sind so aufgebaut,
    deshalb gibt es das hier – aber **bytegenau ist es nicht**: Das
    Format verlangt, dass eine Zeile, die mit ``From `` beginnt, im Text
    zu ``>From `` wird, sonst gilt sie als Anfang der nächsten Mail. Eine
    DKIM-Signatur über einen so veränderten Text stimmt nicht mehr.
``eml``
    Eine Datei je Nachricht, ohne Maildir-Gerüst. Zum Hineinziehen in ein
    beliebiges Mailprogramm.

**Was hier nicht geschieht: Löschen.** Zurückgespielt wird eine Kopie;
das Archiv bleibt unverändert, und das Journal bekommt einen Eintrag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: Die Formate, die geschrieben werden können.
FORMATE = ("maildir", "mbox", "eml")

#: So viele Treffer werden auf einmal aus dem Index geholt. Bei einer
#: halben Million Mails alles in eine Liste zu laden hieße, das Archiv
#: einmal in den Arbeitsspeicher zu legen.
SEITE = 500

#: Aus IMAP-Marken werden Maildir-Buchstaben. ``\Seen`` heißt dort ``S``.
_MARKEN = {
    "\\seen": "S",
    "\\answered": "R",
    "\\flagged": "F",
    "\\draft": "D",
    "\\deleted": "T",
}

_UNGEEIGNET = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ZielFehler(RuntimeError):
    """Mit diesem Ziel lässt sich nicht arbeiten."""


@dataclass
class Bericht:
    """Was ein Lauf getan hat.

    **Der Bericht ist nicht Beiwerk, sondern der Zweck.** Wer zehntausend
    Mails wegschreibt, sieht dem Zielordner nicht an, ob alle ankamen.
    """

    ziel: Path
    format: str
    geschrieben: int = 0
    uebersprungen: int = 0
    gesamt: int = 0
    ordner: dict[str, int] = field(default_factory=dict)
    fehler: list[tuple[str, str]] = field(default_factory=list)
    mehrfach: int = 0
    """Wie viele Mails an mehr als einer Stelle lagen – siehe ``_ordner``."""

    abgebrochen: bool = False

    @property
    def vollstaendig(self) -> bool:
        return not self.fehler and not self.abgebrochen

    def zusammenfassung(self) -> str:
        from mailburg.core.sprache import anzahl

        teile = [f"{anzahl(self.geschrieben, 'Mail', 'Mails')} geschrieben"]
        if self.uebersprungen:
            teile.append(f"{self.uebersprungen} schon vorhanden")
        if self.fehler:
            teile.append(f"{anzahl(len(self.fehler), 'Fehler', 'Fehler')}")
        if self.abgebrochen:
            teile.append("abgebrochen")
        return ", ".join(teile)


def _sauber(name: str) -> str:
    """Ein Ordnername, den jedes Dateisystem hinnimmt."""
    name = _UNGEEIGNET.sub("_", name).strip(" .")
    return name or "ohne-Namen"


def maildir_ordner(konto: str, ordner: str) -> str:
    """``Firma`` + ``Projekte/2025`` → ``.Firma.Projekte.2025``.

    Die Umkehrung von ``sources.local._maildir_name()``. Maildir++ kennt
    keine Verzeichnisse, sondern kodiert die Hierarchie in den Namen –
    und der Punkt ist dabei das Trennzeichen. **Punkte im Ordnernamen
    müssen deshalb weichen**, sonst entsteht aus »Rechnungen 2024.alt«
    eine Ebene, die es nie gab.
    """
    stuecke = [konto, *ordner.split("/")] if ordner else [konto]
    return "." + ".".join(_sauber(s).replace(".", "_") for s in stuecke if s)


def _marken(flags: str) -> str:
    """IMAP-Marken oder Maildir-Buchstaben → Maildir-Buchstaben.

    **Beides kommt vor.** Aus IMAP und JMAP stehen sie als ``\\Seen
    \\Answered`` im Index, aus einem eingelesenen Maildir als ``SR``.
    Wer nur das eine versteht, verliert beim Zurückspielen genau die
    Mails wieder als ungelesen, die er gerade erst richtig eingelesen
    hat.
    """
    if not flags:
        return ""
    if "\\" in flags:
        gefunden = {
            _MARKEN[teil.lower()]
            for teil in flags.split()
            if teil.lower() in _MARKEN
        }
    else:
        gefunden = {z for z in flags if z in "SRFDTP"}
    return "".join(sorted(gefunden))


def _dateiname(hit) -> str:
    """Ein Name, der bei jedem Lauf derselbe ist.

    **Darauf beruht die Duplikaterkennung.** Der Hash der Nachricht steckt
    darin, also erkennt ein zweiter Lauf seine eigene Arbeit wieder – ohne
    eine Beiakte, die jemand löschen könnte, und ohne die Zieldateien
    aufmachen zu müssen.
    """
    datum = (hit.date or "0000-00-00")[:10]
    return f"{datum}-{hit.hash[:16]}.mailburg"


class _Maildir:
    """Schreibt in ein Maildir++."""

    endung = ""

    def __init__(self, wurzel: Path) -> None:
        self.wurzel = wurzel
        self._bekannt: dict[Path, set[str]] = {}

    def _ordner(self, name: str) -> Path:
        ort = self.wurzel / name if name else self.wurzel
        if ort not in self._bekannt:
            for unter in ("cur", "new", "tmp"):
                (ort / unter).mkdir(parents=True, exist_ok=True)
            # Einmal je Ordner auflisten statt einmal je Mail nachsehen.
            # Bei zehntausend Dateien ist der Unterschied der zwischen
            # Sekunden und Minuten.
            vorhanden = set()
            for unter in ("cur", "new"):
                for datei in (ort / unter).iterdir():
                    vorhanden.add(datei.name.partition(":2,")[0])
            self._bekannt[ort] = vorhanden
        return ort

    def schon_da(self, ordner: str, hit, marken: str) -> bool:
        return _dateiname(hit) in self._bekannt[self._ordner(ordner)]

    def schreiben(self, ordner: str, hit, roh: bytes, marken: str) -> None:
        ort = self._ordner(ordner)
        name = _dateiname(hit)
        # Gelesene Post gehört nach cur/, neue nach new/ – so verlangt es
        # das Format, und Mailprogramme richten sich danach.
        unter = "cur" if marken else "new"
        ziel = ort / unter / (f"{name}:2,{marken}" if marken else name)
        # Erst nach tmp/, dann umbenennen: So sieht ein Mailprogramm, das
        # gleichzeitig hineinschaut, nie eine halbe Nachricht. Genau
        # dafür ist tmp/ im Format vorgesehen.
        vorlaeufig = ort / "tmp" / name
        vorlaeufig.write_bytes(roh)
        vorlaeufig.replace(ziel)
        self._bekannt[ort].add(name)

    def schliessen(self) -> None:
        pass


class _Eml:
    """Eine Datei je Nachricht, Ordner als Verzeichnisse."""

    def __init__(self, wurzel: Path) -> None:
        self.wurzel = wurzel
        self._bekannt: dict[Path, set[str]] = {}

    def _ordner(self, name: str) -> Path:
        ort = self.wurzel / name if name else self.wurzel
        if ort not in self._bekannt:
            ort.mkdir(parents=True, exist_ok=True)
            self._bekannt[ort] = {d.name for d in ort.iterdir()}
        return ort

    def schon_da(self, ordner: str, hit, marken: str) -> bool:
        return f"{_dateiname(hit)}.eml" in self._bekannt[self._ordner(ordner)]

    def schreiben(self, ordner: str, hit, roh: bytes, marken: str) -> None:
        ort = self._ordner(ordner)
        name = f"{_dateiname(hit)}.eml"
        (ort / name).write_bytes(roh)
        self._bekannt[ort].add(name)

    def schliessen(self) -> None:
        pass


class _Mbox:
    """Eine Datei je Ordner, im MBOX-Format.

    **Hier wird die Nachricht verändert**, und das ist keine Nachlässig-
    keit, sondern das Format: Eine Zeile, die mit ``From `` beginnt,
    trennt in einer MBOX zwei Nachrichten. Steht so etwas im Text – und
    »From Monday on…« kommt vor –, muss ein ``>`` davor. Wer die Datei
    später wieder einliest, bekommt den ursprünglichen Text zurück; eine
    DKIM-Signatur über die veränderte Fassung stimmt aber nicht mehr.

    Deshalb steht in jeder Anleitung: Maildir, wenn es genau sein soll.
    """

    #: Neben jeder MBOX liegt eine Liste der geschriebenen Hashes. Ohne
    #: sie ließe sich nicht sagen, was schon drinsteht – im Format selbst
    #: ist kein Platz für eine Kennung, und eine hineinzuschreiben hieße,
    #: die Mails zu verändern.
    BEIAKTE = ".mailburg-bestand"

    def __init__(self, wurzel: Path) -> None:
        self.wurzel = wurzel
        self._offen: dict[str, object] = {}
        self._bekannt: dict[str, set[str]] = {}

    def _datei(self, ordner: str) -> str:
        return f"{ordner}.mbox" if ordner else "Archiv.mbox"

    def _oeffnen(self, ordner: str):
        if ordner not in self._offen:
            pfad = self.wurzel / self._datei(ordner)
            pfad.parent.mkdir(parents=True, exist_ok=True)
            beiakte = pfad.with_name(f"{pfad.name}{self.BEIAKTE}")
            self._bekannt[ordner] = set(
                beiakte.read_text(encoding="ascii").split()
            ) if beiakte.exists() else set()
            self._offen[ordner] = pfad.open("ab")
        return self._offen[ordner]

    def schon_da(self, ordner: str, hit, marken: str) -> bool:
        self._oeffnen(ordner)
        return hit.hash in self._bekannt[ordner]

    def schreiben(self, ordner: str, hit, roh: bytes, marken: str) -> None:
        datei = self._oeffnen(ordner)
        wann = (hit.date or "")[:19].replace("T", " ") or "01 Jan 1970 00:00:00"
        datei.write(b"From MAILBURG " + wann.encode("ascii", "replace") + b"\n")
        datei.write(_von_maskieren(roh))
        if not roh.endswith(b"\n"):
            datei.write(b"\n")
        datei.write(b"\n")
        self._bekannt[ordner].add(hit.hash)

    def schliessen(self) -> None:
        for ordner, datei in self._offen.items():
            datei.close()
            pfad = self.wurzel / self._datei(ordner)
            pfad.with_name(f"{pfad.name}{self.BEIAKTE}").write_text(
                "\n".join(sorted(self._bekannt[ordner])) + "\n", encoding="ascii"
            )
        self._offen.clear()


def _von_maskieren(roh: bytes) -> bytes:
    """``From `` am Zeilenanfang wird zu ``>From ``.

    Auch schon maskierte Zeilen bekommen ein weiteres ``>`` – so
    verlangt es das Format (»mboxrd«), und nur so lässt sich beim Lesen
    wieder auseinanderhalten, was Text war und was Trennzeichen.
    """
    zeilen = roh.split(b"\n")
    return b"\n".join(
        b">" + z if z.lstrip(b">").startswith(b"From ") else z for z in zeilen
    )


def _schreiber(format: str, ziel: Path):
    if format == "maildir":
        return _Maildir(ziel)
    if format == "mbox":
        return _Mbox(ziel)
    if format == "eml":
        return _Eml(ziel)
    raise ZielFehler(
        f"Unbekanntes Format »{format}«. Möglich sind: {', '.join(FORMATE)}."
    )


def _ordnername(format: str, konto: str, ordner: str) -> str:
    if format == "maildir":
        return maildir_ordner(konto, ordner)
    stuecke = [_sauber(konto), *(_sauber(t) for t in ordner.split("/") if t)]
    return "/".join(stuecke)


def ziel_pruefen(ziel: Path, format: str) -> str:
    """Sieht nach, ob sich dorthin schreiben lässt – vor dem ersten Byte.

    Gibt einen Satz zurück, den man dem Anwender zeigen kann, oder wirft.
    """
    ziel = Path(ziel).expanduser()
    if format not in FORMATE:
        raise ZielFehler(
            f"Unbekanntes Format »{format}«. Möglich sind: {', '.join(FORMATE)}."
        )
    if ziel.exists() and not ziel.is_dir():
        raise ZielFehler(f"{ziel} ist eine Datei, kein Ordner.")
    # Ein Ordner, in dem schon etwas liegt, ist kein Fehler – ein zweiter
    # Lauf soll ja gerade ergänzen. Gesagt werden muss es trotzdem.
    if ziel.is_dir() and any(ziel.iterdir()):
        return f"In {ziel} liegt bereits etwas. Vorhandenes wird ergänzt, nicht ersetzt."
    return f"Geschrieben wird nach {ziel}."


def zurueckspielen(
    archiv,
    ziel,
    *,
    format: str = "maildir",
    suche: str = "",
    struktur: bool = True,
    sicht=None,
    fortschritt=None,
    weiter=None,
    trockenlauf: bool = False,
    actor: str = "",
) -> Bericht:
    """Schreibt die gefundenen Mails ins Dateisystem.

    ``suche`` ist ein Ausdruck der Suchsprache; leer heißt »alles«.
    ``struktur`` legt Konto und Ordner als Zielordner an – ohne das
    landet alles in einem Topf.

    ``fortschritt(getan, gesamt)`` wird unterwegs gerufen, ``weiter()``
    darf ``False`` sagen und bricht dann ab. **Abgebrochen heißt nicht
    kaputt:** Was geschrieben ist, ist vollständig geschrieben, und ein
    späterer Lauf setzt dort an, wo dieser aufgehört hat.

    ``trockenlauf`` zählt nur und rührt die Platte nicht an.
    """
    ziel = Path(ziel).expanduser()
    bericht = Bericht(ziel=ziel, format=format)
    bericht.gesamt = archiv.index.count(suche, sicht=sicht)

    if trockenlauf:
        schreiber = None
    else:
        ziel_pruefen(ziel, format)
        ziel.mkdir(parents=True, exist_ok=True)
        schreiber = _schreiber(format, ziel)

    getan = 0
    try:
        for hit in _treffer(archiv, suche, sicht, weiter):
            if weiter is not None and not weiter():
                bericht.abgebrochen = True
                break

            konto, ordner, flags = _ordner_fuer(archiv, hit, sicht, bericht)
            name = _ordnername(format, konto, ordner) if struktur else ""
            marken = _marken(flags) if format == "maildir" else ""

            try:
                if trockenlauf:
                    bericht.geschrieben += 1
                elif schreiber.schon_da(name, hit, marken):
                    bericht.uebersprungen += 1
                else:
                    roh = archiv.store.get(hit.hash, hit.bucket)
                    schreiber.schreiben(name, hit, roh, marken)
                    bericht.geschrieben += 1
            except Exception as fehler:  # noqa: BLE001 – siehe unten
                # **Eine kaputte Mail darf den Lauf nicht beenden.** Bei
                # zehntausend Nachrichten ist die Wahrscheinlichkeit
                # hoch, dass eine davon klemmt – eine fehlende Datei,
                # ein Name, den das Dateisystem nicht mag. Wer dann
                # abbricht, hat nichts. Notiert wird jede einzelne.
                bericht.fehler.append((hit.hash, str(fehler)))
            else:
                bericht.ordner[name or "."] = bericht.ordner.get(name or ".", 0) + 1

            getan += 1
            if fortschritt is not None and getan % 25 == 0:
                fortschritt(getan, bericht.gesamt)
    finally:
        if schreiber is not None:
            schreiber.schliessen()

    if fortschritt is not None:
        fortschritt(getan, bericht.gesamt)

    if not trockenlauf:
        # **Der Vorgang gehört ins Journal.** Aus einem Archiv sind Daten
        # herausgegangen; wer in einem Jahr fragt, wohin, muss es
        # nachlesen können. Dasselbe gilt für die Auskunft nach DSGVO.
        archiv.journal.append(
            "note",
            art="zurueckgespielt",
            format=format,
            ziel=str(ziel),
            suche=suche,
            nachrichten=bericht.geschrieben,
            uebersprungen=bericht.uebersprungen,
            fehler=len(bericht.fehler),
            abgebrochen=bericht.abgebrochen,
            actor=actor,
        )
        archiv.journal.flush()

    return bericht


def _treffer(archiv, suche: str, sicht, weiter):
    """Holt die Treffer seitenweise aus dem Index."""
    offset = 0
    while True:
        if weiter is not None and not weiter():
            return
        seite = archiv.index.search(
            suche, limit=SEITE, offset=offset, sortierung="datum",
            absteigend=False, sicht=sicht,
        )
        if not seite:
            return
        yield from seite
        offset += len(seite)


def _ordner_fuer(archiv, hit, sicht, bericht) -> tuple[str, str, str]:
    """Wohin diese Mail gehört – Konto, Ordner, Marken.

    **Eine Mail kann an mehreren Stellen gelegen haben**, und dann ist die
    Frage nicht, welche davon richtig ist, sondern wie oft sie hinterher
    dasteht. Bei Proton und Gmail ist Mehrfachablage der Normalfall: Dort
    ist jedes Etikett ein weiterer Fundort. Wer alle schreibt, hat die
    Rundmail von 2019 fünfmal im wiederhergestellten Postfach.

    Deshalb: **eine Mail, ein Ort.** Genommen wird der erste – die Liste
    ist sortiert, also ist die Wahl bei jedem Lauf dieselbe. Wie oft es
    vorkam, steht im Bericht.
    """
    orte = archiv.index.fundorte(hit.hash, sicht=sicht)
    if not orte:
        return "", "", ""
    if len(orte) > 1:
        bericht.mehrfach += 1
    return orte[0]
