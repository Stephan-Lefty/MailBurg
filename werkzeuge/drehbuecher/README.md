# Drehbücher für die Videos

Zwei Drehbücher, Szene für Szene: was auf dem Bildschirm passiert, was
dazu gesagt wird, worauf beim Aufnehmen zu achten ist.

| Datei | Inhalt | Länge |
|---|---|---|
| [1-einrichten.md](1-einrichten.md) | Installieren, Assistent, erster Abruf | ~5 Minuten |
| [2-arbeiten.md](2-arbeiten.md) | Suchen, Lesen, Zurückholen, Regeln, Sichern | ~7 Minuten |

## Vor der ersten Aufnahme

**Niemals mit dem eigenen Archiv aufnehmen.** Absender, Betreffs,
Adressen und Geschäftspartner stehen sonst im Bild, und ein Video lässt
sich schlechter zurückholen als ein Screenshot – es wird kopiert,
eingebettet und weiterverbreitet.

Dafür gibt es das Vorführarchiv:

```bash
python werkzeuge/vorfuehrarchiv.py
mailburg-gui ~/MailBurg-Vorfuehrung
```

Es enthält 27 erfundene Mails über mehrere Jahre, auf zwei Postfächern
und in mehreren Ordnern – genug, dass sich Suche, Sortierung und
Eingrenzung wirklich vorführen lassen. Alle Adressen enden auf
`.example`, einer nach RFC 2606 reservierten Endung, die nie jemandem
gehören wird. Ein Test wacht darüber.

Nur der Einrichtungsassistent im ersten Video braucht ein echtes
Postfach. Nehmen Sie dafür ein Wegwerf-Konto, dessen Adresse Sie zeigen
dürfen.

## Was in beiden Videos vorkommen muss

**Der SmartScreen-Hinweis unter Windows.** Nicht überspringen, nicht
beschönigen. Wer ihn unvorbereitet sieht, bricht ab.

**Der Satz zur Rechtslage.** MailBurg *unterstützt* revisionssicheren
Betrieb, es *stellt ihn nicht her* – keine Software kann das. Die
Begründung steht in [RECHTLICHES.md](../../RECHTLICHES.md).

**Nichts vorspielen, was nicht wirklich lief.** Steht für eine Szene
kein Server zur Verfügung, lieber den Befehl zeigen und den Ablauf
beschreiben, als ein Ergebnis nachzustellen.

## Wenn sich die Oberfläche ändert

Die Drehbücher nennen Menüpunkte wörtlich. Ändert sich einer, stimmen
sie nicht mehr – anders als die Bilder in `docs/bilder`, die sich mit
`werkzeuge/screenshots.py` neu erzeugen lassen. Wer einen Menüpunkt
umbenennt, sieht bitte hier nach.
