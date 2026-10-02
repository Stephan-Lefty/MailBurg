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

    return Archive.open(
        lage.archiv, exclusive=False, passwort=lage.passwort
    )


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
        return HTMLResponse(seiten.anmeldung(thema=_thema(anfrage)))

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
                    seiten.anmeldung(str(fehler), thema=_thema(anfrage)),
                    status_code=429,
                )

            if benutzer is None:
                # **Nie sagen, was falsch war.** »Benutzer unbekannt«
                # verriete, welche Anmeldenamen es gibt.
                return HTMLResponse(
                    seiten.anmeldung(
                        "Anmeldung fehlgeschlagen. Bitte Name und Passwort "
                        "prüfen.",
                        thema=_thema(anfrage),
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

    #: Wo die Helligkeitswahl steht. **Kein httponly und kein
    #: Sitzungsbezug**: Sie ist keine Anmeldung, sondern eine Vorliebe,
    #: und sie soll die Abmeldung überleben - wer schlecht liest, will
    #: das nicht bei jeder Anmeldung neu einstellen.
    THEMAKEKS = "mailburg_thema"

    def _thema(anfrage) -> str:
        """Die gewählte Helligkeit - oder »system«, der Vorgabe."""
        wahl = anfrage.cookies.get(THEMAKEKS, "")
        return wahl if wahl in seiten.THEMEN else "system"

    async def thema_waehlen(anfrage):
        """Setzt die Helligkeit und führt dorthin zurück, wo man war.

        **Das Ziel wird geprüft, nicht übernommen.** Ein ``weiter``, das
        aus der Anfrage kommt und ungeprüft in eine Weiterleitung geht,
        ist eine offene Umleitung: Ein Link auf diesen Server führte dann
        auf eine fremde Seite, die wie MailBurg aussieht und nach dem
        Passwort fragt.
        """
        wahl = anfrage.query_params.get("wahl", "system")
        if wahl not in seiten.THEMEN:
            wahl = "system"

        ziel = anfrage.query_params.get("weiter", "/")
        if not ziel.startswith("/") or ziel.startswith("//"):
            ziel = "/"

        antwort = RedirectResponse(ziel, status_code=303)
        antwort.set_cookie(
            THEMAKEKS, wahl,
            max_age=60 * 60 * 24 * 365,
            samesite="lax",
            secure=anfrage.url.scheme == "https",
            path="/",
        )
        return antwort

    async def rechtliches(anfrage):
        """Lizenz und Haftung – **auch ohne Anmeldung.**

        Was vor der Nutzung gilt, muss vor der Anmeldung lesbar sein.
        Der Angemeldete bekommt trotzdem seine Kopfzeile; dafür wird er
        nachgeschlagen, wenn eine Sitzung da ist.
        """
        benutzer = None
        try:
            with _archiv(lage) as archiv:
                benutzer = _angemeldet(anfrage, archiv)
        except Exception:  # noqa: BLE001
            # **Weit gefangen, mit Grund:** Diese Seite muss auch dann
            # antworten, wenn das Archiv klemmt - gerade dann sucht
            # jemand nach den Bedingungen.
            benutzer = None
        return HTMLResponse(
            seiten.rechtliches(benutzer, thema=_thema(anfrage))
        )

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
                benutzer, ausdruck, treffer, gesamt, seite_nr, JE_SEITE,
                postfaecher=archiv.index.account_totals(sicht=blick),
                thema=_thema(anfrage),
            ))

    async def maske(anfrage):
        """Die ausführliche Suche.

        Zwei Knöpfe, ein Formular: »Suchtext zeigen« bleibt hier und
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
                benutzer, werte, konten, sorted(ordner), fertig,
                thema=_thema(anfrage),
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
                        thema=_thema(anfrage),
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
            return HTMLResponse(seiten.nachricht(
                benutzer, kopf, zerlegt.body or "", kennung,
                anhaenge=zerlegt.attachments,
                # Mit derselben Sicht: Ein Gespräch kann über mehrere
                # Postfächer laufen, und wer nur eines sehen darf,
                # bekommt auch nur die Teile daraus.
                verlauf=archiv.index.verlauf(kennung, sicht=Sicht.fuer(benutzer)),
                thema=_thema(anfrage),
            ))

    async def anhang(anfrage):
        """Einen Anhang herunterladen – ohne den Umweg über die .eml.

        **Über die Nummer, nicht über den Dateinamen.** Ein Anhangsname
        kommt von einem Fremden: Er kann Schrägstriche, Zeilenumbrüche
        oder Kodierungen enthalten, die in einer Adresse nichts zu
        suchen haben. Die Nummer ist die Stelle in der Mail und sonst
        nichts.
        """
        kennung = anfrage.path_params["kennung"]
        try:
            nummer = int(anfrage.path_params["nummer"])
        except ValueError:
            return Response("Nicht gefunden", status_code=404)

        with _archiv(lage) as archiv:
            benutzer = _angemeldet(anfrage, archiv)
            if benutzer is None:
                return _weiter_zur_anmeldung()

            treffer = _sichtbarer_treffer(archiv, benutzer, kennung)
            if treffer is None:
                return Response("Nicht gefunden", status_code=404)

            from mailburg.extract.message import parse

            rohdaten = archiv.store.get(treffer.hash, treffer.bucket)
            # Erst hier mit Inhalten: Für die Anzeige der Liste genügen
            # Name und Größe, und eine Mail mit einem 40-MB-Anhang soll
            # nicht bei jedem Blick darauf im Speicher liegen.
            zerlegt = parse(rohdaten, with_payloads=True)

            if not 0 <= nummer < len(zerlegt.attachments):
                return Response("Nicht gefunden", status_code=404)
            stueck = zerlegt.attachments[nummer]

        return Response(
            stueck.payload,
            # **Nie den Typ aus der Mail übernehmen.** Ein Anhang ist
            # eine fremde Datei; stünde dort "text/html" und lieferte
            # der Browser sie an, liefe fremdes JavaScript im Kontext
            # dieses Dienstes - und käme an das Sitzungscookie.
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": _dateiname_kopfzeile(
                    stueck.filename or f"anhang-{nummer + 1}"
                ),
                # Und der Browser soll auch nicht selbst raten.
                "X-Content-Type-Options": "nosniff",
            },
        )

    def _nachricht_ausliefern(anfrage, *, herunterladen: bool):
        """Die Rohnachricht – zum Speichern oder zum Öffnen.

        **Der Unterschied ist eine einzige Kopfzeile, und er ist groß.**
        Mit ``attachment`` legt der Browser die Datei in den
        Download-Ordner, und wer sie lesen will, sucht sie dort und
        klickt sie an. Ohne das überlässt er dem Betriebssystem die
        Frage, womit ``message/rfc822`` zu öffnen sei – und das ist das
        eingerichtete Mailprogramm.

        **Was ein Browser nicht kann**, und das soll hier stehen, damit
        es niemand für einen Fehler hält: Er startet kein Programm von
        sich aus. Je nach Browser und Einstellung erscheint ein Dialog
        »Öffnen mit …«, oder die Datei landet doch im Download-Ordner.
        Beides ist richtig; der Browser entscheidet, nicht wir.
        """
        kennung = anfrage.path_params["kennung"]
        with _archiv(lage) as archiv:
            benutzer = _angemeldet(anfrage, archiv)
            if benutzer is None:
                return _weiter_zur_anmeldung()

            treffer = _sichtbarer_treffer(archiv, benutzer, kennung)
            if treffer is None:
                return Response("Nicht gefunden", status_code=404)

            rohdaten = archiv.store.get(treffer.hash, treffer.bucket)

        # Der Dateiname als reine Kennung: Ein Betreff kann alles
        # enthalten, und ein Dateiname mit Anführungszeichen oder
        # Zeilenumbruch darin ist ein eigenes Problem.
        name = f'{kennung[:16]}.eml'
        art = "attachment" if herunterladen else "inline"

        return Response(
            rohdaten,
            media_type="message/rfc822",
            headers={
                "Content-Disposition": f'{art}; filename="{name}"',
                # **Auch beim Öffnen kein Raten.** ``message/rfc822``
                # bleibt, was es ist; ohne diese Zeile könnte ein Browser
                # den Inhalt für HTML halten und ihn darstellen – samt
                # allem, was ein Absender hineingeschrieben hat.
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def datei(anfrage):
        return _nachricht_ausliefern(anfrage, herunterladen=True)

    async def oeffnen(anfrage):
        return _nachricht_ausliefern(anfrage, herunterladen=False)

    return [
        Route("/", suchen),
        Route("/anmelden", anmeldeseite),
        Route("/anmelden", anmelden, methods=["POST"]),
        Route("/abmelden", abmelden),
        Route("/thema", thema_waehlen),
        Route("/rechtliches", rechtliches),
        Route("/maske", maske),
        Route("/nachricht/{kennung}", nachricht),
        Route("/nachricht/{kennung}/datei", datei),
        Route("/nachricht/{kennung}/oeffnen", oeffnen),
        Route("/nachricht/{kennung}/anhang/{nummer}", anhang),
    ]





def _dateiname_kopfzeile(name: str) -> str:
    """Eine ``Content-Disposition``-Zeile, die auch Umlaute überlebt.

    Ein Anhangsname kommt von einem Fremden. In der Kopfzeile darf er
    weder Anführungszeichen noch Zeilenumbrüche enthalten – letztere
    hängten sonst eigene Kopfzeilen an die Antwort an.

    Zweimal genannt, wie RFC 6266 es vorsieht: einmal auf ASCII
    zurückgestutzt für alte Programme, einmal als ``filename*`` mit
    UTF-8. Wer beides versteht, nimmt das zweite.
    """
    from urllib.parse import quote

    sauber = "".join(
        zeichen for zeichen in name
        if zeichen.isprintable() and zeichen not in '"\\'
    ).strip() or "anhang"
    sauber = sauber.replace("/", "-").replace("\\", "-")[:120]

    einfach = sauber.encode("ascii", "replace").decode("ascii")
    return (
        f'attachment; filename="{einfach}"; '
        f"filename*=UTF-8''{quote(sauber, safe='')}"
    )
