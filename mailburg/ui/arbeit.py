"""Langwierige Arbeit aus der Oberfläche heraushalten.

Eine Anmeldung am Mailserver dauert Sekunden, ein erster Abruf Minuten bis
Stunden. Beides im Faden der Oberfläche zu erledigen, hieße: Das Fenster
reagiert nicht mehr, das System meldet »Anwendung antwortet nicht«, und der
Anwender bricht ab – mitten im Archivieren.

Deshalb läuft hier alles in einem eigenen Faden und meldet sich über
Signale zurück. Fäden genügen dafür, obwohl der GIL Python-Code nicht
wirklich gleichzeitig laufen lässt: Warten auf das Netz gibt den GIL frei,
und um mehr geht es hier nicht. Die rechenintensive Arbeit – Anhänge
auslesen – verteilt ``core/importer.py`` ohnehin auf eigene Prozesse.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal


class Auftrag(QObject):
    """Ein Stück Arbeit, das im Hintergrund läuft.

    Absichtlich klein gehalten: Wer erbt, überschreibt nur ``ausfuehren``
    und meldet sich über die Signale. Alles, was mit Fenstern zu tun hat,
    bleibt draußen – aus einem fremden Faden darf keine Oberfläche
    angefasst werden.
    """

    fertig = Signal(object)
    gescheitert = Signal(str)
    meldung = Signal(str)
    fortschritt = Signal(int, int)
    """Erledigt und insgesamt; ist die Gesamtzahl unbekannt, steht dort 0."""

    def __init__(self) -> None:
        super().__init__()
        self._abbrechen = False

    def abbrechen(self) -> None:
        """Bittet um Abbruch – wirkt erst beim nächsten Prüfpunkt."""
        self._abbrechen = True

    @property
    def abgebrochen(self) -> bool:
        return self._abbrechen

    def ausfuehren(self):
        """Die eigentliche Arbeit. Rückgabewert geht an ``fertig``."""
        raise NotImplementedError

    def starten(self) -> None:
        """Einstieg im Hintergrundfaden."""
        try:
            ergebnis = self.ausfuehren()
        except Exception as exc:  # noqa: BLE001 – sonst stirbt der Faden stumm
            self.gescheitert.emit(str(exc))
            return
        self.fertig.emit(ergebnis)


class Läufer:
    """Hält Faden und Auftrag zusammen, solange sie leben.

    Ohne eine Referenz von außen räumt Python beides weg, während es noch
    läuft – ein Fehler, der sich als sporadischer Absturz zeigt und
    entsprechend schwer zu finden ist.
    """

    def __init__(self, auftrag: Auftrag) -> None:
        self.auftrag = auftrag
        self.faden = QThread()
        auftrag.moveToThread(self.faden)

        self.faden.started.connect(auftrag.starten)
        auftrag.fertig.connect(self._beenden)
        auftrag.gescheitert.connect(self._beenden)

    def starten(self) -> None:
        self.faden.start()

    def _beenden(self, *_egal) -> None:
        self.faden.quit()

    def warten(self, millisekunden: int = 5000) -> bool:
        """Wartet auf das Ende – beim Schließen des Fensters."""
        self.auftrag.abbrechen()
        self.faden.quit()
        return self.faden.wait(millisekunden)


class Anmeldeprobe(Auftrag):
    """Meldet sich einmal an und holt die Ordnerliste.

    Ergebnis ist die Liste der Ordner, die archiviert würden – das ist die
    brauchbarste Rückmeldung: Der Anwender sieht sofort, ob er das richtige
    Postfach erwischt hat.
    """

    def __init__(self, konto, passwort: str) -> None:
        super().__init__()
        self.konto = konto
        self.passwort = passwort

    def ausfuehren(self) -> list[str]:
        from mailburg.sources.imap import ImapSource

        self.meldung.emit(f"Verbinde mit {self.konto.server} …")
        quelle = ImapSource(self.konto, self.passwort)
        try:
            return quelle.folders()
        finally:
            quelle.close()


class Abruflauf(Auftrag):
    """Holt neue Mails für eine Reihe von Konten ins Archiv."""

    konto_beginnt = Signal(str)
    konto_fertig = Signal(str, object)

    def __init__(self, archiv_pfad, konten, *, voll: bool = False,
                 mit_anhangstext: bool = True) -> None:
        super().__init__()
        self.archiv_pfad = archiv_pfad
        self.konten = list(konten)
        self.voll = voll
        self.mit_anhangstext = mit_anhangstext

    def ausfuehren(self) -> dict:
        from mailburg.core import accounts
        from mailburg.core.archive import Archive
        from mailburg.core.importer import importieren
        from mailburg.core.sync import Abrufzustand
        from mailburg.sources.imap import ImapFehler, ImapSource

        ergebnisse: dict = {}
        with Archive.open(self.archiv_pfad) as archiv:
            zustand = Abrufzustand(archiv.uuid)

            for konto in self.konten:
                if self.abgebrochen:
                    break
                self.konto_beginnt.emit(konto.name)

                passwort = accounts.passwort_holen(konto)
                if not passwort:
                    ergebnisse[konto.name] = ImapFehler(
                        f"Für '{konto.name}' liegt kein Passwort im "
                        f"Schlüsselbund."
                    )
                    self.konto_fertig.emit(konto.name, ergebnisse[konto.name])
                    continue

                try:
                    quelle = ImapSource(
                        konto,
                        passwort,
                        hoechststand=lambda ordner, k=konto: archiv.index.max_uid(
                            k.name, ordner
                        ),
                        zustand=zustand,
                        voll=self.voll,
                    )
                except ImapFehler as exc:
                    ergebnisse[konto.name] = exc
                    self.konto_fertig.emit(konto.name, exc)
                    continue

                def melden(stat, name=konto.name) -> None:
                    self.meldung.emit(f"{name}: {stat.gelesen} geholt, {stat.neu} neu")
                    self.fortschritt.emit(stat.gelesen, 0)

                def vormerken(nachricht, exc, k=konto) -> None:
                    if nachricht.uid is not None:
                        zustand.vormerken(k.name, nachricht.folder, nachricht.uid)

                try:
                    stat = importieren(
                        archiv,
                        quelle,
                        mit_anhangstext=self.mit_anhangstext,
                        fortschritt=melden,
                        auf_fehler=vormerken,
                    )
                    ergebnisse[konto.name] = stat
                finally:
                    # Auch bei Abbruch: Sonst gehen die Vormerkungen der
                    # gescheiterten Mails verloren.
                    zustand.speichern()
                    quelle.close()

                self.konto_fertig.emit(konto.name, ergebnisse[konto.name])

            if any(getattr(e, "neu", 0) for e in ergebnisse.values()):
                self.meldung.emit("Verdichte den Suchindex …")
                archiv.index.optimize()

        return ergebnisse
