import logging
import unittest

from tunerpro_exporter import UniversalXDFExporter


class ScalarExportErrorTests(unittest.TestCase):
    def setUp(self):
        self.exporter = UniversalXDFExporter.__new__(UniversalXDFExporter)
        self.exporter.logger = logging.getLogger(__name__)

    def test_malformed_equation_is_reported_without_using_raw_as_value(self):
        item = {
            "title": "Malformed scalar",
            "equation": "*2**14",
            "linked_vars": {},
        }

        value, error = self.exporter._scalar_export_value(item, 197)

        self.assertIsNone(value)
        self.assertIn("Invalid equation", error)
        self.assertIn("raw=197", error)

    def test_scalar_without_equation_keeps_raw_value(self):
        item = {"title": "Raw scalar", "equation": ""}

        value, error = self.exporter._scalar_export_value(item, 42)

        self.assertEqual(value, 42)
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
