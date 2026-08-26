"""Was beim letzten Abruf war – damit der nächste nicht von vorn anfängt.

Ein Postfach mit dreißigtausend Mails jedes Mal vollständig herunterzuladen,
ist weder dem Server noch der Leitung zuzumuten. IMAP bietet dafür die UID:
eine Zahl, die innerhalb eines Ordners aufsteigt und nie neu vergeben wird.
Wer weiß, bis zu welcher UID er gekommen ist, holt beim nächsten Mal nur
noch, was darüber liegt.

**Woher der Höchststand kommt.** Nicht aus dieser Datei, sondern aus dem
Suchindex: ``MAX(uid)`` über die Fundorte eines Ordners. Das ist die einzige
Auskunft, die nicht lügen kann – sie sagt, was *tatsächlich* im Archiv
liegt. Eine mitgeschriebene Zahl wäre schon dann falsch, wenn der Lauf
mitten im Ordner abbricht: Die Zahl stünde auf der zuletzt *geholten* Mail,
nicht auf der zuletzt *abgelegten*. Beim nächsten Lauf fehlte der Rest für
immer. Der Umweg über den Index kostet eine Abfrage und macht einen
Abbruch folgenlos.

Der Index überlebt auch seinen eigenen Neuaufbau, denn die UID steht im
Journal und wird von ``Archive.rebuild_index`` wieder mitgeschrieben.

**Was dann noch hierher gehört.** Zweierlei, das der Index nicht wissen
kann:

*UIDVALIDITY.* Der Server darf seine UIDs für ungültig erklären – nach
einem Umzug des Postfachs oder einer Wiederherstellung aus der Sicherung.
Dann zählt er von vorn, und alte Höchststände zeigen ins Leere. Ändert sich
der Wert, wird der Ordner vollständig neu gelesen. Doppelt abgelegt wird
dabei nichts: Die Ablage erkennt jede Mail an ihrem Inhalt wieder.

*Nachzuholende UIDs.* Scheitert eine einzelne Mail – kaputte Kodierung,
Abbruch mitten in der Übertragung –, läuft der Abruf weiter und der
Höchststand zieht an ihr vorbei. Ohne Vormerkung wäre sie für immer
verloren, und zwar unbemerkt. Deshalb wird sie hier notiert und beim
nächsten Lauf ausdrücklich noch einmal angefordert.
"""

from __future__ import annotations

import json
from pathlib import Path

from mailburg.core import paths

#: Aufbau der Zustandsdatei. Wird sie einmal anders, lässt sich daran
#: entscheiden, ob der Inhalt noch zu gebrauchen ist.
ZUSTAND_VERSION = 1

#: Mehr als so viele Nachzügler je Ordner werden nicht aufgehoben. Wer so
#: viele Fehlschläge hat, hat ein grundsätzliches Problem – dann hilft nur
#: ein Vollabruf, und eine endlos wachsende Liste macht es nicht besser.
HOECHSTZAHL_NACHZUEGLER = 500


class Abrufzustand:
    """Was MailBurg über den letzten Abruf eines Archivs weiß.

    Eine Datei je Archiv, benannt nach dessen Kennung – aus demselben Grund
    wie beim Suchindex: Eine externe Platte, die einmal woanders eingehängt
    wird, soll ihren Zustand behalten.

    Die Datei liegt neben dem Index und nicht im Archiv. Sie ist entbehrlich:
    Geht sie verloren, wird einmal alles neu gelesen. Das kostet Zeit, aber
    keine Mail.
    """

    def __init__(self, archiv_uuid: str, datei: Path | None = None) -> None:
        self.datei = datei or (paths.data_dir() / "abruf" / f"{archiv_uuid}.json")
        self.konten: dict[str, dict[str, dict]] = {}
        self.zuletzt: str = ""
        """Wann zuletzt ein Abruf zu Ende lief, als ISO-Zeit.

        Nicht wann es zuletzt *versucht* wurde: Ein Abruf, der an einem
        stummen Server scheitert, darf das Archiv nicht als aktuell
        ausweisen. Genau darauf schaut der Anwender, bevor er sein
        Postfach aufräumen lässt.
        """
        self.laden()

    def laden(self) -> None:
        try:
            daten = json.loads(self.datei.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if daten.get("version") != ZUSTAND_VERSION:
            # Aus einer fremden Fassung lieber gar nichts übernehmen als
            # etwas halb Verstandenes. Der Preis ist ein Vollabruf.
            return
        self.konten = daten.get("konten", {})
        self.zuletzt = daten.get("zuletzt", "")

    def speichern(self) -> None:
        self.datei.parent.mkdir(parents=True, exist_ok=True)
        inhalt = {
            "version": ZUSTAND_VERSION,
            "konten": self.konten,
            "zuletzt": self.zuletzt,
        }
        vorlaeufig = self.datei.with_suffix(".neu")
        vorlaeufig.write_text(
            json.dumps(inhalt, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        vorlaeufig.replace(self.datei)

    def lauf_beendet(self) -> None:
        """Vermerkt, dass ein Abruf durchgelaufen ist."""
        from datetime import datetime

        self.zuletzt = datetime.now().astimezone().isoformat(timespec="seconds")

    # ------------------------------------------------------------ Abfragen

    def _ordner(self, konto: str, ordner: str) -> dict:
        return self.konten.setdefault(konto, {}).setdefault(ordner, {})

    def uidvalidity(self, konto: str, ordner: str) -> int | None:
        """Der beim letzten Mal gesehene UIDVALIDITY-Wert des Ordners."""
        wert = self.konten.get(konto, {}).get(ordner, {}).get("uidvalidity")
        return int(wert) if wert is not None else None

    def nachzuegler(self, konto: str, ordner: str) -> list[int]:
        """UIDs, die beim letzten Mal scheiterten und noch fehlen."""
        return sorted(self.konten.get(konto, {}).get(ordner, {}).get("nachholen", []))

    # ---------------------------------------------------------- Festhalten

    def ordner_gesehen(self, konto: str, ordner: str, uidvalidity: int) -> bool:
        """Hält den UIDVALIDITY-Wert fest.

        Gibt zurück, ob der Ordner vollständig neu gelesen werden muss –
        also ob der Server seine UIDs zwischenzeitlich neu vergeben hat.
        """
        vorher = self.uidvalidity(konto, ordner)
        self._ordner(konto, ordner)["uidvalidity"] = int(uidvalidity)
        neu_lesen = vorher is not None and vorher != int(uidvalidity)
        if neu_lesen:
            # Die alten Nachzügler zeigen auf Mails, die es unter dieser
            # Nummer nicht mehr gibt. Sie anzufordern brächte nichts.
            self._ordner(konto, ordner).pop("nachholen", None)
        return neu_lesen

    def vormerken(self, konto: str, ordner: str, uid: int) -> None:
        """Merkt eine UID vor, die beim nächsten Lauf noch einmal drankommt."""
        eintrag = self._ordner(konto, ordner)
        offen = set(eintrag.get("nachholen", []))
        if len(offen) >= HOECHSTZAHL_NACHZUEGLER:
            return
        offen.add(int(uid))
        eintrag["nachholen"] = sorted(offen)

    def erledigt(self, konto: str, ordner: str, uid: int) -> None:
        """Streicht eine vorgemerkte UID – sie ist jetzt im Archiv."""
        eintrag = self.konten.get(konto, {}).get(ordner)
        if not eintrag or "nachholen" not in eintrag:
            return
        offen = [u for u in eintrag["nachholen"] if u != int(uid)]
        if offen:
            eintrag["nachholen"] = offen
        else:
            del eintrag["nachholen"]

    def konto_vergessen(self, konto: str) -> None:
        """Wirft alles zu einem Konto weg – der nächste Lauf holt alles."""
        self.konten.pop(konto, None)
