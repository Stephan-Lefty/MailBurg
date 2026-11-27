"""Was fehlt – und ein Weg, es ohne Terminal zu bekommen.

**»Hier ist ein Befehl, tippen Sie ihn ins Terminal« ist keine
Lösung.** Für jemanden, der MailBurg auf einem fertigen System
vorfindet, ist es die Stelle, an der er aufhört. Stephans Vorgabe vom
2026-11-25, nachdem er auf einem frischen GuideOS nacheinander
PySide6, tesseract und die Sprachdaten von Hand nachinstalliert hatte:

    Egal wo man MailBurg installiert, wir müssen dem User immer die
    Chance geben, dass er per Klick die Pakete nachinstallieren kann,
    die noch benötigt werden! Und dann ein erledigt kommt, damit er
    die Einrichtung weiter vornehmen kann.

Dieses Modul beantwortet drei Fragen, und zwar getrennt voneinander:
*Was fehlt?* – *Wie hieße das hier?* – *Wie bekommt man es?* Die
Oberfläche setzt daraus einen Dialog zusammen; die Kommandozeile
nennt denselben Befehl zum Abtippen.

**Vier Festlegungen, die nicht ohne ihren Grund aufgemacht werden
sollten:**

*Der Befehl wird gezeigt, bevor er läuft.* Ein Programm, das
ungefragt Pakete auf einem fremden Rechner installiert, hat sein
Vertrauen verspielt, auch wenn es das Richtige tut. Wer den Knopf
drückt, muss vorher lesen können, was passiert.

*Ein sichtbares Terminal, nicht ``pkexec``.* Der erste Entwurf nahm
PolicyKit: ein grafischer Passwortdialog, und dahinter läuft etwas,
das niemand sieht. Stephans Einwand vom 2026-11-25 wiegt schwerer –
im Terminal sieht der Anwender, *was* installiert wird, und wenn
etwas schiefgeht, steht die Ursache da, statt in einem Rückgabewert
zu verschwinden. Dass gleich ein Passwort verlangt wird, steht
vorher im Dialog; sonst wirkt die Abfrage wie ein Übergriff.

*Niemals von selbst.* Auch nicht »beim ersten Start einmal«. Der
Anwender drückt den Knopf, oder es passiert nichts – und er kann
stattdessen abbrechen.

*Was sich nicht automatisch machen lässt, wird gesagt statt
verschwiegen.* Auf einer unbekannten Distribution, in einem Flatpak
oder ohne PolicyKit gibt es keinen Knopf – dann bleibt der Befehl zum
Abtippen, und daneben steht, warum.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Baustein:
    """Etwas, das MailBurg braucht und nicht selbst mitbringt.

    ``pakete`` ordnet der Paketverwaltung die Namen zu – dieselbe
    Sache heißt bei Debian anders als bei Arch.
    """

    name: str
    """Wie es im Fenster heißt – kein Paketname, sondern die Sache."""

    wofuer: str
    """Was ohne diesen Baustein nicht geht. Ein Satz, kein Fachjargon."""

    pruefen: str
    """Das Programm oder Modul, an dem sich das Vorhandensein zeigt."""

    art: str = "programm"
    """Wie geprüft wird.

    ``programm`` sucht im Suchpfad, ``modul`` versucht einen Import,
    ``sprachdaten`` fragt tesseract nach seinen Sprachen, ``pdftext``
    fragt ``extract/pdf.py``, ob überhaupt ein Weg zum Text da ist.

    **Die dritte Art gibt es, weil die zweite nicht reichte.** Am
    2026-11-25 entfernte Stephan zum Prüfen ``tesseract-ocr-deu`` –
    und MailBurg bot nichts zum Nachrüsten an. ``tesseract`` war ja
    noch da. Gleichzeitig sagte ``ocr.bereit()`` »nicht bereit«: Zwei
    Prüfungen, die dasselbe beurteilen sollen und sich widersprechen,
    und das ist in diesem Projekt die häufigste Fehlerklasse
    überhaupt.

    **Die vierte aus demselben Grund, zwei Tage später.** Der
    Baustein »PDF lesen« suchte nach ``pypdf``. Zum Text einer PDF
    gibt es aber zwei Wege, und ``pdftotext`` aus poppler ist der
    bevorzugte – ``extract/pdf.py`` fragt ihn zuerst. Auf einem
    Rechner mit poppler und ohne pypdf meldete MailBurg deshalb »Ohne
    das ist der Text in PDF-Anhängen nicht durchsuchbar«, während er
    es tatsächlich war. Nachgemessen am 2026-11-27, angestoßen durch
    die Frage des GuideOS-Admins, wofür die *Recommends* eigentlich
    da seien.
    """

    pakete: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def da(self) -> bool:
        if self.art == "modul":
            import importlib.util

            try:
                return importlib.util.find_spec(self.pruefen) is not None
            except (ImportError, ValueError):
                return False
        if self.art == "sprachdaten":
            from mailburg.extract import ocr

            # Ohne tesseract gibt es nichts zu fragen – dann meldet
            # der Baustein darüber, und dieser hier schweigt.
            if not shutil.which("tesseract"):
                return True
            return bool(ocr.sprachwahl())
        if self.art == "pdftext":
            from mailburg.extract import pdf

            # **Dieselbe Quelle wie der Rest des Programms.** Es gibt
            # zwei Wege zum Text einer PDF – pdftotext aus poppler und
            # pypdf –, und einer genügt. Wer hier nach einem von
            # beiden sucht, meldet etwas als fehlend, das nicht fehlt.
            return pdf.verfuegbar() is not None
        return shutil.which(self.pruefen) is not None


#: **Nur was sich nachrüsten lässt.** PySide6 steht bewusst nicht
#: hier: Ohne Qt gibt es kein Fenster, in dem ein Knopf stehen könnte.
#: Dafür ist seit dem 2026-11-25 das ``Depends`` des Debian-Pakets da.
BAUSTEINE = (
    Baustein(
        name="Texterkennung",
        wofuer="Ohne sie bleiben eingescannte PDF unauffindbar – für "
               "die Suche sind sie ein weißes Blatt.",
        pruefen="tesseract",
        pakete={
            "apt": ("tesseract-ocr", "tesseract-ocr-deu"),
            "pacman": ("tesseract", "tesseract-data-deu"),
            "dnf": ("tesseract", "tesseract-langpack-deu"),
            "zypper": ("tesseract-ocr", "tesseract-ocr-traineddata-german"),
        },
    ),
    Baustein(
        name="Deutsche Sprachdaten",
        wofuer="Tesseract liest sonst mit dem englischen Modell – aus "
               "deutschem Text wird dabei Buchstabensalat mit "
               "zerstörten Umlauten. Lieber gar nicht erkennen als "
               "falsch.",
        pruefen="deu",
        art="sprachdaten",
        pakete={
            "apt": ("tesseract-ocr-deu",),
            "pacman": ("tesseract-data-deu",),
            "dnf": ("tesseract-langpack-deu",),
            "zypper": ("tesseract-ocr-traineddata-german",),
        },
    ),
    Baustein(
        name="Seitenbilder aus PDF",
        wofuer="Die Texterkennung braucht aus jeder Seite erst ein Bild.",
        pruefen="pdftoppm",
        pakete={
            "apt": ("poppler-utils",),
            "pacman": ("poppler",),
            "dnf": ("poppler-utils",),
            "zypper": ("poppler-tools",),
        },
    ),
    Baustein(
        name="PDF lesen",
        wofuer="Ohne das ist der Text in PDF-Anhängen nicht durchsuchbar – "
               "auch nicht in solchen, die gar nicht eingescannt sind.",
        pruefen="pdftotext",
        art="pdftext",
        # **Angeboten wird poppler, nicht pypdf**, obwohl beide den
        # Zweck erfüllen: poppler ist schneller, kommt mit
        # fehlerhaften Dateien besser zurecht, und dasselbe Paket
        # liefert die Seitenbilder für die Texterkennung gleich mit.
        # Wer beide Bausteine vermisst, bekommt deshalb einen Befehl
        # statt zweier – ``paketnamen()`` wirft die Dublette weg.
        pakete={
            "apt": ("poppler-utils",),
            "pacman": ("poppler",),
            "dnf": ("poppler-utils",),
            "zypper": ("poppler-tools",),
        },
    ),
    Baustein(
        name="Verschlüsselung",
        wofuer="Ohne sie lassen sich verschlüsselte Archive nicht öffnen "
               "und der Tresor nicht benutzen.",
        pruefen="cryptography",
        art="modul",
        pakete={
            "apt": ("python3-cryptography",),
            "pacman": ("python-cryptography",),
            "dnf": ("python3-cryptography",),
            "zypper": ("python3-cryptography",),
        },
    ),
)


def fehlendes() -> list[Baustein]:
    """Was auf diesem Rechner gerade nicht da ist."""
    from mailburg.core import werkzeuge

    # Erst den mitgelieferten Ordner einhängen: In der gepackten
    # Fassung liegen die Werkzeuge daneben und nicht im Suchpfad.
    werkzeuge.bereitstellen()
    return [b for b in BAUSTEINE if not b.da()]


def paketverwaltung() -> str | None:
    """Welche Paketverwaltung hier zuständig ist – oder ``None``.

    **Über das vorhandene Programm, nicht über den Namen der
    Distribution.** ``/etc/os-release`` kennt Dutzende Ableger, und
    die nächste heißt wieder anders; ``apt-get`` heißt überall
    ``apt-get``.
    """
    if sys.platform != "linux":
        return None
    for programm, name in (("apt-get", "apt"), ("pacman", "pacman"),
                           ("dnf", "dnf"), ("zypper", "zypper")):
        if shutil.which(programm):
            return name
    return None


#: Warum es hier keinen Knopf gibt. Die Gründe stehen als Text und
#: nicht als Fehlernummer: Sie landen unverändert im Fenster.
def warum_nicht() -> str:
    """Leer, wenn das Nachrüsten möglich ist – sonst der Grund."""
    if sys.platform == "win32":
        return (
            "Unter Windows bringt die fertige MailBurg.exe alles mit. "
            "Fehlt dort etwas, ist die Datei unvollständig "
            "heruntergeladen worden."
        )
    if sys.platform != "linux":
        return "Das automatische Nachrüsten gibt es nur unter Linux."
    if _im_flatpak():
        return (
            "MailBurg läuft hier in einem Flatpak und kann keine "
            "Systempakete installieren. Die fehlenden Teile gehören "
            "in das Flatpak selbst."
        )
    if paketverwaltung() is None:
        return (
            "Die Paketverwaltung dieses Systems ist MailBurg nicht "
            "bekannt. Bekannt sind apt, pacman, dnf und zypper."
        )
    if not shutil.which("pkexec"):
        return (
            "Für das Nachrüsten braucht MailBurg pkexec (PolicyKit). "
            "Es fragt nach dem Verwalterpasswort – ohne das darf kein "
            "Programm etwas installieren."
        )
    return ""


def _im_flatpak() -> bool:
    return bool(os.environ.get("FLATPAK_ID")) or os.path.exists("/.flatpak-info")


def paketnamen(fehlende) -> list[str]:
    """Die Paketnamen für diese Paketverwaltung, ohne Dubletten.

    Mehrere Bausteine können auf dasselbe Paket zeigen; zweimal
    dasselbe zu installieren wäre nicht falsch, sähe aber nach einem
    Fehler aus.
    """
    verwaltung = paketverwaltung()
    if verwaltung is None:
        return []
    namen: list[str] = []
    for baustein in fehlende:
        for paket in baustein.pakete.get(verwaltung, ()):
            if paket not in namen:
                namen.append(paket)
    return namen


def befehl(fehlende) -> list[str]:
    """Der Befehl, der die fehlenden Pakete holt – als Liste.

    **Als Liste und nicht als Zeichenkette**, damit nichts durch eine
    Shell läuft. Paketnamen stehen zwar fest in diesem Modul, aber ein
    Befehl, der sich zusammenbauen lässt, wird irgendwann aus einer
    Datei zusammengebaut.
    """
    namen = paketnamen(fehlende)
    if not namen:
        return []
    verwaltung = paketverwaltung()
    if verwaltung == "apt":
        return ["apt-get", "install", "-y", *namen]
    if verwaltung == "pacman":
        return ["pacman", "-S", "--noconfirm", *namen]
    if verwaltung == "dnf":
        return ["dnf", "install", "-y", *namen]
    if verwaltung == "zypper":
        return ["zypper", "--non-interactive", "install", *namen]
    return []


def zum_abtippen(fehlende) -> str:
    """Derselbe Befehl, wie ihn ein Mensch eintippen würde.

    **Ohne Satzzeichen dahinter, und auf einer eigenen Zeile.** Am
    2026-11-25 stand in einer Meldung »… tesseract-ocr-deu, unter
    Arch: …«; das Komma wurde mitkopiert, und die Installation
    scheiterte an einem Paket namens ``tesseract-ocr-deu,``. Wenn
    derjenige, der das Programm gebaut hat, beim Kopieren danebengreift,
    ist es eine Falle und keine Unachtsamkeit.
    """
    teile = befehl(fehlende)
    return f"sudo {' '.join(teile)}" if teile else ""


#: Terminalprogramme und wie man ihnen einen Befehl mitgibt.
#:
#: **``x-terminal-emulator`` zuerst.** Auf Debian und allem, was
#: davon abstammt – also auch GuideOS –, zeigt dieser Name über das
#: Alternativen-System auf das Terminal, das der Anwender wirklich
#: benutzt. Die übrigen sind der Rückfall für Systeme ohne dieses
#: Verfahren.
TERMINALS = (
    ("x-terminal-emulator", "-e"),
    ("gnome-terminal", "--"),
    ("konsole", "-e"),
    ("xfce4-terminal", "-x"),
    ("mate-terminal", "-x"),
    ("alacritty", "-e"),
    ("kitty", "-e"),
    ("foot", "-e"),
    ("xterm", "-e"),
)


def terminal() -> tuple[str, str] | None:
    """Das Terminalprogramm dieses Systems, mit seinem Schalter."""
    for name, schalter in TERMINALS:
        pfad = shutil.which(name)
        if pfad:
            return pfad, schalter
    return None


#: Wie die Terminals nach einer Fensterposition fragen lassen. Der
#: Reihe nach probiert; genommen wird der erste, den die eigene Hilfe
#: des Programms nennt.
GEOMETRIESCHALTER = ("--geometry", "--qwindowgeometry", "-geometry")


def geometrieschalter(programm: str) -> str | None:
    """Fragt das Terminal selbst, wie es nach einer Position fragt.

    **Nachgesehen statt erinnert, und hier zwingend.** Dieselbe Sache
    heißt bei jedem Terminal anders: ``gnome-terminal`` kennt
    ``--geometry``, ``konsole`` nur das Qt-eigene
    ``--qwindowgeometry``, ``xterm`` schreibt es mit einem Strich.
    Und hinter ``x-terminal-emulator`` kann jedes davon stecken – der
    Name sagt nichts darüber, worauf die Alternative zeigt.

    Ein geratener Schalter wäre hier teuer: Ein Terminal, das sein
    erstes Argument nicht versteht, startet gar nicht, und dann steht
    der Anwender vor einem Dialog, der auf ein Fenster wartet, das
    nie aufgeht.

    Gibt ``None`` zurück, wenn sich nichts finden lässt – dann geht
    das Terminal eben dorthin, wohin der Fenstermanager es legt.
    """
    try:
        lauf = subprocess.run(
            [programm, "--help"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # xterm kennt kein --help und listet seine Optionen daraufhin auf
    # der Fehlerausgabe auf. Beides zählt.
    hilfe = f"{lauf.stdout}\n{lauf.stderr}"
    for schalter in GEOMETRIESCHALTER:
        if schalter in hilfe:
            return schalter
    return None


def _position_angeben(schalter: str, position) -> list[str]:
    """Die Positionsangabe, wie X11 sie seit jeher schreibt.

    **Nur die Position, keine Größe.** ``+X+Y`` ist für sich
    genommen eine gültige Geometrieangabe – und das ist kein Geiz,
    sondern der Ausweg aus einer Falle: In ``80x24+0+0`` zählen die
    ersten beiden Zahlen bei ``gnome-terminal`` Zeichen und Zeilen,
    bei allem, was über Qt läuft, dagegen Bildpunkte. Wer eine Größe
    mitgibt, trifft in einem der beiden Fälle daneben.
    """
    x, y = position
    # **Das Pluszeichen steht immer davor, auch vor einer negativen
    # Zahl.** In dieser Schreibweise misst »-10« vom *rechten* Rand;
    # zehn Punkte links außerhalb heißen »+-10«. Ein ``{:+d}`` – der
    # naheliegende Griff – schriebe genau das Falsche.
    return [f"{schalter}=+{x}+{y}"]


def im_terminal(fehlende, fertigmarke, position=None) -> subprocess.Popen | None:
    """Öffnet ein Terminal, das die Pakete holt und sich dann schließt.

    ``fertigmarke`` ist ein Pfad, in den das Terminal am Ende den
    Rückgabewert schreibt. **Daran und nicht am Prozess erkennt
    MailBurg, dass es durch ist** – und das ist kein Umweg, sondern
    nötig: ``gnome-terminal`` kehrt sofort zurück, weil es die Arbeit
    an einen laufenden Server weiterreicht. Wer auf diesen Prozess
    wartet, wartet nicht. Eine Datei, die am Ende entsteht, verhält
    sich bei jedem Terminal gleich.

    ``position`` ist ein Paar aus Bildpunkten, an das das Fenster
    gelegt werden soll. **Es ist ein Wunsch, keine Zusage.** Unter
    Wayland darf ein Fenster seine Lage nicht selbst bestimmen; dort
    verfällt die Angabe stillschweigend, und das ist in Ordnung – die
    Anzeige im Dialog verlässt sich nicht darauf.

    Das Terminal **schließt sich von selbst**, sobald es fertig ist;
    Stephans Vorgabe vom 2026-11-25. Was dabei herauskam, sagt danach
    MailBurg – im selben Fenster, in dem der Anwender ohnehin steht.
    """
    teile = befehl(fehlende)
    gefunden = terminal()
    if not teile or gefunden is None:
        return None
    programm, schalter = gefunden

    lage: list[str] = []
    if position is not None:
        gefragt = geometrieschalter(programm)
        if gefragt:
            lage = _position_angeben(gefragt, position)

    # **``sudo`` und nicht ``pkexec``:** Im Terminal gibt es eine
    # Passwortabfrage, die jeder kennt. Der Dialog sagt vorher, dass
    # sie kommt.
    innen = (
        "sudo " + " ".join(teile)
        + f"; echo $? > {_geschuetzt(str(fertigmarke))}"
    )
    try:
        return subprocess.Popen(
            [programm, *lage, schalter, "bash", "-c", innen]
        )
    except OSError:
        return None


def _geschuetzt(pfad: str) -> str:
    """Ein Pfad, wie ihn eine Shell unfallfrei liest."""
    import shlex

    return shlex.quote(pfad)


def ergebnis(fehlende) -> tuple[bool, str]:
    """Was nach dem Lauf herauskam – am Rechner nachgesehen.

    **Nicht am Rückgabewert.** ``apt-get`` meldet auch dann Erfolg,
    wenn es nichts zu tun fand, und ein Anwender kann die
    Passwortabfrage weggeklickt haben. Was zählt, ist allein, ob der
    Baustein jetzt da ist.
    """
    offen = [b for b in fehlende if not b.da()]
    if not offen:
        return True, "Erledigt – alles Nötige ist jetzt da."
    fehlen = ", ".join(b.name for b in offen)
    return False, (
        f"Es fehlt weiterhin: {fehlen}.\n\n"
        f"Entweder wurde die Passwortabfrage abgebrochen, oder die "
        f"Pakete ließen sich nicht holen. Von Hand geht es so:\n\n"
        f"{zum_abtippen(offen)}"
    )
