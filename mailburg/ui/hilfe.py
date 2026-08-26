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
dieses Verzeichnis. <i>Hilfe → Suchsprache</i>, <i>Hilfe → Was das Journal ist</i> und
<i>Hilfe → Postfach aufräumen</i> führen zum selben Handbuch, nur
gleich ans passende Kapitel.</p>

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

<p><b>Wenn das Zertifikat abgelehnt wird.</b> Läuft Ihr Mailserver bei
einem größeren Anbieter, weist er sich oft unter dessen Namen aus.
MailBurg sieht dann nach, für welchen Namen das Zertifikat gilt, und
schlägt ihn vor. Nehmen Sie den Vorschlag an, ist die Verbindung danach
vollständig geprüft. Eine Möglichkeit, die Prüfung einfach abzuschalten,
gibt es bewusst nicht.</p>

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

<p>Ein Klick mit der <b>rechten Maustaste</b> auf eine Nachricht führt
weiter:</p>

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

<p><b>Es dauert.</b> Etwa fünf bis acht Sekunden je Seite. Bei hundert
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

<p>Beim Abruf über die Kommandozeile wird nebenbei immer ein Häppchen
miterledigt. Wer den <a href="#abrufen">Abruf im Hintergrund</a>
eingerichtet hat, muss sich also meist gar nicht darum kümmern – der
Rückstand arbeitet sich von selbst ab.</p>

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
            _menue("Post → Postfächer verwalten …",
                   "Postfächer hinzufügen, Passwörter ändern, ein Postfach "
                   "stilllegen oder entfernen. Ein stillgelegtes Postfach "
                   "bleibt eingerichtet, wird beim Abruf aber übergangen. "
                   "Die bereits archivierten Mails bleiben in jedem Fall "
                   "erhalten.")
        ))),
        Kapitel("abrufen", "Mails holen", _ABRUFEN.format(menue=(
            _menue("Post → Jetzt abrufen (F5)",
                   "Holt sofort, was neu ist. Am Ende steht, ob alle "
                   "Postfächer erreichbar waren.")
            + _menue("Post → Abruf im Hintergrund …",
                     "Richtet den regelmäßigen Abruf ein – alle 15 Minuten "
                     "bis einmal täglich.")
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
            + _menue("Archiv → Sicherung zurückholen …",
                     "Macht aus einer solchen Datei wieder ein Archiv. Das "
                     "Zielverzeichnis muss leer sein, und der Suchindex "
                     "wird anschließend neu aufgebaut.")
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
