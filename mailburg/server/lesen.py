"""Lesender Zugriff über den Browser: anmelden, suchen, lesen, laden.

**Jede Abfrage geht mit der Sicht des Angemeldeten.** Das ist die
einzige Zeile, auf die es hier ankommt – der Rest ist Anzeige. Was ein
Benutzer nicht sehen darf, taucht deshalb auch in keiner Zahl auf;
siehe :mod:`mailburg.core.sicht`.

**Die Rechte kommen bei jeder Anfrage frisch aus dem Archiv**, nicht aus
dem Sitzungscookie. Sonst gälte eine Rechteänderung erst nach der
nächsten Anmeldung, und ein entzogenes Recht bliebe stundenlang
wirksam.

**Geschrieben wird hier nichts.** Kein Einstufen, kein Löschen, kein
Zurücklegen ins Postfach. Das ist der Zuschnitt dieser Stufe: erst
lesen, und die Vorgänge, die ins Journal schreiben, später und mit
Bedacht.
"""

from __future__ import annotations

from urllib.parse import parse_qsl

from mailburg.core import sprache
from mailburg.core.sicht import Sicht
from mailburg.server import seiten

#: Wie viele Treffer je Seite. Genug, dass Blättern selten nötig ist;
#: wenig genug, dass die Seite auch bei einer halben Million Mails in
#: Millisekunden steht.
JE_SEITE = 50


def _archiv(lage):
    """Öffnet das Archiv nur lesend.

    Ohne Sperrdatei: Ein lesender Dienst darf einen laufenden Abruf auf
    demselben Archiv nicht blockieren.
    """
    from mailburg.core.archive import Archive

    return Archive.open(lage.archiv, exclusive=False)


def routen(lage, sitzungen):
    """Die Adressen des lesenden Zugriffs."""
    from starlette.responses import (
        HTMLResponse,
        RedirectResponse,
        Response,
    )
    from starlette.routing import Route

    from mailburg.server.sitzung import COOKIE, DAUER, Anmeldesperre

    def _angemeldet(anfrage, archiv):
        return sitzungen.einloesen(
            anfrage.cookies.get(COOKIE), archiv.benutzer
        )

    def _weiter_zur_anmeldung():
        return RedirectResponse("/anmelden", status_code=303)

    async def anmeldeseite(anfrage):
        return HTMLResponse(seiten.anmeldung())

    async def anmelden(anfrage):
        # **Selbst zerlegt, nicht über anfrage.form().** Starlette
        # verlangt dafür »python-multipart« – das ist für Dateiuploads
        # da, und die gibt es hier nicht. Ein Anmeldeformular schickt
        # »application/x-www-form-urlencoded«, und dafür genügt die
        # Standardbibliothek. Eine Abhängigkeit weniger, die mitgepflegt
        # und mitgeprüft werden müsste.
        rohtext = (await anfrage.body()).decode("utf-8", "replace")
        felder = dict(parse_qsl(rohtext))
        name = felder.get("name", "")
        passwort = felder.get("passwort", "")

        with _archiv(lage) as archiv:
            try:
                benutzer = sitzungen.anmelden(archiv.benutzer, name, passwort)
            except Anmeldesperre as fehler:
                return HTMLResponse(
                    seiten.anmeldung(str(fehler)), status_code=429
                )

            if benutzer is None:
                # **Nie sagen, was falsch war.** »Benutzer unbekannt«
                # verriete, welche Anmeldenamen es gibt.
                return HTMLResponse(
                    seiten.anmeldung(
                        "Anmeldung fehlgeschlagen. Bitte Name und Passwort "
                        "prüfen."
                    ),
                    status_code=401,
                )
            kekstext = sitzungen.ausstellen(benutzer)

        antwort = RedirectResponse("/", status_code=303)
        antwort.set_cookie(
            COOKIE, kekstext,
            max_age=DAUER,
            httponly=True,      # kein Zugriff aus JavaScript
            samesite="lax",     # kein Mitschicken bei fremden Formularen
            # **Secure nur bei HTTPS.** Fest gesetzt wäre das Cookie im
            # Firmennetz ohne TLS wirkungslos - und niemand käme darauf,
            # warum die Anmeldung nicht hält.
            secure=anfrage.url.scheme == "https",
            path="/",
        )
        return antwort

    async def abmelden(anfrage):
        antwort = RedirectResponse("/anmelden", status_code=303)
        antwort.delete_cookie(COOKIE, path="/")
        return antwort

    async def suchen(anfrage):
        with _archiv(lage) as archiv:
            benutzer = _angemeldet(anfrage, archiv)
            if benutzer is None:
                return _weiter_zur_anmeldung()

            blick = Sicht.fuer(benutzer)
            ausdruck = anfrage.query_params.get("q", "").strip()
            try:
                seite_nr = max(1, int(anfrage.query_params.get("s", "1")))
            except ValueError:
                seite_nr = 1

            gesamt = archiv.index.count(ausdruck, sicht=blick)
            treffer = archiv.index.search(
                ausdruck,
                limit=JE_SEITE,
                offset=(seite_nr - 1) * JE_SEITE,
                sicht=blick,
            )
            return HTMLResponse(seiten.trefferliste(
                benutzer, ausdruck, treffer, gesamt, seite_nr, JE_SEITE
            ))

    async def maske(anfrage):
        """Die ausführliche Suche.

        Zwei Knöpfe, ein Formular: »Ausdruck zeigen« bleibt hier und
        zeigt, was zusammenkommt – wie die Vorschau im Fenster. »Suchen«
        geht damit zur Trefferliste.
        """
        from mailburg.search.maske import FELDER, ausdruck as bauen

        with _archiv(lage) as archiv:
            benutzer = _angemeldet(anfrage, archiv)
            if benutzer is None:
                return _weiter_zur_anmeldung()

            werte = {
                feld.name: anfrage.query_params.get(feld.name, "")
                for feld in FELDER
            }
            fertig = bauen(werte)

            if anfrage.query_params.get("tun") == "suchen":
                from urllib.parse import quote

                return RedirectResponse(
                    f"/?q={quote(fertig)}", status_code=303
                )

            # **Nur die Postfächer, die dieser Benutzer sehen darf.**
            # Sonst stünden die Namen der übrigen in der Auswahlliste –
            # und die verraten schon für sich genommen einiges.
            blick = Sicht.fuer(benutzer)
            konten, ordner = [], set()
            for konto, ordnername, _ in archiv.index.accounts(sicht=blick):
                if konto not in konten:
                    konten.append(konto)
                ordner.add(ordnername)

            return HTMLResponse(seiten.suchmaske(
                benutzer, werte, konten, sorted(ordner), fertig
            ))

    def _sichtbarer_treffer(archiv, benutzer, kennung: str):
        """Eine Nachricht – aber nur, wenn dieser Benutzer sie sehen darf.

        ``Index.nachricht`` prüft die Rechte selbst – ein Weg daran
        vorbei wäre die Stelle, an der ein Leck entsteht.
        """
        return archiv.index.nachricht(kennung, sicht=Sicht.fuer(benutzer))

    async def nachricht(anfrage):
        kennung = anfrage.path_params["kennung"]
        with _archiv(lage) as archiv:
            benutzer = _angemeldet(anfrage, archiv)
            if benutzer is None:
                return _weiter_zur_anmeldung()

            treffer = _sichtbarer_treffer(archiv, benutzer, kennung)
            if treffer is None:
                # **Dieselbe Antwort wie »gibt es nicht«.** Ein
                # unterscheidbares »dürfen Sie nicht« verriete, dass es
                # sie gibt.
                return HTMLResponse(
                    seiten.fehlerseite(
                        "Nicht gefunden",
                        "Diese Nachricht gibt es nicht – oder sie liegt in "
                        "einem Postfach, das Sie nicht sehen dürfen.",
                        benutzer,
                    ),
                    status_code=404,
                )

            from mailburg.extract.message import parse

            rohdaten = archiv.store.get(treffer.hash, treffer.bucket)
            zerlegt = parse(rohdaten)
            absender = treffer.from_name or ""
            if treffer.from_addr:
                absender = (
                    f"{absender} <{treffer.from_addr}>" if absender
                    else treffer.from_addr
                )
            kopf = {
                "Von": absender,
                "An": ", ".join(zerlegt.to_addrs),
                "Datum": sprache.zeitpunkt(treffer.date or ""),
                "Betreff": treffer.subject,
                "Größe": sprache.groesse(treffer.size),
            }
            if zerlegt.attachments:
                kopf["Anhänge"] = ", ".join(
                    a.filename for a in zerlegt.attachments if a.filename
                )
            return HTMLResponse(
                seiten.nachricht(benutzer, kopf, zerlegt.body or "", kennung)
            )

    async def datei(anfrage):
        kennung = anfrage.path_params["kennung"]
        with _archiv(lage) as archiv:
            benutzer = _angemeldet(anfrage, archiv)
            if benutzer is None:
                return _weiter_zur_anmeldung()

            treffer = _sichtbarer_treffer(archiv, benutzer, kennung)
            if treffer is None:
                return Response("Nicht gefunden", status_code=404)

            rohdaten = archiv.store.get(treffer.hash, treffer.bucket)

        return Response(
            rohdaten,
            media_type="message/rfc822",
            headers={
                # Der Dateiname als reine Kennung: Ein Betreff kann alles
                # enthalten, und ein Dateiname mit Anführungszeichen oder
                # Zeilenumbruch darin ist ein eigenes Problem.
                "Content-Disposition":
                    f'attachment; filename="{kennung[:16]}.eml"',
            },
        )

    return [
        Route("/", suchen),
        Route("/anmelden", anmeldeseite),
        Route("/anmelden", anmelden, methods=["POST"]),
        Route("/abmelden", abmelden),
        Route("/maske", maske),
        Route("/nachricht/{kennung}", nachricht),
        Route("/nachricht/{kennung}/datei", datei),
    ]



