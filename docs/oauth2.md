[Übersicht](../README.md) | [Anleitungen](README.md) | [Erste Schritte](erste-schritte.md) | [Postfächer](postfaecher-einrichten.md) | [Windows](windows.md) | [Zeitsteuerung](zeitsteuerung.md) | [Sichern](sicherung.md)

# Anmeldung per OAuth2

**Für Microsoft-Konten führt kein Weg daran vorbei.** Outlook.com,
Hotmail, Live und Exchange Online nehmen kein Passwort mehr an – auch
kein App-Kennwort. Microsoft hat das abgeschaltet: für Geschäftskonten am
1. Oktober 2022, für private Konten am 16. September 2024.

**Bei Gmail brauchen Sie es vorerst nicht.** Dort funktionieren
App-Passwörter weiterhin, und sie sind deutlich einfacher einzurichten.
Warum OAuth2 bei Google trotzdem umständlich ist, steht [weiter
unten](#warum-google-schwieriger-ist).

## Warum Sie sich eine eigene Anwendung registrieren müssen

Andere Programme bringen ihre Zugangsdaten mit. MailBurg tut das nicht,
und dafür gibt es einen Grund, der nichts mit Bequemlichkeit zu tun hat.

Google verlangt für den vollen Zugriff auf ein Postfach ein
Sicherheitsaudit durch ein zugelassenes Prüflabor. Es kostet je nach
Stufe einige hundert bis mehrere tausend Dollar und muss **jährlich
wiederholt** werden. Für ein quelloffenes Programm, mit dem niemand Geld
verdient, ist das nicht tragbar.

Die Alternative wäre, die Zugangsdaten eines anderen Programms
mitzubenutzen. Das tun manche. Es verstößt gegen die Bedingungen der
Anbieter, und es hieße, dass Ihr Postfachzugriff auf einer fremden
Registrierung steht, die jederzeit gesperrt werden kann.

Deshalb: **Sie registrieren eine Anwendung auf Ihren Namen.** Bei
Microsoft dauert das fünf Minuten, kostet nichts und braucht kein
Prüfverfahren.

## Microsoft: Schritt für Schritt

> **Zu den Menüpfaden:** Microsoft benennt seine Oberflächen häufig um.
> Was hier steht, war zuletzt so – finden Sie es nicht, suchen Sie im
> Portal nach »App-Registrierungen«.

1. **Portal öffnen:** <https://entra.microsoft.com> — anmelden mit dem
   Microsoft-Konto, dessen Postfach archiviert werden soll.

2. **Anwendung registrieren.** Unter *Identität → Anwendungen →
   App-Registrierungen* auf **Neue Registrierung**.

3. **Name:** frei wählbar, etwa `MailBurg`. Er erscheint später auf der
   Zustimmungsseite — Sie sehen ihn also wieder.

4. **Kontotypen:** *Konten in einem beliebigen Organisationsverzeichnis
   und persönliche Microsoft-Konten*. Wer nur ein Geschäftskonto
   anbindet, kann es enger fassen.

5. **Umleitungs-URI:** Plattform **Öffentlicher Client / nativ**, Wert:

   ```
   http://localhost
   ```

   Genau so, ohne Anschlussnummer. MailBurg sucht sich beim Anmelden
   einen freien Anschluss; Microsoft erlaubt das bei `localhost`
   ausdrücklich.

6. **Registrieren** klicken. Auf der Übersichtsseite steht dann die
   **Anwendungs-ID (Client)** — eine Zeichenfolge mit Bindestrichen. Die
   brauchen Sie.

7. **Berechtigung hinzufügen.** Unter *API-Berechtigungen → Berechtigung
   hinzufügen → APIs, die meine Organisation verwendet* nach `Office 365
   Exchange Online` suchen, dann *Delegierte Berechtigungen* →
   `IMAP.AccessAsUser.All`.

8. **Öffentlichen Client erlauben.** Unter *Authentifizierung* ganz
   unten: *Öffentliche Clientflows zulassen* auf **Ja**. Ohne das
   scheitert die Anmeldung mit einer Meldung über einen fehlenden
   geheimen Clientschlüssel — den ein Desktop-Programm gar nicht haben
   kann.

Kein geheimer Clientschlüssel. Sie brauchen keinen, und Sie sollten
keinen anlegen: Ein Programm auf Ihrem Rechner kann kein Geheimnis
bewahren. Deshalb PKCE — dazu unten mehr.

## Dann in MailBurg

Postfach einrichten wie sonst auch, aber ohne Passwort:

```bash
mailburg konten hinzufuegen Arbeit \
    --server outlook.office365.com --benutzer post@example.com
```

Und anmelden:

```bash
mailburg konten anmelden Arbeit \
    --anbieter microsoft \
    --kennung 11111111-2222-3333-4444-555555555555
```

Der Browser öffnet sich, Sie melden sich bei Microsoft an und erlauben
den Zugriff. Danach steht im Browserfenster »Angemeldet«, und MailBurg
kann das Postfach abrufen.

**Die Kennung merkt sich MailBurg.** Beim nächsten Mal genügt:

```bash
mailburg konten anmelden Arbeit
```

## Was danach geschieht

Der Zugriff läuft nach einer Stunde ab. MailBurg erneuert ihn bei jedem
Verbindungsaufbau selbsttätig, fünf Minuten vor Ablauf — Sie merken
davon nichts, auch beim Abruf im Hintergrund nicht.

**Neu anmelden müssen Sie nur, wenn:**

- Sie das Kontopasswort ändern,
- Sie den Zugriff beim Anbieter entziehen,
- oder das Konto länger als 90 Tage gar nicht abgerufen wurde.

MailBurg sagt es Ihnen dann mit der Meldung »Die gespeicherte Anmeldung
gilt nicht mehr«.

## Wo die Anmeldung liegt

Im **Schlüsselbund Ihres Systems**, nie in einer Datei. Das ist
wichtiger als beim Passwort: Ein Erneuerungs-Token ist auf Monate hinaus
ein Vollzugang zum Postfach, und es hat die Zwei-Faktor-Anmeldung
bereits hinter sich.

Zurücknehmen:

```bash
mailburg konten abmelden Arbeit
```

Das entfernt die Token von Ihrem Rechner. **Beim Anbieter besteht die
Erlaubnis weiter** — widerrufen lässt sie sich nur dort, bei Microsoft
unter *Mein Konto → Apps und Dienste*.

## Warum Google schwieriger ist

Technisch ist es derselbe Ablauf. Die Hürde liegt davor:

- Für den vollen IMAP-Zugriff braucht es den Scope
  `https://mail.google.com/`. Google zählt ihn zu den **restricted
  scopes** — mit dem oben beschriebenen jährlichen Audit.
- Ohne Audit lässt sich die Anwendung im **Testmodus** betreiben, mit bis
  zu 100 selbst eingetragenen Testnutzern. Dort verfallen die
  Erneuerungs-Token allerdings **nach sieben Tagen**. Für einen Abruf im
  Hintergrund heißt das: wöchentlich neu anmelden.

**Deshalb die Empfehlung:** Bei Gmail bleiben Sie vorerst beim
App-Passwort. Es ist in zwei Minuten erstellt, funktioniert unbegrenzt
und lässt sich einzeln widerrufen. Siehe [Postfächer
einrichten](postfaecher-einrichten.md).

Wer es dennoch will: In der [Google Cloud
Console](https://console.cloud.google.com/) ein Projekt anlegen, die
Gmail-API aktivieren, unter *APIs & Dienste → Anmeldedaten*
OAuth-Client-ID vom Typ **Desktop-App** erzeugen und sich selbst als
Testnutzer eintragen. Dann:

```bash
mailburg konten anmelden Privat --anbieter google --kennung IHRE-KENNUNG
```

## Was MailBurg beim Anmelden tut

Für den Fall, dass Sie es genau wissen wollen — oder jemandem erklären
müssen, warum das unbedenklich ist.

**PKCE statt Geheimnis.** Ein Programm auf Ihrem Rechner kann nichts
geheim halten: Wer die Datei hat, hat auch das Geheimnis. Deshalb
erzeugt MailBurg für **jede einzelne Anmeldung** einen neuen
Zufallswert, schickt vorab nur dessen Fingerabdruck an den Anbieter und
weist sich beim Einlösen mit dem Wert selbst aus. Fängt jemand die
Rückleitung ab, nützt ihm der Code nichts.

**Nur der eigene Rechner.** Für die Rückkehr aus dem Browser lauscht
MailBurg auf `127.0.0.1` — nicht auf allen Netzwerkadressen. Es nimmt
genau eine Anfrage entgegen und hört danach wieder auf.

**Prüfung der Antwort.** Jede Anmeldung bekommt einen Zufallswert
mitgegeben, der in der Antwort wieder auftauchen muss. Eine
untergeschobene Antwort wird abgewiesen.

**Kein Umweg über Dritte.** MailBurg spricht ausschließlich mit den
Servern des Anbieters. Es gibt keinen Vermittlungsdienst, keine
Anmeldung bei uns und keine Stelle, an der Ihre Token vorbeikämen.

## Wenn es klemmt

| Meldung | Was dahintersteckt |
|---|---|
| *Die Anwendungskennung wird nicht anerkannt* | Kennung vertippt, oder die Anwendung ist nicht als öffentlicher Client angelegt (Schritt 8). |
| *Das Umleitungsziel stimmt nicht* | Bei der Registrierung fehlt `http://localhost` — oder es steht dort mit Anschlussnummer. |
| *Die gespeicherte Anmeldung gilt nicht mehr* | Passwort geändert, Zugriff entzogen, oder bei Google die sieben Tage des Testmodus. Neu anmelden. |
| *Innerhalb von 5 Minuten kam keine Antwort* | Das Browserfenster wurde geschlossen oder die Anmeldung abgebrochen. |
| *Der angeforderte Zugriff wurde nicht bewilligt* | Bei Microsoft fehlt die Berechtigung `IMAP.AccessAsUser.All` (Schritt 7). |

## Ehrlich dazu

**Dieser Teil ist ungeprüft.** Der Ablauf ist gegen einen nachgebauten
Anbieter durchgespielt worden, und die Rechenvorschriften stimmen mit den
Normen überein — PKCE nach RFC 7636, das XOAUTH2-Format nach der
Beschreibung beider Anbieter. Aber niemand hat MailBurg bisher an einem
echten Microsoft- oder Google-Konto angemeldet.

Wenn Sie der erste sind: Eine Rückmeldung wäre viel wert. Wo es hakt,
steht in [Hilfe → Info](oberflaeche.md).
