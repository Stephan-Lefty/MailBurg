[Übersicht](../README.md) | [Änderungsprotokoll](../CHANGELOG.md) | [TODO](../TODO.md) | [Rechtliches](../RECHTLICHES.md)

# Anleitungen

- **[Erste Schritte](erste-schritte.md)** – von der Installation bis zum
  ersten durchsuchbaren Archiv, Schritt für Schritt mit Bildern.
- **[Die Oberfläche](oberflaeche.md)** – jedes Fenster und jeder Menüpunkt,
  mit Bild und Erklärung.
- **[Postfächer einrichten](postfaecher-einrichten.md)** – IMAP-Konten anlegen,
  App-Passwörter bei den großen Anbietern, was archiviert wird und was nicht.
- **[Anmeldung per OAuth2](oauth2.md)** – für Microsoft-Konten, die kein
  Passwort mehr annehmen. Warum Sie sich dafür eine eigene Anwendung
  registrieren müssen, und wie das in fünf Minuten geht.
- **[Regelmäßig abrufen](zeitsteuerung.md)** – nächtlicher Abruf unter Linux,
  Windows und macOS, und warum der Schlüsselbund dabei der Haken ist.
- **[Postfach entlasten](postfach-entlasten.md)** – der eigentliche Zweck:
  nachweisen, dass alles im Archiv ist, und erst dann beim Anbieter aufräumen
  lassen. Mit der Einstellung in Thunderbird und einer Liste zum Abhaken.
- **[Private Post im Geschäftsarchiv](regeln.md)** – wie Regeln den Verein
  und die Familie von selbst als privat einstufen, damit sie nicht unter
  Aufbewahrungsfristen fallen, die für sie nicht gelten.
- **[Post aus dem Archiv zurückholen](zurueckspielen.md)** – eine einzelne
  Nachricht ins Mailprogramm, oder ein ganzes Postfach als Maildir, MBOX oder
  einzelne `.eml`. Welches Format wofür taugt, und warum zweimal
  zurückspielen nichts doppelt schreibt.
- **[Das Archiv sichern](sicherung.md)** – warum ein Archiv kein Backup ist,
  wie aus zehntausend Dateien eine wird, und wie sie in die Cloud kommt.
- **[JMAP – der Nachfolger von IMAP](jmap.md)** – was es ist, warum es für
  ein Archiv der bessere Weg ist, und wie man ein Postfach darüber
  einrichtet. Können bisher nur wenige Anbieter.
- **[Das Archiv verschlüsseln](verschluesselung.md)** – für Post, die das
  Haus verlässt: Passwort, Notschlüssel, was geschützt ist und was nicht,
  und wie ein bestehendes Archiv umzieht.
- **[MailBurg unter Windows](windows.md)** – Einrichtung, Ablageorte,
  Thunderbird und Outlook.
- **[Das Archiv im Browser einrichten](server-einrichten.md)** – vom leeren
  Rechner bis zum Archiv im Browser: Tresor, Zugänge, Dienst, Reverse
  Proxy. Für Debian durchgespielt, der Windows-Teil noch ungeprüft.
- **[Das Archiv im Browser: der Entwurf](server.md)** – die Überlegungen
  dahinter. Was der Server können muss, welche Entscheidungen warum so
  gefallen sind und was noch offen ist.

Die Suchsprache erklärt das Programm selbst:

```bash
mailburg suchhilfe
```

Wie das Archiv aufgebaut ist und warum, steht in der
[Übersicht](../README.md). Zur Rechtslage in Deutschland, Österreich und der
Schweiz – Aufbewahrungsfristen, GoBD, DSGVO – siehe
[RECHTLICHES.md](../RECHTLICHES.md).

Die Abbildungen entstehen aus `werkzeuge/screenshots.py` – mit erfundenen Postfächern, damit nie fremde Post darin steht, und damit sie nicht veralten, wenn sich die Oberfläche ändert.
