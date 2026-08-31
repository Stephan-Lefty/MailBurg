"""MailBurg auf der Kommandozeile.

Solange die grafische Oberfläche noch nicht steht, ist das der Weg ins
Archiv. Sie bleibt aber auch danach erhalten – für Sicherungsläufe im
Hintergrund und für alles, was sich in einer Zeitsteuerung anstoßen lässt,
ist sie ohnehin das bessere Werkzeug.
"""

from __future__ import annotations

import argparse
import getpass
import shutil
import sys
import time
from pathlib import Path

from mailburg import APP_NAME, __version__
from mailburg.core import accounts, sprache
from mailburg.core.accounts import Konto, Kontenliste
from mailburg.core.archive import Archive, ArchiveError, ArchiveLocked, Mode
from mailburg.core.importer import importieren
from mailburg.core.index import IndexOutdated
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
            print(f"Mit Anhangstext: {sprache.mails(stat.mit_anhangstext)}")
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

    geht, grund = accounts.schluesselbund_lage()
    if not geht:
        print(f"Hinweis: {grund}\n", file=sys.stderr)

    for konto in liste.konten:
        zustand = "aktiv" if konto.aktiv else "stillgelegt"
        gemerkt = "Passwort gemerkt" if accounts.passwort_holen(konto) else "kein Passwort"
        print(f"  {konto.beschreibung()}  [{zustand}, {gemerkt}]")
        if args.ausführlich and konto.ausschluss:
            print(f"      übergangen: {', '.join(konto.ausschluss)}")
    return 0


def cmd_konten_anmelden(args: argparse.Namespace) -> int:
    """Meldet ein Postfach per OAuth2 an.

    Öffnet den Browser, wartet auf die Rückkehr und legt die Token im
    Schlüsselbund ab. Danach läuft der Abruf ohne Zutun weiter – bis der
    Anbieter die Anmeldung entzieht oder das Kontopasswort geändert
    wird.
    """
    from mailburg.core import accounts
    from mailburg.core.oauth2 import ANBIETER, OAuthFehler
    from mailburg.core.oauth2_anmelden import anmelden

    liste = Kontenliste()
    konto = liste.finden(args.name)
    if konto is None:
        print(f"Kein Postfach namens '{args.name}'.", file=sys.stderr)
        return 2

    anbieter_kennung = args.anbieter or konto.oauth_anbieter
    if not anbieter_kennung:
        print(
            f"Für '{konto.name}' ist kein Anmeldedienst hinterlegt.\n"
            f"Mit --anbieter angeben: {', '.join(ANBIETER)}",
            file=sys.stderr,
        )
        return 2

    anbieter = ANBIETER.get(anbieter_kennung)
    if anbieter is None:
        print(
            f"Unbekannter Anmeldedienst '{anbieter_kennung}'. "
            f"Bekannt sind: {', '.join(ANBIETER)}",
            file=sys.stderr,
        )
        return 2

    kennung = args.kennung or konto.oauth_kennung
    if not kennung:
        print(
            f"Es fehlt die Kennung Ihrer registrierten Anwendung "
            f"(--kennung).\n\n{anbieter.hinweis}\n\n"
            f"Schritt für Schritt steht das in docs/oauth2.md.",
            file=sys.stderr,
        )
        return 2

    geht, grund = accounts.schluesselbund_lage()
    if not geht:
        # Ohne Schlüsselbund wäre die Anmeldung sinnlos: Die Token
        # müssten in eine Datei, und ein Erneuerungs-Token ist auf
        # Monate hinaus ein Vollzugang zum Postfach.
        print(f"Anmeldung nicht möglich: {grund}", file=sys.stderr)
        return 2

    print(f"Der Browser öffnet sich für die Anmeldung bei {anbieter.name}.")
    print("Melden Sie sich dort an und erlauben Sie MailBurg den Zugriff.")
    print()

    try:
        token = anmelden(anbieter, kennung)
    except OAuthFehler as exc:
        print(f"Nicht angemeldet: {exc}", file=sys.stderr)
        return 1

    konto.oauth_anbieter = anbieter.kennung
    konto.oauth_kennung = kennung
    liste.speichern()

    if not accounts.token_setzen(konto, token):
        print(
            "Die Anmeldung hat geklappt, ließ sich aber nicht im "
            "Schlüsselbund ablegen. In eine Datei geschrieben wird sie "
            "nicht – melden Sie sich erneut an, wenn der Schlüsselbund "
            "wieder erreichbar ist.",
            file=sys.stderr,
        )
        return 1

    print(f"'{konto.name}' ist angemeldet.")
    print(
        "Die Anmeldung liegt im Schlüsselbund. Der Abruf erneuert sie von "
        "selbst; nur wenn Sie das Kontopasswort ändern oder den Zugriff "
        "entziehen, ist eine neue Anmeldung nötig."
    )
    return 0


def cmd_konten_abmelden(args: argparse.Namespace) -> int:
    """Nimmt die OAuth2-Anmeldung eines Postfachs zurück.

    Entfernt nur die Token aus dem Schlüsselbund. Das Postfach bleibt
    eingerichtet, die archivierten Mails bleiben ohnehin.

    **Beim Anbieter gilt der Zugriff damit noch.** Ihn dort zu widerrufen
    kann nur der Anwender – im Sicherheitsbereich seines Kontos. Das
    steht in der Ausgabe, weil sonst der Eindruck entstünde, mit diesem
    Befehl sei die Sache erledigt.
    """
    from mailburg.core import accounts

    liste = Kontenliste()
    konto = liste.finden(args.name)
    if konto is None:
        print(f"Kein Postfach namens '{args.name}'.", file=sys.stderr)
        return 2

    accounts.token_loeschen(konto)
    konto.oauth_anbieter = ""
    liste.speichern()

    print(f"'{konto.name}' ist abgemeldet, die Token sind entfernt.")
    print()
    print(
        "Beim Anbieter besteht die Erlaubnis weiter. Widerrufen lässt sie "
        "sich nur dort – bei Microsoft unter »Mein Konto → Apps und "
        "Dienste«, bei Google unter »Konto → Sicherheit → Drittanbieter-Apps«."
    )
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
            f"Achtung: {accounts.schluesselbund_lage()[1]}\n"
            f"         In eine Datei geschrieben wird es nicht.",
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
        print(f"  {sprache.mails(len(zeilen))}, davon {len(nur_hier)} "
              f"nur hier zu finden.")
        if auch_anderswo:
            print(f"  {auch_anderswo} "
                  + ("liegt" if auch_anderswo == 1 else "liegen")
                  + " auch unter einem anderen Postfach "
                  + ("und bleibt" if auch_anderswo == 1 else "und bleiben")
                  + " unangetastet.")

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
    """Zeigt, welches Postfach in welches Archiv geht.

    **Nach Archiven gruppiert, nicht nach Postfächern.** Die Frage
    lautet »was landet in meinem Geschäftsarchiv?«, und die beantwortet
    eine Liste, in der jedes Postfach seine Kennung wiederholt, nur
    mühsam. Genau diese Zuordnung entscheidet über zehnjährige
    Aufbewahrungsfristen – am 2026-08-26 lagen deswegen 9.690 Mails im
    falschen Archiv.
    """
    liste = Kontenliste()
    if not liste.konten:
        print("Noch kein Postfach eingerichtet.")
        return 0

    from mailburg.core.archive import archivnamen

    namen = archivnamen()
    nach_archiv: dict[str, list] = {}
    ohne = []
    for konto in liste.konten:
        if not konto.archive:
            ohne.append(konto)
            continue
        for kennung in konto.archive:
            nach_archiv.setdefault(kennung, []).append(konto)

    def beschriften(konto) -> str:
        return f"   {konto.name}" + ("" if konto.aktiv else "  (abgeschaltet)")

    # Benannte Archive zuerst, alphabetisch; unbekannte Kennungen ans
    # Ende - sie sagen ohnehin am wenigsten.
    def schluessel(kennung: str) -> tuple[int, str]:
        return (0, namen[kennung].lower()) if kennung in namen else (1, kennung)

    for kennung in sorted(nach_archiv, key=schluessel):
        if kennung in namen:
            print(f"{namen[kennung]}")
        else:
            print(f"{kennung}")
            print("   (dieses Archiv wurde hier noch nicht geöffnet)")
        for konto in nach_archiv[kennung]:
            print(beschriften(konto))
        print()

    if ohne:
        print("Keinem Archiv zugeordnet – wird nicht abgerufen")
        for konto in ohne:
            print(beschriften(konto))
        print()
        print("   Zuordnen mit:  mailburg konten zuordnen NAME ARCHIV")
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
            f"\n{sprache.postfaecher(len(offen))} "
            + ("ist" if len(offen) == 1 else "sind")
            + " keinem Archiv zugeordnet und "
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
                    f"  {sprache.mails(stat.fehlgeschlagen)} "
                    + ("ist" if stat.fehlgeschlagen == 1 else "sind")
                    + " vorgemerkt und "
                    + ("wird" if stat.fehlgeschlagen == 1 else "werden")
                    + " beim "
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

        # Bei der Gelegenheit die Textmenge nachtragen: Sie steht in
        # denselben Dateien, und ohne sie lässt sich nicht sagen, welche
        # Dokumente nur scheinbar gelesen wurden.
        ergaenzt, duenn = erkennung.zeichen_nachtragen(archive)
        if ergaenzt:
            print(f"Textmenge für {ergaenzt} Dokumente nachgetragen.")
        if duenn:
            print(f"\nDavon {duenn} mit auffällig wenig Text – "
                  f"vermutlich schlechte Vorlagen:")
            for name, seiten, zeichen in erkennung.duenne(archive)[:10]:
                print(f"   {name[:52]:54s} {seiten} S., {zeichen} Zeichen")
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

        if stat.duenn:
            # Diese Dokumente gelten als erledigt und werden nie wieder
            # angefasst. Wer sie nicht kennt, sucht später vergeblich
            # nach ihrem Inhalt und hält das Archiv für unvollständig -
            # dabei ist nur die Vorlage schlecht gewesen.
            print(f"\n{len(stat.duenn)} Dokumente haben auffällig wenig "
                  f"Text ergeben. Vermutlich schlechte Vorlagen:")
            for name, seiten, zeichen in stat.duenn[:10]:
                print(f"   {name[:52]:54s} {seiten} S., {zeichen} Zeichen")
            if len(stat.duenn) > 10:
                print(f"   … und {len(stat.duenn) - 10} weitere")
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
            print(f"  Hash-Kette:  unversehrt "
                  f"({sprache.eintraege(report['chain_entries'])})")
        else:
            print(f"  Hash-Kette:  BESCHÄDIGT ({len(report['chain_errors'])} Fundstellen)")
            for problem in report["chain_errors"][:20]:
                print(f"    - {problem}")

        print(f"  Erwartet:    {sprache.mails(report['expected'])} laut Journal")
        print(f"  Vorhanden:   {sprache.dateien(report['on_disk'])} in der Ablage")

        if report["missing"]:
            print(f"  FEHLEND:     {sprache.mails(len(report['missing']))} ohne Datei")
            for digest in report["missing"][:10]:
                print(f"    - {digest[:16]}…")

        if report["unexpected"]:
            print(f"  UNBEKANNT:   {sprache.dateien(len(report['unexpected']))} "
                  f"ohne Journaleintrag")
            print("               Diese Mails wurden nicht über MailBurg aufgenommen.")
            for digest in report["unexpected"][:10]:
                print(f"    - {digest[:16]}…")

        print()
        print("Ergebnis: " + ("alles in Ordnung" if report["ok"] else "Beanstandungen, siehe oben"))
    return 0 if report["ok"] else 1


def cmd_neuaufbau(args: argparse.Namespace) -> int:
    """Baut den Suchindex neu."""
    # **Den alten Index gleich beim Öffnen wegwerfen.** Stammt er aus
    # einer älteren Programmfassung, ließe er sich nicht öffnen - und
    # ausgerechnet der Befehl, auf den die Meldung verweist, käme nicht
    # an das Archiv heran. Verloren geht nichts: Die Zeilen darunter
    # bauen ihn ohnehin von Grund auf neu.
    with Archive.open(Path(args.archiv), index_verwerfen=True) as archive:
        print("Baue den Suchindex neu. Das Archiv selbst wird dabei nur gelesen.")
        started = time.monotonic()

        def progress(done: int, total: int) -> None:
            print(f"  … {done} von {total}", end="\r", flush=True)

        count = archive.rebuild_index(progress=progress)
        print(" " * 60, end="\r")
        print(f"Fertig: {sprache.mails(count)} in "
              f"{time.monotonic() - started:.1f} s indiziert.")
    return 0


def cmd_siegel(args: argparse.Namespace) -> int:
    """Setzt ein Siegel über den aktuellen Stand."""
    with Archive.open(Path(args.archiv)) as archive:
        entry = archive.seal()
        print(f"Siegel gesetzt über {sprache.eintraege(entry['count'])}.")
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
        print(f"  Journal:      {sprache.eintraege(archive.journal.count)}")

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


def cmd_werkzeuge(args: argparse.Namespace) -> int:
    """Zeigt, was für Volltext und Texterkennung bereitsteht.

    **Wozu das gut ist.** Wenn eine eingescannte Rechnung im Archiv
    liegt und die Suche sie nicht findet, gibt es genau zwei Gründe: Der
    Scan war zu schlecht, oder die Texterkennung lief gar nicht. Ohne
    diesen Befehl ist das von außen nicht zu unterscheiden - man sucht
    dann in der falschen Richtung.

    Unter Windows kommt hinzu, dass die gepackte Fassung ihre Werkzeuge
    selbst mitbringt. Ob sie tatsächlich gefunden werden, soll man
    nachsehen können, ohne erst eine Rechnung durchlaufen zu lassen.
    """
    from mailburg.core import werkzeuge as mitgebracht
    from mailburg.extract import ocr

    ort = mitgebracht.mitgeliefert()
    if ort is not None:
        print(f"Mitgeliefert in: {ort}")
    print()

    geht, grund = ocr.bereit()
    print(f"Texterkennung: {'ja' if geht else 'nein'}")
    if not geht:
        print(f"  {grund}")
    else:
        sprachen = ", ".join(sorted(ocr.sprachen_vorhanden()))
        print(f"  Sprachen: {sprachen}")
        print(f"  Benutzt wird: {ocr.sprachwahl()}")

    print()
    for name, wofuer in (
        ("pdftoppm", "Seiten in Bilder wandeln"),
        ("pdftotext", "Text aus PDF holen"),
        ("pdfinfo", "Seitengröße und Verschlüsselung prüfen"),
        ("tesseract", "Text aus Bildern lesen"),
    ):
        pfad = shutil.which(name)
        print(f"{name:11} {pfad or '– fehlt –':60} {wofuer}")

    return 0 if geht else 1


def cmd_verfahrensdoku(args: argparse.Namespace) -> int:
    """Erzeugt den technischen Teil einer Verfahrensdokumentation.

    Die GoBD verlangen sie für jedes datenverarbeitende System: Ein
    sachverständiger Dritter soll in angemessener Zeit sehen, wie die
    Daten entstehen, wo sie liegen und wie sie geschützt sind.

    **Verantwortlich ist der Steuerpflichtige, nicht das Programm.**
    MailBurg steuert bei, was es selbst weiß. Alles Organisatorische
    bleibt als sichtbare Lücke stehen – eine Dokumentation, die
    vollständig aussieht und es nicht ist, fällt erst in der Prüfung
    auf, und dann ist keine Zeit mehr.
    """
    from mailburg.core import verfahrensdoku
    from mailburg.core.archive import Archive

    archiv_pfad = Path(args.archiv).expanduser().resolve()
    with Archive.open(archiv_pfad, exclusive=False) as archiv:
        konten = None
        try:
            konten = Kontenliste()
        except Exception:  # noqa: BLE001
            pass

        zeitplaene = {}
        try:
            from mailburg.core import zeitplan

            abruf = zeitplan.zustand(archiv_pfad)
            if abruf.laeuft:
                zeitplaene["Abruf"] = (
                    f"{verfahrensdoku.takt_in_worten(abruf.takt).capitalize()}, "
                    f"selbsttätig im Hintergrund, solange der Benutzer am "
                    f"Rechner angemeldet ist. Versäumte Läufe werden beim "
                    f"nächsten Anmelden nachgeholt."
                )
            sicher = zeitplan.sicherung_zustand(archiv_pfad)
            if sicher.laeuft:
                wohin = getattr(sicher, "archiv", "") or ""
                zeitplaene["Sicherung"] = (
                    f"Selbsttätig eingerichtet"
                    + (f", Ziel `{wohin}`." if wohin else ".")
                    + " Gepackt wird das gesamte Archiv in eine Datei; der"
                    + " Suchindex bleibt außen vor, weil er aus dem"
                    + " Protokoll jederzeit neu entsteht."
                )
        except Exception:  # noqa: BLE001
            pass

        text = verfahrensdoku.erzeugen(archiv, konten, zeitplaene or None)

    if not args.ziel:
        print(text)
        return 0

    ziel = Path(args.ziel).expanduser()
    if ziel.suffix.lower() not in (".md", ".txt"):
        ziel = ziel.with_suffix(".md")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(text, encoding="utf-8")

    luecken = text.count(verfahrensdoku.LUECKE)
    print(f"Geschrieben: {ziel}")
    print()
    print(
        f"**{luecken} Stellen** sind noch auszufüllen – suchen Sie in der\n"
        f"Datei nach »BITTE ERGÄNZEN«. Was dort steht, kann kein Programm\n"
        f"wissen: wer zuständig ist, wer vertreten darf, wie oft geprüft\n"
        f"wird. Verantwortlich für die Verfahrensdokumentation ist\n"
        f"ausschließlich der Steuerpflichtige."
    )
    return 0


def cmd_auskunft(args: argparse.Namespace) -> int:
    """Stellt alles zu einer Person zusammen – Art. 15 DSGVO.

    Gibt nichts heraus. Es packt zusammen und sagt dazu, was vor der
    Herausgabe noch zu prüfen ist: Daten Dritter in denselben
    Nachrichten, und ob die Person unter weiteren Adressen schreibt.
    Beides kann kein Programm entscheiden.
    """
    from mailburg.core import auskunft
    from mailburg.core.archive import Archive

    archiv_pfad = Path(args.archiv).expanduser().resolve()
    with Archive.open(archiv_pfad, exclusive=bool(args.ziel)) as archiv:
        befund = auskunft.zusammenstellen(
            archiv, args.adresse, im_text=args.im_text
        )

        print(f"Zu »{args.adresse}« im Archiv »{archiv.name}«:\n")
        print(f"  Nachrichten gesamt: {befund.anzahl}")
        print(f"    als Absender:     {befund.als_absender}")
        print(f"    als Empfänger:    {befund.als_empfaenger}")
        if args.im_text:
            print(f"    im Text erwähnt:  {befund.im_text}")

        if not befund.anzahl:
            print("\nNichts gefunden. Schreibt die Person unter einer "
                  "anderen Adresse?")
            return 0

        von = (befund.treffer[0].date or "")[:10]
        bis = (befund.treffer[-1].date or "")[:10]
        print(f"  Zeitraum:           {von} bis {bis}")

        if not args.ziel:
            print()
            print("Nichts geschrieben. Zum Packen ein Ziel angeben:")
            print(f"  mailburg auskunft ARCHIV {args.adresse} auskunft.zip")
            return 0

        auskunft.packen(archiv, befund, Path(args.ziel).expanduser())
        groesse = befund.ziel.stat().st_size / 1024 / 1024
        print(f"\nGeschrieben: {befund.ziel}  ({groesse:.1f} MB)")
        print("Im Journal vermerkt.")
        print()
        print(
            "Vor der Herausgabe prüfen: In denselben Nachrichten stehen\n"
            "oft Daten Dritter – Adressen im Verteiler, Namen im Text,\n"
            "Unterschriften in Anhängen. Nach Art. 15 Abs. 4 DSGVO darf\n"
            "die Kopie deren Rechte nicht beeinträchtigen. Das Begleitblatt\n"
            "im Paket sagt es noch einmal."
        )
    return 0


def cmd_faellig(args: argparse.Namespace) -> int:
    """Zeigt, was seine Aufbewahrungsfrist hinter sich hat.

    **Fristen wirken in beide Richtungen.** Sie schützen vor zu frühem
    Löschen – aber nach ihrem Ablauf verlangt die DSGVO, dass
    personenbezogene Daten auch wieder verschwinden. Ein Archiv, das nur
    aufbewahrt, erfüllt die eine Hälfte und verletzt die andere.

    Gelöscht wird hier trotzdem nichts. Die Entscheidung gehört dem
    Anwender: Ob eine Betriebsprüfung läuft, ob ein Rechtsstreit
    anhängig ist, ob eine Branchenvorschrift länger bindet – das kann
    kein Programm wissen.
    """
    from mailburg.core.archive import Archive

    archiv_pfad = Path(args.archiv).expanduser().resolve()
    with Archive.open(archiv_pfad, exclusive=False) as archiv:
        if not archiv.mode.is_business:
            # **Ein Privatarchiv kennt keine Fristen.** Was hier gezeigt
            # wird, ist deshalb keine Fälligkeit, sondern eine Auskunft
            # beim Aufräumen - und der Unterschied gehört in die Worte.
            # Bei privater Post ist Alter ein schlechter Ratgeber: Die
            # Mail vom verstorbenen Vater aus 2012 ist mehr wert als die
            # von gestern.
            from mailburg.core.archive import ALT_AB_JAHREN

            jahre = args.jahre or ALT_AB_JAHREN
            alte = archiv.alte(jahre)
            if not alte:
                print(f"Keine Mail ist älter als {jahre} Jahre.")
                return 0

            nach_jahr: dict[str, int] = {}
            for eintrag in alte:
                nach_jahr[(eintrag.date or "????")[:4]] = (
                    nach_jahr.get((eintrag.date or "????")[:4], 0) + 1
                )
            print(
                f"{sprache.mails(len(alte))} "
                + ("ist" if len(alte) == 1 else "sind")
                + f" älter als {jahre} Jahre.\n"
            )
            for jahr in sorted(nach_jahr):
                print(f"  {jahr}: {nach_jahr[jahr]}")
            print()
            print(
                "Ein Privatarchiv kennt keine Aufbewahrungsfristen – das\n"
                "hier ist kein Grund zum Löschen, nur eine Auskunft. Alter\n"
                "sagt bei privater Post wenig darüber, was einem wichtig\n"
                "ist. Ansehen lässt sich das mit:  "
                f"mailburg suchen ARCHIV \"jahr:1900-{sorted(nach_jahr)[-1]}\""
            )
            return 0

        treffer = archiv.faellige()
        if not treffer:
            print("Keine Mail hat ihre Aufbewahrungsfrist hinter sich.")
            return 0

        nach_jahr: dict[str, int] = {}
        for eintrag in treffer:
            jahr = (eintrag.date or "????")[:4]
            nach_jahr[jahr] = nach_jahr.get(jahr, 0) + 1

        wort = "Mail hat" if len(treffer) == 1 else "Mails haben"
        print(f"{len(treffer)} {wort} die Aufbewahrungsfrist hinter sich.\n")
        for jahr in sorted(nach_jahr):
            print(f"  {jahr}: {nach_jahr[jahr]}")

        if args.ausfuehrlich:
            print()
            for eintrag in treffer[:200]:
                datum = (eintrag.date or "")[:10]
                print(f"  {datum}  {eintrag.category:14} {eintrag.subject[:50]}")
            if len(treffer) > 200:
                print(f"  … und {len(treffer) - 200} weitere")

        print()
        print(
            "Gelöscht wird nichts von selbst. Ob eine Betriebsprüfung läuft\n"
            "oder ein Rechtsstreit anhängig ist, kann das Programm nicht\n"
            "wissen – fragen Sie im Zweifel Ihren Steuerberater."
        )
    return 0


def cmd_einstufen(args: argparse.Namespace) -> int:
    """Stuft die Treffer einer Suche aufbewahrungsrechtlich ein.

    **Über die Suche, nicht Mail für Mail.** Wer ein Archiv einstuft, hat
    hunderte Belege vor sich, keine drei. »Alles von der Steuerkanzlei
    ist Buchungsbeleg« ist eine Regel, die sich als Suchausdruck schreiben
    lässt – und die sich später nachvollziehen lässt, weil jeder Vorgang
    im Journal steht.

    Ohne ``--wirklich`` wird nur gezeigt, was geschähe. Eine Einstufung
    verlängert Aufbewahrungsfristen und lässt sich nicht formlos
    zurücknehmen; ein Tippfehler im Suchausdruck soll nicht hundert Mails
    für acht Jahre festsetzen.
    """
    from mailburg.core.archive import Archive
    from mailburg.core.retention import Category

    archiv_pfad = Path(args.archiv).expanduser().resolve()
    try:
        ziel = Category(args.kategorie)
    except ValueError:
        moeglich = ", ".join(k.value for k in Category)
        print(f"'{args.kategorie}' ist keine Kategorie. Möglich: {moeglich}",
              file=sys.stderr)
        return 2

    with Archive.open(archiv_pfad, exclusive=args.wirklich) as archiv:
        treffer = archiv.index.search(args.suche, limit=1_000_000)
        if not treffer:
            print(f"Keine Treffer für: {args.suche}")
            return 0

        # Was schon so eingestuft ist, bleibt unangetastet - und wird
        # auch nicht mitgezählt. Sonst meldet der Befehl beim zweiten
        # Aufruf dieselbe Zahl und man hält ihn für wirkungslos.
        offen = [t for t in treffer if t.category != ziel.value]

        print(f"{len(treffer)} Treffer für: {args.suche}")
        if not offen:
            print(f"Alle sind bereits »{ziel.value}«. Nichts zu tun.")
            return 0
        print(f"Davon einzustufen als »{ziel.value}«: {len(offen)}")

        if not args.wirklich:
            for t in offen[:10]:
                print(f"   {t.date or '        '}  {t.subject[:60]}")
            if len(offen) > 10:
                print(f"   … und {len(offen) - 10} weitere")
            print()
            print("Nichts geändert. Zum Ausführen: --wirklich")
            return 0

        for t in offen:
            archiv.classify(t.hash, ziel, note=f"Suche: {args.suche}")
        wort = "Mail" if len(offen) == 1 else "Mails"
        print(f"Eingestuft: {len(offen)} {wort}. Im Journal vermerkt.")
    return 0


def cmd_zugaenge(args: argparse.Namespace) -> int:
    """Zugänge zum Archiv – der Weg ohne Oberfläche.

    **Auf einem Server gibt es keine.** Ohne diesen Befehl käme man dort
    an sein eigenes Archiv nicht heran: Die Rechteverwaltung säße in
    einem Fenster, das sich nicht öffnen lässt.
    """
    from mailburg.core.benutzer import Benutzer, BenutzerFehler

    archiv_pfad = Path(args.archiv).expanduser().resolve()
    schreibend = args.was != "liste"

    with Archive.open(archiv_pfad, exclusive=schreibend) as archiv:
        liste = archiv.benutzer

        if args.was == "liste":
            if not len(liste):
                print("Es ist kein Zugang eingerichtet.")
                print("Anlegen mit:  mailburg zugaenge ARCHIV hinzufuegen NAME")
                return 0

            print(f"{sprache.anzahl(len(liste), 'Zugang', 'Zugänge')}:\n")
            for eintrag in liste:
                zeile = f"  {eintrag.name}"
                if eintrag.anzeigename:
                    zeile += f" ({eintrag.anzeigename})"
                if not eintrag.aktiv:
                    zeile += "  – stillgelegt"
                print(zeile)

                rollen = []
                if eintrag.verwalter:
                    rollen.append("verwaltet Zugänge")
                if eintrag.alle_postfaecher:
                    rollen.append("sieht alle Postfächer")
                elif eintrag.postfaecher:
                    rollen.append(
                        "sieht: " + ", ".join(sorted(eintrag.postfaecher))
                    )
                else:
                    rollen.append("sieht nichts")
                if not eintrag.pruefwert:
                    rollen.append("KEIN PASSWORT")
                print(f"      {' · '.join(rollen)}")
            return 0

        name = args.name

        if args.was == "hinzufuegen":
            try:
                neu = Benutzer(name, anzeigename=args.anzeigename)
                neu.passwort_setzen(_passwort_erfragen(neu.name))
                if args.alle:
                    neu.alle_postfaecher = True
                if args.postfach:
                    neu.postfaecher = list(args.postfach)
                neu.verwalter = args.verwalter
                liste.hinzufuegen(neu)
                archiv.benutzer_setzen(liste)
            except BenutzerFehler as fehler:
                print(fehler, file=sys.stderr)
                return 1

            print(f"Zugang »{neu.name}« angelegt.")
            if not (neu.alle_postfaecher or neu.postfaecher):
                print(
                    "Er sieht noch nichts. Postfächer zuordnen mit:\n"
                    f"  mailburg zugaenge {args.archiv} rechte {neu.name} --alle"
                )
            return 0

        eintrag = liste.finden(name)
        if eintrag is None:
            print(f"»{name}« gibt es nicht.", file=sys.stderr)
            return 1

        if args.was == "passwort":
            try:
                eintrag.passwort_setzen(_passwort_erfragen(eintrag.name))
            except BenutzerFehler as fehler:
                print(fehler, file=sys.stderr)
                return 1
            archiv.benutzer_setzen(liste)
            print(f"Passwort für »{eintrag.name}« gesetzt.")
            return 0

        if args.was == "rechte":
            if args.alle:
                eintrag.alle_postfaecher = True
            if args.nur:
                eintrag.alle_postfaecher = False
                eintrag.postfaecher = list(args.nur)
            if args.verwalter:
                eintrag.verwalter = True
            if args.kein_verwalter:
                eintrag.verwalter = False

            try:
                archiv.benutzer_setzen(liste)
            except BenutzerFehler as fehler:
                print(fehler, file=sys.stderr)
                return 1

            if eintrag.alle_postfaecher:
                print(f"»{eintrag.name}« sieht alle Postfächer.")
            elif eintrag.postfaecher:
                print(f"»{eintrag.name}« sieht: {', '.join(eintrag.postfaecher)}")
            else:
                print(f"»{eintrag.name}« sieht nichts.")
            return 0

        # stilllegen / zulassen
        eintrag.aktiv = args.was == "zulassen"
        try:
            archiv.benutzer_setzen(liste)
        except BenutzerFehler as fehler:
            print(fehler, file=sys.stderr)
            return 1
        print(
            f"»{eintrag.name}« ist "
            f"{'wieder zugelassen' if eintrag.aktiv else 'stillgelegt'}."
        )
        return 0


def _passwort_erfragen(name: str) -> str:
    """Fragt ein Passwort ab – nie als Argument.

    Ein Passwort auf der Befehlszeile steht in der Prozessliste und in
    der Verlaufsdatei der Shell.
    """
    import getpass

    return getpass.getpass(f"Passwort für »{name}« (mind. 10 Zeichen): ")


def cmd_server(args: argparse.Namespace) -> int:
    """Startet den Dienst der Server Edition."""
    from mailburg.server import einstellungen as serverlage

    try:
        from mailburg.server.dienst import starten
    except ImportError:
        print(
            "Für den Dienst fehlen Pakete.\n"
            "Nachrüsten mit:  pip install 'mailburg[server]'",
            file=sys.stderr,
        )
        return 2

    try:
        lage = serverlage.Serverlage.aus_umgebung()
    except serverlage.Fehlt as fehler:
        print(fehler, file=sys.stderr)
        print(
            f"\nErwartet werden diese Umgebungsvariablen:\n"
            f"  {serverlage.ARCHIV}   der Ordner des Archivs (nötig)\n"
            f"  {serverlage.ADRESSE}  worauf gelauscht wird "
            f"(Vorgabe {serverlage.STANDARD_ADRESSE})\n"
            f"  {serverlage.ANSCHLUSS}     der Port "
            f"(Vorgabe {serverlage.STANDARD_ANSCHLUSS})",
            file=sys.stderr,
        )
        return 1

    if not serverlage.anschluss_frei(lage.adresse, lage.anschluss):
        print(
            f"Auf {lage.adresse}:{lage.anschluss} lauscht schon etwas.\n\n"
            f"Meistens ist es ein zweiter MailBurg-Server, der noch läuft – "
            f"in einem anderen\nFenster oder als Dienst. Nachsehen mit:\n\n"
            f"  ss -ltnp | grep :{lage.anschluss}\n\n"
            f"Oder einen anderen Port nehmen:\n\n"
            f"  {serverlage.ANSCHLUSS}={lage.anschluss + 1} mailburg server",
            file=sys.stderr,
        )
        return 1

    print(f"MailBurg Server {__version__}")
    print(f"  Archiv:     {lage.archiv}")
    print(f"  Erreichbar: http://{lage.adresse}:{lage.anschluss}/")
    if lage.oeffentlich:
        print(
            "\n  Achtung: Dieser Dienst lauscht über den eigenen Rechner\n"
            "  hinaus. Solange es keine Anmeldung gibt, gehört er hinter\n"
            "  ein VPN oder eine Firewall.",
            file=sys.stderr,
        )
    print()
    return starten(lage)


def cmd_tresor(args: argparse.Namespace) -> int:
    """Passwörter auf einem Rechner ohne Schlüsselbund."""
    from mailburg.core import accounts, tresor

    if args.was == "schluessel":
        try:
            neu = tresor.schluessel_erzeugen()
        except tresor.TresorFehler as fehler:
            print(fehler, file=sys.stderr)
            return 1

        print("Ein neuer Hauptschlüssel:\n")
        print(f"  {neu}\n")
        print("Legen Sie ihn dorthin, wo der Dienst ihn findet – und sonst")
        print("niemand. Zum Beispiel:\n")
        print("  install -m 600 /dev/null /etc/mailburg/schluessel")
        print(f"  echo '{neu}' > /etc/mailburg/schluessel")
        print(f"  export {tresor.UMGEBUNG_DATEI}=/etc/mailburg/schluessel\n")
        print("**Bewahren Sie ihn zusätzlich außerhalb dieses Rechners auf.**")
        print("Ohne ihn sind die abgelegten Passwörter verloren – dann müssen")
        print("sie alle neu eingegeben werden.")
        return 0

    if args.was == "liste":
        eintraege = tresor.eintraege()
        if not eintraege:
            print("Im Tresor liegt nichts.")
            return 0
        print(f"{sprache.anzahl(len(eintraege), 'Eintrag', 'Einträge')}:")
        for name in eintraege:
            print(f"  {name}")
        return 0

    if args.was == "pruefen":
        if not tresor.verfuegbar():
            print(
                "Es ist kein Hauptschlüssel eingerichtet. "
                f"Setzen Sie {tresor.UMGEBUNG_DATEI} oder {tresor.UMGEBUNG}.",
                file=sys.stderr,
            )
            return 1

        eintraege = tresor.eintraege()
        schlecht = 0
        for name in eintraege:
            try:
                tresor.holen(name)
                print(f"  {name}: lesbar")
            except tresor.TresorFehler:
                print(f"  {name}: NICHT LESBAR", file=sys.stderr)
                schlecht += 1

        if not eintraege:
            print("Im Tresor liegt nichts.")
        elif schlecht:
            print(
                f"\n{sprache.anzahl(schlecht, 'Eintrag', 'Einträge')} "
                f"nicht lesbar. Vermutlich der falsche Hauptschlüssel.",
                file=sys.stderr,
            )
            return 1
        return 0

    # uebernehmen
    if not tresor.verfuegbar():
        print(
            "Es ist kein Hauptschlüssel eingerichtet. Legen Sie zuerst "
            "einen an:\n\n  mailburg tresor schluessel\n",
            file=sys.stderr,
        )
        return 1
    if not accounts.schluesselbund_verfuegbar():
        print(
            "Auf diesem Rechner ist kein Schlüsselbund erreichbar – es gibt "
            "also nichts zu übernehmen. Dieser Befehl gehört auf den "
            "Arbeitsplatz, auf dem die Postfächer eingerichtet wurden.",
            file=sys.stderr,
        )
        return 1

    # **Am Tresor vorbei lesen.** ``passwort_holen`` nähme sonst den
    # Tresor, weil der ja gerade eingerichtet ist - und übernähme dessen
    # eigene Einträge auf sich selbst.
    import keyring

    liste = accounts.Kontenliste()
    uebernommen, ohne = 0, []
    for konto in liste.konten:
        try:
            wort = keyring.get_password(APP_ID, konto.schluessel)
        except Exception:  # noqa: BLE001 – ein gesperrter Schlüsselbund wirft
            wort = None
        if wort:
            tresor.setzen(konto.schluessel, wort)
            uebernommen += 1
        else:
            ohne.append(konto.name)

    print(f"{sprache.anzahl(uebernommen, 'Passwort', 'Passwörter')} übernommen.")
    if ohne:
        print(
            f"Ohne hinterlegtes Passwort: {', '.join(ohne)}. "
            f"Diese müssen auf dem Server neu eingegeben werden."
        )
    print(
        "\nDie Datei liegt unter:\n"
        f"  {paths.config_dir() / tresor.DATEI}\n\n"
        "Sie und der Hauptschlüssel gehören auf den Server – aber nicht "
        "denselben Weg.\nWer beides zusammen abfängt, hat die Postfächer."
    )
    return 0


def cmd_regeln(args: argparse.Namespace) -> int:
    """Zeigt, ergänzt oder entfernt Einstufungsregeln.

    **Wozu.** In einem Geschäftsarchiv landet private Post, die dort
    Aufbewahrungsfristen unterliegt, die für sie nicht gelten. Eine
    Regel nimmt das vorweg: Was aus dem Vereinsordner kommt, ist privat,
    ohne dass jemand es Mail für Mail nachträgt.

    Die Regel greift beim Aufnehmen, nicht beim Abruf – geholt wird
    alles, eingestuft nur, was passt. Bestehende Post bleibt
    unangetastet; dafür gibt es ``regeln anwenden``.
    """
    from mailburg.core.archive import Archive
    from mailburg.core.regeln import BESCHRIFTUNG, FELDER, Regel, Regelwerk
    from mailburg.core.retention import Category

    archiv_pfad = Path(args.archiv).expanduser().resolve()
    schreibend = args.was in ("hinzufuegen", "entfernen", "anwenden")

    with Archive.open(archiv_pfad, exclusive=schreibend) as archiv:
        werk = archiv.regeln

        if args.was == "zeigen":
            if not len(werk):
                print("Keine Regeln eingerichtet.")
                print()
                print("Eine anlegen, etwa:")
                print(f"  mailburg regeln {args.archiv} hinzufuegen "
                      f"von '*@verein.example' privat")
                return 0
            print(f"{sprache.anzahl(len(werk), 'Regel', 'Regeln')}, "
                  f"in dieser Reihenfolge geprüft:")
            for nummer, regel in enumerate(werk, 1):
                zustand = "" if regel.aktiv else "  (abgeschaltet)"
                print(f"  {nummer}. {regel.beschreibung()}{zustand}")
                if regel.bemerkung:
                    print(f"     {regel.bemerkung}")
            print()
            print("Die erste passende Regel gilt. Eine Ausnahme gehört "
                  "deshalb nach oben.")
            return 0

        if args.was == "hinzufuegen":
            if args.feld not in FELDER:
                print(f"'{args.feld}' ist kein Feld. Möglich: "
                      f"{', '.join(FELDER)}", file=sys.stderr)
                return 2
            try:
                kategorie = Category(args.kategorie)
            except ValueError:
                print(f"'{args.kategorie}' ist keine Kategorie. Möglich: "
                      f"{', '.join(k.value for k in Category)}",
                      file=sys.stderr)
                return 2
            try:
                neu = Regel(
                    feld=args.feld, muster=args.muster, kategorie=kategorie,
                    bemerkung=args.bemerkung or "",
                )
            except ValueError as fehler:
                print(str(fehler), file=sys.stderr)
                return 2

            # Vorne einfügen, wenn gewünscht: Eine Ausnahme muss vor die
            # allgemeinere Regel, sonst greift sie nie.
            regeln = list(werk)
            if args.zuerst:
                regeln.insert(0, neu)
            else:
                regeln.append(neu)
            archiv.regeln_setzen(Regelwerk(regeln))
            print(f"Regel angelegt: {neu.beschreibung()}")
            print("Sie gilt für Post, die ab jetzt aufgenommen wird.")
            return 0

        if args.was == "entfernen":
            if not 1 <= args.nummer <= len(werk):
                print(f"Es gibt keine Regel {args.nummer}. "
                      f"Vorhanden: 1 bis {len(werk)}", file=sys.stderr)
                return 2
            regeln = list(werk)
            weg = regeln.pop(args.nummer - 1)
            archiv.regeln_setzen(Regelwerk(regeln))
            print(f"Entfernt: {weg.beschreibung()}")
            print("Bereits eingestufte Post bleibt, wie sie ist.")
            return 0

        # anwenden
        if not len(werk):
            print("Keine Regeln eingerichtet – es gibt nichts anzuwenden.")
            return 0

        treffer = archiv.index.search("", limit=1_000_000)
        vorgemerkt = []
        for eintrag in treffer:
            # **Jeder Fundort zählt.** Dieselbe Mail kann in zwei Ordnern
            # liegen; trifft eine Regel auch nur auf einen davon zu, ist
            # sie gemeint. Andersherum entschiede die Reihenfolge, in der
            # die Datenbank die Ordner ausspuckt – und das wäre Zufall.
            ordner = [
                z["folder"] for z in archiv.index.db.execute(
                    """SELECT l.folder FROM locations l
                       JOIN messages m ON m.id = l.msg_id
                       WHERE m.hash = ?""",
                    (eintrag.hash,),
                )
            ] or [""]

            befund = None
            for einer in ordner:
                befund = werk.einstufung(
                    ordner=einer, von=eintrag.from_addr or "", an=""
                )
                if befund is not None:
                    break
            if befund is None:
                continue
            kategorie, begruendung = befund
            if eintrag.category == kategorie.value:
                continue
            vorgemerkt.append((eintrag, kategorie, begruendung))

        if not vorgemerkt:
            print("Keine Mail müsste umgestuft werden.")
            return 0

        print(f"{sprache.mails(len(vorgemerkt))} "
              + ("würde" if len(vorgemerkt) == 1 else "würden")
              + " umgestuft:")
        for eintrag, kategorie, _ in vorgemerkt[:10]:
            print(f"   {eintrag.date or '        '}  "
                  f"{(eintrag.category or 'unbestimmt'):>13} → "
                  f"{kategorie.value:<13} {eintrag.subject[:40]}")
        if len(vorgemerkt) > 10:
            print(f"   … und {len(vorgemerkt) - 10} weitere")

        if not args.wirklich:
            print()
            print("Nichts geändert. Zum Ausführen: --wirklich")
            return 0

        for eintrag, kategorie, begruendung in vorgemerkt:
            archiv.classify(
                eintrag.hash, kategorie, actor="Regel", note=begruendung
            )
        print()
        print(f"Umgestuft: {sprache.mails(len(vorgemerkt))}. "
              f"Im Journal vermerkt.")
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

    # **Erst nachsehen, ob das Ziel überhaupt da ist.** Ein
    # Einhängepunkt ohne eingehängten Datenträger sieht aus wie ein
    # leerer Ordner; ohne diese Prüfung liefe die Sicherung durch und
    # landete auf der Systemplatte. Auffallen würde das erst, wenn man
    # sie braucht.
    #
    # Im Zeitplan (--leise) wird nichts angelegt: Ein fehlender Ordner
    # ist dort kein Anlass, einen neuen zu erfinden, sondern der
    # Hinweis, dass die Platte fehlt.
    darf, grund = sicherung.ziel_pruefen(
        archiv_pfad, ziel, anlegen=not args.leise
    )
    if not darf:
        print(f"Fehler: {grund}", file=sys.stderr)
        return 1

    if sicherung.gleiche_platte(archiv_pfad, ziel):
        # Kein Abbruch: Es gibt Aufbauten, in denen das gewollt ist -
        # ein Cloud-Ordner auf derselben Platte, der anderswohin
        # synchronisiert. Aber gesagt gehört es.
        print(
            "Achtung: Die Sicherung liegt auf demselben Datenträger wie "
            "das Archiv. Geht der verloren, ist beides weg.",
            file=sys.stderr,
        )

    try:
        befund = sicherung.packen(archiv_pfad, ziel)
    except sicherung.SicherungFehler as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    if not args.leise:
        print(f"Gesichert: {befund.ziel}")
        print(
            f"  {sprache.dateien(befund.dateien)}, "
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

    k = konten_befehle.add_parser(
        "anmelden",
        help="ein Postfach per OAuth2 anmelden",
        description=(
            "Öffnet den Browser, meldet das Postfach beim Anbieter an und "
            "legt die Zugangsmarken im Schlüsselbund ab. Nötig bei "
            "Microsoft, wo die Anmeldung mit Passwort abgeschaltet ist. "
            "MailBurg bringt keine eigene Anwendungskennung mit – Sie "
            "registrieren Ihre eigene, siehe docs/oauth2.md."
        ),
    )
    k.add_argument("name", help="Kurzname des Postfachs")
    k.add_argument(
        "--anbieter",
        help="microsoft oder google. Ohne Angabe der schon hinterlegte.",
    )
    k.add_argument(
        "--kennung",
        help="Kennung Ihrer beim Anbieter registrierten Anwendung",
    )
    k.set_defaults(func=cmd_konten_anmelden)

    k = konten_befehle.add_parser(
        "abmelden",
        help="die OAuth2-Anmeldung eines Postfachs zurücknehmen",
    )
    k.add_argument("name", help="Kurzname des Postfachs")
    k.set_defaults(func=cmd_konten_abmelden)

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

    p = subparsers.add_parser(
        "verfahrensdoku",
        help="Entwurf einer Verfahrensdokumentation nach GoBD",
        description=(
            "Erzeugt den technischen Teil aus der eigenen Konfiguration. "
            "Der organisatorische Teil bleibt als sichtbare Lücke stehen "
            "– verantwortlich für die Verfahrensdokumentation ist "
            "ausschließlich der Steuerpflichtige."
        ),
    )
    p.add_argument("archiv")
    p.add_argument(
        "ziel", nargs="?",
        help="Zieldatei (.md). Ohne Angabe wird der Text ausgegeben.",
    )
    p.set_defaults(func=cmd_verfahrensdoku)

    p = subparsers.add_parser(
        "auskunft",
        help="alles zu einer Person zusammenstellen (Art. 15 DSGVO)",
        description=(
            "Sucht alle Nachrichten, in denen eine Person vorkommt, und "
            "packt sie auf Wunsch als ZIP – mit einem Begleitblatt, das "
            "nennt, was noch zu prüfen ist. MailBurg stellt zusammen; "
            "herausgegeben wird von einem Menschen."
        ),
    )
    p.add_argument("archiv")
    p.add_argument("adresse", help="Mailadresse der betroffenen Person")
    p.add_argument(
        "ziel", nargs="?",
        help="Zieldatei (.zip). Ohne Angabe wird nur gezählt.",
    )
    p.add_argument(
        "--im-text", action="store_true", dest="im_text",
        help=(
            "auch Nachrichten aufnehmen, in denen die Adresse bloß "
            "erwähnt wird – trifft oft Verteiler, in denen die Person "
            "nicht Beteiligte ist"
        ),
    )
    p.set_defaults(func=cmd_auskunft)

    p = subparsers.add_parser(
        "faellig",
        help="zeigen, was seine Aufbewahrungsfrist hinter sich hat",
        description=(
            "Fristen wirken in beide Richtungen: Sie schützen vor zu "
            "frühem Löschen, und nach ihrem Ablauf verlangt die DSGVO, "
            "dass personenbezogene Daten wieder verschwinden. Gelöscht "
            "wird hier nichts – die Entscheidung bleibt beim Anwender."
        ),
    )
    p.add_argument("archiv")
    p.add_argument(
        "--ausfuehrlich", action="store_true",
        help="jede einzelne Mail auflisten, nicht nur die Jahreszahlen",
    )
    p.add_argument(
        "--jahre", type=int, default=None, metavar="ANZAHL",
        help=(
            "nur für Privatarchive: ab welchem Alter eine Mail als alt "
            "gilt (Vorgabe: 10 Jahre). Im Geschäftsarchiv gelten die "
            "gesetzlichen Fristen."
        ),
    )
    p.set_defaults(func=cmd_faellig)

    p = subparsers.add_parser(
        "einstufen",
        help="Mails aufbewahrungsrechtlich einordnen",
        description=(
            "Stuft die Treffer einer Suche als Handelsbrief, Buchungsbeleg "
            "oder privat ein. Davon hängt ab, wie lange MailBurg das "
            "Löschen bremst – sechs, acht oder zehn Jahre. Ohne "
            "--wirklich wird nur gezeigt, was geschähe."
        ),
    )
    p.add_argument("archiv")
    p.add_argument("suche", help="Suchausdruck, etwa »von:steuerkanzlei«")
    p.add_argument(
        "kategorie",
        help="handelsbrief, buchungsbeleg, privat oder unbestimmt",
    )
    p.add_argument(
        "--wirklich", action="store_true",
        help="die Einstufung tatsächlich vornehmen",
    )
    p.set_defaults(func=cmd_einstufen)

    p = subparsers.add_parser(
        "zugaenge",
        help="wer sich am Archiv anmelden darf (Server Edition)",
        description=(
            "Zugänge und ihre Rechte – derselbe Bestand wie in der "
            "Oberfläche unter »Einstellungen → Zugänge verwalten«, nur "
            "ohne Fenster. Auf einem Server gibt es keines.\n\n"
            "Solange MailBurg nur auf einem Arbeitsplatz läuft, ändern "
            "Zugänge nichts: Wer am Rechner sitzt, hat das Archiv ohnehin."
        ),
    )
    p.add_argument("archiv")
    unter = p.add_subparsers(dest="was", required=True)

    u = unter.add_parser("liste", help="wer eingetragen ist")
    u.set_defaults(func=cmd_zugaenge)

    u = unter.add_parser("hinzufuegen", help="einen Zugang anlegen")
    u.add_argument("name", help="Anmeldename, kleingeschrieben")
    u.add_argument("--anzeigename", default="", help="Vor- und Nachname")
    u.add_argument(
        "--alle", action="store_true", help="darf alle Postfächer sehen")
    u.add_argument(
        "--postfach", action="append", default=[],
        help="ein Postfach, das er sehen darf (mehrfach möglich)")
    u.add_argument(
        "--verwalter", action="store_true",
        help="darf Zugänge anlegen und Rechte vergeben")
    u.set_defaults(func=cmd_zugaenge)

    u = unter.add_parser("rechte", help="Rechte eines Zugangs ändern")
    u.add_argument("name")
    u.add_argument("--alle", action="store_true", help="alle Postfächer")
    u.add_argument(
        "--nur", action="append", default=[],
        help="nur diese Postfächer (mehrfach möglich)")
    u.add_argument("--verwalter", action="store_true")
    u.add_argument(
        "--kein-verwalter", dest="kein_verwalter", action="store_true")
    u.set_defaults(func=cmd_zugaenge)

    u = unter.add_parser("passwort", help="ein neues Passwort setzen")
    u.add_argument("name")
    u.set_defaults(func=cmd_zugaenge)

    u = unter.add_parser(
        "stilllegen",
        help="der Zugang meldet sich nicht mehr an, bleibt aber eingetragen")
    u.add_argument("name")
    u.set_defaults(func=cmd_zugaenge)

    u = unter.add_parser("zulassen", help="einen stillgelegten wieder zulassen")
    u.add_argument("name")
    u.set_defaults(func=cmd_zugaenge)

    p = subparsers.add_parser(
        "server",
        help="MailBurg als Dienst betreiben (Server Edition)",
        description=(
            "Startet den Dienst. Er liest seine Einstellungen aus "
            "Umgebungsvariablen – den Weg kennen systemd, Docker und die "
            "Windows-Dienstverwaltung gleichermaßen.\n\n"
            "In der Vorgabe lauscht er nur auf dem eigenen Rechner. Ein "
            "Archivdienst, der beim ersten Start ungefragt im ganzen Netz "
            "steht, wäre eine böse Überraschung."
        ),
    )
    p.set_defaults(func=cmd_server)

    p = subparsers.add_parser(
        "tresor",
        help="Passwörter ohne Schlüsselbund – für den Serverbetrieb",
        description=(
            "Auf einem Server ohne Desktop gibt es keinen Schlüsselbund: "
            "Er hängt an einer Anmeldesitzung, und ein Dienst läuft ohne. "
            "Der Tresor tritt dort an seine Stelle – eine verschlüsselte "
            "Datei, deren Hauptschlüssel woanders liegt. Er greift nur, "
            "wenn ein Hauptschlüssel eingerichtet ist; auf einem "
            "Arbeitsplatz bleibt alles beim Schlüsselbund."
        ),
    )
    unter = p.add_subparsers(dest="was", required=True)

    u = unter.add_parser(
        "schluessel", help="einen neuen Hauptschlüssel erzeugen")
    u.set_defaults(func=cmd_tresor)

    u = unter.add_parser(
        "uebernehmen",
        help="Passwörter aus dem Schlüsselbund in den Tresor legen",
        description=(
            "Für den Umzug: Auf dem Arbeitsplatz ausführen, auf dem die "
            "Postfächer eingerichtet sind. Die entstandene Datei gehört "
            "dann auf den Server."
        ),
    )
    u.set_defaults(func=cmd_tresor)

    u = unter.add_parser("liste", help="was im Tresor liegt")
    u.set_defaults(func=cmd_tresor)

    u = unter.add_parser(
        "pruefen", help="ob sich alle Einträge lesen lassen")
    u.set_defaults(func=cmd_tresor)

    p = subparsers.add_parser(
        "regeln",
        help="Post beim Aufnehmen einstufen lassen",
        description=(
            "Regeln stufen eingehende Post ein, ohne dass jemand sie Mail "
            "für Mail nachträgt. Nützlich vor allem im Geschäftsarchiv: "
            "Was aus dem Vereinsordner kommt, ist privat und unterliegt "
            "keiner Aufbewahrungsfrist. Geholt wird trotzdem alles – die "
            "Regel bestimmt nur die Einstufung."
        ),
    )
    p.add_argument("archiv")
    unter = p.add_subparsers(dest="was", required=True)

    u = unter.add_parser("zeigen", help="die eingerichteten Regeln auflisten")
    u.set_defaults(func=cmd_regeln)

    u = unter.add_parser("hinzufuegen", help="eine Regel anlegen")
    u.add_argument("feld", help="ordner, von oder an")
    u.add_argument(
        "muster",
        help="Suchmuster mit * und ?, etwa »*@verein.example«",
    )
    u.add_argument(
        "kategorie", nargs="?", default="privat",
        help="privat (Vorgabe), handelsbrief, buchungsbeleg oder unbestimmt",
    )
    u.add_argument(
        "--zuerst", action="store_true",
        help="ganz nach oben stellen – für Ausnahmen von einer weiteren Regel",
    )
    u.add_argument("--bemerkung", default="", help="wozu diese Regel da ist")
    u.set_defaults(func=cmd_regeln)

    u = unter.add_parser("entfernen", help="eine Regel löschen")
    u.add_argument("nummer", type=int, help="die Nummer aus »regeln zeigen«")
    u.set_defaults(func=cmd_regeln)

    u = unter.add_parser(
        "anwenden",
        help="die Regeln auf bereits archivierte Post anwenden",
        description=(
            "Beim Aufnehmen greifen die Regeln von selbst. Bestehende Post "
            "rühren sie nicht an – wer das will, sagt es hier ausdrücklich. "
            "Ohne --wirklich wird nur gezeigt, was geschähe."
        ),
    )
    u.add_argument(
        "--wirklich", action="store_true",
        help="die Umstufung tatsächlich vornehmen",
    )
    u.set_defaults(func=cmd_regeln)

    p = subparsers.add_parser("suchhilfe", help="die Suchsprache erklären")
    p.set_defaults(func=cmd_hilfe_suche)

    p = subparsers.add_parser(
        "werkzeuge",
        help="zeigen, ob die Texterkennung bereitsteht",
        description=(
            "Zeigt, welche Hilfsprogramme MailBurg für Volltext und "
            "Texterkennung findet. Wenn eine eingescannte Rechnung im "
            "Archiv liegt und die Suche sie nicht findet, steht hier, ob "
            "es am Scan lag oder daran, dass die Texterkennung gar nicht "
            "lief."
        ),
    )
    p.set_defaults(func=cmd_werkzeuge)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ArchiveLocked as exc:
        print(f"Archiv gesperrt:\n{exc}", file=sys.stderr)
        return 3
    except IndexOutdated as exc:
        # Ein Traceback wäre hier besonders unangebracht: Wer nach einer
        # Aktualisierung sein Archiv nicht mehr öffnen kann, denkt an
        # Datenverlust. Es geht aber nur das Verzeichnis neu, nicht die
        # Post - und der Weg dorthin steht in der Meldung.
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    except ArchiveError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        # **Der wahrscheinlichste Grund ist eine verschwundene Platte.**
        # Externe Platte abgezogen, Netzlaufwerk getrennt, Cloud nicht
        # mehr eingehängt. Bisher schlug das als nackter Traceback
        # durch - ein Wall aus Python-Zeilen, der die einzige wichtige
        # Frage nicht beantwortet: Ist mein Archiv jetzt kaputt?
        #
        # Es ist nicht kaputt, und das darf man sagen. MailBurg
        # schreibt in der Reihenfolge Ablage, Journal, Index; bricht es
        # dazwischen ab, fehlt höchstens der letzte Eintrag. Am
        # 2026-08-28 nachgestellt: 1000 Mails abgelegt, Platte mitten im
        # Lauf gezogen, danach Hash-Kette unversehrt.
        # **Ein ungültiger Pfad ist die häufigere Ursache.** WinError 123
        # heißt »Die Syntax für den Dateinamen ist falsch« und trifft
        # fast immer denselben Fall: eine Umgebungsvariable, die nicht
        # aufgelöst wurde. Wer einen PowerShell-Befehl in die klassische
        # Eingabeaufforderung tippt, bekommt »$env:USERPROFILE« wörtlich
        # in den Pfad geschrieben. Am 2026-08-29 unter Windows genau so
        # passiert.
        if getattr(exc, "winerror", None) == 123 or isinstance(
            exc, (NotADirectoryError,)
        ):
            print(
                f"Dieser Pfad ist nicht verwendbar:\n"
                f"  {getattr(exc, 'filename', '') or exc}\n"
                f"\n"
                f"Steht darin noch eine Variable wie »$env:USERPROFILE« "
                f"oder »%USERPROFILE%«? Die löst nur die passende "
                f"Eingabeschale auf – »$env:…« in PowerShell, »%…%« in "
                f"der Eingabeaufforderung. Am sichersten ist der "
                f"ausgeschriebene Pfad.",
                file=sys.stderr,
            )
            return 2

        # Der Pfad kann unter verschiedenen Namen ankommen: »archiv« bei
        # den meisten Befehlen, »pfad« beim Anlegen.
        archiv = getattr(args, "archiv", None) or getattr(args, "pfad", None)
        weg = archiv is not None and not Path(archiv).expanduser().is_dir()
        if weg:
            print(
                f"Der Archivordner {archiv} ist nicht mehr erreichbar.\n"
                f"\n"
                f"Meist steckt eine abgezogene Platte dahinter, ein "
                f"getrenntes Netzlaufwerk oder ein Cloud-Ordner, der "
                f"nicht mehr eingehängt ist.\n"
                f"\n"
                f"Am Archiv kann dabei nichts zu Schaden gekommen sein: "
                f"MailBurg legt erst die Mail ab, dann den "
                f"Journaleintrag, dann den Index. Bricht es dazwischen "
                f"ab, fehlt höchstens der letzte Eintrag - der nächste "
                f"Lauf holt ihn nach. Hängen Sie den Datenträger wieder "
                f"ein und lassen Sie zur Beruhigung »mailburg pruefen« "
                f"laufen.",
                file=sys.stderr,
            )
            return 4
        print(f"Fehler beim Zugriff: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nAbgebrochen.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
