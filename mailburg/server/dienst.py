"""Der Dienst selbst – vorerst nur mit einer Seite, die »läuft« sagt.

**Warum das der richtige erste Schritt ist.** Ein Dienst hat mehr
Fragen zu klären als eine Funktion: unter welchem Benutzer er läuft, wo
seine Konfiguration steht, wie er startet, wie er beim Neustart
wiederkommt, was er meldet, wenn etwas fehlt. Diese Fragen einmal
sauber zu beantworten, bevor Funktion dazukommt, erspart, sie später
mit halbem Blick nachzuziehen.

Die Seite zeigt deshalb genau das, was man beim Einrichten wissen will:
welches Archiv, wie viele Mails, ob der Tresor erreichbar ist, wie viele
Zugänge eingerichtet sind – und, wenn etwas davon nicht stimmt, was zu
tun ist.

**Was hier noch nicht ist: die Anmeldung.** Diese Seite verrät nichts,
was nicht ohnehin schon weiß, wer die Adresse kennt – Betriebszustand,
keine Post. Der lesende Zugriff auf Nachrichten kommt erst mit der
Anmeldung, und dann sitzt sie davor.

Deshalb lauscht der Dienst in der Vorgabe nur auf ``127.0.0.1``.
"""

from __future__ import annotations

import html
from typing import Any

from mailburg import __version__
from mailburg.core import sprache


def _zustand(lage) -> dict[str, Any]:
    """Alles, was die Statusseite zeigt – und ihre Sorgen.

    Als eigene Funktion, damit sich der Zustand prüfen lässt, ohne
    einen Server zu starten.
    """
    from mailburg.core import tresor
    from mailburg.core.archive import Archive

    bericht: dict[str, Any] = {
        "fassung": __version__,
        "archiv": str(lage.archiv),
        "adresse": f"{lage.adresse}:{lage.anschluss}",
        "sorgen": [],
    }

    try:
        # Ohne Sperrdatei: Ein lesender Dienst darf einen laufenden
        # Abruf auf demselben Archiv nicht blockieren.
        with Archive.open(lage.archiv, exclusive=False) as archiv:
            bericht["name"] = archiv.meta.get("name", "")
            bericht["betriebsart"] = str(archiv.mode)
            bericht["mails"] = archiv.index.statistics()["mails"]
            bericht["postfaecher"] = len(archiv.index.account_totals())

            zugaenge = archiv.benutzer
            bericht["zugaenge"] = len(zugaenge)
            bericht["verwalter"] = len(zugaenge.verwalter)

            if not len(zugaenge):
                bericht["sorgen"].append(
                    "Es ist kein Zugang eingerichtet. Niemand kann sich "
                    "anmelden, sobald die Anmeldung dazukommt."
                )
            elif not zugaenge.verwalter:
                bericht["sorgen"].append(
                    "Es gibt keinen Verwalter. Zugänge lassen sich dann nur "
                    "noch am Archiv selbst ändern."
                )
    except Exception as fehler:  # noqa: BLE001 – die Seite muss antworten
        bericht["sorgen"].append(f"Das Archiv ließ sich nicht öffnen: {fehler}")

    try:
        if tresor.verfuegbar():
            bericht["tresor"] = f"{len(tresor.eintraege())} Einträge"
            for name in tresor.eintraege():
                tresor.holen(name)
        else:
            bericht["tresor"] = "nicht eingerichtet"
            bericht["sorgen"].append(
                "Kein Tresor eingerichtet. Ohne ihn kommt der Dienst an "
                "keine Postfach-Passwörter – er läuft, holt aber nichts. "
                "Siehe »mailburg tresor schluessel«."
            )
    except Exception as fehler:  # noqa: BLE001
        bericht["tresor"] = "unlesbar"
        bericht["sorgen"].append(f"Der Tresor ließ sich nicht öffnen: {fehler}")

    if lage.oeffentlich:
        bericht["sorgen"].append(
            "Dieser Dienst lauscht über den eigenen Rechner hinaus. Solange "
            "es keine Anmeldung gibt, gehört er hinter ein VPN oder eine "
            "Firewall – nicht ins offene Netz."
        )

    return bericht


_SEITE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MailBurg Server</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 42rem;
         margin: 3rem auto; padding: 0 1.5rem; line-height: 1.5; }}
  h1 {{ font-size: 1.5rem; }}
  .marke {{ color: #c62828; }}
  dl {{ display: grid; grid-template-columns: max-content 1fr;
        gap: .4rem 1.5rem; }}
  dt {{ color: #667080; }}
  dd {{ margin: 0; }}
  .sorge {{ border-left: 4px solid #c62828; padding: .3rem 0 .3rem .8rem;
            margin: .8rem 0; }}
  footer {{ margin-top: 2.5rem; color: #667080; font-size: .9rem; }}
</style>
</head>
<body>
<h1>MailBurg <span class="marke">SERVER</span></h1>
<p>Der Dienst läuft.</p>
<dl>{zeilen}</dl>
{sorgen}
<footer>Fassung {fassung}</footer>
</body>
</html>
"""

#: Was auf der Seite steht, in dieser Reihenfolge.
FELDER = (
    ("name", "Archiv"),
    ("archiv", "Ort"),
    ("betriebsart", "Betriebsart"),
    ("mails", "Mails"),
    ("postfaecher", "Postfächer"),
    ("zugaenge", "Zugänge"),
    ("tresor", "Tresor"),
    ("adresse", "Erreichbar auf"),
)


def seite(bericht: dict[str, Any]) -> str:
    zeilen = []
    for schluessel, beschriftung in FELDER:
        if schluessel not in bericht:
            continue
        wert = bericht[schluessel]
        if schluessel == "mails":
            wert = sprache.mails(wert)
        elif schluessel == "postfaecher":
            wert = sprache.postfaecher(wert)
        elif schluessel == "zugaenge":
            wert = sprache.anzahl(wert, "Zugang", "Zugänge")
            if bericht.get("verwalter"):
                wert += f", davon {bericht['verwalter']} verwaltend"
        zeilen.append(
            f"<dt>{html.escape(beschriftung)}</dt>"
            f"<dd>{html.escape(str(wert))}</dd>"
        )

    sorgen = "".join(
        f'<p class="sorge">{html.escape(text)}</p>'
        for text in bericht.get("sorgen", [])
    )
    return _SEITE.format(
        zeilen="".join(zeilen), sorgen=sorgen,
        fassung=html.escape(bericht.get("fassung", "")),
    )


def anwendung(lage=None):
    """Baut die Starlette-Anwendung.

    Als Funktion und nicht als Modulvariable: So lässt sie sich in
    Tests mit einer anderen Lage bauen, und der Import dieses Moduls
    startet nichts.
    """
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, JSONResponse
    from starlette.routing import Route

    from mailburg.server.einstellungen import Serverlage

    wo = lage or Serverlage.aus_umgebung()

    async def status(anfrage):
        return HTMLResponse(seite(_zustand(wo)))

    async def zustand_json(anfrage):
        """Für die Überwachung – dieselben Angaben, maschinenlesbar."""
        return JSONResponse(_zustand(wo))

    async def lebt(anfrage):
        """Nur »ja«, ohne das Archiv anzufassen.

        Für den Neustart-Wächter des Betriebssystems: Er soll wissen,
        ob der Prozess antwortet, und dafür nicht bei jeder Abfrage
        einen Suchindex öffnen.
        """
        return JSONResponse({"lebt": True})

    from mailburg.server.lesen import routen
    from mailburg.server.sitzung import Sitzungen

    # **Eine Sitzungsverwaltung je Anwendung.** Ihr Schlüssel entsteht
    # beim Start und wird nicht aufbewahrt; ein Neustart meldet damit
    # alle ab. Siehe mailburg/server/sitzung.py.
    sitzungen = Sitzungen()

    return Starlette(routes=[
        # Der Zustand liegt unter /zustand, nicht mehr unter /: Dort
        # steht jetzt die Suche, und die ist das, was jemand sehen will,
        # der die Adresse aufruft.
        Route("/zustand", status),
        Route("/zustand.json", zustand_json),
        Route("/lebt", lebt),
        *routen(wo, sitzungen),
    ])


def starten(lage=None) -> int:
    """Startet den Dienst. Kehrt erst zurück, wenn er endet."""
    import uvicorn

    from mailburg.server.einstellungen import Serverlage

    wo = lage or Serverlage.aus_umgebung()
    uvicorn.run(
        anwendung(wo),
        host=wo.adresse,
        port=wo.anschluss,
        # Kein Zugriffsprotokoll auf der Konsole: Es landete sonst in
        # journald und wüchse dort mit jedem Aufruf. Wer es braucht,
        # bekommt es vom Reverse Proxy davor.
        access_log=False,
    )
    return 0
