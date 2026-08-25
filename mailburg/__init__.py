"""MailBurg – plattformübergreifendes Archiv für E-Mail.

Archiviert beliebig viele Postfächer an einen Ort, den der Benutzer selbst
bestimmt, und durchsucht Mailtexte wie Anhänge im Volltext.
"""

from __future__ import annotations

__version__ = "0.1.0"

APP_ID = "de.stephanlefty.MailBurg"
APP_NAME = "MailBurg"

# Version des Archivformats auf der Platte. Wird in archive.json geschrieben
# und beim Öffnen geprüft, damit eine ältere Programmfassung ein neueres
# Archiv nicht halb versteht und dabei beschädigt.
FORMAT_VERSION = 1
