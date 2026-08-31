[Deutsch](README.md) | [English](README.en.md) | [Änderungsprotokoll](CHANGELOG.md) | [TODO](TODO.md) | [Anleitungen](docs/README.md) | [Rechtliches](RECHTLICHES.md)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark-1600.png">
    <img src="assets/banner-1600.png" alt="MailBurg – E-Mails. Sicher bewahrt." width="620">
  </picture>
</p>

# MailBurg

Ein Archiv für E-Mail, das an den Ort gehört, den Sie bestimmen.

MailBurg holt Ihre Post aus beliebig vielen Postfächern zusammen, legt sie an
einer Stelle ab und macht sie durchsuchbar – Mailtexte, Kopfzeilen und den
Inhalt der Anhänge. Wo dieser eine Ort liegt, entscheiden Sie: interne Platte,
externe Platte, ein von Nextcloud synchronisierter Ordner.

Entwickelt und im Alltag erprobt unter Linux. Unter **Windows** gibt es eine
fertige `MailBurg.exe` – ohne Python, ohne Installation, mit eingebauter
Texterkennung; Einrichtung, Abruf, Suche und der regelmäßige Abruf über die
Aufgabenplanung sind dort durchgespielt. Unter **macOS** laufen bisher nur
Tests und Einrichtung nachweislich durch, im täglichen Betrieb war MailBurg
dort noch nicht – wer es dort einsetzt, sollte anfangs regelmäßig
`mailburg pruefen` laufen lassen und das Postfach nicht zu früh aufräumen.

<p align="center">
  <img src="assets/uebersicht-2000.png" alt="Übersicht: Postfächer, Mailprogramme und die Proton-Bridge werden nur gelesen; MailBurg legt jede Mail bytegenau in einem Archiv ab, dessen Ort frei wählbar ist, mit Protokoll und Hash-Kette. Der Suchindex liegt außerhalb des Archivs und ist jederzeit neu erzeugbar. Zugriff über Oberfläche und Kommandozeile." width="960">
</p>

**Neu hier?** [Erste Schritte](docs/erste-schritte.md) führt mit Bildern von der Installation bis zum ersten durchsuchbaren Archiv. [Die Oberfläche](docs/oberflaeche.md) erklärt jedes Fenster und jeden Menüpunkt.

## Warum

Es gibt gute Programme für diese Aufgabe, aber sie haben Grenzen: Sie laufen
nur unter Windows, sie beschränken die Zahl der Konten, oder sie sperren das
Archiv in ein Format, aus dem man es ohne das Programm nicht wieder herausbekommt.

MailBurg macht es andersherum:

- **Keine Beschränkung der Kontenzahl.** Dreißig Adressen sind vorgesehen, mehr
  ist kein Problem.
- **Ihr Archiv, Ihr Format.** Jede Mail liegt als einzelne `.eml`-Datei. Auch
  ohne MailBurg kommen Sie an jede einzelne heran.
- **Der Suchindex ist wegwerfbar.** Er lässt sich jederzeit vollständig aus dem
  Archiv neu erzeugen und muss deshalb nicht gesichert werden.
- **Verschlüsseln, wenn die Post das Haus verlässt.** Wahlweise beim Anlegen:
  Mails und Protokoll wandern dann verschlüsselt auf die Platte, samt
  verdeckter Dateinamen. Dazu ein Notschlüssel zum Ausdrucken – ein Archiv
  überdauert Jahrzehnte, ein Passwort im Kopf nicht.

## Stand

**Fassung 0.12.0, im Alltag im Einsatz.** Archivformat, IMAP-Abruf, Suche,
Oberfläche, Texterkennung für eingescannte PDF, Sicherung und der regelmäßige
Abruf im Hintergrund stehen und werden täglich benutzt – unter Linux mit einem
Bestand von über 16.000 Mails, unter Windows mit der fertigen `MailBurg.exe`.

OAuth2 ist gebaut, aber nur gegen einen nachgebauten Anbieter geprüft: Bei
einem echten Microsoft- oder Google-Konto hat sich damit noch niemand
angemeldet. Wer dort abruft, nimmt vorerst besser ein App-Passwort.

Verschlüsselte Archive gibt es seit dem 31.08.2026 – gebaut und getestet,
aber im Alltag noch nicht erprobt. Siehe
[docs/verschluesselung.md](docs/verschluesselung.md).

Was noch fehlt: Outlook-`.pst`, Pakete für alle drei Systeme. Und der Betrieb unter macOS ist ungeprüft. Die vollständige
Liste steht in [TODO.md](TODO.md).

## Wie es funktioniert

Ein Archiv ist ein Verzeichnis:

```
MeinArchiv/
├── archive.json     Kennung, Betriebsart, Fristenregel
├── mail/            die Mails, nach Monat sortiert
│   └── 2026/08/3f/3f8a9c1e….eml.zst
└── meta/            das Journal mit der Hash-Kette
```

Der Dateiname jeder Mail ist der SHA-256 ihres Inhalts. Das hat zwei Folgen:
Dieselbe Mail zweimal einzulesen erzeugt keine zweite Datei, und eine
beschädigte Datei fällt beim Lesen von selbst auf.

Die Mail wird dabei **bytegenau** abgelegt – keine geglätteten Zeilenenden,
keine reparierten Kopfzeilen. Nur so bleibt eine DKIM-Signatur später noch
prüfbar.

### Zwei Betriebsarten

Beim Anlegen entscheiden Sie, worum es geht:

**Privatarchiv.** Keine Fristen, kein Ballast, löschen jederzeit. Das entspricht
der Rechtslage: Wer ausschließlich eigene Mails archiviert, fällt unter die
Haushaltsausnahme der DSGVO und unterliegt ihr gar nicht.

**Geschäftsarchiv.** Jeder Vorgang wandert in eine Hash-Kette – jeder Eintrag
trägt den Hash seines Vorgängers. Wer nachträglich etwas ändert, zerreißt die
Kette sichtbar. Gelöscht wird nur über Grabsteine: Der Inhalt verschwindet, der
Vorgang bleibt protokolliert. So lassen sich das Recht auf Löschung und die
Unveränderbarkeit gleichzeitig erfüllen. Aufbewahrungsfristen für Deutschland,
Österreich und die Schweiz bremsen zu frühes Löschen.

> **Wichtig:** MailBurg *unterstützt* einen revisionssicheren Betrieb, es
> *stellt ihn nicht her*. Dazu gehören eine Verfahrensdokumentation und
> geregelte Abläufe. Eine Software allein kann das nicht leisten. Mehr dazu in
> [RECHTLICHES.md](RECHTLICHES.md).

### Suchen

Die Suche ist deutsch und läuft über zwei Indizes:

```
rechnung                    irgendwo in Text, Betreff oder Anhang
von:müller rechnung         beides muss zutreffen
betreff:"offene posten"     mehrere Wörter in Anführungszeichen
hat:anhang typ:pdf jahr:2025
konto:firma ordner:Gesendet
-werbung                    schließt Treffer aus
```

`betreff:rechnung` findet auch **Schluss**rechnung. Das ist kein Sonderwunsch,
sondern im Deutschen der Normalfall – wir schreiben zusammen. Dafür gibt es
neben dem Wortindex einen zweiten über Dreizeichengruppen.

Auch die Schreibweise darf abweichen: `von:muller` und `von:mueller` finden
beide „Müller", `bahnhofstrasse` findet „Bahnhofstraße". Groß- und
Kleinschreibung spielt nirgends eine Rolle.

Ging eine Sache mehrmals hin und her, zeigt MailBurg zu jeder Nachricht den
**ganzen Gesprächsverlauf** – zusammengehalten über die Kopfzeilen, die jedes
Mailprogramm mitführt, nicht über den Betreff. Der wechselt unterwegs, und
zwei Mails mit „Rechnung" im Betreff haben meistens nichts miteinander zu tun.

## Loslegen

Voraussetzung ist Python 3.11 oder neuer. Weitere Pakete braucht der Kern nicht.

```bash
git clone https://github.com/Stephan-Lefty/MailBurg.git
cd MailBurg
./install.sh
```

Das richtet MailBurg im Benutzerverzeichnis ein – ohne Administratorrechte, ohne
etwas am System zu ändern – und legt den Befehl `mailburg` an. Unter Windows
übernimmt das `.\install.ps1`, siehe [docs/windows.md](docs/windows.md).
`./install.sh --entfernen` baut alles wieder ab; das Archiv bleibt dabei
unangetastet.

Wer lieber selbst bestimmt, wohin es geht, nimmt `pip install ".[alles]"` – oder
lässt die Installation ganz weg und ruft `python3 -m mailburg` direkt im
Quellverzeichnis auf.

**Wenn Sie einzelne Zusätze wählen:** Der Kern kommt ohne Fremdpakete aus, aber
er kann dann auch nur das Nötigste. Was wozu gehört:

| Zusatz | wofür | ohne ihn |
|---|---|---|
| `oberflaeche` | das Fenster, PySide6 | nur die Kommandozeile |
| `imap` | Postfächer abrufen, Passwörter im Schlüsselbund | kein IMAP |
| `anhaenge` | Text aus PDF und Büroformaten | Anhänge bleiben unauffindbar |
| `packen` | kleinere Sicherungen (Zstandard) | LZMA, langsamer |
| `verschluesselung` | verschlüsselte Archive | nur unverschlüsselt |

`pip install ".[oberflaeche]"` genügt also nicht, um Postfächer abzurufen –
dafür braucht es `imap` dazu. Am einfachsten ist `".[alles]"`.

```bash
# Archiv anlegen
mailburg anlegen ~/Archiv --modus privat

# Thunderbird-Profil einlesen (findet die Ordnerstruktur von selbst)
mailburg importieren ~/Archiv ~/.thunderbird/xxxx.default --konto privat

# Suchen
mailburg suchen ~/Archiv betreff:rechnung jahr:2025

# Nachsehen, was drin ist
mailburg info ~/Archiv

# Hash-Kette und Ablage prüfen
mailburg pruefen ~/Archiv
```

`mailburg suchhilfe` erklärt die Suchsprache.

Als Quelle taugt ein Thunderbird-Profil, ein Maildir-Verzeichnis oder eine
einzelne MBOX-Datei. Bei einem Thunderbird-Profil werden alle Konten und Ordner
mitsamt ihrer Verschachtelung übernommen.

## Postfächer abrufen

Für die laufende Archivierung holt MailBurg die Post direkt aus dem Postfach:

```bash
# Postfach einrichten – das Passwort wird abgefragt, nicht als Argument übergeben
mailburg konten hinzufuegen Firma \
    --server imap.example.org --benutzer post@example.org

# Nachsehen, was eingerichtet ist und welche Ordner archiviert würden
mailburg konten liste
mailburg konten pruefen Firma

# Abrufen – beim ersten Mal alles, danach nur noch das Neue
mailburg abrufen ~/Archiv
mailburg abrufen ~/Archiv --konto Firma
```

Der Abruf eignet sich für die Zeitsteuerung: `mailburg abrufen ~/Archiv` in
einem nächtlichen Cron-Auftrag genügt.

**Das Postfach bleibt unangetastet.** MailBurg öffnet jeden Ordner nur lesend
und holt die Mails mit `BODY.PEEK[]`. Ungelesene Post ist hinterher immer noch
ungelesen – ein Archivprogramm, das das nicht einhält, ist unbrauchbar.

**Passwörter stehen im Schlüsselbund** des Betriebssystems, nie in einer
Konfigurationsdatei. Dafür wird das Paket `keyring` gebraucht; fehlt es, läuft
alles weiter, nur wird das Passwort bei jedem Abruf neu erfragt. In die
Kontenliste kommt es auch dann nicht.

Bei Gmail, GMX, Web.de und Outlook genügt das Kennwort der Weboberfläche nicht –
diese Anbieter verlangen für den Zugriff von außen ein eigenes App-Passwort.
Die Anmeldung per OAuth2 gibt es inzwischen ebenfalls, sie ist aber nur gegen
einen nachgebauten Anbieter geprüft – siehe
[Anmeldung per OAuth2](docs/oauth2.md).

**Was übergangen wird:** Papierkorb, Spamverdacht und Entwürfe. Der Anwender hat
diese Post schon einmal aussortiert; sie ins Archiv zu holen, würde diese
Entscheidung rückgängig machen. Bei Gmail bleibt zusätzlich »Alle Nachrichten«
außen vor – dieser Ordner enthält sämtliche Mails ein zweites Mal.

**Nur das Neue.** Woher MailBurg weiß, wo es stehen geblieben ist, ist die
einzige wirklich heikle Stelle daran: Der Höchststand wird nicht mitgeschrieben,
sondern aus dem Archiv selbst abgelesen. Bricht ein Abruf mitten im Ordner ab,
holt der nächste genau den Rest. Und eine einzelne Mail, an der sich MailBurg
verschluckt hat, wird vorgemerkt und beim nächsten Lauf erneut angefordert –
sonst fehlte sie für immer, ohne dass es je jemand bemerkte.

## Zu Nextcloud

Ein Archiv in einem synchronisierten Ordner funktioniert, weil die Ablage darauf
ausgelegt ist: Jede Mail ist eine eigene Datei, und alte Monatsordner ändern sich
nie wieder – synchronisiert werden sie also genau einmal.

Der **Suchindex liegt bewusst nicht im Archiv**, sondern lokal im
Anwendungsverzeichnis. SQLite auf einem synchronisierten Laufwerk geht früher
oder später kaputt; das ist der häufigste Weg, sich ein Archiv zu zerschießen.
Verloren geht dabei nichts – der Index entsteht mit `neuaufbau` in Minuten neu.

Solange ein Rechner das Archiv geöffnet hat, liegt eine Sperrdatei darin. Zwei
Rechner, die gleichzeitig hineinschreiben, würden sonst einen
Synchronisationskonflikt erzeugen, den niemand mehr auflösen kann.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Lizenz

MIT – siehe [LICENSE](LICENSE).
