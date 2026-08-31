"""Die Server Edition – MailBurg als Dienst im Netz.

**Dieses Verzeichnis darf nichts aus ``mailburg/ui`` anfassen** und
umgekehrt. Beide kennen den Kern, sonst nichts voneinander;
``tests/test_schichten.py`` hält das fest. Ein Dienst, der ein Modul
namens ``ui`` einlädt, holt sich früher oder später eine
Qt-Abhängigkeit auf eine Maschine ohne Bildschirm.

Was der Server können muss und in welcher Reihenfolge er entsteht,
steht in ``docs/server.md``.
"""

from __future__ import annotations
