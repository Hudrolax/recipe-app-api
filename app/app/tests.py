from django.test import SimpleTestCase

from app.calc import calc


class CalcTests(SimpleTestCase):
    """Test the calc methods"""

    def test_add_numbers(self):
        res = calc(5, 6)
        self.assertEqual(res, 11)
