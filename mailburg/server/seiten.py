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
                 seite_nr: int, je_seite: int) -> str:
    """Die Suchseite mit ihrer Trefferliste."""
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
<p class="ergebnis">{html.escape(ergebnis)}</p>
{tabelle}
{blaettern}
""", benutzer)


def nachricht(benutzer, kopf: dict[str, Any], text: str, kennung: str) -> str:
    """Eine einzelne Nachricht."""
    zeilen = "".join(
        f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd>"
        for k, v in kopf.items() if v
    )
    return _rahmen(f"{kopf.get('Betreff', 'Nachricht')} – MailBurg", f"""
<p><a href="javascript:history.back()">← zurück</a></p>
<h1>{html.escape(str(kopf.get("Betreff", "(ohne Betreff)")))}</h1>
<dl class="kopf">{zeilen}</dl>
<p><a href="/nachricht/{html.escape(kennung)}/datei">Als Datei
   herunterladen (.eml)</a></p>
<hr>
<pre class="text">{html.escape(text)}</pre>
""", benutzer)


def fehlerseite(titel: str, text: str, benutzer=None) -> str:
    return _rahmen(f"{titel} – MailBurg", f"""
<h1>{html.escape(titel)}</h1>
<p>{html.escape(text)}</p>
<p><a href="/">Zur Suche</a></p>
""", benutzer)
