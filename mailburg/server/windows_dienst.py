"""MailBurg als Windows-Dienst.

    python -m mailburg.server.windows_dienst install
    python -m mailburg.server.windows_dienst start
    python -m mailburg.server.windows_dienst stop
    python -m mailburg.server.windows_dienst remove

**Nicht geprüft.** Hier steht kein Windows-Rechner zur Verfügung. Der
Aufbau folgt dem Muster aus den pywin32-Beispielen, nachgeschlagen am
2026-08-31 – aber gelaufen ist er nie. Wer ihn zum ersten Mal einrichtet,
sollte damit rechnen, dass etwas klemmt, und `mailburg server` von Hand
danebenlaufen lassen, um die Einstellungen zu prüfen.

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


def _fehlt() -> None:
    print(
        "Für den Windows-Dienst fehlt pywin32.\n"
        "Nachrüsten mit:  pip install 'mailburg[server-windows]'",
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

            from mailburg.server.dienst import anwendung
            from mailburg.server.einstellungen import Serverlage

            lage = Serverlage.aus_umgebung()
            self.server = uvicorn.Server(
                uvicorn.Config(
                    anwendung(lage),
                    host=lage.adresse,
                    port=lage.anschluss,
                    access_log=False,
                )
            )

            # **In einem eigenen Faden.** uvicorn.run() kehrt erst zurück,
            # wenn der Server endet - dieser Faden muss aber frei bleiben,
            # um auf das Halte-Ereignis zu warten. Sonst könnte SvcStop
            # nichts ausrichten.
            faden = threading.Thread(target=self.server.run, daemon=True)
            faden.start()

            win32event.WaitForSingleObject(self.halt, win32event.INFINITE)
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
