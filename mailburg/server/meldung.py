"""Wann der Bericht hinausgeht – und was er sagt.

Das Bindeglied zwischen dem Abruf und :mod:`mailburg.core.bericht`:
Dort steht, *wie* eine Mail aussieht und wann sie fällig ist, hier,
*woraus* sie sich speist.

**Getrennt, damit es prüfbar bleibt.** Der Abruf hat ein Archiv, einen
Faden und eine Schleife; diese Entscheidungen hier haben keines davon
nötig und lassen sich deshalb einzeln durchspielen – auch die Fälle,
die im Betrieb hoffentlich nie eintreten.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from mailburg.core import bericht


def standdatei(archiv_uuid: str) -> Path:
    """Wo der Berichtsstand liegt.

    Neben dem Abrufzustand und **nicht im Archiv**: Es ist eine Sache
    des Rechners, nicht des Bestands. Ein Archiv, das umzieht, soll am
    neuen Ort nicht glauben, es habe gestern berichtet.
    """
    from mailburg.core import paths

    return paths.data_dir() / "bericht" / f"{archiv_uuid}.json"


def _passwort_holen() -> str:
    """Das Versandpasswort aus dem Tresor – oder nichts.

    Mancher Postausgangsserver im eigenen Netz will keine Anmeldung;
    dann ist »nichts« die richtige Antwort und kein Fehler.
    """
    from mailburg.core import tresor

    if not tresor.verfuegbar():
        return ""
    try:
        return tresor.holen(bericht.TRESORSCHLUESSEL) or ""
    except Exception:  # noqa: BLE001
        return ""


def nach_einem_lauf(archivpfad, *, neu: int, uebersprungen: int,
                    befund: str, passwort: str = "", melden=None,
                    jetzt: datetime | None = None) -> str:
    """Prüft nach einem Abruf, ob etwas zu melden ist, und meldet es.

    Gibt zurück, was getan wurde – für die Tests und fürs Protokoll.

    **Drei Fälle, und die Reihenfolge ist nicht beliebig:**

    1. Eine **Störung** geht sofort hinaus, ohne auf die Uhrzeit zu
       warten. Wer um sieben erfährt, dass seit Mitternacht nichts mehr
       ankommt, hat sieben Stunden verloren.
    2. Eine **Entwarnung**, sobald eine gemeldete Störung vorbei ist.
       Ohne sie ist eine Störungsmeldung halb so viel wert: Wer abends
       eine bekommt und morgens nichts hört, weiß nicht, ob es wieder
       läuft oder ob auch die Meldung nicht mehr durchkommt.
    3. Der **Tagesbericht** zur eingestellten Zeit, im eingestellten
       Takt.
    """
    lage = bericht.Lage.aus_umgebung()
    if not lage.eingerichtet:
        return "nicht eingerichtet"

    jetzt = jetzt or datetime.now()
    sagen = melden or (lambda *_a, **_k: None)

    from mailburg.core.archive import Archive

    with Archive.open(archivpfad, exclusive=False, passwort=passwort) as archiv:
        name = archiv.name
        gesamt = archiv.index.count()
        pruefung = _pruefen(archiv)

    datei = standdatei(archiv.uuid if hasattr(archiv, "uuid") else name)
    stand = bericht.Stand.lesen(datei)

    stoerung = _stoerung(uebersprungen, befund, pruefung)
    passwort_smtp = _passwort_holen()

    if stoerung:
        if stand.stoerung == stoerung:
            return "Störung bekannt, nicht wiederholt"
        betreff, text = bericht.stoerung_bauen(name, stoerung)
        bericht.senden(lage, betreff, text, passwort_smtp)
        stand.schreiben(datei, stoerung=stoerung)
        sagen(f"Störungsmeldung an {lage.an} geschickt.")
        return "Störung gemeldet"

    if stand.stoerung:
        betreff, text = bericht.entwarnung_bauen(name, stand.stoerung)
        bericht.senden(lage, betreff, text, passwort_smtp)
        stand.schreiben(datei, stoerung="")
        sagen(f"Entwarnung an {lage.an} geschickt.")
        return "Entwarnung gemeldet"

    if not bericht.faellig(lage, stand, jetzt):
        return "noch nicht fällig"

    dazu = max(0, gesamt - stand.mails_zuletzt) if stand.zuletzt else gesamt
    betreff, text, _ = bericht.bericht_bauen(
        name, dazu, gesamt, stand.zuletzt, pruefung, abruf=befund
    )
    bericht.senden(lage, betreff, text, passwort_smtp)
    stand.schreiben(datei, jetzt=jetzt, mails=gesamt)
    sagen(f"Tagesbericht an {lage.an} geschickt.")
    return "Bericht geschickt"


def _pruefen(archiv) -> tuple[str, bool]:
    """Archivprüfung in der Form, die der Bericht braucht.

    **Die Prüfung liest keine Mailinhalte** – sie hält das Journal gegen
    die Dateinamen. Deshalb ist sie täglich bezahlbar, auch bei 70.000
    Mails.
    """
    from mailburg.core.bericht import pruefbericht

    return pruefbericht(archiv.verify())


def _stoerung(uebersprungen: int, befund: str,
              pruefung: tuple[str, bool]) -> str:
    """Was sofort gemeldet werden muss – oder nichts.

    **Nur Dinge, bei denen Post ausbleibt oder das Archiv leidet.** Eine
    Meldung, die bei Kleinigkeiten anschlägt, wird nach zwei Wochen
    weggefiltert, und dann kommt auch die wichtige nicht mehr an.
    """
    text, heikel = pruefung
    if heikel:
        return text.split("\n")[0]
    if uebersprungen:
        return (
            f"{befund}\n\nVon diesen Postfächern kommt keine Post, und der "
            f"Dienst meldet das sonst nicht als Fehler."
        )
    return ""
