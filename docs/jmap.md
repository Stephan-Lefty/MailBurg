[Übersicht](../README.md) | [Anleitungen](README.md) | [Postfächer einrichten](postfaecher-einrichten.md) | [Erste Schritte](erste-schritte.md)

# JMAP – der Nachfolger von IMAP

> **Kurz vorweg:** Sie brauchen JMAP nicht. MailBurg holt Ihre Post seit jeher
> über IMAP, und das bleibt so. Wenn Ihr Anbieter aber JMAP kann, ist es für
> ein Archiv der bessere Weg – schneller und mit weniger Vermutungen.
>
> Kann Ihr Anbieter es? Wahrscheinlich nicht. Fastmail ja, Stalwart und Cyrus
> ja. Gmail, Outlook, GMX, Web.de, Proton: nein.

## Was JMAP ist

**JMAP** steht für *JSON Meta Application Protocol* und ist ein Standard der
Internet Engineering Task Force – festgeschrieben in
[RFC 8620](https://www.rfc-editor.org/rfc/rfc8620) (der Grundlage) und
[RFC 8621](https://www.rfc-editor.org/rfc/rfc8621) (dem Teil für E-Mail).
Entstanden ist er bei Fastmail, einem australischen Mailanbieter, der ihn
seit 2019 im Betrieb einsetzt.

Gedacht ist er als **Ablösung für IMAP**, und dafür gibt es einen Grund.

### IMAP ist von 1986

IMAP wurde entworfen, als Mail auf einem Rechner lag, an dem man saß. Es ist
ein *Dialog*: Man meldet sich an, wählt einen Ordner, fragt nach Nachrichten,
holt sie einzeln, schließt den Ordner, wählt den nächsten. Jeder Schritt ist
eine eigene Zeile über die Leitung, und jede Antwort muss abgewartet werden,
bevor die nächste Frage kommt.

Bei zwanzig Ordnern sind das über hundert Umläufe, bevor die erste Mail
angekommen ist. Auf einer schnellen Leitung im selben Haus fällt das nicht
auf; über Mobilfunk, wo jeder Umlauf hundert Millisekunden kostet, sehr wohl.

Dazu kommt ein zweiter Punkt, der ein Archiv besonders trifft: **IMAP kann
nicht sagen, was sich geändert hat.** Es gibt keine Frage »was ist seit
gestern dazugekommen?«. MailBurg baut sie über Umwege nach – es merkt sich
die höchste bekannte Nummer je Ordner und fragt nach allem darüber. Das
funktioniert, ist aber eine Näherung: Nachrichten, die nachträglich
einsortiert wurden, rutschen durch, und nach einem Serverumzug beginnt die
Zählung von vorn.

### Was JMAP anders macht

**JSON über HTTPS.** Keine eigene Verbindung, kein eigenes Protokoll –
dieselbe Technik, mit der jede Webseite arbeitet. Das klingt nach einer
Kleinigkeit und ist keine: Verschlüsselung, Zwischenspeicher, Firewalls und
Proxys funktionieren damit ohne Sonderbehandlung.

**Stapelabfragen.** Mehrere Fragen gehen in einer einzigen Anfrage hinaus,
und spätere dürfen sich auf frühere beziehen: *»Such mir die Mails aus dem
Ordner, den du gerade gefunden hast«* – ohne dass der Ordner ein zweites Mal
über die Leitung geht. Aus hundert Umläufen werden zwei.

**Änderungsverfolgung.** Das ist der Punkt, um den es für ein Archiv geht.
JMAP kennt einen *Stand* – eine Zeichenkette, die den Zustand des Postfachs
beschreibt. Beim nächsten Abruf schickt MailBurg diesen Stand mit und fragt:
was ist seither passiert? Der Server antwortet mit einer Liste. Keine
Näherung, keine Zählerei, kein Nachfiltern.

**Marken statt Passwörter.** Bei den meisten JMAP-Anbietern melden Sie sich
nicht mit Ihrem Kontopasswort an, sondern mit einer eigens erzeugten
*Zugriffsmarke* (englisch »API token«). Die lässt sich einzeln widerrufen,
ohne dass Sie Ihr Passwort ändern müssen – und ein Archivprogramm, dem Sie
eine Marke geben, kommt damit an keine Kontoeinstellungen.

## Was das für MailBurg bedeutet

| | IMAP | JMAP |
|---|---|---|
| Erster Abruf | Ordner für Ordner | zwei Anfragen |
| Weitere Abrufe | »alles über Nummer N« | »was hat sich geändert« |
| Nachträglich einsortierte Mails | rutschen durch | kommen mit |
| Nach einem Serverumzug | Zählung beginnt von vorn | Stand bleibt gültig |
| Anmeldung | Passwort oder App-Passwort | meist eine Zugriffsmarke |

**Die Nachricht selbst ist in beiden Fällen dieselbe.** MailBurg holt sie bei
JMAP über eine eigene Download-Adresse, byteweise so, wie sie ankam – mit
allen Kopfzeilen, mit prüfbarer DKIM-Signatur. Die zerlegte Fassung, die JMAP
daneben anbietet, wäre bequemer und für ein Archiv wertlos.

## Einrichten

### Im Fenster

*Post → Postfächer …* und dann **Weiteres Postfach von Hand eintragen**.
Ganz oben steht **Abrufweg** – stellen Sie ihn auf *JMAP*. Die Felder
darunter ändern sich mit: Port und Verschlüsselung verschwinden (JMAP ist
immer HTTPS), und statt eines Servernamens tragen Sie eine vollständige
Adresse ein.

### Auf der Kommandozeile

```bash
mailburg konten hinzufuegen Fastmail \
    --jmap --server https://api.fastmail.com/jmap/session
```

Nach der Marke wird gefragt; sie landet im Schlüsselbund wie jedes andere
Passwort. Den Benutzernamen lassen Sie leer, wenn Sie eine Marke benutzen.

### Woher die Adresse kommt

Zwei Wege, und beide gehen:

**Die Adresse steht beim Anbieter.** Bei Fastmail ist es
`https://api.fastmail.com/jmap/session`.

**Oder MailBurg findet sie selbst.** Tragen Sie nur den Domainnamen ein, sucht
MailBurg unter `https://IHRE-DOMAIN/.well-known/jmap` – so sieht es RFC 8620
vor. Bei einem selbst betriebenen Server ist das meistens der einfachere Weg.

### Woher die Marke kommt

Bei **Fastmail**: *Settings → Privacy & Security → Integrations → API tokens*,
dann eine neue Marke mit Leserechten für Mail.

Bei einem selbst betriebenen **Stalwart** oder **Cyrus** genügen oft
Benutzername und Passwort – dann füllen Sie beide Felder aus.

## Was Sie wissen sollten

> **Einmal gegen einen echten Server gelaufen.** Am 03.09.2026 hat ein
> Anwender rund 5.000 Nachrichten über JMAP aus einem selbst betriebenen
> **Stalwart** geholt – 200 Mails in weniger als fünf Sekunden. Das ist der
> erste Lauf außerhalb der eigenen Werkstatt; bis dahin war alles nur gegen
> einen nachgebauten Server geprüft, also gegen die Annahmen des Programms.
>
> **Fastmail** ist damit noch nicht erprobt. Dort meldet man sich mit einer
> Zugriffsmarke an statt mit Benutzername und Passwort, und die Ordner heißen
> anders. Wer es dort ausprobiert: Bitte melden.
>
> Wenn Sie JMAP an einem echten Konto ausprobieren: Lassen Sie nach dem ersten
> Abruf `mailburg pruefen ARCHIV` laufen und vergleichen Sie die Zahl der
> Mails mit dem, was Ihr Anbieter im Webmailer anzeigt. Und räumen Sie Ihr
> Postfach nicht auf, bevor Sie das getan haben.

**Papierkorb, Spam und Entwürfe bleiben draußen** – wie bei IMAP, nur
verlässlicher: JMAP kennzeichnet Ordner mit einer *Rolle*. Ein Ordner heißt je
nach Sprache »Papierkorb«, »Trash« oder »Corbeille«; seine Rolle heißt überall
`trash`.

**Der Gmail-Fall ist ebenfalls abgedeckt.** Ein Ordner mit der Rolle `all`
enthält sämtliche Mails ein zweites Mal; er wird übergangen. Auf der Platte
gäbe das keine doppelte Datei, wohl aber einen zweiten Fundort je Mail im
Protokoll.

**Eine Mail kann in mehreren Ordnern liegen.** Bei JMAP ist das vorgesehen,
bei Gmail der Normalfall – dort sind Ordner in Wahrheit Etiketten. MailBurg
schreibt sie dem ersten Ordner zu, den es nicht übergeht.

**Beides gleichzeitig geht.** Der Abrufweg steht am einzelnen Postfach, nicht
am Programm. Sie können ein Fastmail-Konto über JMAP holen und Ihre übrigen
weiter über IMAP – im selben Archiv, im selben Lauf.

## Wenn es nicht klappt

**»Der Server hat die Anmeldung abgelehnt (401).«** Der häufigste Grund: Sie
haben Ihr Kontopasswort eingetragen statt einer Zugriffsmarke. Die beiden sind
bei JMAP-Anbietern selten dasselbe.

**»Dieser Server spricht JMAP, aber nicht für Mail.«** JMAP ist ein
allgemeines Protokoll; Mail ist nur eine seiner Anwendungen. Manche Server
können Kalender oder Kontakte darüber, aber keine Post.

**»Unter … antwortet kein JMAP-Server – die Antwort ist kein JSON.«** Dann
zeigt die Adresse ins Leere oder auf eine gewöhnliche Webseite. Prüfen Sie,
ob sie auf `/jmap/session` oder `/.well-known/jmap` endet.
