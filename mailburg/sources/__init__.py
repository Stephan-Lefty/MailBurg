"""Teilpaket sources von MailBurg – woher die Mails kommen.

Hier steht die eine Stelle, an der entschieden wird, *wie* ein Postfach
abgerufen wird. Alles andere im Programm arbeitet mit einer
:class:`~mailburg.sources.base.Source` und weiß nicht, ob dahinter IMAP
steckt, JMAP oder eine Datei auf der Platte.
"""

from __future__ import annotations


def quelle_fuer(konto, passwort: str, **mehr):
    """Baut die passende Quelle zu einem Postfach.

    **Warum das nicht jeder selbst tut.** Ein Postfach wird an fünf
    Stellen abgerufen: aus dem Fenster, aus dem Zeitplan, über
    ``mailburg abrufen``, beim Prüfen einer Verbindung und beim
    Abgleich. Jede dieser Stellen erzeugte bisher eine ``ImapSource``
    von Hand – und die sechste, die später dazukäme, wüsste von JMAP
    nichts.

    Der Anwender merkte das als das Merkwürdigste, was ein Programm
    tun kann: Es funktioniert an vier Stellen und an der fünften nicht,
    ohne dass irgendwo ein Fehler steht.

    ``mehr`` geht an die gewählte Quelle weiter – etwa ``zeitgrenze``
    oder ``seit_zustand``. Was eine Quelle nicht kennt, fällt hier weg,
    statt ihr um die Ohren zu fliegen: Ein Aufrufer soll nicht wissen
    müssen, welches Protokoll gerade dahintersteckt.
    """
    if getattr(konto, "per_jmap", False):
        from mailburg.sources.jmap import JmapSource

        erlaubt = {"marke", "seit_zustand", "zeitgrenze"}
        return JmapSource(konto, passwort,
                          **{k: v for k, v in mehr.items() if k in erlaubt})

    from mailburg.sources.imap import ImapSource

    erlaubt = {"zeitgrenze", "zustand", "hoechststand", "ordner",
               "voll", "verbindung"}
    return ImapSource(konto, passwort,
                      **{k: v for k, v in mehr.items() if k in erlaubt})
