import os
import shutil
import tempfile
import unittest

import merge_hex


class MergeHexTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="merge_hex_test_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.dir, name)

    def test_round_trip_above_64k(self):
        mem = {0x0FFFE: 1, 0x0FFFF: 2, 0x10000: 3, 0x4E000: 0xAA}
        merge_hex.write_hex(mem, self.path("a.hex"))
        self.assertEqual(merge_hex.read_hex(self.path("a.hex")), mem)
        with open(self.path("a.hex")) as f:
            text = f.read()
        self.assertIn(":020000040001F9", text)
        self.assertTrue(text.rstrip().endswith(":00000001FF"))

    def test_offset_shifts_every_byte(self):
        merge_hex.write_hex({0x1000: 0x11, 0x1001: 0x22}, self.path("b.hex"))
        self.assertEqual(merge_hex.read_hex(self.path("b.hex"), 0x26000), {0x27000: 0x11, 0x27001: 0x22})

    def test_overlap_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            merge_hex.merge([{0x1000: 1}, {0x0FFF: 9, 0x1000: 2}])
        self.assertIn("0x01000", str(ctx.exception))

    def test_bad_checksum_is_rejected(self):
        with open(self.path("bad.hex"), "w") as f:
            f.write(":0100000011EF\n:00000001FF\n")
        with self.assertRaises(ValueError):
            merge_hex.read_hex(self.path("bad.hex"))

    def test_segment_address_records_are_understood(self):
        with open(self.path("seg.hex"), "w") as f:
            f.write(":020000021000EC\n:01000000AB54\n:00000001FF\n")
        self.assertEqual(merge_hex.read_hex(self.path("seg.hex")), {0x10000: 0xAB})


if __name__ == "__main__":
    unittest.main()
