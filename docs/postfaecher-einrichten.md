[Übersicht](../README.md) | [Anleitungen](README.md) | [Erste Schritte](erste-schritte.md) | [JMAP](jmap.md) | [Zeitsteuerung](zeitsteuerung.md) | [Windows](windows.md) | [Postfach entlasten](postfach-entlasten.md) | [Sichern](sicherung.md)

# Postfächer einrichten

MailBurg holt die Post über IMAP. Dafür braucht es drei Angaben – Server,
Benutzername und Passwort – und einen Kurznamen, unter dem die Mails im Archiv
erscheinen.

> Es gibt einen zweiten Weg: **[JMAP](jmap.md)**, den Nachfolger von IMAP.
> Er ist für ein Archiv der bessere, aber nur wenige Anbieter können ihn –
> Fastmail, Stalwart, Cyrus. Wenn Ihrer nicht dabei ist, lesen Sie hier
> einfach weiter.

```bash
mailburg konten hinzufuegen Firma \
    --server imap.example.org \
    --benutzer post@example.org
```

Das Passwort wird abgefragt, nicht als Argument übergeben. Das ist Absicht:
Argumente stehen in der Prozessliste und in der Verlaufsdatei der Shell.

Gleich nach der Eingabe meldet sich MailBurg am Server an und zeigt, welche
Ordner archiviert würden. Klappt die Anmeldung nicht, wird das Konto gar nicht
erst gespeichert – sonst scheiterte jeder nächtliche Abruf an einem Tippfehler,
den niemand mehr sucht.

## Aus Thunderbird oder Evolution übernehmen

Wer seine Postfächer schon in einem Mailprogramm eingerichtet hat, muss sie
nicht ein zweites Mal eintippen:

```bash
mailburg konten uebernehmen --zeigen    # erst nachsehen
mailburg konten uebernehmen             # dann übernehmen
```

Gesucht wird nach **Thunderbird-Profilen** (auch als Flatpak und Snap) und
nach **Evolutions Kontoverzeichnis** unter `~/.config/evolution/sources`. Ein
bestimmter Ort lässt sich auch angeben:

```bash
mailburg konten uebernehmen ~/.config/evolution/sources
```

Übernommen werden Server, Port, Benutzername und Verschlüsselungsart.
**Passwörter ausdrücklich nicht** – sie liegen dort verschlüsselt, und ein
Programm, das die Passwörter anderer Programme abgreift, verhält sich wie
Schadsoftware. Einem Archiv vertrauen Sie jahrzehntealte Post an; dieses
Vertrauen ist mehr wert als die gesparte Tipparbeit.

Konten, die kein IMAP sprechen, werden genannt statt verschwiegen: Bei POP3
liegt die Post schon auf Ihrer Platte und kommt über
*Post → Lokale Mailordner einlesen …* herein; bei Exchange lässt sich fast
immer zusätzlich IMAP freischalten.

## Wo das Passwort landet

Im Schlüsselbund des Betriebssystems:

| System  | Ablage |
|---------|--------|
| Linux   | GNOME Keyring oder KWallet |
| Windows | Anmeldeinformationsverwaltung |
| macOS   | Schlüsselbund |

**Nie in einer Datei.** In `konten.json` steht nur, *wo* ein Postfach liegt und
*wie* es heißt. Wer die Datei kopiert – oder versehentlich in eine Sicherung
packt –, hat damit noch keinen Zugang.

Ist kein Schlüsselbund erreichbar, läuft alles weiter; das Passwort wird dann
bei jedem Abruf neu erfragt. Für die Zeitsteuerung taugt das nicht, deshalb
lohnt es sich, einen einzurichten:

```bash
# Debian, Ubuntu
sudo apt install gnome-keyring python3-keyring

# Arch, Manjaro
sudo pacman -S gnome-keyring python-keyring
```

## Wenn die Post weitergeleitet und danach gelöscht wird

**Dann kommt neue Post dort nicht mehr an.** Wer bei seinem Anbieter eine
Weiterleitung eingerichtet hat, die eingehende Nachrichten an eine andere
Adresse schickt und anschließend hier löscht, hat ein Postfach, durch das die
neue Post nur hindurchfällt. MailBurg holt, was da ist – und da ist nichts
mehr.

**Der Altbestand bleibt erhalten.** Eine Weiterleitung wirkt nur auf das, was
nach ihrer Einrichtung eintrifft; was vorher da war, liegt weiter im Ordner.
Ein solches Postfach sieht deshalb gut gefüllt aus und ist trotzdem seit
Monaten stehen geblieben. Ebenso bleiben die **gesendeten** Nachrichten, denn
die Weiterleitung betrifft nur den Posteingang.

Das ist das Tückische daran: Das Archiv füllt sich beim ersten Abruf,
`mailburg pruefen` meldet »alles in Ordnung«, und die Zahlen sehen plausibel
aus. Nur kommt nichts Neues mehr dazu.

**MailBurg kann das nicht bemerken.** Ein leerer Posteingang sieht genauso
aus wie ein aufgeräumter.

Archivieren Sie deshalb **das Postfach, in dem die Post am Ende liegt** – also
das Ziel der Weiterleitung, nicht die Quelle. Den Altbestand und die
gesendeten Nachrichten der Quelladresse holen Sie zusätzlich, wenn Sie sie
brauchen.

Aufgefallen am 22.09.2026: Zwei Testmails an drei eigene Gmail-Konten kamen
im Archiv nur zweimal statt dreimal an. Der Abruf war korrekt – zwei der
Konten leiteten weiter und löschten danach. Der Abgleich zeigte am selben Tag
die andere Hälfte des Bildes: In denselben Postfächern lagen 754 und 185
ältere Nachrichten, alle vollständig archiviert.

## App-Passwörter

Die großen Anbieter lassen das Kennwort der Weboberfläche für den Zugriff von
außen nicht mehr zu. Sie verlangen ein eigens erzeugtes Passwort, das nur für
diesen einen Zweck gilt und sich einzeln widerrufen lässt.

| Anbieter | Server | Wo das App-Passwort herkommt |
|----------|--------|------------------------------|
| Gmail | `imap.gmail.com` | Eigener Abschnitt weiter unten – der Weg ist nicht mehr im Menü zu finden |
| GMX | `imap.gmx.net` | Einstellungen → POP3/IMAP-Abruf zuerst freischalten |
| Web.de | `imap.web.de` | Einstellungen → POP3/IMAP-Abruf zuerst freischalten |
| Posteo | `posteo.de` | Das gewöhnliche Passwort genügt |
| mailbox.org | `imap.mailbox.org` | Das gewöhnliche Passwort genügt |
| IONOS | `imap.ionos.de` | Das gewöhnliche Passwort genügt |

## Gmail Schritt für Schritt

Am 22.09.2026 an einem echten Konto durchlaufen. Bis dahin stand hier ein
Klickpfad, den es nicht mehr gibt.

**Voraussetzung: die Zwei-Faktor-Anmeldung muss an sein.** Ohne sie bietet
Google App-Passwörter gar nicht erst an. Nachsehen können Sie es im
Google-Konto unter *Sicherheit und Anmeldung*: Dort steht ein Punkt
**2-Faktor-Authentifizierung**, und wenn sie läuft, steht daneben
»Aktiviert seit …«. Ist sie aus, schalten Sie sie zuerst dort ein – Google
führt Sie dabei durch die Einrichtung.

> Die Anmeldung mit einem **Passkey** ist etwas anderes als ein
> App-Passwort und ersetzt es nicht. Ein Passkey meldet *Sie* an der
> Weboberfläche an; ein App-Passwort meldet *ein Programm* am Postfach an.
> MailBurg braucht das zweite.

**Den Weg dorthin finden Sie nicht im Menü.** Google hat die App-Passwörter
aus den Sicherheitseinstellungen entfernt; auf der Seite zur
2-Faktor-Authentifizierung stehen sie ebenfalls nicht mehr. Erreichbar sind
sie nur noch über die Adresse selbst:

```
https://myaccount.google.com/apppasswords
```

Google fragt dort noch einmal, ob Sie es wirklich sind – mit Passkey oder
Passwort. Das ist normal, die Seite gilt als heikel.

**Dann:** einen Namen eintragen, etwa `MailBurg`, und auf *Erstellen*
klicken. Google zeigt daraufhin 16 Buchstaben, der Lesbarkeit halber in vier
Vierergruppen.

- Das Passwort erscheint **genau einmal**. Danach listet die Seite nur noch
  den Namen. Kopieren Sie es sofort oder tragen Sie es gleich in MailBurg
  ein.
- Die **Leerzeichen gehören nicht dazu**. In das Passwortfeld kommen die 16
  Zeichen am Stück.

**In MailBurg** tragen Sie das Postfach dann so ein:

| Feld | Wert |
|------|------|
| Server | `imap.gmail.com` |
| Anschluss | 993, mit SSL |
| Benutzer | Ihre vollständige Mailadresse |
| Passwort | die 16 Zeichen ohne Leerzeichen |

Der Server heißt auch dann `imap.gmail.com`, wenn Ihre Adresse auf
**@googlemail.com** endet – das ist nur der alte deutsche Name für dasselbe
Postfach.

**Wenn Sie das Passwort verlegt haben**, kommen Sie nicht mehr daran. Löschen
Sie den Eintrag auf derselben Seite über das Mülleimer-Symbol und legen Sie
einen neuen an. Das ist kein Schaden – ein App-Passwort gilt nur für dieses
eine Programm.

Zurückziehen können Sie es ebenso: Ein gelöschtes App-Passwort sperrt
MailBurg aus, Ihr Google-Konto bleibt unberührt.

**Ordner »Alle Nachrichten«:** Gmail legt jede Mail zusätzlich dort ab. Beim
Archivieren würde dadurch jede Nachricht ein zweites Mal gezählt. MailBurg
übergeht diesen Ordner von sich aus; einstellen müssen Sie dafür nichts.

Wer statt des App-Passworts die Anmeldung per OAuth2 möchte: siehe
[Anmeldung per OAuth2](oauth2.md). Sie erspart das App-Passwort, verlangt
dafür eine einmalige Einrichtung in der Google Cloud Console – und im
Testmodus verfallen die Marken nach sieben Tagen.

## Microsoft-Konten gehen nur über OAuth2

**Outlook.com, Hotmail, Live und Exchange Online nehmen kein Passwort mehr
an** – auch kein App-Kennwort. Microsoft hat die einfache Anmeldung
abgeschaltet: für Geschäftskonten (Exchange Online) am 1. Oktober 2022, für
private Konten am 16. September 2024. Wer es dennoch versucht, bekommt eine
Anmeldefehlermeldung, die den wahren Grund nicht nennt.

**MailBurg beherrscht OAuth2** – seit Fassung 1.0, die Anleitung dazu ist
[Anmeldung per OAuth2](oauth2.md). Sie müssen sich dafür eine eigene
Anwendung bei Microsoft registrieren; das ist kostenlos, dauert zehn
Minuten und ist dort Schritt für Schritt beschrieben.

> **Ungeprüft an einem echten Konto.** Der Ablauf ist gegen einen
> nachgebauten Anbieter getestet, nicht gegen Microsoft selbst – hier hat
> sich damit noch niemand angemeldet. Wenn Sie es ausprobieren, ist eine
> Rückmeldung viel wert.

**Der sichere Umweg, solange das so ist:** Das Konto zusätzlich in
Thunderbird einrichten und MailBurg das Thunderbird-Profil einlesen lassen.
Thunderbird beherrscht OAuth2 seit Jahren. Die Mails landen dabei genauso
bytegenau im Archiv wie über IMAP.

**Warum Sie sich selbst eine Anwendung registrieren müssen** und MailBurg
nicht einfach eine eigene mitbringt: Google verlangt für den vollen
IMAP-Zugriff ein jährlich zu wiederholendes Sicherheitsaudit durch ein
zugelassenes Labor, das für ein quelloffenes Programm ohne Einnahmen nicht
tragbar ist. Bei Microsoft ist die Registrierung kostenlos und ohne
Prüfverfahren – deshalb geht dieser Weg dort ohne Weiteres, bei Gmail
bleibt vorerst das App-Passwort die bessere Wahl.

## Proton geht nur über die Bridge

**Proton Mail gibt seine Mails nicht per IMAP heraus** – sie liegen dort
Ende-zu-Ende-verschlüsselt, und es gibt keinen Server, den MailBurg direkt
fragen könnte. Den Zugang schafft die **Proton Mail Bridge**: ein Programm,
das auf Ihrem Rechner läuft, sich bei Proton anmeldet, entschlüsselt und die
Mails örtlich als IMAP-Server anbietet. Ohne sie kommt kein Programm an diese
Post, auch MailBurg nicht.

Eingetragen wird dann nicht Proton, sondern die Bridge. Dafür genügt
`--proton` – Server, Port und Verschlüsselung setzt MailBurg selbst:

```bash
mailburg konten hinzufuegen Proton --proton --benutzer ich@example.com
```

**Das Passwort dazu erzeugt die Bridge**, es steht in ihrem Fenster. Das
Kennwort Ihres Proton-Kontos taugt dafür nicht.

Im Einrichtungsassistenten tragen Sie dieselben Angaben über *Weiteres
Postfach von Hand eintragen …* ein: Server `127.0.0.1`, Port 1143, STARTTLS.

**Die Nachsicht beim Zertifikat gilt nur örtlich.** Die Bridge stellt sich
ihr Zertifikat selbst aus, deshalb sieht MailBurg bei ihr darüber hinweg –
aber nur, wenn der Server wirklich der eigene Rechner ist (`127.0.0.1`,
`localhost`, `::1`). Bei jeder anderen Adresse greift die Ausnahme nicht.
Sonst ließe sich damit die Zertifikatsprüfung für beliebige Server
abschalten, und zwar unbemerkt.

### Nach einer Neuanmeldung der Bridge: zwei Dinge sind fällig

**Das ist der Punkt, an dem man sich sonst wundert.** Meldet sich die Bridge
neu bei Proton an – oder ändert man dort etwas –, hat das zwei Folgen, und
beide betreffen MailBurg.

**Erstens erzeugt die Bridge ein neues Passwort.** Das alte gilt nicht mehr,
und zwar für *jedes* Programm, das die Bridge benutzt. Eintragen müssen Sie es
überall dort, wo es stand:

```bash
mailburg konten passwort Proton
```

Das legt das neue Passwort ab und probiert es gleich aus. Das Postfach bleibt
sonst unangetastet – **anders als beim Entfernen und Neuanlegen**, das den
Abrufzustand wegwirft und den nächsten Lauf das ganze Postfach noch einmal
durchgehen ließe. Im Fenster geht es über *Postfächer verwalten →
Passwort ändern …*.

Denken Sie an Ihr Mailprogramm: Thunderbird, Evolution und alles andere, was
die Bridge nutzt, brauchen dasselbe neue Passwort. Sonst steht dort ab sofort
„Anmeldung fehlgeschlagen", und man sucht den Fehler bei Proton.

**Zweitens lädt die Bridge ihren Bestand wieder herunter** – sie hält die
Mails ja örtlich vor. Während dieser Zeit ist ihr IMAP-Zugang zwar erreichbar,
aber noch nicht vollständig gefüllt.

**Rufen Sie erst ab, wenn sie damit fertig ist.** Sonst sieht MailBurg ein
halb gefülltes Postfach – nicht schlimm, denn beim nächsten Lauf kommt der
Rest nach, aber die Zahlen im Fenster verwirren. Steht die Bridge, holt ein
Druck auf **F5** den aktuellen Stand.

Anlass für eine Neuanmeldung gibt es selten – aber einer kam am 16.09.2026
vor: Wechselt der Schlüsselbund, in dem die Bridge ihre Zugangsdaten hält,
findet sie sie nicht mehr (siehe [Wenn etwas
schiefgeht](#wenn-etwas-schiefgeht) weiter unten). Danach ist die ganze Runde
fällig: neues Passwort in der Bridge, eintragen im Mailprogramm, eintragen in
MailBurg, warten bis der Bestand geladen ist.

## Welche Ordner archiviert werden

Alle, bis auf diese:

- **Papierkorb, Spam und Entwürfe.** Diese Post hat der Anwender bereits
  aussortiert. Sie ins Archiv zu holen, würde diese Entscheidung rückgängig
  machen und das Archiv ohne Nutzen aufblähen.
- **»Alle Nachrichten« bei Gmail.** Dieser Ordner enthält sämtliche Mails ein
  zweites Mal. Auf der Platte gäbe das keine doppelte Datei, wohl aber einen
  zweiten Fundort je Mail im Journal.

Was übergangen wird, lässt sich je Konto einstellen. Die Liste steht in
`konten.json` unter `ausschluss`; nachsehen lässt sie sich mit
`mailburg -v konten liste`.

Groß- und Kleinschreibung, Bindestriche und Leerzeichen spielen dabei keine
Rolle: »Junk-E-Mail«, »Junk E-Mail« und »junk email« meinen denselben Ordner.
Ein Ordner, der nur so *ähnlich* heißt, bleibt drin – »Werbung 2024« ist ein
eigener Name, kein Spamordner.

**Dieselbe Liste gilt beim Einlesen von der Platte** (`mailburg importieren`,
*Post → Lokale Mailordner einlesen …*). Ein Export aus einem anderen
Archivprogramm bringt die Ordnerstruktur mit, aus der er stammt – samt
Papierkorb. Mit `--alles` kommt alles mit.

### Post mit Spam-Marke im Betreff

Manche Server sortieren Spamverdacht nicht in einen Ordner, sondern setzen dem
Betreff eine Marke voran: `[SPAM] Gewinnbenachrichtigung`. Solche Post landet
im Posteingang, und kein Ordnerausschluss der Welt hält sie auf.

Auf Wunsch nimmt MailBurg sie gar nicht erst auf:

```bash
mailburg konten spamfilter Firma --ein     # mit den üblichen Marken
mailburg konten spamfilter Firma           # zeigen, was gilt
mailburg konten spamfilter Firma --aus     # wieder alles aufnehmen
mailburg konten spamfilter Firma --marke "***SPAM***"   # eigene Marke
```

**Nur wenn der Betreff mit der Marke beginnt.** Das ist die eine Entscheidung,
auf die es hier ankommt, und sie stammt aus einem echten Bestand: In einem
Archiv mit 68.000 Mails trugen 312 Nachrichten `[SPAM]` im Betreff – 304 am
Anfang, 8 mittendrin. Diese 8 sahen so aus:

```
AW: [SPAM]  Ihr Auftrag Nr. 22761 – Fragen zu Ihrer Bestellung
WG: [SPAM]  Teckentrup: Wöchentliches Update zur Lieferfähigkeit
```

Das ist Kundenkorrespondenz. Jemand hat auf eine markierte Mail geantwortet,
und die Marke wanderte in den Betreff der Antwort. **Wer solche Post
fernhält, verliert eine Bestellung.** Deshalb zählt ausschließlich der Anfang.

### Sehen Sie vorher nach, was der Filter treffen würde

**Der wichtigste Rat auf dieser Seite.** In demselben Archiv sah die Probe so
aus – alle Nachrichten, deren Betreff mit `[SPAM]` beginnt:

```
[SPAM] Rechnung 13007 / 13150 / 13405 / 13470 / 13479
[SPAM] Abbuchungs-Anzeige KdNr 600101
[SPAM] Lastschriftankündigung
[SPAM] RE: Bestellnr.: 30246, Rechnung Nr. 20423026
[SPAM] VS Sonnenschutz Auftragsbestätigung Nr. 369012
[SPAM] Teckentrup: Wöchentliches Update zur Lieferfähigkeit
```

**Kein einziger echter Spam.** Sieben Rechnungen, Lastschriften,
Auftragsbestätigungen – alles Geschäftspost, die der Spamfilter des Anbieters
falsch markiert hatte. Bei diesem Anbieter trägt die Marke im Betreff also
keine Aussagekraft; verlässlich war allein der Ordner, in den er sortiert.

Prüfen Sie das vor dem Einschalten an Ihrem eigenen Bestand:

```bash
mailburg suchen ~/Archiv 'betreff:"[SPAM]"'
```

Stehen dort Rechnungen und Bestellungen, lassen Sie den Filter aus. Der
Ordnerausschluss oben erledigt die Arbeit dann ohnehin – und er ist die
harmlosere Regel, weil eine Mail im Spamordner niemand gerettet hat.

**Von Haus aus ist der Filter aus**, und das hat einen Grund: Ein Spamfilter
irrt, und was nie archiviert wurde, fällt erst Jahre später auf – wenn
überhaupt. Diese Entscheidung trifft der Anwender für sein Archiv, nicht das
Programm für ihn. Wer sie trifft, sollte wissen:

- Was übergangen wurde, **steht in der Bilanz jedes Laufs** – stillschweigend
  verschwindet nichts.
- Ein Ordnerausschluss ist harmloser: Post im Papierkorb hat *jemand* dorthin
  gelegt. Eine Betreffmarke ist die Vermutung eines Filters.
- Für ein Geschäftsarchiv kann das Gegenteil richtig sein. Wer belegen muss,
  was ihn erreicht hat, will auch die falsch markierte Rechnung.

Für den umgekehrten Fall – einzelne Ordner *ausschließlich* archivieren – gibt
es beim Abruf `--ordner`:

```bash
mailburg abrufen ~/Archiv --konto Firma --ordner INBOX "INBOX/Rechnungen"
```

## Das Postfach bleibt unangetastet

MailBurg öffnet jeden Ordner nur lesend und holt die Mails so, dass der Server
sie nicht als gelesen markiert. Ungelesene Post ist nach dem Archivieren immer
noch ungelesen.

Gelöscht wird im Postfach nie. Wer eine Mail dort wegwirft, hat sie trotzdem
weiterhin im Archiv – das ist der Zweck der Übung.

## Nachsehen und prüfen

```bash
mailburg konten liste              # was eingerichtet ist
mailburg -v konten liste           # dazu die Ausschlusslisten
mailburg konten pruefen            # bei allen anmelden, Ordner zeigen
mailburg konten pruefen Firma      # nur bei diesem einen
mailburg konten entfernen Firma    # Konto und Passwort weg, Mails bleiben
```

## Wenn etwas schiefgeht

**„Für … liegt kein Passwort im Schlüsselbund" – und zwar bei allen Konten
auf einmal.** Dann fehlen die Passwörter fast nie wirklich. Sieben Passwörter
verschwinden nicht gemeinsam; was gleichzeitig passiert, ist etwas anderes.

Unter Linux beantwortet **nur ein Dienst** die Passwortanfragen aller
Programme – er hält den Namen `org.freedesktop.secrets`, und wer zuerst da
ist, gewinnt. Laufen zwei Schlüsselbünde nebeneinander, liegen Ihre
Passwörter womöglich im einen, während der andere antwortet und leer ist.
MailBurg sagt es dazu, wenn es diese Lage erkennt.

Nachsehen lässt sich das so:

```bash
busctl --user list | grep -E "secrets|kwallet|ksecret"
```

Steht neben `org.freedesktop.secrets` ein anderer Dienst, als Sie erwarten,
ist das die Ursache. **Neu eintragen hilft dann nicht** – die Passwörter
landen im falschen Tresor, und beim nächsten Wechsel stehen Sie wieder da.

MailBurg merkt sich beim Speichern, welcher Schlüsselbund geantwortet hat
(in `schluesselbund.json` neben der Kontenliste, nur der Name des Dienstes).
Wechselt er später, sagt MailBurg genau das – dann müssen Sie gar nicht erst
selbst nachsehen.

Am 07.09.2026 unter Manjaro mit KDE Plasma so passiert: Ein Systemupdate
brachte `gnome-keyring` mit, dessen systemd-Einheit ab Werk eingeschaltet ist
(`gnome-keyring-daemon.socket`). Sie startet den Dienst, sobald ein Programm
nach einem Passwort fragt – noch bevor KDEs eigener Schlüsselbund so weit ist.
Abhilfe war:

```bash
systemctl --user mask --now gnome-keyring-daemon.socket gnome-keyring-daemon.service
```

Danach einmal ab- und anmelden. **Bedenken Sie, was sonst noch in diesem
Schlüsselbund liegt** – dort gespeicherte Zugänge anderer Programme sind
danach ebenfalls im anderen Tresor zu suchen.

### Und wenn es trotz Maskierung wiederkommt

**Am 16.09.2026 war dieselbe Lage wieder da**, auf demselben Rechner, obwohl
die Maskierung von oben unverändert griff. Der Grund: Sie schließt nur *einen*
von zwei Wegen. Der zweite hat mit systemd gar nichts zu tun.

Neben den systemd-Einheiten kann D-Bus einen Dienst **selbst starten**, sobald
jemand nach seinem Namen fragt. Wer dafür zuständig ist, steht hier:

```bash
grep -l org.freedesktop.secrets /usr/share/dbus-1/services/*.service | \
  xargs grep -H Exec=
```

Steht dort `gnome-keyring-daemon`, ist das die Ursache – unabhängig davon, ob
irgendeine systemd-Einheit maskiert ist. Es genügt, dass ein beliebiges
Programm beim Anmelden nach einem Passwort fragt.

**Die Abhilfe ist ein eigener Eintrag im Benutzerordner.** D-Bus sucht dort
zuerst; `/usr/share` wird damit überstimmt, und kein Systemupdate kann es
zurückdrehen:

```bash
mkdir -p ~/.local/share/dbus-1/services
cat > ~/.local/share/dbus-1/services/org.freedesktop.secrets.service <<'ENDE'
[D-BUS Service]
Name=org.freedesktop.secrets
Exec=/usr/bin/ksecretd
ENDE
```

`/usr/bin/ksecretd` ist der Weg unter KDE Plasma. Unter anderen Arbeitsumgebungen
steht dort ein anderes Programm – welches, verrät die Liste oben.

Danach abmelden genügt **nicht**, wenn der alte Dienst schon läuft: Er hält den
Namen weiter, und ein Aktivierungseintrag greift nur bei einem freien Namen.
Zwei Dinge sind nötig:

```bash
busctl --user call org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus ReloadConfig
pkill -f "gnome-keyring-daemon.*--components=secrets"
```

Das erste liest die neue Datei ein – D-Bus kennt sie sonst nicht, weil er seit
dem Anmelden läuft. Das zweite gibt den Namen frei. Danach ab- und anmelden;
erst dann beansprucht der neue Dienst ihn beim Start.

> **Ist `Linger=yes` gesetzt** (`loginctl show-user $USER | grep Linger`),
> überlebt der alte Dienst sogar das Abmelden – dann führt kein Weg daran
> vorbei, ihn wie oben zu beenden. Genau daran ist der erste Reparaturversuch
> am 16.09. gescheitert: Der Prozess trug nach dem Neuanmelden dieselbe
> Nummer wie vorher. **Ein Prozess, dessen Nummer eine Abmeldung überlebt,
> wird nicht von der Sitzung gestartet.**

**Wer den falschen Dienst weckt, ist selten schuld.** Auf Stephans Rechner war
es die Proton Mail Bridge: Sie startet automatisch mit der Anmeldung, nutzt
`secret-service` (siehe `~/.config/protonmail/bridge-v3/keychain.json`) und
fragt als erste nach einem Passwort. Jedes andere Programm mit Autostart hätte
dasselbe ausgelöst – der Fehler saß in der Registrierung, nicht im Programm.

**Rechnen Sie damit, dass sich Programme neu anmelden müssen.** Ihre Zugänge
liegen im alten Tresor, und der antwortet nicht mehr. Bei der Bridge war eine
neue Proton-Anmeldung fällig; danach lag alles im richtigen Tresor.

**„Anmeldung abgelehnt"** – meist fehlt das App-Passwort, siehe oben. Bei GMX
und Web.de muss der IMAP-Zugriff zusätzlich in den Einstellungen der
Weboberfläche freigeschaltet werden.

**„Keine Verbindung"** – Server oder Port falsch. Fast alle Anbieter nutzen
Port 993 mit durchgehender Verschlüsselung; das ist die Vorgabe. Server, die
nur STARTTLS auf Port 143 anbieten, brauchen `--port 143 --starttls`.

**Ein einzelner Ordner fehlt** – MailBurg meldet übersprungene Ordner als
Hinweis am Ende des Laufs. Ein Ordner, den der Server nicht hergibt, bricht den
Abruf nicht ab; die übrigen kommen trotzdem durch.

**Eine einzelne Mail fehlt** – hat sich MailBurg an einer Nachricht verschluckt,
wird sie vorgemerkt und beim nächsten Lauf erneut angefordert. `mailburg -v
abrufen …` zeigt, um welche es ging und woran es lag.
