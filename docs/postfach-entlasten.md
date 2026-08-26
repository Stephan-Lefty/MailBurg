[Übersicht](../README.md) | [Anleitungen](README.md) | [Postfächer](postfaecher-einrichten.md) | [Regelmäßig abrufen](zeitsteuerung.md) | [Windows](windows.md)

# Postfach entlasten

Das ist der Punkt, um den es letztlich geht. Ein Archiv ist kein Selbstzweck:
Es soll Ihr Postfach beim Anbieter wieder leer werden lassen, ohne dass etwas
verlorengeht.

Und genau hier ist Sorgfalt angebracht. Was Sie beim Anbieter löschen, ist
weg – endgültig und ohne Papierkorb, sobald auch der geleert ist. Deshalb die
Reihenfolge in dieser Anleitung: **erst nachweisen, dann löschen.** Nie
umgekehrt.

## Der Ablauf in drei Schritten

### 1. Abrufen, bis alles drin ist

```bash
mailburg abrufen ~/Archiv
```

Der erste Lauf holt den ganzen Bestand und dauert entsprechend. Läuft schon
eine [Zeitsteuerung](zeitsteuerung.md), passiert das ohnehin von selbst.

In der Oberfläche sagt MailBurg nach jedem selbst gestarteten Abruf, ob alle
Postfächer erreichbar waren. **Steht dort auch nur eines als nicht erreichbar,
fangen Sie hier nicht an aufzuräumen** – dessen Mails fehlen im Archiv.

### 2. Nachweisen

```bash
mailburg abgleich ~/Archiv --aelter-als 180
```

Der Befehl fragt jeden Server, welche Mails älter als der Stichtag sind, und
hält jede einzelne gegen das Archiv. Was dabei herauskommt, sieht so aus:

```
Stichtag: 01.01.2026
Geprüft wird, was der Server hat und im Archiv fehlt.

Kontakt (kontakt@example.org auf mail.example.org:143)
  ✓ INBOX                                       8  alle im Archiv
    INBOX/Projekte                              0  nichts so altes vorhanden
  ✓ Sent                                       14  alle im Archiv

  Alle 22 Mails vor dem 01.01.2026 sind im Archiv.
  Sie können sie im Mailprogramm gefahrlos aufräumen lassen.
```

Ein fester Stichtag statt einer Tageszahl geht auch:

```bash
mailburg abgleich ~/Archiv --stichtag 2026-01-01
mailburg abgleich ~/Archiv --konto Kontakt        # nur ein Postfach
```

**Im Zweifel gibt es kein grünes Licht.** Kann MailBurg einen Ordner nicht
lesen, hat der Server seine `UIDVALIDITY` geändert oder bricht die Verbindung
ab, lautet der Befund *unklar* – nicht *alles in Ordnung*. Ein Archivprogramm,
das im Zweifel Entwarnung gibt, ist gefährlicher als gar keines.

### 3. Aufräumen lassen

Erst jetzt, und im Mailprogramm oder beim Anbieter – nicht in MailBurg.
**MailBurg löscht nichts auf Ihren Servern.** Es öffnet Ordner nur lesend und
holt Nachrichten so, dass ungelesene Post ungelesen bleibt.

Das ist Absicht: Ein Programm, das Ihr Archiv füllt *und* Ihr Postfach leert,
kann sich bei einem Fehler in beiden Richtungen irren. Die Trennung sorgt
dafür, dass ein Fehler in MailBurg Ihre Post nicht vernichtet.

## Thunderbird: alte Nachrichten automatisch entfernen

Thunderbird kann das je Ordner erledigen.

1. Rechtsklick auf den Ordner → **Eigenschaften**
2. Reiter **Aufräumen** (in älteren Fassungen: *Speicherplatz*)
3. **Nachrichten löschen, die älter sind als …** anhaken und die Tage eintragen

Die Zahl sollte **großzügiger sein als Ihr Abrufabstand**. Wer alle 30 Minuten
abruft, ist mit 180 Tagen auf der sicheren Seite – der Abstand ist dann so
groß, dass selbst ein Rechner, der zwei Wochen aus war, nichts verpasst.

Zwei Dinge zum Posteingang:

- **Fangen Sie mit einem unwichtigen Ordner an**, nicht mit dem Posteingang.
  So sehen Sie einmal in Ruhe, was passiert.
- **Prüfen Sie, ob Ihr Papierkorb sich mit leert.** Manche Anbieter behalten
  gelöschte Nachrichten dort noch Wochen – das ist ein Sicherheitsnetz, aber
  auch der Grund, warum das Postfach trotz Aufräumens voll bleibt.

## Was ist mit Post, die noch keine 180 Tage alt ist?

Die bleibt, wo sie ist. Genau dafür ist der Stichtag da: Aktuelle Vorgänge
gehören ins Postfach, weil Sie dort damit arbeiten. Ins Archiv kommen sie
trotzdem – nur gelöscht werden sie beim Anbieter eben noch nicht.

## Und wenn ich eine gelöschte Mail doch wieder brauche?

Dann holen Sie sie zurück. In der Oberfläche: Doppelklick auf die Nachricht in
der Trefferliste, Postfach wählen, fertig – sie landet im Posteingang, mit
allen Anhängen und mit ihrem ursprünglichen Datum.

Das geht auch dann, wenn es das Postfach von damals gar nicht mehr gibt: Sie
wählen frei, in welches der eingerichteten Postfächer sie soll. Und wenn gar
keines mehr existiert, speichern Sie die Nachricht als `.eml`-Datei – die
öffnet jedes Mailprogramm.

## Bevor Sie zum ersten Mal aufräumen

Eine kurze Liste, die sich abhaken lässt:

- [ ] Der Abruf lief durch, **alle** Postfächer waren erreichbar
- [ ] `mailburg abgleich` sagt für den Stichtag: alle im Archiv
- [ ] Das Archiv liegt **nicht** auf derselben Platte wie das Betriebssystem
- [ ] Es gibt eine Sicherung des Archivs – oder es liegt auf einem Laufwerk,
      das gesichert wird
- [ ] `mailburg pruefen ~/Archiv` meldet keine Fehler

Der letzte Punkt ist der, den man am ehesten überspringt und am wenigsten
überspringen sollte: Er vergleicht das Protokoll mit dem, was tatsächlich auf
der Platte liegt. Wenn dort etwas fehlt, erfahren Sie es lieber jetzt als in
dem Moment, in dem Sie es suchen.
