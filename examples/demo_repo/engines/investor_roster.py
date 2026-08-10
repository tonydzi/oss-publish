# -*- coding: utf-8 -*-
"""A file that must NEVER be published, whatever the dictionary can do to it.

The test is not "does it mention someone" - almost every file in a working system does. It
is: **is third-party personal data the POINT of the file?**

Here it is. Fake the names and you have a list of nobody; keep them and you have put other
people's contact details, their funds and their verbatim replies into a public repo. There
is no substitution that leaves this file useful and safe at the same time, so it is named
in `deny_files` and refused by basename, with a reason a human can read.

The real one had 37 rows. Two are enough to show the shape - and deliberately two, because
three or more of these tuples in a row is exactly what the `people-roster` gate rule looks
for, and this kit's own tree has to stay clean of that shape.
"""

TARGETS = [
    ("Harold Pike (Northwind Ventures)", 418209934, "passed - too early, ping at Series A"),
    ("Marina Belova (Sunrise Capital)", 771204558, "wants the deck, follow up Tuesday"),
]

NEXT_TOUCH_DAYS = 14
