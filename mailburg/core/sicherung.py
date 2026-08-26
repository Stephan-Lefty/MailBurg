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


def vorschlag(archiv_pfad: Path, name: str = "") -> str:
    """Ein Dateiname mit Datum – Sicherungen will man unterscheiden."""
    stamm = name or Path(archiv_pfad).name or "Mailarchiv"
    try:
        import zstandard  # noqa: F401

        endung = "tar.zst"
    except ImportError:
        endung = "tar.xz"
    return f"{stamm}-{datetime.now():%Y-%m-%d}.{endung}"


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
    try:
        with _stream(ziel) as roh:
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
        ziel.unlink(missing_ok=True)
        raise SicherungFehler("Abgebrochen – die halbe Datei wurde entfernt.")
    except OSError as exc:
        ziel.unlink(missing_ok=True)
        raise SicherungFehler(str(exc)) from exc

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


def _stream(ziel: Path):
    """Öffnet das Ziel zum Schreiben, passend zu seiner Endung.

    Zstandard, wenn vorhanden – es packt bei dieser Stufe schneller, als
    eine Festplatte schreibt, kostet also praktisch nichts. Sonst LZMA,
    das überall dabei ist. Die Endung sagt, was drin ist; wer die Datei
    in zehn Jahren findet, soll sie ohne MailBurg auspacken können.
    """
    if ziel.suffix == ".zst":
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
