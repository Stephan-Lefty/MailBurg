"""Der Archivierungslauf.

Hier steckt die Schleife, die eine Quelle leerliest und ins Archiv schreibt.
Sie liegt bewusst nicht in der Kommandozeile: Die grafische Oberfläche wird
dieselbe Logik brauchen, nur mit einer anderen Fortschrittsanzeige.

**Warum parallel.** Text aus einem PDF zu holen ist rechenintensiv und
läuft in einem Fremdprozess oder in Python-Code – in beiden Fällen wäre ein
einzelner Faden der Flaschenhals. Ein ``ProcessPoolExecutor`` verteilt das
auf alle Kerne. Fäden (``ThreadPoolExecutor``) helfen hier nicht: Der GIL
lässt Python-Code nicht wirklich gleichzeitig laufen.

**Warum nicht alles parallel.** Eine Mail an einen anderen Prozess zu
schicken kostet, weil sie dafür kopiert wird. Bei einer zwei Kilobyte
großen Nachricht ohne Anhang ist das teurer als das Zerlegen selbst.
Deshalb wandern nur die großen Nachrichten in den Pool – die kleinen erledigt
der Hauptprozess nebenbei.

**Warum eine Warteschlange mit Deckel.** Ohne Begrenzung würde die Schleife
Hunderttausende Aufträge einreihen, bevor der erste fertig ist, und der
Speicher liefe voll. Es sind immer nur so viele unterwegs, wie die Kerne
verarbeiten können.
"""

from __future__ import annotations

import os
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass, field, replace
from typing import Any

#: Ab dieser Größe geht eine Mail in den Pool. Darunter lohnt der Aufwand
#: für das Hin- und Herschicken nicht.
SCHWELLE_PARALLEL = 24 * 1024

#: So viele Aufträge dürfen gleichzeitig unterwegs sein, als Vielfaches der
#: Kernzahl.
PUFFER_JE_KERN = 3


@dataclass
class Statistik:
    """Wie ein Lauf ausging."""

    gelesen: int = 0
    neu: int = 0
    vorhanden: int = 0
    fehlgeschlagen: int = 0
    mit_anhangstext: int = 0
    anhaenge: dict[str, int] = field(default_factory=dict)
    """Zählung der Anhänge nach Art – etwa wie viele PDF eingescannt waren."""

    def __str__(self) -> str:
        teile = [f"{self.gelesen} gelesen", f"{self.neu} neu aufgenommen"]
        if self.vorhanden:
            teile.append(f"{self.vorhanden} bereits vorhanden")
        if self.fehlgeschlagen:
            teile.append(f"{self.fehlgeschlagen} fehlgeschlagen")
        return ", ".join(teile)

    @property
    def eingescannt(self) -> int:
        """PDF ohne Textebene – diese Dokumente sind nicht durchsuchbar."""
        return self.anhaenge.get("pdf:eingescannt", 0)


def _verarbeiten(roh: bytes, mit_anhangstext: bool) -> tuple[Any, str, dict[str, int]]:
    """Zerlegt eine Mail und holt den Text ihrer Anhänge.

    Läuft im Arbeitsprozess. Die Nutzdaten der Anhänge werden vor der
    Rückgabe entfernt: Sie werden nur zum Auslesen gebraucht und würden
    sonst als Kopie über die Prozessgrenze wandern – bei einem Archivlauf
    wären das Gigabyte ohne jeden Nutzen.
    """
    from mailburg.extract import message, text

    zerlegt = message.parse(roh, with_payloads=mit_anhangstext)
    anhangstext, zaehlung = ("", {})
    if mit_anhangstext and zerlegt.attachments:
        anhangstext, zaehlung = text.aus_mail(zerlegt)

    zerlegt.attachments = [replace(a, payload=b"") for a in zerlegt.attachments]
    return zerlegt, anhangstext, zaehlung


def _umbenennungen_nachziehen(archiv, quelle) -> None:
    """Zieht umbenannte Ordner nach, bevor der Lauf beginnt.

    **Sonst wird der Ordner zweimal geführt.** MailBurg merkt sich den
    Fundort unter dem angezeigten Namen; wird aus »Kunden« ein »Kunden
    2025«, ist der Höchststand für den neuen Namen null. Der ganze
    Ordner wird erneut durchlaufen, jede Mail bekommt einen zweiten
    Fundort, und im Ordnerbaum steht der alte Name als Geist weiter.
    Verloren geht dabei nichts – doppelt liegt auch nichts, die Ablage
    ist inhaltsadressiert –, aber bei fünftausend Mails sind das
    fünftausend überflüssige Journaleinträge.

    Nur Quellen, die es können, werden gefragt: Ein Thunderbird-Profil
    hat keine ``UIDVALIDITY``, und ein Ordner heißt dort, wie er heißt.
    """
    zustand = getattr(quelle, "zustand", None)
    if zustand is None or not hasattr(quelle, "umbenennungen"):
        return

    bekannte = zustand.bekannte_ordner(quelle.account)
    if not bekannte:
        return

    try:
        paare = quelle.umbenennungen(bekannte)
    except Exception:  # noqa: BLE001
        # Eine Erkennung, die scheitert, darf den Abruf nicht kosten.
        # Im schlimmsten Fall wird eben doppelt gelesen, wie bisher.
        return

    for alt, neu in paare:
        umgezogen = archiv.index.ordner_umbenennen(quelle.account, alt, neu)
        if not umgezogen:
            continue
        zustand.ordner_umbenennen(quelle.account, alt, neu)
        # **Der Vorgang gehört ins Journal.** Ein Fundort, der sich
        # ändert, ist eine Änderung am Archiv - und beim nächsten
        # Neuaufbau des Index muss nachvollziehbar sein, warum die Mails
        # jetzt woanders liegen.
        archiv.journal.append(
            "note",
            art="ordner_umbenannt",
            konto=quelle.account,
            alt=alt,
            neu=neu,
            fundorte=umgezogen,
        )
        archiv.journal.flush()
        archiv.index.commit()


def importieren(
    archiv,
    quelle,
    *,
    mit_anhangstext: bool = True,
    prozesse: int | None = None,
    fortschritt=None,
    auf_fehler=None,
) -> Statistik:
    """Liest eine Quelle vollständig ins Archiv.

    ``fortschritt`` wird gelegentlich mit der bisherigen Statistik gerufen,
    ``auf_fehler`` mit der Nachricht und der Ausnahme, wenn eine einzelne
    Mail scheitert. Ein Fehler bricht den Lauf nie ab – eine unlesbare
    Nachricht unter zehntausend darf die übrigen nicht kosten.

    Übergeben wird die ganze ``RawMessage`` und nicht nur ihr Ordner, weil
    der IMAP-Abruf die UID braucht: Nur mit ihr lässt sich die gescheiterte
    Mail beim nächsten Lauf noch einmal anfordern. Ohne sie zöge der
    Höchststand an ihr vorbei, und sie fehlte für immer im Archiv – ohne
    dass es je jemand bemerkte.
    """
    stat = Statistik()
    kerne = prozesse if prozesse is not None else min(os.cpu_count() or 2, 8)
    deckel = max(kerne * PUFFER_JE_KERN, 4)

    _umbenennungen_nachziehen(archiv, quelle)

    def ablegen(nachricht, zerlegt, anhangstext: str) -> None:
        ergebnis = archiv.add(
            nachricht.raw,
            account=quelle.account,
            folder=nachricht.folder,
            uid=nachricht.uid,
            flags=nachricht.flags,
            parsed=zerlegt,
            attachment_text=anhangstext,
        )
        if ergebnis.stored:
            stat.neu += 1
        else:
            stat.vorhanden += 1
        if anhangstext:
            stat.mit_anhangstext += 1

    def zwischenstand() -> None:
        if stat.gelesen % 200 == 0:
            archiv.index.commit()
            archiv.journal.flush()
            if fortschritt:
                fortschritt(stat)

    # Ohne Anhangstext lohnt kein Pool - dann ist nur das MIME-Zerlegen zu
    # tun, und das ist billig.
    if not mit_anhangstext or kerne < 2:
        for nachricht in quelle.iter_messages():
            stat.gelesen += 1
            try:
                zerlegt, anhangstext, zaehlung = _verarbeiten(nachricht.raw, mit_anhangstext)
                for schluessel, anzahl in zaehlung.items():
                    stat.anhaenge[schluessel] = stat.anhaenge.get(schluessel, 0) + anzahl
                ablegen(nachricht, zerlegt, anhangstext)
            except Exception as exc:  # noqa: BLE001
                stat.fehlgeschlagen += 1
                if auf_fehler:
                    auf_fehler(nachricht, exc)
            zwischenstand()
        archiv.index.commit()
        archiv.journal.flush()
        return stat

    offen: dict[Any, Any] = {}

    def einsammeln(fertig) -> None:
        for auftrag in fertig:
            nachricht = offen.pop(auftrag)
            try:
                zerlegt, anhangstext, zaehlung = auftrag.result()
                for schluessel, anzahl in zaehlung.items():
                    stat.anhaenge[schluessel] = stat.anhaenge.get(schluessel, 0) + anzahl
                ablegen(nachricht, zerlegt, anhangstext)
            except Exception as exc:  # noqa: BLE001
                stat.fehlgeschlagen += 1
                if auf_fehler:
                    auf_fehler(nachricht, exc)

    with ProcessPoolExecutor(max_workers=kerne) as pool:
        for nachricht in quelle.iter_messages():
            stat.gelesen += 1

            if nachricht.size < SCHWELLE_PARALLEL:
                # Klein genug, um sie gleich hier zu erledigen.
                try:
                    zerlegt, anhangstext, zaehlung = _verarbeiten(nachricht.raw, True)
                    for schluessel, anzahl in zaehlung.items():
                        stat.anhaenge[schluessel] = stat.anhaenge.get(schluessel, 0) + anzahl
                    ablegen(nachricht, zerlegt, anhangstext)
                except Exception as exc:  # noqa: BLE001
                    stat.fehlgeschlagen += 1
                    if auf_fehler:
                        auf_fehler(nachricht, exc)
            else:
                offen[pool.submit(_verarbeiten, nachricht.raw, True)] = nachricht
                if len(offen) >= deckel:
                    fertig, _ = wait(offen, return_when=FIRST_COMPLETED)
                    einsammeln(fertig)

            zwischenstand()

        einsammeln(list(offen))

    archiv.index.commit()
    archiv.journal.flush()
    return stat
