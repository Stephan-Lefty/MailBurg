"""Zehn Tests, die nichts tun – zur Messung, nicht zum Bleiben.

**Die Frage:** Bricht der Testlauf in der CI ab, weil ein bestimmter
neuer Test etwas falsch macht – oder schlicht, weil es mehr Tests
geworden sind? Beim Herunterfahren meldet Qt »shared QObject was
deleted directly« und der Prozess stirbt, nachdem alle Tests grün
gemeldet haben.

Diese zehn tun nichts, fassen nichts an und erzeugen nichts. Kracht
der Lauf mit ihnen genauso, liegt es an der Zahl und nicht am Inhalt –
und dann ist der Fehler alt und mein Commit nur der Tropfen gewesen.
"""

import unittest


class LeerlastTest(unittest.TestCase):
    pass


for _nummer in range(1, 11):
    setattr(
        LeerlastTest,
        f"test_leer_{_nummer:02d}",
        lambda self: self.assertTrue(True),
    )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
