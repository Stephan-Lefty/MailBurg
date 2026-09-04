[Deutsch](CHANGELOG.md) | [Übersicht](README.md) | [TODO](TODO.md) | [Anleitungen](docs/README.md)

# Änderungsprotokoll

Alle nennenswerten Änderungen an MailBurg stehen hier.

Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionsnummern folgen [Semantic Versioning](https://semver.org/lang/de/).

## [Unveröffentlicht]

### Hinzugefügt

- **Das rote Wappen steht jetzt in der Weboberfläche** – in der Kopfzeile
  jeder Seite und als Lesezeichensymbol im Browser.

  `werkzeuge/server_logo.py` erzeugt es seit dem 31.08., `assets/server/`
  enthält es in allen Größen samt `.ico` – **benutzt wurde es an keiner
  einzigen Stelle.** Stephan hat am 03.09. danach gesucht und es nicht
  gefunden. Dieselbe Klasse wie die drei Befunde vom selben Tag: etwas,
  das vollständig da ist und nirgends abgeholt wird.

  Die Bildersuche liegt dafür jetzt in `mailburg/bilder.py` statt in
  `mailburg/ui/bilder.py`: Der Dienst darf nicht von PySide6 abhängen,
  das auf einem Server gar nicht installiert ist. Was zwei Teile
  brauchen, gehört keinem von beiden.

  Nebenbei aufgefallen: Die `.ico` wiegt 370 KB, weil sie alle Größen bis
  256 Pixel enthält – als Lesezeichensymbol das Hundertfache des
  64er-PNG für dieselbe Briefmarke. Verlinkt sind deshalb die PNG; die
  `.ico` liegt allein unter `/favicon.ico`, für Programme, die dort
  blind nachfragen.

- **Viele Nachrichten auf einmal aus dem Archiv auf die Platte
  zurückspielen** – *Post → Ins Dateisystem zurückspielen …* und
  `mailburg zurueckspielen`. Anleitung:
  [docs/zurueckspielen.md](docs/zurueckspielen.md).

  Gewünscht am 03.09.2026 von dem Anwender, der auch JMAP angestoßen
  hat: »Ich würde mir ein Restore wünschen, wie in MailStore Home. […]
  Also unabhängige Backups und Restores.« Einzelne Nachrichten gingen
  längst zurück – ins Mailprogramm, in ein beliebiges Postfach, als
  Datei. Was fehlte, war die Menge.

  **Drei Formate, und die Wahl ist keine Geschmacksfrage.** *Maildir*
  ist bytegenau und bringt den Lesezustand mit – das Format für alles,
  was wieder ein Postfach werden soll. *MBOX* ist das Format von
  Thunderbirds lokalen Ordnern und **als einziges nicht bytegenau**: Eine
  Zeile, die mit »From « beginnt, bekommt ein »>« davor, sonst gälte sie
  als Anfang der nächsten Nachricht. *.eml* ist eine Datei je Mail zum
  Hineinziehen in ein beliebiges Programm.

  **Zweimal zurückspielen ändert nichts.** MailBurg erkennt im
  Zielordner wieder, was von ihm stammt – der Dateiname enthält den Hash
  der Nachricht. Ein abgebrochener Lauf lässt sich deshalb einfach
  wiederholen, und ein zweiter holt nach, was dazugekommen ist.

  **Das ist der Grund, warum dieser Weg vor dem über IMAP kam.** Dort
  legt der Server bei jedem `APPEND` eine neue Kopie an, und die neuen
  UIDs identifizieren nichts. Wiedererkennen ginge nur über die
  `Message-ID`, und die müsste MailBurg vor dem Schreiben aus dem Ziel
  auslesen – bei zehntausend Mails ein eigener Durchlauf.

  Weiteres, das nicht offensichtlich ist: Eine Mail, die an mehreren
  Stellen lag, wird trotzdem nur einmal geschrieben – bei Gmail und
  Proton ist Mehrfachablage der Normalfall, und wer alle Fundorte
  schreibt, hat dieselbe Rundmail fünfmal. Eine kaputte Nachricht
  beendet den Lauf nicht, sondern kommt in den Bericht. Und der Vorgang
  steht im Journal, mit Ziel, Format und Anzahl: Aus dem Archiv sind
  Daten herausgegangen.

## [1.2.1] – 2026-09-03

### Behoben

- **`install.sh` gab einen Hinweis, der bei fish und zsh ins Leere ging.**
  Gemeldet von dem Anwender, der auch JMAP angestoßen hat: »Ich habe noch
  das Problem, dass ich es nach der Installation nicht via Konsole starten
  kann, aber das liegt vermutlich an fish.«

  Es lag an fish, und der Fehler war unserer, gleich doppelt. Erstens
  prüfte das Skript **seinen eigenen** Suchpfad – den von bash, in dem es
  läuft. Viele Distributionen tragen `~/.local/bin` in `/etc/profile` ein,
  das fish gar nicht liest: bash findet den Ordner, das Skript schweigt,
  und in der Shell des Anwenders fehlt er trotzdem.

  Zweitens nannte der Hinweis `~/.bashrc` – eine Datei, die weder fish
  noch zsh anfassen. **Ein Hinweis, der auf die falsche Datei zeigt, ist
  schlimmer als keiner:** Wer die Zeile dort einträgt, sucht den Fehler
  danach überall, nur nicht mehr im Suchpfad.

  Jetzt wird die Anmelde-Shell gefragt und die passende Zeile genannt –
  `fish_add_path`, `~/.zshrc` oder `~/.bashrc` –, dazu der Satz, dass der
  Start aus dem Anwendungsmenü davon unberührt bleibt: Der Menüeintrag
  nennt den vollen Pfad. Vier Tests führen den Block wirklich aus.

### Geändert

- **JMAP ist zum ersten Mal gegen einen echten Server gelaufen.** Am
  03.09.2026 hat ein Anwender rund 5.000 Nachrichten aus einem selbst
  betriebenen **Stalwart** geholt – »JMAP funktioniert einwandfrei und das
  Teil ist echt schnell. Für 200 Mails benötige ich weniger als 5
  Sekunden.«

  Damit fällt der Vorbehalt, der seit der 1.1.0 in README, Handbuch,
  Anleitung und Quelltext stand. **Er fällt aber nicht ganz:** Bei
  Fastmail hat es weiterhin niemand ausprobiert, und dort ist zweierlei
  anders – die Anmeldung mit einer Zugriffsmarke statt mit Benutzername
  und Passwort, und die Ordnerrollen kommen von einem fremden Anbieter.

## [1.2.0] – 2026-09-03

### Hinzugefügt

- **Lokale Mailordner lassen sich jetzt aus dem Fenster einlesen**
  (*Post → Lokale Mailordner einlesen …*). Thunderbird-Profile, Maildir,
  MBOX und Verzeichnisse voller `.eml` konnte MailBurg von Anfang an –
  aber nur über `mailburg importieren` im Terminal.

  Ein Anwender hat sich am 01.09. genau das gewünscht, was längst da
  war. **Das ist ein Befund über die Oberfläche, nicht über den
  Funktionsumfang:** Eine Funktion, die niemand findet, gibt es für den
  Anwender nicht. Im Post-Menü standen an der Stelle zwei Trennlinien
  hintereinander – die Lücke, in der der Punkt fehlte.

  Der Dialog schlägt vor, was er auf dem Rechner findet, und zeigt vor
  dem Start, was er im gewählten Ordner erkannt hat, mitsamt den
  Ordnernamen. Wer »Maildir« nicht kennt, kann einem Pfadfeld sonst
  nicht ansehen, ob er das Richtige gewählt hat.

- **Konten lassen sich aus Evolution übernehmen**, nicht mehr nur aus
  Thunderbird. Von demselben Anwender gewünscht, der unter GNOME
  umgestiegen ist: »Wünschenswert für die Zukunft wäre also auch ein
  Import der Konten aus Evolution.«

  Evolution legt jedes Konto als eigene `.source`-Datei unter
  `~/.config/evolution/sources` ab. Gelesen werden Server, Port,
  Benutzername und Verschlüsselungsart – **Passwörter ausdrücklich
  nicht**, aus demselben Grund wie bei Thunderbird.

  Neu ist dabei `uebernahme.alle_quellen()`: **eine Stelle, die weiß,
  welche Mailprogramme in Frage kommen.** Vorher nannte jeder Aufrufer
  Thunderbird beim Namen – die Kommandozeile, der Assistent, der
  Kontendialog. Evolution hinzuzufügen hieße sonst, dieselbe Ergänzung
  dreimal zu machen und beim vierten Aufrufer zu vergessen.

- **In einer geöffneten Nachricht lässt sich suchen** (*Strg+F*).
  Ebenfalls von einem Anwender gewünscht: »Leider wird innerhalb des
  Fensters keine Suchfunktion angeboten, so dass die Suche innerhalb
  einer einzelnen langen Mail nach einem Stichwort innerhalb des Tools
  nicht möglich ist.«

  Ein blinder Fleck: MailBurg sucht sehr gut *über* Mails – Volltext,
  zwei Indizes, Anhänge bis in eingescannte PDF hinein – und hörte in
  der einzelnen Mail auf. Wer einen Newsletter mit zweihundert Zeilen
  öffnet, weil die Volltextsuche ihn gefunden hat, stand dann davor.

  Während des Tippens springt MailBurg zur ersten Stelle und nennt die
  Zahl der Treffer; `F3` und `Umschalt+F3` gehen weiter und zurück, am
  Ende beginnt es von vorn. Groß- und Kleinschreibung zählt zunächst
  nicht. **Bewusst keine zweite Suchsprache** – kein `von:`, kein
  `jahr:`. Wer eine Stelle in einem Text sucht, erwartet Strg+F und
  nichts weiter.

- **Evolutions lokale Ordner werden erkannt.** Sie liegen nach
  Maildir++ unter `~/.local/share/evolution/mail/local`: Die Wurzel
  enthält kein `cur/`, sondern Unterverzeichnisse `.Inbox`, `.Sent`.
  Wer sie auswählte, bekam die Meldung, das sei kein Maildir – obwohl
  genau das darin lag. Der führende Punkt fällt weg, die weiteren
  werden zu Unterordnern: `.Projekte.2025` wird zu `Projekte/2025`.

### Behoben

- **Beim Einlesen eines Maildirs ging der Lesezustand verloren.** Ein
  Fehler, der seit der ersten Fassung darin steckte: Maildir kodiert
  den Zustand im Dateinamen hinter `:2,` – Pythons `mailbox.Maildir`
  schneidet diesen Teil bei `keys()` aber ab. Zerlegt wurde trotzdem
  der Schlüssel, und das ergab **immer** einen leeren Zustand. Jede
  eingelesene Mail landete als ungelesen im Archiv, auch die vor Jahren
  beantwortete.

  Gefunden nur, weil für Evolution ein Test geschrieben wurde, der den
  Zustand mitprüft.

- **Der Postfachbaum wächst während des Abrufs mit.** Er wurde bisher
  erst aufgebaut, wenn der Abruf fertig war. Bei 6.000 Mails hieß das:
  minutenlang ein leerer Baum und »0 Mails im Archiv · noch nicht
  abgerufen«, während unten links »2800 geholt, 2791 neu« stand – zwei
  Anzeigen im selben Fenster, die einander widersprachen.

  Der Rückmelder dazu: »Während des Abrufs war ich mir nicht sicher, ob
  das Tool wirklich etwas Sinnvolles macht.« Dabei sagt der Kommentar in
  `core/index.py` seit jeher, wofür der WAL-Modus da ist.

- **Geöffnete Anhänge landeten in `/tmp` und blieben dort liegen.** Für
  die vollständige Mail daneben war seit jeher begründet, warum sie dort
  nicht hingehört – auf einem Mehrbenutzersystem darf dort jeder
  mitlesen. Für den PDF-Anhang derselben Mail galt dieselbe Begründung,
  nur wandte sie niemand an. Ein Anhang aus einem Geschäftsarchiv ist
  eine Rechnung, ein Vertrag, ein Arztbericht.

  Sie liegen jetzt im geschützten Cache-Ordner mit `0600` und
  verschwinden nach vier Stunden, spätestens beim Beenden.

- **Ließ sich ein Anhang nicht öffnen, passierte stillschweigend
  nichts.** Der Rückgabewert von `openUrl()` wurde nie angesehen. Ein
  Anwender klickte in einem Container ohne PDF-Betrachter auf ein PDF
  und bekam einen Browser mit einer fremden Seite; dass MailBurg dazu
  schwieg, machte aus einer erklärbaren Lage ein Rätsel.

## [1.1.0] – 2026-09-03

### Hinzugefügt

- **JMAP als zweiter Abrufweg** ([RFC 8620](https://www.rfc-editor.org/rfc/rfc8620)
  und [RFC 8621](https://www.rfc-editor.org/rfc/rfc8621)), von einem Anwender
  gewünscht. Anleitung: [docs/jmap.md](docs/jmap.md).

  **Warum das für ein Archiv lohnt.** IMAP kann nicht sagen, was sich
  geändert hat – MailBurg baut die Frage über die höchste bekannte
  Nachrichtennummer je Ordner nach, und das ist eine Näherung: Nachträglich
  einsortierte Mails rutschen durch, nach einem Serverumzug beginnt die
  Zählung von vorn. JMAP kennt einen *Stand* und beantwortet in einer
  Anfrage, was seither dazugekommen ist.

  Nachgemessen am nachgebauten Server: Der zweite Lauf lädt genau die neuen
  Nachrichten und rührt die vorhandenen nicht an. Kennt der Server den Stand
  nicht mehr – Änderungslisten werden nicht ewig aufbewahrt –, fällt der
  Abruf auf den vollständigen Weg zurück, statt stillschweigend nichts mehr
  zu holen.

  **Die Nachricht kommt über die Download-Adresse**, nicht aus dem JSON:
  byteweise so, wie sie ankam, mit prüfbarer DKIM-Signatur. Die zerlegte
  Fassung wäre bequemer und für ein Archiv wertlos.

  **Ordner werden über ihre Rolle beurteilt**, nicht über den Namen. Ein
  Ordner heißt je nach Sprache »Papierkorb«, »Trash« oder »Corbeille«; seine
  Rolle heißt überall `trash`. Der Gmail-Fall ist mit abgedeckt: Ein Ordner
  mit der Rolle `all` enthält sämtliche Mails ein zweites Mal.

  Einzurichten im Fenster über *Abrufweg* im Postfachdialog oder mit
  `mailburg konten hinzufuegen … --jmap`. Der Weg steht am einzelnen
  Postfach – ein Fastmail-Konto über JMAP und die übrigen weiter über IMAP
  ist ausdrücklich vorgesehen.

  **Wer es benutzen kann:** Fastmail, Stalwart, Cyrus ab 3.6, Apache James.
  Nicht Gmail, Outlook, GMX, Web.de oder Proton. Das ist heute die
  Einschränkung – JMAP ist die bessere Technik und die seltenere.

  **Noch nie gegen einen echten Anbieter gelaufen.** Geprüft ist alles gegen
  `tests/fake_jmap.py`, also gegen die Annahmen des Programms. Derselbe Satz
  steht bei OAuth2, und er stimmt dort wie hier.

- **Zeitstempel nach RFC 3161.** Ein Siegel kann jetzt zusätzlich ein
  Datum von dritter Seite tragen: Ein Zeitstempeldienst bestätigt, dass
  der Zustand des Archivs zu einem bestimmten Zeitpunkt schon so war.
  Bisher stand nur die Uhr des eigenen Rechners dahinter, und die lässt
  sich stellen.

  ASN.1 und DER sind von Hand kodiert (`core/der.py`), damit der Kern
  ohne Fremdpakete auskommt – ein Archivprogramm soll in zwanzig Jahren
  noch an seine eigenen Daten kommen. Geprüft gegen `openssl ts`, das
  die erzeugten Anfragen liest und die Stempel mit »Verification: OK«
  bestätigt. **Ein echter Dienst wurde noch nie gefragt.**

- **Der Abschnitt über das Archiv im Browser steht jetzt auch im
  README.** Gebaut ist der Dienst seit dem 31.08., aber wer nur die
  Übersicht las, erfuhr nichts davon.

### Behoben

- **Der Neuaufbau des Suchindex verlor den erkannten Text aus
  eingescannten PDF.** Der Kommentar in `erkennung.py` sagte seit jeher,
  welcher Schlüssel dafür gedacht ist; abgeholt hat ihn niemand. Wer
  seinen Index neu baute – nach der 1.0 also jeder –, fand seine Scans
  nicht mehr, und es sagte ihm nichts.

- **Eine verwaiste Sperrdatei sperrte das Archiv dauerhaft aus.** Nach
  einem Absturz blieb sie liegen und nannte einen Vorgang, den es nicht
  mehr gab. MailBurg räumt sie jetzt selbst weg, wenn sie von diesem
  Rechner stammt und der Vorgang tot ist. Stammt sie von einem anderen
  Rechner, lässt sich das nicht entscheiden – dann **fragt MailBurg und
  der Anwender entscheidet**, statt ihn ins Terminal zu schicken.

- **Die DBus-Meldung beim ersten Start.**
  `qt.qpa.services: Failed to register with host portal` –
  `setDesktopFileName` ist statisch und stand nach der Erzeugung der
  `QApplication`. Harmlos war die Meldung immer; sie stand aber als
  Erstes im Terminal, wenn jemand MailBurg zum ersten Mal startet.

- **Zwei JMAP-Konten beim selben Anbieter überschrieben sich im
  Schlüsselbund.** Der Eintrag heißt `benutzer@server`; bei einer
  Zugriffsmarke gibt es keinen Benutzer, und alle Fastmail-Konten zeigen
  auf dieselbe Adresse. Jetzt tritt der Kontoname an die Stelle des
  fehlenden Benutzernamens.

### Geändert

- **Eine Stelle entscheidet, wie abgerufen wird.** Fünf Stellen im Programm
  erzeugten eine IMAP-Verbindung von Hand – aus dem Fenster, aus dem
  Zeitplan, über `mailburg abrufen`, beim Prüfen und beim Abgleich. Die
  sechste, die später dazukäme, wüsste von JMAP nichts, und der Anwender
  merkte das als das Merkwürdigste, was ein Programm tun kann: Es
  funktioniert an vier Stellen und an der fünften nicht.

### Oberfläche

Vier Punkte aus der ersten Rückmeldung von außerhalb – jemand, der
MailBurg nicht gebaut hat, hat es benutzt. Drei davon waren echte
Fehler.

- **Die Bereiche heben sich jetzt voneinander ab.** Wörtlich bemängelt:
  »Für meinen Geschmack fehlen da ein paar Rahmen oder farbliche
  Abhebungen.« Suchbereich, Postfachbaum, Kopf einer Nachricht und
  Statuszeile sind abgesetzt, und die Griffe der Teiler sind sichtbar –
  vorher wusste niemand, dass sich die Bereiche verschieben lassen.

  **Alle Farben stammen aus der Systempalette.** Feste Farbwerte säßen
  im dunklen Thema oder bei einem Hochkontrast-Thema falsch; ein
  Wächtertest prüft das Stylesheet Wert für Wert.

- **Der Knopf zur Ordnerwahl war zu übersehen.** Er heißt jetzt »Ordner
  auswählen …«, trägt ein Symbol und ist der Vorgabeknopf der Seite. Wo
  das Archiv liegt, ist die wichtigste Entscheidung des Assistenten –
  wer den Knopf nicht findet, nimmt den Vorschlag, statt zu wählen.

- **Die Passwortfelder gingen unter.** Sie standen weit rechts vom
  Kontonamen, weil sich die Namensspalte dehnte.

- **In der Standardgröße wird nicht mehr gerollt.** Sechs Runden
  Meldungen an einem Abend, jede ein echter Fehler: Auswahlfelder so
  breit wie das Layout statt wie ihr Inhalt, aufgeklappte Listen, die
  bei 120 px blieben, Dialoggrößen als geratene Zahlen, und umbrechende
  Texte, die zusammengedrückt wurden. Geratene Maße sitzen falsch,
  sobald jemand die Schrift ändert – und die lässt sich in MailBurg
  einstellen.

- **Strg++ vergrößerte nichts.** `QKeySequence.ZoomIn` *ist* unter Linux
  Strg++, und daneben stand dasselbe noch einmal von Hand. Qt hält zwei
  gleiche Kürzel für mehrdeutig und löst dann keines aus. Das Menü
  zeigte es brav an – deshalb sucht man dort zuletzt.

- **Die Schriftgröße wirkte nur auf das Hauptfenster.** Menüs, Dialoge
  und das Lesefenster sind in Qt eigene Fenster, keine Kinder.

- **Die Bilder in den Anleitungen zeigten ein anderes MailBurg als das
  Programm** – das Werkzeug, das sie erzeugt, setzte das Stylesheet gar
  nicht.

## [1.0.1] – 2026-08-31

### Behoben

- **Beim Start ging das Fenster zu, statt den Suchindex zu bauen.** Wer
  ein Archiv aus einer älteren Fassung öffnete, bekam die Frage »Jetzt
  aufbauen?« – und nach dem Klick auf *Ja* verschwand MailBurg
  kommentarlos. Kein Aufbau, keine Meldung.

  Zwei Ursachen. Während des Aufbaus ist absichtlich kein Archiv offen:
  Das eigene Handle muss weg, weil der Aufbau selbst in den Index
  schreibt. `ui/app.py` las das als »Archiv lässt sich nicht öffnen« und
  beendete das Programm. Und der Arbeitsfaden startete aus dem
  Konstruktor heraus, also bevor Qts Ereignisschleife lief – ein
  QThread liefert seine Signale dann an niemanden.

  Der zweite Punkt ist derselbe Fehler wie am 2026-08-28 beim ersten
  Abruf, und die Begründung stand seitdem zwei Zeilen weiter in
  derselben Datei.

  **Betroffen war genau der Weg, den nach einer Aktualisierung jeder
  geht.** Kein Test hatte ihn je genommen; geprüft war nur der Kern.
  Jetzt halten ihn drei Tests fest, darunter einer, der die Bedingung in
  `ui/app.py` selbst prüft – ein Test am Fenster allein hätte den Fehler
  nicht gefunden, denn das Fenster verhielt sich richtig. Geschlossen
  wurde es woanders.

- **Ein gescheiterter Indexaufbau meldete »Abruf gescheitert«.** Er lief
  in den Fehlerweg des Postabrufs: Der schaltete den Abrufknopf wieder
  ein und nannte einen Vorgang, der gar nicht lief. Jetzt sagt die
  Meldung, was ist – und dass die Mails davon unberührt sind.

## [1.0.0] – 2026-08-31

**Die erste Fassung, die sich fertig nennt.** Nicht, weil nichts mehr
fehlte – die Liste in [TODO.md](TODO.md) ist lang genug –, sondern weil
das, was da ist, im Alltag getragen hat: Ein Jahr Post durch die
Werkstatt, zwei laufende Archive, über 16.000 Mails unter Linux und der
durchgespielte Betrieb unter Windows.

**Was ausdrücklich noch nicht erprobt ist**, steht dort, wo man sich
dafür entscheidet, und nicht im Kleingedruckten: die Archivverschlüsselung
(neu in dieser Fassung), OAuth2 an echten Konten, der Windows-Dienst und
der Betrieb unter macOS. Für die drei Letzteren gilt dasselbe wie seit
jeher – MailBurg behauptet nichts, was niemand nachgeprüft hat.

### Hinzugefügt

- **Die Archivverschlüsselung.** Ein Archiv lässt sich mit einem Passwort
  anlegen — im Assistenten unter *Schutz*, auf der Kommandozeile mit
  `mailburg anlegen … --verschluesseln`. Verschlüsselt werden die Mails und
  das Journal, also alles, was im Archivordner liegt und was in eine
  Sicherung wandert. Anleitung:
  [docs/verschluesselung.md](docs/verschluesselung.md).

  **Auch die Dateinamen.** Sie waren der SHA-256 der Mail, und den kann
  jeder ausrechnen, der die Mail selbst hat: Der Inhalt wäre verschlüsselt
  und die Frage »liegt diese Nachricht im Archiv?« trotzdem beantwortet.
  Jetzt steht dort ein HMAC darüber.

  **Zwei Ebenen, damit ein Passwortwechsel möglich bleibt.** Die Daten
  hängen an einem zufälligen Archivschlüssel, der eingewickelt in
  `archive.json` liegt — einmal mit dem Passwort, einmal mit einem
  Notschlüssel. Hinge die Verschlüsselung direkt am Passwort, müsste ein
  Wechsel 700.000 Dateien neu schreiben, mitten darin ein Archiv, das halb
  dem alten und halb dem neuen Passwort gehört. So sind es ein paar hundert
  Byte, und `mailburg passwort aendern` ist in einem Augenblick durch.

  **Der Notschlüssel ist kein Beiwerk.** Ein Langzeitarchiv überlebt das
  Gedächtnis seines Besitzers — wer nach sieben Jahren eine Rechnung
  braucht, hat das Passwort von damals womöglich nicht mehr. 32 Zeichen zum
  Ausdrucken, ohne `I`, `O`, `0` und `1`: Die sind auf Papier nicht sicher
  zu unterscheiden. Er erscheint genau einmal.

  **Das Journal gehört mit darunter**, Zeile für Zeile. In ihm stehen
  Absender, Betreff, Postfach und Ordner jeder Mail; ein verschlüsseltes
  `mail/` neben einem lesbaren `meta/` wäre ein verschlossener Schrank mit
  einem Inhaltsverzeichnis an der Tür. Die Hash-Kette rechnet weiter über
  den Klartext und bleibt unverändert prüfbar.

  **scrypt statt Argon2id**, gegen den ursprünglichen Entwurf: scrypt steckt
  in `hashlib`. Ein Archivprogramm, das seine Daten in zwanzig Jahren noch
  aufbekommen soll, sollte für die Schlüsselableitung nichts brauchen, was
  man erst installieren muss.

  **Was nicht geschützt ist, steht überall dabei:** der Suchindex. Er liegt
  außerhalb des Archivs und enthält Betreff, Absender und Text im Klartext —
  anders könnte er nicht suchen. Für den Anlass, um den es geht (Sicherung
  in der Cloud, verlorene Platte, weitergegebener Ordner), genügt das, denn
  der Index wandert dort nicht mit. Wer den ganzen Rechner absichern will,
  verschlüsselt die Platte.

  Für Zeitplan und Dienst lässt sich das Passwort hinterlegen
  (`mailburg passwort hinterlegen`). Ein Abruf, der nachts um drei auf eine
  Eingabe wartet, ist der gefährlichste Fehlerfall des Programms: kein
  Krachen, nur Stille, bis Wochen später auffällt, dass nichts mehr
  archiviert wurde. Was das an Schutz kostet, steht in der Anleitung.

  **Nachträglich verschlüsseln geht nicht.** Der Umstieg führt über eine
  Sicherung in ein neues Archiv.

- **Die Server Edition.** Ein Archiv, auf das mehrere Menschen aus dem
  Firmennetz und über das Internet zugreifen — im Browser, lesend. Bis zu
  50 Zugänge, bis zu 60 Postfächer.

  **Die Zugänge liegen im Archiv, nicht neben dem Dienst.** Wer das Archiv
  sichert, sichert die Rechte mit; wer es auf einen anderen Server umzieht,
  nimmt sie mit. Andersherum wäre nach jedem Umzug offen, wer was sehen
  darf — und im Zweifel sieht dann jeder alles.

  **Die Rechteprüfung steht in der Abfrage, nicht dahinter.** Jede Suche
  bekommt eine SQL-Bedingung mitgegeben, die auf die erlaubten Postfächer
  einschränkt. Nachträglich filtern wäre der bequemere Weg und der falsche:
  Trefferzahlen, Statistiken und Postfachlisten entstünden dann aus dem
  ganzen Archiv, und schon die Zahl »191 Treffer« verriete, dass es Post
  gibt, die man nicht sehen darf. Ein Test wacht darüber, dass keine neue
  lesende Methode ohne Sicht auskommt.

  Dazu: Zugänge auf der Kommandozeile und in einem eigenen Fenster,
  Passwörter ohne Schlüsselbund (verschlüsselter Tresor, Hauptschlüssel per
  `LoadCredential=` oder Umgebung), systemd-Dienst, Windows-Dienst
  (geschrieben, noch nicht gelaufen), Anmeldung mit Sperre nach zu vielen
  Fehlversuchen, dieselbe ausführliche Suchmaske wie im Fenster, Anhänge
  einzeln herunterladbar, und eine Leiste, die zeigt, über welche
  Postfächer man überhaupt suchen kann.

  Alles davon steht in `docs/server.md` und `docs/server-einrichten.md`,
  samt der Frage, wie man von außerhalb herankommt — mit Vor- und
  Nachteilen der Wege, nicht nur mit einer Empfehlung.

- **Der Gesprächsverlauf.** Ging eine Sache mehrmals hin und her, zeigt
  MailBurg jetzt den ganzen Austausch: in der Vorschau als Zeile
  (*Gespräch: 7 Nachrichten – erste vom …, letzte vom …*), im Browser als
  anklickbare Liste unter der Nachricht.

  **Zusammengehalten über die Kopfzeilen, nicht über den Betreff.** Jede
  Antwort trägt in `References` die Kennungen ihrer Vorgänger; die erste
  davon ist die Wurzel des Gesprächs, und alles mit derselben Wurzel gehört
  zusammen. Der Betreff taugt dafür nicht — er wechselt im Verlauf (»Re:«,
  »AW:«, »Fwd:«), und zwei Mails mit »Rechnung« im Betreff haben meistens
  nichts miteinander zu tun. Am Testarchiv belegt: Von vier Mails mit dem
  Betreff »Angebot« sind drei verkettet; der Verlauf findet genau diese
  drei und lässt die vierte in Ruhe.

  Die Kennungen stehen mal mit spitzen Klammern in der Mail und mal ohne.
  Wer sie so übernimmt, wie sie kommen, baut Verläufe, die nie
  zusammenfinden — sie werden deshalb einheitlich abgelegt.

  **Ein Verlauf ist nie garantiert vollständig.** Was nie ins Archiv kam,
  fehlt auch hier, und wer über den Server nur einen Teil der Postfächer
  sehen darf, sieht auch nur die Teile daraus. Beides steht dabei, im
  Browser wie im Handbuch: Aus »da steht nichts« darf niemand auf »da war
  nichts« schließen.

  **Bestehende Archive brauchen einen `mailburg neuaufbau ARCHIV` — und
  öffnen sich vorher nicht.** Die Angaben stehen in jeder Mail, wurden bis
  0.12 aber nicht in den Suchindex übernommen.

  Die Spalte einfach leer nachzurüsten wäre der bequeme Weg gewesen und der
  gefährlichere: MailBurg zeigte dann Verläufe an, die nur aus den seither
  archivierten Mails bestehen — vollständig aussehend, tatsächlich halb.
  Lieber einmal deutlich im Weg stehen als dauerhaft still danebenliegen.

  Verloren ist nichts. Die Mails liegen bytegenau samt allen Kopfzeilen im
  Archiv; der Index ergibt sich daraus und sonst nirgendwoher. Die Meldung
  sagt das und nennt den Befehl, das Fenster bietet den Neuaufbau gleich an,
  und der Befehl selbst kommt auch dann noch an das Archiv heran, wenn sein
  Index veraltet ist — sonst verwiese die Meldung auf einen Weg, der am
  selben Fehler scheitert.

### Behoben

- **Ein Stromausfall mitten im Abruf sperrte das Archiv aus.** Bricht das
  Schreiben mitten in einer Journalzeile ab, bleibt eine halbe Zeile stehen.
  Der Docstring von `_scan_tail` behauptete seit jeher, die zu überspringen —
  der Code tat es nicht: `json.loads` warf, und das Archiv war überhaupt
  nicht mehr zu öffnen.

  Jetzt wird sie übersprungen *und aus der offenen Datei entfernt*. Ohne das
  Zweite wäre die Nachsicht eine Falle: Eine abgebrochene Zeile endet nicht
  auf einem Zeilenumbruch, der nächste Eintrag klebte an ihr fest, und aus
  einem verlorenen würden zwei — der zweite einer, den MailBurg für
  geschrieben hält.

  Die Nachsicht gilt nur der letzten Zeile. Eine kaputte mittendrin kann kein
  Absturz verursacht haben; dort soll es krachen.

- **Ein beschädigtes Journal warf einen Traceback.** Wer sein Archiv nicht
  mehr aufbekommt, denkt an Datenverlust und braucht als Erstes einen Satz
  dazu, wo seine Mails geblieben sind. Es gibt jetzt eine Meldung, die das
  sagt und den Weg über die Sicherung nennt.

- **Die Sperrdatei blieb liegen, wenn das Journal beim Öffnen scheiterte.**
  Derselbe Fehler wie tags zuvor beim Index, an derselben Stelle: Ein
  `__init__`, das fliegt, hinterlässt kein Objekt, und niemand ruft mehr
  `close()`. Aus einem Problem wurden zwei, das zweite ohne erkennbaren
  Grund. Der Bereich umfasst jetzt beides.

### Geändert

- **Ein Datum sieht überall gleich aus: deutsch.** Bisher kam das Format
  aus den Systemeinstellungen, während das übrige Programm fest deutsch
  spricht — heraus kam »Weiter« neben »8/24/2026«, auf einem Bauserver ohne
  Spracheinstellung »24 08 2026«. Die Umrechnung liegt jetzt an einer
  einzigen Stelle (`core/sprache.py`), die Fenster und Browser gemeinsam
  benutzen.

## [0.12.0] – 2026-08-31

### Hinzugefügt

- **Ein eigenes Wappen für die Server Edition.** Dieselbe Burg in Rot, mit
  dem Wort SERVER über dem „urg" von Burg — kantenbündig mit ihm und nicht
  höher als das „B", so dass beide zusammen einen Block ergeben.

  Wer ein Bild sieht, soll auf einen Blick wissen, ob er den Arbeitsplatz
  oder den Server vor sich hat, und trotzdem dieselbe Burg erkennen.
  Erzeugt wird es aus der Desktop-Fassung durch `werkzeuge/server_logo.py`,
  nicht daneben gezeichnet: Zwei getrennt gepflegte Zeichnungen liefen
  auseinander, sobald jemand am Original etwas verschiebt.

  Die Leitfarbe ist das `ROT` der Palette, kein eigener Ton. Zwei Rot, die
  sich um Nuancen unterscheiden, wären schlimmer als eines. Das hat einen
  Preis: In der Weboberfläche steht die Marke dann in derselben Farbe wie
  Fehlermeldungen — die müssen dort über die Form kenntlich sein, nicht
  über die Farbe allein.

- **„In Mailprogramm öffnen".** Der dritte und kürzeste Weg aus dem
  Archiv, neben dem Zurücklegen ins Postfach und dem Speichern als Datei:
  Rechte Maustaste auf eine Nachricht, und sie geht in Thunderbird,
  Outlook oder Apple Mail auf. Verändert wird dabei nichts.

  Der heikle Teil ist nicht das Öffnen, sondern die Datei, die dafür
  entsteht. Eine `.eml` ist die vollständige Nachricht — Text, Anhänge,
  Adressen. Im allgemeinen Temp-Verzeichnis dürfte auf einem gemeinsam
  genutzten Rechner jeder mitlesen; sie liegt deshalb im Zwischenspeicher
  des Benutzerkontos, in einem Ordner, der nur ihm gehört.

  Und sie verschwindet wieder: was älter als vier Stunden ist beim
  nächsten Öffnen, der ganze Ordner beim Beenden von MailBurg. Sofort
  löschen ginge nicht — das Mailprogramm liest die Datei ja noch.

## [0.11.0] – 2026-08-30

### Hinzugefügt

- **Regeln, die eingehende Post von selbst einstufen.** Wer geschäftlich
  archiviert, bekommt private Post mit ins Archiv — den Verein, die
  Familie, den Handwerker für die eigene Wohnung. Sie unterliegt dort
  Aufbewahrungsfristen von sechs bis zehn Jahren, die für sie gar nicht
  gelten; umgekehrt verlangt die DSGVO, personenbezogene Daten zu löschen,
  sobald der Zweck entfällt.

  Eine Regel schaut auf Ordner, Absender oder Empfänger und bestimmt die
  Einstufung. Als Muster dienen `*` und `?`, nicht reguläre Ausdrücke:
  `*@verein.example` versteht jeder, und ein verunglückter regulärer
  Ausdruck kann alles treffen, ohne dass man es ihm ansieht.

  Drei Festlegungen bestimmen den Entwurf:

  **Beim Einstufen, nicht beim Abruf.** Geholt wird alles. Eine Regel, die
  schon das Holen verhindert, wirft weg, was sie trifft — und wer später
  merkt, dass sie zu weit griff, hat die Post verloren, falls sie im
  Postfach inzwischen gelöscht wurde. Eine falsche Einstufung lässt sich
  zurücknehmen.

  **Die erste passende gewinnt.** Nicht die schärfste, nicht die zuletzt
  angelegte. Das ist die einzige Regelung, die sich ohne Nachdenken
  vorhersagen lässt; wer eine Ausnahme braucht, schiebt sie nach oben.

  **Bestehende Post bleibt unangetastet.** Eine später angelegte Regel
  überfährt keine Einstufung, die jemand von Hand vorgenommen hat — sonst
  wöge eine bewusste Entscheidung weniger als ein Suchmuster. Wer
  nachstufen will, verlangt es ausdrücklich.

  Jede Anwendung steht im Journal, mit der Regel als Urheber statt eines
  Menschen. Jede Änderung an den Regeln ebenfalls: Welche Regel wann galt,
  gehört zur Verfahrensdokumentation.

  In der Oberfläche unter *Post → Beim Aufnehmen einstufen …*, auf der
  Kommandozeile als `mailburg regeln`. Erklärt in
  [docs/regeln.md](docs/regeln.md).

### Entfernt

- **Das Startbild der Windows-Fassung.** Es sollte die Stille beim Start
  überbrücken: Die `.exe` ist eine einzige Datei, Windows packt sie bei
  jedem Start aus, und in einer virtuellen Maschine dauerte das 20–25
  Sekunden ohne jedes Lebenszeichen.

  Auf echter Hardware startet MailBurg in wenigen Sekunden. Damit ist der
  Anlass weg — ein Bild, das aufblitzt und wieder verschwindet,
  verunsichert mehr als die Wartezeit, gegen die es antreten sollte.

  Dass es zuletzt ohnehin nur ein leeres Fenster zeigte, gab den Anstoß,
  war aber nicht der Grund. Wer es wieder aufgreift, findet die Spuren in
  `werkzeuge/mailburg.spec`.

### Behoben

- **Fehlermeldungen aus der Windows-Aufgabenplanung kamen mit zerlegten
  Umlauten an.** Zu sehen war: „Die Aufgaben-XML enth„lt einen
  unerwarteten Knoten." Der Satz stimmte, nur gelesen war er falsch.

  Konsolenprogramme unter Windows schreiben in der OEM-Codepage, in
  Deutschland cp850; dort ist „ä" das Byte 0x84. Python dekodiert ohne
  weitere Angabe jedoch in der ANSI-Codepage cp1252, und dort steht
  dasselbe Byte für ein Anführungszeichen.

  Betroffen war jede Meldung, die `schtasks.exe` zurückgibt — also
  ausgerechnet die Sätze, die jemand lesen soll, wenn etwas schiefging.
  Wo MailBurg ein fremdes Programm im Textmodus ausliest, gibt es die
  Kodierung jetzt ausdrücklich an. Und einen Notausgang für unerwartete
  Bytes: Ohne ihn wirft ein einzelnes davon einen Programmabbruch mitten
  im Einrichten eines Zeitplans, statt eine Meldung anzuzeigen.

- **Der Sicherungsdialog überschrieb stillschweigend die eigene
  Einstellung.** Er las zurück, *ob* gesichert wird und *wohin* — nicht
  aber, wie oft und wie viele Stände. Beim Öffnen stand deshalb immer
  „täglich" und „immer dieselbe Datei ersetzen" da, unabhängig davon, was
  tatsächlich eingerichtet war.

  Wer darin etwas anderes änderte — den Zielordner etwa — und auf
  Übernehmen ging, schrieb den Zeitplan mit diesen Vorgaben neu. Aus
  „monatlich mit zwei Ständen" wurde ein tägliches Überschreiben
  derselben Datei: aus zwei Sicherungsständen einer, ohne Meldung, ohne
  Nachfrage. Aufgefallen wäre das erst, wenn jemand eine Sicherung
  gebraucht hätte, die es nicht mehr gibt.

  Gelesen wird jetzt beides, unter Linux aus `OnCalendar` und der
  Befehlszeile des Dienstes, unter Windows aus der Aufgabe. Steht dort
  eine Zahl, die der Dialog nicht anbietet — von Hand eingetragen —,
  kommt sie zur Auswahl hinzu, statt auf die Vorgabe zu fallen.

- **Auf einem Bild in der Anleitung stand der Sicherungsordner des
  Entwicklers** — mitsamt seinem Namen darin. Das Bilderwerkzeug setzt
  jedem Fenster erfundene Daten vor, aber der Zeitplandialog fragt das
  Betriebssystem, was eingerichtet ist. Er bekommt jetzt ebenfalls einen
  erfundenen Zustand.

  Die eingebaute Selbstkontrolle hatte es nicht gefunden: Sie suchte nach
  Namen großer Mailanbieter, nicht nach Pfaden. Sie kennt jetzt auch den
  Namen dessen, der die Bilder gerade erzeugt — ermittelt beim Lauf, damit
  er nicht im Repo stehen muss, um aus dem Repo herausgehalten zu werden.
  Und sie liest jetzt auch `.webp`; die von Hand aufgenommenen
  Windows-Bilder waren ihr bis dahin entgangen.

- **Windows zeigte Pfade in einer Schreibweise, die es selbst nirgends
  verwendet.** Wer im Sicherungsdialog über „Auswählen …" einen Ordner
  heraussuchte, bekam `C:/Users/…` zu sehen statt `C:\Users\…` — Qt gibt
  Pfade immer mit Schrägstrich zurück. In den übrigen Auswahlfeldern fiel
  es nicht auf, weil der Pfad dort erst durch `pathlib.Path` geht, dessen
  `str()` von sich aus die Trennzeichen des laufenden Systems setzt. Auf
  die Funktion hatte es keine Auswirkung; es ging allein darum, was
  dastand.

- **»1 Mails im Archiv«** stand in der Statuszeile, sobald genau eine Mail
  darin lag — bei einem frisch angelegten Archiv also immer, an der
  Stelle, an der ein neuer Anwender zum ersten Mal nachsieht. Dieselbe
  Fallunterscheidung fehlte beim Einstufen („1 Mails werden geändert. Sie
  sind dann acht Jahre geschützt"), bei den Fristen, beim Einlesen einer
  Sicherung und auf der Abschlussseite des Assistenten („1 Postfächer sind
  eingerichtet"). Die Zahlwörter liegen jetzt an einer Stelle, die auch die
  Kommandozeile benutzt.

- **»Das Archiv liegt in None«** auf der letzten Seite des Assistenten. Der
  Pfad darf leer sein; ein durchgereichtes Python-`None` durfte trotzdem
  nicht auf dem Bildschirm landen. Auf demselben Bild stand außerdem
  „0 Postfächer sind eingerichtet“, obwohl der Schritt davor drei zeigte —
  das Bilderwerkzeug rief die Seiten einzeln auf, statt sie der Reihe nach
  zu durchlaufen.

- **Ein Bild in der Windows-Anleitung zeigte etwas anderes als seine
  Beschreibung** — angekündigt war die Abschlussseite des Assistenten, zu
  sehen war der Willkommensbildschirm. Beim Aufnehmen war dasselbe Fenster
  zweimal gespeichert worden.

### Geändert

- **Der Sicherungsdialog schlägt jetzt einen Ordner vor.** Wer das Häkchen
  bei der regelmäßigen Sicherung setzte und auf „Übernehmen" ging, bekam
  „Bitte einen Ordner für die Sicherungen wählen" — eine Fehlermeldung für
  einen leeren Zustand, den der Dialog selbst hergestellt hatte.

  Vorgeschlagen wird zuerst ein Cloud-Ordner, dann eine externe Platte,
  dann ein anderes Laufwerk. Der Benutzerordner nie: Er liegt auf derselben
  Platte wie in aller Regel das Archiv. Findet sich gar nichts auf einer
  anderen Platte, bleibt das Feld leer — eine Sicherung neben dem Original
  geht mit ihm zusammen verloren, und ein Vorschlag, der dem
  fettgedruckten Rat direkt darunter widerspricht, wäre schlimmer als
  nichts. Eine bereits getroffene Wahl wird nie überschrieben.

- **Die Doku nannte Abrufabstände, die es nicht gibt.** In
  `zeitsteuerung.md` stand „Wählbar sind 10, 30, 60 oder 90 Minuten", in der
  Übersichtsgrafik „alle 10–90 Minuten". Tatsächlich stehen in der
  Oberfläche alle 15 Minuten, alle 30 Minuten, stündlich, alle 4 Stunden und
  einmal am Tag zur Wahl — weder 10 noch 90 kamen je vor. Die Angaben
  stammten aus einem früheren Entwurf. Ein Test vergleicht die Doku jetzt
  mit der tatsächlichen Liste.

- **»? (2)« im Fristendialog** stand für Mails, deren Datum sich nicht lesen
  ließ — wer es sah, wusste nicht, ob das Programm etwas nicht konnte oder ob
  es ein Jahr gibt, das so heißt. Jetzt steht dort „ohne Datum", am Ende der
  Aufzählung statt alphabetisch zwischen den Jahren.

- **Die Bilder in der Anleitung haben Beschreibungen bekommen.** Vorher
  stand als Alternativtext meist nur eine Überschrift — „Willkommen“,
  „Fertig“, „Handbuch“. Ein Vorleseprogramm gab damit nichts von dem
  wieder, was auf dem Bild steht. Ein Test achtet jetzt darauf, und
  gleichzeitig darauf, dass kein eingebundenes Bild fehlt und keines
  unbenutzt herumliegt.

- **Das im Dialog eingetippte Passwort ging verloren** — und daraus wurde
  eine Sackgasse. In der Postfachliste blieb das Feld leer; beim
  Weitergehen kam „Für dieses Postfach fehlt noch das Passwort" mit den
  Knöpfen *Erneut versuchen* und *Dieses Postfach auslassen*. Wer
  auslassen wählte, bekam „Kein Postfach gewählt" und kam ebenfalls nicht
  weiter; wer ankreuzte, landete wieder bei der Passwortfrage.

  Ursache war eine Methode, die die angelegte Zeile nicht zurückgab —
  der Aufrufer hatte damit nichts, wohin er das Passwort hätte schreiben
  können.

- **»Ohne Prüfung übernehmen« stand schon vor dem Verbindungstest da.**
  Solange „Übernehmen" ausgegraut ist, war er der einzige anklickbare Weg
  nach vorn — und damit lag der ungeprüfte Weg näher als der geprüfte. Er
  erscheint jetzt erst nach einem gescheiterten Versuch; wer den Test
  nicht bestehen kann, sieht vorher, woran es liegt.

- **Ein Archiv ohne Postfach ließ sich nicht anlegen.** Der Assistent
  bestand auf mindestens einem und begründete das mit „Ohne Postfach gibt
  es nichts zu archivieren". Das stimmt nicht: Wer ein Archiv anlegt, um
  ein Thunderbird-Profil oder eine Sicherung hineinzulesen, braucht
  keins. Jetzt fragt MailBurg statt zu verbieten — mit „Nein" als
  Vorgabe, damit niemand versehentlich durchrutscht.

- **Ein umbenannter IMAP-Ordner wurde zweimal geführt.** Wird aus
  „Kunden" ein „Kunden 2025", war der Höchststand für den neuen Namen
  null: Der ganze Ordner wurde erneut durchlaufen, jede Mail bekam einen
  zweiten Fundort, und im Ordnerbaum stand der alte Name als Geist
  weiter. Verloren ging dabei nichts — die Ablage ist inhaltsadressiert,
  doppelt lag keine einzige Datei —, aber das Journal wuchs ohne Not: bei
  einem Ordner mit fünftausend Mails um fünftausend Einträge.

  Erkannt wird es an der `UIDVALIDITY`, die beim Umbenennen gleich
  bleibt. Nur bei genau einem verschwundenen und genau einem neuen
  Ordner — zwei Ordner können dieselbe Kennzahl tragen, und ein falsch
  zusammengeführter Ordner wäre schlimmer als ein doppelt gelesener.

### Hinzugefügt

- **Anmeldung per OAuth2.** Microsoft nimmt seit dem 16. September 2024
  (private Konten) beziehungsweise 1. Oktober 2022 (Exchange Online) kein
  Passwort mehr an — auch kein App-Kennwort. Ohne OAuth2 ließen sich diese
  Postfächer überhaupt nicht abrufen.

  Über `mailburg konten anmelden` oder den Knopf **Anmelden …** in der
  Postfachverwaltung. Der Browser öffnet sich, danach erneuert MailBurg
  den Zugriff selbsttätig — auch beim Abruf im Hintergrund.

  **MailBurg bringt keine eigene Anwendungskennung mit.** Google verlangt
  für den vollen Postfachzugriff ein jährlich zu wiederholendes
  Sicherheitsaudit durch ein zugelassenes Labor; für ein quelloffenes
  Programm ohne Einnahmen ist das nicht tragbar. Sie registrieren deshalb
  eine Anwendung auf Ihren Namen — bei Microsoft kostenlos und in fünf
  Minuten. Die Anleitung dazu ist [docs/oauth2.md](docs/oauth2.md).

  Öffentlicher Client mit PKCE, kein Geheimnis: Ein Programm auf fremden
  Rechnern kann nichts geheim halten. Die Marken liegen im Schlüsselbund,
  nie in einer Datei — ein Erneuerungs-Token ist auf Monate hinaus ein
  Vollzugang zum Postfach.

  **Ungeprüft an einem echten Konto.** Der Ablauf ist gegen einen
  nachgebauten Anbieter durchgespielt, PKCE gegen RFC 7636 gegengerechnet
  — aber niemand hat sich damit bisher bei Microsoft oder Google
  angemeldet. Wer der erste ist: Rückmeldung erwünscht.


- **Entwurf einer Verfahrensdokumentation nach GoBD.** Über *Archiv →
  Verfahrensdokumentation …* oder `mailburg verfahrensdoku`. MailBurg
  füllt, was es selbst weiß — Fassung, Ablageort, Verfahren, Postfächer,
  Zeitpläne, Bestandszahlen. Alles Organisatorische bleibt als sichtbare
  Lücke stehen, mit `[BITTE ERGÄNZEN]` ausgezeichnet.

  Das ist Absicht: Eine Dokumentation, die vollständig aussieht und es
  nicht ist, wäre schlimmer als gar keine — sie fällt erst in der Prüfung
  auf, und dann ist keine Zeit mehr. Im Text steht deshalb auch, was
  MailBurg *nicht* leistet: dass keine Software GoBD-konform sein kann
  und dass die Hash-Kette neu berechenbar ist, wer Zugriff auf das
  Archiv hat.

- **Auskunft nach Art. 15 DSGVO.** Fragt jemand, was über ihn gespeichert
  ist, stellt MailBurg alle Nachrichten zusammen, in denen er vorkommt,
  und packt sie als ZIP — mit einem Begleitblatt, das Herkunft, Zeitraum
  und Verarbeitungszweck nennt. Über *Archiv → Auskunft nach DSGVO …*
  oder `mailburg auskunft`.

  **Herausgegeben wird von einem Menschen.** Zwei Dinge kann kein
  Programm entscheiden, und beide stehen deshalb im Begleitblatt: In
  denselben Nachrichten stehen oft Daten Dritter — Adressen im
  Verteiler, Namen im Text, Unterschriften in Anhängen —, und nach
  Art. 15 Abs. 4 darf die Kopie deren Rechte nicht beeinträchtigen. Und
  gesucht wird nach genau einer Adresse; wer unter mehreren schreibt,
  taucht nur unter der gesuchten auf.

  Kein PDF, sondern `.eml`: Eine Mail als PDF zu drucken heißt, sie zu
  verändern — Anhänge fallen weg, Kopfzeilen verschwinden. Der Vorgang
  wird im Journal vermerkt, weil Art. 5 Abs. 2 verlangt, dass der
  Verantwortliche die Einhaltung nachweisen kann.

- **Einmal im Jahr fragt MailBurg nach abgelaufenen Fristen.** Ab dem
  1. Mai, und nur einmal je Kalenderjahr. Nicht ab dem 1. Januar, wenn
  die Fristen ablaufen: Eine Meldung, die bei jedem Öffnen erscheint,
  wird nach der dritten Wiederholung weggeklickt, ohne gelesen zu werden
  — und dann auch beim vierten Mal, wenn es darauf ankäme. Im Januar
  steckt man ohnehin im Jahresabschluss, und ob eine Betriebsprüfung den
  Ablauf hemmt, weiß man im Frühjahr eher.

  **Auch im Privatarchiv, dort aber mit anderem Ton.** Es gibt keine
  Fristen, also zeigt MailBurg nur, was älter als zehn Jahre ist, und
  sagt ausdrücklich dazu, dass Alter kein Grund zum Löschen ist. Bei
  privater Post sagt das Datum wenig darüber, was einem wichtig ist —
  eine Nachricht von jemandem, den es nicht mehr gibt, wiegt schwerer
  als die von gestern.

  Zehn Jahre und nicht sechs: Sechs ist die Handelsbrieffrist und hat in
  einem Privatarchiv nichts zu suchen. Post von vor sechs Jahren ist oft
  noch in Gebrauch — Versicherungspolicen, Garantien, Kaufbelege.

  Dazu `mailburg faellig` für dieselbe Auskunft auf der Kommandozeile.
  Gelöscht wird in keinem Fall etwas von selbst.

- **Aufbewahrung festlegen, aus der Trefferliste heraus.** *Post →
  Aufbewahrung festlegen …* ordnet die gerade gefundenen Mails ein. Das
  Fenster zeigt vorher, wie viele betroffen sind und was die Wahl
  bedeutet — „8 Jahre lang vor dem Löschen geschützt" statt bloß
  „Buchungsbeleg". Nur im Geschäftsarchiv; ein Privatarchiv kennt keine
  Fristen, und ein Menüpunkt, der dort nichts bewirkt, wäre eine
  Einladung, sich über etwas Gedanken zu machen, das keine Rolle spielt.

- **`mailburg einstufen` ordnet Mails aufbewahrungsrechtlich ein.** Das
  Rechenwerk stand seit dem 25. August und war getestet — aber es gab
  keinen Weg, einer Mail eine Kategorie *zuzuweisen*. Der Index hatte die
  Spalte, die Suche kannte `kategorie:`, die Löschsperre fragte sie ab,
  und niemand konnte sie setzen.

  Eingestuft wird über einen Suchausdruck, nicht Mail für Mail: Wer ein
  Archiv einordnet, hat hunderte Belege vor sich. „Alles von der
  Steuerkanzlei ist Buchungsbeleg" ist eine Regel, die sich schreiben
  lässt. Ohne `--wirklich` wird nur gezeigt, was geschähe — eine
  Einstufung verlängert Fristen und lässt sich nicht formlos zurücknehmen.

  Jeder Vorgang wandert als `classify` ins Journal, mit vorheriger und
  neuer Kategorie: Für ein Geschäftsarchiv ist „wer hat wann was wozu
  erklärt" Teil der Verfahrensdokumentation.

  Die Wirkung ist belegt: Eine Mail von Anfang 2019 in einem deutschen
  Geschäftsarchiv ist als Buchungsbeleg bis Ende 2027 gesperrt, als
  Handelsbrief bereits frei, als privat jederzeit löschbar.

### Geändert

- **Menüpunkte, die nur zu einer Archivart passen, sind ausgegraut statt
  ausgeblendet.** Ein verschwundener Eintrag lässt niemanden wissen, dass
  es die Funktion gibt — wer sie einmal braucht, sucht sie im falschen
  Programm. Ein grauer Eintrag zeigt sie und sagt im Statustext, warum er
  hier nicht gilt.

- **`[oberflaeche]` bringt jetzt den Schlüsselbund mit.** Wer nur die
  Oberfläche installierte, bekam ein Programm, das Postfächer einrichten
  und abrufen kann, aber kein Passwort behält — `keyring` steckte allein
  im Zusatz `imap`. Ein Assistent, der nach Passwörtern fragt und sie dann
  vergisst, ist schlimmer als einer, der gar nicht erst fragt.

  Die Meldung dazu unterscheidet nun auch die beiden Ursachen: fehlendes
  Paket oder fehlender Speicher auf diesem System. »Auf diesem Rechner ist
  kein Schlüsselbund erreichbar« war im ersten Fall falsch — der Rechner
  hat einen, MailBurg wurde nur ohne den passenden Zusatz installiert.

- **Die Zusätze stehen jetzt in der Anleitung.** Weder `[oberflaeche]` noch
  `[imap]` wurden irgendwo erwähnt; wer nicht `install.sh` benutzte, kam
  von selbst nicht darauf.

- **`mailburg konten zuordnung` zeigt Archivnamen statt Kennungen** und
  gruppiert nach Archiv. Vorher stand je Postfach eine Zeile mit
  `c89fdf58-7ec8-4804-af89-915b71440b7b` – für einen Menschen keine
  Information. Die Frage lautet »was landet in meinem Geschäftsarchiv?«,
  und genau diese Zuordnung entscheidet über zehnjährige
  Aufbewahrungsfristen.

### Behoben

- **Eine Sicherung an den falschen Ort blieb unbemerkt.** Schreibt der
  Zeitplan nach `/mnt/…/Storage-Box/` und ist das ein Einhängepunkt ohne
  eingehängten Datenträger, dann existiert der Ordner trotzdem – leer, auf
  der Systemplatte. MailBurg legte den Rest mit `mkdir -p` an, packte
  hinein und meldete Erfolg. Aufgefallen wäre das erst, wenn man die
  Sicherung braucht; bis dahin läuft der Zeitplan Monat für Monat.

  MailBurg legt jetzt eine Marke (`.mailburg-sicherungsziel`) im
  Zielordner ab. Fehlt sie in einem leeren oder fehlenden Ordner, bricht
  der Zeitplan ab, statt ins Leere zu schreiben – mit Rückgabewert 1,
  damit systemd und die Aufgabenplanung den Fehlschlag zeigen. Von Hand
  gestartet darf weiterhin angelegt werden: Wer danebensteht, richtet
  gerade ein. Ordner mit vorhandenen Sicherungen werden nicht abgewiesen,
  sondern nachträglich ausgezeichnet.

- **Eine verschwundene Platte endete in einem Python-Traceback.** Wird
  eine externe Platte abgezogen, während MailBurg schreibt, sah der
  Anwender einen Wall aus Zeilen — ohne Antwort auf die einzige wichtige
  Frage: Ist mein Archiv jetzt kaputt?

  Es ist nicht kaputt, und das steht jetzt dort. Nachgestellt wurde es
  mit einem Import von 3.000 Mails, mitten im Lauf unterbrochen: 1.000
  Mails abgelegt, Hash-Kette unversehrt, Journal und Ablage stimmen
  überein. Die Reihenfolge Ablage → Journal → Index hält.

- **»Nicht auf dieselbe Platte wie das Archiv« war nur ein Ratschlag.**
  Der Satz stand im Einrichtungsfenster, geprüft wurde er nie. Jetzt sagt
  MailBurg es, wenn Sicherung und Archiv auf demselben Datenträger lägen.
  Kein Abbruch – es gibt Aufbauten, in denen das gewollt ist.

## [0.10.0] – 2026-08-28

### Hinzugefügt

- **Die Suche kennt jetzt deutsche Schreibweisen.** »Bahnhofstrasse« findet
  »Bahnhofstraße«, »mueller« findet »Müller«. Bisher nicht: Der Index legt
  Wörter zwar ohne Umlautpunkte ab, weshalb »muller« schon immer »Müller« fand
  – aber das **ß** blieb stehen, und die Umschreibung mit e war ihm fremd.

  In der Schweiz gibt es überhaupt kein ß, dort schreibt jeder »ss«. Bei einem
  Programm, das Aufbewahrungsfristen für DE, AT *und* CH kennt, ist das keine
  Kleinigkeit.

  Lösen lässt sich das nicht im Index – SQLite kann es nicht. Die Suchanfrage
  fächert deshalb selbst auf: aus `strasse` wird `strasse OR straße`. Dass
  dabei auch Unsinn entsteht (aus »Steuer« wird »Steür«), schadet nicht: Solche
  Varianten finden schlicht nichts.

  Groß- und Kleinschreibung war und ist der Suche gleichgültig, auch bei
  Umlauten.

- **Der regelmäßige Abruf lässt sich jetzt auch unter Windows einstellen.**
  Bisher stand dort ein grauer Kasten: „Unter Windows richtet MailBurg den
  regelmäßigen Abruf noch nicht selbst ein." Wer die Windows-Fassung benutzt,
  musste also täglich von Hand abrufen – und ein Archiv, das man von Hand
  füttern muss, wird nach zwei Wochen nicht mehr gefüttert. Dann fehlt Post,
  und gemerkt hat es niemand.

  MailBurg legt nun eine Aufgabe im Ordner „MailBurg" der
  Windows-Aufgabenplanung an, je Archiv eine eigene. Ohne Verwaltungsrechte,
  sichtbar und löschbar wie jede andere Aufgabe. Dasselbe gilt für die
  regelmäßige Sicherung.

  Der Umweg über eine XML-Beschreibung statt über die Schalter von `schtasks`
  hat einen Grund: Nur so lässt sich `StartWhenAvailable` setzen – das
  Gegenstück zu systemds `Persistent=true`. Ohne das fällt eine tägliche
  Sicherung schlicht aus, wenn der Rechner zur fraglichen Zeit ausgeschaltet
  war, und zwar stillschweigend.


- **Die Farbpalette steht jetzt geschrieben** – in `assets/farben.md` zum
  Nachlesen und in `mailburg/farben.py` als Werte, samt Kontrastrechnung nach
  WCAG 2.1. `tests/test_farben.py` prüft die Paarungen, die tatsächlich
  vorkommen. Beide Dateien sind zum Kopieren in andere Projekte gedacht; diese
  Palette gilt seit dem 2026-08-28 für alle.
- **`GRAU_LEISE` (`#667080`)** für zurückgenommenen Text auf hellem Grund.
  `GRAU_MITTE` (`#97a1ad`) taugt nur auf dunklem – siehe oben.


- **Hilfe → Info** nennt Urheber, Fassung und die Wege für
  Fehlermeldungen.
- **Dokumente mit auffällig wenig Text** werden nach der Erkennung
  benannt. Erledigt heißt nicht gelesen.
- **`texterkennung --nochmal`** versucht aufgegebene Dokumente erneut –
  nötig, wenn die Erkennung selbst besser geworden ist.
- **Beim Öffnen eines Archivs** steht die jüngste Nachricht oben.



- **`mailburg konten zuordnen` und `mailburg konten zuordnung`** –
  Postfächer einem Archiv zuweisen und die Zuordnung ansehen.
- **`mailburg loeschen`** nimmt Mails eines Postfachs wieder aus dem
  Archiv. Der Trockenlauf ist die Voreinstellung, und entfernt wird nur,
  was ausschließlich an diesem Postfach hängt.

- **Derselbe Anhang wurde mehrfach durch die Texterkennung geschickt.**
  Ein Vertrag, der weitergeleitet und mehrfach beantwortet wurde, hängt
  an vielen Mails – aber es ist ein einziges Dokument. Am Geschäftsarchiv
  gemessen: 222 gelesene Dokumente mit 986 Seiten, davon 153 Dokumente
  mit 691 Seiten Abschriften. Siebzig Prozent der Rechenzeit. Verglichen
  werden jetzt die Bytes des Anhangs, und zwar über Läufe und Archive
  hinweg; in den Suchindex kommt der Text trotzdem für jede Mail einzeln.

- **Im Fortschrittsfenster fehlte Text.** Ein umbrechendes Etikett meldet
  Qt eine Höhe, die für eine angenommene Breite gilt, nicht für die
  tatsächliche. Sobald der Fortschrittsbalken Platz verlangte, nahm sich
  das Layout ihn beim Absatz darüber – der Text war nicht abgeschnitten,
  sondern weg.


- **`mailburg vorrat`** macht schon erkannten Text für künftige Läufe
  nutzbar. Für Bestände, die vor der Dublettenprüfung erkannt wurden:
  Der Text ist da, aber unter dem Schlüssel der Mail statt dem des
  Dokuments. Erkannt wird nichts neu.

### Geändert

- **Der Erkennungsdialog verspricht keine Dauer mehr.** Die Angabe war
  aus zwölf Sekunden je Dokument hochgerechnet; die Rechenzeit hängt aber
  an der Seitenzahl, und die sieht man einem PDF von außen nicht an. Eine
  Schätzung, die um ein Vielfaches danebenliegt, legt nahe, es laufe
  etwas falsch, sobald es länger dauert.

### Behoben

- **Bei jedem Aufruf eines Hilfsprogramms blitzte unter Windows ein
  Konsolenfenster auf.** `pdftoppm`, `pdftotext` und `tesseract` sind
  Konsolenprogramme; startet eine Anwendung mit Fenster sie, öffnet Windows
  jedes Mal eine Konsole. Bei der Texterkennung geschieht das mehrfach je
  Seite – über die Dauer eines Laufs dutzende Fenster, die sich vor alles
  andere schieben. Wer das sieht, hält das Programm für kaputt.

- **Die gepackte `MailBurg.exe` kannte ihre eigene Kommandozeile nicht.** Jedes
  Argument wurde als Archivpfad gedeutet: `MailBurg.exe abrufen --leise
  C:\Archiv` öffnete ein Fenster mit dem Archiv »abrufen«, fand keines und
  blieb mit einem Fehlerdialog stehen. Das traf auch den eingerichteten
  Zeitplan — er hätte alle 30 Minuten ein Fenster geöffnet, statt Post zu
  holen.

- **Der erste Abruf lief nach der Einrichtung nicht an.** Auf der
  Abschlussseite steht „Jetzt den ersten Abruf starten", angekreuzt. Man
  klickt Fertig, das Hauptfenster geht auf – und das Archiv bleibt leer. Erst
  F5 holte die Post.

  `main()` rief den Assistenten zwar auf, fragte sein `soll_abrufen` aber nie
  ab. Über *Archiv → Neues Archiv* hat es die ganze Zeit funktioniert; nur der
  Weg beim allerersten Start – der einzige, den ein neuer Anwender überhaupt
  geht – war der ungeprüfte.

- **In der Postfachliste des Assistenten schwebte die Beschreibung in der
  Mitte.** Ohne Dehnung am Ende verteilt Qt den freien Platz gleichmäßig auf
  alle Zeilen; bei einem einzigen Postfach stand der Name oben und seine
  Serveradresse eine Handbreit darunter.

- **Serverfehler standen in der Sprache des Betriebssystems.** Wer sich im
  Servernamen vertippte, bekam „[Errno -2] Name or service not known" zu
  lesen. Vier Fälle decken fast alles ab, was beim Einrichten schiefgeht –
  Name falsch, Port falsch, Server antwortet nicht, Passwort stimmt nicht –,
  und jeder bekommt jetzt einen Satz, der sagt, wo man nachsehen muss. Die
  ursprüngliche Meldung bleibt sichtbar.

- **Die Beschriftungen in der Übersichtsgrafik waren zu blass zum Lesen.**
  `assets/uebersicht.svg` setzte neun Textstellen bei 11,5 bis 13 Pixeln in
  `#97a1ad` auf weißen Grund – das sind 2,6 Kontrast, verlangt sind 4,5. Die
  Kastenrahmen lagen mit demselben Wert unter den 3,0, die WCAG für grafische
  Elemente fordert. Text steht jetzt in `#667080` (5,0), Rahmen in `#7f8a99`
  (3,5).

  Aufgefallen ist das nicht beim Hinsehen. Solche Werte sieht man einem
  Farbton nicht an – sie kamen ans Licht, als die Palette in ein anderes
  Projekt übernommen und dort erstmals nachgerechnet wurde.


- **Scans mit riesigen Seitenmaßen blieben stumm.** Eine Seite aus der
  iPhone-Kamera-App misst 4507 × 6681 Punkte statt 595 × 842 – bei 300
  dpi wären das 523 Megapixel, woran tesseract erstickt, ohne einen
  Fehler zu melden. Die Auflösung richtet sich jetzt nach der
  Seitengröße; für A4 und A3 ändert sich nichts.
- **Passwortgeschützte PDF** gaben sich als »kein Text erkannt« aus. Ein
  Dokument, das nach einem Kennwort verlangt, ist nicht kaputt – es ist
  zu, und der Unterschied gehört in die Meldung.
- **Im dunklen Thema verschwammen die Bereiche.** Zwischen
  Fensterhintergrund und Inhaltsbereich liegt ein Kontrastverhältnis
  von 1,15 – kein Farbproblem, sondern eine fehlende Kante. Gezeichnet
  werden jetzt Rahmen in der Systemfarbe, für alle Fenster.
  Platzhaltertexte werden im Dunkeln aufgehellt.


- **Postfächer wurden in jedes Archiv geholt.** Die Kontenliste galt für
  das ganze Programm, das Archiv aber nicht: Jedes »Abrufen« holte alle
  eingerichteten Postfächer in das gerade geöffnete Archiv. Wer
  geschäftlich und privat trennt, bekam in beiden denselben Bestand. An
  einem echten Aufbau aufgefallen: Von 9.866 Mails in einem
  Geschäftsarchiv gehörten 176 dorthin – die übrigen waren private Post
  und lagen damit unter zehnjährigen Aufbewahrungsfristen.

  Ein Konto führt jetzt die Kennungen der Archive, in die es gehört.
  Eine leere Liste heißt »noch nicht zugeordnet«, nicht »überall«: Nach
  dem Update ruft zunächst nichts mehr ab, und beide Wege sagen deutlich,
  warum.

- **Ein Abruf-Zeitplan für alle Archive.** Derselbe Denkfehler, an
  derselben Stelle übersehen – für die Sicherung gab es längst eine
  Einheit je Archiv. Das Einrichten des zweiten Zeitplans überschrieb
  den ersten; danach wurde nur noch ein Archiv beliefert.

## [0.9.0] – 2026-08-26

Vollständig und im Alltag erprobt – aber auf genau einem System.

Der dritte Tag war der erste im echten Betrieb, und dabei kam ein
Dutzend Fehler zutage, die keine Testsuite gefunden hätte: ein
eingefrorenes Fenster, eine Prüfschleife, die den Mailserver mit
Anmeldungen überzog, eine Fenstergeometrie, die unter Wayland nie
gespeichert wurde, zwei Zahlen für dieselbe Sache. Alle brauchten einen
Menschen, der das Programm benutzt.

Deshalb 0.9.0 und nicht 1.0.0. Eine 1.0 ist ein Versprechen – *das ist
fertig, darauf kannst du bauen* –, und bei einem Archivprogramm wiegt
das schwerer als anderswo: Was nicht geholt wurde, fällt erst Jahre
später auf. Die 1.0 wartet, bis MailBurg auf einem Rechner läuft, den
nicht sein Autor eingerichtet hat.

**Erprobt an:** zwei Archiven mit zusammen 19.154 Mails, sieben
IMAP-Postfächern samt Proton Bridge, 12.436 Mails aus einer
Thunderbird-Sicherung, 310 Seiten Texterkennung, zwei Sicherungen à
2,3 und 1,8 GB samt geprüfter Rückholung.

- **Grafische Oberfläche.** Einrichtungsassistent, Hauptfenster mit
  Postfachbaum, Trefferliste und Vorschau, Suchmaske (Strg+F). Startbefehl
  `mailburg-gui`, Menüeintrag unter Büroprogrammen.
- **`mailburg abgleich`** belegt vor dem Aufräumen im Mailprogramm, dass alles
  vor einem Stichtag im Archiv liegt. Im Zweifel kein grünes Licht: Bei
  geändertem `UIDVALIDITY` oder einem Fehler bleibt der Befund offen.
- **Abruf im Hintergrund aus der Oberfläche.** Ankreuzfeld und Abstand von
  15 Minuten bis täglich, in der Abschlussseite und unter „Post → Abruf im
  Hintergrund …". MailBurg muss dafür weder geöffnet bleiben noch in den
  Autostart; nötig ist nur die Anmeldung, weil daran der Schlüsselbund hängt.
- **Bestand und letzter Abruf** stehen dauerhaft in der Statuszeile. Vermerkt
  wird erst ein durchgelaufener Abruf – ein Lauf, der an einem stummen Server
  scheitert, darf das Archiv nicht als aktuell ausweisen.
- **Taggenaue Suche** mit `seit:`, `bis:` und `am:`, wahlweise `26.08.2026`
  oder `2026-08-26`. Schrägstriche werden abgelehnt: `08/09/2026` ist hier der
  8. September und in den USA der 9. August, und diesen Irrtum bemerkt bei
  einer Suche im eigenen Archiv niemand.
- **Texterkennung für eingescannte PDF** über pdftoppm und tesseract, in
  Häppchen nach jedem Abruf statt in einem nächtlichen Lauf – nicht jeder lässt
  den Rechner über Nacht an.
- **Vorschlag statt Ausnahme bei Zertifikatsfehlern.** Läuft der Mailserver
  unter dem Namen eines Massenhosters, sieht MailBurg nach, für welchen Namen
  das Zertifikat gilt, und bietet ihn an. Danach ist die Verbindung vollständig
  geprüft – statt einer Ausnahme, die für immer bestehen bliebe.
- **Fenstergröße und Aufteilung** werden gemerkt, „Ansicht → Fenster auf
  Standard zurücksetzen" holt die Vorgabe zurück.

### Neu

- **Handbuch mit Kapiteln** (F1) statt zweier Meldungsfenster. Jeder Menüpunkt
  ist mit dem Wortlaut erklärt, mit dem er im Menü steht; ein Test liest die
  Punkte aus dem echten Menü, damit Programm und Handbuch nicht auseinander
  laufen.
- **Der Weg zurück.** Doppelklick auf eine Nachricht öffnet sie in einem
  eigenen Fenster. Über die rechte Maustaste lässt sie sich in den Posteingang
  eines frei gewählten Postfachs zurücklegen – auch in ein anderes als das
  ursprüngliche, denn das gibt es vielleicht nicht mehr – oder als
  `.eml`-Datei speichern. Zurückgelegt wird bytegenau, mit dem
  ursprünglichen Versanddatum und als ungelesen, damit die Nachricht im
  Mailprogramm auffindbar ist.
- **Sortierbare Trefferliste.** Klick auf den Spaltenkopf sortiert, nochmal
  klicken dreht um – sortiert wird im Index, nicht in der geladenen Liste.
  Ein ⇅ zeigt, welche Spalten sich sortieren lassen.
- **Postfächer lassen sich anordnen**, mit der Maus oder über Strg+Auf/Ab.
- **Bestand und letzter Abruf** stehen dauerhaft in der Statuszeile.
- **Kalender für den Zeitraum** in der erweiterten Suche.
- **[Postfach entlasten](docs/postfach-entlasten.md)** – die Anleitung zum
  eigentlichen Zweck: nachweisen, dass alles im Archiv ist, und erst dann beim
  Anbieter aufräumen lassen.


- **IMAP-Abruf.** Mails werden direkt aus dem Postfach geholt, für beliebig
  viele Konten. Das Postfach bleibt dabei unangetastet: Ordner werden nur
  lesend geöffnet (`EXAMINE`) und Mails mit `BODY.PEEK[]` geholt, damit
  ungelesene Post ungelesen bleibt.
- **Inkrementeller Abruf.** Nach dem ersten Lauf wird nur noch geholt, was
  dazugekommen ist. Der Höchststand wird nicht mitgeschrieben, sondern aus dem
  Archiv abgelesen – so ist ein Abbruch mitten im Ordner folgenlos. Ändert der
  Server seinen `UIDVALIDITY`-Wert, wird der Ordner vollständig neu gelesen.
- **Vormerkung gescheiterter Mails.** Eine Nachricht, an der sich MailBurg
  verschluckt, wird notiert und beim nächsten Lauf erneut angefordert. Ohne das
  zöge der Höchststand an ihr vorbei und sie fehlte für immer im Archiv, ohne
  dass es jemand bemerkte.
- **Kontenverwaltung** mit `konten liste`, `konten hinzufuegen`,
  `konten entfernen` und `konten pruefen`. Passwörter liegen im Schlüsselbund
  des Betriebssystems, nie in einer Konfigurationsdatei; in der Kontenliste
  steht nur, wo ein Postfach liegt und wie es heißt.
- **Ordnernamen im abgewandelten UTF-7** nach RFC 3501 werden aufgelöst, sodass
  aus `Entw&APw-rfe` wieder „Entwürfe" wird. Fremde Trennzeichen werden auf `/`
  vereinheitlicht.
- **Sonderordner bleiben draußen.** Papierkorb, Spamverdacht und Entwürfe nach
  Namen und nach den Merkmalen aus RFC 6154. Bei Gmail auch »Alle Nachrichten«,
  das sonst jede Mail ein zweites Mal ins Journal brächte.
- **Befehl `abrufen`**, geeignet für die Zeitsteuerung, mit `--konto`,
  `--ordner` und `--voll`.
- **64 weitere Tests**, darunter ein nachgebildeter IMAP-Server. Geprüft wird
  auch die Eigenheit aus RFC 3501, dass `UID n:*` immer mindestens die höchste
  UID liefert – wer das übersieht, holt bei jedem Lauf dieselbe Mail erneut.

- **Einrichtung mit einem Aufruf.** `install.sh` für Linux und macOS,
  `install.ps1` für Windows. Beide legen eine eigene Python-Umgebung im
  Benutzerverzeichnis an, richten den Befehl `mailburg` ein und brauchen keine
  Administratorrechte. `--zeitsteuerung` richtet den nächtlichen Abruf ein
  (systemd-Timer beziehungsweise Aufgabenplanung), `--entfernen` baut alles
  wieder ab – das Archiv bleibt dabei unangetastet.
- **`pyproject.toml`**, damit `pip install .` funktioniert und der Befehl
  `mailburg` entsteht. Der Kern bleibt ohne Fremdpakete; `keyring`, `pypdf` und
  `zstandard` sind Kür und einzeln zuschaltbar.
- **[docs/](docs/README.md)** mit Anleitungen zu Postfächern (samt
  App-Passwörtern der großen Anbieter), Zeitsteuerung auf allen drei Systemen
  und MailBurg unter Windows.
- **Die Einrichtung läuft in der CI wirklich durch**, auf Linux, Windows und
  macOS: einrichten, Archiv anlegen, wieder abbauen – und die Prüfung, dass das
  Abbauen das Archiv verschont.

### Geändert

- **Datumsangaben folgen der Systemsprache** statt dem Speicherformat. Die
  Trefferliste zeigte `2026-08-26`, die Vorschau darunter `25.08.2026`.
  Jahreszahlen bleiben dabei vierstellig – in einem Archiv stünden Post von
  1998 und Post von 2098 sonst beide als „98" da.
- **Die Postfachliste zeigt die Mailadresse** statt des frei gewählten Namens,
  samt Gesamtzahl je Postfach.
- **Übergangene Postfächer werden nicht mehr aufgezählt.** Der Hinweis nannte
  Mailadressen – eine Zeile, die man versehentlich mit einem Bildschirmfoto
  weitergibt, und was das Mailprogramm kennt, gehört nicht zwangsläufig hierher.

- `importieren()` übergibt dem Fehler-Rückruf jetzt die ganze Nachricht statt
  nur ihren Ordner. Der IMAP-Abruf braucht die UID, um die gescheiterte Mail
  vormerken zu können.

### Behoben

- **Mails, die nur als HTML vorliegen, wurden zur Textwurst.** Bei Proton ist
  das der Regelfall. Die Umwandlung nach Text fasste allen Leerraum zu
  Leerzeichen zusammen, Zeilenumbrüche eingeschlossen – richtig für den
  Suchindex, falsch für die Anzeige. Wirkt ohne Neuimport, weil die Vorschau
  die Nachricht ohnehin frisch aus den Rohdaten zerlegt.

- **Die Postfachliste addierte Fundorte statt Mails.** Bei Proton trägt jede
  Nachricht neben ihrem Ordner noch Etiketten, und jedes Etikett ist ein
  weiterer Fundort. Der Baum meldete 2.877, die Statuszeile 2.078 – eine der
  beiden Zahlen gab es nicht.

- **Die Spalten der Trefferliste standen nach dem Start zusammengedrängt.**
  Wiederhergestellt wurde ein gespeicherter Zustand, der auch die damalige
  Breite der Tabelle festhält; angewandt auf ein Fenster, das seine Größe
  noch nicht hat, ergibt das die Breiten von damals.

- **`archiviert:` nahm nur die ISO-Schreibweise**, obwohl Datumsangaben sonst
  der Systemsprache folgen.

- **Die Oberfläche fror bei der Einrichtung ein.** Die Anmeldeprobe lief
  richtig im Hintergrund, ihre Antwort wurde aber über ein Lambda
  entgegengenommen. Einem Lambda kann Qt keinen Faden zuordnen und ruft es
  deshalb sofort auf – im Arbeitsfaden. Die Zeilen darunter fassten Widgets an
  und öffneten Dialoge. Für den Anwender ließ sich das Fenster noch verschieben
  (das macht der Fenstermanager), aber innen ging nichts mehr: Ein modaler
  Dialog, im falschen Faden entstanden, schluckte jede Eingabe, ohne je
  sichtbar zu werden.

- **Die Kontenseite prüfte endlos im Kreis.** `validatePage` prüft nebenläufig,
  sagt deshalb erst Nein und schickt die Seite selbst weiter, sobald alle
  Antworten da sind – was `validatePage` erneut aufrief. Prüfen,
  weiterschicken, prüfen. Sichtbar als flackernde Zustandsspalte; unsichtbar
  bekam der Mailserver bei jedem Umlauf neue Anmeldungen.

- **Gescheiterte Verbindungen blieben offen.** Schlug die Anmeldung fehl, wurde
  die halbfertige Verbindung nie geschlossen – drei abgelehnte Anmeldungen,
  drei tote Verbindungen zum Server, die erst mit dem Programm verschwanden.

- **Wer einen Teil seiner Postfächer ausließ, kam nicht weiter.** Weitergehen
  war nur erlaubt, wenn *alle* gefundenen Postfächer eingerichtet waren – bei
  acht Postfächern und zweien, die man bewusst überspringt, also nie.

- **MailBurg fragte nach Passwörtern, die im Schlüsselbund lagen.** Ein
  eingerichtetes Postfach zeigt sein Passwort nicht im Eingabefeld; die Seite
  schaute nur aufs leere Feld und hielt es für vergessen.

- **Der Rat, die Sperrdatei zu löschen, kam auch während eines Abrufs.**
  Meistens hält sie kein Absturz, sondern der geplante Abruf im Hintergrund.
  Wer dem Rat folgte, hatte zwei Läufe gleichzeitig am selben Journal – genau
  das, wovor die Sperre schützt. Die PID stand längst in der Datei, sie wurde
  nur nicht ausgewertet.

- **MailBurg stand zweimal im Anwendungsmenü**, unter Büroprogrammen und unter
  Dienstprogrammen: zwei Hauptkategorien im Desktop-Eintrag.

- **Zustandsfarben waren im dunklen Thema kaum lesbar.** „Anmeldung
  gescheitert" erreichte ein Kontrastverhältnis von 2,7 statt der geforderten
  4,5 – ausgerechnet die Meldung, deren Übersehen bedeutet, dass ein Postfach
  stillschweigend nicht archiviert wird.

- **Das Merken des Archivs löschte die gemerkte Fenstergröße.** Die
  Einstellungsdatei wurde jedes Mal komplett neu geschrieben.

- **Unter Windows lief MailBurg überhaupt nicht.** Das Journal zwingt seine
  Einträge mit `fsync` auf die Platte und öffnete die Datei dafür nur lesend.
  POSIX erlaubt das, Windows nicht – dort scheiterte jeder Aufruf mit
  „Bad file descriptor". Weil schon das Anlegen eines Archivs dort vorbeikommt,
  war kein einziger Vorgang möglich. Aufgefallen ist es lange nicht, weil die
  CI zwar unter Windows lief, ihre roten Ergebnisse aber in einer Matrix aus
  dreizehn Jobs untergingen.

- **Die Sperrdatei konnte unlesbar werden.** Sie wird ausdrücklich als UTF-8
  gelesen, entstand aber in der Kodierung des Systems – cp1252 unter Windows,
  ASCII bei `LC_ALL=C`. Auf einem Rechner mit Umlaut im Namen ging damit der
  Hinweis verloren, wo das Archiv gerade geöffnet ist.

- **Der Verursacher einer Löschung fehlte unter Windows.** Der Grabstein las den
  Benutzernamen aus `$USER`; diese Variable gibt es nur unter Unix, unter
  Windows heißt sie `USERNAME`. Im Protokoll eines Geschäftsarchivs stand
  deshalb „unbekannt" – wer gelöscht hat, gehört dort aber hin. Jetzt über
  `getpass.getuser()`.

## [0.1.0] – 2026-08-25

Erste Fassung. Der Unterbau steht; Oberfläche und IMAP fehlen noch.

### Neu

- **Archivformat.** Ein Archiv ist ein Verzeichnis mit `archive.json`, `mail/`
  und `meta/`. Jede Mail liegt als einzelne, gepackte Datei, benannt nach dem
  SHA-256 ihres Inhalts, sortiert nach Monat.
- **Bytegenaue Ablage.** Mails werden unverändert gespeichert – keine
  geglätteten Zeilenenden, keine reparierten Kopfzeilen. Damit bleibt eine
  DKIM-Signatur prüfbar.
- **Journal mit Hash-Kette.** Jeder Eintrag trägt den Hash seines Vorgängers.
  Nachträgliche Änderungen, entfernte Einträge und untergeschobene Mails fallen
  bei der Prüfung auf.
- **Grabsteine statt Löschen.** Der Inhalt verschwindet, der Vorgang bleibt
  protokolliert – mit Zeitpunkt, Verursacher und Grund.
- **Siegel** über den Stand des Journals, mit vorgesehenem Feld für einen
  Zeitstempel nach RFC 3161.
- **Zwei Betriebsarten.** Privatarchiv ohne Fristen, Geschäftsarchiv mit
  Hash-Kette, Fristenschutz und Protokoll.
- **Aufbewahrungsfristen** für Deutschland (6/8 Jahre), Österreich (7) und die
  Schweiz (10), gerechnet ab Ende des Kalenderjahres. Sonderfall BaFin
  berücksichtigt.
- **Suchindex** mit SQLite und FTS5, außerhalb des Archivs abgelegt und
  jederzeit vollständig daraus neu erzeugbar.
- **Zweiter Index über Dreizeichengruppen**, damit `betreff:rechnung` auch
  „Schlussrechnung" findet, und mit Umlautnormalisierung, damit `von:muller`
  auch „Müller" findet.
- **Deutsche Suchsprache**: `von:`, `an:`, `betreff:`, `text:`, `inhalt:`,
  `hat:anhang`, `typ:`, `jahr:`, `konto:`, `ordner:` sowie Ausschluss per `-`.
- **Mailquellen**: Thunderbird-Profile mit allen Konten und Ordnern, Maildir und
  MBOX-Dateien. Thunderbird-Profile werden auf allen drei Systemen selbst
  gefunden, auch bei Flatpak- und Snap-Installationen.
- **Sperrdatei**, damit nicht zwei Rechner gleichzeitig in ein Archiv in der
  Cloud schreiben.
- **Kommandozeile** mit `anlegen`, `importieren`, `suchen`, `pruefen`,
  `neuaufbau`, `siegel`, `info` und `suchhilfe`.
- **121 Tests**, darunter der Nachweis, dass eine Fälschung auch dann auffällt,
  wenn der Fälscher den Eigenhash mitrechnet.
- [RECHTLICHES.md](RECHTLICHES.md) zur Rechtslage in Deutschland, Österreich und
  der Schweiz.

[0.12.0]: https://github.com/Stephan-Lefty/MailBurg/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/Stephan-Lefty/MailBurg/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/Stephan-Lefty/MailBurg/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/Stephan-Lefty/MailBurg/compare/v0.1.0...v0.9.0
[0.1.0]: https://github.com/Stephan-Lefty/MailBurg/releases/tag/v0.1.0
