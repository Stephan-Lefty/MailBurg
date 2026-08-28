"""Ein Archiv in eine einzelne Datei packen – für die Ablage anderswo.

**MailBurg ist ein Archiv, kein Backup.** Es liegt auf einer Platte;
geht die kaputt, ist alles weg. Eine Sicherung ist eine Kopie an einem
zweiten Ort. Dieses Modul macht daraus eine einzelne Datei, die sich
hochladen, wegtragen oder auf eine andere Platte legen lässt.

**Kleiner wird das Archiv dabei kaum.** Die Mails liegen bereits
komprimiert; nachgemessen an 300 Nachrichten: null Prozent Ersparnis.
Das Protokoll dagegen ist Text und schrumpft um vier Fünftel – nur ist
es eben auch nur ein Promille des Ganzen.

Der Gewinn liegt woanders: **aus zweitausend Dateien wird eine.**
Cloud-Programme laden jede Datei einzeln hoch, mit eigenem Vorgang und
eigener Prüfung; bei tausenden kleinen dauert das ein Vielfaches von
einer großen gleicher Größe. Und jeder Stand ist eine Datei mit Datum
statt eines Ordners, den man mit dem vorigen vergleichen müsste.

**Der Index kommt nicht mit.** Er liegt ohnehin außerhalb, ändert sich
bei jedem Abruf vollständig und lässt sich aus dem Protokoll neu
aufbauen. Ihn mitzusichern hieße, die größte Datei ohne Not durch die
Leitung zu schicken.
"""

from __future__ import annotations

import tarfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

#: Was Zstandard beim Packen leisten soll. Höhere Stufen kosten spürbar
#: Zeit und bringen hier nichts – die Mails sind schon komprimiert.
STUFE = 3


class SicherungFehler(RuntimeError):
    """Die Sicherung ließ sich nicht anlegen."""


@dataclass
class Befund:
    """Was beim Sichern herauskam."""

    ziel: Path | None = None
    dateien: int = 0
    quelle_bytes: int = 0
    ziel_bytes: int = 0
    kette_geprueft: bool = False
    kette_heil: bool = True
    warnungen: list[str] = field(default_factory=list)

    @property
    def ersparnis(self) -> int:
        """Wie viel Prozent kleiner die Datei ist – meist wenig."""
        if not self.quelle_bytes:
            return 0
        return round((1 - self.ziel_bytes / self.quelle_bytes) * 100)


#: Umlaute werden umgeschrieben, nicht durchgereicht. Ein Dateiname
#: wandert bei einer Sicherung durch fremde Hände: Cloud-Server,
#: Weboberflächen, fremde Rechner. macOS speichert Umlaute anders als
#: Linux (NFD statt NFC), manche Weboberfläche zeigt sie als Fragezeichen,
#: und wer die Datei später per Kommandozeile sucht, tippt sie falsch.
#: »Geschaeftsarchiv« liest jeder, überall.
_UMSCHRIFT = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    "ß": "ss", "é": "e", "è": "e", "à": "a", "ç": "c",
})


def dateiname(name: str) -> str:
    """Ein fester Dateiname ohne Datum – für Sicherungen, die ersetzt werden.

    Wer wöchentlich denselben Stand überschreibt, will keine wachsende
    Sammlung, sondern eine Datei, die immer aktuell ist. Die Versionen
    dazu führt bei Nextcloud ohnehin der Server.
    """
    umgeschrieben = (name or "Mailarchiv").translate(_UMSCHRIFT)
    sauber = "".join(
        "-" if z in '\\/:*?"<>| ' else z
        for z in umgeschrieben
        if z.isascii() or z.isalnum()
    ).strip("-")
    return f"MailBurg-{sauber or 'Archiv'}.{_endung()}"


def _endung() -> str:
    try:
        import zstandard  # noqa: F401
    except ImportError:
        return "tar.xz"
    return "tar.zst"


def vorschlag(archiv_pfad: Path, name: str = "") -> str:
    """Ein Dateiname mit Datum – Sicherungen will man unterscheiden."""
    stamm = name or Path(archiv_pfad).name or "Mailarchiv"
    try:
        import zstandard  # noqa: F401

        endung = "tar.zst"
    except ImportError:
        endung = "tar.xz"
    return f"{stamm}-{datetime.now():%Y-%m-%d}.{endung}"


#: Legt MailBurg im Sicherungsordner ab, um ihn wiederzuerkennen.
#:
#: **Wozu.** Eine Sicherung schreibt nach ``/mnt/…/Storage-Box/``. Ist
#: das ein Einhängepunkt und die Platte hängt nicht, dann existiert der
#: Ordner trotzdem – leer, auf der Systemplatte. ``mkdir -p`` legt den
#: Rest an, das Packen läuft durch, und am Ende steht eine Sicherung an
#: einem Ort, den niemand gemeint hat. Auf derselben Platte wie das
#: Archiv womöglich, also genau dort, wo sie im Ernstfall mit
#: verlorengeht.
#:
#: Auffallen würde das erst, wenn man die Sicherung braucht. Bis dahin
#: läuft der Zeitplan Monat für Monat und meldet Erfolg.
#:
#: Die Marke ist der Beweis, dass hier schon einmal etwas lag. Fehlt sie
#: in einem Ordner, in den zuvor gesichert wurde, ist es nicht mehr
#: derselbe Ort.
MARKE = ".mailburg-sicherungsziel"


def marke_setzen(ordner: Path) -> None:
    """Zeichnet einen Ordner als Sicherungsziel aus."""
    from datetime import datetime

    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / MARKE).write_text(
        "Dieser Ordner ist ein Sicherungsziel von MailBurg.\n"
        "\n"
        "Die Datei dient als Wiedererkennung: Fehlt sie, geht MailBurg\n"
        "davon aus, dass der Datenträger nicht eingehängt ist, und\n"
        "sichert lieber gar nicht als an den falschen Ort.\n"
        "\n"
        f"Angelegt am {datetime.now().strftime('%d.%m.%Y um %H:%M')}.\n",
        encoding="utf-8",
    )


def _geraet(pfad: Path) -> int:
    """Auf welchem Datenträger ein Pfad liegt – 0, wenn unbekannt."""
    versuch = pfad
    for _ in range(40):
        try:
            return versuch.stat().st_dev
        except OSError:
            if versuch.parent == versuch:
                return 0
            versuch = versuch.parent
    return 0


def ziel_pruefen(archiv_pfad: Path, ziel: Path, *,
                 anlegen: bool = False) -> tuple[bool, str]:
    """Sagt, ob an dieses Ziel gesichert werden darf – und sonst warum nicht.

    ``anlegen`` gilt für den Fall, dass jemand danebensteht: Dann darf
    ein neuer Ordner entstehen und wird ausgezeichnet. Im Zeitplan ist
    das anders – dort ist ein fehlender Ordner kein Anlass, einen neuen
    zu erfinden, sondern der Hinweis, dass die Platte fehlt.
    """
    archiv_pfad = Path(archiv_pfad)
    ordner = Path(ziel)
    if ordner.suffix:
        ordner = ordner.parent

    if (ordner / MARKE).is_file():
        return True, ""

    if not ordner.exists() or not any(ordner.iterdir()):
        if anlegen:
            marke_setzen(ordner)
            return True, ""
        return False, (
            f"Der Sicherungsordner {ordner} ist leer oder nicht "
            f"vorhanden. Wenn dort ein Datenträger eingehängt sein "
            f"sollte – eine externe Platte, ein Netzlaufwerk, eine "
            f"Storage Box –, dann hängt er gerade nicht. Es wurde "
            f"nichts gesichert. Eine Sicherung an den falschen Ort wäre "
            f"schlimmer als keine: Sie stünde da und sähe richtig aus."
        )

    # Der Ordner ist nicht leer, trägt aber keine Marke: gewachsener
    # Bestand aus der Zeit vor dieser Prüfung. Nachtragen statt
    # verweigern - wer dort schon Sicherungen liegen hat, soll nicht
    # plötzlich vor einem Fehler stehen.
    try:
        marke_setzen(ordner)
        return True, ""
    except OSError as exc:
        return False, f"In {ordner} lässt sich nicht schreiben: {exc}"


def gleiche_platte(archiv_pfad: Path, ziel: Path) -> bool:
    """Ob Sicherung und Archiv auf demselben Datenträger lägen.

    Eine Sicherung neben dem Original geht mit ihm zusammen verloren –
    bei einem Plattenschaden, bei einem versehentlichen Löschen des
    ganzen Ordners, bei einem verschlüsselnden Schädling. Der Hinweis
    stand bisher nur im Text des Einrichtungsfensters; geprüft wurde er
    nicht.
    """
    ordner = Path(ziel)
    if ordner.suffix:
        ordner = ordner.parent
    a, b = _geraet(Path(archiv_pfad)), _geraet(ordner)
    return bool(a) and a == b


def _zielgroesse(ziel: Path) -> int:
    try:
        return ziel.stat().st_size
    except OSError:
        return 0


def packen(archiv_pfad: Path, ziel: Path, *, fortschritt=None,
           abbruch=None) -> Befund:
    """Packt ein Archivverzeichnis in eine Datei.

    ``fortschritt`` bekommt Anzahl und Gesamtzahl der Dateien,
    ``abbruch`` wird zwischen den Dateien gefragt. Bricht jemand ab,
    wird die halbfertige Datei entfernt: Eine Sicherung, die zur Hälfte
    dasteht, ist gefährlicher als gar keine – man hält sie für eine.

    **Geschrieben wird erst daneben, dann umbenannt.** Wer eine
    Sicherung wöchentlich unter demselben Namen ersetzt, hätte sonst
    ein Zeitfenster von Minuten, in dem die alte schon überschrieben
    und die neue noch nicht fertig ist. Stürzt der Rechner genau dann
    ab, ist beides weg. Das Umbenennen am Ende geschieht in einem Zug.
    """
    archiv_pfad = Path(archiv_pfad)
    ziel = Path(ziel)
    if not (archiv_pfad / "archive.json").is_file():
        raise SicherungFehler(f"In {archiv_pfad} liegt kein Archiv.")

    dateien = sorted(
        p for p in archiv_pfad.rglob("*")
        if p.is_file() and p.name != ".mailburg-lock"
    )
    befund = Befund(ziel=ziel, dateien=len(dateien))
    befund.quelle_bytes = sum(p.stat().st_size for p in dateien)

    ziel.parent.mkdir(parents=True, exist_ok=True)
    # Daneben schreiben, am Ende umbenennen. Der Name beginnt mit einem
    # Punkt, damit ein Cloud-Programm die halbfertige Datei gar nicht
    # erst hochlädt.
    vorlaeufig = ziel.with_name(f".{ziel.name}.unfertig")
    try:
        # Die Endung des *endgültigen* Ziels entscheidet über das
        # Packverfahren, nicht die der Arbeitsdatei - die heißt ja
        # ".unfertig".
        with _stream(vorlaeufig, ziel.suffix) as roh:
            # "w|" statt "w": ein fortlaufender Strom, der nicht
            # zurückspringt. Nur so lässt er sich durch einen Kompressor
            # schieben, ohne alles im Speicher zu halten.
            with tarfile.open(fileobj=roh, mode="w|") as bündel:
                for nummer, pfad in enumerate(dateien, 1):
                    if abbruch is not None and abbruch():
                        raise _Abgebrochen
                    bündel.add(pfad, arcname=str(pfad.relative_to(archiv_pfad)))
                    if fortschritt:
                        fortschritt(nummer, len(dateien))
    except _Abgebrochen:
        vorlaeufig.unlink(missing_ok=True)
        raise SicherungFehler("Abgebrochen – die halbe Datei wurde entfernt.")
    except OSError as exc:
        vorlaeufig.unlink(missing_ok=True)
        raise SicherungFehler(str(exc)) from exc

    try:
        vorlaeufig.replace(ziel)
    except OSError as exc:
        vorlaeufig.unlink(missing_ok=True)
        raise SicherungFehler(
            f"Die fertige Datei ließ sich nicht ablegen: {exc}"
        ) from exc

    befund.ziel_bytes = _zielgroesse(ziel)
    return befund


def entpacken(datei: Path, ziel: Path, *, fortschritt=None) -> Befund:
    """Holt ein gesichertes Archiv wieder heraus.

    **Das Ziel muss leer sein.** In ein vorhandenes Archiv hinein zu
    entpacken hieße, zwei Protokolle zu vermischen: Die Hash-Kette der
    Sicherung passt nicht zu der, die schon da ist, und hinterher wäre
    keine von beiden prüfbar. Wer zusammenführen will, entpackt daneben
    und nimmt das eine ins andere auf – dabei bleiben beide Ketten heil.

    **Der Suchindex fehlt anschließend**, denn er wird nicht
    mitgesichert. Er baut sich aus dem Protokoll neu auf.
    """
    datei = Path(datei)
    ziel = Path(ziel)
    if not datei.is_file():
        raise SicherungFehler(f"{datei} gibt es nicht.")
    if ziel.exists() and any(ziel.iterdir()):
        raise SicherungFehler(
            f"{ziel} ist nicht leer. Bitte einen leeren Ordner wählen – "
            f"zwei Archive ineinander ergäben ein Protokoll, das sich "
            f"nicht mehr prüfen lässt."
        )

    befund = Befund(ziel=ziel)
    ziel.mkdir(parents=True, exist_ok=True)
    try:
        with _lesestream(datei) as roh:
            with tarfile.open(fileobj=roh, mode="r|") as bündel:
                for eintrag in bündel:
                    # Kein Pfad, der aus dem Zielordner herausführt. Ein
                    # Bündel aus fremder Hand könnte "../../etc/…"
                    # enthalten; tarfile folgt dem bereitwillig.
                    if eintrag.name.startswith("/") or ".." in Path(
                        eintrag.name
                    ).parts:
                        befund.warnungen.append(
                            f"Übergangen: {eintrag.name}"
                        )
                        continue
                    bündel.extract(eintrag, ziel, filter="data")
                    befund.dateien += 1
                    if fortschritt:
                        fortschritt(befund.dateien, 0)
    except (OSError, tarfile.TarError) as exc:
        raise SicherungFehler(str(exc)) from exc

    if not (ziel / "archive.json").is_file():
        raise SicherungFehler(
            "In der Datei war kein Archiv – archive.json fehlt."
        )
    return befund


def uebernehmen(ziel_archiv, datei: Path, *, fortschritt=None,
                abbruch=None) -> Befund:
    """Nimmt die Mails einer Sicherung in ein vorhandenes Archiv auf.

    Anders als :func:`entpacken` entsteht kein zweites Archiv: Die
    Nachrichten wandern in das gerade geöffnete, mit ihrem
    ursprünglichen Postfach und Ordner. Woher sie stammen, steht im
    Protokoll der Sicherung – deshalb braucht es dafür keinen Suchindex,
    der ja ohnehin nicht mitgesichert wird.

    **Doppelte erkennt das Archiv selbst.** Eine Mail, die schon da ist,
    wird nicht zweimal abgelegt; sie bekommt höchstens einen weiteren
    Fundort. Man kann dieselbe Sicherung also gefahrlos zweimal
    einlesen.
    """
    import tempfile

    from mailburg.core.archive import Archive

    datei = Path(datei)
    befund = Befund(ziel=Path(getattr(ziel_archiv, "root", "")))

    with tempfile.TemporaryDirectory(prefix="mailburg-sicherung-") as zwischen:
        ausgepackt = Path(zwischen) / "archiv"
        entpacken(datei, ausgepackt)

        # Nur lesend und ohne Index: Wir brauchen die Rohdaten und die
        # Angaben aus dem Protokoll, sonst nichts.
        with Archive.open(ausgepackt, exclusive=False) as quelle:
            eintraege = [
                e for e in quelle.journal.read_all()
                if e.get("op") == "add" and e.get("hash")
            ]
            for nummer, eintrag in enumerate(eintraege, 1):
                if abbruch is not None and abbruch():
                    break
                try:
                    roh = quelle.store.get(eintrag["hash"], eintrag.get("bucket", ""))
                except (OSError, KeyError) as exc:
                    befund.warnungen.append(
                        f"{eintrag.get('subject', '(ohne Betreff)')}: {exc}"
                    )
                    continue
                ziel_archiv.add(
                    roh,
                    account=eintrag.get("account", "Sicherung"),
                    folder=eintrag.get("folder", ""),
                )
                befund.dateien += 1
                if fortschritt:
                    fortschritt(nummer, len(eintraege))
    return befund


def _lesestream(datei: Path):
    """Öffnet eine Sicherung zum Lesen, passend zu ihrer Endung."""
    if datei.suffix == ".zst":
        try:
            import zstandard
        except ImportError as exc:
            raise SicherungFehler(
                "Diese Sicherung ist mit Zstandard gepackt, das hier "
                "fehlt. Nachrüsten mit: pip install zstandard"
            ) from exc
        return zstandard.ZstdDecompressor().stream_reader(datei.open("rb"))
    import lzma

    return lzma.open(datei, "rb")


def _stream(ziel: Path, endung: str = ""):
    """Öffnet das Ziel zum Schreiben, passend zur gewünschten Endung.

    Zstandard, wenn vorhanden – es packt bei dieser Stufe schneller, als
    eine Festplatte schreibt, kostet also praktisch nichts. Sonst LZMA,
    das überall dabei ist. Die Endung sagt, was drin ist; wer die Datei
    in zehn Jahren findet, soll sie ohne MailBurg auspacken können.
    """
    if (endung or ziel.suffix) == ".zst":
        try:
            import zstandard
        except ImportError:
            pass
        else:
            return zstandard.ZstdCompressor(level=STUFE).stream_writer(
                ziel.open("wb")
            )
    import lzma

    # Niedrige Stufe: Die Mails sind schon komprimiert, mehr Aufwand
    # bringt bei ihnen nichts und dauert das Zehnfache.
    return lzma.open(ziel, "wb", preset=1)


class _Abgebrochen(Exception):
    """Nur für den Weg nach draußen."""
