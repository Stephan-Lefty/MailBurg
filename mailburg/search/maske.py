"""Aus ausgefüllten Feldern einen Suchausdruck bauen.

**Warum das hier liegt und nicht in der Oberfläche.** Bis zum
2026-08-31 stand diese Übersetzung in ``ui/suchmaske.py``, verwoben mit
Qt-Widgets. Für den Browser hätte es sie ein zweites Mal gebraucht – und
zwei Fassungen derselben Übersetzung weichen voneinander ab, sobald
jemand ein Feld ergänzt. Dann fände dieselbe Eingabe im Fenster etwas
anderes als im Browser, und niemand käme darauf, warum.

Jetzt beschreibt :data:`FELDER` einmal, welche Felder es gibt, und
:func:`ausdruck` macht daraus die Suche. Beide Masken zeigen dieselben
Felder in derselben Reihenfolge, weil sie dieselbe Liste lesen.

**Die Maske kann nichts, was die Suchsprache nicht kann.** Das ist
Absicht: Sie zeigt den Ausdruck, den sie zusammensetzt, und wer sie
benutzt, lernt die Sprache nebenbei. Ein Feld, für das es keine
Schreibweise gäbe, wäre eine Sackgasse.
"""

from __future__ import annotations

from dataclasses import dataclass


def quoten(wert: str) -> str:
    """Setzt einen Wert in Anführungszeichen, wenn er Leerzeichen enthält."""
    wert = wert.strip()
    if not wert:
        return ""
    return f'"{wert}"' if " " in wert else wert


@dataclass(frozen=True)
class Feld:
    """Ein Eingabefeld der Maske."""

    name: str
    """Wie es in Formularen und Wörterbüchern heißt."""

    beschriftung: str
    schluessel: str = ""
    """Das Wort der Suchsprache. Leer heißt: Freitext ohne Präfix."""

    hinweis: str = ""
    """Ein Beispiel oder eine Erklärung, klein darunter."""

    art: str = "text"
    """``text``, ``haken``, ``auswahl`` oder ``datum``."""

    auswahl: tuple[tuple[str, str], ...] = ()
    """Bei ``auswahl``: Paare aus Wert und Beschriftung."""


#: Die Felder der Maske, in der Reihenfolge, in der sie erscheinen.
#:
#: Wer hier eines ergänzt, bekommt es in beiden Masken – im Fenster und
#: im Browser. Wer es nur in einer ergänzt, hat den Fehler gebaut, den
#: dieses Modul verhindern soll.
FELDER = (
    Feld("begriff", "Suchen nach", "",
         "Sucht in Betreff, Text, Absender, Empfänger und Anhängen"),
    Feld("von", "Absender", "von", "z. B. müller oder @firma.example"),
    Feld("an", "An, Kopie oder Blindkopie", "an"),
    Feld("betreff", "Betreff", "betreff"),
    Feld("datei", "Dateiname eines Anhangs", "datei", "z. B. *.pdf"),
    Feld("konto", "Postfach", "konto", art="auswahl"),
    Feld("ordner", "Ordner", "ordner", art="auswahl"),
    Feld("jahr", "Jahr", "jahr", "eine Zahl oder ein Bereich wie 2020-2024"),
    Feld("seit", "Verschickt oder empfangen ab", "seit",
         "TT.MM.JJJJ", art="datum"),
    Feld("bis", "… bis", "bis", "TT.MM.JJJJ", art="datum"),
    Feld("archiviert", "Ins Archiv aufgenommen", "archiviert",
         "Das ist nicht dasselbe: Eine Mail von 2016 kann heute "
         "hinzugekommen sein"),
    Feld("mit_anhang", "Nur mit Anhang", "hat:anhang", art="haken"),
    Feld("typ", "Anhang vom Typ", "typ", "pdf, docx, jpg …"),
    Feld("groesse", "Größe", "groesse", "z. B. >5MB oder <100KB"),
    Feld("wichtigkeit", "Wichtigkeit", "wichtigkeit", art="auswahl",
         auswahl=(("", "egal"), ("hoch", "hoch"), ("normal", "normal"),
                  ("niedrig", "niedrig"))),
    Feld("ohne", "Ohne diese Wörter", "-",
         "Mehrere durch Leerzeichen getrennt"),
)


def ausdruck(werte: dict[str, str]) -> str:
    """Setzt aus ausgefüllten Feldern einen Suchausdruck zusammen.

    Leere Felder fallen weg. Was nicht in :data:`FELDER` steht, wird
    übergangen – ein Formular aus dem Netz enthält, was jemand
    hineinschreibt, nicht was vorgesehen war.
    """
    teile: list[str] = []

    for feld in FELDER:
        roh = str(werte.get(feld.name, "") or "").strip()

        if feld.art == "haken":
            # Ein Häkchen trägt seinen ganzen Ausdruck im Schlüssel.
            if roh and roh.lower() not in ("0", "false", "nein", "off"):
                teile.append(feld.schluessel)
            continue

        if not roh:
            continue

        if feld.name == "ohne":
            # Mehrere Wörter, jedes einzeln ausgeschlossen.
            teile.extend(f"-{quoten(wort)}" for wort in roh.split())
            continue

        if feld.name == "typ":
            # »pdf« und ».pdf« meinen dasselbe.
            teile.append(f"typ:{roh.lstrip('.')}")
            continue

        if not feld.schluessel:
            teile.append(quoten(roh))
            continue

        teile.append(f"{feld.schluessel}:{quoten(roh)}")

    return " ".join(teile)


def leer(werte: dict[str, str]) -> bool:
    """Ob die Maske nichts eingrenzt – dann fände sie alles."""
    return not ausdruck(werte).strip()


def felder(text: str) -> dict[str, str] | None:
    """Zerlegt einen Suchausdruck zurück in Maskenfelder.

    Gibt ``None`` zurück, wenn das nicht geht – dann lässt sich dieser
    Ausdruck in der Maske nicht darstellen.

    **Wozu die Umkehrung gebraucht wird.** Wer einen gespeicherten
    Suchordner bearbeitet und auf *Ausführlich …* geht, erwartet die
    Felder gefüllt. Von joka63 gemeldet (2026-09-22), der es zuerst
    anders gebaut hatte: Er legte die Feldwerte zusätzlich ab, also
    doppelt neben dem Ausdruck – und war damit selbst unzufrieden. Zwei
    Quellen für dieselbe Sache laufen auseinander.

    **Warum ``None`` und nicht »so gut es geht«.** Die Maske *schreibt
    zurück*: Wer sie mit OK schließt, ersetzt den Ausdruck durch das,
    was in den Feldern steht. Alles, was hier verloren ginge, wäre
    danach still weg – an einem Suchordner, den sich jemand über Monate
    zurechtgelegt hat.

    Deshalb joka63s Lösung, und sie ist besser als jede Teilübernahme:
    Der Knopf *Ausführlich …* wird nur angeboten, wenn diese Funktion
    etwas zurückgibt. **Wo die Umwandlung nicht geht, gibt es den Weg
    gar nicht** – der Sonderfall wird nicht erklärt, sondern unmöglich
    gemacht.

    **Streng ist hier richtig.** Zwei freie Wörter (``rechnung
    müller``) sind etwas anderes als eine Phrase (``"rechnung
    müller"``), und die Maske erzeugt nur die Phrase. Ein Ausdruck mit
    beidem kam nie aus ihr heraus; wer ihn von Hand geschrieben hat,
    braucht sie auch nicht.
    """
    from mailburg.search.query import _TERM_RE

    text = (text or "").strip()
    werte: dict[str, str] = {}
    if not text:
        return werte

    nach_schluessel = {
        f.schluessel.lower(): f for f in FELDER
        if f.schluessel and f.art != "haken" and f.name != "ohne"
    }
    haken = {f.schluessel.lower(): f for f in FELDER if f.art == "haken"}
    freitext = next((f for f in FELDER if not f.schluessel), None)
    ohne: list[str] = []

    for treffer in _TERM_RE.finditer(text):
        wert = treffer.group("quoted")
        gequotet = wert is not None
        if not gequotet:
            wert = treffer.group("bare") or ""
        wert = wert.strip()
        if not wert:
            continue

        schluessel = (treffer.group("field") or "").lower()
        verneint = bool(treffer.group("neg"))

        if verneint:
            if schluessel or gequotet:
                # »-von:x« und »-"a b"« erzeugt die Maske nicht.
                return None
            ohne.append(wert)
            continue

        ganz = f"{schluessel}:{wert}".lower() if schluessel else ""
        if ganz in haken:
            feld = haken[ganz]
            if feld.name in werte:
                return None
            werte[feld.name] = "1"
            continue

        if not schluessel:
            if freitext is None or freitext.name in werte:
                return None
            werte[freitext.name] = wert
            continue

        feld = nach_schluessel.get(schluessel)
        if feld is None or feld.name in werte:
            # Ein Wort der Suchsprache, für das es kein Feld gibt, oder
            # dasselbe Feld zweimal – beides kann die Maske nicht.
            return None
        werte[feld.name] = wert

    if ohne:
        werte["ohne"] = " ".join(ohne)

    # **Die Probe aufs Exempel, und sie ist der eigentliche Wächter.**
    # Der Knopf verlässt sich darauf, dass nichts verloren geht – das
    # lässt sich hier ausrechnen, statt es zu versprechen. Weicht der
    # neu gebaute Ausdruck ab, war die Zerlegung nicht verlustfrei, und
    # dann wird lieber nichts angeboten.
    #
    # Verglichen wird wortweise: Die Reihenfolge der Felder liegt in
    # FELDER fest, und ein Ausdruck, der sie anders anordnet, ergäbe
    # dieselbe Suche. Das ist kein Verlust.
    if sorted(ausdruck(werte).split()) != sorted(text.split()):
        return None
    return werte
