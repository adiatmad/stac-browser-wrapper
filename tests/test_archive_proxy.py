import io
import unittest
from unittest.mock import patch

from archive_proxy import _find_eocd, find_member


class ArchiveProxyTests(unittest.TestCase):
    def test_find_eocd_reads_standard_zip_footer(self):
        footer = bytes.fromhex("504b0506") + bytes.fromhex("0000000001000100") + (123).to_bytes(4, "little") + (456).to_bytes(4, "little") + bytes.fromhex("0000")
        self.assertEqual(_find_eocd(footer, 0), (456, 123))

    def test_find_eocd_rejects_zip64(self):
        footer = bytes.fromhex("504b0506") + bytes.fromhex("00000000") + bytes.fromhex("ffffffff") + (0xFFFFFFFF).to_bytes(4, "little") + (0xFFFFFFFF).to_bytes(4, "little") + bytes.fromhex("0000")
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
