"""MailBurg – plattformübergreifendes Archiv für E-Mail.

Archiviert beliebig viele Postfächer an einen Ort, den der Benutzer selbst
bestimmt, und durchsucht Mailtexte wie Anhänge im Volltext.
"""

from __future__ import annotations

__version__ = "1.0.1"

APP_ID = "de.stephanlefty.MailBurg"
APP_NAME = "MailBurg"

#: Wo der Quelltext liegt. Steht hier und nicht verstreut im Programm,
#: weil die Adresse an mehreren Stellen auftaucht – in der Oberfläche, in
#: der Paketbeschreibung, in der Doku – und nirgends veralten darf.
QUELLTEXT_URL = "https://github.com/Stephan-Lefty/MailBurg"

# Version des Archivformats auf der Platte. Wird in archive.json geschrieben
# und beim Öffnen geprüft, damit eine ältere Programmfassung ein neueres
# Archiv nicht halb versteht und dabei beschädigt.
FORMAT_VERSION = 1
