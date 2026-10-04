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


class ForceReassemblyTests(unittest.TestCase):
    """--force must replace an earlier copy even though some SDK files are read-only."""

    def test_force_reassembles_over_existing_copy(self):
        dest = tempfile.mkdtemp(prefix="spike_force_test_")
        try:
            assemble_spike.assemble(dest)
            dirs = assemble_spike.assemble(dest, force=True)
            self.assertTrue(os.path.isfile(os.path.join(dirs["node"], "HAL", "include", "CONFIG.h")))
        finally:
            shutil.rmtree(dest, onexc=assemble_spike.force_remove)


class SpikeFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dest = tempfile.mkdtemp(prefix="spike_feat_test_")
        cls.node = assemble_spike.assemble(cls.dest)["node"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dest, ignore_errors=True)

    def test_mesh_config_enables_pb_gatt_proxy_and_spec_sizes(self):
        cfg = read(os.path.join(self.node, "APP", "include", "app_mesh_config.h"))
        self.assertRegex(cfg, r"#define CONFIG_BLE_MESH_PROXY\s+1\b")
        self.assertRegex(cfg, r"#define CONFIG_BLE_MESH_PB_GATT\s+1\b")
        self.assertRegex(cfg, r"#define CONFIG_MESH_UNSEG_LENGTH_DEF\s+\(7\)")
        self.assertRegex(cfg, r"#define CONFIG_MESH_RX_SDU_DEF\s+\(256\)")

    def test_app_uses_static_oob_and_skips_custom_peripheral(self):
        app = read(os.path.join(self.node, "APP", "app.c"))
        self.assertIn(".static_val = spike_static_oob,", app)
        self.assertIn(".static_val_len = sizeof(spike_static_oob),", app)
        self.assertIn("0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF", app)
        self.assertNotIn("    GAPRole_PeripheralInit();\n    Peripheral_Init();", app)
        self.assertIn("spike_boot_blink(SPIKE_VERSION);", app)
        self.assertIn("if(events & SPIKE_PUB_EVT)", app)
        self.assertIn("tmos_start_task(App_TaskID, SPIKE_PUB_EVT, SPIKE_PUB_PERIOD);", app)
        self.assertIn("// SPIKE: unicast commands arrive as acknowledged WRT", app)

    def test_node_advertises_as_unprovisioned(self):
        app = read(os.path.join(self.node, "APP", "app.c"))
        self.assertEqual(app.count("prov_enable(); // SPIKE: advertise as unprovisioned"), 3)

    def test_provisioned_led_is_weact_pb6(self):
        hdr = read(os.path.join(self.node, "APP", "include", "app_trans_process.h"))
        self.assertIn("#define LED_PIN    GPIO_Pin_6", hdr)
        self.assertNotIn("GPIO_Pin_18", hdr)

    def test_peripheral_entry_points_are_guarded(self):
        per = read(os.path.join(self.node, "APP", "peripheral.c"))
        self.assertEqual(per.count("    return; // SPIKE: custom peripheral not started"), 3)


if __name__ == "__main__":
    unittest.main()
