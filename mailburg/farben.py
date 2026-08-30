"""Die gemeinsame Farbpalette, an einer Stelle.

Sie ist hier entstanden und gilt seit 2026-08-28 für alle Programme. Erklärt
sind die Farben in [assets/farben.md](../assets/farben.md); hier stehen nur die
Werte, damit Oberfläche, Bilder und Ausgaben nicht jeweils eigene Zahlen führen.

Warum eine eigene Datei und keine Konstanten im Oberflächencode: Weil die
Palette in mehr als einem Programm gilt. Diese Datei ist zum Kopieren gedacht -
sie hat keine Abhängigkeiten und lässt sich unverändert in ein anderes Projekt
legen.
"""

from __future__ import annotations

# -- Blau, die Leitfarbe ---------------------------------------------------

BLAU_HELL = "#0e8af6"    # oberes Ende des Verlaufs im Icon
BLAU = "#1668e3"         # Flächen, Knöpfe, Hervorhebungen
BLAU_TIEF = "#0047a7"    # unteres Ende des Verlaufs im Icon
BLAU_DUNKEL = "#0d3a8a"  # Ränder und Schatten auf blauem Grund
BLAU_NACHT = "#0d2141"   # Hintergründe im dunklen Thema
BLAU_LEUCHT = "#6cb6ff"  # Verweise auf dunklem Grund; auf hellem zu blass

# -- Grau, alles andere ----------------------------------------------------

GRAU_PAPIER = "#f7f9fc"  # Seitenhintergrund, helles Thema
GRAU_HELL = "#d6dde8"    # Linien, Trenner, Rahmen
GRAU_MITTE = "#97a1ad"   # zurückgenommener Text auf *dunklem* Grund
# Für zurückgenommenen Text auf hellem Grund. GRAU_MITTE taugt dort nicht:
# Auf GRAU_PAPIER erreicht es nur 2,48 Kontrast und verfehlt damit sogar die
# 3,0 für große Schrift. Aufgefallen ist das nicht beim Hinsehen, sondern
# durch den Test in tests/test_farben.py - solche Werte sieht man nicht, man
# rechnet sie. Auf hellem Grund kommt dieser Ton auf 4,75 und ist damit auch
# für Fließtext zulässig.
GRAU_LEISE = "#667080"
GRAU = "#5b6672"         # Fließtext auf hellem Grund
GRAU_DUNKEL = "#3a4048"  # Überschriften
GRAU_KOHLE = "#2b323c"   # Flächen im dunklen Thema
GRAU_NACHT = "#20262f"   # Seitenhintergrund, dunkles Thema
WEISS = "#ffffff"

# -- Signalfarben ----------------------------------------------------------
#
# Sparsam verwenden. Sie sagen »hier ist etwas passiert«, und das verlieren
# sie, sobald sie zur Dekoration werden.

ROT = "#c62828"         # Fehler, Gescheitertes
ROT_HELL = "#ef9a9a"    # dasselbe auf dunklem Grund
GRUEN = "#2e7d32"       # Erledigtes, Gesendetes
GRUEN_HELL = "#81c784"  # dasselbe auf dunklem Grund

#: Der Verlauf des Icons, von oben nach unten.
ICON_VERLAUF = (BLAU_HELL, BLAU_TIEF)

# -- Die Server Edition ----------------------------------------------------
#
# Dasselbe Wappen in Rot. Entschieden am 2026-08-31: Wer ein Bild sieht,
# soll auf einen Blick wissen, ob er den Arbeitsplatz oder den Server vor
# sich hat - und trotzdem dieselbe Burg erkennen.
#
# **Die Leitfarbe ist das ROT der Palette**, kein eigener Ton. Zwei Rot,
# die sich um Nuancen unterscheiden, wären schlimmer als eines: Niemand
# könnte sie auseinanderhalten, aber jeder müsste sich fragen, welches
# gerade gemeint ist.
#
# Das hat einen Preis, und der gehört benannt: In der Weboberfläche des
# Servers steht dann die Marke in derselben Farbe wie Fehlermeldungen.
# Dort müssen Fehler deshalb über Form kenntlich sein - Symbol, Rahmen,
# Text -, nicht über die Farbe allein. Für Menschen mit Farbsehschwäche
# gilt das ohnehin.

SERVER_ROT = ROT                # Turm, Fahne, Tor, Schriftzug, das Wort SERVER
SERVER_ROT_HELL = ROT_HELL      # das Wort SERVER auf dunklem Grund
SERVER_ROT_TIEF = "#7a1414"     # die Fensterschlitze im roten Turm
SERVER_ROT_LEUCHT = "#e5484d"   # oberes Ende des Verlaufs im Icon
SERVER_ROT_NACHT = "#8f1616"    # unteres Ende desselben Verlaufs

#: Der Verlauf des Server-Icons, von oben nach unten.
SERVER_ICON_VERLAUF = (SERVER_ROT_LEUCHT, SERVER_ROT_NACHT)


def als_css(dunkel: bool = False) -> str:
    """Die Palette als CSS-Variablen für die Weboberfläche.

    Erzeugt statt gepflegt: Eine zweite, von Hand geschriebene Liste derselben
    Werte wiche früher oder später ab, und man fände es erst, wenn ein Knopf
    eine andere Farbe hat als der Rest.
    """
    gemeinsam = {
        "--blau": BLAU,
        "--blau-hell": BLAU_HELL,
        "--blau-tief": BLAU_TIEF,
        "--rot": ROT_HELL if dunkel else ROT,
        "--gruen": GRUEN_HELL if dunkel else GRUEN,
    }
    if dunkel:
        gemeinsam.update({
            "--grund": GRAU_NACHT,
            "--flaeche": GRAU_KOHLE,
            "--linie": GRAU_DUNKEL,
            "--text": GRAU_HELL,
            "--text-leise": GRAU_MITTE,
            "--verweis": BLAU_LEUCHT,
        })
    else:
        gemeinsam.update({
            "--grund": GRAU_PAPIER,
            "--flaeche": WEISS,
            "--linie": GRAU_HELL,
            "--text": GRAU_DUNKEL,
            "--text-leise": GRAU_LEISE,
            "--verweis": BLAU,
        })
    zeilen = "\n".join(f"  {name}: {wert};" for name, wert in gemeinsam.items())
    waehler = ':root[data-thema="dunkel"]' if dunkel else ":root"
    return f"{waehler} {{\n{zeilen}\n}}"


def rgb(farbe: str) -> tuple[int, int, int]:
    """»#1668e3« zu (22, 104, 227) – für Bildbearbeitung und Kontrastrechnung."""
    roh = farbe.lstrip("#")
    if len(roh) == 3:
        roh = "".join(z * 2 for z in roh)
    if len(roh) != 6:
        raise ValueError(f"Keine Farbe im Format #rrggbb: {farbe!r}")
    return int(roh[0:2], 16), int(roh[2:4], 16), int(roh[4:6], 16)


def _helligkeit(farbe: str) -> float:
    """Relative Helligkeit nach WCAG 2.1."""
    def kanal(wert: int) -> float:
        anteil = wert / 255
        return anteil / 12.92 if anteil <= 0.03928 else ((anteil + 0.055) / 1.055) ** 2.4

    r, g, b = (kanal(k) for k in rgb(farbe))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def kontrast(vorne: str, hinten: str) -> float:
    """Kontrastverhältnis zweier Farben, 1 bis 21.

    WCAG verlangt 4.5 für Fließtext und 3.0 für große Schrift. Bei einem
    Werkzeug, das neben DialOS entsteht, sollte das nicht nur eine Zahl in
    einer Norm sein – die Prüfung steht deshalb in den Tests.
    """
    hell, dunkel = sorted((_helligkeit(vorne), _helligkeit(hinten)), reverse=True)
    return (hell + 0.05) / (dunkel + 0.05)
