"""Den technischen Teil einer Verfahrensdokumentation erzeugen.

Die GoBD verlangen für jedes datenverarbeitende System eine
Verfahrensdokumentation (Rz. 151 ff.): Sie soll einem sachverständigen
Dritten in angemessener Zeit zeigen, wie die Daten entstehen, wo sie
liegen und wie sie gegen Verlust und Veränderung geschützt sind.

**Verantwortlich dafür ist ausschließlich der Steuerpflichtige.**
MailBurg kann nur den Teil beisteuern, den es selbst weiß: seine
Fassung, den Ablageort, das Verfahren, die eingerichteten Postfächer,
die Zeitpläne, die Bestandszahlen. Alles Organisatorische – wer
zuständig ist, wer vertreten darf, was bei einem Ausfall geschieht –
kann es nicht wissen und erfindet es auch nicht.

**Lücken bleiben sichtbar.** Was fehlt, steht als ``[BITTE ERGÄNZEN]``
im Text. Eine Dokumentation, die vollständig aussieht und es nicht ist,
wäre schlimmer als gar keine: Sie fällt erst in der Prüfung auf, und
dann ist keine Zeit mehr.
"""

from __future__ import annotations

from datetime import datetime

#: Was der Anwender ergänzen muss. Als auffälliger Platzhalter, nicht
#: als leere Zeile – wer die Datei überfliegt, soll die Lücken sehen.
LUECKE = "**[BITTE ERGÄNZEN]**"


def takt_in_worten(minuten: int) -> str:
    """»Alle 1440 Minuten« ist keine Angabe, mit der jemand rechnet.

    Ein Prüfer liest dieses Papier, kein Programmierer. »Einmal
    täglich« steht in derselben Zeile und sagt dasselbe, nur
    verständlich.
    """
    if minuten % 1440 == 0:
        tage = minuten // 1440
        return "einmal täglich" if tage == 1 else f"alle {tage} Tage"
    if minuten % 60 == 0:
        stunden = minuten // 60
        return "stündlich" if stunden == 1 else f"alle {stunden} Stunden"
    return f"alle {minuten} Minuten"


def _abschnitt(titel: str, zeilen: list[str]) -> str:
    return "\n".join([f"## {titel}", "", *zeilen, ""])


def erzeugen(archiv, konten=None, zeitplaene: dict | None = None) -> str:
    """Baut den technischen Teil als Markdown.

    ``konten`` ist die Kontenliste, ``zeitplaene`` ein Wörterbuch mit
    den Angaben zu Abruf und Sicherung. Fehlen sie, bleiben die
    entsprechenden Abschnitte als Lücke stehen – lieber ehrlich leer als
    falsch gefüllt.
    """
    from mailburg import __version__
    from mailburg.core.retention import describe

    heute = datetime.now().strftime("%d.%m.%Y")
    stand = archiv.index.statistics()

    teile: list[str] = [
        f"# Verfahrensdokumentation: E-Mail-Archivierung",
        "",
        f"Archiv **{archiv.name}**, Stand {heute}.",
        "",
        "> **Diese Datei ist ein Entwurf, keine fertige Dokumentation.**",
        "> MailBurg hat den technischen Teil aus seiner eigenen",
        "> Konfiguration erzeugt. Verantwortlich für die",
        "> Verfahrensdokumentation ist ausschließlich der",
        f"> Steuerpflichtige – alles mit {LUECKE} müssen Sie selbst",
        "> ausfüllen, und den ganzen Text sollten Sie prüfen. Eine",
        "> Software kann nicht wissen, wie in Ihrem Betrieb gearbeitet",
        "> wird.",
        "",
    ]

    teile.append(_abschnitt("1. Allgemeine Beschreibung", [
        "**Gegenstand.** Archivierung des E-Mail-Verkehrs zur Erfüllung",
        "handels- und steuerrechtlicher Aufbewahrungspflichten.",
        "",
        f"**Verantwortlicher (Steuerpflichtiger).** {LUECKE}",
        "",
        f"**Anschrift.** {LUECKE}",
        "",
        f"**Zuständig für den Betrieb des Archivs.** {LUECKE}",
        "",
        f"**Vertretung im Verhinderungsfall.** {LUECKE}",
        "",
        f"**Gültig ab.** {LUECKE}",
        "",
        "**Welche Post archiviert wird.** Der ein- und ausgehende",
        "Mailverkehr der unten genannten Postfächer, soweit nicht",
        f"ausgeschlossen. Abgrenzung privater Post: {LUECKE}",
    ]))

    teile.append(_abschnitt("2. Eingesetztes System", [
        f"| | |",
        f"|---|---|",
        f"| Programm | MailBurg {__version__} |",
        f"| Bezugsquelle | https://github.com/Stephan-Lefty/MailBurg |",
        f"| Lizenz | MIT (quelloffen) |",
        f"| Archivkennung | `{archiv.uuid}` |",
        f"| Betriebsart | {archiv.mode.value} |",
        f"| Ablageort | `{archiv.root}` |",
        "",
        f"**Betriebssystem und Rechner.** {LUECKE}",
        "",
        f"**Wer hat Zugriff auf den Ablageort.** {LUECKE}",
    ]))

    verfahren = [
        "**Ablage.** Jede Nachricht wird **bytegenau** so gespeichert, wie",
        "sie empfangen wurde – ohne geglättete Zeilenenden oder reparierte",
        "Kopfzeilen. Nur so bleibt eine vorhandene DKIM-Signatur prüfbar.",
        "",
        "**Dateiname.** Der SHA-256-Fingerabdruck des Inhalts. Daraus",
        "folgt zweierlei: Dieselbe Nachricht zweimal einzulesen erzeugt",
        "keine zweite Datei, und eine nachträglich veränderte Datei fällt",
        "beim Lesen von selbst auf, weil ihr Fingerabdruck nicht mehr zum",
        "Namen passt.",
        "",
        "**Protokoll (Journal).** Jeder Vorgang – Aufnahme, Löschung,",
        "Einstufung, Auskunft – wird protokolliert. Jeder Eintrag trägt",
        "den Fingerabdruck seines Vorgängers; die Einträge hängen damit",
        "zusammen wie die Glieder einer Kette. Wird ein alter Eintrag",
        "nachträglich geändert, zeigt der folgende ins Leere, und die",
        "Prüfung nennt die Stelle.",
        "",
        "**Löschung.** Nur über Grabsteine: Der Inhalt verschwindet, der",
        "Vorgang bleibt protokolliert. Damit lassen sich das Recht auf",
        "Löschung nach Art. 17 DSGVO und die Unveränderbarkeit zugleich",
        "erfüllen.",
        "",
        "**Suchindex.** Liegt außerhalb des Archivs und ist jederzeit aus",
        "dem Protokoll neu erzeugbar. Er ist keine Aufbewahrung, sondern",
        "eine Bequemlichkeit – und muss deshalb nicht gesichert werden.",
    ]
    if archiv.mode.is_business:
        verfahren += [
            "",
            f"**Aufbewahrungsfristen.** {describe(archiv.policy)}",
            "",
            "Die Frist beginnt mit dem Ende des Kalenderjahres, in dem die",
            "Nachricht entstand (§ 147 Abs. 4 AO). MailBurg bremst das",
            "Löschen bis dahin und weist einmal jährlich auf abgelaufene",
            "Fristen hin; gelöscht wird nur nach ausdrücklicher",
            "Bestätigung.",
        ]
    teile.append(_abschnitt("3. Verfahren der Archivierung", verfahren))

    # **Nur die Postfächer dieses Archivs.** Die Kontenliste gilt für das
    # ganze Programm; wer zwei Archive führt, hätte sonst in beiden
    # Dokumentationen dieselben Postfächer stehen - und in keiner der
    # beiden stünde die Wahrheit.
    zeilen = []
    eigene = []
    if konten is not None:
        eigene = [
            k for k in getattr(konten, "konten", [])
            if str(archiv.uuid) in (k.archive or [])
        ]

    if eigene:
        zeilen += [
            "| Postfach | Server | Benutzer |",
            "|---|---|---|",
        ]
        for konto in eigene:
            zustand = "" if konto.aktiv else " *(stillgelegt)*"
            zeilen.append(
                f"| {konto.name}{zustand} | {konto.server} | "
                f"{konto.benutzer} |"
            )
        zeilen += [""]

        # Die Ausschlüsse können je Postfach abweichen. Gemeinsame
        # zuerst, Abweichungen einzeln - sonst behauptet die Tabelle
        # eine Einheitlichkeit, die es nicht gibt.
        mengen = [frozenset(k.ausschluss or []) for k in eigene]
        gemeinsam = set.intersection(*[set(m) for m in mengen]) if mengen else set()
        if gemeinsam:
            zeilen += [
                "**Nicht archivierte Ordner** (in allen Postfächern): "
                + ", ".join(sorted(gemeinsam)),
                "",
            ]
        for konto, menge in zip(eigene, mengen):
            abweichend = set(menge) - gemeinsam
            if abweichend:
                zeilen.append(
                    f"Zusätzlich bei **{konto.name}**: "
                    + ", ".join(sorted(abweichend))
                )
        if gemeinsam:
            zeilen += [
                "",
                "Diese Ordner enthalten Post, die der Anwender bereits",
                "verworfen hat oder die nie versendet wurde. Ob das im",
                f"Einzelfall zulässig ist: {LUECKE}",
            ]
    elif konten is not None:
        zeilen += [
            f"{LUECKE}",
            "",
            "**Diesem Archiv ist kein Postfach zugeordnet.** Es wird also",
            "nichts hineingeholt. Das kann Absicht sein – ein Archiv, das",
            "nur aus einem Import stammt – oder ein Versehen. Nachsehen mit",
            "`mailburg konten zuordnung`.",
        ]
    else:
        zeilen.append(f"{LUECKE} (Postfächer konnten nicht gelesen werden)")
    teile.append(_abschnitt("4. Erfasste Postfächer", zeilen))

    zeilen = []
    if zeitplaene:
        for was, text in zeitplaene.items():
            zeilen.append(f"**{was}.** {text}")
            zeilen.append("")
    else:
        zeilen += [
            f"**Abruf.** {LUECKE}",
            "",
            f"**Sicherung.** {LUECKE}",
            "",
        ]
    zeilen += [
        f"**Auf welchem Datenträger die Sicherungen liegen und wer "
        f"Zugriff darauf hat.** {LUECKE}",
        "",
        f"**Wer prüft, dass sie tatsächlich entstehen.** {LUECKE}",
        "",
        "Das ist die Frage, an der Sicherungen scheitern: Sie werden",
        "eingerichtet und danach nie wieder angesehen. MailBurg bricht",
        "ab, wenn das Ziel nicht erreichbar ist, statt ins Leere zu",
        "schreiben – gemerkt hat das aber nur, wer nachsieht.",
        "",
        "**Prüfung des Archivs.** `mailburg pruefen` vergleicht die",
        "Hash-Kette und den Bestand auf der Platte mit dem Protokoll.",
        "",
        f"**Wie oft wird geprüft, und wer hält das Ergebnis fest.** {LUECKE}",
    ]
    teile.append(_abschnitt("5. Betrieb und Sicherung", zeilen))

    if stand:
        teile.append(_abschnitt("6. Bestand zum Stichtag", [
            f"| | |",
            f"|---|---|",
            f"| Nachrichten | {stand.get('mails', 0):,} |".replace(",", "."),
            f"| davon mit Anhang | {stand.get('anhaenge', 0):,} |".replace(",", "."),
            f"| Protokolleinträge | {archiv.journal.count:,} |".replace(",", "."),
            "",
            f"Erhoben am {heute}.",
        ]))

    teile.append(_abschnitt("7. Was diese Dokumentation nicht leistet", [
        "**Keine Software ist GoBD-konform.** Die GoBD richten sich an den",
        "Steuerpflichtigen, nicht an ein Programm. MailBurg unterstützt",
        "einen revisionssicheren Betrieb – es stellt ihn nicht her. Dazu",
        "gehören immer auch geregelte Abläufe im Betrieb, und die",
        "beschreibt niemand außer Ihnen.",
        "",
        "**Die Hash-Kette hat eine Grenze.** Wer Zugriff auf das Archiv",
        "hat und sich Zeit nimmt, kann sie vollständig neu berechnen.",
        "Dagegen hilft nur ein Siegel, dessen Wert außerhalb des Archivs",
        "liegt – notiert, verschickt oder von einem Zeitstempeldienst",
        "bestätigt.",
        "",
        f"**Wie dieses Papier aufbewahrt und fortgeschrieben wird.** {LUECKE}",
        "",
        "Änderungen an der Verfahrensweise gehören dokumentiert, samt",
        "Datum und Grund. Eine Verfahrensdokumentation ist kein Dokument,",
        "das man einmal schreibt.",
    ]))

    return "\n".join(teile).rstrip() + "\n"
