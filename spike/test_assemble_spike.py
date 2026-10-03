import os
import shutil
import tempfile
import unittest

import assemble_spike


def read(path):
    with open(path, "rb") as f:
        return f.read().decode("latin-1").replace("\r\n", "\n")


class AssembleBoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dest = tempfile.mkdtemp(prefix="spike_test_")
        cls.dirs = assemble_spike.assemble(cls.dest)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dest, ignore_errors=True)

    def test_ram_regions_are_ch584(self):
        for key in ("node", "iap"):
            ld = read(os.path.join(self.dirs[key], "Ld", "Link.ld"))
            self.assertIn("ORIGIN = 0x20005000, LENGTH = 76K", ld)
            self.assertNotIn("LENGTH = 108K", ld)
        ld = read(os.path.join(self.dirs["jumpiap"], "Ld", "Link.ld"))
        self.assertIn("ORIGIN = 0x20000000, LENGTH = 96K", ld)
        self.assertNotIn("LENGTH = 128K", ld)

    def test_linked_folders_are_copied_and_projects_renamed(self):
        node = self.dirs["node"]
        for sub in ("HAL/include/CONFIG.h", "MESH_LIB/LIBCH58xMESHROM.a", "MESH_LIB/CH584BLE_ROM_MESH.hex",
                    "LIB/CH58xBLE_ROM.h", "StdPeriphDriver/libISP585.a", "RVMSIS/core_riscv.h"):
            self.assertTrue(os.path.isfile(os.path.join(node, sub)), sub)
        for key, name in (("node", "spike_node"), ("iap", "spike_iap"), ("jumpiap", "spike_jumpiap")):
            project = read(os.path.join(self.dirs[key], ".project"))
            self.assertIn(f"<name>{name}</name>", project)
            self.assertNotIn("<linkedResources>", project)

    def test_board_settings_on_node(self):
        node = self.dirs["node"]
        cproject = read(os.path.join(node, ".cproject"))
        self.assertIn('value="CLK_OSC32K=0"', cproject)
        self.assertIn('value="DCDC_ENABLE=1"', cproject)
        main = read(os.path.join(node, "APP", "app_main.c"))
        self.assertIn("PWR_DCDCCfg(ENABLE);", main)
        self.assertIn("HSECFG_Capacitance(HSECap_10p);", main)
        self.assertNotIn("HSECap_18p", main)
        key_h = read(os.path.join(node, "HAL", "include", "KEY.h"))
        self.assertIn("#define KEY2_BV                  ()", key_h)

    def test_refuses_to_overwrite_without_force(self):
        with self.assertRaises(SystemExit):
            assemble_spike.assemble(self.dest)


if __name__ == "__main__":
    unittest.main()
