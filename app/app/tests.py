from django.test import SimpleTestCase

from app.calc import calc, subtract


class CalcTests(SimpleTestCase):
    """Test the calc methods"""

    def test_add_numbers(self):
        res = calc(5, 6)
        self.assertEqual(res, 11)

    def test_subtract_numbers(self):
        """Test subtracting numbers."""
        res = subtract(10, 15)

        self.assertEqual(res, 5)
