# CLAUDE.md

Landkarte des Repositorys. Ergänzt [README.md](README.md) und
[TODO.md](TODO.md), wiederholt sie nicht.

## Hier war Schluss (Stand 2026-09-07, Montag spätabends)

**Der Abend gehörte einer Meldung, die etwas Falsches behauptete.** Nach
Stephans Manjaro-Update mit über 300 Paketen sagte MailBurg für **alle
sieben** Postfächer: »liegt kein Passwort im Schlüsselbund«.

Sieben Passwörter verschwinden nicht gemeinsam. Was gleichzeitig
passiert, ist etwas anderes – und die Diagnose ging über zwei Stufen,
von denen die erste falsch war.

### Erste Stufe: das Auffangnetz

`accounts.passwort_holen` hatte:

```python
except Exception:  # noqa: BLE001 – ein gesperrter Schlüsselbund wirft
    return None
```

**Der Kommentar benannte den Fehler und lebte damit.** Dritte Instanz
derselben Klasse an einem Tag – nach `APP_ID` im Tresor und dem doppelt
geöffneten Anhang. Die Regel steht jetzt unten bei den Gepflogenheiten.

### Zweite Stufe: es war gar nicht gesperrt

`busctl --user status org.freedesktop.secrets` zeigte: Den Namen hält
**gnome-keyring**, während **ksecretd** und **kwalletd6** danebenlaufen.
Unter Linux beantwortet nur *ein* Dienst die Passwortanfragen; wer
zuerst da ist, gewinnt. Stephans Passwörter liegen im KDE-Tresor,
gefragt wurde der GNOME-Tresor.

**Von außen sieht das aus wie ein leerer Schlüsselbund** – und wer
darauf hereinfällt, trägt sieben Passwörter neu ein, in den falschen
Tresor, und steht beim nächsten Wechsel wieder da.

`accounts.schluesselbund_konkurrenz()` erkennt das jetzt und sagt es,
wenn ein Passwort fehlt. Geprüft wird allein über die laufenden
D-Bus-Namen – **nicht** durch einen Blick in fremde Tresore; zweimal hat
die Freigabe genau das zu Recht verhindert.

**Ein Detail, das ein Test gefunden hat:** `busctl` schreibt in leere
Spalten einen Strich. Ein Strich ist eine Zeichenkette und damit wahr,
wenn man nicht hinsieht – ein nur startbarer Dienst galt so als
laufender.

### Was dabei sonst noch auffiel

**Die Ausschlussliste wird beim Anlegen ins Konto kopiert.** Stephans
Konten tragen die Liste von vor Wochen; die drei Namen, die heute
dazukamen, fehlen dort. Für `Junk-E-Mail` folgenlos, weil die neue
Normalisierung Bindestriche ignoriert – für einen Ordner namens
»Spamverdacht« nicht. **Eine kopierte Vorgabe veraltet still**, und was
daraus folgt, steht als Frage in der TODO.

**Bei Arch und Manjaro überlebt eine venv keinen Python-Sprung.**
3.13 → 3.14 hätte MailBurg unbenutzbar gemacht; hier ging es gut, weil
`install.sh` an diesem Tag ohnehin dreimal lief. Auch das steht in der
TODO.

## Hier war Schluss (Stand 2026-09-07, Montagabend)

**1.3.3 ist veröffentlicht**, samt `MailBurg.exe` (165 MB). Der dritte
Release an einem Tag, und alle drei kamen aus dem Betrieb: 1.3.1 aus
einer Rückmeldung zur Server-Variante, 1.3.2 aus zwei Bildschirmfotos,
1.3.3 aus einer Frage nach dem Einlesen.

**Das Firmenarchiv steht bei rund 68.000 Mails und läuft sauber** – der
MailStore-Export von Stephans Firmenpostfach ist durch. Das Vierfache
des bisherigen Alltagsbestands und die erste Zahl in dieser
Größenordnung überhaupt.

### Die Frage, die dabei aufkam

»Werden Mails aus dem Spam-Ordner oder mit [SPAM] im Betreff
rausgefiltert?« Antwort: **beim Abruf ja, beim Einlesen von der Platte
nein.** Die Ausschlussliste hing am *Konto* – IMAP und JMAP kannten sie,
`mailburg importieren` nie. Ein Export bringt aber die Ordnerstruktur
mit, aus der er stammt, samt Papierkorb und Spamverdacht.

Dieselbe Klasse wie so oft in diesen Tagen: **Etwas ist an einer Stelle
gelöst und an der anderen nicht** – und niemand hatte die Frage
gestellt, weil beide Wege bis dahin nie nebeneinander lagen.

**Als Hülle gebaut, nicht fünfmal einzeln.** `local.OhnePapierkorb`
umschließt jede lokale Quelle; `open_path()` hüllt sie ein, sofern nicht
`alles=True`. Damit bekommt es auch die sechste Quelle, die später
dazukommt. Zwei Tests mussten mitziehen, weil `open_path` jetzt eine
Hülle liefert – dafür gibt es `.roh`.

**Zwei Entscheidungen, die nicht ohne Grund aufgemacht werden sollten:**

*Was übergangen wurde, wird genannt* – im Dialog vor dem Start, auf der
Kommandozeile danach. Eine stille Auslassung wäre schlimmer als keine.

*Eine ausdrücklich gewählte Datei wird nicht gefiltert.* Wer im Dialog
»MBOX-Datei …« anklickt und dort »Junk« auswählt, hat entschieden.

**Und ein Fehler, der dabei auffiel und älter ist:** Der Vergleich lief
über `casefold()` allein. Outlook schreibt »Junk-E-Mail«, in der Liste
stand »Junk E-Mail« – der Bindestrich ging daran vorbei, und der Ordner
wurde **auch beim IMAP-Abruf** archiviert. `_vergleichsform()` wirft
jetzt alles weg, was nicht Buchstabe oder Ziffer ist.

**Nicht gebaut: ein Filter auf `[SPAM]` im Betreff.** Der Marker steht
auch auf falsch-positiven Mails, und was einmal nicht archiviert wurde,
fällt erst Jahre später auf. Ein Ordner ist eine Entscheidung des
Anwenders, ein Betreffmarker die Vermutung eines Filters.

## Hier war Schluss (Stand 2026-09-07, Montag) – 1.3.2 ist draußen

**Stephans Regel des Tages, und sie steht ab jetzt in der CI:**

> »Es sollten immer vor der Veröffentlichung einer Version alle Fenster
> auf Lesbarkeit, Text und Felder überprüft werden. Mit jedem dieser
> Fenster machen wir unsere Arbeit beim User kaputt.«

Anlass waren zwei Bildschirmfotos: das Pfadfeld im Einlesedialog 108 px
breit mit »erbird« statt `/home/…/.thunderbird`, und »Noch ke…« im
Rückspieldialog.

### Warum das Prüfwerkzeug geschwiegen hat

**Es maß Eingabefelder gar nicht** – nur Auswahlfelder und Fließtexte.
Vier Fenster waren betroffen, zwei davon hatte niemand gemeldet
(Zeitplan, Einstufungsregeln). Und es lief **nur bei der
Vorgabeschrift**: Die drei Befunde in der Suchmaske treten erst ab 16 pt
auf – also genau bei denen, die die Schrift vergrößert haben, weil sie
sonst schlecht lesen.

**Ein Prüfwerkzeug mit einer Lücke sagt »alles lesbar« und meint »alles,
wonach ich gesucht habe«.** Deshalb prüft `lesbarkeit.py` jetzt
QLineEdit mit, spielt 9/12/16/20/24 pt durch – und läuft in der CI
(3 Sekunden), statt darauf zu warten, dass jemand daran denkt.

### Drei Dinge über Qt, die dabei zu lernen waren

**Der Dialog ist vor seinen Kindern dran.** Qt schickt das Show-Ereignis
erst an das Fenster, dann an den Inhalt – die Größe steht fest, bevor
ein Feld auf seinen Inhalt gewachsen ist. Wer danach eine Mindestbreite
setzt, nimmt sie dem Nachbarn weg: Im Zeitplan verlor der Fließtext eine
Zeile und brach mitten im Satz ab. Ein `QTimer.singleShot(0, …)` landet
hinter allen Show-Ereignissen und sieht das fertige Fenster.

**Ein Rollbereich verschluckt die Breite seines Inhalts.** Nach außen
meldet er nur, dass er rollen kann. Für die Höhe ist das sein Zweck, für
die Breite ein Fehler – **waagerecht gerollt wird nie.** `_dialog_weiten`
unterscheidet das jetzt.

**Ein `QLineEdit` kennt seinen Inhalt nicht.** Seine Mindestgröße ist
eine Konstante; in einer Zeile mit einem Knopf schrumpft es auf 108 px,
egal was drinsteht. Die Breite kommt jetzt aus der Schrift (45 Zeichen
Deckel, sonst sprengt ein langer Pfad das Fenster).

### Und der Anhang, der sich zweimal öffnete

Derselbe Befund wie beim Wappen und beim Archivpasswort, nur andersherum:
**Nicht etwas Neues wurde nicht abgeholt, sondern das Alte blieb
stehen.** Am 03.09. wanderte das Öffnen aus `ui/vorschau.py` nach
`core/rueckgabe.py` – und der alte `QDesktopServices.openUrl`-Aufruf
blieb daneben liegen, wurde bei der Gelegenheit sogar noch um eine
Fehlerbehandlung erweitert.

**Kein Test lief je durch diese Methode.** Geprüft wurde
`anhang_oeffnen` unmittelbar, und dort war alles in Ordnung. Der neue
Test zählt deshalb *beide* Wege zusammen und verlangt genau eins.

Nebenbei: Der `.eml`-Ordner-Import gibt es seit jeher und stand
nirgends – weder im README noch in `docs/oberflaeche.md`, wo der ganze
Dialog *Lokale Mailordner einlesen …* fehlte.

### Altbestand in ein laufendes Konto

Stephan exportiert ein Postfach aus MailStore, das im Archiv
weiterläuft, und fragte, wie die `.eml`-Dateien sauber zugeordnet
werden. Die Antwort ist `--konto` mit demselben Namen – **die Frage
dahinter war, ob das den laufenden Abruf zerschießt.**

Tut es nicht, und das steht jetzt in `tests/test_abruf.py` statt in
einer Zusage: `max_uid()` zählt nur echte Nachrichtennummern,
eingelesene Dateien haben keine. Mitgeprüft: Der Export-Ordner steht
neben `INBOX`, Überschneidungen liegen einmal auf der Platte, der zweite
Fundort steht trotzdem im Journal, zweimal einlesen legt nichts doppelt
an, die Hash-Kette bleibt heil.

**Die Lücke war die Eingabe, nicht der Kern.** Der Kontoname war ein
freies Textfeld – ein »Firma « mit Leerzeichen ergibt einen zweiten
Zweig, der im Baum genauso aussieht wie der erste. Jetzt stehen die
vorhandenen Postfächer zur Auswahl (aus `index.accounts()` **und** der
Kontenliste, denn ein eingerichtetes Postfach kann noch nie abgerufen
worden sein), und ein Name, der einem vorhandenen bis auf Groß- und
Kleinschreibung gleicht, wird gemeldet.

## Hier war Schluss (Stand 2026-09-07, Montag früh)

**1.3.1 ist veröffentlicht**, samt `MailBurg.exe` (165 MB) am Release.
Danach alle fünfzehn Dateien in `docs/` durchgesehen – die Frage war,
wo sonst noch eine Umgebung vorausgesetzt wird, die auf einem Server
fehlt. Zwölf waren in Ordnung, drei nicht:

**»Microsoft-Konten gehen derzeit nicht«** stand seit der 0.10 in
`postfaecher-einrichten.md`. Seit der 1.0 stimmt das nicht mehr – sie
gehen über OAuth2, und drei Absätze weiter unten stand das sogar, als
»seit dem 2026-08-29 vorbereitet«. **Der Anwender liest die Überschrift
und hört auf zu lesen.**

**Ein Wächtertest hielt genau diesen falschen Satz fest:**
`assertIn("gehen derzeit nicht", doku)`. Daraus folgt eine Regel, die
noch nirgends stand: **Ein Wächtertest, der auf einen Wortlaut zeigt,
hält den Wortlaut fest, nicht seinen Sinn** – und wird damit zum
Bremsklotz gegen die Korrektur. Er prüft jetzt, dass der Abschnitt auf
`oauth2.md` verweist und App-Kennwörter ausschließt.

**Und wieder: etwas ist da und wird nirgends abgeholt.** Der Dienst
reicht seit dem 31.08. ein Archivpasswort durch (`dienst.py:67`,
`lesen.py:42`), `/zustand` warnt sogar ausdrücklich, wenn es fehlt – in
`server-einrichten.md` kam verschlüsselt betriebenes Archiv nicht vor.
Jetzt steht dort »Wenn das Archiv verschlüsselt ist«, mit
`mailburg passwort hinterlegen` und `MAILBURG_ARCHIVPASSWORTDATEI`.
`docs/server.md` sagte außerdem noch »vier der fünf Brocken sind
gebaut« – es sind fünf.

Nebenbei: Die Vergleichslinks im CHANGELOG hörten bei 0.12.0 auf, alle
Fassungen ab 1.0.0 waren tote Klammern. Und die Datumsangaben zum
Tresor-Fix heißen jetzt »mindestens Fassung 1.3.1« – **ein Anwender
kennt seine Fassungsnummer, nicht unser Commit-Datum.**

### Zwei Werkzeugpunkte hinterher erledigt

**Die CI sucht jetzt undefinierte Namen.** Der Schritt daneben heißt
»Syntax prüfen« und läuft `compileall` – und findet genau diese Klasse
nicht: Ein Aufruf von etwas, das es nicht gibt, ist syntaktisch
tadellos. Gefiltert auf `undefined name`, weil unbenutzte Importe
Kosmetik sind: **Eine CI, die rot ist, ohne dass etwas kaputt ist,
gewöhnt man sich an.** Beide Richtungen sind nachgestellt.

**`werkzeuge/lesbarkeit.py` zeigt keine echten Postfächer mehr.** Die
Ursache war ein halber Patch: `data_dir()` umgelenkt, `config_dir()`
nicht – und dort liegt die Kontenliste. Beim Bauen fiel ein zweites
Risiko auf: Ein `Kontenliste()` ohne Pfad nähme `config_dir()`; fiele
der Patch weg, überschriebe das Messwerkzeug die echten Postfächer. Das
Ziel wird jetzt übergeben. **Ein Messwerkzeug darf messen, nicht
ändern.**

Der Beleg dafür war nicht der Testlauf, sondern eine Gegenprobe im
Scratchpad: `_befunde` durch einen Spion ersetzt, der jeden Eintrag
jedes Auswahlfelds mitschreibt – 52 Einträge, drei Postfächer, alle auf
`.example`.

## Hier war Schluss (Stand 2026-09-06, Sonntag)

**Das vierte Nutzer-Feedback, und diesmal zur Server-Variante.**
Derselbe Anwender wie beim JMAP- und Restore-Wunsch – **der erste
Mensch außer Stephan, der sich den Dienst überhaupt ansieht.** Sein
Einwand war eine Frage, keine Fehlermeldung, und trotzdem der beste
Befund seit Tagen:

> »Du schreibst *ohne Oberfläche, das sind hundertfünfzig Megabyte Qt
> für ein Fenster, das auf einem Server niemand öffnet*. Dann soll man
> aber die WebUI via Port 8383 auf localhost öffnen. Aber localhost kann
> ich ja gar nicht aufrufen, weil ich an einem headless Server sitze.«

Beide Sätze stehen in derselben Anleitung, keine drei Bildschirmseiten
auseinander. **Die Anleitung war auf Debian durchgespielt worden – von
jemandem, der dabei einen Bildschirm hatte.**

### Der eigentliche Fund liegt tiefer

Der Widerspruch war in zwanzig Minuten behoben (SSH-Tunnel in Abschnitt
4, `curl …/zustand.json` daneben, `ssh -L` in der Startmeldung). Beim
Nachsehen, wo dieselbe Voraussetzung noch klemmt, kam OAuth2 dran: Die
Anmeldung braucht einen Browser auf demselben Rechner. Der einzige Weg
auf einen Server führt über den Tresor.

**Und dort lagen zwei Fehler übereinander:**

`mailburg tresor uebernehmen` nahm nur Passwörter mit, keine Token –
also genau das nicht, was sich auf einem Server nicht nachholen lässt.
Beim Schreiben des ersten Tests dafür fielen zwei weitere auf, beide
seit dem 31.08. drin: **`APP_ID` war in `__main__.py` nirgends
importiert** – ein blankes `except Exception` verschluckte den NameError
bei jedem Konto, der Befehl meldete »0 Passwörter übernommen«, als wäre
der Schlüsselbund leer. Und **`paths` fehlte ebenfalls**, weshalb die
Schlussmeldung danach im Traceback endete.

**Der zweite beweist, dass den Befehl nie jemand ausgeführt hat** – er
kracht laut. Der erste ist trotzdem der lehrreichere, und die Lehre ist
neu in dieser Sammlung: Ein Auffangnetz, das auch Programmierfehler
fängt, macht aus einem Absturz eine falsche Auskunft. »0 übernommen«
sieht aus wie ein Ergebnis; ein Traceback sieht aus wie ein Fehler. Das
`except` ist jetzt auf `keyring.errors.KeyringError` eingeengt.

**`pyflakes mailburg/` hätte das in einer Sekunde gesagt.** Es läuft
nirgends – steht als offener Punkt in der TODO. Nachgesehen: Der
APP_ID-Fehler war der einzige seiner Art, der Rest sind unbenutzte
Importe.

### Was daraus für die Zukunft folgt

**Wer eine Anleitung schreibt, hat die Umgebung im Kopf, in der er sie
geschrieben hat.** Zwei Fälle sind gefunden (Weboberfläche, OAuth2), der
dritte steht als Aufgabe in der TODO. Es ist dieselbe Klasse wie der
fish-Fehler vom 03.09.: eine Voraussetzung, die dort selbstverständlich
ist, wo geprüft wurde – und anderswo nicht gilt.

Nebenbei fiel ein überholter Text auf: Der Hinweis beim Lauschen im Netz
sagte »solange es keine Anmeldung gibt«. Die gibt es seit dem 31.08. Der
Grund, der geblieben ist, wiegt schwerer – HTTP ohne TLS – und steht
jetzt da. Ein Test hält Startmeldung und `/zustand` zusammen, damit die
beiden nicht wieder auseinanderlaufen.

1664 Tests grün, **als 1.3.1 getaggt.** Eine Fassung aus einer einzigen
Rückmeldung – wie die 1.2.0, und aus demselben Grund: Ein Anwender
benutzt das Programm anders, als der es gebaut hat.

**Warum eine eigene Fassung und nicht »kommt mit der nächsten mit«:**
Der Tresor-Fehler trifft jeden, der die Server-Variante aufsetzt, und
sieht dabei nicht nach einem Fehler aus, sondern nach einem leeren
Schlüsselbund. Wer danach sucht, sucht am falschen Ende.

### Beim Abschluss noch: das Messwerkzeug hat gelogen

`werkzeuge/lesbarkeit.py` meldete ein zu schmales Auswahlfeld im
Rückspieldialog. **Nachgemessen war nichts dran:** Das Feld ist beim
Öffnen versteckt und trägt die Breite, die das Layout ihm zugeteilt
hat, während sein Platz vom Pfadfeld belegt war. Beim Einblenden wächst
es auf 691 px und das Fenster von 324 auf 834.

Mein erster Anlauf war ein Fix in `ui/farben.py` samt Test – **beide
habe ich zurückgenommen.** Die Gegenprobe im Scratchpad zeigte, dass Qt
den Dialog von selbst weitet: Der Test wäre auch ohne den Fix grün
gewesen. Ein Test, der nicht rot werden kann, ist keiner, und eine
Änderung ohne belegten Grund ist Ballast.

**Der Fehler lag im Werkzeug**, und er ist die schlimmere Sorte: Ein
Prüfwerkzeug, das etwas meldet, was im Betrieb nicht auftritt, entwertet
seine übrigen Befunde. In CLAUDE.md steht seit dem 31.08. der Satz »was
das Werkzeug findet, ist echt« – der galt nicht mehr. Versteckte Felder
werden jetzt übersprungen und **am Ende des Berichts genannt**: Was ein
Prüfwerkzeug auslässt, muss es sagen, sonst liest sich »nichts
abgeschnitten« wie »alles geprüft«.

Nebenbei aufgefallen und in der TODO: **Das Werkzeug liest die echten
Konten des Rechners.** In der Ausgabe stand eine echte Firmenadresse
samt Mailserver – also genau das, was man in einen Fehlerbericht
kopiert.

## Hier war Schluss (Stand 2026-09-04, Freitagabend)

**1.3.0 ist veröffentlicht**, samt `MailBurg.exe`. Zwei Punkte aus der
TODO abgearbeitet, 1655 Tests grün, `werkzeuge/lesbarkeit.py` ohne
Befund.

Die Fassung bringt vor allem eines: **den Restore.** Damit ist der
Wunsch des dritten Rückmelders vollständig erfüllt – Sicherung und
Rückgabe haben nichts mehr miteinander zu tun.

### Das rote Wappen ist endlich in der Weboberfläche

`server_logo.py` erzeugte es seit dem 31.08., `assets/server/` enthielt
es in allen Größen – **benutzt wurde es an keiner einzigen Stelle.**
Wieder derselbe Befund wie am 03.09.: etwas, das vollständig da ist und
nirgends abgeholt wird.

Drei Dinge, die dabei nicht offensichtlich sind:

**Die Bildersuche liegt jetzt in `mailburg/bilder.py`**, nicht mehr in
`ui/bilder.py`. Der Dienst darf nicht von PySide6 abhängen, das auf
einem Server gar nicht installiert ist. Was zwei Teile brauchen, gehört
keinem von beiden.

**Je Bild eine eigene Route, kein `/{name}`.** Ein Platzhalter dort
verschluckte alles Einteilige – auch `/anmelden`, denn die Bildrouten
stehen vor denen der Weboberfläche. Ein Test hält das fest.

**Die Namen kommen aus `dienst.WAPPEN`, nicht aus der URL.** Ein
Dateiname aus einer Anfrage ist die klassische Stelle für ein `..`.

Nebenbei: Die `.ico` wiegt 370 KB (alle Größen bis 256 Pixel). Verlinkt
sind deshalb die PNG; die `.ico` liegt allein unter `/favicon.ico`.

### Zurückspielen per IMAP – der zweite Teil des Restore-Wunsches

`core/zurueckspielen.py` hat jetzt ein viertes Ziel: `_Postfach`. Damit
ist der Wunsch vom 03.09. vollständig erfüllt – Sicherung und Rückgabe
haben nichts mehr miteinander zu tun.

**Der ganze Aufwand steckt in einer einzigen Eigenschaft des
Protokolls:** `APPEND` legt jedes Mal eine neue Kopie an und vergibt
eine neue UID. Der Server hilft beim Wiedererkennen **nicht**. Deshalb
holt MailBurg vor dem Schreiben alle `Message-ID` des Zielordners – in
*einer* Anfrage je Ordner, nicht in einer je Mail. Bei zehntausend
Nachrichten ist das der Unterschied zwischen einem Durchlauf und
zehntausend Umläufen.

**Die Gegenprobe war nötig.** Alle 52 Tests liefen auf Anhieb grün, und
das ist verdächtig. Setzt man `_vorhandene()` außer Kraft, schlagen
genau die beiden Tests fehl, die das Verdoppeln verhindern sollen – die
Tests prüfen also wirklich etwas. `tests/fake_imap.py` kann dafür seit
heute `CREATE` und `APPEND` und verhält sich dabei wie ein echter
Server.

**Drei Kleinigkeiten, die man leicht rät statt nachzusehen:** Das
Trennzeichen der Ordner kommt aus `LIST` (`/` bei den meisten, `.` bei
Courier und Dovecot); Umlaute gehen durch `utf7_kodieren()`, das
Gegenstück zum Lesen, das es bis heute nicht gab; und `\Deleted` bleibt
beim Übertragen der Marken absichtlich draußen.

**`Hit` trägt jetzt `message_id`.** Ohne sie müsste für die
Duplikatprüfung jede Mail von der Platte gelesen werden, bevor
feststeht, ob sie überhaupt gebraucht wird.

### Und wie man an neue Fassungen kommt, steht jetzt auch da

Stephans Frage nach dem Release: Wie kommt man unter Linux an ein
Update? Die Antwort war `git pull` und `./install.sh` – und **nirgends
aufgeschrieben.** Jetzt in
[docs/erste-schritte.md](docs/erste-schritte.md) als Abschnitt 8, mit
dem Satz, der die eigentliche Sorge beantwortet: Archiv, Kontenliste,
Suchindex und Schlüsselbund bleiben unangetastet.

**Solange es keine Pakete gibt, bleibt das die Hürde vor jeder neuen
Fassung** – fünf bis fünfzehn Minuten, weil die Oberfläche jedes Mal neu
geholt wird. Für Stephan in Ordnung, für einen Anwender nicht. Steht bei
den Paketen in der TODO.

### Was als Nächstes ansteht

Die TODO ist an den zwei Stellen abgehakt, und der veraltete Abschnitt
»Für die 1.2« heißt jetzt »Für eine der nächsten Fassungen« – so
veraltet er nicht wieder.

Oben stehen: das Testpostfach mit 500.000 Mails (Stephans
Entscheidung), die Rückfrage zum PDF-Betrachter, Gmail/OAuth2 – und die
Fenstergrößen am echten Bildschirm, die ohne Stephan nicht zu prüfen
sind.

**Der Vorbehalt, der mit der 1.3.0 dazugekommen ist:** Der Weg ins
Postfach ist gegen `tests/fake_imap.py` geprüft, nicht gegen einen
echten Server. Derselbe Satz wie bei OAuth2 und bei JMAP – hier wiegt er
schwerer, denn zum ersten Mal schreibt MailBurg *viele* Nachrichten in
ein fremdes Postfach. Er steht im Release-Text und gehört stehen
gelassen, bis es jemand ausprobiert hat.

## Hier war Schluss (Stand 2026-09-03, nachts)

**Der Weg aus dem Archiv hinaus, erste Hälfte: auf die Platte.**
`core/zurueckspielen.py`, `ui/zurueckspielen.py`, `mailburg
zurueckspielen`, [docs/zurueckspielen.md](docs/zurueckspielen.md). 1615
Tests grün, `werkzeuge/lesbarkeit.py` ohne Befund. **Noch nicht
veröffentlicht** – die 1.2.1 ist die letzte Fassung draußen.

### Warum die Platte zuerst kam, und nicht IMAP

Der Rückmelder wünschte sich »ein Restore wie in MailStore Home«.
Stephans Frage dazu war berechtigt: Passt das überhaupt zum Konzept?
**Es ist das Konzept** – `core/rueckgabe.py` sagt seit dem 26.08.: »Ein
Archiv, aus dem nichts wieder herauskommt, ist ein Grab.«

Der Unterschied ist die Menge, und dort steckt ein technischer Haken,
der die Reihenfolge bestimmt hat: **`APPEND` legt jedes Mal eine neue
Kopie an.** Wer zweimal in dasselbe Postfach restauriert, hat alles
doppelt, und die neuen UIDs identifizieren nichts. Auf der Platte
schreibt MailBurg die Zieldateien selbst und kann deshalb vorher
nachsehen – der Dateiname enthält den Hash der Nachricht.

**Das ist die Eigenschaft, um die es ging**, und dafür gibt es Tests in
jedem Format: derselbe Lauf zweimal schreibt nichts doppelt, ein
abgebrochener setzt fort, ein zweiter holt Neues nach.

### Drei Entscheidungen, die nicht ohne Grund aufgemacht werden sollten

**MBOX ist als einziges Format nicht bytegenau**, und das steht überall
dabei – im Modulkopf, in der Anleitung, im Dialog, in der Meldung der
Kommandozeile. Eine Zeile, die mit »From « beginnt, muss ein »>«
bekommen, sonst gälte sie als Anfang der nächsten Nachricht. Für ein
Archiv, das Bytegenauigkeit verspricht, ist das eine Aussage, die man
nicht verschweigt.

**Bei MBOX liegt eine Beiakte neben der Datei** (`.mailburg-bestand`).
Im Format ist kein Platz für eine Kennung, und eine hineinzuschreiben
hieße, die Mails zu verändern. Wer die Beiakte löscht, bekommt beim
nächsten Lauf Duplikate – das steht in der Anleitung.

**Eine Mail, die an mehreren Stellen lag, wird einmal geschrieben.** Bei
Gmail und Proton ist Mehrfachablage der Normalfall: Jedes Etikett ist
ein weiterer Fundort. Wer alle schreibt, hat dieselbe Rundmail fünfmal.
Genommen wird der erste Fundort, die Zahl steht im Bericht.

### Neu in `Index`: `fundorte(digest, sicht=…)`

Und **prompt vom Wächtertest gemeldet**, weil sie in
`tests/test_sicht.py` noch nicht eingetragen war. Genau dafür ist er da:
Die Ordnerliste einer sichtbaren Mail verriete sonst, in welchen fremden
Postfächern sie sonst noch liegt.

### So geht es weiter

Der zweite Teil ist **Zurückspielen per IMAP**, und der Kern ist dafür
vorbereitet: Auswahl, Fortschritt, Abbruch, Bericht und Journaleintrag
hängen nicht am Zielformat. **Was fehlt, ist eine Klasse neben
`_Maildir`, `_Mbox` und `_Eml`**, die in ein Postfach schreibt und
vorher einmal nachsieht, was dort liegt (`UID SEARCH HEADER Message-ID`
je Ordner). Die vollständige Liste – Ordner anlegen, Trennzeichen aus
`LIST`, Datum im `APPEND`, Mails ohne `Message-ID` – steht in der
[TODO.md](TODO.md) unter »Zurückspielen per IMAP«.

## Nach der 1.2.0: das dritte Feedback (2026-09-03, spätabends)

**JMAP ist gelaufen – gegen einen echten Server.** Der Anwender, der es
angestoßen hatte, hat ein **Stalwart** aufgesetzt, 5.000 Testmails
hochgeladen und abgerufen: 200 Mails in unter fünf Sekunden. Damit fällt
der Satz »noch nie gegen einen echten Anbieter gelaufen«, der seit der
1.1.0 an sechs Stellen stand (README beide Sprachen, `sources/jmap.py`,
`docs/jmap.md`, `ui/hilfe.py`, `tests/test_jmap.py`, TODO beide
Sprachen).

**Er fällt nicht ganz, und das ist wichtig:** Fastmail bleibt offen.
Dort meldet man sich mit einer Zugriffsmarke an statt mit Benutzername
und Passwort, und die Ordnerrollen kommen von einem fremden Anbieter –
zwei Stellen, an denen Stalwart nichts beweist.

**Der Fehler des Abends steckte in `install.sh`.** »Ich kann es nach der
Installation nicht via Konsole starten, aber das liegt vermutlich an
fish.« Es lag an fish, und der Fehler war unserer, doppelt:

1. Das Skript prüfte **seinen eigenen** Suchpfad, also den von bash.
   Viele Distributionen tragen `~/.local/bin` in `/etc/profile` ein, das
   fish nicht liest – bash findet den Ordner, das Skript schweigt, und
   in der Shell des Anwenders fehlt er trotzdem.
2. Der Hinweis nannte `~/.bashrc`, eine Datei, die weder fish noch zsh
   anfassen. **Ein Hinweis auf die falsche Datei ist schlimmer als
   keiner** – wer die Zeile dort einträgt, sucht danach überall, nur
   nicht mehr im Suchpfad.

Dieselbe Klasse wie die drei Befunde vom Nachmittag: **Eine Prüfung, die
nicht das misst, was sie zu messen vorgibt.** Der Test dazu führt den
Block wirklich aus (`tests/test_install.py`), statt seinen Text zu
lesen – ob eine Fallunterscheidung stimmt, sieht man ihr nicht an.

**Offen und Stephans Entscheidung:** Der Rückmelder bietet ein
Testpostfach mit bis zu 500.000 Mails an. Das beantwortet die
Suchgeschwindigkeit bei einer halben Million, ohne auf MailStore und die
Windows-VM zu warten. Und er wünscht sich **Restore als eigenen
Vorgang** – Massenrückgabe in ein frei gewähltes Ziel, unabhängig von
der Herkunft. Beides steht ausführlich in der TODO.

## Hier war Schluss (Stand 2026-09-03, Donnerstag abends)

**1.2.0 ist getaggt.** Sie besteht fast vollständig aus einer einzigen
Rückmeldung – Fedora Silverblue, MailBurg in einer Toolbox, Umsteiger
von Thunderbird auf Evolution.

### Die Lehre dieses Tages

**Zwei Anwender an zwei Tagen haben mehr gefunden als alles Geplante.**
Und dreimal war der Befund derselbe: Ein Kommentar im Code versprach
etwas, das der Code nicht tat.

- `core/index.py` erklärt seit jeher, dass WAL dafür da ist, »während im
  Hintergrund archiviert wird« zu lesen. Abgeholt hat es niemand – der
  Postfachbaum blieb den ganzen Abruf über leer.
- `paths.geoeffnet_dir()` begründet sorgfältig, warum eine Mail nicht in
  `/tmp` gehört. Der PDF-Anhang derselben Mail ging trotzdem dorthin.
- `erkennung.py` nannte den Schlüssel für den erkannten PDF-Text; der
  Neuaufbau holte ihn nie.

**Wer einen Kommentar schreibt, der eine Zusage macht, schuldet einen
Test dazu.** Sonst ist er eine Behauptung, die mit den Jahren falsch
wird, ohne dass es auffällt.

### Was in der 1.2.0 steckt

**Der Postfachbaum wächst während des Abrufs mit** (`MITWACHSEN`,
3 Sekunden, `_baum_fuellen(auswahl_halten=True)`). Vorher stand
minutenlang »0 Mails im Archiv · noch nicht abgerufen« neben »2800
geholt« – zwei Anzeigen im selben Fenster, die einander widersprachen.

**Anhänge liegen nicht mehr in `/tmp`** (`rueckgabe.anhang_oeffnen`),
sondern im Cache-Ordner mit `0600`, und werden aufgeräumt. Beim
Aufräumen erkennt MailBurg seine eigenen Dateien an den acht
Zufallsziffern im Namen – ein bestehender Test hielt dagegen, als ich
einfach alles löschen wollte.

**Lokale Mailordner einlesen gibt es jetzt im Fenster**
(`ui/einlesen.py`). Die Quellen konnte MailBurg von Anfang an, nur über
die Kommandozeile. **Der Wunsch nach etwas Vorhandenem ist ein Befund
über die Oberfläche, nicht über den Funktionsumfang.**

**Strg+F in der geöffneten Nachricht** (`ui/suchleiste.py`). Beim Bauen
stand dort zuerst `[QKeySequence.Find, QKeySequence("Strg+F")]` –
dieselbe Folge zweimal, also mehrdeutig, also wirkungslos: **genau der
Fehler vom 31.08. bei Strg++**, vier Tage später wiederholt. Und »Strg«
kennt Qt nicht, es heißt »Ctrl«; eine so geschriebene Folge ist leer und
tut nichts, ohne dass Qt meckert. Dafür gibt es jetzt einen
Wächtertest, der die Aktionen des **echten** Fensters durchgeht.

**Evolution** – lokale Ordner (Maildir++, Wurzel ohne `cur/`) und Konten
(`.source`-Dateien, GKeyFile). Zwei Fallstricke: `configparser` macht
Schlüssel klein, Evolution schreibt sie groß (`optionxform = str`); und
im selben Verzeichnis liegen Adressbücher und Kalender.

**Und ein Fehler, der seit der ersten Fassung drinsteckte:** Beim
Einlesen eines Maildirs ging der Lesezustand verloren. Maildir kodiert
ihn hinter `:2,`, Pythons `mailbox.Maildir` schneidet das bei `keys()`
ab – zerlegt wurde trotzdem der Schlüssel, was **immer** leer ergab.
Jede eingelesene Mail landete als ungelesen im Archiv. Gefunden nur,
weil ich für Evolution einen Test schrieb, der den Zustand mitprüft.

### Zwei Stellen, die jetzt allein entscheiden

`sources.quelle_fuer()` (IMAP oder JMAP) und `uebernahme.alle_quellen()`
(Thunderbird oder Evolution). Beide aus demselben Grund: Vorher nannte
jeder Aufrufer das eine Programm beim Namen, und das nächste hätte man
drei- oder fünfmal ergänzen und beim letzten vergessen.

## Hier war Schluss (Stand 2026-09-03, Donnerstag)

**1.1.0 ist getaggt und veröffentlicht.** Sie bringt JMAP, die Struktur
in der Oberfläche und die RFC-3161-Zeitstempel. 1507 Tests grün, ohne
Zusatzpakete 1486 mit 486 übersprungenen.

### JMAP, und warum es für ein Archiv lohnt

`sources/jmap.py`, Anleitung in [docs/jmap.md](docs/jmap.md). Der Gewinn
ist `Email/changes`: **IMAP kann nicht sagen, was sich geändert hat.**
MailBurg baut die Frage über die höchste bekannte Nachrichtennummer je
Ordner nach – eine Näherung, bei der nachträglich einsortierte Mails
durchrutschen. JMAP kennt einen Zustand und beantwortet die Frage in
einer Anfrage.

Drei Festlegungen, die nicht ohne Kenntnis des Grundes aufgemacht
werden sollten:

**Die Rohnachricht kommt über `downloadUrl`, nicht aus dem JSON.** Die
zerlegte Fassung wäre bequemer und für ein Archiv wertlos – die
DKIM-Signatur wäre dahin.

**Ordner werden über ihre Rolle beurteilt, nicht über den Namen.** Ein
Ordner heißt je nach Sprache »Papierkorb«, »Trash« oder »Corbeille«,
seine Rolle heißt überall `trash`. Der Gmail-Fall (`all` enthält alles
doppelt) fällt damit von selbst mit ab.

**Es gibt genau eine Stelle, die entscheidet, wie abgerufen wird:**
`sources.quelle_fuer()`. Vorher erzeugten fünf Stellen eine
IMAP-Verbindung von Hand. Die sechste, die später dazukäme, wüsste von
JMAP nichts – und das merkte der Anwender als das Merkwürdigste, was
ein Programm tun kann: Es funktioniert an vier Stellen und an der
fünften nicht.

**Noch nie gegen einen echten Anbieter gelaufen.** Geprüft ist alles
gegen `tests/fake_jmap.py`, also gegen meine eigenen Annahmen –
derselbe Satz wie bei OAuth2, und er stimmt dort wie hier. Fastmail
bietet ein kostenloses Probekonto; das wäre der Weg.

**Ein Fehler, der dabei auffiel und älter ist als JMAP:** Der
Schlüsselbund-Eintrag heißt `benutzer@server`. Wer sich mit einer
Zugriffsmarke anmeldet, hat keinen Benutzer, und alle Fastmail-Konten
zeigen auf dieselbe Adresse – zwei Konten hätten sich stillschweigend
überschrieben. Jetzt tritt der Kontoname an die Stelle.

### Was das erste Nutzer-Feedback gebracht hat

Vier Punkte aus dem Linux-Guides-Forum, **drei davon echte Fehler.**
Das ist dieselbe Lehre wie am 31.08. mit Stephans Meldungen: Diese
Fehlerklasse findet kein Test, den ich mir ausdenke.

Der vierte war Geschmack und der wichtigste: »Für meinen Geschmack
fehlen da ein paar Rahmen oder farbliche Abhebungen.« Jetzt heben sich
Suchbereich, Postfachbaum, Nachrichtenkopf und Statuszeile ab, und die
Griffe der Teiler sind sichtbar – **vorher wusste niemand, dass sich
die Bereiche verschieben lassen.**

**Alle Farben kommen aus der Systempalette**, ein Wächtertest prüft das
Stylesheet Wert für Wert. Feste Farbwerte säßen im dunklen Thema oder
bei einem Hochkontrast-Thema falsch.

Dabei fiel auf, dass **die Bilder in den Anleitungen ein anderes
MailBurg zeigten als das Programm** – `werkzeuge/screenshots.py` setzte
das Stylesheet gar nicht.

### Zwei Dinge, die Anwender ins Terminal geschickt hätten

**Der Neuaufbau des Index verlor den erkannten PDF-Text.** Der Kommentar
in `erkennung.py` sagte seit jeher, welcher Schlüssel dafür da ist;
abgeholt hat ihn niemand. Nach der 1.0 baute jeder seinen Index neu –
und fand seine Scans nicht mehr, ohne Meldung.

**Eine verwaiste Sperrdatei sperrte dauerhaft aus.** Stephan hat sie an
seinem Geschäftsarchiv getroffen: Vorgang 9814 gab es längst nicht
mehr. MailBurg räumt sie jetzt selbst weg, wenn Rechner und Vorgang das
zulassen – und **wo es nicht sicher ist, fragt es**, statt den Anwender
mit einem Pfad ins Terminal zu schicken. Vier Lagen, nur die letzte
braucht eine Entscheidung.

### Und der Begriff »Server Edition« ist aus der Anwender-Doku raus

Stephans Urteil: Das schreckt ab. Die Anleitungen heißen jetzt »Das
Archiv im Browser«. Im Code bleibt er (Modulname, Windows-Dienst), in
CHANGELOG und TODO auch – das sind Protokolle.

**Dabei fiel auf, dass der Dienst im README gar nicht vorkam.** Gebaut
seit dem 31.08., aber wer nur die Übersicht las, erfuhr nichts davon.
Und das rote Wappen unter `assets/server/` wird **an keiner einzigen
Stelle im Programm benutzt** – seit heute steht es wenigstens über den
beiden Anleitungen. Der Rest steht in der TODO.

## Hier war Schluss (Stand 2026-08-31, Montag abends)

**1.0.0 ist getaggt, 1.0.1 vorbereitet.** Der Tag `v1.0.1` steht auf
GitHub, veröffentlicht ist er noch nicht – das löst auch den Bau der
`MailBurg.exe` aus. Notizen dafür liegen im Sitzungsordner.

### Der Tag in einem Satz

Vormittags Verschlüsselung und Gesprächsverlauf, nachmittags die 1.0,
abends sechs Runden Oberfläche – und die haben mehr gebracht als alles
Geplante zusammen.

### Was Stephans Meldungen zutage gefördert haben

Er hat die 1.0 an seinem echten Archiv gestartet, und **jede einzelne
Meldung war ein echter Fehler.** Das ist die Lehre des Tages: Diese
Fehlerklasse findet kein Test, den ich mir ausdenke, sondern nur
jemand, der das Programm benutzt.

**Das Fenster ging beim Neuaufbau einfach zu.** Während des Aufbaus ist
`archiv` absichtlich `None`; `ui/app.py` las das als »lässt sich nicht
öffnen« und beendete das Programm. Dazu startete der Arbeitsfaden vor
der Ereignisschleife – derselbe Fehler wie am 28.08. beim ersten Abruf,
und die Begründung stand seitdem zwei Zeilen weiter in derselben Datei.

**Strg++ vergrößerte nichts.** `QKeySequence.ZoomIn` *ist* unter Linux
Strg++, und daneben stand dasselbe noch einmal von Hand. Qt hält zwei
gleiche Kürzel für mehrdeutig und löst dann keines aus. Das Menü zeigte
es brav an – deshalb sucht man dort zuletzt.

**Die Schriftgröße wirkte nur auf das Hauptfenster.** Menüs, Dialoge
und das Lesefenster sind in Qt eigene Fenster, keine Kinder. Und Qt
führt neben der Anwendungsschrift eine je Widgetklasse: Breeze setzt
Menüs auf 14 pt, die Anwendung auf 9 – wer beide gleichsetzt, macht die
Menüs beim Vergrößern erst einmal *kleiner*.

**Und viermal Text, der nicht hineinpasste.** Auswahlfelder so breit
wie das Layout statt wie ihr Inhalt; aufgeklappte Listen, die bei
120 px blieben; Dialoggrößen als geratene Zahlen; umbrechende Texte,
die zusammengedrückt wurden, weil Qt nur auf ausdrückliche Ansage nach
der nötigen Höhe fragt (`setHeightForWidth`).

### Zwei Regeln, die daraus folgen

**In der Standardgröße wird nicht gerollt.** Stephans Regel. Der
Rollbereich ist die Rückfalllinie für kleine Bildschirme, nicht der
Normalzustand. Mein erster Anlauf hat das verletzt und es dadurch
*schlimmer* gemacht: Der Dialog ging winzig auf, man sah drei Zeilen.

**Geratene Maße sitzen falsch, sobald jemand die Schrift ändert.** Und
die lässt sich in MailBurg einstellen. Jede feste Pixelzahl in einem
Dialog ist ein Fehler, der auf sein Auftreten wartet.

### Das Werkzeug dafür

```bash
QT_QPA_PLATFORM=offscreen python3 werkzeuge/lesbarkeit.py
```

Öffnet neun Fenster, misst nach, meldet abgeschnittenen Text und
Rollbalken, die es nicht geben dürfte. Bei 9 bis 24 pt ohne Befund.

**Aber Vorsicht, und das steht auch in der TODO:** Qt meldet offscreen
»does not support propagateSizeHints«. Fenstergrößen sind dort nicht
verlässlich zu messen. Was das Werkzeug findet, ist echt; was es *nicht*
findet, ist damit nicht erledigt. Der letzte gemeldete Punkt – die
Breite bei fünffach vergrößerter Schrift – konnte deshalb nicht
abschließend geprüft werden.

### Neu an diesem Abend

`core/der.py` und `core/zeitstempel.py` – **Zeitstempel nach RFC 3161**.
ASN.1 von Hand, weil der Kern ohne Fremdpakete auskommen soll; geprüft
gegen `openssl`, das die Anfragen liest und die Stempel verifiziert. Ein
echter Dienst wurde noch nie gefragt.

## Hier war Schluss (Stand 2026-08-31, Montag)

**Die Fassung steht auf 1.0.0**, der Tag ist noch nicht gesetzt – das
Release macht Stephan, sobald er die `MailBurg.exe` geprüft hat. Sie
entsteht von selbst, sobald ein Release veröffentlicht wird
(`windows-exe.yml` hört auf `release: published`).

Der Tag brachte: die **Server Edition**, den **Gesprächsverlauf** und die
**Archivverschlüsselung**. 1423 Tests mit allen Zusätzen, 1406 ohne.

### Was 1.0 heißt und was nicht

Stephans Entscheidung vom 31.08.: Die Verschlüsselung bleibt drin, aber
als das, was sie ist – **neu und im Alltag nicht erprobt**. Und **macOS
wandert in die 1.1**.

Das Muster dafür gibt es im Projekt längst: OAuth2 steht seit der 0.10
im Release mit dem Satz, dass sich damit an einem echten Konto noch
niemand angemeldet hat. Es blockiert nichts, weil dabeisteht, woran man
ist.

**Bei der Verschlüsselung wiegt das schwerer**, denn der Schaden ist ein
anderer: Bei OAuth2 heißt »geht schief«, dass der Abruf nicht läuft –
auffällig und reparierbar. Hier heißt es, dass das Archiv weg ist.
Deshalb steht der Hinweis nicht im README, wo ihn niemand vor dem Klick
liest, sondern an den vier Stellen, an denen man sich entscheidet:
Assistent, Passwortdialog, `mailburg anlegen`, Handbuch.
`krypto.hinweis_neu()` hält den Wortlaut an einer Stelle, ein Test wacht
darüber, dass er überall ankommt.

**Wer ihn streicht** – also sobald jemand damit im Alltag gearbeitet hat
–, muss den Test in `tests/test_krypto.py` mitziehen. Ein Hinweis, der
stehen bleibt, nachdem er nicht mehr stimmt, ist schlimmer als keiner.

### Die Archivverschlüsselung

`core/krypto.py`, `core/passwort.py`, Anleitung in
[docs/verschluesselung.md](docs/verschluesselung.md). **Gebaut und
getestet, aber im Alltag noch nie benutzt** – das ist der wichtigste
Satz dazu.

Vier Entscheidungen, die nicht ohne Kenntnis des Grundes aufgemacht
werden sollten:

**Zwei Ebenen.** Die Daten hängen an einem zufälligen Archivschlüssel,
der eingewickelt in `archive.json` liegt – einmal mit dem Passwort,
einmal mit dem Notschlüssel. Hinge alles direkt am Passwort, müsste ein
Wechsel 700.000 Dateien neu schreiben.

**Auch die Dateinamen.** Der Klartext-Hash hätte verraten, ob eine
bestimmte Mail im Archiv liegt – berechnen kann ihn jeder, der die Mail
hat.

**Das Journal gehört mit darunter.** In ihm stehen Absender, Betreff,
Postfach und Ordner. Verschlüsselt wird Zeile für Zeile; die Hash-Kette
rechnet weiter über den Klartext und bleibt unverändert prüfbar.

**scrypt, nicht Argon2id** – gegen den ursprünglichen Entwurf in der
TODO. Es steckt in `hashlib`, und ein Archivprogramm sollte in zwanzig
Jahren ohne nachzuinstallierende Pakete an seine Schlüssel kommen.

**Die offene Flanke ist der Suchindex.** Er liegt außerhalb des Archivs
und enthält Betreff, Absender und Volltext im Klartext. Für den Anlass
(Sicherung in der Cloud, verlorene Platte) genügt der Zuschnitt, weil er
nicht mitwandert; auf einem Server hilft nur eine verschlüsselte Platte.
Der Hinweis steht in `krypto.hinweis_suchindex()` und muss in jeder
Anleitung auftauchen, solange das so ist.

### Was dabei an alten Fehlern hochkam

**Ein Stromausfall mitten im Abruf sperrte das Archiv aus.** Der
Docstring von `journal._scan_tail` behauptete seit jeher, eine
angefangene letzte Zeile zu überspringen – der Code tat es nicht. Jetzt
wird sie übersprungen *und aus der Datei entfernt*; ohne das Zweite
klebte der nächste Eintrag an ihr fest.

**Die Kennwerte der Schlüsselableitung** wurden aus dem Modul gelesen,
der Schlüssel aber mit den Vorgabeargumenten erzeugt. Wer `SCRYPT_N`
erhöht hätte, hätte Archive angelegt, die sich mit dem richtigen
Passwort nicht mehr öffnen lassen.

**Und ein Namenskonflikt**, den nur der Durchstich über die echte
Kommandozeile fand: Es gab schon ein `_passwort_erfragen` für
Postfächer, das meines überschrieb. Kein Test der Verschlüsselung hätte
das gefunden, weil keiner durch die Kommandozeile ging – jetzt gibt es
`tests/test_verschluesselung_cli.py`.

**Die CI hatte zweimal recht.** Der erste Job installiert bewusst nichts
außer dem Kern; dort fehlten `cryptography` *und* PySide6. Lokal in der
venv ist alles da, also sah ich nichts. **Nachstellen lässt sich das so:**

```bash
mkdir -p /tmp/blocker && printf 'raise ImportError()\n' > /tmp/blocker/cryptography.py
PYTHONPATH="/tmp/blocker:$PWD" python3 -m unittest discover -s tests
```

**Die Server Edition steht** (`mailburg/server/`), bis auf die
Archivverschlüsselung: Zugänge im Archiv (`core/benutzer.py`), die
Rechteprüfung (`core/sicht.py`), Tresor ohne Schlüsselbund
(`core/tresor.py`), Dienst, Weboberfläche mit Anmeldung, Suche, Lesen,
Anhängen und Suchmaske. Anleitungen: [docs/server.md](docs/server.md)
und [docs/server-einrichten.md](docs/server-einrichten.md).

**Die eine Regel, die dort nicht aufgeweicht werden darf:** Die
Rechteprüfung steht *in* der Abfrage, nicht dahinter. Nachträglich zu
filtern wäre bequemer und falsch – schon die Trefferzahl »191« verriete,
dass es Post gibt, die man nicht sehen darf. Ein Wächtertest
(`tests/test_sicht.py`) schlägt an, wenn eine neue lesende Methode ohne
`sicht=` auskommt; er hat an diesem Tag zweimal zu Recht zugeschlagen.

**Der Gesprächsverlauf** hängt an `References`/`In-Reply-To`, nie am
Betreff. Die Kennungen stehen mal mit spitzen Klammern in der Mail und
mal ohne – wer sie übernimmt, wie sie kommen, baut Verläufe, die nie
zusammenfinden. Sie werden deshalb entklammert abgelegt
(`extract/message.py`, Property `gespraech`).

**Der Preis dafür, und der wichtigste Satz hier:** `SCHEMA_VERSION` ging
von 1 auf 2. **Ein Archiv aus 0.12 lässt sich nicht mehr öffnen, bis
`mailburg neuaufbau` gelaufen ist.** Das ist Absicht – die Spalte leer
nachzurüsten hätte Verläufe erzeugt, die vollständig aussehen und halb
sind. Wer eine Schemaänderung macht, muss dann aber auch alles
mitziehen, was daran hängt; drei Dinge fielen erst beim Nachfassen auf:

- Der Fehler wurde **nirgends gefangen** – die Kommandozeile warf einen
  Traceback, und wer nach einer Aktualisierung sein Archiv nicht mehr
  aufbekommt, denkt an Datenverlust, nicht an einen Index.
- **Die Sperrdatei blieb liegen.** `_acquire_lock()` läuft vor dem
  Öffnen des Index; fliegt der Konstruktor danach, ruft niemand mehr
  `close()`. Aus einem Problem wurden zwei, das zweite ohne Grund.
- **`mailburg neuaufbau` wäre selbst gescheitert** – der Weg aus der
  Meldung lief in denselben Fehler. Dafür gibt es jetzt
  `Archive.open(..., index_verwerfen=True)`.

Alle drei stehen in `tests/test_index_fassung.py`.

**Was noch offen ist:** die Verschlüsselung an einem echten Archiv
erproben (die Liste dazu steht in der TODO), der Suchindex, Outlook-PST,
Pakete für alle drei Systeme, RFC-3161-Zeitstempel und die Frage nach
dem Betreffmuster als Regelfeld. Windows Server und die 700.000 Mails
sind auf **Mitte Oktober 2026** vertagt.

## Hier war Schluss (Stand 2026-08-30, Sonntag)

**0.11.0 ist veröffentlicht**, mit `MailBurg.exe` am Release. Der Tag
brachte zwei Dinge: die Einstufungsregeln und den ersten Durchgang auf
einem richtigen Windows-11-Rechner.

**Die Tests lokal vollständig laufen lassen** – bitte so, nicht mit dem
System-Python:

```bash
PYTHONPATH="$PWD" QT_QPA_PLATFORM=offscreen \
  ~/.local/share/mailburg/venv/bin/python3 -m unittest discover -s tests
```

Das sind 1087 Tests. Mit `python -m unittest` aus dem Systempfad sind es
1062, und 325 werden **stillschweigend übersprungen** – PySide6 liegt
nur in der venv von `install.sh`. Wer das nicht weiß, prüft einen ganzen
Tag lang an der Oberfläche vorbei und merkt es erst in der CI. Genau das
ist am 30.08. passiert.

**Die Einstufungsregeln** (`core/regeln.py`, `mailburg regeln`, *Post →
Beim Aufnehmen einstufen …*, [docs/regeln.md](docs/regeln.md)). Drei
Festlegungen, die nicht wieder aufgemacht werden sollten, ohne den Grund
zu kennen: Geholt wird alles – die Regel bestimmt nur die Einstufung.
Die erste passende gewinnt. Bestehende Post bleibt unangetastet.

**Windows auf echter Hardware.** Alles lief. Zwei Ergebnisse, die eine VM
nicht liefern konnte:

*Der Start dauert Sekunden, nicht zwanzig.* Fast die ganze Wartezeit in
der VM ging auf die Virtualisierung. Damit ist die einzelne Datei als
Vertriebsform bestätigt.

*Das Startbild ist ausgebaut.* Es erschien auch dort nicht – aber
entfernt wurde es, weil der Anlass weg ist, nicht weil der Fehler
unlösbar wäre. Die Spuren stehen in `werkzeuge/mailburg.spec`.

**Zwei Fehler, die kein Test gefunden hätte**, beide aus einem
Bildschirmfoto von Stephan:

*Die OEM-Codepage.* Fehlermeldungen von `schtasks.exe` kamen als
»enth„lt« statt »enthält« an – Konsolenprogramme unter Windows schreiben
in cp850, Python las cp1252. `werkzeuge.konsolenkodierung()` gibt die
Kodierung jetzt überall an, wo ein fremdes Programm im Textmodus
ausgelesen wird.

*Der Sicherungsdialog überschrieb die eigene Einstellung.* Er las beim
Öffnen nicht zurück, wie oft gesichert wird und wie viele Stände
bleiben. Aus »monatlich mit zwei Ständen« wurde beim nächsten Übernehmen
ein tägliches Überschreiben derselben Datei.

**Die Lehre des Tages steht in der TODO:** Das erste Bildschirmfoto
zeigte einen Fehler, der seit dem Vortag behoben war – die gelaufene
`.exe` war älter als die Korrektur. Wer eine Prüfung ansetzt, baut
vorher neu und notiert sich den Commit.

**Neu und nicht offensichtlich:** `werkzeuge/vorfuehrarchiv.py` legt ein
Archiv mit 27 erfundenen Mails an, das *stehen bleibt* – für
Vorführungen und Videos. `screenshots.py` taugt dafür nicht, es räumt
sein Archiv wieder weg. Ein Test wacht darüber, dass jede Adresse auf
`.example` endet.

**Am späten Abend noch dazugekommen:** der Rückweg »In Mailprogramm
öffnen« – damit stehen alle drei Wege aus dem Archiv. Die Frage war
nicht das Öffnen, sondern die `.eml`, die dabei entsteht: Sie liegt im
Zwischenspeicher des Benutzers mit `0700`/`0600`, nicht in `/tmp`, und
verschwindet beim nächsten Öffnen (nach vier Stunden) oder beim Beenden.

**Und beide Sprachen sind wieder gleichauf.** `TODO.en.md` war seit dem
26.08. stehengeblieben. Stephans Ansage dazu: »alles bitte in Deutsch
und Englisch im Repo auf dem Laufenden halten« – wer die deutsche Datei
ändert, zieht die englische im selben Zug nach. Beide stehen jetzt in
derselben Ordnung, damit ein Abgleich überhaupt möglich bleibt.

**Als Nächstes:** Die Liste *Muss vor dem ersten echten Einsatz
passieren* enthält nur noch eine Frage, und die ist bewusst offen
(Betreffmuster als Regelfeld). Der MailStore-Import mit den 700.000
Mails ist vertagt – Stephan kann das frühestens Ende Oktober 2026
prüfen; er steht deshalb unter »Vertagt« und nicht in der laufenden
Liste.

## Hier war Schluss (Stand 2026-08-29, Samstag)

**OAuth2 ist gebaut** – Ablauf, Bedienung auf beiden Wegen,
[docs/oauth2.md](docs/oauth2.md). PKCE nach RFC 7636, Marken im
Schlüsselbund, Erneuerung mit Vorlauf beim Verbindungsaufbau.

**Was offen bleibt, und das ist der wichtigste Satz hier:** Niemand hat
sich damit bisher bei einem echten Anbieter angemeldet. Geprüft ist der
Ablauf gegen einen nachgebauten Anbieter auf dem eigenen Rechner.
Stephans Konten liegen auf eigenen Servern und bei Proton – ein
Microsoft-Konto zum Testen gibt es nicht. In der Anleitung steht das
ausdrücklich; wer den Text ändert, soll diesen Satz stehen lassen,
solange er stimmt.

Zweite offene Frage: ob Googles Testmodus die Erneuerungs-Token
wirklich nach sieben Tagen verfallen lässt. Falls ja, taugt OAuth2 bei
Gmail nicht für den Zeitplan – die Anleitung rät dort deshalb weiterhin
zum App-Passwort.

**Die Historie ist bereinigt** (2026-08-29). Plattenseriennummer,
Domain, Mailserver, Firmenname und Ordnerpfade sind aus allen 188
Commits verschwunden – geprüft an einem frischen Klon von GitHub. Die
Sicherung des alten Standes liegt außerhalb des Repos unter
`/mnt/…/MailBurg-vor-bereinigung-2026-08-29.bundle`.

Wer künftig etwas hinzufügt: **Keine echten Adressen, Server oder
Pfade.** Für Beispiele gibt es `example.org`, `example.com` und
`example.net` – die sind nach RFC 2606 dafür reserviert. Die
Autorennennung in LICENSE, `pyproject.toml` und `ui/info.py` ist davon
ausgenommen; ein Urheber darf genannt werden.

**Noch offen aus der Verabredung:** Bilder. Stephan will sie zum
Schluss, wenn alles andere sauber ist – die Linux-Screenshots in
`docs/bilder/` sind vom 26.08. und zeigen den Assistenten vor den
Änderungen, für Windows fehlen SmartScreen, Hauptfenster und
Zeitplan-Dialog.

### Was der 28.08. gebracht hat

Der Tag zerfiel in zwei Hälften. Vormittags Windows: die `.exe` fertig
gebaut, in einer VM mit einem echten Postfach durchgespielt und dabei
sechs Fehler gefunden, die unter Linux nie aufgefallen wären – darunter
zwei, die den Zeitplan unbrauchbar gemacht hätten. Nachmittags die
GoBD- und DSGVO-Ecke: Einstufen, Fälligkeitsbericht, Auskunftsexport,
Verfahrensdokumentation.

**Die Lehre des Tages steht in den Prüfschritten des Bau-Workflows.**
Der Fehler, dass die `.exe` ihre eigene Kommandozeile nicht kannte, kam
nur ans Licht, weil ein Prüfschritt hängenblieb: Er wartete auf einen
Klick, den auf einem Bauserver niemand macht. Von Hand hätte ich das
Fenster gesehen und für einen Fehlstart gehalten.

**Und eine zweite:** Ein Test prüft, dass jeder Menüpunkt im Handbuch
erklärt ist. Er hat an diesem Tag dreimal zugeschlagen, jedes Mal zu
Recht. Solche Tests sind mehr wert als zehn, die Rechenwege prüfen.

## Hier war Schluss (Stand 2026-08-26, vormittags)

Der dritte Tag war der erste im echten Betrieb – und dabei ist ein
Dutzend Fehler aufgefallen, die keine Testsuite gefunden hätte. Das ist
die Lehre des Tages: **Diese Oberfläche musste einmal von jemandem
benutzt werden, der sie nicht gebaut hat.**

478 Tests, alles auf GitHub. Zwei Archive laufen produktiv auf der
externen Platte `Linux-Mobil`: ein Geschäftsarchiv (AT) mit sieben
Postfächern samt Proton über die Bridge, und ein Privatarchiv mit 1.557
Mails aus Thunderbirds lokalen Ordnern.

**Die drei lehrreichsten Fehler:**

1. **Ein Lambda an einem Signal aus dem Arbeitsfaden.** Qt kann einem
   Lambda keinen Faden zuordnen und ruft es deshalb sofort auf – im
   Arbeitsfaden. Die Zeilen darunter fassten Widgets an und öffneten
   einen modalen Dialog, der nie gezeichnet wurde, aber jede Eingabe
   schluckte. Für Stephan sah das so aus: Fenster verschiebbar, innen
   tot. Die Regel steht jetzt in `ui/arbeit.py`, ein Test verbietet
   Lambdas an diesen Signalen.
2. **`validatePage` warf sich selbst wieder an.** Sie prüft nebenläufig,
   sagt erst Nein und schickt die Seite weiter, sobald die Antworten da
   sind – was `validatePage` erneut aufrief. Sichtbar als flackernde
   Zustandsspalte; unsichtbar bekam der Mailserver bei jedem Umlauf drei
   frische Anmeldungen.
3. **`saveGeometry()` unter Wayland.** Dort darf ein Fenster seine
   Position nicht kennen; Qt schreibt Platzhalter, und
   `restoreGeometry()` stellt sie treu wieder her. Bei jedem Start
   dasselbe 720×720. Größe wird jetzt als Zahl gespeichert.

**Was als Prüfmuster bleibt:** Zustand, der zu früh gesichert wird, ist
falsch – `saveState()` beim Aufbau hält die Breite eines Fensters fest,
das seine Größe noch nicht hat. Und was der Anwender sieht, muss aus
derselben Quelle stammen wie das, was gilt: Der Postfachbaum addierte
Fundorte, die Statuszeile zählte Mails, und beide behaupteten eine
Gesamtzahl.

**Neu an diesem Tag:** Handbuch mit Kapiteln (`ui/hilfe.py`, ein Test
liest die Menüpunkte aus dem echten Menü), Hintergrundabruf aus der
Oberfläche (`core/zeitplan.py`), der Weg zurück ins Postfach
(`core/rueckgabe.py`, `ui/zurueck.py`), sortierbare Trefferliste,
taggenaue Suche mit `seit:`/`bis:`/`am:`.

**Am Nachmittag kam dazu:** Sicherung als eine Datei samt Zeitplan,
Anleitungen mit erzeugten Bildern (`werkzeuge/screenshots.py`),
Menü »Einstellungen«, Schriftgröße einstellbar, parallele Texterkennung.
Version 0.9.0 ist getaggt.

**GuideOS läuft.** Debian mit Cinnamon, apt-Zweig, gnome-keyring – die
zweite Umgebung, die für 1.0 fehlte. Zwei Befunde von dort: Der
Installer schwieg zehn Minuten, während pip PySide6 holte (`-q`), und
im dunklen Thema sind die Kontraste zu schwach. Ersteres behoben,
Zweites teilweise – die Linkfarbe stimmt jetzt, die Schriftgröße lässt
sich einstellen, der Rest kommt vom System-Thema.

**Offen und als Nächstes dran:**

1. **Dunkles Thema auf kleinen Bildschirmen.** Stephans Urteil: „alles
   relativ dunkel, auf 14 Zoll schlecht lesbar, die Unterschiede
   zwischen Hintergrund, Text, Menüs und Links kaum zu erkennen."
   Schriftgröße und Linkfarbe sind gemacht; die Abgrenzung der Bereiche
   noch nicht.
2. **Messung der parallelen Texterkennung** an 431 echten Dokumenten.
   Erwartet: aus einer Stunde werden fünfzehn Minuten.
3. **700.000 Mails** aus dem MailStore-Archiv der Firma. Gerechnet: 2,5
   bis 4 Stunden Import, ~170 GB. Der unbekannte Teil ist, wie MailStore
   die Daten herausgibt – dort würde es scheitern, nicht bei MailBurg.

## Vom zweiten Tag (Stand 2026-08-25, spätabends)

Der zweite Tag ging fast vollständig in die Oberfläche. Sie steht jetzt:
Einrichtungsassistent, Hauptfenster mit Suche und Vorschau, Startbefehl
`mailburg-gui`, Menüeintrag. 322 Tests, alles auf GitHub.

**Offen und als Nächstes dran:**

1. **Der Absturz bei falschen Passwörtern ist nicht gefunden.** Stephan
   hat absichtlich falsche eingegeben, die Oberfläche verschwand
   kommentarlos. Nachgestellt ließ er sich nicht – der reine Fehlerweg
   läuft sauber durch. Eingebaut ist jetzt ein Ausnahmehaken, der
   Programmfehler anzeigt statt sie zu verschlucken; beim nächsten Mal
   sollte also eine Meldung kommen. **Verdacht:** ein QThread, der
   weggeräumt wird, während er noch läuft – klassischer Qt-Absturz, der
   sich nicht als Python-Ausnahme zeigt. Zu prüfen wäre die
   Läuferverwaltung in `ui/assistent.py`, besonders wenn dieselbe Zeile
   zweimal geprüft wird (Zertifikatsvorschlag).
2. Die Oberfläche ist noch nie im Alltag gelaufen, nur in Durchgängen.
3. `mailburg abgleich` fehlt weiterhin – siehe unten.

**Was Stephan an der Oberfläche wichtig war** (gilt für alles Weitere):
Die Ersteinrichtung ist der Moment, in dem Vertrauen entsteht. Lieber
ausführlich als knapp, Fachjargon vermeiden (»meldet nichts nach Hause«
sagt niemandem etwas), keine Formulierung, die Misstrauen voraussetzt,
und nichts behaupten, was die Oberfläche nicht auch zeigt – ein Text,
der Nextcloud verspricht, während nur ein Pfadfeld dasteht, ist eine
halbe Zusage.

## Vom ersten Tag (Stand 2026-08-25 abends)

Alles Committete läuft, 232 Tests grün, alles auf GitHub. Unterbrochen
mitten in einem Arbeitsgang – **angefangen und nicht zu Ende gebracht:**

- **Doku zu Proton und zur Übernahme fehlt noch.** Der Code steht
  (`konten uebernehmen`, `--proton`, `--bruecke`), aber in
  `docs/postfaecher-einrichten.md` steht nichts davon. Dort gehört hin: die
  Bridge muss laufen, sie erzeugt ein eigenes Passwort (das Proton-Kennwort
  taugt nicht), sie braucht ein bezahltes Abo, und ohne laufende Bridge
  scheitert jeder Abruf. Ebenso ein Absatz zu `konten uebernehmen` samt der
  Begründung, warum Passwörter nicht mit übernommen werden.
- **CHANGELOG.md ist für beides noch nicht nachgezogen** – der Abschnitt
  „Unveröffentlicht" endet beim laufenden Abruf.
- **`docs/postfach-entlasten.md` ist verlinkt, aber existiert nicht.**
  `docs/zeitsteuerung.md` verweist darauf.

**Als Nächstes besprochen, noch nicht angefangen:**

1. **`mailburg abgleich`** – der wichtigste offene Punkt. Er soll belegen,
   dass alle Mails vor einem Stichtag im Archiv sind, *bevor* der Mailclient
   sie auf dem Server wegräumt. Ohne ihn ist das Aufräumen in Thunderbird
   eine Hoffnung. Gedachter Weg: je Ordner `UID SEARCH BEFORE <datum>`, jede
   gefundene UID gegen die Fundorte im Index halten, Bericht ausgeben.
   Danach `docs/postfach-entlasten.md` mit dem ganzen Ablauf.
2. **Erprobung an einem echten Postfach.** Der Abruf ist bisher nur gegen
   `tests/fake_imap.py` gelaufen. Stephan hat Konten bei Proton (Bridge auf
   1143), eines auf 993 und sechs auf 143 – gute Gelegenheit.

**Entschieden und nicht mehr zu diskutieren:** kein Passwort beim
Programmstart. Ohne Archivverschlüsselung wäre es Sicherheitstheater (die
Mails liegen als Dateien im Ordner) und machte den Abruf im Hintergrund
unmöglich. Ein Passwort gehört an die Verschlüsselung, und dann pro Archiv.

**Veröffentlichung: noch nicht.** Das Repo bleibt privat, bis der Abruf an
echten Postfächern gelaufen ist. Der Grund ist nicht die Codequalität,
sondern dass Fehler in einem Archivprogramm unbemerkt und unumkehrbar sind:
Was nicht geholt wurde, fällt erst Jahre später auf. Bisher ist alles nur
gegen `tests/fake_imap.py` gelaufen – also gegen meine eigenen Annahmen.

**Zwei Testumgebungen, die Stephan hat.** Sie sollen Verschiedenes abdecken:

- *Manjaro / KDE Plasma / Wayland* – der Echtbetrieb. Acht Konten in
  Thunderbird (eines über die Proton Bridge auf 1143, eines auf 993, sechs
  auf 143), der große Altbestand, der laufende Abruf. Schlüsselbund ist hier
  **ksecretd**, nicht gnome-keyring.
- *GuideOS (Debian 13) / Cinnamon* – die andere Hälfte: der apt-Zweig von
  `install.sh`, gnome-keyring, und der **manuelle** Weg über
  `konten hinzufuegen` ohne Thunderbird-Übernahme. Den ist noch nie jemand
  gegangen. Mit Evolution als Client käme die Maildir-Quelle an echte Daten.
- *Beide zusammen* – endlich prüfbar, was unter „Noch nicht getestet" steht:
  Sperrdatei bei zwei Rechnern an einem Archiv, Index-Neuaufbau auf dem
  zweiten, Nextcloud mit laufendem Synchronisationsclient.

**Kein macOS-Testgerät vorhanden, Windows ebenfalls nicht bestätigt.** Das
README behauptet „Läuft unter Linux, Windows und macOS". Geprüft ist davon
nur, dass Tests und Einrichtung in der CI durchlaufen – der Betrieb auf keiner
der beiden. Und selbst das stimmte bis zum 26.08.2026 nicht: Unter Windows
scheiterte in Wahrheit *jeder* Test, weil das Journal `fsync` auf einem nur
lesend geöffneten Deskriptor aufrief. Die Läufe waren rot, nur sah es niemand. Vorschlag lag Stephan vor, ist **noch nicht entschieden**: den Satz
auf das herunterziehen, was tatsächlich erprobt ist. Passt zur Haltung des
Projekts, nichts zu behaupten, was nicht belegt ist (siehe RECHTLICHES.md).

## Aufbau

```
mailburg/
├── core/
│   ├── archive.py     hält alles zusammen; Anlegen, Öffnen, Aufnehmen, Löschen, Prüfen
│   ├── journal.py     das Protokoll mit der Hash-Kette – das Herzstück
│   ├── store.py       inhaltsadressierte Ablage der Mails
│   ├── index.py       SQLite mit FTS5, zwei Volltextindizes
│   ├── importer.py    der Archivierungslauf, mit Prozesspool für Anhänge
│   ├── accounts.py    Postfächer und Passwörter (Schlüsselbund)
│   ├── sync.py        UIDVALIDITY und vorgemerkte Nachzügler je Ordner
│   ├── retention.py   Aufbewahrungsfristen DE/AT/CH, rein rechnend
│   ├── compress.py    Zstandard mit Rückfall auf LZMA
│   ├── benutzer.py    Zugänge und Rechte – liegen im Archiv, nicht beim Dienst
│   ├── krypto.py      Schlüssel und Hüllen verschlüsselter Archive
│   ├── passwort.py    woher das Archivpasswort kommt: Umgebung, Tresor, Frage
│   ├── sicht.py       woraus die Rechteprüfung in jeder Abfrage entsteht
│   ├── tresor.py      Passwörter ohne Schlüsselbund, für den Server
│   ├── sprache.py     Zahlen und Datumsangaben für Menschen – deutsch, fest
│   ├── rueckgabe.py   eine Mail zurück: ins Postfach, als Datei, ins Programm
│   ├── zurueckspielen.py  viele auf einmal: Maildir, MBOX, eml oder ins Postfach
│   └── paths.py       Verzeichnisse je Betriebssystem
├── bilder.py          wo die Grafiken liegen - für Fenster und Weboberfläche
├── extract/message.py Mails zerlegen; pdf.py, office.py, text.py für Anhänge
├── search/           query.py (Suchausdruck -> SQL), maske.py (Felder ->
│                      Suchausdruck, gemeinsam für Fenster und Browser)
├── server/            dienst.py, lesen.py, seiten.py, sitzung.py,
│                      einstellungen.py, windows_dienst.py
├── sources/           base.py (Schnittstelle), local.py (Thunderbird/Maildir/MBOX),
│                      imap.py (Postfächer)
├── ui/                die Oberfläche: hauptfenster, assistent, konten,
│                      suchmaske, vorschau, hilfe, zeitplan, sichern,
│                      einstufen, fristen, auskunft, anmelden, zugaenge,
│                      archivpasswort
└── __main__.py        Kommandozeile

install.sh / install.ps1   Einrichtung; laufen in der CI wirklich durch
pyproject.toml             Paket und der Befehl "mailburg"
docs/                      Anleitungen für Anwender
```

## Regeln, die aus Fehlern stammen

**Ein Auffangnetz darf keine Auskunft erfinden.** Wer jeden Fehler in
ein leeres Ergebnis verwandelt, macht aus einer Störung eine falsche
Aussage – und die fällt niemandem auf, weil sie aussieht wie ein
Ergebnis. Am 2026-09-07 dreimal an einem Tag:

- `except Exception` um `keyring.get_password` verwandelte einen
  gesperrten Schlüsselbund in »kein Passwort hinterlegt« (sieben
  Postfächer auf einmal).
- Dasselbe Muster verschluckte in `tresor uebernehmen` einen
  NameError – der Befehl meldete fünf Fassungen lang »0 Passwörter
  übernommen«, als wäre der Schlüsselbund leer.
- Und ein `except Exception` in einem Prüfwerkzeug ließ es melden, was
  im Betrieb gar nicht auftrat.

**Die Faustregel:** Ein Traceback sieht aus wie ein Fehler und wird
gemeldet. »Nichts gefunden« sieht aus wie ein Ergebnis und wird
geglaubt. Deshalb eng fangen (`keyring.errors.KeyringError`,
`OSError`), und wo ein Aufrufer dem Anwender etwas schreibt, den Grund
mitgeben statt ihn wegzuwerfen.

**Das Journal ist die Wahrheit, der Index ist Beiwerk.** Jede Information, die
zum Wiederaufbau nötig ist, muss im Journal stehen. Beim ersten Entwurf bekam
ein zweiter *Fundort* derselben Mail keinen Journaleintrag, weil die Datei ja
schon da war – damit ging beim Neuaufbau der zweite Ordner verloren.
Protokolliert wird der Fundort, nicht die Datei.

**Mails werden bytegenau abgelegt.** Keine geglätteten Zeilenenden, keine
reparierten Kopfzeilen. Sonst ist die DKIM-Signatur hinüber und die
Unveränderbarkeit dahin. Das heißt auch: Dieselbe Rundmail an drei Adressen
liegt dreimal auf der Platte, weil sich die `Received:`-Zeilen unterscheiden.
Das ist Absicht.

**Der Index gehört nicht ins Archiv.** SQLite auf einem synchronisierten
Laufwerk geht kaputt. Er liegt unter `paths.index_path()`, benannt nach der
Archivkennung – nicht nach dem Pfad, damit er eine umgehängte externe Platte
überlebt.

**Reihenfolge beim Aufnehmen:** erst `store.put()`, dann Journal, dann Index.
Andersherum entstünde bei einem Absturz ein Eintrag ohne Inhalt – und der sieht
aus wie eine Manipulation.

**Wer `SCHEMA_VERSION` erhöht, sperrt bestehende Archive aus.** Das ist
richtig so, sobald eine neue Spalte für alte Mails leer bliebe: Ein still
halb gefüllter Index sieht vollständig aus und ist es nicht. Aber dann
gehören drei Dinge dazu, und alle drei fehlten beim ersten Anlauf
(2026-08-31, Fassung 2 für den Gesprächsverlauf):

1. **Den Fehler fangen.** `IndexOutdated` ist ein `RuntimeError` und lief
   ungebremst durch bis zum Traceback. Wer nach einer Aktualisierung sein
   Archiv nicht mehr aufbekommt, denkt an den Verlust von zwanzig Jahren
   Post, nicht an ein Verzeichnis, das sich in Minuten neu baut.
2. **Die Sperre freigeben.** `_acquire_lock()` läuft vor dem Öffnen des
   Index; fliegt `Archive.__init__` danach, ruft niemand mehr `close()` –
   es gibt ja kein Objekt. Ohne Aufräumen hätte man zwei Probleme statt
   einem, und das zweite ohne erkennbaren Grund.
3. **Den Ausweg gangbar halten.** `mailburg neuaufbau` öffnet dasselbe
   Archiv und wäre am selben Fehler gescheitert – die Meldung hätte auf
   einen Weg verwiesen, den es nicht gibt. Dafür ist
   `Archive.open(..., index_verwerfen=True)` da.

Steht alles in `tests/test_index_fassung.py`.

**Die CI läuft je Push nur auf Linux.** Seit dem 26.08.2026 ist das
Repository öffentlich, Actions-Minuten kosten dort nichts mehr. Die Regel
bleibt trotzdem – sie stammt aus der Zeit davor und hat einen Grund, der
noch gilt: GitHub rundet *jeden einzelnen Job* auf volle Minuten auf, rechnet macOS zehnfach und
Windows zweifach. Die erste Fassung startete dreizehn Jobs je Push und
verbrauchte an einem einzigen Arbeitstag das Monatskontingent des Kontos
(1.800 von 2.000 Minuten). Deshalb: ein Job je Push, alle Schritte darin
gebündelt, die teuren Systeme montags. Wer hier einen Job hinzufügt, sollte
vorher rechnen – ein zusätzlicher macOS-Job kostet zehn Minuten, auch wenn er
nach neun Sekunden fertig ist.

**Keine AGPL- oder GPL-Abhängigkeiten.** Das Projekt ist MIT und soll als
Binärpaket verteilt werden. Also PySide6 statt PyQt6, pypdf statt PyMuPDF.

**`fsync` nicht pro Eintrag.** Bei hunderttausend Mails am Stück ist das der
Flaschenhals. `journal.flush()` am Ende eines Durchlaufs und vor jedem Siegel.

**Das Postfach wird nur gelesen.** `EXAMINE` statt `SELECT`, `BODY.PEEK[]`
statt `BODY[]`. Beides zusammen sorgt dafür, dass ungelesene Post ungelesen
bleibt. Wer eines davon vergisst, macht aus einem Archivprogramm ein Programm,
das fremde Postfächer verändert.

**Der Höchststand für den nächsten Abruf wird nicht mitgeschrieben.** Er kommt
aus `index.max_uid()`, also aus dem, was *tatsächlich* im Archiv liegt. Eine
mitgeschriebene Zahl wäre nach einem Abbruch mitten im Ordner falsch – sie
stünde auf der zuletzt geholten Mail, nicht auf der zuletzt abgelegten, und
alles dazwischen fehlte dauerhaft. Deshalb steht in `core/sync.py` nur, was
der Index nicht wissen kann: `UIDVALIDITY` und die Nachzügler.

**Eine gescheiterte Mail muss vorgemerkt werden.** Sonst zieht der Höchststand
an ihr vorbei und sie fehlt für immer, ohne Spur. Das ist der Grund, warum
`importieren()` dem Fehler-Rückruf die ganze `RawMessage` gibt und nicht nur
den Ordner – ohne die UID lässt sie sich nicht wieder anfordern.

**`UID n:*` liefert immer mindestens eine UID.** Auch wenn die höchste
vorhandene kleiner als `n` ist; so steht es in RFC 3501. Ohne Nachfiltern holt
jeder Abruf die zuletzt archivierte Mail erneut.

**Gmails »Alle Nachrichten« gehört nicht ins Archiv.** Der Ordner (`\All` nach
RFC 6154) enthält sämtliche Mails ein zweites Mal. Auf der Platte gäbe das
keine doppelte Datei, wohl aber einen zweiten Fundort je Mail im Journal.

## Lizenzen und Recht

Im README und überall sonst gilt: MailBurg **unterstützt** revisionssicheren
Betrieb, es **stellt ihn nicht her**. Keine Software kann GoBD-konform sein –
wer das behauptet, macht sich angreifbar. Die Belege dafür stehen in
[RECHTLICHES.md](RECHTLICHES.md).

## Gepflogenheiten

- Docstrings und Kommentare auf Deutsch, Bezeichner auf Englisch.
- Kommentare erklären das *Warum*, nicht das *Was*.
- Tests mit `unittest` in `tests/`, Methodennamen auf Deutsch.
- Version steht in `mailburg/__init__.py`, sonst nirgends.
- Fristen und Jahreszahlen stehen ausschließlich in `core/retention.py`.

## Noch nicht getestet

- ~~Verhalten bei einem Archiv auf einem Laufwerk, das während des Betriebs
  verschwindet.~~ Am 28.08.2026 nachgestellt: Das Archiv bleibt heil
  (1.000 Mails, Hash-Kette unversehrt), die Meldung war ein nackter
  Traceback und ist behoben.
- Zusammenspiel mit einem laufenden Nextcloud-Client.
- Große Bestände: **Am 2026-09-07 lief der MailStore-Export von Stephans
  Firmenpostfach durch – das Archiv steht bei rund 68.000 Mails, sauber.**
  Das ist das Vierfache des bisherigen Alltagsbestands und die erste Zahl
  in dieser Größenordnung überhaupt (vorher: 5.187 beim Messen, 16.000 im
  Alltag). Offen bleibt die Größenordnung darüber: eine halbe Million.
- **Gmail und Exchange.** Der Abruf gegen echte Server läuft seit dem
  26.08.2026 im Alltag – acht Postfächer, darunter Proton über die Bridge,
  und am 28.08. auch unter Windows. Alle liegen aber bei denselben zwei
  Anbietern. Ungeprüft bleiben die Eigenheiten von Gmail (Etiketten statt
  Ordner), Exchange (eigenwillige LIST-Antworten) und Servern, die bei zu
  vielen UIDs in einer Zeile aussteigen.
- **OAuth2 an einem echten Konto.** Siehe ganz oben: Der Ablauf ist nur
  gegen einen nachgebauten Anbieter geprüft.
