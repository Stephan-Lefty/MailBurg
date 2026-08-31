[Übersicht](../README.md) | [Anleitungen](README.md) | [Erste Schritte](erste-schritte.md) | [Die Oberfläche](oberflaeche.md)

# Server Edition – Entwurf

**Hiervon ist noch nichts gebaut.** Dieses Dokument hält fest, was ein
MailBurg-Server können muss, was dafür fehlt und in welcher Reihenfolge
es entstehen sollte. Es ist die Grundlage für die Entscheidung, nicht
ihr Ergebnis.

Stand: 2026-08-31. Zielsysteme: **Debian Server** und **Windows Server
2025** oder jünger.

## Wozu überhaupt

Das Firmenarchiv umfasst rund 700.000 Mails. So etwas gehört nicht auf
einen Arbeitsplatzrechner: Es soll von mehreren Stellen erreichbar sein,
im Firmennetz und von unterwegs, und es soll laufen, wenn niemand
angemeldet ist.

Die Reihenfolge ist deshalb: **erst der Server, dann der Import.** Ein
Bestand dieser Größe wandert nicht zweimal.

## Das Wappen

Dieselbe Burg in Rot, mit dem Wort **SERVER** über dem »urg« von Burg –
kantenbündig mit ihm und nicht höher als das »B«, so dass beide zusammen
einen Block ergeben. Am 2026-08-31 mit Stephan entworfen.

Erzeugt wird es aus der Desktop-Fassung, nicht daneben gezeichnet:

```bash
python werkzeuge/server_logo.py
```

Es sind dieselbe Burg, derselbe Schriftzug, dieselben Maße. Zwei getrennt
gepflegte Zeichnungen würden auseinanderlaufen, sobald jemand am Original
etwas verschiebt.

**Zwei Dinge daran waren nicht offensichtlich.** Rot verhält sich anders
als Blau: Auf Weiß kommt es auf 5,62, im dunklen Thema aber nur auf 2,71
– dort wechselt das Wort deshalb auf den helleren Ton der Palette (7,07).
Und `textLength`, mit dem das Wort zuerst auf die Breite gezwungen wurde,
**wertet rsvg nicht aus**; in den erzeugten PNG stand es 162 statt 300
Einheiten breit. Das Wort besteht deshalb aus Umrissen, eingemessen am
gerenderten Bild.

Die Farbwerte stehen in [assets/farben.md](../assets/farben.md).

## Ein Repository, saubere Trennung

Am 2026-08-31 besprochen und entschieden: **Die Server Edition bekommt
kein eigenes Repository.**

Der Gedanke dahinter war Sauberkeit – und genau die spricht dagegen. Ein
zweites Repo hieße ein zweiter Kern: Archivformat, Journal, Hash-Kette,
Index. Zwei Fassungen davon laufen auseinander, und zwar unbemerkt. Der
Tag, an dem ein Server ein Archiv schreibt, das der Desktop nicht mehr
liest, ist der schlimmste Tag, den ein Archivprogramm haben kann – er
fällt erst Jahre später auf.

Dazu kommt: **Die Rechteprüfung gehört in den Kern**, nicht in den
Server (siehe unten). Bei zwei Repositorys läge der
sicherheitsentscheidende Teil im jeweils anderen.

Und das Muster gibt es schon. Die Desktop-Oberfläche ist auch nur ein
Zusatz – `pip install "mailburg[oberflaeche]"`, hundertfünfzig Megabyte
PySide6, und trotzdem kein eigenes Repo. Der Server wird das dritte
Frontend nach demselben Muster: `mailburg[server]`.

**Getrennt wird trotzdem, nur an der richtigen Stelle:**

* Ein eigenes Verzeichnis `mailburg/server/`, das **nichts** aus
  `mailburg/ui/` anfassen darf – und umgekehrt. Beide kennen den Kern,
  sonst nichts voneinander. `tests/test_schichten.py` hält das fest,
  seit dem 2026-08-31 und damit vor der ersten Zeile Servercode.
* Eigene Doku für Verwalter, getrennt von der Anwenderdoku.
* Eigene Release-Artefakte für Debian und Windows Server.
* Ein CI-Lauf, der **beide Frontends gegen dasselbe Archiv prüft**. Das
  ist der Test, den zwei Repositorys gerade nicht hergeben.

Zu ändern wäre die Entscheidung, wenn der Server einmal eine andere
Lizenz bekommt oder jemand anderem gehört. Beides ist heute nicht so.

### Eine Altlast, erledigt am 2026-08-31

Beim Prüfen der Schichten aufgefallen: `core/archive.py` und
`core/nachfrage.py` holten sich aus `ui/app.py`, was der Anwender
zuletzt geöffnet hatte – `zuletzt_benutzte_pfade`, `gemerktes`,
`merken_unter`.

Schlimm war es nicht: Der Import stand in der Funktion, und `ui/app.py`
selbst lädt PySide6 erst in seinen eigenen Funktionen. Es zog also kein
Qt nach.

Sauber war es trotzdem nicht, und für einen Dienst die falsche Adresse:
Gemerkte Pfade und Einstellungen sind kein Anliegen der Oberfläche,
sondern des Programms.

**Aufgelöst am 2026-08-31.** Sie liegen jetzt in
`core/einstellungen.py`. Die Ausnahmeliste im Schichtentest ist leer;
der Kern kennt kein Frontend mehr.

Die Datei heißt weiterhin `oberflaeche.json` – umbenennen hieße, dass
jeder beim nächsten Start seine Fenstergröße, seine Archivliste und
seine Schriftgröße verliert. Dafür ist ein stimmiger Dateiname zu wenig
wert.

**Eine Frage bleibt offen:** `core/archive.py` löst Archivkennungen zu
Namen auf und nimmt dafür die zuletzt benutzten Pfade als Suchraum. Für
einen Dienst ergibt das keinen Sinn – er hat keine »zuletzt benutzten«
Pfade eines Menschen, sein Archiv steht in seiner Konfiguration. Das
braucht dort eine eigene Antwort.

## Was schon trägt

`core`, `search`, `sources` und `extract` sind vollständig frei von Qt –
nachgeprüft am 2026-08-30. Der Kern hat überhaupt keine
Pflichtabhängigkeiten (`dependencies = []` in `pyproject.toml`).

Eine Weboberfläche wäre damit ein **drittes Frontend** neben
Kommandozeile und Desktop-Fenster, kein zweites Programm. Archivformat,
Journal, Hash-Kette, Index und Fristenrechnung bleiben, wie sie sind.

Das ist die gute Nachricht. Die folgenden fünf Punkte sind die andere.

## 1. MailBurg kennt keine Benutzer

Es gibt kein Konto, keine Anmeldung, keine Rolle, kein Recht. Das
Journal führt zwar einen `actor`, aber der ist ein Name aus dem
Betriebssystem – eine Behauptung, keine geprüfte Identität.

**Das ist der größte Brocken, größer als die Weboberfläche selbst.**

### Entschieden am 2026-08-31

**Rechte je Postfach.** Am Server wird festgelegt, auf welche Postfächer
ein Benutzer zugreifen darf – von einem einzigen bis zu allen.

Die Größenordnung, die Stephan genannt hat: **bis zu 50 Benutzer, bis zu
60 Postfächer.** Das ist klein genug, dass die Zuordnung eine
gewöhnliche Tabelle sein kann (höchstens 3.000 Zeilen), und groß genug,
dass sie sich nicht von Hand in einer Konfigurationsdatei pflegen lässt.

Diese Entscheidung ist die richtige – und sie ist teurer als eine bloße
Anmeldung. Was daran hängt:

### Die Rechte gehören in die Abfrage, nicht dahinter

Wer erst sucht und dann wegfiltert, was der Benutzer nicht sehen darf,
baut ein Leck. Die **Trefferzahl** stimmt dann nicht mit dem überein,
was in der Liste steht – und aus »1.284 Treffer, davon 12 sichtbar«
liest jeder heraus, dass es 1.272 weitere gibt. Dasselbe gilt für die
Sortierung, für das Blättern und für jede Statistik.

Gut daran: **Der Mechanismus ist schon da.** Die Suchsprache kennt
`konto:` und setzt es als Prädikat in die Abfrage:

```sql
EXISTS (SELECT 1 FROM locations l WHERE l.msg_id = m.id AND l.account = ?)
```

Die Rechteprüfung ist dasselbe Muster mit einer Liste statt eines Werts
– nur darf sie nicht weglassbar sein. Sie gehört deshalb nicht in die
Suchsprache, sondern eine Ebene tiefer: an die Stelle, an der die
Abfrage zusammengesetzt wird, für jede Abfrage, ohne Schalter.

### Eine Mail kann in mehreren Postfächern liegen

Das ist keine Ausnahme, sondern der Normalfall bei Rundmails: Die
Tabelle `locations` führt je Nachricht beliebig viele Fundorte.

Daraus folgt eine Falle, die man einmal übersieht und nie wieder: Ein
Benutzer, der Postfach A sehen darf, **darf die Mail sehen**, wenn sie in
A liegt – auch wenn sie zusätzlich in B liegt. Aber die
**Fundortanzeige darf B nicht nennen.** Sonst verrät die Detailansicht
einer erlaubten Mail die Struktur des übrigen Archivs, samt Namen der
Postfächer, die es sonst noch gibt.

Betroffen sind alle Stellen, die Fundorte zeigen oder zählen: die
Trefferliste, die Detailansicht, der Postfachbaum links und die
Gesamtzahl unten (»2.431 Mails im Archiv« ist für jeden Benutzer eine
andere Zahl).

### Wer die Rechte vergibt

Es braucht eine Rolle »Verwalter« – jemanden, der Benutzer anlegt,
Postfächer zuordnet und Zugänge stilllegt. Und zwar von Anfang an, samt
Kommandozeilenbefehl: Ein Server, dessen Weboberfläche klemmt, muss sich
von der Konsole aus wieder zugänglich machen lassen.

**Stilllegen statt löschen**, wie bei den Postfächern schon: Wer
ausscheidet, verliert den Zugang – aber sein Name muss im Journal
lesbar bleiben, sonst stehen dort Vorgänge ohne Urheber.

### Und alles davon ins Journal

Jede Anmeldung, jede Rechteänderung und jeder Zugriff auf Post. Bei
personenbezogenen Daten ist das keine Fleißarbeit, sondern die
Rechenschaftspflicht aus Art. 5 Abs. 2 DSGVO – und bei einem Archiv, in
dem 50 Menschen suchen können, ist es die einzige Möglichkeit,
nachträglich zu beantworten, wer was gesehen hat.

**Ein Vorbehalt dazu:** Jeden Suchzugriff zu protokollieren, lässt das
Journal schnell wachsen, und es ist selbst eine Sammlung
personenbezogener Daten – nämlich darüber, wonach Mitarbeiter suchen.
Das gehört bedacht, bevor es gebaut wird: vermutlich Zugriffe auf
einzelne Nachrichten ja, jede getippte Suchanfrage nein.

## 2. Ohne Desktop gibt es keinen Schlüsselbund – gelöst

Die Postfach-Passwörter liegen im Schlüsselbund des Betriebssystems.
Der hängt an einer **Anmeldesitzung** – unter Linux an gnome-keyring
oder ksecretd, die ein angemeldeter Benutzer startet.

**Auf einem Debian-Server ohne Desktop gibt es keinen.** Und genau das
ist der Betriebszustand, den wir wollen: Der Dienst läuft, ohne dass
jemand angemeldet ist.

Nachgeprüft in `core/accounts.py`: Es gibt derzeit **keinen anderen
Weg** an ein Passwort. Fehlt der Schlüsselbund, meldet MailBurg das und
hört auf. Für den Desktop ist das richtig; für einen Server ist es das
Ende.

**Gebaut am 2026-08-31:** `core/tresor.py`. Eine Datei mit
verschlüsselten Passwörtern, deren Hauptschlüssel woanders liegt – in
einer Umgebungsvariablen oder einer eigenen Datei.

```bash
mailburg tresor schluessel        # Hauptschlüssel erzeugen
mailburg tresor uebernehmen       # vom Arbeitsplatz in den Tresor
mailburg tresor pruefen           # kommt der Server an alles heran?
```

**Der Tresor greift nur, wenn er eingerichtet ist.** Sonst gilt der
Schlüsselbund wie bisher: Auf einem Arbeitsplatz soll nichts an ihm
vorbei geschrieben werden, nur weil eine Datei existiert.

**Wogegen das schützt, und wogegen nicht.** Es schützt gegen
Sicherungskopien des Konfigurationsordners, versehentlich weitergegebene
Ordner und jeden, der an die Datei kommt, aber nicht an den Schlüssel –
der häufige Fall. Es schützt *nicht* gegen jemanden, der als der
Dienstbenutzer Programme ausführen kann: Der hat beides, denn der Dienst
braucht beides. Ein Passwort, mit dem sich ein Programm ohne Zutun
anmelden soll, lässt sich nicht vor diesem Programm verstecken.

**Ohne `cryptography` gibt es keinen Rückfall auf Klartext**, sondern
eine Absage. Eine Datei, die aussieht wie ein Tresor und keiner ist,
wäre schlimmer als gar keine. Das Paket kommt mit `mailburg[server]`.

**Was der systemd-Weg noch beitragen kann:** `LoadCredential=` reicht
den Hauptschlüssel an den Dienst durch, ohne dass er im Dateisystem des
Dienstes steht. Das ist die bessere Aufbewahrung und ändert an MailBurg
nichts – es liest ihn aus `MAILBURG_SCHLUESSELDATEI`, egal wer die Datei
dorthin gelegt hat.

Was **nicht** geht: den Desktop-Schlüsselbund auf einem Server
nachbauen zu wollen. Ein entsperrter Schlüsselbund ohne angemeldeten
Menschen ist eine Datei mit Extraschritten.

## 3. Als Dienst laufen – Debian gebaut, Windows offen

```bash
mailburg server
```

Der Dienst liest seine Einstellungen aus Umgebungsvariablen – den Weg
kennen systemd, Docker und die Windows-Dienstverwaltung gleichermaßen:

| Variable | wofür |
|---|---|
| `MAILBURG_ARCHIV` | der Ordner des Archivs (nötig) |
| `MAILBURG_ADRESSE` | worauf gelauscht wird (Vorgabe `127.0.0.1`) |
| `MAILBURG_PORT` | der Port (Vorgabe 8383) |
| `MAILBURG_SCHLUESSELDATEI` | der Hauptschlüssel des Tresors |

**Die Vorgabe lauscht nur auf dem eigenen Rechner.** Ein Archivdienst,
der beim ersten Start ungefragt im ganzen Netz steht, wäre eine böse
Überraschung. Wer ihn im Firmennetz erreichbar machen will, sagt es
ausdrücklich — und die Statusseite erinnert daran, solange es noch keine
Anmeldung gibt.

Drei Adressen gibt es bisher: `/` zeigt den Zustand als Seite,
`/zustand.json` dasselbe maschinenlesbar, `/lebt` antwortet nur »ja«,
ohne das Archiv anzufassen — für den Neustart-Wächter des Systems.

**Debian:** die Vorlage liegt in
[`werkzeuge/mailburg-server.service`](../werkzeuge/mailburg-server.service),
mit eigenem Benutzer, `ProtectSystem=strict`, `Restart=on-failure` und
dem Hauptschlüssel über `LoadCredential=` — so steht er weder in der
Prozessliste noch im Dateisystem des Dienstes.

### Windows Server 2025 – zu entscheiden

Nachgeschlagen am 2026-08-31, nicht geraten:

**Die Aufgabenplanung reicht nicht.** Sie kann ein Programm »beim
Systemstart« und ohne Anmeldung starten — das tut MailBurg für den
regelmäßigen Abruf bereits. Aber sie hält es nicht am Leben: Stürzt es
ab, bleibt es unten. Für einen Dienst, der lauscht, ist das zu wenig.

**NSSM scheidet aus.** Der verbreitetste Wrapper hat seit über einem
Jahrzehnt kein stabiles Release mehr. Für ein Archiv, das zwanzig Jahre
halten soll, ist das die falsche Grundlage.

Bleiben drei Wege, und die Wahl gehört Stephan:

* **pywin32** — echte Anmeldung beim Dienstmanager, Python-nativ, kein
  zusätzliches Programm. Etabliert und gepflegt. Dafür der meiste Code,
  und er lässt sich hier nicht prüfen.
* **WinSW** — XML-gesteuerter Wrapper, verbreitet (Jenkins nutzt ihn),
  aber im Wartungsmodus.
* **Servy** — jung, ausdrücklich für Windows 11 und Server 2025. Für ein
  Archivprogramm wäre eine unerprobte Abhängigkeit ein Risiko.

Empfehlung: **pywin32**, als eigenes Extra `mailburg[server-windows]`.
Mit dem ausdrücklichen Vermerk, dass es hier nicht geprüft werden kann —
wie bei OAuth2 auch.

## 4. Erreichbarkeit und HTTPS

Im Firmennetz ist das überschaubar. »Über das Internet« ist die Aussage
mit dem Risiko.

Das Repo rät für den verwandten IMAP-Gedanken zu VPN statt Portfreigabe
(siehe TODO, Abschnitt *Danach*). Wer stattdessen einen Webdienst
öffentlich stellt, sollte wenigstens:

* **hinter einem Reverse Proxy** stehen – nginx oder Caddy unter Debian,
  IIS unter Windows –, nicht mit dem eigenen HTTP-Server nach außen;
* **HTTPS erzwingen**, mit HSTS, und niemals eine Anmeldung über
  ungesicherte Verbindung anbieten;
* **Anmeldeversuche begrenzen** und verzögern, sonst probiert sie
  jemand in Ruhe durch;
* **keine Fehlermeldung geben, die Konten verrät** – »Anmeldung
  fehlgeschlagen«, nicht »Benutzer unbekannt«.

**Eine ehrliche Empfehlung bleibt trotzdem:** Wenn VPN oder Tailscale in
Frage kommen, ist das der bessere Weg. Ein Archiv mit zwanzig Jahren
Geschäftspost ist ein lohnenderes Ziel als das, was sonst so im Netz
steht.

## 5. Die Verschlüsselung rückt nach vorn

In der TODO steht sie unter *Danach*. Für einen Server gehört sie
weiter nach oben – nicht weil der Server unsicherer wäre, sondern weil
die Begründung von damals nicht mehr trägt.

Die Entscheidung vom 2026-08-25 lautete: kein Passwort beim
Programmstart, weil es ohne Archivverschlüsselung Theater wäre – die
Mails liegen als Dateien im Ordner, wer am Rechner sitzt, liest sie
ohnehin. **Das stimmt für einen Arbeitsplatz.** Bei einem Server ist
»wer am Rechner sitzt« nicht mehr dieselbe Person wie »wer die Daten
sehen darf«, und Sicherungen wandern womöglich in eine Cloud.

## Was die Weboberfläche können muss

In dieser Reihenfolge, und zunächst **nur lesend**:

1. Anmelden und abmelden.
2. Suchen – dieselbe Suchsprache wie überall, mit der Trefferliste.
3. Eine Nachricht lesen, mit Anhängen zum Herunterladen.
4. Als `.eml` herunterladen.
5. Den Zustand sehen: wie viele Mails, wann zuletzt abgerufen, ob alle
   Postfächer erreichbar waren.

**Später und nur mit Bedacht:** Einstufen, Fristenbericht, Auskunft nach
Art. 15 DSGVO, Verfahrensdokumentation. Alles vier sind Vorgänge, die
ins Journal schreiben – dort muss vorher geklärt sein, wer sie auslösen
darf.

**Bewusst nicht im Browser:** das Zurücklegen ins Postfach. Das ist die
einzige Stelle, an der MailBurg in ein fremdes Postfach schreibt; sie
soll eng gefasst bleiben.

## Technikwahl

Alles MIT oder BSD – AGPL und GPL bleiben draußen, wie im ganzen
Projekt.

* **Starlette** (MIT) mit **uvicorn** (BSD) als HTTP-Grundlage.
* **Server-gerendertes HTML** mit Jinja2 (BSD). Kein JavaScript-Gerüst,
  keine Inhalte von fremden Servern – dieselbe Haltung wie beim Rest:
  Was das Programm anzeigt, bringt es mit.
* **argon2-cffi** (MIT) für die Passwörter der Benutzer. Dasselbe
  Verfahren steht ohnehin für die Archivverschlüsselung im Plan.
* Als eigener Zusatz: `pip install "mailburg[server]"`. Wer den Server
  nicht braucht, installiert ihn nicht.

## Reihenfolge

Jede Stufe ist für sich brauchbar und prüfbar:

0. ~~**Die Altlast auflösen:** gemerkte Pfade und Einstellungen aus
   `ui/app.py` in den Kern.~~ Erledigt am 2026-08-31.
1. ~~**Benutzer, Rechte und Anmeldung** im Kern~~ Erledigt am
   2026-08-31, samt Rechteprüfung in der Suche und der Oberfläche
   dazu. Was dort ursprünglich stand:

   **Benutzer, Rechte und Anmeldung** im Kern – ohne Web, mit
   Kommandozeilenbefehlen zum Anlegen und Zuordnen. Journal mit
   geprüftem `actor`. Dazu die Rechteprüfung an der Stelle, an der die
   Suchabfrage entsteht, mit Tests, die belegen: Was ein Benutzer nicht
   sehen darf, taucht auch in keiner Zahl auf.
2. ~~**Passwörter ohne Schlüsselbund**, sonst ruft der Server nie ab.~~
   Erledigt am 2026-08-31.
3. **Der Dienst**, auf beiden Systemen, mit einer Seite, die »läuft«
   sagt. Damit ist der Betrieb geklärt, bevor Funktion dazukommt.
4. **Lesender Zugriff** im Browser: Suche, Lesen, Herunterladen.
5. **Der Import der 700.000 Mails.**
6. Alles Weitere.

Der Import steht mit Absicht erst an fünfter Stelle. Vorher soll sich
zeigen, dass der Dienst über Wochen stabil läuft – ein Lasttest an
einem Bestand, den man nicht ersetzen kann, beweist wenig, solange die
Grundlage nicht steht.

## Was offen ist

* **Der Windows-Dienst**: nachzuschlagen, nicht zu raten.
* **Wo der Server steht.** Auf eigener Hardware in der Firma oder
  gemietet? Bei gemietet liegt Geschäftspost bei einem Dritten – eine
  Auftragsverarbeitung nach Art. 28 DSGVO, die einen Vertrag mit dem
  Anbieter braucht.
* **Wie ein Benutzer zu seinem Postfach kommt.** Trägt der Verwalter die
  Zuordnung von Hand ein, oder soll sie sich aus der Mailadresse
  ergeben? Von Hand ist mühsamer, aber durchschaubar – und bei 50
  Benutzern einmalig zu leisten.
* **Wie viel gleichzeitig los ist.** 50 Benutzer heißt nicht 50
  Suchanfragen zur selben Sekunde. SQLite liest im WAL-Modus problemlos
  parallel; die Frage ist eher, ob ein einzelner Prozess mit
  Arbeiterfäden genügt oder ob es mehrere braucht. Zu messen, nicht zu
  raten – erst recht bei 700.000 Mails und 9 GB Index.
* **Wie Benutzer ihr Passwort zurücksetzen.** Ohne Mailversand vom
  Server aus bleibt nur: Der Verwalter setzt es zurück. Das ist bei 50
  Menschen vertretbar und erspart dem Archivserver, selbst Mails zu
  verschicken.
