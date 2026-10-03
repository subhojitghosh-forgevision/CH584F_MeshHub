import hashlib
import os
import shutil
import tempfile
import unittest

import mrs_build

PROJECTS = r"C:\Embedded\WCH\projects"
RELAY = os.path.join(PROJECTS, "CH584F_Mesh_Relay_LED")
BLE_LED = os.path.join(PROJECTS, "CH584F_BLE_LED")


def rel(project, paths):
    return [os.path.relpath(p, project).replace("\\", "/") for p in paths]


class ParseTests(unittest.TestCase):
    def test_parses_mesh_relay_project(self):
        cfg = mrs_build.parse_cproject(RELAY)
        self.assertEqual(cfg.name, "CH584F_Mesh_Relay_LED")
        self.assertEqual(sorted(cfg.defines), sorted(
            ["DEBUG=0", "CLK_OSC32K=0", "DCDC_ENABLE=1", "BLE_MEMHEAP_SIZE=4096", "HAL_KEY=1"]))
        self.assertEqual(cfg.libs, ["ISP585", "MESH", "CH58xBLE"])
        self.assertIn("-march=rv32imc_zba_zbb_zbc_zbs_xw", cfg.compile_flags)
        self.assertIn("-mabi=ilp32", cfg.compile_flags)
        self.assertIn("-Os", cfg.compile_flags)
        self.assertIn("--param=highcode-gen-section-name=1", cfg.compile_flags)
        self.assertEqual(cfg.c_std, "-std=gnu99")
        self.assertTrue(cfg.linker_script.endswith(os.path.join("Ld", "Link.ld")))
        sources = rel(RELAY, cfg.sources)
        self.assertIn("APP/app_generic_onoff_model.c", sources)
        self.assertIn("Startup/startup_CH585.S", sources)
        self.assertEqual(len(sources), 33)
        self.assertEqual(sources, sorted(sources))

    def test_respects_source_exclusions(self):
        cfg = mrs_build.parse_cproject(BLE_LED)
        sources = rel(BLE_LED, cfg.sources)
        self.assertNotIn("HAL/KEY.c", sources)
        self.assertNotIn("HAL/LED.c", sources)
        self.assertIn("Profile/ledservice.c", sources)
        self.assertEqual(cfg.libs, ["ISP585", "CH58xBLE"])


class AssemblerDefineTests(unittest.TestCase):
    """Assembly files get the .cproject assembler defines (assembler.defs), not the C defines."""

    def test_reads_assembler_defines(self):
        sdk_node = (r"C:\Embedded\WCH\SDK\CH585EVT\EVT\EXAM\BLE\MESH"
                    r"\adv_vendor_self_provision_with_peripheral")
        self.assertEqual(mrs_build.parse_cproject(sdk_node).asm_defines,
                         ["LIB_FLASH_BASE_ADDRESSS=0x0004E000"])

    def test_projects_without_assembler_defines_get_none(self):
        self.assertEqual(mrs_build.parse_cproject(RELAY).asm_defines, [])


class RegressionTests(unittest.TestCase):
    """The tool must reproduce hex files that were built and verified on 2026-10-03."""

    def build_hash(self, project):
        out = tempfile.mkdtemp(prefix="mrs_build_test_")
        try:
            paths = mrs_build.build(mrs_build.parse_cproject(project), out, mrs_build.DEFAULT_TOOLCHAIN, [])
            with open(paths["hex"], "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_reproduces_mesh_relay_led_hex(self):
        self.assertEqual(self.build_hash(RELAY),
                         "2a942bdf4dbc5ba64934b1884aa9a401dc47f078e098aa1919e6ef29dca20491")

    def test_reproduces_ble_led_hex(self):
        self.assertEqual(self.build_hash(BLE_LED),
                         "a1d5e197fa85a45bf372492e11e80262adaf811abdea1b50e866fd693d421ca7")


if __name__ == "__main__":
    unittest.main()
