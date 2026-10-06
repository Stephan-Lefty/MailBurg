[Übersicht](../README.md) | [Anleitungen](README.md) | [Änderungsprotokoll](../CHANGELOG.md) | [TODO](../TODO.md)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../assets/server/banner-dark-1600.png">
    <img src="../assets/server/banner-1600.png" alt="MailBurg im Browser – E-Mails. Sicher bewahrt." width="620">
  </picture>
</p>

# MailBurg Server

**Alles zum Serverbetrieb an einer Stelle.** Ein Dienst, der rund um die
Uhr läuft, die Post selbst holt und das Archiv im Browser bereitstellt –
für mehrere Menschen, mit getrennten Rechten.

Wer MailBurg am eigenen Arbeitsplatz benutzt, braucht nichts davon;
dafür gibt es [Erste Schritte](erste-schritte.md).

---

## Womit anfangen

| Ich will … | Seite |
|---|---|
| **von Null einrichten**, Schritt für Schritt | [Das Archiv im Browser einrichten](server-einrichten.md) |
| …und zwar auf **Windows Server** | [Windows Server 2025](server-windows.md) |
| wissen, **warum** es so gebaut ist | [Das Archiv im Browser – Entwurf](server.md) |
| ein vorhandenes Archiv **umziehen** | [Windows Server 2025](server-windows.md#kommt-das-archiv-als-sicherungsdatei) |

Unter Windows gibt es dafür ein Fenster: **MailBurg im Browser –
einrichten und warten** (`mailburg-server-einrichten`, oder als eigene
Datei `MailBurg-Server-Einrichten.exe`). Es prüft siebzehn Dinge nach
und stellt neben jedes, was fehlt, den Knopf, der es behebt.

---

## Im Betrieb

**Die Ampel oben im Einrichtungsfenster** beantwortet die Frage, mit der
man es öffnet: Muss ich etwas tun?

| | |
|---|---|
| **Rot** | Es fehlt etwas Zwingendes – der Dienst läuft nicht oder liefert nichts aus. |
| **Gelb** | Es läuft, aber etwas gehört nachgezogen. Der häufigste Fall ist ein Dienst ohne Abruf: Er liefert ein Archiv aus, das nicht mehr wächst. |
| **Grün** | Alles in Ordnung. |

Daneben steht ein Knopf, der zur **ersten** offenen Sache führt.

### Der Tagesbericht

MailBurg schickt, was es getan hat: wie viele Mails dazugekommen sind
und ob das Archiv in Ordnung ist – **geprüft, nicht behauptet**.

Einzustellen unter *Tagesbericht …*: Empfänger, Uhrzeit, Takt (täglich,
alle 7, 14 oder 30 Tage), Postausgangsserver, Absender und Anmeldung.

Drei Dinge, die dabei wichtig sind:

- **Ein eigenes Postfach für den Versand**, nicht eines der
  archivierten. Sonst landet jeder Bericht beim nächsten Abruf wieder
  im Archiv.
- **Eine Störung wartet nicht auf die Uhrzeit.** Sie geht sofort
  hinaus, wiederholt sich nicht, solange sie dieselbe bleibt, und es
  kommt eine Entwarnung, sobald sie behoben ist.
- **Bleibt eine Mail aus, läuft der Dienst nicht mehr.** Das ist dann
  selbst der Befund – und der Grund, warum der Bericht auch dann kommt,
  wenn alles gut ist.

Das Versandpasswort liegt im Tresor, nicht in der Registry. Liegt es
dort schon – weil dasselbe Postfach abgerufen wird –, lässt es sich
übernehmen, ohne es noch einmal einzutippen:

```
mailburg tresor liste
```

**Und vor dem Schließen den Knopf *Probe schicken* drücken.** Sonst
erfahren Sie erst am nächsten Morgen, ob das Passwort stimmt und der
Server die Anmeldung annimmt. Eine Einstellung, die sich einen Tag
später als falsch herausstellt, ist genau die Sorte, vor der diese
Funktion warnen soll.

### Wartung

Im Kasten *Wartung* stehen drei Werkzeuge, für die es sonst nur die
Kommandozeile gibt:

- **Archiv prüfen** – hält die Hash-Kette gegen die Ablage. Drei Fragen
  auf einmal: Ist die Kette unversehrt, liegt zu jeder Mail noch eine
  Datei, und liegt dort etwas, das im Journal nicht vorkommt? Das Letzte
  ist das interessanteste: Eine von Hand hineingelegte Datei ist nicht
  archiviert, sondern untergeschoben.
- **Tresor prüfen** – beide Richtungen. Ein Postfach ohne Anmeldung kann
  der Dienst nicht abrufen, und er meldet das **nicht** als Fehler; er
  überspringt es. Ein Eintrag ohne Postfach ist ein fremdes Passwort auf
  einem Rechner, an dem mehrere Menschen arbeiten.
- **Mails einlesen** – Post aus Dateien übernehmen, etwa einen Export
  aus einem anderen Archivprogramm. Der Dienst wird dafür angehalten und
  bleibt es, bis Sie ihn wieder starten.

Auf der Kommandozeile dasselbe:

```bash
mailburg pruefen ARCHIV
mailburg tresor pruefen
mailburg importieren ARCHIV ORDNER --konto NAME
```

---

## Was man wissen sollte, bevor es ernst wird

**Der Dienst läuft als Systemkonto und hat ein anderes Profil als Sie.**
Ohne `MAILBURG_EINSTELLUNGEN` und `MAILBURG_DATEN` sucht er Kontenliste,
Tresor und Suchindex dort, wo nie ein Mensch etwas hingelegt hat. Er
läuft dann, die Anmeldung geht, und **jede Suche bleibt leer**. Siehe
[Das Archiv im Browser einrichten](server-einrichten.md).

**Im Netz spricht er HTTP.** Anmeldename und Passwort gehen im Klartext
über die Leitung. Für den dauerhaften Betrieb gehört ein Reverse Proxy
mit TLS davor – unter Windows der IIS. Ins offene Internet gehört er so
oder so nicht.

**Nur ein Prozess schreibt ins Archiv.** Der Abruf liegt deshalb im
Dienst und nicht in der Aufgabenplanung. Wer von Hand einliest, hält den
Dienst vorher an; das Fenster tut es von selbst.

**Zieht ein Archiv um, muss der erkannte Text aus Scans mit.** Er
entsteht nicht beim Indexbauen, sondern durch Texterkennung, und liegt
in einem eigenen Ordner neben dem Index. Fehlt er, sind die Mails alle
da – nur wer nach einer Rechnungsnummer sucht, die ausschließlich im
Scan steht, bekommt keinen Treffer.

---

## Weiter

- [Zugänge und Rechte](server-einrichten.md#3-zugänge-anlegen) – wer was
  sehen darf; die Einschränkung wirkt *in* der Suchabfrage, nicht
  dahinter.
- [Verschlüsselte Archive](verschluesselung.md) – und warum der
  Suchindex dabei die offene Flanke ist.
- [Postfächer einrichten](postfaecher-einrichten.md)
- [Sichern und zurückholen](sicherung.md)
- [Rechtliches](../RECHTLICHES.md) – MailBurg **unterstützt**
  revisionssicheren Betrieb, es stellt ihn nicht her.
