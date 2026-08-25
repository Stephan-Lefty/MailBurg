[Deutsch](RECHTLICHES.md) | [Übersicht](README.md) | [Änderungsprotokoll](CHANGELOG.md)

# Rechtliches

Was MailBurg leisten kann, was es nicht leisten kann, und worauf Sie beim
Archivieren von E-Mail achten müssen.

> **Kein Rechtsrat.** Diese Seite fasst den Regelfall zusammen, damit Sie
> wissen, wonach Sie fragen müssen. Sie ersetzt nicht die Auskunft eines
> Steuerberaters oder Rechtsanwalts. Ob eine bestimmte Mail aufbewahrungs-
> pflichtig ist, kann nur beurteilen, wer den Sachverhalt kennt.

## Das Wichtigste zuerst: Keine Software ist GoBD-konform

Es gibt keine Zertifizierung, die einer Software bescheinigt, dass sie die GoBD
erfüllt – und wer etwas anderes behauptet, verkauft Ihnen etwas. Die GoBD
betreffen den gesamten Ablauf beim Anwender: wie Belege hereinkommen, wer sie
prüft, wie archiviert wird, wie das dokumentiert ist. Ein Programm ist davon
ein Baustein.

Verantwortlich für die **Verfahrensdokumentation** ist ausschließlich der
Steuerpflichtige. MailBurg kann dabei helfen, indem es den technischen Teil aus
seiner eigenen Konfiguration erzeugt – den organisatorischen Teil müssen Sie
ergänzen.

Was MailBurg beiträgt: unveränderbare Ablage, lückenlose Protokollierung,
Nachweisbarkeit von Löschungen, Fristenüberwachung. Das ist die technische
Grundlage. Mehr nicht, aber auch nicht weniger.

## Privat oder geschäftlich – der entscheidende Unterschied

**Privat.** Wer ausschließlich eigene Mails archiviert, verarbeitet
personenbezogene Daten „zur Ausübung ausschließlich persönlicher oder
familiärer Tätigkeiten". Nach Art. 2 Abs. 2 lit. c DSGVO gilt die Verordnung
dafür **nicht**. Keine Fristen, keine Auskunftspflichten, keine
Verfahrensdokumentation.

**Aber Vorsicht:** Diese Ausnahme wird streng ausgelegt. Sobald ein Konto auch
geschäftlich genutzt wird – bei Selbständigen praktisch immer –, entfällt sie.
Es genügt schon, dass dieselbe Adresse für beides dient.

**Geschäftlich.** Dann gelten Aufbewahrungspflichten, DSGVO und GoBD
gleichzeitig. Legen Sie das Archiv mit `--modus geschaeftlich` an.

## Aufbewahrungsfristen

Die Frist beginnt jeweils mit dem **Ende des Kalenderjahres**, nicht am Tag der
Mail. Eine Rechnung vom März 2025 ist in Deutschland bis Ende 2033 zu halten.

| Land | Handelsbriefe | Buchungsbelege | Grundlage |
|---|---|---|---|
| Deutschland | 6 Jahre | 8 Jahre | § 257 HGB, § 147 AO |
| Österreich | 7 Jahre | 7 Jahre | § 132 BAO, § 212 UGB |
| Schweiz | 10 Jahre | 10 Jahre | Art. 958f OR, GeBüV |

Die deutsche Frist für Buchungsbelege wurde zum 1. Januar 2025 durch das Vierte
Bürokratieentlastungsgesetz von zehn auf acht Jahre verkürzt. Für Unternehmen
unter Aufsicht der BaFin bleibt es bei zehn Jahren – dafür gibt es einen
Schalter in den Archiveinstellungen.

Zu beachten: Die E-Mail selbst ist Handelsbrief, eine angehängte Rechnung ist
Buchungsbeleg. In einem Objekt können also **zwei verschiedene Fristen** stecken.

## DSGVO und Aufbewahrung – der Konflikt und seine Auflösung

Art. 17 DSGVO gibt Betroffenen ein Recht auf Löschung. Handels- und Steuerrecht
verlangen Aufbewahrung. Beides zugleich geht nicht.

Die Auflösung: Gesetzliche Aufbewahrungspflichten gehen im Zweifel vor
(Art. 17 Abs. 3 lit. b DSGVO). Aber **nach Ablauf der Frist** verlangt
Art. 5 Abs. 1 lit. e (Speicherbegrenzung), dass die Daten auch wirklich
verschwinden. Ein Archiv, das nie löscht, ist kein sicheres Archiv, sondern ein
Datenschutzverstoß mit Verfallsdatum.

MailBurg bildet beide Richtungen ab: Fristen schützen vor zu frühem Löschen und
melden, wenn etwas fällig wird. Gelöscht wird nie automatisch, sondern nur nach
ausdrücklicher Bestätigung.

**Grabsteine.** Wird eine Mail entfernt, verschwindet ihr Inhalt, aber das
Journal behält einen Eintrag: wer, wann, aus welchem Grund. Damit ist ein
Löschverlangen erfüllt *und* nachweisbar, dass nichts heimlich verschwand.

## Der häufigste Fehler: private Mails im Firmenkonto

Erlaubt ein Arbeitgeber die private Nutzung des dienstlichen Postfachs, darf er
private Nachrichten **nicht ohne Weiteres mitarchivieren**. Das ist der
klassische Stolperstein bei der Mailarchivierung in Deutschland, und er führt
regelmäßig zu Datenschutzverstößen.

Drei Wege, das zu regeln:

1. Private Nutzung per Betriebsvereinbarung untersagen.
2. Private Nutzung erlauben, aber betroffene Mails von der Archivierung
   ausnehmen – etwa über einen eigenen Ordner oder eine Betreffkennzeichnung.
3. Eine Einwilligung der Beschäftigten einholen (in der Praxis heikel, weil im
   Arbeitsverhältnis an der Freiwilligkeit gezweifelt wird).

Kommt ein Betriebsrat hinzu, ist er nach § 87 BetrVG zu beteiligen.

*Die Ausschlussregeln für Weg 2 sind in MailBurg noch nicht umgesetzt – siehe
[TODO.md](TODO.md).*

## Archiv in der Cloud

Liegt das Archiv auf einem Nextcloud-Server, den ein Dienstleister betreibt, ist
das eine **Auftragsverarbeitung** nach Art. 28 DSGVO. Dafür braucht es einen
Vertrag mit dem Anbieter. Betreiben Sie den Server selbst, entfällt das.

Unabhängig davon verlangt Art. 32 DSGVO angemessene Sicherheitsmaßnahmen. Für
ein Archiv außer Haus heißt das in aller Regel: verschlüsseln.

*Die Verschlüsselung ist noch nicht umgesetzt – siehe [TODO.md](TODO.md).*

## Was die Hash-Kette beweist und was nicht

Die Kette beweist die **Reihenfolge** und die **Unversehrtheit** der Einträge.
Wer nachträglich etwas ändert, muss alle folgenden Einträge neu berechnen –
und selbst dann verrät ihn das nächste Siegel.

Was sie **nicht** beweist, ist der Zeitpunkt. Wer Zugriff auf das gesamte
Journal hat und genug Aufwand treibt, kann eine in sich stimmige Kette neu
schreiben. Dagegen hilft nur ein Zeitstempel von dritter Seite nach RFC 3161,
der einen Stand zu einem bestimmten Datum festschreibt. Das Format sieht das
Feld vor; die Anbindung ist noch offen.

## Quellen

- [Art. 2 DSGVO – Sachlicher Anwendungsbereich](https://dsgvo-gesetz.de/art-2-dsgvo/)
- [Aufbewahrungsfristen 2026 nach dem BEG IV](https://onlinebilanz.de/aufbewahrungsfristen-2026-tabelle-unternehmen/)
- [E-Mail-Archivierung: DSGVO, GoBD und Rechtssicherheit](https://ibp-kanzlei.de/e-mail-archivierung-und-aufbewahrungspflichten-dsgvo-gobd-und-rechtssicherheit/)
- [Warum ein Testat nicht alles abdeckt](https://www.continia.com/de/blog/gob-und-gobd-was-unternehmen-wirklich-beachten-muessen-und-warum-ein-testat-nicht-alles-abdeckt/)
- [E-Mail-Archivierung – DSGVO-Pflicht oder Kür?](https://externer-datenschutzbeauftragter-dresden.de/datenschutz/e-mail-archivierung-dsgvo-pflicht-oder-kuer/)
