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


OPTION = "ilg.gnumcueclipse.managedbuild.cross.riscv.option."
CPROJECT = f"""<?xml version="1.0" encoding="UTF-8"?>
<cproject><configuration>
<option superClass="{OPTION}c.linker.scriptfile"><listOptionValue value="&quot;${{workspace_loc:/${{ProjName}}/src/x.ld}}&quot;"/></option>
<option superClass="{OPTION}c.compiler.include.paths"><listOptionValue value="&quot;${{workspace_loc:/${{ProjName}}/shared/inc}}&quot;"/></option>
<entry kind="sourcePath" name="src"/>
<entry kind="sourcePath" name="shared" excluding="skip.c"/>
<entry kind="sourcePath" name="abs"/>
<entry kind="sourcePath" name="lnk"/>
</configuration></cproject>
"""
SDK = r"C:\Embedded\WCH\SDK\CH585EVT\EVT\EXAM"
SDK_NODE = SDK + r"\BLE\MESH\adv_vendor_self_provision_with_peripheral"


class LinkedResourceTests(unittest.TestCase):
    """MounRiver/Eclipse linked resources (.project <linkedResources>), the way WCH's SDK examples use them."""

    def make_tree(self):
        root = tempfile.mkdtemp(prefix="mrs_links_")
        self.addCleanup(shutil.rmtree, root, True)
        for rel in ("shared/a.c", "shared/skip.c", "shared/inc/shared.h", "abs dir/b.c", "single/one.c",
                    "proj/src/main.c", "proj/src/x.ld"):
            path = os.path.join(root, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
        return root

    def write_project(self, root, links):
        proj = os.path.join(root, "proj")
        xml = "".join(f"<link><name>{n}</name><type>{t}</type><locationURI>{u}</locationURI></link>"
                      for n, t, u in links)
        with open(os.path.join(proj, ".project"), "w", encoding="utf-8") as f:
            f.write(f"<projectDescription><name>demo</name><linkedResources>{xml}</linkedResources>"
                    "</projectDescription>")
        with open(os.path.join(proj, ".cproject"), "w", encoding="utf-8") as f:
            f.write(CPROJECT)
        return proj

    def file_uri(self, root, *parts):
        return "file:/" + "/".join([root.replace("\\", "/")] + list(parts)).replace(" ", "%20")

    def links(self, root):
        return [("shared", 2, "PARENT-1-PROJECT_LOC/shared"),
                ("abs", 2, self.file_uri(root, "abs dir")),
                ("lnk", 2, "virtual:/virtual"),
                ("lnk/one.c", 1, self.file_uri(root, "single", "one.c"))]

    def test_resolves_location_forms(self):
        proj = r"C:\a\b\c"
        self.assertEqual(mrs_build.resolve_location(proj, "PARENT-2-PROJECT_LOC/x/y"), r"C:\a\x\y")
        self.assertEqual(mrs_build.resolve_location(proj, "PROJECT_LOC/z"), r"C:\a\b\c\z")
        self.assertEqual(mrs_build.resolve_location(proj, "file:/C:/q/with%20space"), r"C:\q\with space")
        self.assertIsNone(mrs_build.resolve_location(proj, "virtual:/virtual"))

    def test_sources_come_through_folder_and_file_links(self):
        root = self.make_tree()
        cfg = mrs_build.parse_cproject(self.write_project(root, self.links(root)))
        self.assertEqual([cfg.virtual[s] for s in cfg.sources], ["abs/b.c", "lnk/one.c", "shared/a.c", "src/main.c"])
        self.assertEqual(os.path.normcase(cfg.sources[0]), os.path.normcase(os.path.join(root, "abs dir", "b.c")))
        self.assertEqual(os.path.normcase(cfg.sources[1]), os.path.normcase(os.path.join(root, "single", "one.c")))

    def test_include_paths_resolve_through_links(self):
        root = self.make_tree()
        cfg = mrs_build.parse_cproject(self.write_project(root, self.links(root)))
        self.assertEqual([os.path.normcase(i) for i in cfg.includes],
                         [os.path.normcase(os.path.join(root, "shared", "inc"))])

    def test_link_colliding_with_a_project_folder_is_an_error(self):
        root = self.make_tree()
        proj = self.write_project(root, [("src", 2, "PARENT-1-PROJECT_LOC/shared")])
        with self.assertRaises(mrs_build.BuildError):
            mrs_build.parse_cproject(proj)

    def test_missing_link_target_is_an_error(self):
        root = self.make_tree()
        proj = self.write_project(root, [("shared", 2, "PARENT-1-PROJECT_LOC/no_such_folder")])
        with self.assertRaises(mrs_build.BuildError) as cm:
            mrs_build.parse_cproject(proj)
        self.assertIn("no_such_folder", str(cm.exception))


class SdkExampleTests(unittest.TestCase):
    """WCH's own example compiles in place, its linked folders resolved into the SDK."""

    def test_sdk_example_sources_resolve_through_its_links(self):
        cfg = mrs_build.parse_cproject(SDK_NODE)
        by_virtual = {v: r for r, v in cfg.virtual.items()}
        self.assertEqual(os.path.normcase(by_virtual["HAL/MCU.c"]),
                         os.path.normcase(os.path.join(SDK, "BLE", "HAL", "MCU.c")))
        for v in ("StdPeriphDriver/CH58x_gpio.c", "LIB/ble_task_scheduler.S", "APP/app.c", "Startup/startup_CH585.S"):
            self.assertIn(v, by_virtual)
        self.assertIn(os.path.normcase(os.path.join(SDK, "BLE", "HAL", "include")),
                      [os.path.normcase(i) for i in cfg.includes])

    def test_builds_the_sdk_example_in_place(self):
        out = tempfile.mkdtemp(prefix="mrs_sdk_")
        self.addCleanup(shutil.rmtree, out, True)
        cfg = mrs_build.parse_cproject(SDK_NODE)
        paths = mrs_build.build(cfg, out, mrs_build.DEFAULT_TOOLCHAIN, [])
        self.assertGreater(os.path.getsize(paths["hex"]), 0)
        objects = [f for _, _, files in os.walk(out) for f in files if f.endswith(".o")]
        self.assertEqual(len(objects), len(cfg.sources))


if __name__ == "__main__":
    unittest.main()
