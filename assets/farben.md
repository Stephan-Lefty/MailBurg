# Farben

Die gemeinsame Palette für alle Programme. Sie ist hier entstanden und gilt
seit 2026-08-28 als Vorgabe – Abweichungen nur, wenn ausdrücklich etwas
anderes gesagt wird.

Diese Datei ist zum Weiterreichen gedacht: Sie liegt in jedem Repository gleich
und ist die Antwort auf »welches Blau war das noch?«. Die maschinenlesbaren
Werte stehen in [`mailburg/farben.py`](../mailburg/farben.py), damit
Oberfläche und Bilder nicht jeweils eigene Zahlen führen.

## Blau – die Leitfarbe

| Name | Wert | Wofür |
|---|---|---|
| `BLAU_HELL` | `#0e8af6` | oberes Ende des Verlaufs im Icon |
| `BLAU` | `#1668e3` | die Leitfarbe. Flächen, Knöpfe, Hervorhebungen |
| `BLAU_TIEF` | `#0047a7` | unteres Ende des Verlaufs im Icon |
| `BLAU_DUNKEL` | `#0d3a8a` | Ränder und Schatten auf blauem Grund |
| `BLAU_NACHT` | `#0d2141` | Hintergründe im dunklen Thema |
| `BLAU_LEUCHT` | `#6cb6ff` | Verweise auf dunklem Grund. Auf hellem zu blass |

Der Verlauf im Icon geht von `BLAU_HELL` oben nach `BLAU_TIEF` unten, senkrecht
über die volle Höhe.

## Grau – alles andere

| Name | Wert | Wofür |
|---|---|---|
| `GRAU_PAPIER` | `#f7f9fc` | Seitenhintergrund im hellen Thema |
| `GRAU_HELL` | `#d6dde8` | Linien, Trenner, Rahmen |
| `GRAU_MITTE` | `#97a1ad` | zurückgenommener Text auf **dunklem** Grund |
| `GRAU_LEISE` | `#667080` | dasselbe auf **hellem** Grund |
| `GRAU` | `#5b6672` | Fließtext auf hellem Grund |
| `GRAU_DUNKEL` | `#3a4048` | Überschriften |
| `GRAU_KOHLE` | `#2b323c` | Flächen im dunklen Thema |
| `GRAU_NACHT` | `#20262f` | Seitenhintergrund im dunklen Thema |
| `WEISS` | `#ffffff` | Zeichnungen auf Blau, Flächen im hellen Thema |

Zwei Töne für dieselbe Aufgabe, weil einer nicht reicht: `GRAU_MITTE` kommt auf
hellem Grund nur auf 2,48 Kontrast und verfehlt damit sogar die 3,0, die WCAG
für große Schrift verlangt. Das sieht man einem Farbwert nicht an – es fiel
erst auf, als `tests/test_farben.py` es nachgerechnet hat.

## Signalfarben

Sparsam. Sie sagen »hier ist etwas passiert«, und das verliert seine Wirkung,
wenn sie zur Dekoration werden.

| Name | Wert | Wofür |
|---|---|---|
| `ROT` | `#c62828` | Fehler, Gescheitertes |
| `ROT_HELL` | `#ef9a9a` | dasselbe auf dunklem Grund |
| `GRUEN` | `#2e7d32` | Erledigtes, Gesendetes |
| `GRUEN_HELL` | `#81c784` | dasselbe auf dunklem Grund |

## Die Server Edition

Dasselbe Wappen in Rot. Entschieden am 2026-08-31: Wer ein Bild sieht, soll auf
einen Blick wissen, ob er den Arbeitsplatz oder den Server vor sich hat – und
trotzdem dieselbe Burg erkennen.

| Name | Wert | Wofür |
|---|---|---|
| `SERVER_ROT` | `#c62828` | Turm, Fahne, Tor, Schriftzug, das Wort SERVER |
| `SERVER_ROT_HELL` | `#ef9a9a` | das Wort SERVER auf dunklem Grund |
| `SERVER_ROT_TIEF` | `#7a1414` | die Fensterschlitze im roten Turm |
| `SERVER_ROT_LEUCHT` | `#e5484d` | oberes Ende des Verlaufs im Icon |
| `SERVER_ROT_NACHT` | `#8f1616` | unteres Ende desselben Verlaufs |

**Die Leitfarbe ist das `ROT` der Palette**, kein eigener Ton. Zwei Rot, die
sich um Nuancen unterscheiden, wären schlimmer als eines: Niemand könnte sie
auseinanderhalten, aber jeder müsste sich fragen, welches gerade gemeint ist.

**Das hat einen Preis, und der gehört benannt.** In der Weboberfläche des
Servers steht die Marke dann in derselben Farbe wie Fehlermeldungen. Dort
müssen Fehler deshalb über die Form kenntlich sein – Symbol, Rahmen, Text –,
nicht über die Farbe allein. Für Menschen mit Farbsehschwäche gilt das ohnehin.

**Rot ist heikler als Blau.** Auf Weiß kommt `SERVER_ROT` auf 5,62. Auf dem
Markenblau wären es 1,10, im dunklen Thema 2,71 – beides unlesbar. Deshalb der
Wechsel auf `SERVER_ROT_HELL` (7,07), sobald der Grund dunkel ist.

Die Bilder entstehen aus `werkzeuge/server_logo.py`, nicht von Hand.

## Eine Anmerkung zur Herkunft

Diese Palette ist aus MailBurgs Icon und Banner gewachsen und wurde am
2026-08-28 zur Vorgabe für alle Programme erklärt. Dabei fiel auf, dass
`#97a1ad` – hier lange als Textfarbe verwendet – auf hellem Grund nur 2,6
Kontrast erreicht. Die betroffenen Stellen in `assets/uebersicht.svg` wurden
korrigiert; siehe das Änderungsprotokoll.
