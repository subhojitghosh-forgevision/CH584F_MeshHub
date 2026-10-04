import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import check_image  # noqa: E402
import mrs_build  # noqa: E402
import projects  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class GeneratedFilesTests(unittest.TestCase):
    def test_committed_project_files_match_the_generator(self):
        for p in projects.PROJECTS:
            for name, text in ((".project", projects.project_xml(p)), (".cproject", projects.cproject_xml(p))):
                self.assertEqual(read(os.path.join(HERE, p.folder, name)), text,
                                 f"firmware/{p.folder}/{name} differs from firmware/projects.py: run python firmware/projects.py")


class LoaderProjectTests(unittest.TestCase):
    def test_iap_sources_come_from_the_sdk(self):
        cfg = mrs_build.parse_cproject(os.path.join(HERE, "iap"))
        self.assertEqual(cfg.name, "meshhub_iap")
        self.assertIn("APP/app_main.c", cfg.virtual.values())
        self.assertEqual(os.path.normcase(cfg.linker_script),
                         os.path.normcase(os.path.join(HERE, "iap", "Ld", "Link.ld")))

    def test_ram_regions_are_ch584_sized(self):
        for folder, line in (("iap", "RAM (xrw) : ORIGIN = 0x20005000, LENGTH = 76K"),
                             ("jumpiap", "RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 96K")):
            self.assertIn(line, read(os.path.join(HERE, folder, "Ld", "Link.ld")))


class LoaderBuildTests(unittest.TestCase):
    def build(self, folder):
        out = tempfile.mkdtemp(prefix=f"fw_{folder}_")
        self.addCleanup(shutil.rmtree, out, True)
        return mrs_build.build(mrs_build.parse_cproject(os.path.join(HERE, folder)), out,
                               mrs_build.DEFAULT_TOOLCHAIN, [])

    def test_iap_builds_inside_its_slot(self):
        p = self.build("iap")
        self.assertEqual(check_image.check(p["hex"], 0x4D000, 0x4E000, elf=p["elf"], stack_top=0x20018000), [])

    def test_jumpiap_builds_inside_its_slot(self):
        p = self.build("jumpiap")
        self.assertEqual(check_image.check(p["hex"], 0x00000, 0x01000), [])


if __name__ == "__main__":
    unittest.main()
