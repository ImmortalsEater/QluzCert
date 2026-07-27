from datetime import date, datetime

import pandas as pd
from django.test import SimpleTestCase

from core.app_Gestor.parsing import bool_from, parse_date, parse_decimal


class ParseDateTests(SimpleTestCase):

    def test_none_returns_none(self):
        self.assertIsNone(parse_date(None))

    def test_datetime_instance_returns_its_date(self):
        self.assertEqual(parse_date(datetime(2024, 3, 15, 10, 30)), date(2024, 3, 15))

    def test_pandas_timestamp_returns_its_date(self):
        self.assertEqual(parse_date(pd.Timestamp('2024-03-15')), date(2024, 3, 15))

    def test_iso_date_string_is_parsed(self):
        self.assertEqual(parse_date('2024-03-15'), date(2024, 3, 15))

    def test_br_date_string_is_parsed(self):
        self.assertEqual(parse_date('15/03/2024'), date(2024, 3, 15))

    def test_unparseable_string_returns_none(self):
        self.assertIsNone(parse_date('não é uma data'))


class ParseDecimalTests(SimpleTestCase):

    def test_none_returns_none(self):
        self.assertIsNone(parse_decimal(None))

    def test_numeric_type_passthrough(self):
        self.assertEqual(parse_decimal(1234.5), 1234.5)

    def test_plain_numeric_string(self):
        self.assertEqual(parse_decimal('1234.56'), 1234.56)

    def test_brazilian_currency_format(self):
        self.assertEqual(parse_decimal('R$ 1.234,56'), 1234.56)

    def test_comma_decimal_without_thousands_separator(self):
        self.assertEqual(parse_decimal('99,90'), 99.90)

    def test_unparseable_string_returns_none(self):
        self.assertIsNone(parse_decimal('não é um número'))


class BoolFromTests(SimpleTestCase):

    def test_none_is_false(self):
        self.assertFalse(bool_from(None))

    def test_empty_string_is_false(self):
        self.assertFalse(bool_from(''))

    def test_recognized_truthy_values(self):
        for value in ['sim', 'Sim', 'SIM', 'true', '1', 'pago', 'yes', 'ok', 's']:
            with self.subTest(value=value):
                self.assertTrue(bool_from(value))

    def test_unrecognized_values_are_false(self):
        for value in ['não', 'nao', 'false', '0', 'n', 'talvez']:
            with self.subTest(value=value):
                self.assertFalse(bool_from(value))
