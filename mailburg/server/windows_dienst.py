"""MailBurg als Windows-Dienst.

    python -m mailburg.server.windows_dienst install
    python -m mailburg.server.windows_dienst start
    python -m mailburg.server.windows_dienst stop
    python -m mailburg.server.windows_dienst remove

**Am 2026-10-02 zum ersten Mal auf einem Windows Server 2025 gelaufen –
und sofort gestorben.** uvicorns Vorgabe-Protokoll setzt eine
Standardausgabe voraus, die ein Dienst nicht hat; die Einzelheiten
stehen bei :func:`uvicorn_einstellungen`. Behoben, aber der Weg dorthin
ist lehrreich: Der Dienst meldete sich im Ereignisprotokoll als
*gestartet* und war eine Sekunde später wieder unten. In `services.msc`
sah das aus wie »lässt sich nicht starten«.

**Was darüber hinaus ungeprüft bleibt:** Ob er über einen Neustart
hinweg oben bleibt, und ob er als LocalSystem an den Tresor kommt – er
hat kein Benutzerprofil und damit kein `%APPDATA%`. Wer ihn einrichtet,
lässt vorher `mailburg server` von Hand laufen: Geht das, liegt ein
Fehler danach am Dienstgerüst und nicht an MailBurg.

Derselbe Vermerk steht in `docs/server.md` und gilt so lange, wie er
stimmt.

**Warum pywin32 und nicht NSSM.** Am 2026-08-31 nachgeschlagen: NSSM,
der verbreitetste Wrapper, hat seit über einem Jahrzehnt kein stabiles
Release mehr. Für ein Archiv, das zwanzig Jahre halten soll, ist das die
falsche Grundlage. WinSW ist im Wartungsmodus, Servy zu jung. pywin32
meldet den Dienst richtig beim Dienstmanager an – Start und Stopp über
``services.msc``, Neustart über ``sc failure`` – und ist Python-eigen,
also kein zweites Programm, das mitgepflegt werden will.

**Warum die Aufgabenplanung nicht reicht**, obwohl MailBurg sie für den
regelmäßigen Abruf schon benutzt: Sie startet ein Programm auch ohne
angemeldeten Benutzer, hält es aber nicht am Leben. Stürzt der Dienst
ab, bleibt er unten.
"""

from __future__ import annotations

import logging
import sys

#: Wie der Dienst in ``services.msc`` heißt.
NAME = "MailBurgServer"
ANZEIGE = "MailBurg Server Edition"
BESCHREIBUNG = (
    "Stellt ein MailBurg-Archiv im Netz bereit. Liest seine Einstellungen "
    "aus den Umgebungsvariablen MAILBURG_ARCHIV, MAILBURG_ADRESSE und "
    "MAILBURG_PORT."
)

#: Wie lange auf ein sauberes Ende gewartet wird, bevor abgebrochen wird.
#: Großzügig: Läuft gerade eine Anfrage, soll sie zu Ende gehen.
ABKLINGEN = 30


def uvicorn_einstellungen(lage):
    """Die uvicorn-Einstellungen für den Dienstbetrieb.

    **Ein Dienst hat keine Standardausgabe.** Unter pywin32 ist
    ``sys.stdout`` schlicht ``None``. uvicorns Vorgabe-Protokoll baut
    einen Formatter, der sich fragt, ob die Ausgabe ein Terminal ist –
    und stolpert über None. Das Ergebnis ist eine Meldung, die nicht im
    Entferntesten nach der Ursache klingt::

        ValueError: Unable to configure formatter 'default'

    Am 2026-10-02 auf einem Windows Server 2025 aufgelaufen, beim ersten
    Startversuch überhaupt. Der Dienst meldete sich im Ereignisprotokoll
    als gestartet und starb eine Sekunde später.

    Deshalb ``log_config=None``. Damit uvicorns Meldungen danach nicht
    einfach verschwinden – darunter die, die einen belegten Port nennt –,
    hängt :func:`_protokoll_einrichten` sie ans Ereignisprotokoll.

    **Eigene Funktion, damit sie ohne Windows prüfbar ist.** Der Fehler
    tritt überall auf, wo keine Standardausgabe da ist; ein Test kann
    das nachstellen, ohne dass ein Windows-Rechner danebensteht.
    """
    import uvicorn

    from mailburg.server.dienst import anwendung

    return uvicorn.Config(
        anwendung(lage),
        host=lage.adresse,
        port=lage.anschluss,
        # Kein Zugriffsprotokoll: Es wüchse im Ereignisprotokoll mit
        # jedem Aufruf. Wer es braucht, bekommt es vom Reverse Proxy.
        access_log=False,
        log_config=None,
    )


def _fehlt() -> None:
    print(
        "Für den Windows-Dienst fehlt pywin32.\n"
        "Nachrüsten mit:  pip install pywin32\n"
        "Danach einmal:   py Scripts\\pywin32_postinstall.py -install",
        file=sys.stderr,
    )


try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
except ImportError:  # pragma: no cover – nur auf Windows vorhanden
    HAT_PYWIN32 = False
else:
    HAT_PYWIN32 = True

    class _Ereignisprotokoll(logging.Handler):
        """Hängt Python-Protokollmeldungen ins Windows-Ereignisprotokoll.

        Ohne ihn verlöre der Dienst mit ``log_config=None`` jede Meldung
        von uvicorn – auch die über einen belegten Port. **Ein Fehler,
        den niemand lesen kann, ist keiner, der gemeldet wurde.**
        """

        def emit(self, satz: logging.LogRecord) -> None:
            try:
                text = self.format(satz)
                if satz.levelno >= logging.ERROR:
                    servicemanager.LogErrorMsg(text)
                elif satz.levelno >= logging.WARNING:
                    servicemanager.LogWarningMsg(text)
                else:
                    servicemanager.LogInfoMsg(text)
            except Exception:  # noqa: BLE001
                # **Hier ist das weite Fangen richtig**, anders als sonst
                # in diesem Projekt: Ein Protokollhandler, der wirft,
                # reißt den Dienst mit, den er beschreiben soll.
                # ``handleError`` ist der dafür vorgesehene Weg.
                self.handleError(satz)

    def _protokoll_einrichten() -> None:
        """uvicorns Meldungen ins Ereignisprotokoll umhängen."""
        handler = _Ereignisprotokoll()
        handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))

        # Nur »uvicorn«: Seine übrigen Protokolle (``uvicorn.error``,
        # ``uvicorn.access``) hängen darunter und reichen nach oben
        # durch. Ein zweiter Handler dort schriebe jede Zeile doppelt.
        logger = logging.getLogger("uvicorn")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

    class MailBurgDienst(win32serviceutil.ServiceFramework):
        """Der Dienst selbst."""

        _svc_name_ = NAME
        _svc_display_name_ = ANZEIGE
        _svc_description_ = BESCHREIBUNG

        def __init__(self, args):
            super().__init__(args)
            # Das Ereignis, mit dem SvcStop dem laufenden Dienst Bescheid
            # gibt. Ohne es liefe er weiter, und der Dienstmanager
            # brächte ihn nach seiner Frist hart um.
            self.halt = win32event.CreateEvent(None, 0, 0, None)
            self.server = None
            self.abruf = None

        def SvcStop(self):  # noqa: N802 – von pywin32 so verlangt
            """Wird vom Dienstmanager beim Beenden gerufen."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            # **Erst uvicorn Bescheid sagen, dann das Ereignis setzen.**
            # Andersherum wachte SvcDoRun auf und beendete den Prozess,
            # während noch eine Anfrage lief.
            if self.server is not None:
                self.server.should_exit = True
            win32event.SetEvent(self.halt)

        def SvcDoRun(self):  # noqa: N802 – von pywin32 so verlangt
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            try:
                self._laufen()
            except Exception as fehler:  # noqa: BLE001
                # **Ins Ereignisprotokoll, nicht auf eine Konsole.** Ein
                # Dienst hat keine; ohne diesen Eintrag stünde in
                # services.msc nur »konnte nicht gestartet werden«.
                servicemanager.LogErrorMsg(
                    f"{ANZEIGE} konnte nicht starten: {fehler}"
                )
                raise

        def _laufen(self) -> None:
            import threading

            import uvicorn

            from mailburg.server.einstellungen import Serverlage

            lage = Serverlage.aus_umgebung()
            _protokoll_einrichten()

            # **Der Abruf gehört in den Dienst.** Die Aufgabenplanung
            # läuft nur bei angemeldetem Benutzer – auf einem Server ist
            # sonntagabends niemand angemeldet. Siehe ``server/abruf.py``.
            from mailburg.server.dienst import _abruf_starten

            self.abruf = _abruf_starten(lage)

            self.server = uvicorn.Server(uvicorn_einstellungen(lage))

            # **In einem eigenen Faden.** uvicorn.run() kehrt erst zurück,
            # wenn der Server endet - dieser Faden muss aber frei bleiben,
            # um auf das Halte-Ereignis zu warten. Sonst könnte SvcStop
            # nichts ausrichten.
            faden = threading.Thread(target=self.server.run, daemon=True)
            faden.start()

            win32event.WaitForSingleObject(self.halt, win32event.INFINITE)

            # **Erst den Abruf anhalten, dann den Webserver.** Mitten im
            # Aufnehmen einer Mail beendet zu werden hinterlässt eine
            # angefangene Journalzeile; sie wird zwar beim nächsten
            # Öffnen übersprungen, aber es gibt keinen Grund, sie zu
            # erzeugen.
            if self.abruf is not None:
                self.abruf.anhalten()
            faden.join(timeout=ABKLINGEN)


def main(argv: list[str] | None = None) -> int:
    if not HAT_PYWIN32:
        _fehlt()
        return 2
    win32serviceutil.HandleCommandLine(
        MailBurgDienst, argv=list(argv or sys.argv)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
