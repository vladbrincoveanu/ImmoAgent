import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from Domain.listing import Listing
from Domain.sources import Source
from Application.coop_format import format_coop_message


def _coop(**kw):
    return Listing(url=kw.pop('url', 'https://www.oevw.at/x'),
                   source=Source.GENOSSENSCHAFT, is_genossenschaft=True,
                   bautraeger=kw.pop('bautraeger', 'ÖVW'), **kw)


class TestFormatCoopMessage(unittest.TestCase):
    def test_html_bold_and_ppm2(self):
        msg = format_coop_message(_coop(bezirk='1100', rooms=3, area_m2=70, price_total=350))
        self.assertIn('<b>ÖVW</b>', msg)
        self.assertIn('5.0€/m²', msg)          # 350/70
        self.assertIn('#1100', msg)
        self.assertIn('https://www.oevw.at/x', msg)

    def test_escapes_html_in_free_text(self):
        msg = format_coop_message(_coop(bautraeger='A & B <Bau>'))
        self.assertIn('A &amp; B', msg)
        self.assertNotIn('<Bau>', msg)

    def test_missing_fields_use_placeholders(self):
        msg = format_coop_message(_coop(bautraeger=None, bezirk=None))
        self.assertIn('Genossenschaft', msg)
        self.assertIn('? Zi', msg)


if __name__ == '__main__':
    unittest.main()
