# Lizenztexte der mitgelieferten Programme

Die Windows-Fassung von MailBurg bringt zwei fremde Programme mit:
**poppler** (GPL-2.0-or-later) macht aus PDF-Seiten Bilder, **tesseract**
(Apache-2.0) liest den Text daraus. Beide werden aufgerufen, nicht
eingebunden, und unverändert weitergegeben.

Diese Texte liegen hier im Repo und nicht im Bau-Skript, aus einem
Grund, der am 2026-08-28 sichtbar wurde: Der erste Versuch lud sie beim
Bauen von `gnu.org` und `apache.org`. Der Bau brach ab, weil `gnu.org`
nicht antwortete — an einem Lizenztext, der sich seit 1991 nicht
geändert hat.

Ein Bau, der an der Erreichbarkeit fremder Websites hängt, ist keiner.
