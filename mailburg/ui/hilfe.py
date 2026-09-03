"""Das Handbuch – nach Kapiteln geordnet und untereinander verlinkt.

Bisher gab es zwei Meldungsfenster mit Fließtext. Das reicht für eine
Auskunft, nicht für ein Nachschlagewerk: Wer wissen will, was ein
bestimmter Menüpunkt tut, sucht nach diesem Menüpunkt – nicht nach einem
Absatz, in dem er vielleicht vorkommt.

Deshalb hier eine feste Ordnung: links die Kapitel, rechts der Text, und
in jedem Kapitel die Menüpunkte, um die es geht – mit demselben Wortlaut
wie im Menü, damit man sie wiedererkennt. Querverweise springen zum
zugehörigen Kapitel.

**Der Text darf nichts behaupten, was das Programm nicht tut.** Eine
Anleitung ist die Stelle, an der ein Anwender Vertrauen fasst oder
verliert; sie ist deshalb an denselben Maßstab gebunden wie die
Oberfläche selbst.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)


@dataclass(frozen=True)
class Kapitel:
    kennung: str
    titel: str
    text: str


def _menue(pfad: str, erklaerung: str) -> str:
    """Ein Menüpunkt mit seinem Wortlaut, so wie er im Menü steht."""
    return f"<p><b>{pfad}</b><br>{erklaerung}</p>"


_UEBERBLICK = """
<h2>Was MailBurg tut</h2>

<p>MailBurg holt Ihre Mails aus Ihren Postfächern und legt sie
dauerhaft auf Ihrer eigenen Festplatte ab. Danach können Sie sie
durchsuchen – auch die Anhänge, bis hinein in eingescannte PDF.</p>

<p>Der Zweck dahinter: Ihr Postfach beim Anbieter darf wieder leer
werden, ohne dass etwas verlorengeht. Was einmal im Archiv liegt,
bleibt dort, auch wenn Sie es im Mailprogramm löschen – und lässt sich
jederzeit <a href="#zurueck">wieder zurückholen</a>.</p>

<p><b>Das Postfach bleibt dabei unangetastet.</b> MailBurg öffnet Ihre
Ordner nur lesend und holt Nachrichten so, dass ungelesene Post
ungelesen bleibt. Gelöscht wird auf dem Server nichts – das entscheiden
Sie in Ihrem Mailprogramm, und erst, wenn Sie sich vergewissert haben
(siehe <a href="#aufraeumen">Postfach aufräumen</a>).</p>

<p><b>Wo Sie Hilfe finden.</b> <i>Hilfe → Handbuch</i> (F1) öffnet
dieses Verzeichnis. <i>Hilfe → Suchsprache</i>, <i>Hilfe → Was das Journal ist</i>,
<i>Hilfe → Postfach aufräumen</i> und <i>Hilfe → Tipps</i> führen zum
selben Handbuch, nur gleich ans passende Kapitel.</p>

<p><b>Wenn etwas nicht stimmt.</b> <i>Hilfe → Info</i> nennt die Fassung
des Programms, wer es gemacht hat und wohin Fehlermeldungen gehen. Ein
Archivprogramm bekommt man selten zu Gesicht – gerade dann, wenn etwas
fehlt, will man wissen, an wen man sich wenden kann. Bitte nennen Sie
in einer Meldung die Fassung mit; sie steht in demselben Fenster.</p>

<p><b>Ihre Daten bleiben bei Ihnen.</b> MailBurg sendet nichts an
Dritte. Es verbindet sich ausschließlich mit den Mailservern, die Sie
selbst eingetragen haben. Wo Ihr Archiv liegt, bestimmen Sie – siehe
<a href="#archiv">Das Archiv</a>.</p>
"""

_ARCHIV = """
<h2>Das Archiv</h2>

<p>Ein Archiv ist ein gewöhnlicher Ordner auf Ihrer Festplatte. Darin
liegen Ihre Mails als Dateien, dazu ein Protokoll über alles, was
aufgenommen wurde. Sie können den Ordner jederzeit ansehen, kopieren
oder auf eine andere Platte verschieben.</p>

<p><b>Legen Sie ihn möglichst nicht auf dieselbe Platte wie Ihr
Betriebssystem.</b> Geht die kaputt, wäre sonst beides weg. Eine externe
Platte oder ein Ordner, den Ihre Cloud abgleicht, ist die bessere
Wahl.</p>

<p><b>Mehrere Archive sind möglich und oft sinnvoll.</b> Geschäftliche
Post gehört in ein Geschäftsarchiv mit Fristen, private in ein
Privatarchiv ohne. Für Arzt- oder Krankenkassenpost ist das kein
Schönheitsfehler: Ein Geschäftsarchiv bremst das Löschen jahrelang,
während die DSGVO für solche Daten das Gegenteil verlangt. Die
Postfächer selbst sind dabei gemeinsam – Sie entscheiden beim Abruf,
in welches Archiv geholt wird.</p>

<p>Der Suchindex gehört ausdrücklich nicht in diesen Ordner. Er liegt
getrennt und lässt sich jederzeit neu aufbauen – aus dem Protokoll,
das die eigentliche Wahrheit ist (siehe <a href="#journal">Das
Journal</a>).</p>

<h3>Verschlüsselte Archive</h3>

<p><b>Neu in dieser Fassung und im Alltag noch nicht erprobt.</b> Legen
Sie damit vorerst kein Archiv an, dessen Mails Sie nicht auch anderswo
noch haben.</p>

<p>Beim Anlegen können Sie ein Archiv <b>verschlüsseln</b>. Sinnvoll ist
das, wenn es auf einer externen Platte liegt, in eine Cloud gesichert
wird oder auf einem Server steht – überall dort, wo die Mails das Haus
verlassen.</p>

<p>Verschlüsselt werden die Nachrichten und das Protokoll, also alles im
Archivordner. <b>Nicht der Suchindex:</b> Der liegt außerhalb und
enthält Betreff, Absender und Text im Klartext – anders könnte er nicht
suchen. Für eine Sicherung in der Cloud oder eine verlorene Platte
genügt das, denn der Index wandert dort nicht mit. Wer den ganzen
Rechner absichern will, verschlüsselt die Platte.</p>

<p><b>Der Notschlüssel ist der wichtigste Teil.</b> Er erscheint einmal
beim Anlegen und öffnet das Archiv anstelle des Passworts. Drucken Sie
ihn aus – ein Archiv überdauert Jahrzehnte, ein Passwort im Kopf nicht.
Legen Sie ihn nicht auf dieselbe Platte: Ein Schlüssel neben dem Schloss
ist keiner.</p>

<p>Sind Passwort und Notschlüssel beide weg, ist das Archiv verloren. Es
gibt keine Hintertür – das ist die Bedingung dafür, dass die
Verschlüsselung überhaupt etwas wert ist.</p>

<p><b>Nachträglich lässt sich ein Archiv nicht verschlüsseln.</b> Wer
umsteigen will, legt ein neues an und spielt eine Sicherung des alten
hinein.</p>

{menue}
"""

_POSTFAECHER = """
<h2>Postfächer</h2>

<p>Jedes Postfach, das archiviert werden soll, wird einmal eingerichtet:
Server, Benutzername und Passwort. Bei der Ersteinrichtung liest
MailBurg die Einstellungen aus Thunderbird aus, falls vorhanden – die
Passwörter aber nicht.</p>

<p><b>Warum Sie die Passwörter noch einmal eingeben müssen.</b>
Technisch ließen sie sich aus anderen Programmen auslesen. Ein Programm,
das die Passwörter anderer Programme abgreift, verhält sich aber wie
Schadsoftware. Einem Archiv vertrauen Sie jahrzehntealte Post an; dieses
Vertrauen ist mehr wert als die gesparte Tipparbeit.</p>

<p>Abgelegt werden die Passwörter im Schlüsselbund Ihres Systems, nie in
einer Datei des Programms.</p>

<h3>IMAP oder JMAP</h3>

<p>Oben im Postfachdialog steht <b>Abrufweg</b>. In aller Regel bleibt
er auf <i>IMAP</i> – so holen fast alle Anbieter ihre Post heraus.</p>

<p><b>JMAP</b> ist der Nachfolger von IMAP: JSON über HTTPS statt eines
eigenen Protokolls von 1986. Für ein Archiv ist er der bessere Weg, denn
er beantwortet in einer einzigen Anfrage, was seit dem letzten Abruf
dazugekommen ist. Über IMAP muss MailBurg das umständlich nachbauen –
und dabei rutschen Nachrichten durch, die jemand nachträglich in einen
Ordner einsortiert hat.</p>

<p><b>Können muss es der Anbieter.</b> Fastmail, Stalwart und Cyrus
sprechen JMAP; Gmail, Outlook, GMX, Web.de und Proton nicht. Wenn Ihrer
nicht dabei ist, ändert sich für Sie nichts.</p>

<p>Bei JMAP tragen Sie statt eines Servernamens eine vollständige
Adresse ein, und statt eines Passworts meist eine <i>Zugriffsmarke</i>,
die Sie beim Anbieter erzeugen. Port und Verschlüsselung entfallen –
JMAP läuft immer über HTTPS.</p>

<p><b>Beides zugleich ist ausdrücklich vorgesehen.</b> Der Abrufweg
gehört zum einzelnen Postfach, nicht zum Programm.</p>

<p><b>Wenn das Zertifikat abgelehnt wird.</b> Läuft Ihr Mailserver bei
einem größeren Anbieter, weist er sich oft unter dessen Namen aus.
MailBurg sieht dann nach, für welchen Namen das Zertifikat gilt, und
schlägt ihn vor. Nehmen Sie den Vorschlag an, ist die Verbindung danach
vollständig geprüft. Eine Möglichkeit, die Prüfung einfach abzuschalten,
gibt es bewusst nicht.</p>

{menue}
"""

_ZUGAENGE = """
<h2>Zugänge</h2>

<p>Wer sich an diesem Archiv anmelden darf – und welche Postfächer er
dabei zu sehen bekommt.</p>

<p><b>Solange MailBurg nur auf diesem Rechner läuft, ändert das
nichts.</b> Wer am Rechner sitzt, hat das Archiv ohnehin; eine Anmeldung
davor wäre Theater. Die Zugänge greifen, sobald das Archiv über einen
Server erreichbar ist und mehrere Menschen darauf zugreifen.</p>

<p><b>Zwei Rechte, und sie sind nicht dasselbe.</b></p>

<p><i>Darf Zugänge verwalten</i> heißt: Diese Person legt Zugänge an,
vergibt Rechte und legt sie still. <i>Darf alle Postfächer sehen</i>
heißt: Sie liest jede Post im Archiv.</p>

<p>Das ist absichtlich getrennt. Wer die Technik betreut, muss keine
Geschäftspost lesen dürfen – und wer alles liest, muss nicht über fremde
Zugänge bestimmen. Beides in eine Rolle zu werfen wäre bequemer und
datenschutzrechtlich schlechter.</p>

<p><b>»Alle Postfächer« ist ein Schalter, keine Liste.</b> Wer ihn
gesetzt hat, sieht auch das Postfach, das nächste Woche dazukommt. Mit
einer angekreuzten Liste müsste das jemand nachpflegen – und würde es
nicht, bis jemand etwas vermisst.</p>

<p><b>Stilllegen statt entfernen.</b> Ein stillgelegter Zugang meldet
sich nicht mehr an, bleibt aber eingetragen. Das ist wichtig für das
Journal: Dort steht bei jedem Vorgang, wer ihn ausgelöst hat. Wer ganz
entfernt wird, hinterlässt Einträge, die auf einen Namen zeigen, den es
nicht mehr gibt.</p>

<p><b>Der letzte Verwalter kann sich nicht selbst aussperren.</b>
MailBurg lässt es nicht zu, dem letzten verbliebenen Verwalter das Recht
zu nehmen, ihn stillzulegen oder zu entfernen. Sonst gäbe es niemanden
mehr, der Zugänge vergeben kann, und das ließe sich nur noch von der
Kommandozeile aus reparieren.</p>

<p><b>Die Passwörter</b> werden nicht im Klartext gespeichert, sondern
als Prüfwert, aus dem sich das Passwort nicht zurückrechnen lässt. Ins
Journal kommen sie nicht: Was dort einmal steht, steht dort für immer.</p>

{menue}
"""

_ABRUFEN = """
<h2>Mails holen</h2>

<p>Der erste Abruf holt alles, was in Ihren Postfächern liegt. Bei einem
gewachsenen Bestand dauert das; Sie können in der Zwischenzeit
weiterarbeiten. Brechen Sie ab, macht der nächste Lauf dort weiter, wo
dieser aufgehört hat – verloren geht dabei nichts.</p>

<p>Danach wird nur noch geholt, was neu dazugekommen ist. Das dauert
Sekunden.</p>

<p><b>Regelmäßig im Hintergrund.</b> Sinnvoll ist ein Zeitplan, sonst
muss jemand daran denken. MailBurg muss dafür weder geöffnet bleiben
noch beim Anmelden mitstarten – geholt wird ohne Fenster. Nötig ist nur,
dass Sie angemeldet sind: Die Passwörter liegen im Schlüsselbund, und
der öffnet sich erst mit Ihrer Anmeldung. War der Rechner aus, wird der
versäumte Abruf beim nächsten Anmelden nachgeholt.</p>

<p>Unten rechts steht immer, wie viele Mails im Archiv liegen und wann
zuletzt abgerufen wurde. Vermerkt wird dabei nur ein Lauf, der
durchgelaufen ist – ein abgebrochener oder gescheiterter Abruf weist Ihr
Archiv nicht als aktuell aus.</p>

<p>Während ein Abruf läuft, wächst der Postfachbaum links mit: Sie sehen
schon, was da ist, bevor der Lauf zu Ende ist.</p>

<h3 id="einlesen">Post von der eigenen Platte</h3>

<p>Nicht alles kommt vom Server. Wer jahrelang mit Thunderbird,
Evolution oder KMail gearbeitet hat, hat Mails in <b>lokalen
Ordnern</b> – die liegen nur auf der Platte und in keinem Postfach mehr.
Dasselbe gilt für Post aus einem Konto, das längst gekündigt ist.</p>

<p><i>Post → Lokale Mailordner einlesen …</i> holt sie ins Archiv.
Erkannt werden:</p>

<ul>
<li><b>Thunderbird-Profile</b> mit allen Konten und Unterordnern –
    üblicherweise unter <tt>~/.thunderbird</tt>.</li>
<li><b>Maildir-Verzeichnisse.</b> So legt Evolution seine lokalen Ordner
    ab, unter <tt>~/.local/share/evolution/mail/local</tt>. Auch eine
    Sammlung mehrerer Maildirs nebeneinander wird erkannt.</li>
<li><b>MBOX-Dateien</b> – eine Datei, die einen ganzen Ordner enthält.</li>
<li><b>Verzeichnisse voller <tt>.eml</tt>-Dateien.</b> Das ist meist das
    Ergebnis, wenn ein anderes Archivprogramm seine Post herausrückt.</li>
</ul>

<p>Der Dialog schlägt vor, was er auf Ihrem Rechner findet, und zeigt
unter dem Pfad, was er dort erkannt hat – mitsamt den Ordnernamen. So
sehen Sie vor dem Start, ob Sie das Richtige gewählt haben.</p>

<p><b>Gelesen wird nur.</b> An Ihren Dateien ändert MailBurg nichts, und
zweimal einlesen erzeugt keine zweite Kopie: Der Name jeder Mail im
Archiv ist der Hash ihres Inhalts.</p>

{menue}
"""

_SUCHEN = """
<h2>Suchen</h2>

<p>Ins Suchfeld oben können Sie einfach hineinschreiben, wonach Sie
suchen. Gesucht wird in Betreff, Text, Absender, Empfänger und in den
Anhängen – auch in <a href="#scans">eingescannten PDF</a>, sofern deren
Text erkannt wurde.</p>

<p>Darunter steht, was dabei herauskam: <i>MailBurg hat 191 Treffer</i>
oder <i>MailBurg hat nichts gefunden</i>.</p>

<p>Wer genauer suchen will, kann Felder angeben. Die vollständige
Übersicht steht weiter unten; wer sie sich nicht merken mag, nimmt die
Suchmaske, die den Ausdruck zusammensetzt und dabei zeigt, wie er
lautet.</p>

<h3>Der Gesprächsverlauf</h3>

<p>Ging eine Sache mehrmals hin und her, steht in der Vorschau, aus wie
vielen Nachrichten der Austausch besteht und wann die erste und die
letzte kam.</p>

<p>Zusammengehalten wird er über Kopfzeilen, die jedes Mailprogramm
mitführt – nicht über den Betreff. Der wechselt unterwegs (»Re:«,
»AW:«, »Fwd:«), und zwei Mails mit »Rechnung« im Betreff haben
meistens nichts miteinander zu tun.</p>

<p><b>Vollständig ist ein Verlauf nie garantiert.</b> Was nie ins
Archiv kam, fehlt auch hier. Schließen Sie aus »da steht nichts« also
nicht auf »da war nichts«.</p>

{menue}

<h3>Die Suchsprache</h3>
<pre style="white-space: pre-wrap">{syntax}</pre>
"""

_ANSICHT = """
<h2>Die Ansicht einrichten</h2>

<p>Größe des Fensters, Breite der Bereiche, Reihenfolge der Postfächer –
das lässt sich alles einstellen und behalten.</p>

<p><b>Postfächer anordnen.</b> Von Haus aus stehen sie in der
Reihenfolge, in der sie eingerichtet wurden. Sie können sie mit der Maus
verschieben oder mit Strg+Auf und Strg+Ab. <i>Alle Postfächer</i> bleibt
dabei oben, und die Ordner bleiben bei ihrem Postfach.</p>

<p><b>Gespeichert wird nur auf Befehl.</b> Wenn Sie das Fenster
schließen, merkt sich MailBurg nichts – sonst überschriebe ein
versehentliches Verziehen die Ansicht, die Sie sich eingerichtet haben.
Nutzen Sie <i>Eigene Ansicht speichern</i>, wenn es Ihnen gefällt.</p>

{menue}
"""

_JOURNAL = """
<h2>Das Journal</h2>

<p><b>Das Journal ist das Protokoll Ihres Archivs.</b> Darin steht jeder
Vorgang: Diese Mail wurde aufgenommen, jene gelöscht, diese eingeordnet.
Es ist die eigentliche Wahrheit des Archivs – die Suche ist nur eine
Bequemlichkeit, die sich daraus jederzeit neu aufbauen lässt.</p>

<p><b>Warum es fälschungssicher ist.</b> Jeder Eintrag bekommt einen
Fingerabdruck seines Inhalts und trägt zusätzlich den Fingerabdruck
seines Vorgängers. So hängen alle Einträge zusammen wie die Glieder
einer Kette.</p>

<p>Ändert jemand nachträglich einen alten Eintrag – etwa um eine
unbequeme Mail verschwinden zu lassen –, ändert sich dessen
Fingerabdruck. Der nächste Eintrag zeigt dann ins Leere: Die Kette ist
gerissen, und die Prüfung sagt Ihnen, an welcher Stelle. Wer die
Änderung verbergen wollte, müsste jeden nachfolgenden Eintrag neu
berechnen.</p>

<p><b>Was das Prüfen Ihnen sagt.</b> Ob die Kette unversehrt ist, ob
alle Mails, die laut Protokoll da sein sollten, auch wirklich auf der
Platte liegen – und ob dort Dateien liegen, die nie über MailBurg
hereingekommen sind.</p>

<p><b>Was es nicht leistet.</b> Wer Zugriff auf das Archiv hat und sich
Zeit nimmt, kann die gesamte Kette neu berechnen. Dagegen hilft die
Kette allein nicht; dagegen hilft nur ein Siegel, dessen Wert außerhalb
des Archivs liegt – notiert, verschickt oder von einem Zeitstempeldienst
bestätigt. Deshalb sagt MailBurg, dass es revisionssicheren Betrieb
<i>unterstützt</i>, und nicht, dass es ihn herstellt. Dazu gehören immer
auch geregelte Abläufe bei Ihnen im Betrieb.</p>

{menue}
"""

_ZURUECK = """
<h2>Eine Mail zurückholen</h2>

<p>Ein Archiv, aus dem nichts wieder herauskommt, wäre ein Grab.
Irgendwann braucht man eine alte Rechnung wieder im Mailprogramm – um
sie zu beantworten, weiterzuleiten oder einfach im gewohnten Ordner zu
haben.</p>

<p>Ein <b>Doppelklick</b> auf eine Nachricht öffnet sie in einem eigenen
Fenster – die Vorschau unten ist zum Überfliegen da, nicht zum Lesen.
Mehrere Fenster gleichzeitig sind möglich, etwa um zwei Rechnungen zu
vergleichen; Strg+W oder Esc schließt sie wieder.</p>

<p><b>In der Nachricht suchen: Strg+F.</b> Unten geht eine Leiste auf,
und während Sie tippen, springt MailBurg zur ersten passenden Stelle.
Daneben steht, wie viele es insgesamt sind. <i>F3</i> geht zum nächsten
Treffer, <i>Umschalt+F3</i> zurück; am Ende beginnt die Suche wieder
von vorn.</p>

<p>Groß- und Kleinschreibung spielt dabei zunächst keine Rolle – wer
eine Stelle sucht, weiß meist nicht mehr, wie sie geschrieben war. Ein
Häkchen in der Leiste ändert das.</p>

<p>Haben Sie vorher ein Wort markiert, steht es schon im Suchfeld.
<i>Esc</i> schließt erst die Leiste und erst danach das Fenster – sonst
wäre die Nachricht mit einem Tastendruck weg, obwohl man nur die Suche
loswerden wollte.</p>

<p><b>Das ist eine gewöhnliche Textsuche</b>, keine zweite Suchsprache:
Hier gibt es kein <tt>von:</tt> und kein <tt>jahr:</tt>. Wer nach
solchen Feldern sucht, tut das im Hauptfenster.</p>

<p>Ein Klick mit der <b>rechten Maustaste</b> auf eine Nachricht führt
weiter:</p>

<p><b>In Mailprogramm öffnen.</b> Der kürzeste Weg zurück: Die
Nachricht geht in dem Programm auf, das Sie für E-Mail-Dateien
eingerichtet haben – Thunderbird, Outlook, Apple Mail. Von dort können
Sie sie lesen, weiterleiten oder beantworten. Verändert wird dabei
nichts, weder im Archiv noch in einem Postfach.</p>

<p><b>Wo die Datei dabei liegt.</b> MailBurg legt die Nachricht kurz im
Zwischenspeicher Ihres Benutzerkontos ab, in einem Ordner, den nur Sie
lesen dürfen – nicht im allgemeinen Temp-Verzeichnis, in das auf einem
gemeinsam genutzten Rechner jeder hineinsehen kann. Aufgeräumt wird
zweimal: Was älter als vier Stunden ist, verschwindet beim nächsten
Öffnen, und beim Beenden von MailBurg der ganze Ordner.</p>

<p><b>Im Postfach wiederherstellen.</b> MailBurg legt die Nachricht in
den <b>Posteingang</b> des gewählten Postfachs – vollständig, mit allen
Anhängen und mit ihrem ursprünglichen Datum, damit sie im Mailprogramm
an der richtigen Stelle steht und nicht ganz oben. Von dort verschieben
Sie sie mit einem Handgriff dahin, wo Sie sie haben wollen.</p>

<p><b>Als ungelesen markiert</b> – dafür sorgt ein Häkchen, das
voreingestellt gesetzt ist. Das klingt nach einer Falschmeldung,
gelesen haben Sie die Mail ja längst. Es ist aber der einzige Weg, sie
wiederzufinden: Mit ihrem alten Datum steht sie mitten in der Post von
damals. Ungelesen erscheint sie hervorgehoben und im Zähler des
Ordners; ein Klick darauf, und sie ist wieder gelesen.</p>

<p><b>Es muss nicht das Postfach sein, aus dem sie stammt.</b> Post
überlebt Arbeitgeber, Anbieter und Adressen; das Konto von damals gibt
es vielleicht gar nicht mehr. Sie wählen frei, wohin.</p>

<p><b>Als Datei speichern.</b> Die Nachricht wird als
<i>.eml</i>-Datei abgelegt. Die öffnet jedes Mailprogramm, und in
Thunderbird lässt sie sich in einen beliebigen Ordner ziehen. Dieser
Weg braucht weder Zugangsdaten noch ein erreichbares Postfach – er
funktioniert also auch dann, wenn gar kein Konto mehr eingerichtet
ist.</p>

<p><b>Hier schreibt MailBurg zum ersten Mal in ein Postfach.</b> Sonst
gilt strikt: nur lesen. Diese Ausnahme ist eng gefasst – sie geschieht
nur auf Ihren ausdrücklichen Befehl, für einzelne Nachrichten, und
niemals im Hintergrund. Gelöscht oder geändert wird in Ihrem Postfach
weiterhin nichts.</p>

<p>Zurückgespielt wird die Nachricht unverändert, Byte für Byte. Nur so
bleibt eine vorhandene Signatur gültig, und nur so ist die Mail im
Postfach dieselbe wie die im Archiv.</p>
"""

_SCANS = """
<h2>Eingescannte PDF</h2>

<p>Die meisten PDF tragen ihren Text mit sich – MailBurg liest ihn beim
Archivieren mit, und Sie finden die Rechnung über ihren Betrag oder die
Kundennummer.</p>

<p><b>Ein eingescanntes PDF ist etwas anderes.</b> Es enthält keinen
Text, sondern ein Foto einer Seite. Für die Suche ist es ein weißes
Blatt: Der Dateiname lässt sich finden, der Inhalt nicht.</p>

<p>Das ist die unangenehmste Sorte Lücke, weil sie sich nicht meldet.
Sie merken sie erst, wenn Sie nach einer Rechnung suchen, die es im
Archiv gibt, und nichts bekommen.</p>

<p><b>Die Texterkennung liest solche Seiten.</b> Sie steht im
Menü, mit der Zahl der wartenden Dokumente dahinter – ist die Zahl
Null, gibt es nichts zu tun.</p>

<p>Zweierlei ist dabei zu wissen:</p>

<p><b>Wie viele Kerne mitarbeiten,</b> stellen Sie selbst ein. MailBurg
liest mehrere Dokumente nebeneinander – die Arbeit steckt in zwei
Hilfsprogrammen, und die laufen unabhängig voneinander. Voreingestellt
bleiben zwei Kerne frei, damit Ihr Rechner benutzbar bleibt. Wer ihn
ohnehin stehen lässt, gibt der Erkennung alles.</p>

<p><b>Es dauert.</b> Etwa fünf bis acht Sekunden je Seite, geteilt
durch die Zahl der Kerne. Bei hundert
Seiten also eine gute Viertelstunde. Sie müssen dabei aber nicht
zusehen: Schließen Sie das Fenster, fragt MailBurg, ob im Hintergrund
weitergelesen werden soll. Sagen Sie ja, können Sie ganz normal
weitersuchen – oben rechts steht dann, wie weit es ist.</p>

<p>Abbrechen geht ebenso. Was gelesen ist, bleibt gelesen: MailBurg
schreibt nach jedem einzelnen Dokument mit. Nur das gerade in Arbeit
befindliche fällt weg und kommt beim nächsten Mal wieder dran – ein
halb gelesenes PDF wäre schlimmer als ein ungelesenes, weil es als
erledigt gälte.</p>

<p>Abgearbeitet wird von klein nach groß. Ein einseitiger Scan ist in
vier Sekunden gelesen, ein zwanzigseitiger Brocken braucht eine halbe
Stunde – so sind die vielen kleinen schnell durch, statt hinter einem
einzigen großen zu warten.</p>

<p><b>Das Archiv bleibt unangetastet.</b> Der erkannte Text kommt nur in
den Suchindex, die PDF selbst werden nicht verändert. Das ist
wesentlich: Ein Dokument, an dem nachträglich etwas geändert wurde, wäre
als Beleg wertlos.</p>

<p><b>Meistens brauchen Sie das gar nicht.</b> Nach jedem Abruf wird
nebenbei ein Häppchen miterledigt – bei halbstündlichem Abruf sind das
mehrere tausend Seiten am Tag. Wer den <a href="#abrufen">Abruf im
Hintergrund</a> eingerichtet hat, findet den Rückstand nach ein paar
Tagen von selbst abgearbeitet. Dieser Menüpunkt ist für den Anfang
gedacht, wenn ein großes Archiv frisch eingelesen wurde.</p>

{menue}
"""

_TIPPS = """
<h2>Tipps</h2>

<p>Dinge, die sich im Alltag als nützlich erwiesen haben.</p>

<h3>Das Archiv sichern</h3>

<p><b>MailBurg ist ein Archiv, kein Backup.</b> Der Unterschied ist
nicht akademisch: Ihr Archiv liegt auf <i>einer</i> Platte. Geht die
kaputt, ist alles weg. Eine Sicherung ist eine Kopie an einem
<i>zweiten</i> Ort – auf einer anderen Platte oder in der Cloud.</p>

<p><b>Am besten von selbst.</b> Unter <i>Einstellungen → Was von selbst
laufen soll (Automatisierung) …</i> lässt sich einstellen, dass MailBurg täglich, wöchentlich
oder monatlich eine Sicherung anlegt und dabei die letzten Stände
behält. Ein Backup, an das jemand denken muss, ist irgendwann
keines.</p>

<p>MailBurg packt das Archiv auf Wunsch in eine einzige Datei. Kleiner
wird sie kaum – Ihre Mails liegen schon komprimiert –, aber statt
tausender einzelner Dateien haben Sie eine, und Cloud-Programme kommen
damit um ein Vielfaches schneller zurecht. Der Dateiname trägt das
Datum, jeder Stand ist also eine Datei.</p>

{menue}

<p>Zwei Dinge dabei:</p>

<p><b>Den Suchindex brauchen Sie nicht mitzusichern.</b> Er liegt
ohnehin außerhalb des Archivordners und lässt sich jederzeit aus dem
Protokoll neu aufbauen. Da er sich bei jedem Abruf vollständig ändert
und die größte einzelne Datei ist, spart das bei jeder Sicherung
erheblich.</p>

<p><b>Sichern Sie möglichst nicht während eines Abrufs.</b> Nicht wegen
Datenverlust, sondern wegen der Vollständigkeit: Läuft gerade ein
Import, erwischt die Kopie einen Zwischenstand, bei dem eine Mail schon
abgelegt, ihr Protokolleintrag aber noch nicht geschrieben ist. Die
Prüfung würde das in der Kopie bemängeln. Die nächste Sicherung räumt
das von selbst auf.</p>

<p>Wie die Datei zu Ihrem Cloud-Anbieter kommt – synchronisierter
Ordner, Weboberfläche, rclone oder WebDAV –, steht ausführlich in der
Anleitung <i>Das Archiv sichern</i> im Ordner <i>docs</i> des
Projekts.</p>

<p><b>Nach dem Zurückholen einmal prüfen.</b> Haben Sie eine Sicherung
zurückgespielt, gehen Sie auf <i>Archiv → Journal prüfen</i>. Eine
Cloud-Synchronisation lässt schon einmal eine Datei aus, und bei einem
Archiv merkt man das sonst erst Jahre später beim Suchen.</p>

<h3>Wo das Archiv liegen sollte</h3>

<p>Möglichst nicht auf derselben Platte wie das Betriebssystem – geht
die kaputt, wäre sonst beides weg. Eine externe Platte ist eine gute
Wahl; sie muss nur angesteckt sein, wenn abgerufen wird. Fehlt sie,
holt der nächste Lauf alles nach.</p>

<h3>Mehrere Archive</h3>

<p>Geschäftliche Post gehört in ein Geschäftsarchiv mit Fristen,
private in ein Privatarchiv ohne. Das ist keine Ordnungsliebe: Ein
Geschäftsarchiv bremst das Löschen jahrelang, während die DSGVO für
Gesundheitsdaten und Ähnliches das Gegenteil verlangt. Über
<i>Archiv → Zuletzt benutzt</i> wechseln Sie mit zwei Klicks.</p>

<h3>Wenn ein Postfach nicht erreichbar war</h3>

<p>Dann fehlen dessen Mails im Archiv – und Sie sollten dort im
Mailprogramm nichts aufräumen. MailBurg sagt es Ihnen nach jedem selbst
gestarteten Abruf. Bleibt es dabei, hilft
<a href="#aufraeumen">Postfach aufräumen</a> weiter.</p>

<h3>Suchen, die sich lohnen</h3>

<p><i>hat:anhang groesse:&gt;5MB</i> – die Brocken, die Ihr Postfach
füllen.<br>
<i>von:finanzamt jahr:2025</i> – alles von einem Absender aus einem
Jahr.<br>
<i>inhalt:kündigung</i> – sucht im Text der Anhänge, nicht in der
Mail.<br>
<i>-newsletter rechnung</i> – Rechnungen ohne Werbung.</p>

<p>Und wenn eine Suche nichts findet, obwohl es die Mail geben müsste:
Vielleicht steckt sie in einem <a href="#scans">eingescannten PDF</a>,
das noch nicht gelesen wurde.</p>
"""

_AUFRAEUMEN = """
<h2>Postfach aufräumen</h2>

<p>Der eigentliche Zweck: Ihr Postfach beim Anbieter wieder leer
bekommen, ohne etwas zu verlieren. Die Reihenfolge ist dabei
entscheidend.</p>

<ol>
<li><b>Abrufen</b>, bis alles im Archiv ist.</li>
<li><b>Vergewissern.</b> Auf der Kommandozeile prüft
<i>mailburg abgleich</i>, ob wirklich jede Mail vor einem Stichtag im
Archiv liegt. Der Befund lautet nur dann „alle im Archiv", wenn es
zweifelsfrei stimmt – bei einem Fehler oder einer Unklarheit bleibt er
offen.</li>
<li><b>Erst dann</b> im Mailprogramm oder beim Anbieter aufräumen.</li>
</ol>

<p><b>Räumen Sie nicht auf, solange ein Postfach beim Abruf gefehlt
hat.</b> MailBurg sagt Ihnen nach jedem selbst gestarteten Abruf, ob
alle Postfächer erreichbar waren. Steht dort ein Postfach als nicht
erreichbar, fehlen dessen Mails im Archiv – und wer dann aufräumt, hat
sie an beiden Stellen nicht mehr.</p>
"""

_FRISTEN = """
<h2>Geschäftsarchiv und Fristen</h2>

<p>Ein Geschäftsarchiv protokolliert jeden Vorgang, sichert die Kette
der Einträge gegen nachträgliche Änderungen und löscht nur mit Vermerk.
Außerdem kennt es die Aufbewahrungsfristen für Deutschland, Österreich
und die Schweiz und bremst zu frühes Löschen.</p>

<p>Die Fristen laufen ab dem Ende des Kalenderjahres, nicht ab dem Tag
der Mail. Eine Rechnung vom März 2025 ist in Deutschland also bis Ende
2033 aufzubewahren, nicht bis März 2033.</p>

<p><b>Fristen wirken in beide Richtungen.</b> Nach ihrem Ablauf verlangt
die DSGVO, dass personenbezogene Daten auch wieder verschwinden.
MailBurg rechnet das aus und sagt es Ihnen – gelöscht wird aber nur nach
ausdrücklicher Bestätigung.</p>

<p><b>Kein Rechtsrat.</b> Die Tabellen bilden den Regelfall ab. Ob eine
bestimmte Mail Handelsbrief oder Buchungsbeleg ist, ob eine
Branchenvorschrift längere Fristen setzt und ob eine laufende Prüfung
den Ablauf hemmt, kann nur Ihr Steuerberater beurteilen. Das Programm
rechnet, es entscheidet nicht.</p>

<p><b>Wozu eine Mail zählt, legen Sie fest.</b> Solange nichts
festgelegt ist, behandelt MailBurg sie wie die längste Pflicht – im
Zweifel aufbewahren ist die Richtung, die nichts vernichtet. Nur bringt
das auch mit sich, dass Post jahrelang gehalten wird, die längst weg
dürfte.</p>

<p>Eingestuft wird über die Suche, nicht Mail für Mail: Wer ein Archiv
einordnet, hat hunderte Belege vor sich. »Alles von der Steuerkanzlei
ist Buchungsbeleg« ist eine Regel, die sich als Suchausdruck schreiben
lässt. Suchen Sie also zuerst, und stufen Sie dann die Treffer ein.</p>

<p>Jede Änderung wird im <a href="#journal">Journal</a> vermerkt, mit
vorheriger und neuer Einordnung. Das ist kein Selbstzweck: Wer später
begründen muss, warum eine Mail nach sechs statt acht Jahren gelöscht
wurde, will auf einen Eintrag zeigen können – und der hängt in der
Kette, lässt sich also nicht nachträglich glattziehen.</p>

<p><b>Einmal im Jahr fragt MailBurg nach.</b> Ab dem 1. Mai, und nur
einmal je Kalenderjahr: Es zeigt, was seine Frist hinter sich hat.
Warum nicht ab dem 1. Januar, wenn die Fristen ablaufen? Weil eine
Meldung, die bei jedem Öffnen erscheint, nach der dritten Wiederholung
weggeklickt wird, ohne gelesen zu werden – und dann auch beim vierten
Mal, wenn es darauf ankäme. Im Januar steckt man ohnehin im
Jahresabschluss, und ob eine Betriebsprüfung den Ablauf hemmt, weiß man
im Frühjahr eher.</p>

<p><b>Auch ein Privatarchiv fragt</b> – dort aber anders. Es gibt keine
Fristen, also zeigt es nur, was älter als zehn Jahre ist, und sagt
ausdrücklich dazu, dass Alter kein Grund zum Löschen ist. Bei privater
Post sagt das Datum wenig darüber, was einem wichtig ist: Eine
Nachricht von jemandem, den es nicht mehr gibt, wiegt schwerer als die
von gestern.</p>

<p>Gelöscht wird in beiden Fällen nichts von selbst. Der Bericht führt
die betroffenen Mails in die Suche – ansehen, beurteilen und
entscheiden liegt bei Ihnen.</p>

<p><b>Die Verfahrensdokumentation.</b> Die GoBD verlangen sie für
jedes System, das steuerlich erhebliche Daten verarbeitet: Ein
sachverständiger Dritter soll in angemessener Zeit sehen können, wie
die Daten entstehen, wo sie liegen und wie sie gegen Verlust und
Veränderung geschützt sind.</p>

<p><b>Verantwortlich dafür sind Sie, nicht das Programm.</b> MailBurg
kann den technischen Teil aus seiner eigenen Konfiguration
erzeugen – Fassung, Ablageort, Verfahren, Postfächer, Zeitpläne,
Bestandszahlen. Alles Organisatorische kann es nicht wissen: wer
zuständig ist, wer im Urlaub vertritt, was bei einem Plattenausfall
geschieht, wie oft jemand nachsieht, ob die Sicherungen wirklich
entstehen.</p>

<p>Diese Lücken bleiben im Entwurf sichtbar stehen und sind mit
<i>BITTE ERGÄNZEN</i> ausgezeichnet. Das ist Absicht: Eine
Dokumentation, die vollständig aussieht und es nicht ist, wäre
schlimmer als gar keine – sie fällt erst in der Prüfung auf, und dann
ist keine Zeit mehr.</p>

<p><b>Archiv → Verfahrensdokumentation …</b><br>Schreibt den Entwurf
als Textdatei, die Sie in jedem Schreibprogramm weiterbearbeiten
können. Nur im Geschäftsarchiv.</p>

<p><b>Wenn jemand fragt, was Sie über ihn gespeichert haben.</b> Nach
Artikel 15 DSGVO hat er Anspruch auf eine Kopie. MailBurg sucht alle
Nachrichten, in denen die Person vorkommt, und packt sie auf Wunsch in
eine Datei – mit einem Begleitblatt, das nennt, woher die Daten stammen
und wozu sie gespeichert sind.</p>

<p><b>Herausgegeben wird von Ihnen, nicht vom Programm.</b> Zwei Dinge
kann keine Software entscheiden. Erstens stehen in denselben
Nachrichten oft Daten Dritter – Adressen im Verteiler, Namen im Text,
Unterschriften in Anhängen; nach Artikel 15 Absatz 4 darf die Kopie
deren Rechte nicht beeinträchtigen. Zweitens wird nach genau einer
Adresse gesucht: Wer unter mehreren schreibt, taucht nur unter der
gesuchten auf.</p>

<p>Der Vorgang wird im <a href="#journal">Journal</a> vermerkt. Artikel
5 Absatz 2 verlangt, dass Sie die Einhaltung nachweisen können – wer in
einem Jahr gefragt wird, ob er fristgerecht Auskunft erteilt hat, will
auf einen Eintrag zeigen können.</p>

<p><b>Archiv → Auskunft nach DSGVO …</b><br>Stellt zusammen, was zu
einer Person im Archiv liegt, und speichert es als ZIP-Datei. Nur im
Geschäftsarchiv: Ein Privatarchiv fällt unter die Haushaltsausnahme der
DSGVO, ein Auskunftsrecht besteht dort nicht.</p>

<p><b>Post → Aufbewahrung festlegen …</b><br>Ordnet die gerade
gefundenen Mails als Buchungsbeleg, Handelsbrief oder privat ein. Das
Fenster zeigt vorher, wie viele betroffen sind und wie lange sie danach
geschützt sind. Nur im Geschäftsarchiv; ein Privatarchiv kennt keine
Fristen.</p>

<p><b>Post → Beim Aufnehmen einstufen …</b><br>Dasselbe im Voraus:
Regeln, die eingehende Post von selbst einordnen. Wer geschäftlich
archiviert, bekommt private Post mit ins Archiv – den Verein, die
Familie –, und die unterliegt dort Fristen, die für sie nicht gelten.
Eine Regel schaut auf Ordner, Absender oder Empfänger und bestimmt die
Einstufung.</p>

<p><b>Geholt wird trotzdem alles.</b> Die Regel verhindert nichts, sie
stuft nur ein – eine nicht geholte Mail lässt sich nicht zurückholen,
eine falsche Einstufung schon. Es gilt die erste passende Regel, weshalb
Ausnahmen nach oben gehören. Bereits archivierte Post bleibt
unangetastet, bis man es im selben Fenster ausdrücklich verlangt. Nur im
Geschäftsarchiv.</p>
"""


def kapitel() -> list[Kapitel]:
    """Alle Kapitel, in der Reihenfolge, in der man sie liest."""
    from mailburg.search.query import describe_syntax

    return [
        Kapitel("ueberblick", "Überblick", _UEBERBLICK),
        Kapitel("archiv", "Das Archiv", _ARCHIV.format(menue=(
            _menue("Archiv → Neues Archiv anlegen …",
                   "Legt ein neues, leeres Archiv an – etwa ein privates "
                   "neben dem geschäftlichen.")
            + _menue("Archiv → Archiv wechseln …",
                     "Wechselt zu einem vorhandenen Archiv.")
            + _menue("Archiv → Zuletzt benutzt",
                     "Die zuletzt geöffneten Archive mit ihrem Namen. Wer "
                     "ein geschäftliches und ein privates Archiv führt, "
                     "wechselt hierüber, ohne den Pfad zu suchen.")
            + _menue("Archiv → Beenden",
                     "Schließt MailBurg. Ein laufender Abruf im Hintergrund "
                     "läuft davon unabhängig weiter.")
        ))),
        Kapitel("postfaecher", "Postfächer", _POSTFAECHER.format(menue=(
            _menue("Einstellungen → Postfächer verwalten …",
                   "Postfächer hinzufügen, Passwörter ändern, ein Postfach "
                   "stilllegen oder entfernen. Ein stillgelegtes Postfach "
                   "bleibt eingerichtet, wird beim Abruf aber übergangen. "
                   "Die bereits archivierten Mails bleiben in jedem Fall "
                   "erhalten.")
        ))),
        Kapitel("zugaenge", "Zugänge", _ZUGAENGE.format(menue=(
            _menue("Einstellungen → Zugänge verwalten …",
                   "Wer sich anmelden darf und welche Postfächer er sieht. "
                   "Nur im Geschäftsarchiv: Ein Privatarchiv gehört einem "
                   "Menschen, und der sitzt davor.")
        ))),
        Kapitel("abrufen", "Mails holen", _ABRUFEN.format(menue=(
            _menue("Post → Jetzt abrufen (F5)",
                   "Holt sofort, was neu ist. Am Ende steht, ob alle "
                   "Postfächer erreichbar waren.")
            + _menue("Post → Lokale Mailordner einlesen …",
                     "Übernimmt Post aus Dateien auf Ihrer Platte statt "
                     "vom Server: Thunderbird-Profile mit allen Konten "
                     "und Unterordnern, Maildir-Verzeichnisse – so legt "
                     "Evolution seine lokalen Ordner ab –, einzelne "
                     "MBOX-Dateien und Verzeichnisse voller "
                     "»eml«-Dateien. Der Weg zu Postfächern, die es "
                     "online längst nicht mehr gibt. Gelesen wird nur; "
                     "an Ihren Dateien ändert MailBurg nichts.")
            + _menue("Einstellungen → Was von selbst laufen soll "
                     "(Automatisierung) …",
                     "Richtet den regelmäßigen Abruf ein – alle 15 Minuten "
                     "bis einmal täglich – und die regelmäßige Sicherung "
                     "des Archivs in einen Ordner Ihrer Wahl.")
        ))),
        Kapitel("suchen", "Suchen", _SUCHEN.format(
            syntax=describe_syntax(),
            menue=_menue("Suchen → Ausführlich suchen … (Strg+F)",
                         "Eine Maske mit Feldern für Absender, Zeitraum, "
                         "Anhänge und mehr. Sie zeigt dabei, wie der "
                         "Suchausdruck lautet, den sie zusammensetzt."),
        )),
        Kapitel("ansicht", "Die Ansicht einrichten", _ANSICHT.format(menue=(
            _menue("Ansicht → Fenster auf Standard zurücksetzen",
                   "Größe und Aufteilung so, wie MailBurg das erste Mal "
                   "aufging. Ihre gespeicherte eigene Ansicht bleibt dabei "
                   "erhalten.")
            + _menue("Ansicht → Schrift größer (Strg++)",
                     "Vergrößert die Schrift im ganzen Fenster. Auf einem "
                     "kleinen Bildschirm ist die Vorgabe vieler "
                     "Arbeitsumgebungen zu klein – und ein Archiv liest man "
                     "nicht im Vorbeigehen.")
            + _menue("Ansicht → Schrift kleiner (Strg+−)",
                     "Wieder zurück, Schritt für Schritt.")
            + _menue("Ansicht → Schrift zurücksetzen (Strg+0)",
                     "Zurück auf die Größe, die Ihr System vorgibt.")
            + _menue("Ansicht → Postfach nach oben (Strg+Auf)",
                     "Rückt das gewählte Postfach eine Stelle nach oben.")
            + _menue("Ansicht → Postfach nach unten (Strg+Ab)",
                     "Rückt es eine Stelle nach unten.")
            + _menue("Ansicht → Eigene Ansicht speichern",
                     "Legt die jetzige Größe, Aufteilung und Reihenfolge ab.")
            + _menue("Ansicht → Eigene Ansicht laden",
                     "Kehrt zur gespeicherten Ansicht zurück.")
        ))),
        Kapitel("journal", "Das Journal", _JOURNAL.format(menue=(
            _menue("Archiv → Journal prüfen",
                   "Prüft die Kette und vergleicht das Protokoll mit dem, "
                   "was tatsächlich auf der Platte liegt.")
        ))),
        Kapitel("scans", "Eingescannte PDF", _SCANS.format(menue=_menue(
            "Post → Eingescannte PDF lesen …",
            "Liest die wartenden Dokumente. Die Zahl dahinter sagt, wie "
            "viele es sind.",
        ))),
        Kapitel("zurueck", "Eine Mail zurückholen", _ZURUECK),
        Kapitel("aufraeumen", "Postfach aufräumen", _AUFRAEUMEN),
        Kapitel("fristen", "Geschäftsarchiv und Fristen", _FRISTEN),
        Kapitel("tipps", "Tipps", _TIPPS.format(menue=(
            _menue("Archiv → Archiv sichern …",
                   "Packt das ganze Archiv in eine Datei mit Datum im "
                   "Namen. Der Suchindex kommt nicht mit.")
            + _menue("Archiv → Sicherung importieren …",
                     "Nimmt die Mails einer Sicherung in das geöffnete "
                     "Archiv auf – mit ihrem ursprünglichen Postfach und "
                     "Ordner. Doppelte werden erkannt, dieselbe Sicherung "
                     "lässt sich also gefahrlos zweimal einlesen.")
            + _menue("Archiv → Sicherung in neues Archiv …",
                     "Macht aus einer Sicherung ein eigenes, neues Archiv. "
                     "Das Zielverzeichnis muss leer sein, und der "
                     "Suchindex wird anschließend neu aufgebaut.")
        ))),
    ]


class Hilfefenster(QDialog):
    """Kapitel links, Text rechts."""

    def __init__(self, eltern=None, beginnen_bei: str = "ueberblick") -> None:
        super().__init__(eltern)
        self.setWindowTitle("MailBurg – Handbuch")
        self.setMinimumSize(860, 620)
        self.kapitel = kapitel()

        self.liste = QListWidget()
        self.liste.setAccessibleName("Kapitel")
        for stueck in self.kapitel:
            eintrag = QListWidgetItem(stueck.titel)
            eintrag.setData(Qt.UserRole, stueck.kennung)
            self.liste.addItem(eintrag)
        self.liste.currentRowChanged.connect(self._zeigen)

        self.text = QTextBrowser()
        # Verweise über das Stylesheet einfärben, nicht Stück für Stück:
        # Qts Standardblau erreicht auf dunklem Grund ein
        # Kontrastverhältnis von 1,8 - ein Link, den man nur findet, wenn
        # man weiß, dass er da ist.
        from mailburg.ui import farben

        self.text.document().setDefaultStyleSheet(
            f"a {{ color: {farben.link()}; }}"
        )
        self.text.setOpenLinks(False)
        self.text.setAccessibleName("Hilfetext")
        # Querverweise springen ins Kapitel, statt einen Browser zu öffnen.
        self.text.anchorClicked.connect(self._springen)

        teiler = QSplitter(Qt.Horizontal)
        teiler.addWidget(self.liste)
        teiler.addWidget(self.text)
        teiler.setSizes([230, 630])

        schliessen = QDialogButtonBox(QDialogButtonBox.Close)
        # Ausdrücklich beschriftet: Qts eigene Übersetzung greift nur,
        # wenn die Sprachdateien vorhanden sind - auf einem englischen
        # System stünde dort sonst "Close" mitten im deutschen Text.
        schliessen.button(QDialogButtonBox.Close).setText("Schließen")
        schliessen.rejected.connect(self.accept)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(teiler, 1)
        aufbau.addWidget(schliessen)

        self.zeige(beginnen_bei)

    def zeige(self, kennung: str) -> None:
        """Springt zu einem Kapitel."""
        for nummer, stueck in enumerate(self.kapitel):
            if stueck.kennung == kennung:
                self.liste.setCurrentRow(nummer)
                return
        self.liste.setCurrentRow(0)

    def _zeigen(self, zeile: int) -> None:
        if 0 <= zeile < len(self.kapitel):
            self.text.setHtml(self.kapitel[zeile].text)
            self.text.verticalScrollBar().setValue(0)

    def _springen(self, ziel: QUrl) -> None:
        self.zeige(ziel.toString().lstrip("#"))


def oeffnen(eltern=None, kapitel_kennung: str = "ueberblick") -> None:
    """Öffnet das Handbuch bei einem bestimmten Kapitel."""
    Hilfefenster(eltern, kapitel_kennung).exec()
