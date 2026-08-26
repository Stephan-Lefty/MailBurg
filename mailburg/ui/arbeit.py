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

from PySide6.QtCore import QObject, Qt, QThread, Signal


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


#: Alle Läufer, die gerade arbeiten. Der entscheidende Punkt: Solange ein
#: Faden läuft, muss irgendetwas auf ihn zeigen. Zeigt niemand mehr auf
#: ihn – etwa weil der Dialog geschlossen wurde, der ihn gestartet hat –,
#: räumt Python ihn weg, und Qt beendet daraufhin **das gesamte Programm**.
#: Ohne Meldung, ohne Rückfrage; für den Anwender verschwindet einfach das
#: Fenster.
#:
#: Genau das ist zweimal passiert: beim Prüfen mit falschen Passwörtern.
#: Der Fehler lässt sich nicht als Python-Ausnahme abfangen, weil er in
#: Qts C++-Teil geschieht – deshalb diese Liste, die jeden laufenden Faden
#: am Leben hält, bis er von sich aus fertig ist.
_LAUFENDE: set = set()


class Läufer(QObject):
    """Hält Faden und Auftrag zusammen, solange sie leben.

    Ein ``QObject`` zu sein ist hier keine Förmlichkeit. Nur an einem
    ``QObject`` erkennt Qt, zu welchem Faden ein Empfänger gehört, und
    stellt einen Aufruf über Fadengrenzen hinweg in dessen Warteschlange.
    Bei einer gewöhnlichen Python-Klasse fehlt diese Angabe – Qt ruft
    dann sofort auf, und zwar im Arbeitsfaden.
    """

    def __init__(self, auftrag: Auftrag) -> None:
        super().__init__()
        self.auftrag = auftrag
        self.faden = QThread()
        auftrag.moveToThread(self.faden)

        self.faden.started.connect(auftrag.starten)
        # Ausdrücklich direkt: Diese beiden fassen keine Oberfläche an,
        # sie rufen nur ``quit()`` - das ist fadensicher. Über die
        # Warteschlange gingen sie erst, wenn die Oberfläche wieder dran
        # ist; bis dahin liefe der Faden weiter, obwohl er fertig ist.
        auftrag.fertig.connect(self._beenden, Qt.DirectConnection)
        auftrag.gescheitert.connect(self._beenden, Qt.DirectConnection)
        # Erst wenn der Faden wirklich zu Ende ist, darf er weggeräumt
        # werden - nicht schon, wenn das Ergebnis vorliegt.
        self.faden.finished.connect(self._abmelden)

    def starten(self) -> None:
        _LAUFENDE.add(self)
        self.faden.start()

    def _beenden(self, *_egal) -> None:
        self.faden.quit()

    def _abmelden(self) -> None:
        _LAUFENDE.discard(self)

    def warten(self, millisekunden: int = 5000) -> bool:
        """Wartet auf das Ende – beim Schließen des Fensters."""
        self.auftrag.abbrechen()
        self.faden.quit()
        fertig = self.faden.wait(millisekunden)
        _LAUFENDE.discard(self)
        return fertig


def alle_abbrechen() -> None:
    """Bittet alle laufenden Fäden aufzuhören – ohne zu warten.

    **Nicht warten ist hier wesentlich.** Ein ``QThread.wait()`` blockiert
    den Faden der Oberfläche: Solange es läuft, verarbeitet Qt keine
    Ereignisse mehr, und für den Anwender ist das Fenster eingefroren –
    Knöpfe reagieren nicht, nicht einmal »Abbrechen«. Bei einer Anmeldung,
    die auf einen stummen Server wartet, dauert das quälend lange.

    Nötig ist das Warten auch gar nicht: Die laufenden Fäden stehen in
    :data:`_LAUFENDE` und halten sich damit selbst am Leben, bis sie fertig
    sind. Sie räumen sich anschließend selbst weg. Das Fenster darf
    ruhig vorher verschwinden.
    """
    for laeufer in list(_LAUFENDE):
        laeufer.auftrag.abbrechen()
        laeufer.faden.quit()


def alle_beenden(millisekunden: int = 3000) -> None:
    """Wartet doch – aber nur beim Beenden des ganzen Programms.

    Dort ist es umgekehrt: Wenn Qt seine Anwendung abbaut, während noch
    Fäden laufen, stürzt es beim Aufräumen ab. Ein kurzes Warten am
    Schluss ist deshalb richtig – ein Fenster, das ohnehin verschwindet,
    kann dabei auch stehen bleiben.
    """
    for laeufer in list(_LAUFENDE):
        laeufer.warten(millisekunden)


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
        from mailburg.sources.imap import ZEITGRENZE_PRUEFEN, ImapSource

        self.meldung.emit(f"Verbinde mit {self.konto.server} …")
        # Kürzer als beim Abruf: Hier sitzt jemand davor und wartet.
        quelle = ImapSource(
            self.konto, self.passwort, zeitgrenze=ZEITGRENZE_PRUEFEN
        )
        try:
            return quelle.folders()
        finally:
            quelle.close()


#: **Regel für alle Empfänger dieser Signale:** eine gebundene Methode
#: eines ``QObject`` aus dem Faden der Oberfläche – niemals ein Lambda,
#: keine ``functools.partial``, keine freie Funktion. Denen fehlt die
#: Fadenzugehörigkeit, also verbindet Qt sie *direkt*: Der Empfänger läuft
#: im Arbeitsfaden mit. Wer dort ein Widget anfasst, bekommt
#: »QObject::setParent: Cannot set parent, new parent is in a different
#: thread«, eine Flut von »QBasicTimer::stop: Failed« – und ein Fenster,
#: das sich nicht mehr rührt. Genau daran hing die Einrichtung fest.
#:
#: Wer mehrere Aufträge auseinanderhalten muss, merkt sich die Zuordnung
#: in einem Wörterbuch und holt den Auftrag im Empfänger über ``sender()``.


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

            if not self.abgebrochen:
                zustand.lauf_beendet()
                zustand.speichern()

            if any(getattr(e, "neu", 0) for e in ergebnisse.values()):
                self.meldung.emit("Verdichte den Suchindex …")
                archiv.index.optimize()

            # Dasselbe Häppchen wie beim Abruf über die Kommandozeile.
            # Ohne das blieben eingescannte PDF für alle unlesbar, die
            # MailBurg nur über die Oberfläche bedienen - und gerade die
            # erfahren am wenigsten davon, dass etwas fehlt.
            if not self.abgebrochen:
                self._anhaenge_lesen(archiv)

        return ergebnisse

    def _anhaenge_lesen(self, archiv) -> None:
        """Ein Häppchen Texterkennung, im Anschluss an den Abruf.

        Begrenzt, damit ein Abruf nicht zur Stunde wird: Wer auf »Jetzt
        abrufen« klickt, wartet auf seine Post, nicht auf Bilderkennung.
        Der Rest bleibt liegen und kommt beim nächsten Mal dran.
        """
        from mailburg.core import erkennung
        from mailburg.extract import ocr

        bereit, _hinweis = ocr.bereit()
        if not bereit:
            return
        offen = erkennung.Warteschlange(archiv.index).anzahl()
        if not offen:
            return

        self.meldung.emit(f"Lese eingescannte PDF ({offen} offen) …")
        stat = erkennung.durchlauf(
            archiv, weiter=lambda: not self.abgebrochen
        )
        if stat.gelesen:
            self.meldung.emit(
                f"{stat.gelesen} eingescannte PDF durchsuchbar gemacht"
            )
