"""MailBurg auf der Kommandozeile.

Solange die grafische Oberfläche noch nicht steht, ist das der Weg ins
Archiv. Sie bleibt aber auch danach erhalten – für Sicherungsläufe im
Hintergrund und für alles, was sich in einer Zeitsteuerung anstoßen lässt,
ist sie ohnehin das bessere Werkzeug.
"""

from __future__ import annotations

import argparse
import getpass
import sys
import time
from pathlib import Path

from mailburg import APP_NAME, __version__
from mailburg.core import accounts
from mailburg.core.accounts import Konto, Kontenliste
from mailburg.core.archive import Archive, ArchiveError, ArchiveLocked, Mode
from mailburg.core.importer import importieren
from mailburg.core.retention import Jurisdiction, describe
from mailburg.core.sync import Abrufzustand
from mailburg.extract import pdf
from mailburg.search.query import QueryError, describe_syntax
from mailburg.sources import local
from mailburg.sources.imap import ImapFehler, ImapSource


def _human_size(count: int) -> str:
    """Bytezahl in etwas, das man vorlesen kann."""
    value = float(count)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def cmd_anlegen(args: argparse.Namespace) -> int:
    """Legt ein neues Archiv an."""
    mode = Mode(args.modus)
    archive = Archive.create(
        Path(args.pfad),
        mode=mode,
        jurisdiction=Jurisdiction(args.recht),
        name=args.name or "",
    )
    try:
        print(f"Archiv angelegt: {archive.root}")
        print(f"  Kennung:     {archive.uuid}")
        print(f"  Betriebsart: {mode.value}")
        if mode.is_business:
            print(f"  Fristen:     {describe(archive.policy)}")
            print()
            print("  Hinweis: MailBurg unterstützt einen revisionssicheren Betrieb,")
            print("  stellt ihn aber nicht allein her. Dazu gehören außerdem eine")
            print("  Verfahrensdokumentation und geregelte Abläufe im Betrieb.")
        else:
            print()
            print("  Privatarchiv: keine Aufbewahrungsfristen, Löschen jederzeit")
            print("  möglich. Für geschäftliche Post stattdessen --modus geschaeftlich.")
    finally:
        archive.close()
    return 0


def cmd_importieren(args: argparse.Namespace) -> int:
    """Liest eine Mailquelle ins Archiv ein."""
    try:
        source = local.open_path(Path(args.quelle), args.konto or "")
    except (ValueError, FileNotFoundError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    print(f"Quelle: {source.describe()}")
    print(f"Konto:  {source.account}")

    mit_text = not args.ohne_anhangstext
    if mit_text:
        weg = pdf.verfuegbar()
        if weg is None:
            print(
                "Hinweis: Weder pdftotext noch pypdf gefunden – PDF-Anhänge\n"
                "         werden nicht durchsuchbar. Abhilfe unter Arch/Manjaro:\n"
                "         sudo pacman -S poppler",
                file=sys.stderr,
            )
    print(f"Anhänge im Volltext: {'ja' if mit_text else 'nein'}")

    with Archive.open(Path(args.archiv)) as archive:
        started = time.monotonic()

        def fortschritt(stat) -> None:
            print(f"  … {stat.gelesen} gelesen, {stat.neu} neu", end="\r", flush=True)

        def auf_fehler(nachricht, exc: Exception) -> None:
            if args.ausführlich:
                print(f"  übersprungen ({nachricht.folder}): {exc}", file=sys.stderr)

        stat = importieren(
            archive,
            source,
            mit_anhangstext=mit_text,
            fortschritt=fortschritt,
            auf_fehler=auf_fehler,
        )

        print(" " * 60, end="\r")
        if stat.neu:
            print("Verdichte den Suchindex …")
            archive.index.optimize()

        seconds = time.monotonic() - started
        rate = stat.gelesen / seconds if seconds else 0
        print(f"Fertig: {stat}")
        print(f"Dauer: {seconds:.1f} s ({rate:.0f} Mails/s)")

        if mit_text:
            print(f"Mit Anhangstext: {stat.mit_anhangstext} Mails")
            if stat.eingescannt:
                print(
                    f"Davon {stat.eingescannt} PDF ohne Textebene – vermutlich "
                    f"eingescannt und daher nicht durchsuchbar."
                )

    source.close()
    return 0


# ------------------------------------------------------------------- Konten


def _passwort_besorgen(konto: Konto, *, fragen: bool = True) -> str:
    """Holt das Passwort aus dem Schlüsselbund oder fragt danach."""
    passwort = accounts.passwort_holen(konto)
    if passwort:
        return passwort
    if not fragen:
        return ""
    return getpass.getpass(f"Passwort für {konto.benutzer} auf {konto.server}: ")


def cmd_konten_liste(args: argparse.Namespace) -> int:
    """Zeigt die eingerichteten Postfächer."""
    liste = Kontenliste()
    if not len(liste):
        print("Noch kein Konto eingerichtet. Anlegen mit 'mailburg konten hinzufuegen'.")
        return 0

    if not accounts.schluesselbund_verfuegbar():
        print(
            "Hinweis: Kein Schlüsselbund erreichbar – die Passwörter werden bei\n"
            "         jedem Abruf neu erfragt. Unter Arch/Manjaro hilft:\n"
            "         sudo pacman -S gnome-keyring python-keyring\n",
            file=sys.stderr,
        )

    for konto in liste.konten:
        zustand = "aktiv" if konto.aktiv else "stillgelegt"
        gemerkt = "Passwort gemerkt" if accounts.passwort_holen(konto) else "kein Passwort"
        print(f"  {konto.beschreibung()}  [{zustand}, {gemerkt}]")
        if args.ausführlich and konto.ausschluss:
            print(f"      übergangen: {', '.join(konto.ausschluss)}")
    return 0


def cmd_konten_hinzufuegen(args: argparse.Namespace) -> int:
    """Richtet ein Postfach ein und prüft es gleich."""
    konto = Konto(
        name=args.name,
        server=args.server,
        benutzer=args.benutzer or args.name,
        port=args.port,
        ssl=not args.starttls,
    )
    passwort = getpass.getpass(f"Passwort für {konto.benutzer} auf {konto.server}: ")
    if not passwort:
        print("Ohne Passwort geht es nicht.", file=sys.stderr)
        return 2

    # Erst prüfen, dann speichern. Ein Konto, das sich nicht anmelden kann,
    # in der Liste stehen zu haben, führt nur dazu, dass jeder nächtliche
    # Abruf mit einem Fehler endet.
    print(f"Verbinde mit {konto.server} …")
    try:
        quelle = ImapSource(konto, passwort)
    except ImapFehler as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    try:
        ordner = quelle.folders()
    finally:
        quelle.close()

    liste = Kontenliste()
    try:
        liste.hinzufuegen(konto)
    except ValueError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    if accounts.passwort_setzen(konto, passwort):
        print("Passwort im Schlüsselbund abgelegt.")
    else:
        print(
            "Achtung: Kein Schlüsselbund erreichbar – das Passwort wird bei\n"
            "         jedem Abruf neu erfragt. In eine Datei geschrieben wird\n"
            "         es nicht.",
            file=sys.stderr,
        )

    print(f"Konto '{konto.name}' eingerichtet. {len(ordner)} Ordner werden archiviert:")
    for name in ordner[:15]:
        print(f"    {name}")
    if len(ordner) > 15:
        print(f"    … und {len(ordner) - 15} weitere")
    print()
    print(f"  Übergangen werden: {', '.join(konto.ausschluss)}")
    return 0


def cmd_konten_entfernen(args: argparse.Namespace) -> int:
    """Nimmt ein Postfach aus der Liste."""
    liste = Kontenliste()
    konto = liste.finden(args.name)
    if konto is None:
        print(f"Ein Konto namens '{args.name}' gibt es nicht.", file=sys.stderr)
        return 2

    accounts.passwort_loeschen(konto)
    liste.entfernen(args.name)
    print(f"Konto '{args.name}' entfernt. Die bereits archivierten Mails bleiben.")
    return 0


def cmd_konten_pruefen(args: argparse.Namespace) -> int:
    """Meldet sich an und zeigt, was archiviert würde."""
    liste = Kontenliste()
    konten = [liste.finden(args.name)] if args.name else liste.konten
    if not konten or konten[0] is None:
        print("Kein passendes Konto gefunden.", file=sys.stderr)
        return 2

    fehler = 0
    for konto in konten:
        print(f"{konto.beschreibung()}")
        try:
            quelle = ImapSource(konto, _passwort_besorgen(konto))
        except ImapFehler as exc:
            print(f"  FEHLER: {exc}", file=sys.stderr)
            fehler += 1
            continue
        try:
            ordner = quelle.folders()
            print(f"  Anmeldung in Ordnung, {len(ordner)} Ordner zum Archivieren:")
            for name in ordner:
                print(f"    {name}")
        finally:
            quelle.close()
    return 1 if fehler else 0


def cmd_abrufen(args: argparse.Namespace) -> int:
    """Holt neue Mails aus den Postfächern ins Archiv."""
    liste = Kontenliste()
    if args.konto:
        konto = liste.finden(args.konto)
        if konto is None:
            print(f"Ein Konto namens '{args.konto}' gibt es nicht.", file=sys.stderr)
            return 2
        konten = [konto]
    else:
        konten = liste.aktive()

    if not konten:
        print(
            "Kein aktives Konto. Einrichten mit 'mailburg konten hinzufuegen'.",
            file=sys.stderr,
        )
        return 2

    mit_text = not args.ohne_anhangstext
    fehler = 0
    neu_gesamt = 0

    # Im leisen Betrieb wird nur gemeldet, was von Belang ist. Ein Abruf,
    # der alle zehn Minuten läuft, würde sonst das Systemprotokoll mit
    # Meldungen darüber füllen, dass nichts zu tun war.
    laut = not args.leise

    def sagen(text: str = "") -> None:
        if laut:
            print(text)

    with Archive.open(Path(args.archiv)) as archive:
        zustand = Abrufzustand(archive.uuid)
        if args.voll:
            sagen("Vollabruf: Der bisherige Stand wird nicht berücksichtigt.")

        for konto in konten:
            sagen(f"\n{konto.beschreibung()}")
            try:
                quelle = ImapSource(
                    konto,
                    _passwort_besorgen(konto),
                    hoechststand=lambda ordner, k=konto: archive.index.max_uid(
                        k.name, ordner
                    ),
                    zustand=zustand,
                    voll=args.voll,
                    ordner=args.ordner or None,
                )
            except ImapFehler as exc:
                print(f"  FEHLER: {exc}", file=sys.stderr)
                fehler += 1
                continue

            started = time.monotonic()

            def fortschritt(stat) -> None:
                if laut:
                    print(f"  … {stat.gelesen} geholt, {stat.neu} neu", end="\r", flush=True)

            def auf_fehler(nachricht, exc: Exception, k=konto) -> None:
                # Vormerken, damit die Mail beim nächsten Lauf noch einmal
                # angefordert wird. Ohne das zöge der Höchststand an ihr
                # vorbei und sie fehlte für immer.
                if nachricht.uid is not None:
                    zustand.vormerken(k.name, nachricht.folder, nachricht.uid)
                if args.ausführlich:
                    print(
                        f"  gescheitert ({nachricht.folder}, UID {nachricht.uid}): {exc}",
                        file=sys.stderr,
                    )

            try:
                stat = importieren(
                    archive,
                    quelle,
                    mit_anhangstext=mit_text,
                    fortschritt=fortschritt,
                    auf_fehler=auf_fehler,
                )
            finally:
                # Der Zustand muss auch dann auf die Platte, wenn der Lauf
                # abbricht: Sonst gehen die Vormerkungen der gescheiterten
                # Mails verloren.
                zustand.speichern()
                quelle.close()

            neu_gesamt += stat.neu
            seconds = time.monotonic() - started

            if laut:
                print(" " * 60, end="\r")
                print(f"  {stat} ({seconds:.1f} s)")
            elif stat.neu:
                # Auch leise: dass etwas ins Archiv ging, gehört ins Protokoll.
                print(f"{konto.name}: {stat.neu} neu ({seconds:.1f} s)")

            for warnung in quelle.warnungen:
                print(f"  Hinweis: {warnung}", file=sys.stderr)
            if stat.fehlgeschlagen:
                print(
                    f"  {stat.fehlgeschlagen} Mails sind vorgemerkt und werden beim "
                    f"nächsten Abruf erneut geholt.",
                    file=sys.stderr if not laut else sys.stdout,
                )

        sagen()
        # Nur wenn wirklich etwas dazugekommen ist. Das Verdichten geht über
        # den ganzen Volltextindex; bei einem Abruf alle zehn Minuten wäre
        # das den halben Tag über Arbeit für nichts.
        if neu_gesamt:
            archive.index.optimize()
    return 1 if fehler else 0


def cmd_suchen(args: argparse.Namespace) -> int:
    """Durchsucht das Archiv."""
    expression = " ".join(args.ausdruck)

    with Archive.open(Path(args.archiv), exclusive=False) as archive:
        started = time.monotonic()
        try:
            hits = archive.index.search(expression, limit=args.limit)
            total = archive.index.count(expression)
        except QueryError as exc:
            print(f"Fehler im Suchausdruck: {exc}", file=sys.stderr)
            return 2

        elapsed = (time.monotonic() - started) * 1000

        if not hits:
            print(f"Keine Treffer für: {expression or '(alles)'}")
            return 1

        for hit in hits:
            date = (hit.date or "")[:10] or "  (kein Datum)"
            marker = "📎" if hit.has_attachments else "  "
            print(f"{date} {marker} {hit.subject[:60]:<60} {hit.sender_display[:35]}")
            if args.ausführlich:
                print(f"           {hit.hash[:16]}…  {_human_size(hit.size)}  {hit.bucket}")

        print()
        print(f"{len(hits)} von {total} Treffern in {elapsed:.0f} ms")
    return 0


def cmd_pruefen(args: argparse.Namespace) -> int:
    """Prüft Hash-Kette und Ablage."""
    with Archive.open(Path(args.archiv), exclusive=False) as archive:
        print(f"Prüfe {archive.name} …")
        report = archive.verify()

        if report["chain_ok"]:
            print(f"  Hash-Kette:  unversehrt ({report['chain_entries']} Einträge)")
        else:
            print(f"  Hash-Kette:  BESCHÄDIGT ({len(report['chain_errors'])} Fundstellen)")
            for problem in report["chain_errors"][:20]:
                print(f"    - {problem}")

        print(f"  Erwartet:    {report['expected']} Mails laut Journal")
        print(f"  Vorhanden:   {report['on_disk']} Dateien in der Ablage")

        if report["missing"]:
            print(f"  FEHLEND:     {len(report['missing'])} Mails ohne Datei")
            for digest in report["missing"][:10]:
                print(f"    - {digest[:16]}…")

        if report["unexpected"]:
            print(f"  UNBEKANNT:   {len(report['unexpected'])} Dateien ohne Journaleintrag")
            print("               Diese Mails wurden nicht über MailBurg aufgenommen.")
            for digest in report["unexpected"][:10]:
                print(f"    - {digest[:16]}…")

        print()
        print("Ergebnis: " + ("alles in Ordnung" if report["ok"] else "Beanstandungen, siehe oben"))
    return 0 if report["ok"] else 1


def cmd_neuaufbau(args: argparse.Namespace) -> int:
    """Baut den Suchindex neu."""
    with Archive.open(Path(args.archiv)) as archive:
        print("Baue den Suchindex neu. Das Archiv selbst wird dabei nur gelesen.")
        started = time.monotonic()

        def progress(done: int, total: int) -> None:
            print(f"  … {done} von {total}", end="\r", flush=True)

        count = archive.rebuild_index(progress=progress)
        print(" " * 60, end="\r")
        print(f"Fertig: {count} Mails in {time.monotonic() - started:.1f} s indiziert.")
    return 0


def cmd_siegel(args: argparse.Namespace) -> int:
    """Setzt ein Siegel über den aktuellen Stand."""
    with Archive.open(Path(args.archiv)) as archive:
        entry = archive.seal()
        print(f"Siegel gesetzt über {entry['count']} Einträge.")
        print(f"  Stand: {entry['covers'][:32]}…")
        print(f"  Zeit:  {entry['ts']}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Zeigt, was im Archiv steckt."""
    with Archive.open(Path(args.archiv), exclusive=False) as archive:
        stats = archive.index.statistics()
        print(f"{archive.name}")
        print(f"  Ort:          {archive.root}")
        print(f"  Kennung:      {archive.uuid}")
        print(f"  Betriebsart:  {archive.mode.value}")
        if archive.mode.is_business:
            print(f"  Fristen:      {describe(archive.policy)}")
        print(f"  Mails:        {stats['mails']:,}".replace(",", "."))
        print(f"  Anhänge:      {stats['anhaenge']:,}".replace(",", "."))
        print(f"  Fundorte:     {stats['fundorte']:,}".replace(",", "."))
        print(f"  Rohgröße:     {_human_size(stats['bytes'])}")
        print(f"  Auf Platte:   {_human_size(archive.store.disk_usage())}")
        print(f"  Journal:      {archive.journal.count} Einträge")

        accounts = archive.index.accounts()
        if accounts:
            print()
            print("  Konten und Ordner:")
            current = None
            for account, folder, count in accounts[:40]:
                if account != current:
                    print(f"    {account}")
                    current = account
                print(f"      {folder:<45} {count:>7}")
            if len(accounts) > 40:
                print(f"      … und {len(accounts) - 40} weitere")
    return 0


def cmd_hilfe_suche(args: argparse.Namespace) -> int:
    """Erklärt die Suchsprache."""
    print(describe_syntax())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mailburg",
        description=f"{APP_NAME} – Archiv für E-Mail, an einem Ort Ihrer Wahl.",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    parser.add_argument(
        "-v", "--ausführlich", action="store_true", help="mehr Einzelheiten ausgeben"
    )

    subparsers = parser.add_subparsers(dest="befehl", required=True)

    p = subparsers.add_parser("anlegen", help="ein neues Archiv anlegen")
    p.add_argument("pfad", help="Verzeichnis für das Archiv")
    p.add_argument(
        "--modus",
        choices=[m.value for m in Mode],
        default=Mode.PRIVAT.value,
        help="privat (Standard) oder geschaeftlich mit Fristen und Hash-Kette",
    )
    p.add_argument(
        "--recht",
        choices=[j.value for j in Jurisdiction],
        default=Jurisdiction.DE.value,
        help="Rechtsraum für die Aufbewahrungsfristen",
    )
    p.add_argument("--name", help="Anzeigename des Archivs")
    p.set_defaults(func=cmd_anlegen)

    p = subparsers.add_parser("importieren", help="Mails aus einer Quelle einlesen")
    p.add_argument("archiv", help="Verzeichnis des Archivs")
    p.add_argument("quelle", help="Thunderbird-Profil, Maildir oder MBOX-Datei")
    p.add_argument("--konto", help="Name, unter dem die Mails erscheinen sollen")
    p.add_argument(
        "--ohne-anhangstext",
        action="store_true",
        help="Anhänge nicht im Volltext erfassen (deutlich schneller, "
             "dafür sind PDF und Office-Dateien nicht durchsuchbar)",
    )
    p.set_defaults(func=cmd_importieren)

    p = subparsers.add_parser("konten", help="Postfächer einrichten und prüfen")
    konten_befehle = p.add_subparsers(dest="unterbefehl", required=True)

    k = konten_befehle.add_parser("liste", help="eingerichtete Postfächer zeigen")
    k.set_defaults(func=cmd_konten_liste)

    k = konten_befehle.add_parser("hinzufuegen", help="ein Postfach einrichten")
    k.add_argument("name", help="Kurzname, unter dem die Mails im Archiv erscheinen")
    k.add_argument("--server", required=True, help="IMAP-Server, etwa imap.gmail.com")
    k.add_argument("--benutzer", help="Anmeldename, meist die Mailadresse")
    k.add_argument("--port", type=int, default=993, help="Standard: 993 (IMAPS)")
    k.add_argument(
        "--starttls",
        action="store_true",
        help="unverschlüsselt verbinden und auf TLS hochstufen (Port meist 143)",
    )
    k.set_defaults(func=cmd_konten_hinzufuegen)

    k = konten_befehle.add_parser("entfernen", help="ein Postfach aus der Liste nehmen")
    k.add_argument("name")
    k.set_defaults(func=cmd_konten_entfernen)

    k = konten_befehle.add_parser("pruefen", help="Anmeldung und Ordner prüfen")
    k.add_argument("name", nargs="?", help="ohne Angabe werden alle geprüft")
    k.set_defaults(func=cmd_konten_pruefen)

    p = subparsers.add_parser("abrufen", help="neue Mails aus den Postfächern holen")
    p.add_argument("archiv", help="Verzeichnis des Archivs")
    p.add_argument("--konto", help="nur dieses Konto abrufen")
    p.add_argument(
        "--ordner",
        nargs="+",
        metavar="NAME",
        help="nur diese Ordner abrufen, mit ihrem angezeigten Namen",
    )
    p.add_argument(
        "--voll",
        action="store_true",
        help="alles holen statt nur das Neue. Doppelt abgelegt wird dabei "
             "nichts – die Ablage erkennt jede Mail an ihrem Inhalt wieder.",
    )
    p.add_argument(
        "--ohne-anhangstext",
        action="store_true",
        help="Anhänge nicht im Volltext erfassen",
    )
    p.add_argument(
        "--leise",
        action="store_true",
        help="nur melden, wenn etwas ankam oder schiefging – für den "
             "Abruf im Hintergrund, damit das Systemprotokoll lesbar bleibt",
    )
    p.set_defaults(func=cmd_abrufen)

    p = subparsers.add_parser("suchen", help="das Archiv durchsuchen")
    p.add_argument("archiv")
    p.add_argument("--limit", type=int, default=30, help="Höchstzahl der Treffer")
    # REMAINDER, damit ausschließende Begriffe wie "-werbung" nicht als
    # Programmoption gelesen werden. Der Preis: --limit muss vor dem
    # Suchausdruck stehen. Dieselbe Regel gilt bei "git log -- pfad".
    p.add_argument(
        "ausdruck",
        nargs=argparse.REMAINDER,
        help="Suchbegriffe, siehe 'suchhilfe' (nach allen Optionen angeben)",
    )
    p.set_defaults(func=cmd_suchen)

    p = subparsers.add_parser("pruefen", help="Hash-Kette und Ablage prüfen")
    p.add_argument("archiv")
    p.set_defaults(func=cmd_pruefen)

    p = subparsers.add_parser("neuaufbau", help="den Suchindex neu erzeugen")
    p.add_argument("archiv")
    p.set_defaults(func=cmd_neuaufbau)

    p = subparsers.add_parser("siegel", help="ein Siegel über den Stand setzen")
    p.add_argument("archiv")
    p.set_defaults(func=cmd_siegel)

    p = subparsers.add_parser("info", help="Kennzahlen des Archivs zeigen")
    p.add_argument("archiv")
    p.set_defaults(func=cmd_info)

    p = subparsers.add_parser("suchhilfe", help="die Suchsprache erklären")
    p.set_defaults(func=cmd_hilfe_suche)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ArchiveLocked as exc:
        print(f"Archiv gesperrt:\n{exc}", file=sys.stderr)
        return 3
    except ArchiveError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nAbgebrochen.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
