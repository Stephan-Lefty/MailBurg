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
    if args.proton:
        # Die Proton Mail Bridge lauscht auf dem eigenen Rechner und
        # spricht STARTTLS auf 1143. Wer diese Werte von Hand einträgt,
        # vertippt sich nur.
        server, port, starttls, bruecke = "127.0.0.1", args.port if args.port != 993 else 1143, True, True
    else:
        server, port, starttls, bruecke = args.server, args.port, args.starttls, args.bruecke

    if not server:
        print("Ohne --server geht es nicht.", file=sys.stderr)
        return 2

    konto = Konto(
        name=args.name,
        server=server,
        benutzer=args.benutzer or args.name,
        port=port,
        ssl=not starttls,
        bruecke=bruecke,
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
        print(f"Passwort abgelegt in: {accounts.schluesselbund_name()}")
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


def cmd_konten_uebernehmen(args: argparse.Namespace) -> int:
    """Übernimmt die Einstellungen aus einem Thunderbird-Profil."""
    from mailburg.core import uebernahme

    if args.profil:
        profile = [Path(args.profil)]
    else:
        profile = local.find_thunderbird_profiles()
        if not profile:
            print(
                "Kein Thunderbird-Profil gefunden. Pfad bitte angeben:\n"
                "  mailburg konten uebernehmen ~/.thunderbird/xxxx.default",
                file=sys.stderr,
            )
            return 2

    liste = Kontenliste()
    vergeben = {k.name for k in liste.konten}
    uebernommen = 0

    for pfad in profile:
        try:
            funde = uebernahme.aus_thunderbird(pfad)
        except (FileNotFoundError, OSError) as exc:
            print(f"Fehler: {exc}", file=sys.stderr)
            continue

        print(f"\nProfil {pfad}")
        if not funde:
            print("  Keine Postfächer eingerichtet.")
            continue

        abrufbar = [f for f in funde if f.brauchbar]
        for fund in funde:
            if not fund.brauchbar:
                print(f"  übergangen: {fund.konto.name} ({fund.art.upper()})")
                print(f"      {fund.begruendung}")

        uebernahme.namen_entzerren(abrufbar, vergeben)

        if args.zeigen:
            # Nur nachsehen, nichts anlegen und nach nichts fragen.
            for fund in abrufbar:
                konto = fund.konto
                art = "IMAPS" if konto.ssl else "STARTTLS"
                marke = "  [Brücke auf diesem Rechner]" if konto.ist_lokale_bruecke else ""
                schon = "  – schon eingerichtet" if liste.finden(konto.name) else ""
                print(f"  {konto.name}{schon}")
                print(f"      {konto.benutzer} auf {konto.server}:{konto.port} ({art}){marke}")
            continue

        for fund in abrufbar:
            konto = fund.konto
            if liste.finden(konto.name):
                print(f"  {konto.name}: schon eingerichtet, übersprungen.")
                continue

            verschluesselung = "IMAPS" if konto.ssl else "STARTTLS"
            print(f"\n  {konto.name}")
            print(f"    Server:  {konto.server}:{konto.port} ({verschluesselung})")
            print(f"    Benutzer: {konto.benutzer}")
            if konto.ist_lokale_bruecke:
                print(
                    "    Brückenprogramm auf diesem Rechner (Proton Mail Bridge\n"
                    "      oder ähnlich). Das Passwort erzeugt die Brücke – das\n"
                    "      Kennwort des Anbieterkontos taugt dafür nicht. Und sie\n"
                    "      muss laufen, sonst gibt es beim Abruf nichts zu holen."
                )

            if not args.alle:
                antwort = input("    Übernehmen? [J/n] ").strip().lower()
                if antwort in ("n", "nein"):
                    continue

            # Das Passwort kommt von Hand. Es aus dem Thunderbird-Profil zu
            # holen, wäre technisch möglich und trotzdem falsch – siehe
            # mailburg/core/uebernahme.py.
            passwort = getpass.getpass(f"    Passwort für {konto.benutzer}: ")
            if not passwort:
                print("    Ohne Passwort übersprungen.")
                continue

            if not args.ohne_test:
                try:
                    quelle = ImapSource(konto, passwort)
                except ImapFehler as exc:
                    print(f"    FEHLER: {exc}", file=sys.stderr)
                    print("    Nicht übernommen.")
                    continue
                try:
                    ordner = quelle.folders()
                finally:
                    quelle.close()
                print(f"    Anmeldung in Ordnung, {len(ordner)} Ordner.")

            liste.hinzufuegen(konto)
            if accounts.passwort_setzen(konto, passwort):
                print("    Übernommen, Passwort im Schlüsselbund.")
            else:
                print("    Übernommen. Kein Schlüsselbund – Passwort wird je Abruf erfragt.")
            uebernommen += 1

    print()
    if uebernommen:
        print(f"{uebernommen} Konten übernommen. Abrufen mit:")
        print("    mailburg abrufen ~/Archiv")
        print()
        print("Für den Altbestand lohnt außerdem der Weg über die lokalen Dateien –")
        print("der kommt ohne Passwort aus und holt auch Konten, die es online")
        print("nicht mehr gibt:")
        print("    mailburg importieren ~/Archiv <Profilpfad> --konto alt")
    else:
        print("Nichts übernommen.")
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


def cmd_loeschen(args: argparse.Namespace) -> int:
    """Nimmt Mails eines Postfachs wieder aus dem Archiv.

    **Der Trockenlauf ist die Voreinstellung.** Wer löscht, tut es
    einmal; wer sich vertut, merkt es beim zwanzigsten Mal. Also zeigt
    der Befehl erst, was er täte, und tut es erst auf ausdrückliche
    Ansage.
    """
    with Archive.open(Path(args.archiv)) as archive:
        zeilen = archive.index.db.execute(
            """SELECT DISTINCT m.hash, m.bucket, m.subject
                 FROM messages m JOIN locations l ON l.msg_id = m.id
                WHERE l.account = ?""",
            (args.konto,),
        ).fetchall()
        if not zeilen:
            print(f"Zu '{args.konto}' liegt in diesem Archiv nichts.")
            return 0

        # Nur, was ausschließlich an diesem Postfach hängt. Eine Mail,
        # die auch anderswo gefunden wurde, verlöre sonst mehr als den
        # einen Fundort.
        nur_hier = []
        for digest, bucket, betreff in zeilen:
            andere = archive.index.db.execute(
                """SELECT COUNT(*) FROM locations l JOIN messages m ON m.id = l.msg_id
                    WHERE m.hash = ? AND l.account <> ?""",
                (digest, args.konto),
            ).fetchone()[0]
            if not andere:
                nur_hier.append((digest, bucket, betreff))

        auch_anderswo = len(zeilen) - len(nur_hier)
        print(f"Postfach '{args.konto}' in '{archive.name}':")
        print(f"  {len(zeilen)} Mails, davon {len(nur_hier)} nur hier zu finden.")
        if auch_anderswo:
            print(f"  {auch_anderswo} liegen auch unter einem anderen Postfach "
                  f"und bleiben unangetastet.")

        if not args.wirklich:
            print()
            for _, _, betreff in nur_hier[:10]:
                print(f"   – {(betreff or '(ohne Betreff)')[:66]}")
            if len(nur_hier) > 10:
                print(f"   … und {len(nur_hier) - 10} weitere")
            print()
            print("Das war ein Trockenlauf. Nichts wurde entfernt.")
            print("Zum Ausführen dasselbe noch einmal mit --wirklich.")
            return 0

        if archive.mode.is_business:
            print()
            print("Dies ist ein Geschäftsarchiv: Jede Löschung hinterlässt "
                  "einen Grabstein im Journal.")

        entfernt = 0
        gesperrt = 0
        for digest, bucket, _ in nur_hier:
            try:
                archive.delete(digest, bucket, reason=args.grund,
                               note=args.notiz)
                entfernt += 1
            except Exception as exc:  # Fristen, fehlende Datei
                gesperrt += 1
                if gesperrt <= 3:
                    print(f"  bleibt liegen: {exc}", file=sys.stderr)
        archive.index.commit()
        print(f"\nEntfernt: {entfernt}")
        if gesperrt:
            print(f"Nicht entfernt: {gesperrt} (Aufbewahrungsfrist oder Fehler)")
    return 0


def cmd_konten_zuordnen(args: argparse.Namespace) -> int:
    """Weist ein Postfach einem Archiv zu – oder nimmt es wieder heraus."""
    liste = Kontenliste()
    with Archive.open(Path(args.archiv), exclusive=False) as archive:
        kennung = archive.uuid
        name = archive.name

    if args.loesen:
        if not liste.loesen(args.konto, kennung):
            print(
                f"'{args.konto}' war '{name}' nicht zugeordnet.", file=sys.stderr
            )
            return 2
        print(f"'{args.konto}' gehört nicht mehr zu '{name}'.")
        return 0

    if not liste.zuordnen(args.konto, kennung):
        print(f"Ein Konto namens '{args.konto}' gibt es nicht.", file=sys.stderr)
        return 2
    print(f"'{args.konto}' gehört jetzt zu '{name}'.")
    return 0


def cmd_konten_zuordnung(args: argparse.Namespace) -> int:
    """Zeigt, welches Postfach in welches Archiv geht."""
    liste = Kontenliste()
    if not liste.konten:
        print("Noch kein Postfach eingerichtet.")
        return 0

    for konto in liste.konten:
        zustand = "" if konto.aktiv else "  (abgeschaltet)"
        if konto.archive:
            ziele = ", ".join(konto.archive)
        else:
            ziele = "keinem Archiv zugeordnet – wird nicht abgerufen"
        print(f"{konto.name}{zustand}")
        print(f"   {ziele}")
    return 0


def _konten_waehlen(liste, archive, gewuenscht: str | None, *, laut: bool = True):
    """Welche Postfächer in dieses Archiv gehören – und was fehlt.

    **Ein Postfach ohne Archivzuordnung wird nicht abgerufen.** Das ist
    die unbequemere Voreinstellung und die einzige vertretbare: Post, die
    fälschlich nicht archiviert wurde, holt der nächste Lauf nach. Post,
    die fälschlich in einem Geschäftsarchiv landet, unterliegt dort zehn
    Jahre lang Aufbewahrungsfristen und lässt sich nur mit einem
    Grabstein im Journal wieder herausnehmen.

    Wird ein Postfach ausdrücklich genannt, entscheidet der Aufrufer –
    dann wird die Zuordnung nur angemerkt, nicht erzwungen.

    Gibt ``(konten, fehlermeldung)`` zurück; ist die Meldung gesetzt,
    soll der Aufruf mit Rückgabewert 2 enden.
    """
    if gewuenscht:
        konto = liste.finden(gewuenscht)
        if konto is None:
            return [], f"Ein Konto namens '{gewuenscht}' gibt es nicht."
        if archive.uuid not in konto.archive and laut:
            print(
                f"Hinweis: '{konto.name}' ist diesem Archiv nicht zugeordnet. "
                f"Es wird trotzdem abgerufen, weil Sie es genannt haben.",
                file=sys.stderr,
            )
        return [konto], ""

    konten = liste.fuer_archiv(archive.uuid)
    offen = liste.ohne_archiv()
    if offen and laut:
        # Nicht verschweigen: Wer nach einem Update feststellt, dass
        # nichts mehr ankommt, soll hier lesen, warum.
        namen = ", ".join(k.name for k in offen)
        print(
            f"\n{len(offen)} Postfächer sind keinem Archiv zugeordnet und "
            f"werden übergangen: {namen}\n"
            f"Zuordnen mit: mailburg konten zuordnen <Archiv> <Postfach>",
            file=sys.stderr,
        )
    if not konten:
        return [], (
            "Diesem Archiv ist kein Postfach zugeordnet. "
            "Zuordnen mit 'mailburg konten zuordnen <Archiv> <Postfach>'."
        )
    return konten, ""


def cmd_abrufen(args: argparse.Namespace) -> int:
    """Holt neue Mails aus den Postfächern ins Archiv."""
    liste = Kontenliste()
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
        konten, meldung = _konten_waehlen(liste, archive, args.konto, laut=laut)
        if meldung:
            print(meldung, file=sys.stderr)
            return 2

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
                if mit_text and stat.neu:
                    # Ob ein PDF durchsuchbar wurde oder nur als Dateiname
                    # dasteht, ist der Unterschied zwischen Finden und
                    # Nichtfinden. Das gehört gesagt.
                    print(f"  Mit Anhangstext: {stat.mit_anhangstext} Mails")
                    if stat.eingescannt:
                        print(
                            f"  Davon {stat.eingescannt} PDF ohne Textebene – "
                            f"vermutlich eingescannt und daher nicht durchsuchbar."
                        )
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

        # Erst hier, nicht im finally je Konto: "Zuletzt abgerufen" soll
        # heißen, dass der Lauf durch ist - nicht, dass er begonnen hat.
        zustand.lauf_beendet()
        zustand.speichern()

        sagen()
        # Nur wenn wirklich etwas dazugekommen ist. Das Verdichten geht über
        # den ganzen Volltextindex; bei einem Abruf alle zehn Minuten wäre
        # das den halben Tag über Arbeit für nichts.
        if neu_gesamt:
            archive.index.optimize()

        # Erst wenn die Post im Archiv ist, wird ein Häppchen Texterkennung
        # nachgeschoben. In dieser Reihenfolge, weil Archivieren Pflicht ist
        # und Durchsuchbarmachen Kür - und weil beides dieselbe Sperre am
        # Archiv braucht, also nicht nebeneinander laufen kann.
        if not args.ohne_texterkennung:
            _texterkennung_nachschieben(archive, laut=laut, budget=args.erkennungsbudget)

    return 1 if fehler else 0


def _texterkennung_nachschieben(archive, *, laut: bool, budget: float) -> None:
    """Arbeitet ein Zeitbudget der Warteschlange ab, falls möglich."""
    from mailburg.core import erkennung
    from mailburg.extract import ocr

    warteschlange = erkennung.Warteschlange(archive.index)
    if not warteschlange.anzahl():
        return

    bereit, hinweis = ocr.bereit()
    if not bereit:
        if laut:
            print(
                f"Hinweis: {warteschlange.anzahl()} eingescannte PDF sind nicht "
                f"durchsuchbar.\n         {hinweis}",
                file=sys.stderr,
            )
        return

    stat = erkennung.durchlauf(archive, budget_sekunden=budget)
    if laut and (stat.gelesen or stat.gescheitert):
        print(f"Texterkennung: {stat}")
    elif stat.gelesen:
        print(f"Texterkennung: {stat.gelesen} Dokumente lesbar gemacht")


def cmd_abgleich(args: argparse.Namespace) -> int:
    """Prüft, ob alles vor einem Stichtag im Archiv liegt."""
    from datetime import date

    from mailburg.core import abgleich

    if args.stichtag:
        try:
            stichtag = date.fromisoformat(args.stichtag)
        except ValueError:
            print(
                f"'{args.stichtag}' ist kein Datum. Erwartet: 2026-02-26",
                file=sys.stderr,
            )
            return 2
    else:
        stichtag = abgleich.stichtag_aus_tagen(args.aelter_als)

    liste = Kontenliste()
    print(f"Stichtag: {stichtag.strftime('%d.%m.%Y')}")
    print("Geprüft wird, was der Server hat und im Archiv fehlt.\n")

    bedenklich = 0
    with Archive.open(Path(args.archiv), exclusive=False) as archive:
        konten, meldung = _konten_waehlen(liste, archive, args.konto)
        if meldung:
            print(meldung, file=sys.stderr)
            return 2
        zustand = Abrufzustand(archive.uuid)

        for konto in konten:
            print(f"{konto.beschreibung()}")
            try:
                quelle = ImapSource(konto, _passwort_besorgen(konto))
            except ImapFehler as exc:
                print(f"  FEHLER: {exc}\n", file=sys.stderr)
                bedenklich += 1
                continue

            try:
                befund = abgleich.pruefen(
                    archive, quelle, konto.name, stichtag, zustand=zustand
                )
            finally:
                quelle.close()

            for eintrag in befund.ordner:
                if eintrag.uidvalidity_geaendert:
                    zeichen, lage = "!", "Nummerierung geändert – kein Vergleich möglich"
                elif eintrag.fehlend:
                    zeichen, lage = "!", f"{len(eintrag.fehlend)} FEHLEN"
                elif eintrag.auf_dem_server:
                    zeichen, lage = "✓", "alle im Archiv"
                else:
                    zeichen, lage = " ", "nichts so altes vorhanden"

                print(
                    f"  {zeichen} {eintrag.ordner:<38} "
                    f"{eintrag.auf_dem_server:>6}  {lage}"
                )
                if eintrag.fehlend and args.ausführlich:
                    nummern = ", ".join(str(u) for u in eintrag.fehlend[:20])
                    weitere = (
                        f" … und {len(eintrag.fehlend) - 20} weitere"
                        if len(eintrag.fehlend) > 20
                        else ""
                    )
                    print(f"      UID {nummern}{weitere}")

            for warnung in befund.warnungen:
                print(f"  Hinweis: {warnung}", file=sys.stderr)

            print()
            print("  " + abgleich.urteil(befund).replace("\n", "\n  "))
            print()

            if not befund.unbedenklich:
                bedenklich += 1

    if bedenklich:
        print(
            f"Bei {bedenklich} von {len(konten)} Postfächern sollte nichts "
            f"aufgeräumt werden."
        )
    return 1 if bedenklich else 0


def cmd_vorrat(args: argparse.Namespace) -> int:
    """Macht schon erkannten Text für künftige Läufe wiederverwendbar."""
    from mailburg.core import erkennung

    with Archive.open(Path(args.archiv), exclusive=False) as archive:
        print("Der schon erkannte Text wird ein zweites Mal abgelegt –")
        print("unter dem Fingerabdruck des Anhangs statt dem der Mail.")
        print("Es wird nichts neu erkannt.")
        print()

        def fortschritt(nr, gesamt, abgelegt) -> None:
            print(f"  … {nr} von {gesamt} geprüft, {abgelegt} abgelegt",
                  end="\r", flush=True)

        abgelegt, ohne = erkennung.vorrat_aufbauen(
            archive, fortschritt=fortschritt
        )

        print(" " * 60, end="\r")
        print(f"Fertig: {abgelegt} Dokumente im Vorrat.")
        if ohne:
            # Kein Fehler, aber erwähnenswert: Meist sind es Vermerke zu
            # Mails, die inzwischen gelöscht wurden.
            print(f"{ohne} Vermerke ließen sich nicht zuordnen.")
    return 0


def cmd_texterkennung(args: argparse.Namespace) -> int:
    """Macht eingescannte PDF durchsuchbar."""
    from mailburg.core import erkennung
    from mailburg.extract import ocr

    bereit, hinweis = ocr.bereit()
    if not bereit:
        print(f"Texterkennung nicht möglich: {hinweis}", file=sys.stderr)
        return 2

    with Archive.open(Path(args.archiv)) as archive:
        if args.nochmal:
            # Nach einer Verbesserung an der Erkennung selbst: Was
            # gestern unlesbar war, kann heute lesbar sein.
            frei = erkennung.gescheiterte_zuruecksetzen(archive)
            print(f"{frei} zuvor aufgegebene Dokumente stehen wieder an.")

        warteschlange = erkennung.Warteschlange(archive.index)
        offen = warteschlange.anzahl()
        if not offen:
            print("Alle eingescannten Dokumente sind bereits gelesen.")
            return 0

        print(f"{offen} Dokumente warten auf Texterkennung.")
        print(f"Sprachen: {ocr.sprachwahl()}")
        if args.alles:
            print("Ohne Zeitgrenze – das kann Stunden dauern. Abbruch mit Strg+C;")
            print("was bis dahin gelesen wurde, bleibt erhalten.")
        print()

        def fortschritt(stat) -> None:
            print(
                f"  … {stat.gelesen} gelesen, {stat.seiten} Seiten",
                end="\r",
                flush=True,
            )

        stat = erkennung.durchlauf(
            archive,
            budget_sekunden=0 if args.alles else args.budget,
            budget_dokumente=0 if args.alles else erkennung.BUDGET_DOKUMENTE,
            fortschritt=fortschritt,
        )

        print(" " * 60, end="\r")
        print(f"Fertig: {stat}")
        print(f"Dauer: {stat.sekunden:.0f} s")
        if stat.offen_danach:
            print(
                f"\nNoch {stat.offen_danach} Dokumente offen. Sie kommen bei den "
                f"nächsten Abrufen nach und nach dran – oder auf einmal mit "
                f"'texterkennung --alles'."
            )
    return 0


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


def cmd_sichern(args) -> int:
    """Packt das Archiv in eine Datei – für den Zeitplan gedacht."""
    from mailburg.core import sicherung
    from mailburg.core.archive import Archive

    archiv_pfad = Path(args.archiv).expanduser().resolve()
    ziel = Path(args.ziel).expanduser()

    # Ein Verzeichnis als Ziel: Dann wird der Name selbst gewählt. So
    # lässt sich derselbe Befehl täglich aufrufen, ohne dass eine
    # Sicherung die vorige überschreibt.
    if ziel.is_dir() or not ziel.suffix:
        name = args.name
        if not name:
            with Archive.open(archiv_pfad, exclusive=False) as archiv:
                name = archiv.name
        ziel = ziel / (
            sicherung.dateiname(name) if args.ersetzen
            else sicherung.vorschlag(archiv_pfad, name)
        )

    try:
        befund = sicherung.packen(archiv_pfad, ziel)
    except sicherung.SicherungFehler as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    if not args.leise:
        print(f"Gesichert: {befund.ziel}")
        print(
            f"  {befund.dateien} Dateien, "
            f"{befund.ziel_bytes / 1024 / 1024:.0f} MB "
            f"({befund.ersparnis}% kleiner als das Original)"
        )

    if args.behalten > 0:
        weg = _alte_sicherungen_entfernen(ziel.parent, args.behalten)
        if weg and not args.leise:
            print(f"  {len(weg)} ältere Sicherung(en) entfernt")
    return 0


def _alte_sicherungen_entfernen(ordner: Path, behalten: int) -> list[Path]:
    """Räumt ältere Sicherungen weg – die jüngsten bleiben.

    Ohne das läuft jede Platte irgendwann voll, und dann scheitert
    ausgerechnet die Sicherung, auf die es ankäme. Gelöscht wird
    ausschließlich, was aussieht wie eine von uns angelegte Sicherung.
    """
    kandidaten = sorted(
        (p for p in ordner.glob("*.tar.*")
         if p.is_file() and p.suffix in (".zst", ".xz")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    entfernt = []
    for alt in kandidaten[behalten:]:
        try:
            alt.unlink()
        except OSError:
            continue
        entfernt.append(alt)
    return entfernt


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
    p.add_argument("quelle",
        help="Thunderbird-Profil, Maildir, MBOX-Datei oder ein Verzeichnis "
             "mit .eml-Dateien")
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
    k.add_argument("--server", help="IMAP-Server, etwa imap.gmail.com")
    k.add_argument("--benutzer", help="Anmeldename, meist die Mailadresse")
    k.add_argument("--port", type=int, default=993, help="Standard: 993 (IMAPS)")
    k.add_argument(
        "--starttls",
        action="store_true",
        help="unverschlüsselt verbinden und auf TLS hochstufen (Port meist 143)",
    )
    k.add_argument(
        "--proton",
        action="store_true",
        help="Postfach über die Proton Mail Bridge: setzt Server, Port und "
             "Verschlüsselung von selbst. Das Passwort erzeugt die Bridge – "
             "das Kennwort des Proton-Kontos taugt dafür nicht.",
    )
    k.add_argument(
        "--bruecke",
        action="store_true",
        help="dahinter läuft ein Brückenprogramm auf diesem Rechner. Dessen "
             "selbstsigniertes Zertifikat wird dann hingenommen – nur bei "
             "127.0.0.1, denn nur da verlässt die Verbindung den Rechner nicht",
    )
    k.set_defaults(func=cmd_konten_hinzufuegen)

    k = konten_befehle.add_parser(
        "uebernehmen",
        help="Postfächer aus einem Thunderbird-Profil übernehmen",
        description="Übernimmt Server, Port, Benutzername und Verschlüsselungsart "
                    "aus Thunderbird. Das Passwort wird von Hand abgefragt – aus "
                    "dem Profil holt MailBurg es ausdrücklich nicht.",
    )
    k.add_argument(
        "profil", nargs="?", help="Thunderbird-Profil; ohne Angabe wird gesucht"
    )
    k.add_argument(
        "--zeigen",
        action="store_true",
        help="nur anzeigen, was gefunden wurde – nichts einrichten, nichts fragen",
    )
    k.add_argument(
        "--alle", action="store_true", help="ohne Rückfrage je Konto übernehmen"
    )
    k.add_argument(
        "--ohne-test",
        action="store_true",
        help="Anmeldung nicht gleich ausprobieren",
    )
    k.set_defaults(func=cmd_konten_uebernehmen)

    k = konten_befehle.add_parser("entfernen", help="ein Postfach aus der Liste nehmen")
    k.add_argument("name")
    k.set_defaults(func=cmd_konten_entfernen)

    k = konten_befehle.add_parser(
        "zuordnen",
        help="ein Postfach einem Archiv zuordnen",
        description=(
            "Nur zugeordnete Postfächer werden abgerufen. Ohne Zuordnung "
            "holte früher jeder Abruf jedes Postfach – wer geschäftlich und "
            "privat trennt, bekam in beiden Archiven denselben Bestand."
        ),
    )
    k.add_argument("archiv", help="Verzeichnis des Archivs")
    k.add_argument("konto", help="Name des Postfachs")
    k.add_argument(
        "--loesen", action="store_true",
        help="die Zuordnung wieder aufheben",
    )
    k.set_defaults(func=cmd_konten_zuordnen)

    k = konten_befehle.add_parser(
        "zuordnung", help="zeigen, welches Postfach in welches Archiv geht"
    )
    k.set_defaults(func=cmd_konten_zuordnung)

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
    p.add_argument(
        "--ohne-texterkennung",
        action="store_true",
        help="im Anschluss keine eingescannten PDF lesbar machen",
    )
    p.add_argument(
        "--erkennungsbudget",
        type=float,
        default=120,
        metavar="SEKUNDEN",
        help="wie lange nach dem Abruf höchstens Texterkennung läuft "
             "(Standard: 120)",
    )
    p.set_defaults(func=cmd_abrufen)

    p = subparsers.add_parser(
        "abgleich",
        help="prüfen, ob alles Ältere im Archiv ist",
        description="Fragt den Server, welche Mails älter als ein Stichtag "
                    "sind, und hält jede gegen das Archiv. Der Nachweis, den "
                    "man braucht, bevor man im Mailprogramm aufräumen lässt.",
    )
    p.add_argument("archiv")
    p.add_argument("--konto", help="nur dieses Konto prüfen")
    p.add_argument(
        "--aelter-als",
        type=int,
        default=180,
        metavar="TAGE",
        help="Stichtag als Abstand von heute (Standard: 180)",
    )
    p.add_argument(
        "--stichtag",
        metavar="JJJJ-MM-TT",
        help="fester Stichtag statt einer Tageszahl",
    )
    p.set_defaults(func=cmd_abgleich)

    p = subparsers.add_parser(
        "texterkennung",
        help="eingescannte PDF durchsuchbar machen",
        description="Liest eingescannte PDF mit tesseract. Das Archiv bleibt "
                    "dabei unangetastet – der erkannte Text kommt nur in den "
                    "Suchindex.",
    )
    p.add_argument("archiv")
    p.add_argument(
        "--alles",
        action="store_true",
        help="ohne Zeitgrenze durchlaufen statt nur ein Häppchen",
    )
    p.add_argument(
        "--budget",
        type=float,
        default=120,
        metavar="SEKUNDEN",
        help="Zeitgrenze für diesen Lauf (Standard: 120)",
    )
    p.add_argument(
        "--nochmal", action="store_true",
        help="zuvor aufgegebene Dokumente erneut versuchen – sinnvoll, "
             "nachdem die Texterkennung selbst verbessert wurde",
    )
    p.set_defaults(func=cmd_texterkennung)

    p = subparsers.add_parser(
        "vorrat",
        help="schon erkannten Text für künftige Läufe nutzbar machen",
        description=(
            "Ein Anhang, der an mehreren Mails hängt, wird nur einmal "
            "gelesen. Erkannt wird er unter dem Fingerabdruck des "
            "Dokuments – wer die Texterkennung laufen ließ, bevor es "
            "diesen Schlüssel gab, hat den Text, aber nicht den Zugriff "
            "darauf. Dieser Befehl holt das nach. Er erkennt nichts neu."
        ),
    )
    p.add_argument("archiv", help="Pfad zum Archiv")
    p.set_defaults(func=cmd_vorrat)

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

    p = subparsers.add_parser(
        "sichern",
        help="das Archiv in eine Datei packen",
        description=(
            "Packt das ganze Archiv in eine einzelne Datei – für die Cloud "
            "oder eine zweite Platte. Kleiner wird dabei kaum etwas, die "
            "Mails liegen schon komprimiert; der Gewinn ist, dass aus "
            "tausenden Dateien eine wird."
        ),
    )
    p.add_argument("archiv")
    p.add_argument("ziel", help="Zieldatei oder -verzeichnis")
    p.add_argument(
        "--behalten", type=int, default=0, metavar="ANZAHL",
        help=(
            "nur die letzten ANZAHL Sicherungen im Zielverzeichnis behalten "
            "(0 = alle behalten)"
        ),
    )
    p.add_argument(
        "--name", default="", metavar="NAME",
        help=(
            "Name für die Sicherungsdatei statt des Archivnamens – etwa "
            "»Geschaeftsarchiv«"
        ),
    )
    p.add_argument(
        "--ersetzen", action="store_true",
        help=(
            "immer dieselbe Datei überschreiben statt eine mit Datum "
            "anzulegen – für Cloud-Ordner, die selbst Versionen führen"
        ),
    )
    p.add_argument("--leise", action="store_true", help="nur bei Fehlern melden")
    p.set_defaults(func=cmd_sichern)

    p = subparsers.add_parser(
        "loeschen",
        help="Mails eines Postfachs wieder aus dem Archiv nehmen",
        description=(
            "Entfernt, was ausschließlich an diesem Postfach hängt. Mails, "
            "die auch unter einem anderen Postfach gefunden wurden, bleiben "
            "unangetastet – sie verlören sonst mehr als den einen Fundort. "
            "Ohne --wirklich ist es ein Trockenlauf."
        ),
    )
    p.add_argument("archiv", help="Verzeichnis des Archivs")
    p.add_argument("--konto", required=True, help="Name des Postfachs")
    p.add_argument(
        "--grund", default="irrtuemlich_archiviert",
        help="warum gelöscht wird – steht so im Journal",
    )
    p.add_argument("--notiz", default="", help="Erläuterung fürs Journal")
    p.add_argument(
        "--wirklich", action="store_true",
        help="tatsächlich löschen statt nur zeigen",
    )
    p.set_defaults(func=cmd_loeschen)

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
