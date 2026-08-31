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
