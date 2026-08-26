[Übersicht](../README.md) | [Anleitungen](README.md) | [Zeitsteuerung](zeitsteuerung.md) | [Windows](windows.md) | [Postfach entlasten](postfach-entlasten.md) | [Sichern](sicherung.md)

# Postfächer einrichten

MailBurg holt die Post über IMAP. Dafür braucht es drei Angaben – Server,
Benutzername und Passwort – und einen Kurznamen, unter dem die Mails im Archiv
erscheinen.

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

## App-Passwörter

Die großen Anbieter lassen das Kennwort der Weboberfläche für den Zugriff von
außen nicht mehr zu. Sie verlangen ein eigens erzeugtes Passwort, das nur für
diesen einen Zweck gilt und sich einzeln widerrufen lässt.

| Anbieter | Server | Wo das App-Passwort herkommt |
|----------|--------|------------------------------|
| Gmail | `imap.gmail.com` | Google-Konto → Sicherheit → Bestätigung in zwei Schritten → App-Passwörter. Setzt zwingend die Zwei-Faktor-Anmeldung voraus. |
| GMX | `imap.gmx.net` | Einstellungen → POP3/IMAP-Abruf zuerst freischalten |
| Web.de | `imap.web.de` | Einstellungen → POP3/IMAP-Abruf zuerst freischalten |
| Outlook, Hotmail | `outlook.office365.com` | Microsoft-Konto → Sicherheit → Erweiterte Optionen → App-Kennwörter |
| Posteo | `posteo.de` | Das gewöhnliche Passwort genügt |
| mailbox.org | `imap.mailbox.org` | Das gewöhnliche Passwort genügt |
| IONOS | `imap.ionos.de` | Das gewöhnliche Passwort genügt |

Anmeldung per OAuth2 – der Weg, den Google und Microsoft eigentlich vorsehen –
ist geplant, aber noch nicht gebaut.

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
