import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import merge_hex  # noqa: E402
import package  # noqa: E402

SPIKE = os.path.dirname(os.path.abspath(__file__))


class PackageTests(unittest.TestCase):
    def test_full_package_layout(self):
        out = package.make_package(SPIKE, include_v2_in_b=True)
        mem = merge_hex.read_hex(out)
        self.assertIn(0x00000, mem)   # JumpIAP
        self.assertIn(0x01000, mem)   # node v1 (application slot)
        self.assertIn(0x27000, mem)   # node v2 (update buffer)
        self.assertIn(0x4D000, mem)   # IAP
        self.assertIn(0x4E000, mem)   # CH584 ROM library
        self.assertLess(max(mem), 0x70000)
        self.assertFalse(any(0x27000 <= a < 0x4D000 for a in merge_hex.read_hex(package.make_package(SPIKE, False))))

    def test_rejects_non_ch584_rom_library(self):
        with self.assertRaises(ValueError):
            package.check_rom_file(r"C:\x\CH585BLE_ROM_MESH.hex")


if __name__ == "__main__":
    unittest.main()
