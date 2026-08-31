"""Die wenigen Farben, die MailBurg selbst festlegt.

Fast alles überlässt die Oberfläche dem System: Auswahl, Hintergrund,
Schrift, Akzent. Wer die Systemfarben überschreibt, sieht auf jedem
fremden Desktop falsch aus und bricht Hochkontrast-Themen.

Zwei Farben lassen sich aber nicht ableiten, weil sie eine *Bedeutung*
tragen und keine Rolle: »hat geklappt« und »ist schiefgegangen«. Dafür
gibt es in keiner Qt-Palette einen Eintrag.

Und genau die müssen zum Thema passen. Ein festes ``#c62828`` erreicht
auf weißem Grund ein Kontrastverhältnis von 5,6 – auf dunklem nur 2,7.
Verlangt sind 4,5 (WCAG AA). Ausgerechnet »Anmeldung gescheitert« wäre
im dunklen Thema also die am schlechtesten lesbare Zeile im Fenster.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

#: Für helle Themen. Nachgerechnet auf Weiß: 5,1 und 5,6.
_HELL = {"gut": "#2e7d32", "schlecht": "#c62828"}

#: Für dunkle. Nachgerechnet auf dem üblichen Breeze-Dunkel (#232629):
#: 8,0 und 7,3. Dieselben Farbtöne, nur aufgehellt – Grün bleibt Grün.
_DUNKEL = {"gut": "#81c784", "schlecht": "#ef9a9a"}

#: Verweise. Qts Standardblau (#0000ff) hat auf dunklem Grund ein
#: Kontrastverhältnis von 2,4 – ein Link, den man nur findet, wenn man
#: weiß, dass er da ist. Auf hellem Grund ist dasselbe Blau in Ordnung.
_LINK_HELL = "#0645ad"
_LINK_DUNKEL = "#6cb6ff"


def link() -> str:
    """Farbe für Verweise, passend zum Thema."""
    return _LINK_DUNKEL if dunkles_thema() else _LINK_HELL


def verweis(adresse: str, beschriftung: str) -> str:
    """Ein Verweis, der auf hellem wie dunklem Grund lesbar ist."""
    return f"<a href='{adresse}' style='color: {link()}'>{beschriftung}</a>"


def dunkles_thema() -> bool:
    """Ob die Oberfläche gerade dunkel eingestellt ist.

    Gefragt wird die Palette, nicht die Arbeitsumgebung: Das Thema kann
    zur Laufzeit wechseln, und es gibt mehr Arbeitsumgebungen, als man
    einzeln abfragen möchte.
    """
    anwendung = QApplication.instance()
    if anwendung is None:
        return False
    grund = anwendung.palette().color(QPalette.Window)
    # value() ist der Helligkeitsanteil in HSV, von 0 bis 255.
    return grund.value() < 128


def kante() -> str:
    """Die Farbe für Trennlinien zwischen den Bereichen.

    **Das dunkle Thema hat kein Farbproblem, es hat ein Kantenproblem.**
    Nachgemessen am 2026-08-27: Zwischen ``Window`` und ``Base`` – also
    zwischen Fensterhintergrund und Inhaltsbereich – liegt ein
    Kontrastverhältnis von **1,15**. Das liest kein Auge als Grenze, und
    zwar in keinem Thema. Im hellen fällt es nicht auf, weil Gewohnheit
    und Bildschirmrand helfen; auf einem 14-Zoll-Gerät im Dunkeln fehlt
    beides, und Baum, Trefferliste und Vorschau verschwimmen zu einer
    Fläche.

    Die Lösung ist deshalb nicht, eigene Farben zu setzen – das bräche
    Hochkontrast-Themen und träfe ausgerechnet die Anwender, für die
    solche Themen gemacht sind. Die Lösung ist, die Linie zu zeichnen,
    die es ohnehin geben sollte. ``Mid`` ist genau dafür da: eine Farbe
    zwischen Hintergrund und Rahmen, die jedes Thema mitliefert und
    jedes Hochkontrast-Thema kräftig setzt.
    """
    anwendung = QApplication.instance()
    if anwendung is None:
        return "#808080"
    return anwendung.palette().color(QPalette.Mid).name()


def bereichsrahmen() -> str:
    """Stylesheet, das die Bereiche voneinander abgrenzt.

    Bewusst knapp: nur der Rahmen, keine Hintergründe, keine Schrift.
    Alles andere bleibt beim Thema des Systems.
    """
    strich = kante()
    return (
        # Die Inhaltsbereiche: Baum, Trefferliste, Vorschau, Textfelder.
        f"QTreeView, QTableView, QListView, QTextBrowser, QTextEdit, "
        f"QPlainTextEdit, QLineEdit, QComboBox, QSpinBox "
        f"{{ border: 1px solid {strich}; }}\n"
        # Gruppen in der Einrichtung. Qt zeichnet sie je nach Thema mit
        # einem Rahmen, der im Dunkeln nicht zu sehen ist - und gerade
        # dort steht die Frage, wofür das Archiv sein soll.
        f"QGroupBox {{ border: 1px solid {strich}; border-radius: 3px; "
        f"margin-top: 0.7em; padding-top: 0.4em; }}\n"
        f"QGroupBox::title {{ subcontrol-origin: margin; left: 0.6em; "
        f"padding: 0 0.3em; }}\n"
        # Der waagerechte Strich, mit dem der Assistent Kopf und Inhalt
        # trennt.
        f"QFrame[frameShape=\"4\"], QFrame[frameShape=\"5\"] "
        f"{{ color: {strich}; }}"
    )


def platzhalter_aufhellen(anwendung) -> None:
    """Macht Platzhaltertexte im dunklen Thema lesbar.

    Ein Platzhalter – »Suchen Sie nach …« im leeren Feld – ist absichtlich
    gedämpft: Er soll als Hinweis erkennbar sein und nicht als Inhalt.
    Qt setzt ihn dafür auf die Textfarbe mit halber Deckkraft.

    **Auf hellem Grund geht diese Rechnung auf, auf dunklem nicht.**
    Schwarz auf Weiß mit 50 % ergibt ein mittleres Grau, das gut zu lesen
    bleibt. Hellgrau auf Fast-Schwarz mit 50 % ergibt ein dunkles Grau,
    das im selben Dunkel verschwindet – der Hinweis, der beim ersten
    Öffnen erklärt, wofür das Feld da ist, ist dann unsichtbar.

    Deshalb hier eine höhere Deckkraft, und zwar nur im dunklen Thema.
    Abgeleitet bleibt sie aus der Textfarbe des Systems: Ein fester
    Grauton säße bei einem Hochkontrast-Thema falsch.
    """
    if not dunkles_thema():
        return
    palette = anwendung.palette()
    farbe = QColor(palette.color(QPalette.Text))
    # 70 statt 50 Prozent. Gedämpft genug, um Hinweis zu bleiben, hell
    # genug, um gelesen zu werden.
    farbe.setAlphaF(0.70)
    palette.setColor(QPalette.PlaceholderText, farbe)
    anwendung.setPalette(palette)


def _waehlen(rolle: str) -> str:
    return (_DUNKEL if dunkles_thema() else _HELL)[rolle]


def gut() -> str:
    """Farbe für »hat geklappt«."""
    return _waehlen("gut")


def schlecht() -> str:
    """Farbe für »ist schiefgegangen«."""
    return _waehlen("schlecht")


def stil(gelungen: bool | None) -> str:
    """Fertiges Stylesheet für eine Zustandsanzeige.

    ``None`` heißt »noch nichts zu sagen« und gibt die Schrift wieder
    frei – dann gilt wieder die Farbe des Themas.
    """
    if gelungen is None:
        return ""
    return f"color: {gut() if gelungen else schlecht()}"


def auswahlfelder_verbreitern(anwendung) -> None:
    """Sorgt dafür, dass in Auswahllisten alles zu lesen ist.

    Qt macht eine ``QComboBox`` standardmäßig so breit, wie das Layout
    ihr Platz gibt, und klappt die Liste in derselben Breite auf. Steht
    dort »die letzten 2 Stände« neben einem Feld, das für »alle 15
    Minuten« bemessen ist, wird der längere Eintrag abgeschnitten – und
    zwar genau dann, wenn man ihn lesen will: beim Aufklappen.

    Am 2026-08-31 von Stephan gemeldet, am Fenster »Was von selbst
    laufen soll«. Betroffen waren alle vierzehn Auswahlfelder des
    Programms; keines hatte eine eigene Einstellung dafür.

    **Hier zentral und nicht vierzehnmal einzeln.** Sonst fehlt sie beim
    fünfzehnten, das später dazukommt – und niemand merkt es, weil das
    Feld ja aussieht wie immer, nur eben zu schmal.

    ``AdjustToContents`` bemisst die Box nach ihrem längsten Eintrag.
    Das macht einzelne Felder breiter als nötig; der Tausch lohnt sich:
    Ein Feld, dessen Inhalt man nicht lesen kann, ist unbrauchbar,
    eines, das zu viel Platz nimmt, nur unschön.
    Seit dem 2026-08-31 richtet derselbe Filter auch Dialoge her, die
    kleiner sind als ihr Inhalt: Dort brach Text unten ab, mitten im
    Satz. Auch das war überall eine geratene Zahl - und eine geratene
    Zahl sitzt falsch, sobald jemand die Schriftgröße ändert, und das
    lässt sich in MailBurg einstellen.
    """
    from PySide6.QtWidgets import QComboBox

    from PySide6.QtWidgets import QDialog, QLabel, QLayout, QScrollArea

    class _Anpasser(QObject):
        def eventFilter(self, gegenstand, ereignis):
            if ereignis.type() != QEvent.Show:
                return False

            # Beim Erzeugen greift es noch nicht - da hat die Box weder
            # Eintraege noch ein Elternteil. Beim ersten Anzeigen schon.
            if (
                isinstance(gegenstand, QComboBox)
                and gegenstand.sizeAdjustPolicy() != QComboBox.AdjustToContents
            ):
                gegenstand.setSizeAdjustPolicy(QComboBox.AdjustToContents)
                gegenstand.adjustSize()
                self._liste_weiten(gegenstand)

            elif isinstance(gegenstand, QLabel) and gegenstand.wordWrap():
                self._umbruch_hoehe(gegenstand)

            elif isinstance(gegenstand, QDialog):
                self._dialog_weiten(gegenstand)
            return False

        @staticmethod
        def _liste_weiten(box) -> None:
            """Gibt der aufgeklappten Liste die Breite ihrer Einträge.

            **Die Liste ist ein eigenes Fenster.** Sie erbt die Breite
            der Box nicht und bleibt bei dem, was Qt einmal ausgerechnet
            hat – bei einer Vorgabeschrift. Wer die Schrift vergrößert,
            bekommt größere Buchstaben in einer gleich schmalen Liste,
            und die Einträge werden abgeschnitten.

            Am 2026-08-31 von Stephan gemeldet: »Die Menüpunkte bei
            Abstand sind nicht lesbar.« Nachgemessen: Die Box wuchs von
            117 auf 223 px mit, die Liste blieb bei 120.
            """
            liste = box.view()
            if liste is None:
                return
            gebraucht = liste.sizeHintForColumn(0)
            # Platz für den Rollbalken, falls die Liste lang wird.
            liste.setMinimumWidth(max(box.width(), gebraucht + 24))

        @staticmethod
        def _umbruch_hoehe(schild) -> None:
            """Sagt dem Layout, dass die Höhe von der Breite abhängt.

            **Der Qt-Fallstrick bei umbrechendem Text.** Ein ``QLabel``
            mit ``wordWrap`` weiß selbst, wie hoch es bei einer
            gegebenen Breite würde – über ``heightForWidth``. Das Layout
            fragt aber nur danach, wenn die Größenrichtlinie es
            ankündigt, und in der Vorgabe tut sie das nicht.

            Die Folge: Steht daneben etwas, das den Platz beansprucht,
            wird der Text zusammengedrückt und bricht unten ab. Bei
            gewöhnlicher Schriftgröße fällt es kaum auf – bei 16 pt
            fehlten auf der Postfachseite des Assistenten hundert Pixel,
            also mehrere Zeilen.

            Ausgerechnet bei jemandem, der die Schrift vergrößert hat,
            weil er sonst schlecht liest.
            """
            richtlinie = schild.sizePolicy()
            if richtlinie.hasHeightForWidth():
                return
            richtlinie.setHeightForWidth(True)
            schild.setSizePolicy(richtlinie)

        @staticmethod
        def _dialog_weiten(dialog) -> None:
            """Macht einen Dialog so groß, wie sein Inhalt es braucht.

            **Ein Rollbereich bleibt unangetastet.** Der ist genau dafür
            da, kleiner zu sein als sein Inhalt; ihn aufzublasen ergäbe
            ein Fenster über den ganzen Bildschirm.
            """
            if dialog.findChildren(QScrollArea):
                return

            # **Qt soll es erzwingen, nicht wir es einmal einstellen.**
            # Ein ``resize`` beim Öffnen hält nur bis zur nächsten
            # Änderung: Wer danach die Schrift vergrößert, hat wieder
            # ein Fenster, das zu klein ist für seinen Inhalt – und
            # genau dann braucht er es am wenigsten.
            #
            # ``SetMinimumSize`` bindet die Mindestgröße dauerhaft an
            # das Layout. Wächst der Text, wächst das Fenster mit; der
            # Anwender kann es nicht kleiner ziehen, als lesbar ist.
            aufbau = dialog.layout()
            if aufbau is not None:
                aufbau.setSizeConstraint(QLayout.SetMinimumSize)

            gebraucht = dialog.sizeHint()
            dialog.resize(
                max(dialog.width(), gebraucht.width()),
                max(dialog.height(), gebraucht.height()),
            )

    # Am Anwendungsobjekt festhalten: Ein Filter, auf den niemand mehr
    # zeigt, wird weggeraeumt - und dann sind die Felder wieder schmal.
    anwendung._auswahlanpasser = _Anpasser(anwendung)
    anwendung.installEventFilter(anwendung._auswahlanpasser)
