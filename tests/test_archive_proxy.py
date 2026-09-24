import io
import unittest
from unittest.mock import patch

from archive_proxy import _find_eocd, find_member


class ArchiveProxyTests(unittest.TestCase):
    def test_find_eocd_reads_standard_zip_footer(self):
        footer = b"PK\\x05\\x06" + b"\\x00\\x00\\x00\\x00\\x01\\x00\\x01\\x00" + (123).to_bytes(4, "little") + (456).to_bytes(4, "little") + b"\\x00\\x00"
        self.assertEqual(_find_eocd(footer, 0), (456, 123))

    def test_find_eocd_rejects_zip64(self):
        footer = b"PK\\x05\\x06" + b"\\x00\\x00\\x00\\x00" + b"\\xff\\xff\\xff\\xff" + (0xFFFFFFFF).to_bytes(4, "little") + (0xFFFFFFFF).to_bytes(4, "little") + b"\\x00\\x00"
        with self.assertRaises(Exception):
            _find_eocd(footer, 0)

    def test_find_member_rejects_missing_member(self):
        with patch("archive_proxy._head", return_value=22), patch(
            "archive_proxy._central_directory", return_value=b"PK\\x01\\x02" + b"\\x00" * 42
        ):
            with self.assertRaises(Exception):
                find_member("https://example.s3.us-west-2.amazonaws.com/a.zip", "missing.tif")


if __name__ == "__main__":
    unittest.main()
