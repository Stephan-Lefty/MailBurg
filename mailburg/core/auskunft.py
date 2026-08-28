"""Auskunft nach Art. 15 DSGVO – alles zu einer Person herausgeben.

Wer fragt, was über ihn gespeichert ist, hat Anspruch auf eine Kopie.
Bei einem Mailarchiv sind das die Nachrichten, in denen er vorkommt –
als Absender, als Empfänger, in Kopie oder namentlich im Text.

**Was dieses Modul nicht kann und niemals können wird.** Eine Mail an
Herrn Müller enthält oft auch Daten von Frau Schmidt: ihre Adresse im
Verteiler, ihren Namen im Text, ihre Unterschrift im Anhang. Art. 15
Abs. 4 DSGVO sagt dazu, dass die Kopie »die Rechte und Freiheiten
anderer Personen nicht beeinträchtigen« darf. Wo diese Grenze im
Einzelfall verläuft, kann kein Programm entscheiden – das ist eine
Abwägung, und sie gehört zum Verantwortlichen.

MailBurg stellt deshalb zusammen und sagt dazu, was noch zu prüfen ist.
Es gibt die Auskunft nicht heraus; das tut ein Mensch.

**Warum der Vorgang ins Journal gehört.** Art. 5 Abs. 2 DSGVO verlangt,
dass der Verantwortliche die Einhaltung nachweisen kann. Wer in einem
Jahr gefragt wird, ob er eine Auskunft fristgerecht erteilt hat, will
auf einen Eintrag zeigen können.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

#: Was MailBurg dem Paket beilegt. Ohne diese Datei wäre der Export ein
#: Haufen ``.eml`` ohne Zusammenhang – und der Empfänger wüsste nicht,
#: was er in der Hand hält.
BEGLEITBLATT = "AUSKUNFT.txt"


@dataclass
class Befund:
    """Was für eine Person zusammengetragen wurde."""

    adresse: str
    treffer: list = field(default_factory=list)
    als_absender: int = 0
    als_empfaenger: int = 0
    im_text: int = 0
    ziel: Path | None = None

    @property
    def anzahl(self) -> int:
        return len(self.treffer)


def zusammenstellen(archiv, adresse: str, *, im_text: bool = False) -> Befund:
    """Sucht alles, was zu einer Person im Archiv liegt.

    ``im_text`` nimmt auch Mails auf, in denen die Adresse bloß erwähnt
    wird. Das ist voreingestellt aus: Eine Erwähnung im Fließtext trifft
    oft Weiterleitungen und Verteiler, in denen die Person selbst nicht
    Beteiligte ist – und jede zusätzliche Mail im Paket ist eine, in der
    womöglich Daten Dritter stehen.
    """
    befund = Befund(adresse=adresse)
    gesehen: dict[str, object] = {}

    def sammeln(ausdruck: str) -> int:
        neu = 0
        for eintrag in archiv.index.search(ausdruck, limit=1_000_000):
            if eintrag.hash not in gesehen:
                gesehen[eintrag.hash] = eintrag
                neu += 1
        return neu

    # In dieser Reihenfolge, damit die Zählung stimmt: Wer Absender
    # *und* Empfänger war, zählt beim ersten Fund.
    befund.als_absender = sammeln(f"von:{adresse}")
    befund.als_empfaenger = sammeln(f"an:{adresse}")
    if im_text:
        befund.im_text = sammeln(f"text:{adresse}")

    befund.treffer = sorted(gesehen.values(), key=lambda t: t.date or "")
    return befund


def _begleitblatt(archiv, befund: Befund) -> str:
    """Der Text, der dem Paket beiliegt.

    Nennt, was drin ist und woher es stammt – und was der
    Verantwortliche vor der Herausgabe noch prüfen muss.
    """
    heute = datetime.now().strftime("%d.%m.%Y")
    zeilen = [
        "Auskunft nach Artikel 15 DSGVO",
        "=" * 30,
        "",
        f"Zusammengestellt am {heute} aus dem Archiv »{archiv.name}«.",
        f"Betroffene Person: {befund.adresse}",
        "",
        f"Gefunden: {befund.anzahl} Nachrichten",
        f"  als Absender:  {befund.als_absender}",
        f"  als Empfänger: {befund.als_empfaenger}",
    ]
    if befund.im_text:
        zeilen.append(f"  im Text erwähnt: {befund.im_text}")

    if befund.treffer:
        von = (befund.treffer[0].date or "")[:10]
        bis = (befund.treffer[-1].date or "")[:10]
        zeilen += ["", f"Zeitraum: {von} bis {bis}"]

    zeilen += [
        "",
        "Die Nachrichten liegen im Ordner »nachrichten« als .eml-Dateien.",
        "Diese öffnet jedes Mailprogramm; sie sind unverändert so, wie sie",
        "angekommen sind.",
        "",
        "Zweck der Speicherung",
        "-" * 21,
    ]

    if archiv.mode.is_business:
        jahre = sorted(
            {
                str(archiv.policy.years(k))
                for k in _kategorien()
                if archiv.policy.years(k)
            }
        )
        zeilen += [
            "Archivierung geschäftlicher Korrespondenz zur Erfüllung",
            "handels- und steuerrechtlicher Aufbewahrungspflichten",
            f"({', '.join(jahre)} Jahre je nach Art des Schriftstücks).",
        ]
    else:
        zeilen += [
            "Privates Mailarchiv. Es unterliegt keiner gesetzlichen",
            "Aufbewahrungspflicht.",
        ]

    zeilen += [
        "",
        "Vor der Herausgabe zu prüfen",
        "-" * 28,
        "",
        "MailBurg hat zusammengestellt, nicht entschieden. Zwei Dinge",
        "kann ein Programm nicht beurteilen:",
        "",
        "1. DATEN DRITTER. Eine Nachricht an die betroffene Person",
        "   enthält oft auch Daten anderer: Adressen im Verteiler, Namen",
        "   im Text, Unterschriften in Anhängen. Nach Art. 15 Abs. 4",
        "   DSGVO darf die Kopie die Rechte anderer nicht",
        "   beeinträchtigen. Was davon zu schwärzen oder wegzulassen",
        "   ist, muss ein Mensch entscheiden.",
        "",
        "2. VOLLSTÄNDIGKEIT. Gesucht wurde nach der angegebenen",
        "   Adresse. Wer unter mehreren Adressen schreibt, taucht",
        "   nur unter der gesuchten auf. Fragen Sie im Zweifel nach",
        "   weiteren Adressen und stellen Sie erneut zusammen.",
        "",
        "Diese Zusammenstellung ist keine Rechtsberatung.",
    ]
    return "\n".join(zeilen) + "\n"


def _kategorien():
    from mailburg.core.retention import Category

    return list(Category)


def packen(archiv, befund: Befund, ziel: Path) -> Befund:
    """Schreibt die Auskunft als ZIP-Datei.

    Ein Ordner ``nachrichten`` mit den ``.eml`` und daneben das
    Begleitblatt. Kein PDF: Eine Mail als PDF zu drucken heißt, sie zu
    verändern – Anhänge fallen weg, Kopfzeilen verschwinden, und die
    Datei taugt nicht mehr als das, was sie war. Wer die Auskunft
    ausgedruckt braucht, druckt sie selbst.
    """
    ziel = Path(ziel)
    if ziel.suffix.lower() != ".zip":
        ziel = ziel.with_suffix(".zip")
    ziel.parent.mkdir(parents=True, exist_ok=True)

    # Erst danebenschreiben, am Ende umbenennen: Eine halbfertige
    # Auskunft, die aussieht wie eine fertige, wäre schlimmer als keine.
    vorlaeufig = ziel.with_name(f".{ziel.name}.unfertig")
    try:
        with zipfile.ZipFile(vorlaeufig, "w", zipfile.ZIP_DEFLATED) as paket:
            paket.writestr(BEGLEITBLATT, _begleitblatt(archiv, befund))
            for nummer, eintrag in enumerate(befund.treffer, 1):
                roh = archiv.store.get(eintrag.hash, eintrag.bucket)
                datum = (eintrag.date or "ohne-datum")[:10]
                paket.writestr(f"nachrichten/{nummer:04d}-{datum}.eml", roh)
        vorlaeufig.replace(ziel)
    finally:
        vorlaeufig.unlink(missing_ok=True)

    befund.ziel = ziel

    # **Der Vorgang gehört ins Journal.** Art. 5 Abs. 2 DSGVO verlangt,
    # dass der Verantwortliche die Einhaltung nachweisen kann. Wer in
    # einem Jahr gefragt wird, ob er fristgerecht Auskunft erteilt hat,
    # will auf einen Eintrag zeigen können.
    archiv.journal.append(
        "note",
        art="auskunft_art15",
        betroffen=befund.adresse,
        nachrichten=befund.anzahl,
        ziel=str(ziel),
    )
    archiv.journal.flush()
    return befund
