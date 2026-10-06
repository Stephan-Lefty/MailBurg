"""Der Dienst holt selbst Post – ohne angemeldeten Benutzer.

**Warum das sein muss.** Der Zeitplan, den MailBurg bisher kennt, läuft
unter Windows über die Aufgabenplanung – und die trägt
``<LogonType>InteractiveToken</LogonType>``: Die Aufgabe läuft **nur,
solange der Benutzer angemeldet ist**. Auf einem Server ist sonntagabends
niemand angemeldet. Die Aufgabe stünde brav in der Liste und täte nichts.

Genau die Art Fehler, die dieses Projekt sonst bei anderen findet: *Was
eingerichtet aussieht, ist damit nicht eingerichtet.* Am 2026-10-02 im
Code bestätigt, bevor es jemanden getroffen hat.

**Die Lösung ist nicht, die Aufgabenplanung zu reparieren.** Der Dienst
läuft ohnehin – als ``LocalSystem`` unter Windows, als eigener Benutzer
unter systemd, rund um die Uhr. Er soll das Archiv nicht nur ausliefern,
sondern auch füllen.

**Und damit schreibt genau ein Prozess ins Archiv.** Das ist der
eigentliche Gewinn: Am 2026-09-21 ist die Hash-Kette gerissen, weil zwei
Prozesse gleichzeitig anhängten – ein offenes Fenster und ein Zeitplan.
Wer den Abruf in den Dienst legt, hat dieses Problem nicht mehr, sondern
eine Stelle, die der Reihe nach arbeitet.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as uhrzeit
from pathlib import Path

#: Wie oft geholt wird, in Minuten. ``0`` schaltet ab.
#:
#: Halbstündlich ist bei Mail ein vernünftiger Kompromiss – neu genug, um
#: nichts zu verpassen, selten genug, um den Mailserver nicht zu
#: belästigen. Dieselbe Vorgabe wie im Zeitplan des Fensters.
TAKT = "MAILBURG_ABRUF"
STANDARDTAKT = 0

#: Wann *nicht* geholt wird, als ``HH:MM-HH:MM``.
#:
#: **Für die nächtliche Sicherung.** Läuft das Band, während MailBurg ins
#: Journal schreibt, erwischt die Sicherung einen Zwischenstand. MailBurg
#: ist darauf vorbereitet – eine angefangene Zeile wird beim nächsten
#: Öffnen übersprungen –, aber es ist sauberer, wenn sich beides nicht
#: ins Gehege kommt.
PAUSE = "MAILBURG_ABRUF_PAUSE"

#: Wie lange nach einem Fehler gewartet wird, bevor es weitergeht.
#: **Nicht aufgeben:** Ein Mailserver, der heute Nacht nicht antwortet,
#: antwortet morgen früh vielleicht wieder. Ein Abruf, der sich nach dem
#: ersten Fehlschlag abschaltet, fällt niemandem auf.
NACH_EINEM_FEHLER = 5 * 60


@dataclass
class Lage:
    """Wie der Abruf eingestellt ist."""

    takt: int = STANDARDTAKT
    pause_von: uhrzeit | None = None
    pause_bis: uhrzeit | None = None

    @property
    def an(self) -> bool:
        return self.takt > 0

    @classmethod
    def aus_umgebung(cls) -> Lage:
        roh = os.environ.get(TAKT, "").strip()
        try:
            takt = int(roh) if roh else STANDARDTAKT
        except ValueError:
            takt = STANDARDTAKT

        von, bis = _pause_lesen(os.environ.get(PAUSE, ""))
        return cls(takt=max(0, takt), pause_von=von, pause_bis=bis)

    def pausiert(self, jetzt: uhrzeit | None = None) -> bool:
        """Ob gerade Ruhe herrscht.

        **Über Mitternacht hinweg.** »23:00-02:00« ist der häufigste
        Fall bei einer nächtlichen Sicherung; eine Prüfung mit ``<=``
        allein fände dort nie ein Fenster.
        """
        if self.pause_von is None or self.pause_bis is None:
            return False
        nun = jetzt or datetime.now().time()
        if self.pause_von <= self.pause_bis:
            return self.pause_von <= nun < self.pause_bis
        return nun >= self.pause_von or nun < self.pause_bis


def _pause_lesen(roh: str) -> tuple[uhrzeit | None, uhrzeit | None]:
    """»01:30-03:00« in zwei Uhrzeiten.

    Was sich nicht lesen lässt, gilt als »keine Pause«. **Lieber zu oft
    abrufen als stillschweigend gar nicht:** Ein Tippfehler in dieser
    Angabe darf nicht dazu führen, dass monatelang keine Post ankommt.
    """
    roh = (roh or "").strip()
    if "-" not in roh:
        return None, None
    anfang, _, ende = roh.partition("-")
    try:
        return (
            uhrzeit.fromisoformat(anfang.strip()),
            uhrzeit.fromisoformat(ende.strip()),
        )
    except ValueError:
        return None, None


class Schleife:
    """Holt in festem Takt Post, bis jemand sie anhält.

    **In einem eigenen Faden, nicht im Webserver.** Ein Abruf über
    siebzig Postfächer dauert Minuten; liefe er im selben Faden wie die
    Weboberfläche, stünde die so lange still.
    """

    def __init__(self, archiv: Path, lage: Lage | None = None,
                 passwort: str = "") -> None:
        self.archiv = Path(archiv)
        self.lage = lage or Lage.aus_umgebung()
        self.passwort = passwort
        self.halt = threading.Event()
        self.faden: threading.Thread | None = None

        #: Für die Statusseite: wann zuletzt geholt wurde und was dabei
        #: herauskam. **Im Speicher, nicht auf der Platte** – es ist eine
        #: Auskunft über diesen Lauf, kein Zustand des Archivs.
        self.zuletzt: datetime | None = None
        self.letzter_befund = ""
        self.laeufe = 0

    def starten(self) -> None:
        if not self.lage.an:
            return
        self.faden = threading.Thread(
            target=self._schleife, name="mailburg-abruf", daemon=True
        )
        self.faden.start()

    def anhalten(self, geduld: float = 30.0) -> None:
        """Hält an – und wartet, bis ein laufender Abruf fertig ist.

        **Nicht abwürgen.** Mitten im Aufnehmen einer Mail beendet zu
        werden, hinterlässt eine angefangene Journalzeile. Die wird zwar
        beim nächsten Öffnen übersprungen, aber es gibt keinen Grund,
        sie zu erzeugen.
        """
        self.halt.set()
        if self.faden is not None:
            self.faden.join(timeout=geduld)

    def _schleife(self) -> None:
        # **Beim Start einmal warten, nicht sofort holen.** Der Dienst
        # kommt beim Hochfahren des Servers hoch; dann ist das Netz
        # womöglich noch nicht da, und ein erster Fehlschlag stünde
        # ohne Grund im Protokoll.
        if self.halt.wait(60):
            return

        while not self.halt.is_set():
            if self.lage.pausiert():
                # Während der Pause im Minutentakt nachsehen, ob sie
                # vorbei ist – nicht den vollen Takt verschlafen.
                if self.halt.wait(60):
                    return
                continue

            wartezeit = self.lage.takt * 60
            try:
                self._einmal()
            except Exception as fehler:  # noqa: BLE001
                # **Weit gefangen, mit Grund:** Was hier durchkäme,
                # beendete den Faden – und der Abruf höre auf, ohne dass
                # etwas rot wird. Genau die Sorte Fehler, die erst
                # auffällt, wenn Wochen fehlen.
                self.letzter_befund = f"Fehlgeschlagen: {fehler}"
                self._melden(f"Abruf fehlgeschlagen: {fehler}", fehler=True)
                wartezeit = max(NACH_EINEM_FEHLER, wartezeit)

            if self.halt.wait(wartezeit):
                return

    def _einmal(self) -> None:
        """Ein Durchgang über alle eingerichteten Postfächer.

        **``Kontenliste`` ist kein Behälter, sondern hat einen.** Hier
        stand bis zum 2026-10-06 ``for k in Kontenliste()`` – und das
        wirft ``'Kontenliste' object is not iterable``, in der ersten
        Zeile, bei jedem Lauf. Der Abruf im Dienst hat damit **nie**
        Post geholt, seit es ihn gibt.

        Gesehen hat es niemand, weil der Fehler genau dort landet, wo er
        hingehört und wo niemand hinsieht: im weiten ``except`` der
        Schleife, von dort ins Ereignisprotokoll. Der Dienst lief
        weiter, die Statusseite meldete »alle 30 Minuten«, und das
        Archiv bekam nichts dazu. Aufgefallen am ersten Tag im echten
        Betrieb, und auch das nur nebenbei.
        """
        from mailburg.core.accounts import Kontenliste
        from mailburg.core.archive import Archive

        konten = [
            k for k in Kontenliste().konten if getattr(k, "aktiv", True)
        ]
        if not konten:
            self.letzter_befund = "Keine Postfächer eingerichtet."
            return

        from mailburg.core.sync import Abrufzustand

        neu = geholt = uebersprungen = 0
        with Archive.open(
            self.archiv, exclusive=True, passwort=self.passwort
        ) as archiv:
            zustand = Abrufzustand(archiv.uuid)
            try:
                for konto in konten:
                    if self.halt.is_set():
                        break
                    zahl = self._konto(archiv, konto, zustand)
                    if zahl is None:
                        uebersprungen += 1
                    else:
                        neu += zahl
                        geholt += 1
            finally:
                # **Auch bei einem Abbruch.** Sonst gehen die
                # Vormerkungen gescheiterter Mails verloren, und der
                # Höchststand zöge an ihnen vorbei – sie fehlten dann
                # für immer, ohne Spur.
                zustand.speichern()

        self.zuletzt = datetime.now()
        self.laeufe += 1
        self.letzter_befund = self._befund(neu, geholt, uebersprungen)
        self._melden(self.letzter_befund, fehler=bool(uebersprungen))

        # **Der Bericht hängt am Abruf und braucht keinen zweiten
        # Faden.** Die Schleife läuft ohnehin alle paar Minuten; ein
        # eigener Zeitgeber wäre ein zweiter Ort, an dem etwas
        # steckenbleiben kann. Und berichtet wird über das, was der
        # Abruf getan hat – ohne ihn gäbe es nichts zu melden.
        self._berichten(neu, uebersprungen)

    def _berichten(self, neu: int, uebersprungen: int) -> None:
        """Tagesbericht und Störungsmeldung – beides nach Lage.

        **Fehler hier dürfen den Abruf nicht kosten.** Ein Mailserver,
        der nicht antwortet, ist ein Grund, keinen Bericht zu schicken –
        kein Grund, die Post nicht zu holen.
        """
        try:
            from mailburg.server import meldung

            meldung.nach_einem_lauf(
                self.archiv, neu=neu, uebersprungen=uebersprungen,
                befund=self.letzter_befund, passwort=self.passwort,
                melden=self._melden,
            )
        except Exception as fehler:  # noqa: BLE001
            self._melden(f"Bericht nicht möglich: {fehler}", fehler=True)

    @staticmethod
    def _befund(neu: int, geholt: int, uebersprungen: int) -> str:
        """Was am Ende eines Laufs dasteht.

        **Übersprungene Postfächer dürfen nicht als geprüft gelten.** Am
        2026-10-06 meldete der Dienst »Nichts Neues in 7 Postfächern«,
        während alle sieben an einem Fehler gescheitert waren. Das ist
        die teuerste Sorte Auskunft: Sie beruhigt und stimmt nicht – und
        wer sie liest, sucht die ausbleibende Post anderswo.
        """
        teile = []
        if geholt:
            teile.append(
                f"{neu} neue Mails aus {geholt} Postfächern."
                if neu else f"Nichts Neues in {geholt} Postfächern."
            )
        if uebersprungen:
            teile.append(
                f"{uebersprungen} Postfächer übersprungen – "
                f"von dort kam nichts."
            )
        return " ".join(teile) or "Keine Postfächer geprüft."

    def _konto(self, archiv, konto, zustand) -> int | None:
        """Ein Postfach – Fehler bleiben bei ihm.

        Gibt die Zahl der neuen Mails zurück, oder ``None``, wenn das
        Postfach übersprungen wurde.

        **Ein klemmendes Postfach beendet den Lauf nicht.** Dieselbe
        Regel wie beim Abgleich: Wer nach dem ersten Fehler aufhört,
        verliert die Post aller übrigen. Was übersprungen wurde, wird
        genannt.

        **Höchststand und Abrufzustand gehören dazu, nicht nur das
        Passwort.** Ohne sie holte jeder Lauf das ganze Postfach erneut –
        alle dreißig Minuten, bei 70.000 Mails. Bis zum 2026-10-06 stand
        hier ``quelle_fuer(konto)``, also ohne alles; der Aufruf kam nie
        bis zum Server, weil schon das fehlende Passwort eine Ausnahme
        warf.
        """
        from mailburg.core import accounts
        from mailburg.core.importer import importieren
        from mailburg.sources import quelle_fuer

        try:
            passwort = accounts.passwort_holen(konto, streng=True) or ""
        except Exception as fehler:  # noqa: BLE001
            self._melden(
                f"Postfach »{konto.name}« übersprungen: {fehler}", fehler=True
            )
            return None

        if not passwort and not getattr(konto, "per_oauth2", False):
            # **Eigene Meldung, nicht dieselbe wie bei einem Netzfehler.**
            # Ein Dienst kann nicht nachfragen; hier fehlt etwas, das ein
            # Mensch auf dem Server hinterlegen muss.
            self._melden(
                f"Postfach »{konto.name}« übersprungen: kein Passwort im "
                f"Tresor. Nachtragen mit »mailburg tresor uebernehmen« auf "
                f"dem Rechner, auf dem das Postfach eingerichtet ist.",
                fehler=True,
            )
            return None

        def vormerken(nachricht, _fehler, k=konto) -> None:
            if nachricht.uid is not None:
                zustand.vormerken(k.name, nachricht.folder, nachricht.uid)

        try:
            quelle = quelle_fuer(
                konto,
                passwort,
                hoechststand=lambda ordner, k=konto: archiv.index.max_uid(
                    k.name, ordner
                ),
                zustand=zustand,
            )
            try:
                statistik = importieren(
                    archiv, quelle,
                    auf_fehler=vormerken,
                    betreffmarken=getattr(konto, "betreffmarken", None) or (),
                    # Beim Anhalten des Dienstes endet auch ein laufender
                    # Abruf – sonst wartet Windows auf einen Vorgang, der
                    # noch zehntausend Mails vor sich hat, und bricht ihn
                    # nach dreißig Sekunden hart ab.
                    weiter=lambda: not self.halt.is_set(),
                )
            finally:
                quelle.close()
            return int(getattr(statistik, "neu", 0))
        except Exception as fehler:  # noqa: BLE001
            self._melden(
                f"Postfach »{konto.name}« übersprungen: {fehler}", fehler=True
            )
            return None

    def _melden(self, text: str, *, fehler: bool = False) -> None:
        """Dorthin, wo auf diesem System jemand hinsieht.

        Unter Windows ins Ereignisprotokoll – auf einer Konsole, die es
        nicht gibt, liest es niemand. Unter systemd auf die
        Standardausgabe, von wo journald es aufnimmt.
        """
        if os.name == "nt":
            try:
                import servicemanager

                if fehler:
                    servicemanager.LogErrorMsg(f"MailBurg-Abruf: {text}")
                else:
                    servicemanager.LogInfoMsg(f"MailBurg-Abruf: {text}")
                return
            except Exception:  # noqa: BLE001
                pass
        print(f"[Abruf] {text}", flush=True)
