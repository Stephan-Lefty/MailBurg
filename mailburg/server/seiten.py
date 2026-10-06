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

#: Die drei Einstellungen für die Helligkeit.
#:
#: **»System« ist die Vorgabe und bleibt es.** Wer sein Windows auf
#: Dunkel gestellt hat, will es meistens überall dunkel – eine Webseite,
#: die sich darüber hinwegsetzt, fällt unangenehm auf. Die beiden festen
#: Werte sind für die Fälle, in denen das nicht stimmt: ein heller Raum,
#: ein schlechter Bildschirm, ein Augenleiden.
THEMEN = ("system", "hell", "dunkel")

_KOPF = """<!doctype html>
<html lang="de" data-thema="{thema}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titel}</title>
<link rel="icon" href="/wappen.png" type="image/png" sizes="64x64">
<link rel="icon" href="/wappen-128.png" type="image/png" sizes="128x128">
<style>
  :root {{ color-scheme: light dark; --marke: #c62828; --leise: #667080; }}
  /* **Die Wahl des Anwenders schlägt die des Systems.** Ohne Angabe
     folgt die Seite dem Betriebssystem – das ist die Vorgabe und für
     die meisten richtig. Wer es anders will, bekommt es: ein heller
     Raum, ein schlechter Bildschirm, müde Augen. */
  html[data-thema="hell"] {{ color-scheme: light; }}
  html[data-thema="dunkel"] {{ color-scheme: dark; }}
  header .thema {{ color: var(--leise); font-size: .9rem; }}
  header .thema a {{ text-decoration: none; }}
  header .thema a.jetzt {{ font-weight: 700; text-decoration: underline; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, sans-serif; margin: 0; line-height: 1.5; }}
  header {{ border-bottom: 1px solid #d6dde8; padding: .8rem 1.5rem;
            display: flex; gap: 1.5rem; align-items: baseline;
            flex-wrap: wrap; }}
  header .wappen {{ align-self: center; margin-right: -.9rem; }}
  header .name {{ font-weight: 700; font-size: 1.15rem; }}
  header .marke {{ color: var(--marke); }}
  header .wer {{ margin-left: auto; color: var(--leise); font-size: .9rem; }}
  /* **Breiter als vorher (62rem).** Seit die Postfächer links als
     eigene Spalte stehen, teilt sich die Breite auf zwei Dinge; die
     Trefferliste soll dabei nicht schmaler werden als zuvor. */
  main {{ max-width: 78rem; margin: 0 auto; padding: 1.5rem; }}
  form.suche {{ display: flex; gap: .6rem; margin-bottom: .4rem; }}
  form.suche input {{ flex: 1; padding: .55rem .7rem; font-size: 1rem;
                      border: 1px solid #97a1ad; border-radius: 4px; }}
  button {{ padding: .55rem 1.1rem; font-size: 1rem; cursor: pointer;
            border: 1px solid #97a1ad; border-radius: 4px;
            background: transparent; color: inherit; }}
  /* **Die Werkzeugleiste: Symbol oben, Wort darunter.** Wie in
     MailStore, das die Mitarbeiter kennen - und mit Beschriftung, denn
     zwei Striche unterscheiden »Erweiterte Suche« nicht von »Neue
     Suche«. */
  .werkzeuge {{ display: flex; gap: .3rem; flex-wrap: wrap;
                border-bottom: 1px solid #d6dde8; padding-bottom: .6rem;
                margin-bottom: 1rem; }}
  .werkzeuge a {{ display: flex; flex-direction: column; gap: .15rem;
                  align-items: center; text-decoration: none;
                  color: inherit; padding: .4rem .7rem; border-radius: 4px;
                  min-width: 5.5rem; font-size: .8rem; }}
  .werkzeuge a:hover {{ background: rgba(127, 127, 127, .12); }}
  .werkzeuge svg {{ color: var(--marke); }}
  ul.wahl {{ list-style: none; padding: 0; margin: 0 0 1.5rem;
             display: grid; gap: .5rem; max-width: 32rem; }}
  ul.wahl a {{ display: block; border: 1px solid #d6dde8; border-radius: 4px;
               padding: .6rem .8rem; text-decoration: none; color: inherit; }}
  ul.wahl a:hover {{ border-color: var(--marke); }}
  ul.wahl a.gewaehlt {{ border-color: var(--marke); border-width: 2px; }}
  ul.wahl span {{ display: block; color: var(--leise); font-size: .88rem; }}
  .hinweis {{ color: var(--leise); font-size: .9rem; }}
  .ergebnis {{ color: var(--leise); font-size: .9rem; margin: .2rem 0 1.2rem; }}
  /* **Die Trefferliste, zweizeilig.** Absender und Datum oben,
     Betreff darunter - wie in MailStore, das die Mitarbeiter kennen.
     Ein Betreff bekommt damit die volle Breite statt einer Spalte. */
  ol.treffer {{ list-style: none; padding: 0; margin: 0; }}
  ol.treffer li {{ border-bottom: 1px solid #d6dde8; }}
  ol.treffer a {{ display: grid; gap: 0 1rem; padding: .5rem .2rem;
                  grid-template-columns: 1fr max-content;
                  text-decoration: none; color: inherit; }}
  ol.treffer a:hover {{ background: rgba(127, 127, 127, .12); }}
  ol.treffer .wer {{ font-weight: 600; }}
  ol.treffer .wann {{ color: var(--leise); font-size: .88rem;
                      white-space: nowrap; }}
  /* Der Betreff über beide Spalten - er ist das Längste und das
     Wichtigste. In der Farbe eines Links, denn der ganze Eintrag ist
     einer. */
  ol.treffer .was {{ grid-column: 1 / -1; color: #0645ad; }}
  @media (prefers-color-scheme: dark) {{
    ol.treffer .was {{ color: #6cb6ff; }}
  }}
  html[data-thema="hell"] ol.treffer .was {{ color: #0645ad; }}
  html[data-thema="dunkel"] ol.treffer .was {{ color: #6cb6ff; }}
  ol.treffer .klammer {{ color: var(--leise); }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: .45rem .6rem;
            border-bottom: 1px solid #d6dde8; vertical-align: top; }}
  th {{ color: var(--leise); font-weight: 600; font-size: .85rem; }}
  td.datum {{ white-space: nowrap; color: var(--leise); }}
  td.groesse {{ white-space: nowrap; color: var(--leise); text-align: right; }}
  a {{ color: #0645ad; }}
  @media (prefers-color-scheme: dark) {{ a {{ color: #6cb6ff; }} }}
  /* **Wege aus der Nachricht als Knöpfe, nicht als Links.** Ein Link
     sieht aus, als führe er irgendwohin; ein Knopf sieht aus, als täte
     er etwas. Hier tut er etwas – und wer den Download-Dialog des
     Browsers kennt, erkennt die Form wieder.
     Dieselben Maße wie ``button``, damit die Oberfläche eine Sprache
     spricht; die Farben kommen aus derselben Palette. */
  .wege {{ display: flex; gap: .6rem; flex-wrap: wrap; margin: 1.2rem 0; }}
  .wege a {{ padding: .55rem 1.1rem; font-size: 1rem;
             border: 1px solid #97a1ad; border-radius: 4px;
             background: transparent; color: inherit;
             text-decoration: none; display: inline-block; }}
  .wege a:hover {{ border-color: var(--marke); }}
  /* Der erste ist der, den die meisten wollen. */
  .wege a:first-child {{ border-color: var(--marke); font-weight: 600; }}
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
  /* **Links die Postfächer, rechts die Treffer.** Wie der
     Postfachbaum im Programmfenster. Die Spalte wächst nicht mit der
     Zahl der Postfächer in die Breite - bei sechzig Stück wäre eine
     Leiste über der Tabelle ein Block, der die Treffer nach unten
     schiebt. */
  .zweispaltig {{ display: grid; gap: 1.5rem 2rem;
                  grid-template-columns: minmax(11rem, 15rem) 1fr;
                  align-items: start; margin-top: 1rem; }}
  /* Zugeschoben gibt es keine zweite Spalte: Die Treffer bekommen die
     ganze Breite, der Griff sitzt neben der Trefferzahl. */
  .zweispaltig.zu {{ grid-template-columns: 1fr; }}
  /* Auf einem schmalen Bildschirm untereinander: Zwei Spalten à 50 %
     wären dort zwei zu schmale Spalten. */
  @media (max-width: 55rem) {{
    .zweispaltig, .zweispaltig.zu {{ grid-template-columns: 1fr; }}
  }}
  /* **``min-width: 0`` auf beiden Seiten.** Ein Grid-Feld wird sonst
     nie schmaler als sein längstes unteilbares Wort - und eine
     Mailadresse wie »buchhaltung@beispielfirma.example« ist für den
     Browser ein Wort. Die Spur ist auf 15 rem gedeckelt, der Inhalt
     brauchte mehr, also lief er in die Nachbarspalte: Am 2026-10-06
     standen auf einem 5:4-Bildschirm die Trefferzahlen quer über den
     Betreffzeilen. Für ``section`` stand die Regel seit jeher da, für
     ``aside`` nicht. Zwei Stellen, eine nachgezogen, die andere
     nicht. */
  .zweispaltig aside {{ position: sticky; top: 1rem; min-width: 0; }}
  .zweispaltig section {{ min-width: 0; }}
  .postfaecher {{ display: flex; flex-wrap: wrap; gap: .4rem;
                  flex-direction: column; align-items: stretch;
                  margin: 0; }}
  /* Eckig statt rund: Die Pillenform stammt aus der Zeit, als die
     Postfächer nebeneinander in einer Leiste standen. Untereinander
     liest sich eine Liste besser als eine Reihe Tabletten. */
  .postfaecher a {{ border: 1px solid #d6dde8; border-radius: 4px;
                    padding: .3rem .6rem; font-size: .9rem;
                    text-decoration: none; display: flex;
                    justify-content: space-between; gap: .6rem;
                    min-width: 0; }}
  /* **Eine Zeile je Postfach, abgeschnitten statt umgebrochen.**
     Bis zum 2026-10-06 brach eine Adresse um, und jeder Eintrag war
     zwei Zeilen hoch – bei sieben Postfächern schon die halbe
     Seitenhöhe, bei den gut zwanzig, die aus MailStore dazukommen,
     unbenutzbar. Der volle Name steht am Element (``title``), und
     Vorlesewerkzeuge bekommen ihn ohnehin ganz. */
  .postfaecher a em {{ font-style: normal; min-width: 0;
                       overflow: hidden; text-overflow: ellipsis;
                       white-space: nowrap; }}
  .postfaecher a span {{ flex: none; }}
  /* Der Griff zum Auf- und Zuschieben. Keine Schaltfläche, sondern ein
     Link: Er führt zu einer Adresse, die den Zustand merkt, und wirkt
     damit auch ohne JavaScript. */
  .schublade {{ display: inline-flex; align-items: center; gap: .35rem;
                border: 1px solid #d6dde8; border-radius: 4px;
                padding: .15rem .5rem; font-size: .85rem;
                text-decoration: none; color: var(--leise);
                white-space: nowrap; margin-right: .5rem; }}
  .schublade:hover {{ border-color: var(--marke); color: var(--marke); }}
  .schublade .pfeil {{ font-size: .75rem; }}
  .postfaecher a:hover {{ border-color: var(--marke); }}
  .postfaecher a span {{ color: var(--leise); }}
  .postfaecher h2 {{ font-size: .85rem; color: var(--leise);
                     font-weight: 600; margin: 0 0 .1rem; }}
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
  /* **Ein Hinweis, keine Sanduhr.** Ein laufender Balken oder ein
     pochendes Wappen zieht das Auge an und sagt doch nur »warte«.
     Dieser Satz sagt, *was* läuft – und steht still dabei. Stephans
     Entscheidung vom 2026-10-06.

     Er erscheint erst nach einer halben Sekunde: Eine Suche über
     70.000 Mails dauert meist Millisekunden, und ein Hinweis, der bei
     jedem Klick aufblitzt, ist Flackern und keine Auskunft. */
  #laeufttext {{ position: fixed; top: 0; left: 50%;
                 transform: translateX(-50%); display: none; z-index: 9;
                 background: var(--marke); color: #fff; font-size: .9rem;
                 padding: .4rem 1.1rem; border-radius: 0 0 5px 5px;
                 box-shadow: 0 1px 4px rgba(0, 0, 0, .25); }}
  html.sucht #laeufttext {{ display: block; }}
</style>
</head>
<body>
<div id="laeufttext" role="status">MailBurg sucht …</div>
<script>
/* **Das einzige Skript der Oberfläche, und es ist eingebettet.**
   Nichts wird nachgeladen; ohne JavaScript funktioniert alles wie
   zuvor, es fehlt dann nur diese Anzeige.

   Die halbe Sekunde Verzug ist der Kern: Eine Suche über 70.000 Mails
   dauert gemessen 125 ms. Ohne Verzug flackerte es bei jeder Suche
   kurz auf – und eine Anzeige, die immer angeht, sagt nichts mehr. */
(function () {{
  var zeiger = null;
  function an() {{
    zeiger = setTimeout(function () {{
      document.documentElement.classList.add("sucht");
    }}, 500);
  }}
  document.addEventListener("submit", an, true);
  /* Auch beim Blättern und beim Öffnen einer Nachricht: Das Lesen
     holt die Mail von der Platte, und bei einem großen Anhang ist das
     die spürbarere Wartezeit. */
  document.addEventListener("click", function (e) {{
    var a = e.target.closest ? e.target.closest("a") : null;
    if (a && a.host === location.host && !a.hasAttribute("download")) an();
  }}, true);
  /* Zurück im Verlauf zeigt der Browser die Seite aus dem Zwischen-
     speicher – dann stünde der Hinweis dort ohne Grund. */
  window.addEventListener("pageshow", function () {{
    if (zeiger) clearTimeout(zeiger);
    document.documentElement.classList.remove("sucht");
  }});
}})();
</script>
"""

#: Wo der Quelltext liegt. Eine Konstante, weil sie an zwei Stellen
#: steht und ein Umzug des Repositorys sonst eine davon vergäße.
QUELLE = "https://github.com/Stephan-Lefty/MailBurg"

_FUSS = """<footer>MailBurg {fassung} &middot;
<a href="{quelle}" rel="noopener noreferrer" target="_blank">Quelltext</a>
&middot; <a href="/rechtliches">Lizenz und Haftung</a></footer>
</body>
</html>
"""


def _themenwahl(thema: str, zurueck: str) -> str:
    """Drei Links: System, hell, dunkel.

    **Ohne JavaScript.** Jeder Link ist ein gewöhnlicher Aufruf, der
    einen Keks setzt und zurückführt. Ein Schalter, der ohne Skripte
    nicht funktioniert, ist auf einem Archivserver eine Zumutung – dort
    sind Browser oft streng eingestellt.
    """
    from urllib.parse import quote

    beschriftung = {"system": "System", "hell": "Hell", "dunkel": "Dunkel"}
    stuecke = []
    for wahl in THEMEN:
        jetzt = ' class="jetzt"' if wahl == thema else ""
        stuecke.append(
            f'<a href="/thema?wahl={wahl}&weiter={quote(zurueck)}"{jetzt}>'
            f"{beschriftung[wahl]}</a>"
        )
    return f'<span class="thema">{" · ".join(stuecke)}</span>'


#: Die Symbole der Werkzeugleiste, als SVG im Dokument.
#:
#: **Nicht nachgeladen, nicht als Schriftart.** Dieselbe Haltung wie
#: beim Rest: Was das Programm anzeigt, bringt es mit. Eine Symbolschrift
#: von einem fremden Server verriete dort jeden Aufruf; ein Bild je
#: Symbol wären sechs Anfragen für sechs Striche.
#:
#: ``currentColor`` statt fester Farbe – damit sie im dunklen Thema
#: mitgehen, ohne dass es eine zweite Fassung braucht.
_STRICH = ('fill="none" stroke="currentColor" stroke-width="1.6" '
           'stroke-linecap="round" stroke-linejoin="round"')

SYMBOLE = {
    # Lupe
    "suche": f'<circle cx="10" cy="10" r="6" {_STRICH}/>'
             f'<path d="M14.5 14.5 L20 20" {_STRICH}/>',
    # Fragezeichen im Kreis
    "hilfe": f'<circle cx="12" cy="12" r="8" {_STRICH}/>'
             f'<path d="M9.5 9.5a2.5 2.5 0 1 1 3 2.4V14" {_STRICH}/>'
             f'<path d="M12 17.2v.1" {_STRICH}/>',
    # Blatt mit Ecke – eine neue, leere Suche
    "neu": f'<path d="M6 3h8l4 4v14H6z" {_STRICH}/>'
           f'<path d="M14 3v4h4" {_STRICH}/>',
    # Zahnrad, vereinfacht: Kreis mit sechs Zacken
    "einstellungen":
        f'<circle cx="12" cy="12" r="3.2" {_STRICH}/>'
        f'<path d="M12 3v2.5M12 18.5V21M4.2 7.5l2.2 1.3M17.6 15.2l2.2 1.3'
        f'M4.2 16.5l2.2-1.3M17.6 8.8l2.2-1.3" {_STRICH}/>',
    # Umschlag – die Mail ans Mailprogramm übergeben
    "brief": f'<rect x="3" y="5.5" width="18" height="13" rx="1.5" '
             f'{_STRICH}/><path d="M3.6 6.5 12 13l8.4-6.5" {_STRICH}/>',
    # Blatt mit Pfeil nach unten – als Datei ablegen
    "ablegen": f'<path d="M6 3h8l4 4v14H6z" {_STRICH}/>'
               f'<path d="M12 10v6M9.5 13.5 12 16l2.5-2.5" {_STRICH}/>',
    # »i« im Kreis
    "info": f'<circle cx="12" cy="12" r="8" {_STRICH}/>'
            f'<path d="M12 11v5.5" {_STRICH}/>'
            f'<path d="M12 7.8v.1" {_STRICH}/>',
}


def _symbol(name: str) -> str:
    """Ein Symbol, 24×24, in der Farbe des Textes."""
    return (
        f'<svg viewBox="0 0 24 24" width="24" height="24" '
        f'aria-hidden="true" focusable="false">{SYMBOLE[name]}</svg>'
    )


def werkzeugleiste(hier: str, ausdruck: str = "", zusatz=()) -> str:
    """Die Leiste über dem Suchfeld: Symbol und Wort darunter.

    **Mit Beschriftung, nicht nur Symbol.** Ein Zahnrad erkennt jeder,
    eine Lupe auch – aber »Erweiterte Suche« gegen »Neue Suche« zu
    unterscheiden, gelingt über zwei Striche nicht. MailStore macht es
    genauso, und das ist der Grund, warum es dort funktioniert.

    **Der erste Eintrag schaltet um**, statt wegzuführen: Wer in der
    ausführlichen Suche steht, kommt mit demselben Knopf zurück. Zwei
    Wege für eine Sache wären einer zu viel.
    """
    from urllib.parse import quote

    in_der_maske = hier.startswith("/maske")
    eintraege = [
        (
            "/" if in_der_maske else f"/maske?begriff={quote(ausdruck)}",
            "suche",
            "Einfache Suche" if in_der_maske else "Erweiterte Suche",
            "Zurück zum einen Suchfeld" if in_der_maske
            else "Nach Absender, Datum, Anhang und mehr suchen",
        ),
        ("/", "neu", "Neue Suche", "Alles zurücksetzen"),
        *zusatz,
        ("/einstellungen", "einstellungen", "Einstellungen",
         "Helligkeit und was sonst noch einzustellen ist"),
        ("/hilfe", "hilfe", "Hilfe", "Wie man sucht"),
        ("/info", "info", "Über", "Fassung, Lizenz und Haftung"),
    ]

    stuecke = []
    for ziel, symbol, wort, warum in eintraege:
        stuecke.append(
            f'<a href="{ziel}" title="{html.escape(warum)}">'
            f"{_symbol(symbol)}<span>{html.escape(wort)}</span></a>"
        )
    return f'<nav class="werkzeuge">{"".join(stuecke)}</nav>'


def _rahmen(titel: str, inhalt: str, benutzer=None, thema: str = "system",
            hier: str = "/") -> str:
    if benutzer is not None:
        wer = (
            f'<span class="wer">{html.escape(benutzer.anzeigename or benutzer.name)}'
            f' · <a href="/abmelden">Abmelden</a></span>'
        )
    else:
        # **Auf der Anmeldeseite bleibt die Wahl in der Kopfzeile.** Dort
        # gibt es keine Werkzeugleiste, und wer schlecht liest, soll die
        # Helligkeit umstellen können, *bevor* er ein Passwort eintippt.
        wer = f'<span class="wer">{_themenwahl(thema, hier)}</span>'
    # **Das Wappen mit fester Größe im Markup, nicht nur im Stylesheet.**
    # Sonst springt die Kopfzeile, während das Bild noch lädt – und beim
    # ersten Aufruf springt sie bei jedem Anwender.
    return (
        _KOPF.format(
            titel=html.escape(titel),
            thema=thema if thema in THEMEN else "system",
        )
        + f'<header><img class="wappen" src="/wappen.png" width="28" '
        f'height="28" alt="">'
        f'<span class="name">MailBurg '
        f'<span class="marke">SERVER</span></span>{wer}</header>\n'
        f"<main>{inhalt}</main>\n"
        + _FUSS.format(fassung=html.escape(__version__), quelle=QUELLE)
    )


def rechtliches(benutzer=None, thema: str = "system") -> str:
    """Lizenz, Haftung und der Satz, der dieses Projekt trägt.

    **Der Text steht hier, nicht als Link ins Netz.** Ein Archivserver
    steht oft in einem Netz ohne Internet; ein rechtlicher Hinweis, der
    dort auf eine tote Adresse zeigt, ist keiner. Die ausführlichen
    Fassungen liegen trotzdem verlinkt daneben, für den, der sie liest.

    **Ohne Anmeldung erreichbar**, aus demselben Grund wie die
    Helligkeitswahl: Was vor der Nutzung gilt, muss vor der Anmeldung
    lesbar sein.
    """
    return _rahmen("Lizenz und Haftung – MailBurg", f"""
<h1>Lizenz und Haftung</h1>

<h2>Lizenz</h2>
<p>MailBurg steht unter der <b>MIT-Lizenz</b>. Sie dürfen es benutzen,
   verändern und weitergeben, auch im Betrieb und auch verändert –
   solange der Lizenztext und die Urhebernennung mitgehen.</p>

<h2>Keine Gewähr</h2>
<p><b>Die Nutzung erfolgt auf eigene Gefahr.</b> Die Lizenz sagt es in
   Juristendeutsch, hier steht es im Klartext: Dieses Programm wird
   bereitgestellt, wie es ist. Es gibt keine Zusicherung, dass es für
   einen bestimmten Zweck taugt, und keine Haftung für Schäden, die aus
   seiner Nutzung entstehen – auch nicht für verlorene Daten.</p>
<p>Daraus folgt das Wichtigste, was man einem Archiv gegenüber tun
   kann: <b>Prüfen Sie Ihre Sicherungen.</b> Eine Sicherung, die noch
   nie zurückgespielt wurde, ist eine Vermutung.</p>

<h2>Keine Software ist GoBD-konform</h2>
<p>Es gibt keine Zertifizierung, die das bescheinigt – wer etwas anderes
   behauptet, verkauft Ihnen etwas. Die GoBD betreffen den gesamten
   Ablauf beim Anwender: wie Belege hereinkommen, wer sie prüft, wie
   archiviert wird, wie das dokumentiert ist.</p>
<p>MailBurg <b>unterstützt</b> einen revisionssicheren Betrieb – es
   <b>stellt ihn nicht her</b>. Was es beiträgt: unveränderbare Ablage,
   lückenlose Protokollierung, Nachweisbarkeit von Löschungen,
   Fristenüberwachung. Verantwortlich für die Verfahrensdokumentation
   bleibt der Steuerpflichtige.</p>

<h2>Kein Rechtsrat</h2>
<p>Diese Seite fasst den Regelfall zusammen, damit Sie wissen, wonach
   Sie fragen müssen. Sie ersetzt nicht die Auskunft eines
   Steuerberaters oder Rechtsanwalts.</p>

<h2>Zum Nachlesen</h2>
<ul>
  <li><a href="{QUELLE}/blob/main/RECHTLICHES.md"
         rel="noopener noreferrer" target="_blank">Rechtliches</a> –
      ausführlich, mit Fristen und Quellen</li>
  <li><a href="{QUELLE}/blob/main/LICENSE"
         rel="noopener noreferrer" target="_blank">Der Lizenztext</a></li>
  <li><a href="{QUELLE}" rel="noopener noreferrer"
         target="_blank">Der Quelltext</a></li>
</ul>
<p class="hinweis">Diese drei Verweise führen ins Internet. Steht dieser
   Server in einem abgeschotteten Netz, bleiben sie ohne Antwort – der
   Text oben gilt trotzdem.</p>

<p><a href="/">Zur Suche</a></p>
""", benutzer, thema=thema, hier="/rechtliches")


def anmeldung(fehler: str = "", thema: str = "system") -> str:
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
""", thema=thema, hier="/anmelden")


def einstellungen(benutzer=None, thema: str = "system") -> str:
    """Was sich einstellen lässt – bisher die Helligkeit.

    **Eine eigene Seite für eine Einstellung.** Das klingt nach zu viel
    und ist trotzdem richtig: In der Kopfzeile standen die drei Wörter
    »System · Hell · Dunkel« ohne erkennbaren Zusammenhang neben dem
    Anmeldenamen. Wer sie nicht suchte, sah sie nicht, und wer sie sah,
    musste raten, wozu sie gehören. Hinter einem Zahnrad sucht man sie.

    Und sie bleibt nicht allein: Treffer je Seite, Sortierung, Spalten –
    das kommt dorthin, wenn es kommt.
    """
    auswahl = []
    for wahl, wort, warum in (
        ("system", "Wie das System",
         "Folgt der Einstellung von Windows oder macOS."),
        ("hell", "Hell", "Dunkle Schrift auf hellem Grund."),
        ("dunkel", "Dunkel", "Helle Schrift auf dunklem Grund."),
    ):
        jetzt = ' class="gewaehlt"' if wahl == thema else ""
        auswahl.append(
            f'<li><a href="/thema?wahl={wahl}&weiter=/einstellungen"{jetzt}>'
            f"<b>{wort}</b><span>{html.escape(warum)}</span></a></li>"
        )

    return _rahmen("Einstellungen – MailBurg", f"""
{werkzeugleiste("/einstellungen")}
<h1>Einstellungen</h1>

<h2>Helligkeit</h2>
<p>Gilt für diesen Browser und bleibt gespeichert – auch über das
   Abmelden hinaus.</p>
<ul class="wahl">{"".join(auswahl)}</ul>

<p class="hinweis">Mehr gibt es noch nicht einzustellen. Was Ihnen
   fehlt, sagen Sie am besten dem, der MailBurg betreut.</p>

<p><a href="/">Zur Suche</a></p>
""", benutzer, thema=thema, hier="/einstellungen")


def hilfeseite(benutzer=None, thema: str = "system") -> str:
    """Wie man sucht – die Suchsprache, in der Oberfläche.

    **Derselbe Text wie auf der Kommandozeile.** Er steht in
    :func:`query.describe_syntax`, und von dort holen ihn alle: das
    Programmfenster, ``mailburg suchhilfe`` und diese Seite. Drei
    Fassungen derselben Erklärung liefen auseinander, und die seltenst
    gelesene wäre dann die falsche.
    """
    from mailburg.search.query import describe_syntax

    return _rahmen("Hilfe – MailBurg", f"""
{werkzeugleiste("/hilfe")}
<h1>Wie man sucht</h1>

<p>Im Suchfeld genügt ein Wort – gesucht wird in Betreff, Text,
   Absender, Empfänger und in den Anhängen. Wer genauer sucht, schreibt
   es dazu; die ausführliche Suche setzt dieselben Ausdrücke aus
   Feldern zusammen.</p>

<h2>In welchen Postfächern suche ich?</h2>
<p>In allen, die Sie sehen dürfen – ohne dass Sie etwas tun müssen.
   Welche das sind, zeigt der Knopf <b>Postfächer</b> neben der
   Trefferzahl: Er schiebt eine Spalte auf, in der jedes Postfach mit
   seiner Mailzahl steht, und ein Klick darauf grenzt die Suche auf
   dieses eine ein. Die Spalte bleibt offen, bis Sie sie wieder
   zuschieben.</p>

<pre class="text">{html.escape(describe_syntax())}</pre>

<h2>Wenn eine Suche länger dauert</h2>
<p>Dann erscheint oben in der Mitte der Hinweis <b>MailBurg sucht …</b>
   – der Server arbeitet also, und es hat sich nichts aufgehängt. Bei
   den meisten Suchen sehen Sie ihn gar nicht: Sie sind nach
   Millisekunden fertig. Länger wird es, wenn der Rechner gerade stark
   beschäftigt ist oder Sie eine Nachricht mit einem großen Anhang
   öffnen.</p>

<h2>Was hier nicht geht</h2>
<p>Diese Oberfläche <b>liest nur</b>. Einstufen, Löschen und das
   Zurücklegen ins Postfach gibt es im Programmfenster und auf der
   Kommandozeile, nicht hier. Das ist Absicht: Was ins Journal
   schreibt, soll nicht über einen Browser gehen.</p>

<h2>Eine Mail weiterverwenden</h2>
<p>In jeder geöffneten Nachricht stehen zwei Knöpfe. <i>Im Mailprogramm
   öffnen</i> übergibt sie an Outlook oder Thunderbird. <i>Als Datei
   speichern</i> legt sie als <code>.eml</code> ab – unverändert, Byte
   für Byte wie archiviert.</p>

<p><a href="/">Zur Suche</a></p>
""", benutzer, thema=thema, hier="/hilfe")


#: Ab wie vielen Postfächern derselben Domain sich das Weglassen lohnt.
#: Bei zweien spart es eine Zeile und kostet die Eindeutigkeit auf den
#: ersten Blick – erst ab dreien überwiegt der Gewinn.
MINDESTENS_GLEICH = 3


def _gemeinsame_domain(postfaecher) -> str:
    """Die Hausdomain – die, auf die die meisten Adressen enden.

    **Der Anlass kommt aus dem Betrieb (06.10.2026).** In Stephans
    Firmenarchiv heißen sieben Postfächer ``…@ourww.hostedoffice.ag``;
    aus MailStore kommen gut zwanzig weitere dazu. In der Spalte standen
    bei jedem Eintrag dieselben zweiundzwanzig Zeichen – und drängten
    das, was ihn unterscheidet, aus dem Bild.

    **Die häufigste, nicht die einzige.** Der erste Entwurf verlangte,
    dass *alle* Adressen gleich enden. Stephans Frage dazu war die
    richtige: »wenn später roesner@gmail.at dazu kommt« – dann hätte
    eine einzige fremde Adresse alle siebenundzwanzig Einträge wieder
    lang gemacht. Jetzt bleibt die fremde Adresse vollständig stehen und
    hebt sich dadurch sogar ab; das ist dasselbe Muster, das
    Mailprogramme seit jeher benutzen.

    **Gekürzt wird nur, wenn danach noch jeder für sich steht.** Beim
    Prüfen an echten Daten fiel auf: Aus
    ``buchhaltung@ourww.hostedoffice.ag`` (laufend) und »Buchhaltung«
    (Altbestand aus MailStore) würden zwei Einträge, die sich nur in
    einem Großbuchstaben unterscheiden. Im Postfachbaum sähen sie aus
    wie derselbe – genau davor warnt der Einlesedialog beim Vergeben des
    Namens, und die Anzeige darf es nicht selbst herbeiführen.

    Namen ohne ``@`` zählen nicht mit: Ein eingelesener Bestand heißt
    »Stephan Rösner« oder »Outlook Persönlich«, und das ist keine
    Adresse, der eine Domain fehlt.
    """
    haeufigkeit: dict[str, int] = {}
    for name in postfaecher:
        if "@" not in name:
            continue
        domain = name.rsplit("@", 1)[1]
        haeufigkeit[domain] = haeufigkeit.get(domain, 0) + 1
    if not haeufigkeit:
        return ""

    # Bei Gleichstand die alphabetisch erste – eine Anzeige darf nicht
    # davon abhängen, in welcher Reihenfolge die Konten zurückkamen.
    domain, wie_oft = sorted(
        haeufigkeit.items(), key=lambda p: (-p[1], p[0])
    )[0]
    if wie_oft < MINDESTENS_GLEICH:
        return ""

    kurz = [_kurzname(name, domain).casefold() for name in postfaecher]
    if len(set(kurz)) != len(kurz):
        return ""
    return domain


def _kurzname(name: str, gemeinsame_domain: str) -> str:
    """Was in der Spalte steht – der volle Name bleibt im ``title``."""
    if not gemeinsame_domain:
        return name
    ende = f"@{gemeinsame_domain}"
    # **Nur kürzen, wenn etwas übrig bleibt.** Ein Postfach, das genau
    # so heißt wie die Domain, würde sonst zu einem leeren Kasten.
    if name.endswith(ende) and len(name) > len(ende):
        return name[: -len(ende)]
    return name


def _postfachleiste(postfaecher: dict[str, int], ausdruck: str,
                    offen: bool = False) -> str:
    """Welche Postfächer der Angemeldete durchsuchen kann.

    **Warum das sichtbar sein muss.** Wer nur einen Teil des Archivs
    sehen darf, sucht sonst ins Ungewisse: Findet er nichts, weiß er
    nicht, ob es die Mail nicht gibt oder ob sie in einem Postfach
    liegt, das er nicht sieht. Die Leiste beantwortet das, bevor die
    Frage aufkommt.

    Jeder Eintrag grenzt die Suche mit einem Klick darauf ein – wie ein
    Klick in den Postfachbaum des Fensters.

    **Zugeschoben ist die Vorgabe, und das aus dem Betrieb.** Stephans
    Firma sucht über alle Postfächer; wer gezielt in einem sucht, nimmt
    die ausführliche Suche. Eine Spalte, an die man selten muss, nimmt
    der Trefferliste dauerhaft ein Fünftel der Breite – auf einem
    5:4-Bildschirm merkt man das sofort. Der Griff bleibt stehen, der
    Zustand wird gemerkt.
    """
    if not postfaecher or not offen:
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

    gemeinsam = _gemeinsame_domain(postfaecher)

    stuecke = []
    # **Sortiert ohne Rücksicht auf Groß- und Kleinschreibung.** Sonst
    # stehen alle Klarnamen oben und alle Adressen unten, weil »B« vor
    # »b« kommt – und »Buchhaltung« landete weit weg von
    # »buchhaltung@…«, obwohl beide dasselbe Postfach meinen.
    for name, anzahl in sorted(postfaecher.items(), key=lambda p: p[0].casefold()):
        ziel = f"{ohne_konto} konto:{quoten_wenn_noetig(name)}".strip()
        gewaehlt = ' class="gewaehlt"' if name == aktiv else ""
        kurz = _kurzname(name, gemeinsam)
        # **Der volle Name bleibt am Element.** Was angezeigt wird, ist
        # gekürzt; was gemeint ist, muss nachlesbar bleiben – sonst
        # unterscheidet niemand zwei Postfächer, die sich erst hinter
        # der Kürzung unterscheiden.
        titel = f' title="{html.escape(name)}"' if kurz != name else ""
        # Der Name in einem eigenen Element: Nur so lässt sich das
        # Kürzen auf ihn beschränken und die Zahl daneben ganz lassen.
        stuecke.append(
            f'<a href="/?q={quote(ziel)}"{gewaehlt}{titel}>'
            f"<em>{html.escape(kurz)}</em>"
            f"<span>{anzahl}</span></a>"
        )

    alle = ""
    if aktiv:
        alle = (
            f'<a href="/?q={quote(ohne_konto)}" class="alle">'
            f"alle Postfächer</a>"
        )

    # **Ohne Vorspann, damit das erste Postfach ganz links steht.** Der
    # Satz »Sie können suchen in:« stand bis zum 2026-10-02 davor und
    # schob jeden Knopf um seine Breite nach rechts – bei einem Klick,
    # den man häufig macht, ist das der falsche Tausch. Was die Leiste
    # bedeutet, steht jetzt am Element selbst (``title``) und wird von
    # Vorlesewerkzeugen über ``aria-label`` genannt.
    # **Mit Überschrift, seit die Leiste eine Spalte ist.** Nebeneinander
    # unter dem Suchfeld war klar, wozu die Knöpfe gehören; als Spalte am
    # Rand braucht es ein Wort davor, sonst steht dort eine Liste ohne
    # erkennbaren Sinn.
    # **Was weggelassen wird, steht dabei.** Sonst rät man, zu welcher
    # Domain »roesner« gehört – besonders, sobald daneben ein
    # vollständiges »roesner@gmail.at« steht.
    weggelassen = (
        f" Bei den kurzen Namen fehlt »@{html.escape(gemeinsam)}«."
        if gemeinsam else ""
    )
    return (
        f'<div class="postfaecher" aria-label="Durchsuchbare Postfächer" '
        f'title="Diese Postfächer dürfen Sie durchsuchen. '
        f'Ein Klick grenzt die Suche darauf ein.{weggelassen}">'
        f"{''.join(stuecke)}{alle}</div>"
    )


def _griff(ausdruck: str, offen: bool) -> str:
    """Der Schalter, der die Postfachspalte auf- und zuschiebt.

    **Er steht neben der Trefferzahl, nicht über der Spalte** – also an
    derselben Stelle, ob die Spalte offen ist oder nicht. Ein Schalter,
    der mitwandert, ist beim zweiten Klick nicht mehr dort, wo die Maus
    gerade war.

    Ein Link und keine Schaltfläche: Er führt zu einer Adresse, die den
    Zustand merkt, und wirkt deshalb auch ohne JavaScript.
    """
    from urllib.parse import quote as _q

    zurueck = _q(f"/?q={_q(ausdruck)}" if ausdruck else "/", safe="")
    if offen:
        return (
            f'<a class="schublade" href="/postfaecher?wahl=zu&amp;'
            f'weiter={zurueck}" title="Schiebt die Postfachspalte zu. '
            f'Gesucht wird weiterhin in allen Postfächern, die Sie '
            f'sehen dürfen.">'
            f'<span class="pfeil">◂</span>Postfächer</a>'
        )
    return (
        f'<a class="schublade" href="/postfaecher?wahl=auf&amp;'
        f'weiter={zurueck}" title="Zeigt, in welchen Postfächern Sie '
        f'suchen dürfen – und grenzt mit einem Klick darauf ein.">'
        f'<span class="pfeil">▸</span>Postfächer</a>'
    )


def quoten_wenn_noetig(wert: str) -> str:
    """Wie in der Suchsprache – Leerzeichen brauchen Anführungszeichen."""
    from mailburg.search.maske import quoten

    return quoten(wert)


def _zeile(treffer) -> str:
    """Ein Treffer: Absender und Datum oben, Betreff darunter.

    **Zweizeilig statt vier Spalten.** So zeigt es MailStore, und die
    Mitarbeiter kennen es von dort. Es ist auch das bessere Format: Ein
    Betreff wie »Unterlagen für die Umsatzsteuervoranmeldung« sprengt
    jede Spalte, über die volle Breite steht er ganz da.

    **Die Größe fällt weg.** Sie stand bis zum 2026-10-02 in einer
    eigenen Spalte und beantwortete eine Frage, die niemand stellt – in
    MailStore gibt es sie in der Liste gar nicht. Wer sie braucht,
    findet sie in der geöffneten Nachricht.

    **Der ganze Eintrag ist der Link**, nicht nur der Betreff. Ein
    Klickziel von zwei Zeilen Höhe trifft man auch mit einer Maus, die
    nicht mehr ganz jung ist.
    """
    from mailburg.core import sprache as s

    # Nur der Tag: Die Uhrzeit steht in der Nachricht selbst.
    datum = s.zeitpunkt(treffer.date or "").split(",")[0]
    absender = treffer.from_name or treffer.from_addr or ""
    klammer = ' <span class="klammer">📎</span>' if treffer.has_attachments else ""
    betreff = treffer.subject or "(ohne Betreff)"
    return (
        f'<li><a href="/nachricht/{html.escape(treffer.hash)}">'
        f'<span class="wer">{html.escape(absender)}</span>'
        f'<span class="wann">{html.escape(datum)}</span>'
        f'<span class="was">{html.escape(betreff)}{klammer}</span>'
        f"</a></li>"
    )


def ergebniszeile(gesamt: int, ausdruck: str, im_archiv: int = 0) -> str:
    """Was über der Trefferliste steht.

    **Die Zahl im Archiv steht auch ohne Suche da.** Wer das Archiv
    öffnet, will sehen, dass es wächst – und nach einer Suche hilft die
    Einordnung: »1.234 von 70.264« sagt mehr als »1.234«.

    **Die Zahl im Archiv ist die ganze, nicht die sichtbare.** Das
    weicht von der Regel ab, dass in keiner Zahl auftauchen darf, was
    jemand nicht sehen soll – und zwar mit Absicht (Stephans Vorgabe
    vom 2026-10-06). Sie sagt, wie groß das Archiv ist und dass es
    wächst; wer weiß, dass 70.000 Mails darin liegen, weiß deshalb über
    keine einzige etwas. Die **Trefferzahl** daneben bleibt
    eingeschränkt – sie handelt vom Inhalt.
    """
    bestand = (
        f"{sprache.anzahl(im_archiv, 'Mail', 'Mails')} im Archiv"
        if im_archiv else ""
    )

    if gesamt:
        treffer = sprache.anzahl(gesamt, "Treffer", "Treffer")
        if not ausdruck:
            # Ohne Suchbegriff sind Treffer und Bestand dasselbe – das
            # zweimal zu nennen liest sich wie ein Fehler.
            return f"MailBurg hat {treffer}."
        return (
            f"MailBurg hat {treffer} – von {bestand}."
            if bestand else f"MailBurg hat {treffer}."
        )

    if ausdruck:
        return (
            f"MailBurg hat nichts gefunden – {bestand}."
            if bestand else "MailBurg hat nichts gefunden."
        )

    return f"{bestand[0].upper()}{bestand[1:]}." if bestand else ""


def trefferliste(benutzer, ausdruck: str, treffer, gesamt: int,
                 seite_nr: int, je_seite: int, postfaecher=None,
                 thema: str = "system", spalte: str = "zu",
                 im_archiv: int = 0) -> str:
    """Die Suchseite mit ihrer Trefferliste.

    ``postfaecher`` sind die, die dieser Benutzer sehen darf, mit ihrer
    Anzahl. Sie stehen links – das entspricht dem Postfachbaum im
    Fenster und beantwortet die Frage, die man sonst nicht beantworten
    kann: *Worin suche ich hier eigentlich?*

    ``spalte`` ist ``auf`` oder ``zu``. Zugeschoben bleibt nur der
    Griff stehen, und die Treffer bekommen die ganze Breite.
    """
    # **Der Griff nur, wenn es etwas zu zeigen gibt.** Wer genau ein
    # Postfach sehen darf, braucht keine Spalte mit einem Eintrag –
    # und eine Schaltfläche, die eine leere Fläche aufschiebt, ist
    # schlimmer als keine.
    offen = spalte == "auf" and bool(postfaecher)
    griff = f"{_griff(ausdruck, offen)} " if postfaecher else ""
    spaltenbereich = (
        f"<aside>{_postfachleiste(postfaecher or {}, ausdruck, True)}</aside>"
        if offen else ""
    )

    if treffer:
        zeilen = "".join(_zeile(t) for t in treffer)
        tabelle = f'<ol class="treffer">{zeilen}</ol>'
    elif ausdruck:
        tabelle = '<p class="leer">MailBurg hat nichts gefunden.</p>'
    else:
        tabelle = (
            '<p class="leer">Schreiben Sie oben hinein, wonach Sie suchen. '
            "Gesucht wird in Betreff, Text, Absender, Empfänger – und in "
            "den Anhängen.</p>"
        )

    ergebnis = ergebniszeile(gesamt, ausdruck, im_archiv)

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

    # **Die Postfächer stehen links, nicht oben.** Wie der Postfachbaum
    # im Programmfenster: Dort ist der Platz, dort sucht man sie, und auf
    # einem breiten Bildschirm lag links ohnehin alles brach. Als Leiste
    # über der Tabelle wuchs sie außerdem mit jedem Postfach in die
    # Breite – bei den sechzig eines Firmenarchivs wäre daraus ein Block
    # geworden, der die Treffer nach unten schiebt.
    return _rahmen("Suchen – MailBurg", f"""
{werkzeugleiste("/", ausdruck)}
<form class="suche" method="get" action="/">
  <input name="q" value="{html.escape(ausdruck)}" autofocus
         placeholder="Suchen … z. B. rechnung · von:müller · jahr:2025">
  <button type="submit">Suchen</button>
</form>
<div class="zweispaltig{'' if offen else ' zu'}">
  {spaltenbereich}
  <section>
    <p class="ergebnis">{griff}{html.escape(ergebnis)}
       · <a href="/maske?begriff={html.escape(ausdruck)}">Ausführlich
       suchen</a></p>
    {tabelle}
    {blaettern}
  </section>
</div>
""", benutzer, thema=thema, hier="/")


def suchmaske(benutzer, werte: dict[str, str], konten, ordner,
              vorschau: str, thema: str = "system") -> str:
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
            platzhalter = (
                ' placeholder="TT.MM.JJJJ"' if feld.art == "datum" else ""
            )
            eingabe = (
                f'<input name="{feld.name}" value="{html.escape(wert)}"'
                f"{platzhalter}>"
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
{werkzeugleiste("/maske", werte.get("begriff", ""))}
<h1>Ausführlich suchen</h1>
<form method="get" action="/maske">
  <div class="maske">{"".join(zeilen)}</div>
  {gezeigt}
  <p>
    <button type="submit" name="tun" value="zeigen">Suchtext zeigen</button>
    <button type="submit" name="tun" value="suchen">Suchen</button>
    <a href="/">zur einfachen Suche</a>
  </p>
</form>
""", benutzer, thema=thema, hier="/maske")


def nachricht(benutzer, kopf: dict[str, Any], text: str, kennung: str,
              anhaenge=(), verlauf=(), thema: str = "system") -> str:
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
    # **Die zwei Wege aus der Nachricht stehen oben in der Leiste.**
    # Wie in MailStore, wo »E-Mail öffnen« und »E-Mail wiederherstellen«
    # dort liegen. Unten bleiben sie trotzdem stehen: Wer eine lange Mail
    # gelesen hat, ist am Ende und nicht mehr oben.
    wege_oben = (
        (f"/nachricht/{kennung}/oeffnen", "brief", "Im Mailprogramm",
         "Die Nachricht an Outlook oder Thunderbird übergeben"),
        (f"/nachricht/{kennung}/datei", "ablegen", "Als Datei",
         "Als .eml speichern – unverändert, Byte für Byte"),
    )
    return _rahmen(f"{kopf.get('Betreff', 'Nachricht')} – MailBurg", f"""
{werkzeugleiste(f"/nachricht/{kennung}", zusatz=wege_oben)}
<p><a href="javascript:history.back()">← zurück</a></p>
<h1>{html.escape(str(kopf.get("Betreff", "(ohne Betreff)")))}</h1>
<dl class="kopf">{zeilen}</dl>
{gespraech}
{anhangsliste}
<p class="wege">
   <a href="/nachricht/{html.escape(kennung)}/oeffnen">Im Mailprogramm öffnen</a>
   <a href="/nachricht/{html.escape(kennung)}/datei">Als Datei speichern (.eml)</a>
</p>
<hr>
<pre class="text">{html.escape(text)}</pre>
""", benutzer, thema=thema, hier=f"/nachricht/{kennung}")


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


def fehlerseite(titel: str, text: str, benutzer=None,
                thema: str = "system") -> str:
    return _rahmen(f"{titel} – MailBurg", f"""
<h1>{html.escape(titel)}</h1>
<p>{html.escape(text)}</p>
<p><a href="/">Zur Suche</a></p>
""", benutzer, thema=thema)
