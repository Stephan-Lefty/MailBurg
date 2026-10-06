[Deutsch](uebernahmeprotokoll-vorlage.md) | [Übersicht](../README.md) | [Anleitungen](README.md) | [Aus MailStore umziehen](mailstore-umzug.md)

# Vorlage: Übernahmeprotokoll E-Mail-Archiv

**Wofür das gut ist.** Wer geschäftliche Post archiviert, muss belegen
können, wie sie in das System gekommen ist und dass dabei nichts
verändert wurde. Beim Wechsel von einem Archivprogramm zum anderen ist
das ein einmaliger Vorgang – und einmalige Vorgänge gehören
protokolliert, solange man sie noch im Kopf hat.

**Das ersetzt die Verfahrensdokumentation nicht.** Diese beschreibt den
*laufenden* Betrieb; MailBurg erzeugt ihren technischen Teil mit
`mailburg verfahrensdoku`. Das Protokoll hier beschreibt den Umzug.

**Verantwortlich bleibt der Steuerpflichtige.** Diese Vorlage ist eine
Hilfe beim Aufschreiben, keine Rechtsberatung. Ob sie für Ihren Fall
genügt, entscheidet Ihr Steuerberater – siehe [RECHTLICHES.md](../RECHTLICHES.md).

---

Alles in `[eckigen Klammern]` ist auszufüllen. **Was Sie nicht wissen,
lassen Sie als sichtbare Lücke stehen** – eine geschätzte Zahl sieht in
einem Protokoll aus wie ein Beleg und ist keiner.

---

## Übernahmeprotokoll E-Mail-Archiv

**[Firma]** · Ablösung von [altes Programm] durch MailBurg ·
Stand [Datum]

### 1. Anlass und Entscheidung

[In zwei, drei Sätzen: Warum wurde gewechselt? Was spricht für die neue
Lösung? Beispiele: Die Daten bleiben im Haus. Keine Lizenzkosten.
Zugriff über den Browser ohne Installation auf den Arbeitsplätzen.]

### 2. Ausgangslage

| | |
|---|---|
| Bisheriges Programm | [Name und Fassung] |
| Bestand | [Anzahl] E-Mails |
| Aufbau | [z. B. 17 Postfächer, 15 Benutzerarchive] |

### 3. Zielsystem

| | |
|---|---|
| Programm | MailBurg [Fassung] |
| Betriebssystem | [z. B. Windows Server 2025 / Debian 13] |
| Ablageort | [Pfad, und ob lokale Platte oder Verbund] |
| Zugriff | [z. B. Browser im Firmennetz, Port 8383] |
| Berechtigungen | [z. B. 5 Zugänge, Rechte je Postfach] |
| Laufender Abruf | [z. B. alle 30 Minuten, Ruhe 17:10–04:00] |

### 4. Verfahren der Übernahme

Die Übernahme erfolgte in zwei getrennten Schritten. So liegt zu jedem
Zeitpunkt eine vollständige Kopie außerhalb beider Programme.

**Schritt 1 – Ausgabe aus dem alten Programm**

- Format: [z. B. EML, also je E-Mail eine Datei in genau der Form, in
  der sie über das Netz übertragen wurde]
- [Wurde die Ordnerstruktur beibehalten?]
- Ergebnis: [Anzahl] Dateien

**Schritt 2 – Einlesen in MailBurg**

- [Wie wurden die Ausgabeordner benannt und zugeordnet?]
- [Ist erkennbar, welche Nachricht aus dem Altbestand stammt?]
- [Blieb die ursprüngliche Ordnerstruktur erhalten?]

> **Die Nachrichten wurden nicht verändert.** MailBurg legt jede E-Mail
> unverändert ab – Byte für Byte so, wie sie angekommen ist. Weder
> Kopfzeilen noch Inhalte werden umgeschrieben oder vereinheitlicht.
> Damit bleiben auch die digitalen Signaturen der Absender überprüfbar.

### 5. Nachweis der Vollständigkeit

| | |
|---|---|
| Bestand im alten Programm | [Anzahl] |
| Ausgegebene Dateien | [Anzahl] |
| Im Archiv vor der Übernahme | [Anzahl] |
| Eingelesen | [Anzahl] |
| Davon bereits vorhanden | [Anzahl] |
| Im Archiv nach der Übernahme | [Anzahl] |
| Dauer des Einlesens | [Zeit] |
| Prüfung der Unversehrtheit | [Ergebnis von `mailburg pruefen`] |

**Mehrfach vorhandene Nachrichten werden einmal abgelegt.** Dieselbe
E-Mail kann in mehreren Postfächern liegen – etwa ein Rundschreiben an
mehrere Empfänger. MailBurg erkennt das am Inhalt und legt sie genau
einmal ab; vermerkt wird dabei jeder Fundort. Die Zahl »davon bereits
vorhanden« beziffert diesen Anteil.

### 6. Unveränderbarkeit und Nachvollziehbarkeit

- **Jeder Vorgang wird protokolliert.** Das Archiv führt ein
  fortlaufendes Journal: wann welche Nachricht aufgenommen wurde, aus
  welchem Postfach und aus welchem Ordner.
- **Das Protokoll ist gegen nachträgliche Änderung gesichert.** Jeder
  Eintrag enthält eine Prüfsumme des vorhergehenden. Wird auch nur ein
  Zeichen geändert, passen die Prüfsummen nicht mehr zusammen, und die
  Prüfung schlägt an.
- **Der Dateiname ist die Prüfsumme des Inhalts.** Eine veränderte
  Nachricht wäre damit sofort erkennbar.
- **Die Weboberfläche kann nicht schreiben.** Über den Browser lässt
  sich ausschließlich suchen und lesen.

Die Unversehrtheit lässt sich jederzeit überprüfen (`mailburg pruefen`).

### 7. Was nicht übernommen wurde

Vollständig übernommen wurden die E-Mails selbst mit allen Anhängen.
Nicht übernommen wurden Verwaltungsangaben des alten Programms:

- [z. B. Markierungen und Einstufungen]
- [z. B. der Lesezustand einzelner Nachrichten]

Diese Angaben sind nicht Bestandteil einer E-Mail, sondern
Zusatzinformationen des jeweiligen Programms; sie lassen sich zwischen
verschiedenen Archivsystemen nicht übertragen.

### 8. Zugriff und Berechtigungen

[Wie viele Zugänge, nach welchem Grundsatz vergeben?]

**Die Einschränkung wirkt bereits in der Suche selbst**, nicht erst bei
der Anzeige. Schon die Trefferzahl verrät damit nicht, dass es
Nachrichten gibt, die man nicht einsehen darf.

Ausgeschiedene Mitarbeiter werden stillgelegt, nicht gelöscht – ihr
Name muss in den Protokollen nachvollziehbar bleiben.

### 9. Sicherung und laufender Betrieb

- [Wo liegt das Archiv, wie ist es gegen Plattenausfall geschützt?]
- [Wie wird gesichert, und wie oft?]
- [Wie oft wird neue Post aufgenommen?]
- [Wer wird benachrichtigt, wenn etwas klemmt?]

### 10. Weiteres Vorgehen

> **Das alte Archiv bleibt zunächst in Betrieb.** Für [Zeitraum] laufen
> beide parallel, und es werden Stichproben verglichen. Erst danach
> wird über die Abschaltung entschieden.
>
> **Der Grund:** Ein Archiv, in dem etwas fehlt, sieht genauso aus wie
> ein vollständiges. Die Vollständigkeit lässt sich nur durch Vergleich
> belegen, nicht durch Betrachtung.

Gesetzliche Aufbewahrungsfristen bleiben davon unberührt.

### 11. Bestätigung

Die vorstehende Übernahme wurde nach dem beschriebenen Verfahren
durchgeführt. Die genannten Zahlen sind den Protokollen des Programms
entnommen.

<br><br>

| | |
|---|---|
| **Ort, Datum** | **Unterschrift** |
| | **[Name ausgeschrieben]**, durchgeführt |

> **Unterschreibt, wer es gemacht hat** – nicht die Geschäftsführung.
> Ein Protokoll bezeugt einen Vorgang; bezeugen kann ihn nur, wer dabei
> war. Die Geschäftsführung nimmt es zur Kenntnis.
>
> **Der Name gehört ausgeschrieben darunter.** Eine Unterschrift ist
> selten zu entziffern, und in zehn Jahren soll noch feststehen, wer
> hier gezeichnet hat.

---

## Wie Sie an die Zahlen kommen

```bash
mailburg info /pfad/zum/Archiv      # Bestand, Postfächer, Zugänge
mailburg pruefen /pfad/zum/Archiv   # Unversehrtheit der Protokollkette
```

Die Zahlen zu »eingelesen« und »davon bereits vorhanden« stehen am Ende
jedes Importlaufs:

```
Fertig: 80.431 gelesen, 80.127 neu aufgenommen, 304 bereits vorhanden
```

**Schreiben Sie sie mit, während der Umzug läuft.** Hinterher sind sie
nur noch mühsam zu rekonstruieren – und was man rekonstruiert, ist
keine Messung mehr.
