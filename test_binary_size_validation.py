from __future__ import annotations

import unittest

from tunerpro_exporter import is_common_binary_size


class BinarySizeValidationTests(unittest.TestCase):
    def test_accepts_bmw_partial_and_full_image_sizes(self) -> None:
        for size in (32 * 1024, 64 * 1024, 116 * 1024, 128 * 1024, 512 * 1024, 1024 * 1024):
            with self.subTest(size=size):
                self.assertTrue(is_common_binary_size(size))

    def test_keeps_arbitrary_length_as_warning_candidate(self) -> None:
        self.assertFalse(is_common_binary_size(12345))


if __name__ == "__main__":
    unittest.main()
