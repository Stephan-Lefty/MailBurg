[Übersicht](../README.md) | [Anleitungen](README.md) | [Erste Schritte](erste-schritte.md) | [Sichern](sicherung.md) | [Server](server-einrichten.md)

# Das Archiv verschlüsseln

Ein Mailarchiv ist der Ort, an dem alles zusammenkommt: Rechnungen,
Kündigungen, Krankmeldungen, Verträge, private Post. Solange es auf der
eigenen Platte im eigenen Wohnzimmer liegt, ist das kein Problem. Sobald es
das Haus verlässt – als Sicherung in eine Cloud, auf einer externen Platte,
auf einem Server –, ist es eines.

Dagegen hilft die Verschlüsselung.

> **Nachträglich geht es nicht.** Ein bestehendes Archiv lässt sich nicht
> verschlüsseln. Wer umsteigen will, legt ein neues verschlüsseltes Archiv an
> und spielt eine Sicherung des alten hinein — siehe [unten](#umsteigen).

## Was geschützt ist und was nicht

**Verschlüsselt sind die Mails und das Journal.** Also alles, was im
Archivordner liegt und was in eine Sicherung wandert. Auch die *Dateinamen*:
Sie waren bisher der SHA-256 der Mail, und den kann jeder ausrechnen, der die
Mail selbst hat. Ohne diese Verdeckung wäre der Inhalt verschlüsselt und die
Frage *»liegt diese Nachricht in dem Archiv?«* trotzdem beantwortet.

**Nicht verschlüsselt ist der Suchindex.** Er liegt außerhalb des Archivs im
Benutzerverzeichnis, nur für Sie lesbar, und enthält Betreff, Absender und
Text im Klartext — anders könnte er nicht suchen.

Für den häufigen Fall genügt das: Eine Sicherung in der Cloud, eine verlorene
externe Platte oder ein weitergegebener Ordner enthalten den Index nicht.
Wer dagegen den ganzen Rechner absichern will, verschlüsselt die Platte;
dafür bringt jedes Betriebssystem etwas mit (LUKS unter Linux, BitLocker
unter Windows, FileVault unter macOS).

**Und die Verschlüsselung schützt nicht vor Ihnen selbst.** Wer das Passwort
hinterlegt, damit der Zeitplan nachts läuft, gibt einen Teil des Schutzes auf
— siehe [Zeitplan und Server](#zeitplan-und-server).

## Ein verschlüsseltes Archiv anlegen

Im Assistenten steht unter *Schutz* ein Häkchen **Das Archiv verschlüsseln**.
Es ist nicht vorangekreuzt: Wer beim Einrichten schnell weiterklickt, soll
nicht Jahre später vor einem Passwort stehen, das er nie bewusst vergeben hat.

Auf der Kommandozeile:

```bash
mailburg anlegen ~/Archiv --verschluesseln
```

Beides fragt das Passwort zweimal ab. Hier gibt es keine Korrektur hinterher:
Ein Tippfehler verschlüsselt zwanzig Jahre Post mit einer Zeichenkette, die
niemand kennt, und auffallen würde er erst beim nächsten Öffnen.

## Der Notschlüssel

Gleich nach dem Anlegen erscheint er, genau einmal:

```
VXTM-9K4P-2HRD-B7YE-QFSN-3JLA-K8MC-TW5G
```

**Drucken Sie ihn aus.** Er öffnet das Archiv anstelle des Passworts, überall
dort, wo nach dem Passwort gefragt wird.

Das ist kein Beiwerk, sondern der wichtigste Teil. Ein Langzeitarchiv
überlebt das Gedächtnis seines Besitzers: Wer nach sieben Jahren eine alte
Rechnung braucht, hat das Passwort von damals womöglich nicht mehr. Und es
überlebt womöglich seinen Besitzer — Erben, die vor einem verschlüsselten
Archiv stehen, haben ohne ihn nichts in der Hand.

Er besteht aus 32 Zeichen ohne `I`, `O`, `0` und `1` — die sind auf Papier
nicht sicher zu unterscheiden. Beim Eintippen sind Bindestriche, Leerzeichen
und Groß- oder Kleinschreibung egal.

**Legen Sie ihn nicht neben das Archiv.** Nicht auf dieselbe Platte, nicht in
denselben Cloud-Ordner. Ein Schlüssel, der neben dem Schloss liegt, ist
keiner. Zu den wichtigen Papieren gehört er, nicht zu den Daten.

MailBurg speichert ihn nirgends und kann ihn nicht noch einmal ausgeben.
Läge er im Archiv, wäre er kein Schutz.

## Das Passwort wechseln

```bash
mailburg passwort aendern ~/Archiv
```

Der Wechsel dauert einen Augenblick, auch bei 700.000 Mails. **Die Mails
werden dabei nicht angefasst.**

Das liegt am Aufbau: Verschlüsselt ist alles mit einem zufälligen
Archivschlüssel, der sich nie ändert. Der wiederum liegt eingewickelt in
`archive.json` — einmal mit Ihrem Passwort, einmal mit dem Notschlüssel. Beim
Wechsel wird nur diese eine Hülle neu geschrieben, ein paar hundert Byte.

Hinge die Verschlüsselung direkt am Passwort, müsste ein Wechsel jede einzelne
Datei neu verschlüsseln — Stunden, und mitten darin ein Archiv, das halb dem
alten und halb dem neuen Passwort gehört.

**Der Notschlüssel gilt weiter.** Er hängt an einer eigenen Hülle und weiß
vom Passwort nichts.

## Zeitplan und Server

Ein Archiv, das nach einem Passwort fragt, kann nicht von selbst abrufen.
Nachts um drei sitzt niemand davor, und ein Abruf, der auf eine Eingabe
wartet, bleibt schweigend stehen — bis Wochen später auffällt, dass nichts
mehr archiviert wurde.

Damit das nicht passiert, wird das Passwort hinterlegt:

```bash
mailburg passwort hinterlegen ~/Archiv
```

Es wandert dann verschlüsselt in den [Tresor](server-einrichten.md). Von da
an fragt MailBurg nicht mehr — auch nicht im Fenster.

**Das kostet einen Teil des Schutzes, und das gehört gesagt.** Wer als Ihr
Benutzer Programme ausführen kann, kommt damit an das Archiv: Der
Hauptschlüssel des Tresors liegt ja bereit, sonst könnte der Dienst ihn nicht
benutzen. Ein Passwort, mit dem sich ein Programm ohne Zutun anmelden soll,
lässt sich vor diesem Programm nicht verstecken.

Was weiterhin geschützt bleibt: die Sicherung in der Cloud, die verlorene
Platte, der weitergegebene Ordner. Das ist der Anlass, um den es geht.

Rückgängig machen:

```bash
mailburg passwort vergessen ~/Archiv
```

Auf einem Server ohne Schlüsselbund geht es stattdessen über die Umgebung —
für systemd der bessere Weg, weil eine Umgebungsvariable in Prozesslisten und
Fehlerberichten auftaucht und eine Datei nicht:

```ini
[Service]
LoadCredential=archivpasswort:/etc/mailburg/archivpasswort
Environment=MAILBURG_ARCHIVPASSWORTDATEI=%d/archivpasswort
```

Fehlt das Passwort, sagt es die Statusseite des Dienstes unter `/zustand` —
mitsamt dem Befehl, der es behebt.

## Sicherungen

Eine Sicherung eines verschlüsselten Archivs ist selbst verschlüsselt. Gepackt
wird der Ordner, wie er liegt; entschlüsselt wird dabei nichts.

Das heißt auch: **Ohne Passwort oder Notschlüssel ist eine Sicherung wertlos.**
Prüfen Sie das, bevor Sie sich darauf verlassen — eine Sicherung, die man
nicht aufbekommt, ist keine.

## Umsteigen

Ein bestehendes Archiv lässt sich nicht nachträglich verschlüsseln. Der Weg
führt über eine Sicherung — in drei Schritten:

**1. Das alte Archiv sichern.**

```bash
mailburg sichern ~/Archiv ~/sicherung.tar.zst
```

**2. Ein neues, verschlüsseltes anlegen.**

```bash
mailburg anlegen ~/Archiv-neu --verschluesseln --modus geschaeftlich
```

Achten Sie darauf, Betriebsart und Rechtsraum wie im alten zu wählen; sie
stehen in `mailburg info ~/Archiv`.

**3. Die Sicherung hineinspielen.** Das geht im Fenster: Archiv wechseln zum
neuen, dann **Archiv → Sicherung importieren …** und die Datei auswählen. Die
Mails wandern mit ihrem ursprünglichen Postfach und Ordner hinein.

**Das alte Archiv nicht sofort löschen.** Prüfen Sie erst, ob im neuen alles
angekommen ist (`mailburg pruefen ~/Archiv-neu`), vergleichen Sie die Zahlen
aus `mailburg info` bei beiden, suchen Sie nach ein paar Nachrichten, die Sie
kennen, und legen Sie eine Sicherung des neuen an.

Ein Punkt zum Bedenken: Die Hash-Kette beginnt im neuen Archiv von vorn. Für
ein Geschäftsarchiv heißt das, dass die lückenlose Nachweiskette an dieser
Stelle einen Schnitt hat. Das alte Archiv sollte deshalb aufbewahrt werden,
solange die Aufbewahrungsfristen laufen.

## Wenn es schiefgeht

**»Das Passwort öffnet dieses Archiv nicht.«** Probieren Sie den
Notschlüssel; er wird an derselben Stelle eingegeben. Achten Sie auf die
Tastaturbelegung — ein `y`/`z`-Tausch fällt bei verdeckter Eingabe nicht auf.
Im Fenster gibt es dafür das Häkchen *Eingabe anzeigen*.

**»Für ein verschlüsseltes Archiv fehlt das Paket cryptography.«** Dann ist
MailBurg ohne das Zusatzpaket eingerichtet. Nachrüsten:

```bash
pip install 'mailburg[verschluesselung]'
```

Ihre Mails sind davon nicht betroffen — sie liegen unversehrt im Archiv und
warten auf das Paket.

**Passwort und Notschlüssel beide weg.** Dann ist das Archiv verloren. Es gibt
keine Hintertür, keinen Wiederherstellungsdienst und niemanden beim
Hersteller, der helfen könnte. Das ist keine Härte, sondern die Bedingung
dafür, dass die Verschlüsselung überhaupt etwas wert ist: Was Sie
wiederbekommen könnten, könnte auch ein anderer wiederbekommen.

## Was im Einzelnen passiert

Für alle, die es genau wissen wollen:

| | |
|---|---|
| Verfahren | AES-256-GCM, jede Datei und jede Journalzeile einzeln |
| Schlüsselableitung | scrypt, N=2¹⁷, r=8, p=1 |
| Dateinamen | HMAC-SHA256 über den Klartext-Hash |
| Archivschlüssel | 32 Byte Zufall, in `archive.json` eingewickelt |
| Notschlüssel | 160 Bit Zufall, 32 Zeichen aus einem Alphabet ohne `IO01` |

**scrypt und nicht Argon2id**, obwohl Argon2id der modernere Vorschlag wäre:
scrypt steckt in Pythons Standardbibliothek. Ein Archivprogramm, das seine
Daten in zwanzig Jahren noch aufbekommen soll, sollte für die
Schlüsselableitung nichts brauchen, was man erst installieren muss. Beide sind
speicherhart, beide taugen für diesen Zweck.

**Was ein Angreifer trotzdem sieht**, der den Archivordner hat: wie viele
Mails darin liegen, ungefähr wie groß jede ist, und aus welchem Monat sie
stammt — die Ordnerstruktur `mail/2025/03/…` bleibt sichtbar, weil sich der
Ablageort sonst nicht mehr berechnen ließe. Inhalte, Betreffzeilen, Adressen
und Postfachnamen sieht er nicht.
