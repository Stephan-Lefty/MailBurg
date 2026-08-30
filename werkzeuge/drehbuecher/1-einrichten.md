# Drehbuch 1: MailBurg einrichten

**Länge:** etwa 5 Minuten. **Ton:** ruhig, keine Musik, keine Werbesprache.

**Vor der Aufnahme lesen — der wichtigste Punkt:** In diesem Video werden
echte Postfächer eingerichtet. Nehmen Sie **nicht** Ihre eigenen auf. Für
die Aufnahme gibt es das Vorführarchiv (`werkzeuge/vorfuehrarchiv.py`);
für den Assistenten brauchen Sie ein Wegwerf-Postfach, dessen Adresse Sie
zeigen dürfen.

---

## Szene 1 — Wozu das Ganze (0:00–0:35)

**Auf dem Bildschirm:** Ein volles Postfach im Mailprogramm. Langsam
nach unten scrollen.

**Gesprochen:**

> Das hier sind zwölf Jahre Post. Rechnungen, Verträge, Behördenschreiben —
> und alles liegt auf dem Server eines Anbieters, der es irgendwann löschen
> wird oder Geld dafür verlangt.
>
> MailBurg holt diese Post auf Ihre eigene Platte und macht sie durchsuchbar.
> Es liest die Postfächer nur, es verändert dort nichts. In den nächsten fünf
> Minuten richten wir es einmal ein.

**Hinweis:** Nicht sagen „sicher" oder „revisionssicher". MailBurg
unterstützt revisionssicheren Betrieb, es stellt ihn nicht her.

---

## Szene 2 — Installieren, Windows (0:35–1:15)

**Auf dem Bildschirm:** Die Release-Seite auf GitHub, `MailBurg.exe`
anklicken, Download-Anzeige, dann Doppelklick im Download-Ordner.

**Gesprochen:**

> Unter Windows ist es eine einzige Datei. Kein Python, keine Installation,
> keine Administratorrechte. Herunterladen, doppelklicken.

**Auf dem Bildschirm:** Der SmartScreen-Hinweis erscheint.

**Gesprochen:**

> Und dann kommt das hier. „Der Computer wurde durch Windows geschützt."
> Das ist zu erwarten: Die Datei ist nicht signiert, weil ein Zertifikat
> dafür mehrere hundert Euro im Jahr kostet. Auf „Weitere Informationen"
> klicken, dann auf „Trotzdem ausführen".
>
> Wenn Sie das nicht wollen — verständlich —, steht die Prüfsumme auf der
> Release-Seite. Wie man sie nachrechnet, steht in der Anleitung.

**Hinweis:** Diesen Teil nicht beschönigen und nicht überspringen. Wer ihn
das erste Mal sieht, bricht sonst ab.

---

## Szene 3 — Installieren, Linux (1:15–1:45)

**Auf dem Bildschirm:** Ein Terminal, die drei Befehle eintippen (nicht
einfügen — das Tippen zeigt, dass es wirklich drei sind).

```
git clone https://github.com/Stephan-Lefty/MailBurg.git
cd MailBurg
./install.sh
```

**Gesprochen:**

> Unter Linux drei Befehle. Das Skript legt eine eigene Python-Umgebung an,
> installiert alles und trägt einen Menüeintrag ein. Es fragt vorher, was es
> tut, und braucht keine Verwaltungsrechte.
>
> Rechnen Sie mit fünf bis fünfzehn Minuten — die grafische Oberfläche allein
> ist rund hundertfünfzig Megabyte. Solange sich etwas bewegt, ist alles in
> Ordnung.

**Auf dem Bildschirm:** Die Frage nach poppler und tesseract.

**Gesprochen:**

> Hier fragt es nach zwei Zusatzprogrammen. Sagen Sie Ja. Ohne das zweite
> bleibt der Inhalt eingescannter Rechnungen für die Suche unsichtbar — nicht
> schwerer zu finden, sondern gar nicht. Und das merken Sie erst Jahre später.

**Hinweis:** Die Installation im Schnelldurchlauf zeigen, nicht in Echtzeit.
Einblendung: „gekürzt".

---

## Szene 4 — Der Assistent, erste Seite (1:45–2:15)

**Auf dem Bildschirm:** MailBurg startet, die Willkommensseite.

**Gesprochen:**

> Beim ersten Start führt ein Assistent durch die Einrichtung. Auf dieser
> Seite steht, was das Programm tut und was nicht: Es liest Ihre Postfächer
> nur, es baut keine Verbindung nach außen auf, es sucht nicht nach
> Aktualisierungen.
>
> Lesen Sie das einmal. Sie entscheiden hier, ob Sie einem Programm Ihre
> gesamte Post anvertrauen.

---

## Szene 5 — Wo das Archiv liegt (2:15–3:05)

**Auf dem Bildschirm:** Die zweite Seite. Die Ortsauswahl aufklappen, den
freien Platz zeigen.

**Gesprochen:**

> Jetzt der Ort. MailBurg schlägt welche vor und zeigt, wie viel Platz dort
> frei ist.
>
> Nehmen Sie möglichst nicht die Platte, auf der Ihr Betriebssystem liegt.
> Geht die kaputt, wäre sonst beides weg — das System und das Archiv. Eine
> externe Platte ist eine gute Wahl.

**Auf dem Bildschirm:** Die Wahl zwischen Privat- und Geschäftsarchiv.

**Gesprochen:**

> Darunter die wichtigere Entscheidung.
>
> Ein Privatarchiv kennt keine Aufbewahrungsfristen. Sie löschen jederzeit,
> was Sie wollen. Das entspricht der Rechtslage: Wer ausschließlich eigene
> Post archiviert, unterliegt der DSGVO gar nicht.
>
> Ein Geschäftsarchiv protokolliert jeden Vorgang, sichert die Kette der
> Einträge gegen nachträgliche Änderungen und bremst das Löschen — sechs,
> acht oder zehn Jahre, je nach Einstufung und Rechtsraum.
>
> Im Zweifel führen Sie zwei Archive. Geschäftspost ins Geschäftsarchiv,
> private ins private. Das ist keine Ordnungsliebe: Ein Geschäftsarchiv
> bremst das Löschen jahrelang, und für private Post verlangt die DSGVO
> genau das Gegenteil.

**Hinweis:** Hier ruhig langsamer sprechen. Das ist die einzige
Entscheidung im Assistenten, die sich später nur mit Aufwand ändern lässt.

---

## Szene 6 — Postfächer (3:05–4:10)

**Auf dem Bildschirm:** Die dritte Seite mit den aus Thunderbird
übernommenen Postfächern.

**Gesprochen:**

> Ist Thunderbird installiert, liest MailBurg dessen Einstellungen aus.
> Server, Benutzername und Verschlüsselung stehen dann schon da.
>
> Die Passwörter nicht. Die müssen Sie einmal von Hand eingeben.

**Auf dem Bildschirm:** In ein Passwortfeld tippen.

**Gesprochen:**

> Technisch ließen sie sich mitlesen — die Datei liegt offen im
> Thunderbird-Profil. Aber ein Programm, das die Passwörter anderer
> Programme abgreift, verhält sich wie Schadsoftware. Einem Archiv
> vertrauen Sie jahrzehntealte Post an; dieses Vertrauen ist mehr wert
> als die gesparte Tipparbeit.
>
> Abgelegt werden sie im Schlüsselbund Ihres Systems, nie in einer Datei
> des Programms.

**Auf dem Bildschirm:** Ein Postfach wird geprüft, der Haken erscheint.

**Gesprochen:**

> Jedes Postfach wird sofort ausprobiert. Sie sehen also gleich, ob es
> klappt — und nicht erst beim ersten Abruf.

**Hinweis (nur aufnehmen, wenn es auftritt):** Wird ein Zertifikat
abgelehnt und MailBurg schlägt einen anderen Servernamen vor — das ist
zeigenswert. Dann sagen: „MailBurg sieht nach, für welchen Namen das
Zertifikat gilt, und schlägt ihn vor. Eine Möglichkeit, die Prüfung
einfach abzuschalten, gibt es bewusst nicht."

---

## Szene 7 — Fertig, und was gleich läuft (4:10–4:50)

**Auf dem Bildschirm:** Die Abschlussseite mit den beiden Häkchen.

**Gesprochen:**

> Letzte Seite. Hier stellen Sie ein, dass MailBurg regelmäßig im
> Hintergrund abruft.
>
> Dafür muss das Programm weder geöffnet bleiben noch mitstarten. Nötig ist
> nur, dass Sie angemeldet sind — daran hängt der Schlüsselbund. War der
> Rechner aus, wird der versäumte Abruf beim nächsten Anmelden nachgeholt.
>
> Und das untere Häkchen holt gleich zum ersten Mal alles.

**Auf dem Bildschirm:** Der erste Abruf läuft, der Fortschritt bewegt sich.

**Gesprochen:**

> Der erste Abruf holt den ganzen Bestand. Bei zwölf Jahren Post dauert das.
> Sie können weiterarbeiten, und wenn Sie abbrechen, macht der nächste Lauf
> dort weiter, wo dieser aufgehört hat.

---

## Szene 8 — Ausblick (4:50–5:10)

**Auf dem Bildschirm:** Das Hauptfenster mit gefülltem Archiv, unten
rechts die Zahl der Mails.

**Gesprochen:**

> Das war die Einrichtung. Unten rechts steht ab jetzt immer, wie viele
> Mails im Archiv liegen und wann zuletzt abgerufen wurde.
>
> Wie man darin sucht, eine Mail zurückholt und das Postfach beim Anbieter
> entlastet — darum geht es im zweiten Video.

**Hinweis:** Kein Abspann mit Musik. Ein Standbild mit der Adresse des
Repos genügt.
