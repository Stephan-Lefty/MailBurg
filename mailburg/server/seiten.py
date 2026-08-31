"""Die Seiten der Weboberfläche.

**Kein JavaScript, keine fremden Server.** Dieselbe Haltung wie beim
Rest: Was das Programm anzeigt, bringt es mit. Ein Archiv, das beim
Öffnen eine Schriftart von einem Werbenetzwerk nachlädt, verrät jedem
dort, wer wann seine alte Post durchsieht.

Alles hier maskiert, was aus dem Archiv kommt. Ein Betreff ist Text,
den ein Fremder geschrieben hat – er darf niemals als HTML gelten.
"""

from __future__ import annotations

import html
from typing import Any

from mailburg import __version__
from mailburg.core import sprache

_KOPF = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titel}</title>
<style>
  :root {{ color-scheme: light dark; --marke: #c62828; --leise: #667080; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, sans-serif; margin: 0; line-height: 1.5; }}
  header {{ border-bottom: 1px solid #d6dde8; padding: .8rem 1.5rem;
            display: flex; gap: 1.5rem; align-items: baseline;
            flex-wrap: wrap; }}
  header .name {{ font-weight: 700; font-size: 1.15rem; }}
  header .marke {{ color: var(--marke); }}
  header .wer {{ margin-left: auto; color: var(--leise); font-size: .9rem; }}
  main {{ max-width: 62rem; margin: 0 auto; padding: 1.5rem; }}
  form.suche {{ display: flex; gap: .6rem; margin-bottom: .4rem; }}
  form.suche input {{ flex: 1; padding: .55rem .7rem; font-size: 1rem;
                      border: 1px solid #97a1ad; border-radius: 4px; }}
  button {{ padding: .55rem 1.1rem; font-size: 1rem; cursor: pointer;
            border: 1px solid #97a1ad; border-radius: 4px;
            background: transparent; color: inherit; }}
  .ergebnis {{ color: var(--leise); font-size: .9rem; margin: .2rem 0 1.2rem; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: .45rem .6rem;
            border-bottom: 1px solid #d6dde8; vertical-align: top; }}
  th {{ color: var(--leise); font-weight: 600; font-size: .85rem; }}
  td.datum {{ white-space: nowrap; color: var(--leise); }}
  td.groesse {{ white-space: nowrap; color: var(--leise); text-align: right; }}
  a {{ color: #0645ad; }}
  @media (prefers-color-scheme: dark) {{ a {{ color: #6cb6ff; }} }}
  .leer {{ color: var(--leise); padding: 2rem 0; }}
  .blaettern {{ display: flex; gap: 1rem; margin-top: 1.5rem;
                align-items: baseline; }}
  dl.kopf {{ display: grid; grid-template-columns: max-content 1fr;
             gap: .35rem 1.2rem; margin: 0 0 1.5rem; }}
  dl.kopf dt {{ color: var(--leise); }}
  dl.kopf dd {{ margin: 0; }}
  pre.text {{ white-space: pre-wrap; word-wrap: break-word;
              font-family: inherit; margin: 0; }}
  .maske {{ display: grid; grid-template-columns: repeat(auto-fit,
            minmax(16rem, 1fr)); gap: .9rem 1.5rem; margin: 1.5rem 0; }}
  .feld {{ display: flex; flex-direction: column; }}
  .feld.weit {{ grid-column: 1 / -1; }}
  .feld label {{ color: var(--leise); font-size: .85rem; margin-bottom: .2rem; }}
  .feld label.haken {{ color: inherit; font-size: 1rem; }}
  .feld input, .feld select {{ padding: .45rem .55rem; font-size: 1rem;
            border: 1px solid #97a1ad; border-radius: 4px;
            background: transparent; color: inherit; }}
  .feld input[type=checkbox] {{ width: auto; margin-right: .4rem; }}
  .feld small {{ color: var(--leise); font-size: .78rem; margin-top: .15rem; }}
  .ausdruck {{ border-left: 4px solid #97a1ad; padding: .4rem 0 .4rem .8rem; }}
  .ausdruck span {{ color: var(--leise); font-size: .85rem; }}
  .ausdruck code {{ font-size: 1rem; }}
  .ausdruck.leise {{ color: var(--leise); }}
  .postfaecher {{ display: flex; flex-wrap: wrap; gap: .5rem;
                  align-items: baseline; margin: .6rem 0 0; }}
  .postfaecher .was {{ color: var(--leise); font-size: .85rem; }}
  .postfaecher a {{ border: 1px solid #d6dde8; border-radius: 999px;
                    padding: .15rem .7rem; font-size: .88rem;
                    text-decoration: none; }}
  .postfaecher a span {{ color: var(--leise); margin-left: .4rem; }}
  .postfaecher a.gewaehlt {{ border-color: var(--marke); font-weight: 600; }}
  .postfaecher a.alle {{ border-style: dashed; }}
  .verlauf {{ border: 1px solid #d6dde8; border-radius: 4px;
              padding: .2rem 1rem 1rem; margin: 0 0 1.5rem; }}
  .verlauf h2 {{ font-size: .95rem; color: var(--leise); }}
  .verlauf ol {{ list-style: none; padding: 0; margin: 0; }}
  .verlauf li {{ padding: .25rem 0; border-left: 2px solid #d6dde8;
                 padding-left: .8rem; }}
  .verlauf li.hier {{ border-left-color: var(--marke); }}
  .verlauf li span {{ color: var(--leise); font-size: .85rem;
                      margin-right: .5rem; }}
  .verlauf em {{ color: var(--leise); font-style: normal; font-size: .85rem; }}
  .verlauf .hinweis {{ color: var(--leise); font-size: .8rem;
                       margin: .8rem 0 0; }}
  .anhaenge {{ border: 1px solid #d6dde8; border-radius: 4px;
               padding: .2rem 1rem 1rem; margin: 0 0 1.5rem; }}
  .anhaenge h2 {{ font-size: .95rem; color: var(--leise); }}
  .anhaenge ul {{ list-style: none; padding: 0; margin: 0; }}
  .anhaenge li {{ padding: .25rem 0; }}
  .anhaenge span {{ color: var(--leise); font-size: .85rem; }}
  .anmeldung {{ max-width: 22rem; margin: 4rem auto; }}
  .anmeldung label {{ display: block; margin: .8rem 0 .2rem; }}
  .anmeldung input {{ width: 100%; padding: .5rem; font-size: 1rem;
                      border: 1px solid #97a1ad; border-radius: 4px; }}
  .fehler {{ border-left: 4px solid var(--marke); padding: .3rem 0 .3rem .8rem;
             margin: 1rem 0; }}
  footer {{ color: var(--leise); font-size: .85rem; padding: 2rem 1.5rem;
            text-align: center; }}
</style>
</head>
<body>
"""

_FUSS = """<footer>MailBurg {fassung}</footer>
</body>
</html>
"""


def _rahmen(titel: str, inhalt: str, benutzer=None) -> str:
    if benutzer is not None:
        wer = (
            f'<span class="wer">{html.escape(benutzer.anzeigename or benutzer.name)}'
            f' · <a href="/abmelden">Abmelden</a></span>'
        )
    else:
        wer = ""
    return (
        _KOPF.format(titel=html.escape(titel))
        + f'<header><span class="name">MailBurg '
        f'<span class="marke">SERVER</span></span>{wer}</header>\n'
        f"<main>{inhalt}</main>\n"
        + _FUSS.format(fassung=html.escape(__version__))
    )


def anmeldung(fehler: str = "") -> str:
    """Die Anmeldeseite.

    **Die Fehlermeldung nennt nie, was falsch war.** »Anmeldung
    fehlgeschlagen« – nicht »Benutzer unbekannt«, denn das verriete,
    welche Anmeldenamen es gibt.
    """
    warnung = f'<p class="fehler">{html.escape(fehler)}</p>' if fehler else ""
    return _rahmen("Anmelden – MailBurg", f"""
<form class="anmeldung" method="post" action="/anmelden">
  <h1>Anmelden</h1>
  {warnung}
  <label for="name">Anmeldename</label>
  <input id="name" name="name" autocomplete="username" autofocus required>
  <label for="wort">Passwort</label>
  <input id="wort" name="passwort" type="password"
         autocomplete="current-password" required>
  <p><button type="submit">Anmelden</button></p>
</form>
""")


def _postfachleiste(postfaecher: dict[str, int], ausdruck: str) -> str:
    """Welche Postfächer der Angemeldete durchsuchen kann.

    **Warum das sichtbar sein muss.** Wer nur einen Teil des Archivs
    sehen darf, sucht sonst ins Ungewisse: Findet er nichts, weiß er
    nicht, ob es die Mail nicht gibt oder ob sie in einem Postfach
    liegt, das er nicht sieht. Die Leiste beantwortet das, bevor die
    Frage aufkommt.

    Jeder Eintrag grenzt die Suche mit einem Klick darauf ein – wie ein
    Klick in den Postfachbaum des Fensters.
    """
    if not postfaecher:
        return ""

    from urllib.parse import quote

    # Was von einer laufenden Suche übrig bleibt, wenn man die
    # Eingrenzung auf ein Postfach herausnimmt.
    ohne_konto = " ".join(
        wort for wort in ausdruck.split() if not wort.startswith("konto:")
    )
    aktiv = ""
    for wort in ausdruck.split():
        if wort.startswith("konto:"):
            aktiv = wort[len("konto:"):].strip('"')

    stuecke = []
    for name, anzahl in sorted(postfaecher.items()):
        ziel = f"{ohne_konto} konto:{quoten_wenn_noetig(name)}".strip()
        gewaehlt = ' class="gewaehlt"' if name == aktiv else ""
        stuecke.append(
            f'<a href="/?q={quote(ziel)}"{gewaehlt}>{html.escape(name)}'
            f"<span>{anzahl}</span></a>"
        )

    alle = ""
    if aktiv:
        alle = (
            f'<a href="/?q={quote(ohne_konto)}" class="alle">'
            f"alle Postfächer</a>"
        )

    return (
        f'<div class="postfaecher"><span class="was">Sie können suchen in:'
        f"</span>{''.join(stuecke)}{alle}</div>"
    )


def quoten_wenn_noetig(wert: str) -> str:
    """Wie in der Suchsprache – Leerzeichen brauchen Anführungszeichen."""
    from mailburg.search.maske import quoten

    return quoten(wert)


def _zeile(treffer) -> str:
    from mailburg.core import sprache as s

    # Nur der Tag: In einer Liste kostet jede Spalte Platz, und die
    # Uhrzeit steht in der Nachricht selbst.
    datum = s.zeitpunkt(treffer.date or "").split(",")[0]
    absender = treffer.from_name or treffer.from_addr or ""
    klammer = " 📎" if treffer.has_attachments else ""
    return (
        f"<tr>"
        f'<td class="datum">{html.escape(datum)}</td>'
        f"<td>{html.escape(absender)}</td>"
        f'<td><a href="/nachricht/{html.escape(treffer.hash)}">'
        f"{html.escape(treffer.subject)}</a>{klammer}</td>"
        f'<td class="groesse">{s.groesse(treffer.size)}</td>'
        f"</tr>"
    )


def trefferliste(benutzer, ausdruck: str, treffer, gesamt: int,
                 seite_nr: int, je_seite: int, postfaecher=None) -> str:
    """Die Suchseite mit ihrer Trefferliste.

    ``postfaecher`` sind die, die dieser Benutzer sehen darf, mit ihrer
    Anzahl. Sie stehen oben – das entspricht dem Postfachbaum links im
    Fenster und beantwortet die Frage, die man sonst nicht beantworten
    kann: *Worin suche ich hier eigentlich?*
    """
    if treffer:
        zeilen = "".join(_zeile(t) for t in treffer)
        tabelle = (
            "<table><thead><tr><th>Datum</th><th>Absender</th>"
            "<th>Betreff</th><th>Größe</th></tr></thead>"
            f"<tbody>{zeilen}</tbody></table>"
        )
    elif ausdruck:
        tabelle = '<p class="leer">MailBurg hat nichts gefunden.</p>'
    else:
        tabelle = (
            '<p class="leer">Schreiben Sie oben hinein, wonach Sie suchen. '
            "Gesucht wird in Betreff, Text, Absender, Empfänger – und in "
            "den Anhängen.</p>"
        )

    if gesamt:
        ergebnis = f"MailBurg hat {sprache.anzahl(gesamt, 'Treffer', 'Treffer')}."
    elif ausdruck:
        ergebnis = "MailBurg hat nichts gefunden."
    else:
        ergebnis = ""

    seiten = max(1, -(-gesamt // je_seite))
    blaettern = ""
    if seiten > 1:
        stellen = []
        if seite_nr > 1:
            stellen.append(
                f'<a href="/?q={html.escape(ausdruck)}&s={seite_nr - 1}">'
                f"← zurück</a>"
            )
        stellen.append(f"<span>Seite {seite_nr} von {seiten}</span>")
        if seite_nr < seiten:
            stellen.append(
                f'<a href="/?q={html.escape(ausdruck)}&s={seite_nr + 1}">'
                f"weiter →</a>"
            )
        blaettern = f'<div class="blaettern">{"".join(stellen)}</div>'

    return _rahmen("Suchen – MailBurg", f"""
<form class="suche" method="get" action="/">
  <input name="q" value="{html.escape(ausdruck)}" autofocus
         placeholder="Suchen … z. B. rechnung · von:müller · jahr:2025">
  <button type="submit">Suchen</button>
</form>
{_postfachleiste(postfaecher or {}, ausdruck)}
<p class="ergebnis">{html.escape(ergebnis)}
   · <a href="/maske?begriff={html.escape(ausdruck)}">Ausführlich suchen</a></p>
{tabelle}
{blaettern}
""", benutzer)


def suchmaske(benutzer, werte: dict[str, str], konten, ordner,
              vorschau: str) -> str:
    """Die ausführliche Suche – dieselben Felder wie im Fenster.

    Die Felder stehen in :data:`mailburg.search.maske.FELDER`, damit
    beide Masken dieselben zeigen. Und wie im Fenster steht unten der
    Suchausdruck, den sie zusammensetzt: So lernt man die Suchsprache
    nebenbei und kann den Ausdruck mitnehmen.
    """
    from mailburg.search.maske import FELDER

    zeilen = []
    for feld in FELDER:
        wert = werte.get(feld.name, "")
        hinweis = (
            f'<small>{html.escape(feld.hinweis)}</small>'
            if feld.hinweis else ""
        )

        if feld.art == "haken":
            angehakt = " checked" if wert else ""
            eingabe = (
                f'<label class="haken"><input type="checkbox" '
                f'name="{feld.name}"{angehakt}> '
                f"{html.escape(feld.beschriftung)}</label>"
            )
            zeilen.append(f"<div class=\"feld weit\">{eingabe}{hinweis}</div>")
            continue

        if feld.art == "auswahl":
            wahl = feld.auswahl
            if feld.name == "konto":
                wahl = (("", "alle"),) + tuple((k, k) for k in konten)
            elif feld.name == "ordner":
                wahl = (("", "alle"),) + tuple((o, o) for o in ordner)
            stuecke = "".join(
                f'<option value="{html.escape(w)}"'
                f'{" selected" if w == wert else ""}>{html.escape(b)}</option>'
                for w, b in wahl
            )
            eingabe = f'<select name="{feld.name}">{stuecke}</select>'
        else:
            eingabe = (
                f'<input name="{feld.name}" value="{html.escape(wert)}"'
                f'{" placeholder=\"TT.MM.JJJJ\"" if feld.art == "datum" else ""}>'
            )

        zeilen.append(
            f'<div class="feld">'
            f'<label for="{feld.name}">{html.escape(feld.beschriftung)}</label>'
            f"{eingabe}{hinweis}</div>"
        )

    if vorschau:
        gezeigt = (
            f'<p class="ausdruck"><span>Suchausdruck:</span> '
            f"<code>{html.escape(vorschau)}</code></p>"
        )
    else:
        gezeigt = (
            '<p class="ausdruck leise">Noch nichts eingegrenzt – '
            "das fände alles.</p>"
        )

    return _rahmen("Ausführlich suchen – MailBurg", f"""
<h1>Ausführlich suchen</h1>
<form method="get" action="/maske">
  <div class="maske">{"".join(zeilen)}</div>
  {gezeigt}
  <p>
    <button type="submit" name="tun" value="zeigen">Ausdruck zeigen</button>
    <button type="submit" name="tun" value="suchen">Suchen</button>
    <a href="/">zur einfachen Suche</a>
  </p>
</form>
""", benutzer)


def nachricht(benutzer, kopf: dict[str, Any], text: str, kennung: str,
              anhaenge=(), verlauf=()) -> str:
    """Eine einzelne Nachricht, mit ihren Anhängen zum Herunterladen."""
    zeilen = "".join(
        f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd>"
        for k, v in kopf.items() if v
    )

    if anhaenge:
        stuecke = "".join(
            f'<li><a href="/nachricht/{html.escape(kennung)}/anhang/{nummer}">'
            f"{html.escape(stueck.filename or f'Anhang {nummer + 1}')}</a>"
            f"<span> · {html.escape(sprache.groesse(stueck.size))}</span></li>"
            for nummer, stueck in enumerate(anhaenge)
        )
        anhangsliste = (
            f'<div class="anhaenge"><h2>'
            f"{html.escape(sprache.anzahl(len(anhaenge), 'Anhang', 'Anhänge'))}"
            f"</h2><ul>{stuecke}</ul></div>"
        )
    else:
        anhangsliste = ""

    gespraech = _verlauf(verlauf, kennung)
    return _rahmen(f"{kopf.get('Betreff', 'Nachricht')} – MailBurg", f"""
<p><a href="javascript:history.back()">← zurück</a></p>
<h1>{html.escape(str(kopf.get("Betreff", "(ohne Betreff)")))}</h1>
<dl class="kopf">{zeilen}</dl>
{gespraech}
{anhangsliste}
<p><a href="/nachricht/{html.escape(kennung)}/datei">Die ganze Nachricht
   als Datei (.eml)</a></p>
<hr>
<pre class="text">{html.escape(text)}</pre>
""", benutzer)


def _verlauf(nachrichten, hier: str) -> str:
    """Der Gesprächsverlauf, in dem diese Nachricht steht.

    **Zusammengehalten über die Kopfzeilen, nicht über den Betreff.**
    Jede Mail trägt in ``References`` die Kennungen ihrer Vorgänger; so
    sieht RFC 5322 das vor. Zwei Mails mit dem Betreff »Rechnung« haben
    dagegen oft nichts miteinander zu tun, und »Re: Re: AW:« wechselt im
    Verlauf ohnehin.

    **Der Hinweis auf die Unvollständigkeit gehört dazu.** Was nie ins
    Archiv kam, fehlt auch hier – und wer nur einen Teil der Postfächer
    sehen darf, sieht auch nur die Teile des Gesprächs daraus. Ohne den
    Satz schließt jemand aus »da steht nichts« auf »da war nichts«.
    """
    if len(nachrichten) < 2:
        return ""

    zeilen = []
    for stueck in nachrichten:
        tag = sprache.zeitpunkt(stueck.date or "").split(",")[0]
        wer = stueck.from_name or stueck.from_addr or ""
        if stueck.hash == hier:
            zeilen.append(
                f'<li class="hier"><span>{html.escape(tag)}</span> '
                f"{html.escape(wer)} · {html.escape(stueck.subject)}"
                f" <em>– diese Nachricht</em></li>"
            )
        else:
            zeilen.append(
                f'<li><span>{html.escape(tag)}</span> '
                f'<a href="/nachricht/{html.escape(stueck.hash)}">'
                f"{html.escape(wer)} · {html.escape(stueck.subject)}</a></li>"
            )

    return (
        f'<div class="verlauf"><h2>'
        f"Teil eines Gesprächs mit "
        f"{html.escape(sprache.anzahl(len(nachrichten), 'Nachricht', 'Nachrichten'))}"
        f'</h2><ol>{"".join(zeilen)}</ol>'
        f'<p class="hinweis">Zusammengestellt aus den Kopfzeilen der '
        f"Nachrichten, nicht aus dem Betreff. Was nicht im Archiv liegt "
        f"oder nicht zu Ihren Postfächern gehört, fehlt hier.</p></div>"
    )


def fehlerseite(titel: str, text: str, benutzer=None) -> str:
    return _rahmen(f"{titel} – MailBurg", f"""
<h1>{html.escape(titel)}</h1>
<p>{html.escape(text)}</p>
<p><a href="/">Zur Suche</a></p>
""", benutzer)
