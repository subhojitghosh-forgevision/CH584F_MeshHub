import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
NODE = os.path.join(HERE, "node")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import check_image  # noqa: E402
import mrs_build  # noqa: E402
from merge_hex import read_hex  # noqa: E402

TEST_UUID = b"MeshHub-M1-test!"


def read_bytes(*parts):
    with open(os.path.join(NODE, *parts), "rb") as f:
        return f.read()


class NodeProjectTests(unittest.TestCase):
    def setUp(self):
        self.cfg = mrs_build.parse_cproject(NODE)

    def test_uses_our_hal_headers_and_the_weact_key_driver(self):
        compiled = set(self.cfg.virtual.values())
        self.assertIn("hal/KEY.c", compiled)
        self.assertNotIn("sdk_hal/KEY.c", compiled)
        for v in ("sdk_hal/MCU.c", "Startup/startup_CH585.S", "LIB/ble_task_scheduler.S", "src/main.c"):
            self.assertIn(v, compiled)
        self.assertEqual(os.path.normcase(self.cfg.includes[0]), os.path.normcase(os.path.join(NODE, "hal", "include")))

    def test_no_compiled_sdk_source_sits_next_to_a_hal_header(self):
        """#include "CONFIG.h" looks in the source's own folder first, which would bypass our CH584 CONFIG.h."""
        ours = os.path.normcase(NODE)
        for src in self.cfg.sources:
            if os.path.normcase(src).startswith(ours):
                continue
            for header in ("CONFIG.h", "HAL.h"):
                self.assertFalse(os.path.exists(os.path.join(os.path.dirname(src), header)), f"{src} next to {header}")

    def test_board_defines_and_libraries(self):
        for d in ("CLK_OSC32K=0", "DCDC_ENABLE=1", "CH58xBLE_ROM", "LIB_FLASH_BASE_ADDRESSS=0x0004E000"):
            self.assertIn(d, self.cfg.defines)
        self.assertEqual(self.cfg.asm_defines, ["LIB_FLASH_BASE_ADDRESSS=0x0004E000"])
        self.assertEqual(self.cfg.libs, ["ISP585", "CH58xMESHROM"])

    def test_config_targets_ch584_without_snv(self):
        text = read_bytes("hal", "include", "CONFIG.h")
        self.assertRegex(text, rb"#define CHIP_ID\s+ID_CH584\b")
        self.assertRegex(text, rb"#define BLE_SNV\s+FALSE\b")

    def test_mesh_stack_settings(self):
        text = read_bytes("src", "app_mesh_config.h")
        for pattern in (rb"#define CONFIG_BLE_MESH_PROXY\s+1\b", rb"#define CONFIG_BLE_MESH_PB_GATT\s+1\b",
                        rb"#define CONFIG_BLE_MESH_CFG_CLI\s+0\b", rb"#define CONFIG_MESH_UNSEG_LENGTH_DEF\s+\(7\)",
                        rb"#define CONFIG_MESH_RX_SDU_DEF\s+\(256\)"):
            self.assertRegex(text, pattern)

    def test_ram_region_is_ch584_sized(self):
        self.assertIn(b"RAM (xrw) : ORIGIN = 0x20005000, LENGTH = 76K", read_bytes("Ld", "Link.ld"))


class NodeBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp(prefix="fw_node_")
        cls.paths = mrs_build.build(mrs_build.parse_cproject(NODE), cls.out, mrs_build.DEFAULT_TOOLCHAIN, [])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_fits_the_application_slot_with_the_ch584_stack(self):
        self.assertEqual(check_image.check(self.paths["hex"], 0x01000, 0x27000, elf=self.paths["elf"],
                                           stack_top=0x20018000), [])

    def test_sets_up_dcdc_and_the_crystal(self):
        for symbol in ("PWR_DCDCCfg", "HSECFG_Capacitance", "board_boot_blink", "mesh_node_init"):
            self.assertIsNotNone(check_image.symbol_value(self.paths["elf"], symbol), symbol)

    def test_image_carries_the_m1_test_uuid(self):
        mem = read_hex(self.paths["hex"])
        image = bytes(mem.get(a, 0xFF) for a in range(min(mem), max(mem) + 1))
        self.assertIn(TEST_UUID, image)


if __name__ == "__main__":
    unittest.main()
