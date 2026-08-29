[Deutsch](CHANGELOG.md) | [Übersicht](README.md) | [TODO](TODO.md) | [Anleitungen](docs/README.md)

# Änderungsprotokoll

Alle nennenswerten Änderungen an MailBurg stehen hier.

Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionsnummern folgen [Semantic Versioning](https://semver.org/lang/de/).

## [Unveröffentlicht]

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

### Hinzugefügt

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

[Unveröffentlicht]: https://github.com/Stephan-Lefty/MailBurg/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Stephan-Lefty/MailBurg/releases/tag/v0.1.0
