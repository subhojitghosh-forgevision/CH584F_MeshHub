import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import build  # noqa: E402
from merge_hex import read_hex, write_hex  # noqa: E402


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fw_pkg_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def hexfile(self, name, start, size=16):
        path = os.path.join(self.tmp, name + ".hex")
        write_hex({start + i: i & 0xFF for i in range(size)}, path)
        return path

    def parts(self):
        return {"jumpiap": self.hexfile("jumpiap", 0x00000), "node": self.hexfile("node", 0x01000),
                "iap": self.hexfile("iap", 0x4D000)}

    def test_reads_the_version_from_the_header(self):
        self.assertEqual(build.read_version(), (1, 0))

    def test_package_places_every_image(self):
        out = build.package(self.parts(), self.hexfile("CH584BLE_ROM_MESH", 0x4E000), os.path.join(self.tmp, "p.hex"))
        mem = read_hex(out)
        for addr in (0x00000, 0x01000, 0x4D000, 0x4E000):
            self.assertIn(addr, mem)

    def test_package_rejects_an_image_outside_its_slot(self):
        parts = self.parts()
        parts["node"] = self.hexfile("node_big", 0x26FF8, size=16)   # runs past 0x27000
        with self.assertRaises(build.FirmwareError):
            build.package(parts, self.hexfile("CH584BLE_ROM_MESH", 0x4E000), os.path.join(self.tmp, "p.hex"))

    def test_package_rejects_a_non_ch584_rom_library(self):
        with self.assertRaises(build.FirmwareError):
            build.package(self.parts(), self.hexfile("CH585BLE_ROM_MESH", 0x4E000), os.path.join(self.tmp, "p.hex"))

    def test_build_all_starts_from_a_clean_folder(self):
        out = os.path.join(self.tmp, "build")
        os.makedirs(out)
        marker = os.path.join(out, "stale.hex")
        open(marker, "w").close()
        self.assertEqual(build.build_all(out, images={}), {})
        self.assertFalse(os.path.exists(marker))


class RunTests(unittest.TestCase):
    def test_failed_build_leaves_no_package_behind(self):
        """Step 1 keeps version 1.0, so a stale meshhub-1.0.hex would be flashed by mistake after a failed build."""
        tmp = tempfile.mkdtemp(prefix="fw_run_")
        self.addCleanup(shutil.rmtree, tmp, True)
        stale = os.path.join(tmp, "meshhub-1.0.hex")
        open(stale, "w").close()
        rc = build.run(tmp, images={"node": ("no_such_project", 0x01000, 0x27000, True)})
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(stale))


class FullBuildTests(unittest.TestCase):
    def test_builds_checks_and_packages_all_images(self):
        tmp = tempfile.mkdtemp(prefix="fw_full_")
        self.addCleanup(shutil.rmtree, tmp, True)
        paths = build.build_all(os.path.join(tmp, "build"))
        self.assertEqual(sorted(paths), ["iap", "jumpiap", "node"])
        out = build.package({n: p["hex"] for n, p in paths.items()}, build.ROM_HEX, os.path.join(tmp, "meshhub.hex"))
        mem = read_hex(out)
        for addr in (0x00000, 0x01000, 0x4D000, 0x4E000):
            self.assertIn(addr, mem)
        self.assertLess(max(mem), 0x70000)


if __name__ == "__main__":
    unittest.main()
