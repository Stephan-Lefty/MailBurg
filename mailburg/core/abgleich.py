"""Nachweisen, dass alles Ältere im Archiv ist – vor dem Aufräumen.

Wer seinem Mailprogramm aufträgt, Post nach einem halben Jahr wegzuräumen,
löscht sie bei einem IMAP-Konto **auf dem Server**. Was MailBurg bis dahin
nicht geholt hat, ist unwiederbringlich weg – und niemand merkt es, weil
beide Seiten für sich genommen richtig gearbeitet haben: Der Mailclient hat
aufgeräumt, wie ihm gesagt wurde, und MailBurg hat archiviert, was es
vorfand.

Dieses Modul schließt die Lücke. Es fragt den Server, welche Mails älter
als ein Stichtag sind, und hält jede einzelne gegen das Archiv. Heraus
kommt eine Aussage, auf die man sich stützen kann: *Alle 4.312 Mails vor
dem 26. Februar sind archiviert* – oder eben, welche fehlen.

**Verglichen wird über die UID**, nicht über den Inhalt. Das ist genau,
solange sich ``UIDVALIDITY`` nicht geändert hat; ändert es sich, sind alle
alten Nummern wertlos, und dann sagt der Abgleich das auch. Ein Vergleich
über Inhaltshashes wäre unabhängig davon, würde aber verlangen, jede Mail
noch einmal vom Server zu holen – und damit genau die Übertragung
auslösen, die man sich sparen wollte.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class Ordnerbefund:
    """Was der Abgleich für einen einzelnen Ordner ergab."""

    ordner: str
    auf_dem_server: int = 0
    im_archiv: int = 0
    fehlend: list[int] = field(default_factory=list)
    uidvalidity_geaendert: bool = False

    @property
    def vollstaendig(self) -> bool:
        return not self.fehlend and not self.uidvalidity_geaendert


@dataclass
class Befund:
    """Das Gesamtergebnis für ein Konto."""

    konto: str
    stichtag: date
    ordner: list[Ordnerbefund] = field(default_factory=list)
    warnungen: list[str] = field(default_factory=list)
    fehler: str = ""

    @property
    def geprueft(self) -> int:
        return sum(o.auf_dem_server for o in self.ordner)

    @property
    def fehlend(self) -> int:
        return sum(len(o.fehlend) for o in self.ordner)

    @property
    def unklar(self) -> bool:
        """Ob der Befund nicht belastbar ist.

        Bei geändertem UIDVALIDITY oder einem Fehler beim Abfragen lässt
        sich nichts zusichern – und eine Aussage, die nur meistens stimmt,
        ist hier wertlos: Man würde darauf hin löschen.
        """
        return bool(self.fehler) or any(o.uidvalidity_geaendert for o in self.ordner)

    @property
    def unbedenklich(self) -> bool:
        """Ob nach diesem Befund gefahrlos aufgeräumt werden kann."""
        return not self.unklar and self.fehlend == 0


def stichtag_aus_tagen(tage: int, heute: date | None = None) -> date:
    """Rechnet »älter als N Tage« in ein Datum um."""
    return (heute or date.today()) - timedelta(days=tage)


def pruefen(archiv, quelle, konto_name: str, stichtag: date,
            zustand=None, fortschritt=None) -> Befund:
    """Hält jede Mail vor dem Stichtag gegen das Archiv.

    ``quelle`` ist eine geöffnete ``ImapSource``. ``zustand`` dient nur
    dazu, einen geänderten ``UIDVALIDITY``-Wert zu erkennen – ist er
    anders als beim letzten Abruf, taugen die gespeicherten UIDs nicht
    mehr zum Vergleich.
    """
    befund = Befund(konto=konto_name, stichtag=stichtag)

    try:
        for ordner, auf_dem_server in quelle.uids_vor(stichtag):
            eintrag = Ordnerbefund(ordner=ordner)
            eintrag.auf_dem_server = len(auf_dem_server)

            if zustand is not None:
                gemerkt = zustand.uidvalidity(konto_name, ordner)
                jetzt = quelle._uidvalidity()  # noqa: SLF001
                if gemerkt is not None and jetzt is not None and gemerkt != jetzt:
                    # Der Server hat neu nummeriert. Ein Vergleich über UIDs
                    # verglicht dann Äpfel mit Birnen.
                    eintrag.uidvalidity_geaendert = True
                    befund.ordner.append(eintrag)
                    continue

            im_archiv = archiv.index.uids_im_ordner(konto_name, ordner)
            eintrag.im_archiv = len(auf_dem_server & im_archiv)
            eintrag.fehlend = sorted(auf_dem_server - im_archiv)
            befund.ordner.append(eintrag)

            if fortschritt:
                fortschritt(eintrag)
    except Exception as exc:  # noqa: BLE001 – der Befund darf nicht abstürzen
        befund.fehler = str(exc)

    befund.warnungen = list(getattr(quelle, "warnungen", []))
    return befund


def urteil(befund: Befund) -> str:
    """Formuliert, was der Befund für das Aufräumen bedeutet."""
    tag = befund.stichtag.strftime("%d.%m.%Y")

    if befund.fehler:
        return (
            f"Der Abgleich für »{befund.konto}« ist nicht durchgelaufen: "
            f"{befund.fehler}\nSolange das so ist, sollte im Postfach nichts "
            f"gelöscht werden."
        )

    if befund.unklar:
        betroffen = [o.ordner for o in befund.ordner if o.uidvalidity_geaendert]
        return (
            f"Der Server hat die Nummerierung geändert – in {', '.join(betroffen)} "
            f"lässt sich nicht sagen, was archiviert ist.\nEin vollständiger "
            f"Abruf (»abrufen --voll«) stellt den Vergleich wieder her; bis "
            f"dahin bitte nichts löschen."
        )

    if befund.fehlend:
        return (
            f"{befund.fehlend} von {befund.geprueft} Mails vor dem {tag} fehlen "
            f"im Archiv.\nBitte erst »mailburg abrufen« laufen lassen und "
            f"danach erneut prüfen – vorher darf im Postfach nichts "
            f"aufgeräumt werden."
        )

    if not befund.geprueft:
        return f"Im Postfach »{befund.konto}« liegt nichts, was älter als der {tag} wäre."

    return (
        f"Alle {befund.geprueft} Mails vor dem {tag} sind im Archiv.\n"
        f"Sie können sie im Mailprogramm gefahrlos aufräumen lassen."
    )
