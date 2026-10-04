# Step 1 / M1 Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CH584F mesh node skeleton from our own code, with the WCH SDK linked in. It builds, is checked and packaged into one flashable hex, and advertises as an unprovisioned mesh device.

**Architecture:**
- **Linked resources.** `tools/mrs_build.py` learns to resolve MounRiver/Eclipse linked resources: linked folders and linked files, in the `PARENT-n-PROJECT_LOC`, `file:/` and `virtual:` forms. A project can then compile WCH SDK sources in place.
- **Project generator.** `firmware/projects.py` describes the three projects (node, iap, jumpiap). It generates their `.project` and `.cproject` from the matching WCH SDK example, so the XML never drifts.
- **Build script.** `firmware/build.py` builds and checks all three images and merges them with the CH584 ROM library into `firmware/out/meshhub-1.0.hex`.

**Tech Stack:**
- Python 3.12 `unittest`;
- MounRiver Studio 2 GCC12 (`riscv-wch-elf-*`);
- WCH CH585EVT SDK (CH58x BLE ROM library and MESH_LIB V1.79);
- bleak 3.0.2 (already installed) for the laptop scan.

**Spec:** `docs/specs/2026-10-04-step1-firmware-design.md`. M1 is its section 12 row "M1 Skeleton"; sections 3, 4 and 7.6 apply. The parent spec is `docs/specs/2026-10-03-ch584f-mesh-hub-design.md`.

## Global Constraints

**Memory layout**
- Application at `0x1000`, length 152 KB.
- RAM `0x20005000`, 76 KB.
- Every build must pass `check_image.py` with `--elf` and stack top `0x20018000`. The exception is JumpIAP, which defines no `_eusrstack` and is range-checked only.

**Board configuration**
- Board defines: `CLK_OSC32K=0`, `DCDC_ENABLE=1` plus `PWR_DCDCCfg(ENABLE)` in `main()`, `HSECap_10p`, `CHIP_ID=ID_CH584`, `BLE_SNV=FALSE`.
- Mesh stack settings: `CONFIG_MESH_UNSEG_LENGTH_DEF` 7, `CONFIG_MESH_RX_SDU_DEF` 256, default TTL 5.
- Composition target: one element with the Config Server, Health Server and WCH vendor server (CID `0x07D7`, model `0x0000`). **No Config Client.** Relay and proxy are on; friend and LPN are off. M1 builds the Config Server and Health Server; the vendor server arrives in M4.

**Security**
- No key material in the source, the images or the UART output.

**Source and tooling**
- **SDK location.** The WCH SDK is used unchanged from `C:\Embedded\WCH\SDK\CH585EVT\EVT\EXAM`, linked as `PARENT-4-PROJECT_LOC/SDK/CH585EVT/EVT/EXAM/...` from `firmware/<project>/`. The repository must stay at `C:\Embedded\WCH\projects\CH584F_MeshHub`.
- **`mrs_build.py` regression.** The existing regression hashes must not change: Mesh Relay `2a942bdf…0491` and BLE LED `a1d5e197…1ca7`.
- **Environment.** Windows with Git Bash. The PowerShell tool is blocked. Write multi-line files with the editor, not with shell heredocs that contain backslashes. No new installs in M1.

**Flashing**
- The user flashes the boards. **Every flash needs the user's explicit approval.**

**Commits**
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

**Test commands**
- `python -m unittest discover -s tools -p "test_*.py"`
- `python -m unittest discover -s firmware -p "test_*.py"`
- `python -m unittest discover -s spike -p "test_*.py"`

## Review Focus

1. **A compiled SDK source sitting next to a `CONFIG.h` or `HAL.h`.** `#include "CONFIG.h"` searches the source file's own folder first. Such a source would silently use WCH's CH585 configuration instead of ours. Pinned by Task 3 `test_no_compiled_sdk_source_sits_next_to_a_hal_header`.
2. **A linked resource that collides with a real folder or file in the project.** The build must fail loudly, not pick one silently. Pinned by Task 1 `test_link_colliding_with_a_project_folder_is_an_error`.
3. **A linked resource whose target is missing,** for example after the SDK moves. The build must fail and name the path, not build an image with files missing. Pinned by Task 1 `test_missing_link_target_is_an_error`.
4. **Paths with spaces in `file:/` URIs** (`%20`). They must resolve. Pinned by Task 1 `test_resolves_location_forms` and the `abs dir` fixture.
5. **A stale image from an earlier run being packaged after a failed build.** `build_all` clears its output folder first, and `package` takes only this run's paths. Pinned by Task 4 `test_build_all_starts_from_a_clean_folder`.

---

### Task 1: Linked resources in `mrs_build.py`

**Files:**
- Modify: `tools/mrs_build.py`, all of it except `_options`, `_val`, `_list`, `_true`, `_march`, `_mabi`, `_run` and `main`
- Test: `tools/test_mrs_build.py`, adding two classes

**Interfaces:**
- **Consumes:** nothing new.
- **Produces:**
  - `resolve_location(project_dir: str, location: str) -> str | None` returns an absolute path, or None for a virtual folder.
  - `parse_links(project_dir: str) -> dict[str, str | None]` maps each virtual name to its real path.
  - `project_files(project_dir: str, links: dict) -> dict[str, str]` maps each virtual project-relative path (with `/` separators) to its real path.
  - `BuildConfig.virtual: dict[str, str]` maps each real source path to its virtual path. The virtual path is used for object file names.
  - `BuildConfig.sources` stays a list of real paths, now sorted by virtual path. For projects without links, the order is unchanged.

- [ ] **Step 1: Write the failing tests.** Append to `tools/test_mrs_build.py`, before `if __name__ == "__main__":`.

```python
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
```

- [ ] **Step 2: Run them to verify they fail.**

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub/tools && python -m unittest test_mrs_build.LinkedResourceTests test_mrs_build.SdkExampleTests 2>&1 | tail -5`

Expected: FAILED. The errors include `AttributeError: module 'mrs_build' has no attribute 'resolve_location'` and `AttributeError: 'BuildConfig' object has no attribute 'virtual'`.

- [ ] **Step 3: Implement.** Edit `tools/mrs_build.py` in five places.

(a) Add to the imports:

```python
from urllib.parse import unquote
```

(b) Add a field to `BuildConfig`, after `gcc_major`:

```python
    virtual: dict = field(default_factory=dict)   # real source path -> project-relative path (object names)
```

(c) Replace `_resolve` and `_sources` with:

```python
def resolve_location(project_dir, location):
    """Absolute path of an Eclipse linked-resource location; None for a virtual folder. Windows paths only."""
    loc = location.strip()
    if loc.startswith("virtual:"):
        return None
    if loc.startswith("PARENT-"):
        count, _, rest = loc[len("PARENT-"):].partition("-PROJECT_LOC")
        base = os.path.abspath(project_dir)
        for _ in range(int(count)):
            base = os.path.dirname(base)
        return os.path.normpath(os.path.join(base, unquote(rest).lstrip("/")))
    if loc.startswith("PROJECT_LOC"):
        return os.path.normpath(os.path.join(os.path.abspath(project_dir), unquote(loc[len("PROJECT_LOC"):]).lstrip("/")))
    if loc.startswith("file:"):
        return os.path.normpath(unquote(loc[len("file:"):]).lstrip("/"))
    if os.path.isabs(loc):
        return os.path.normpath(loc)
    raise BuildError(f"unsupported linked resource location: {location}")


def parse_links(project_dir):
    """Linked resources of .project: {virtual name: real path, or None for a virtual folder}."""
    root = ET.parse(os.path.join(project_dir, ".project")).getroot()
    links = {}
    for link in root.iter("link"):
        name = (link.findtext("name") or "").strip().replace("\\", "/")
        loc = link.findtext("locationURI") or link.findtext("location") or ""
        if not name or not loc:
            raise BuildError(f"incomplete linked resource in .project: {name!r}")
        links[name] = resolve_location(project_dir, loc)
    return links


def _walk(real_root, prefix):
    for dirpath, dirnames, filenames in os.walk(real_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, real_root).replace("\\", "/")
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        for f in filenames:
            yield prefix + rel_dir + f, os.path.normpath(os.path.join(dirpath, f))


def project_files(project_dir, links):
    """Every file of the project as {virtual project-relative path ('/' separators): real path}, links included."""
    files = dict(_walk(project_dir, ""))
    for name, real in sorted(links.items()):
        if real is None:
            continue
        if os.path.exists(os.path.join(project_dir, *name.split("/"))):
            raise BuildError(f"linked resource {name!r} collides with a file or folder inside the project")
        if os.path.isdir(real):
            files.update(_walk(real, name + "/"))
        elif os.path.isfile(real):
            files[name] = real
        else:
            raise BuildError(f"linked resource {name!r} points to a missing path: {real}")
    return files


def _map_virtual(project_dir, links, vpath):
    best = None
    for name in links:
        if (vpath == name or vpath.startswith(name + "/")) and (best is None or len(name) > len(best)):
            best = name
    if best is None or links[best] is None:
        return os.path.normpath(os.path.join(project_dir, vpath))
    rest = vpath[len(best):].lstrip("/")
    return os.path.normpath(os.path.join(links[best], rest)) if rest else links[best]


def _resolve(project_dir, value, links=None):
    v = value.strip().strip('"')
    prefix = "${workspace_loc:/${ProjName}/"
    if v.startswith(prefix):
        return _map_virtual(project_dir, links or {}, v[len(prefix):].rstrip("}"))
    if v.startswith("${workspace_loc:/${ProjName}}"):
        return os.path.normpath(project_dir)
    # Plain relative paths are relative to the build folder (obj/), one level below the project
    return os.path.normpath(os.path.join(project_dir, "obj", v))


def _sources(files, cfg_elem):
    """{real path: virtual path} of every source selected by the sourcePath entries and their exclusions."""
    selected = {}
    for e in cfg_elem.iter("entry"):
        if e.get("kind") != "sourcePath":
            continue
        root = (e.get("name") or "").strip("/")
        excluded = {x for x in (e.get("excluding") or "").split("|") if x}
        for vpath, real in files.items():
            if root and not vpath.startswith(root + "/"):
                continue
            if os.path.splitext(vpath)[1] not in SOURCE_EXTS:
                continue
            rel = vpath[len(root) + 1:] if root else vpath
            if any(rel == x or rel.startswith(x + "/") for x in excluded):
                continue
            selected[real] = vpath
    return selected
```

(d) In `parse_cproject`, replace these lines:

```python
    cfg.includes = [_resolve(project_dir, v) for v in _list(o, "c.compiler.include.paths")]
    cfg.sources = _sources(project_dir, cfg_elem)
    cfg.libs = list(_list(o, "c.linker.libs"))
    cfg.lib_dirs = [_resolve(project_dir, v) for v in _list(o, "c.linker.paths")]
```

with:

```python
    links = parse_links(project_dir)
    cfg.includes = [_resolve(project_dir, v, links) for v in _list(o, "c.compiler.include.paths")]
    cfg.virtual = _sources(project_files(project_dir, links), cfg_elem)
    cfg.sources = sorted(cfg.virtual, key=lambda real: cfg.virtual[real])
    cfg.libs = list(_list(o, "c.linker.libs"))
    cfg.lib_dirs = [_resolve(project_dir, v, links) for v in _list(o, "c.linker.paths")]
```

Then change `cfg.linker_script = _resolve(project_dir, scripts[0])` to `cfg.linker_script = _resolve(project_dir, scripts[0], links)`.

(e) In `build`, replace `rel = os.path.relpath(src, cfg.project_dir)` with:

```python
        rel = cfg.virtual.get(src) or os.path.relpath(src, cfg.project_dir)
```

- [ ] **Step 4: Run the whole tools suite.** It includes the regression hashes.

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub && python -m unittest discover -s tools -p "test_*.py" > /tmp/t1.log 2>&1; echo "exit $?"; grep -E "^(Ran|OK|FAILED|FAIL:|ERROR:)" /tmp/t1.log`

Expected: `exit 0`, `Ran 24 tests`, `OK`. That is 17 existing tests plus 7 new, and the two regression hashes are unchanged.

- [ ] **Step 5: Commit**

```bash
git add tools/mrs_build.py tools/test_mrs_build.py
git commit -m "feat(tools): resolve MounRiver linked resources in mrs_build

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Project generator, plus the IAP and JumpIAP projects

**Files:**
- Create: `firmware/projects.py`
- Create, by copying and editing: `firmware/iap/Ld/Link.ld`, `firmware/jumpiap/Ld/Link.ld`
- Create, generated: `firmware/iap/.project`, `firmware/iap/.cproject`, `firmware/jumpiap/.project`, `firmware/jumpiap/.cproject`
- Modify: `.gitignore`
- Test: `firmware/test_projects.py`

**Interfaces:**
- **Consumes:** `mrs_build.parse_cproject`, `mrs_build.build`, `BuildConfig.virtual` (Task 1); `check_image.check(hex, start, end, elf=None, stack_top=None) -> list[str]`.
- **Produces:**
  - `projects.Project(folder, name, template, links, lists={}, sources=None)`;
  - `projects.project_xml(p) -> str` and `projects.cproject_xml(p) -> str`;
  - `projects.generate(p) -> dict`;
  - `projects.PROJECTS: list[Project]` (JUMPIAP and IAP now; NODE is appended in Task 3);
  - helpers `projects.ws(path) -> str` and `projects.MESH`.

- [ ] **Step 1: Write the failing test.** Create `firmware/test_projects.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails.**

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub && python -m unittest discover -s firmware -p "test_projects.py" 2>&1 | tail -3`

Expected: FAILED with `ModuleNotFoundError: No module named 'projects'`.

- [ ] **Step 3: Create `firmware/projects.py`**

```python
"""Single description of the firmware projects; generates their MounRiver/Eclipse project files.

    python firmware/projects.py      # rewrite firmware/<project>/.project and .cproject

Each .cproject is the matching WCH SDK example's .cproject with our option lists substituted. Each .project
links the SDK folders and files the project compiles, in WCH's own PARENT-n-PROJECT_LOC form.
"""
import os
import re
import sys
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = r"C:\Embedded\WCH\SDK\CH585EVT\EVT\EXAM"
SDK_FROM_PROJECT = "PARENT-4-PROJECT_LOC/SDK/CH585EVT/EVT/EXAM"   # firmware/<project> -> C:\Embedded\WCH
MESH = "BLE/MESH"
OPT = "ilg.gnumcueclipse.managedbuild.cross.riscv.option."

PROJECT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<projectDescription>
\t<name>{name}</name>
\t<comment/>
\t<projects>
\t</projects>
\t<buildSpec>
\t\t<buildCommand>
\t\t\t<name>org.eclipse.cdt.managedbuilder.core.genmakebuilder</name>
\t\t\t<triggers>clean,full,incremental,</triggers>
\t\t\t<arguments>
\t\t\t</arguments>
\t\t</buildCommand>
\t\t<buildCommand>
\t\t\t<name>org.eclipse.cdt.managedbuilder.core.ScannerConfigBuilder</name>
\t\t\t<triggers>full,incremental,</triggers>
\t\t\t<arguments>
\t\t\t</arguments>
\t\t</buildCommand>
\t</buildSpec>
\t<natures>
\t\t<nature>org.eclipse.cdt.core.cnature</nature>
\t\t<nature>org.eclipse.cdt.managedbuilder.core.managedBuildNature</nature>
\t\t<nature>org.eclipse.cdt.managedbuilder.core.ScannerConfigNature</nature>
\t</natures>
\t<linkedResources>
{links}\t</linkedResources>
</projectDescription>
"""
LINK_XML = "\t\t<link>\n\t\t\t<name>{name}</name>\n\t\t\t<type>{type}</type>\n\t\t\t<locationURI>{uri}</locationURI>\n\t\t</link>\n"


@dataclass
class Project:
    folder: str          # firmware/<folder>
    name: str            # Eclipse project name
    template: str        # SDK example under BLE/MESH whose .cproject is the base
    links: list          # [(virtual name, SDK-relative path with '/')]; folder or file is read from the SDK
    lists: dict = field(default_factory=dict)   # .cproject list options to replace: key after OPT -> values
    sources: list = None                         # [(sourcePath name, excluding or None)]; None keeps the template's


def ws(path):
    """A project-relative path as MounRiver writes it in include and library lists."""
    return '"${workspace_loc:/${ProjName}/' + path + '}"'


def _check_sdk_reachable(folder):
    base = os.path.join(HERE, folder)
    for _ in range(4):
        base = os.path.dirname(base)
    if os.path.normcase(os.path.join(base, "SDK", "CH585EVT", "EVT", "EXAM")) != os.path.normcase(SDK):
        raise RuntimeError("PARENT-4-PROJECT_LOC from firmware/<project> does not reach the WCH SDK; "
                           r"the repository must be at C:\Embedded\WCH\projects\CH584F_MeshHub")


def project_xml(p):
    _check_sdk_reachable(p.folder)
    links = []
    for name, sdk_path in p.links:
        real = os.path.join(SDK, *sdk_path.split("/"))
        if not os.path.exists(real):
            raise FileNotFoundError(real)
        links.append(LINK_XML.format(name=name, type=2 if os.path.isdir(real) else 1,
                                     uri=f"{SDK_FROM_PROJECT}/{sdk_path}"))
    return PROJECT_XML.format(name=p.name, links="".join(links))


def set_list_option(text, key, values):
    pattern = re.compile(r'(<option\b[^>]*?superClass="' + re.escape(OPT + key) + r'"[^>]*?)(?:/>|>.*?</option>)', re.S)

    def repl(m):
        opening = re.sub(r'IS_VALUE_EMPTY="(true|false)"', f'IS_VALUE_EMPTY="{"false" if values else "true"}"',
                         m.group(1))
        items = "".join(f'\n\t\t\t\t\t\t\t\t\t<listOptionValue builtIn="false" value="{escape(v, {chr(34): "&quot;"})}"/>'
                        for v in values)
        return f"{opening}>{items}\n\t\t\t\t\t\t\t\t</option>"

    new, count = pattern.subn(repl, text)
    if count == 0:
        raise ValueError(f"option {key} not found in the template .cproject")
    return new


def set_source_entries(text, entries):
    body = "".join(
        "\t\t\t\t\t\t<entry " + (f'excluding="{exc}" ' if exc else "")
        + f'flags="VALUE_WORKSPACE_PATH|RESOLVED" kind="sourcePath" name="{name}"/>\n'
        for name, exc in entries)
    new, count = re.subn(r"<sourceEntries>.*?</sourceEntries>",
                         lambda m: "<sourceEntries>\n" + body + "\t\t\t\t\t</sourceEntries>", text, flags=re.S)
    if count == 0:
        raise ValueError("sourceEntries not found in the template .cproject")
    return new


def cproject_xml(p):
    with open(os.path.join(SDK, *MESH.split("/"), p.template, ".cproject"), encoding="utf-8") as f:
        text = f.read()
    for key, values in p.lists.items():
        text = set_list_option(text, key, values)
    if p.sources is not None:
        text = set_source_entries(text, p.sources)
    return text


def generate(p):
    folder = os.path.join(HERE, p.folder)
    os.makedirs(folder, exist_ok=True)
    files = {".project": project_xml(p), ".cproject": cproject_xml(p)}
    for name, text in files.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return files


IAP_SDK = f"{MESH}/adv_vendor_self_provision_IAP"
JUMPIAP_SDK = f"{MESH}/adv_vendor_self_provision_JumpIAP"

IAP = Project(folder="iap", name="meshhub_iap", template="adv_vendor_self_provision_IAP",
              links=[("APP", f"{IAP_SDK}/APP"),
                     ("Startup", f"{IAP_SDK}/Startup"),
                     ("RVMSIS", "SRC/RVMSIS"),
                     ("StdPeriphDriver", "SRC/StdPeriphDriver")])

JUMPIAP = Project(folder="jumpiap", name="meshhub_jumpiap", template="adv_vendor_self_provision_JumpIAP",
                  links=[("APP", f"{JUMPIAP_SDK}/APP"),
                         ("Profile", f"{JUMPIAP_SDK}/Profile"),
                         ("Startup", f"{JUMPIAP_SDK}/Startup"),
                         ("HAL", "BLE/HAL"),
                         ("LIB", "BLE/LIB"),
                         ("RVMSIS", "SRC/RVMSIS"),
                         ("StdPeriphDriver", "SRC/StdPeriphDriver")])

PROJECTS = [JUMPIAP, IAP]


def main():
    for p in PROJECTS:
        generate(p)
        print(f"generated firmware/{p.folder}/.project and .cproject")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Create the owned linker scripts** (the WCH SDK copies with CH584 RAM)

```bash
cd /c/Embedded/WCH/projects/CH584F_MeshHub
M=/c/Embedded/WCH/SDK/CH585EVT/EVT/EXAM/BLE/MESH
mkdir -p firmware/iap/Ld firmware/jumpiap/Ld
cp "$M/adv_vendor_self_provision_IAP/Ld/Link.ld" firmware/iap/Ld/Link.ld
cp "$M/adv_vendor_self_provision_JumpIAP/Ld/Link.ld" firmware/jumpiap/Ld/Link.ld
sed -i 's|RAM (xrw) : ORIGIN = 0x20005000, LENGTH = 108K|RAM (xrw) : ORIGIN = 0x20005000, LENGTH = 76K /* CH584: 96 KB RAM; 0x20000000-0x20004FFF stays reserved for the ROM library */|' firmware/iap/Ld/Link.ld
sed -i 's|RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 128K|RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 96K /* CH584 */|' firmware/jumpiap/Ld/Link.ld
grep -c "LENGTH = 76K" firmware/iap/Ld/Link.ld; grep -c "LENGTH = 96K" firmware/jumpiap/Ld/Link.ld
```

Expected: `1` and `1`.

- [ ] **Step 5: Generate the project files, and ignore MounRiver's build folders**

```bash
cd /c/Embedded/WCH/projects/CH584F_MeshHub && python firmware/projects.py
printf 'firmware/out/\nfirmware/*/obj/\nfirmware/*/.mrs/\n' >> .gitignore
```

Expected: two `generated firmware/... and .cproject` lines.

- [ ] **Step 6: Run the test to verify it passes.**

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub && python -m unittest discover -s firmware -p "test_projects.py" > /tmp/t2.log 2>&1; echo "exit $?"; grep -E "^(Ran|OK|FAILED|FAIL:|ERROR:)" /tmp/t2.log`

Expected: `exit 0`, `Ran 5 tests`, `OK`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore firmware/projects.py firmware/test_projects.py firmware/iap firmware/jumpiap
git commit -m "feat(firmware): project generator and the IAP/JumpIAP projects (SDK linked, CH584 RAM)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Node project and skeleton firmware

**Files:**
- Modify: `firmware/projects.py` (add `NODE` and append it to `PROJECTS`)
- Create, by copying: `firmware/node/Ld/Link.ld` (CH584 RAM edit); `firmware/node/hal/include/{CONFIG.h,HAL.h,LED.h,RTC.h,SLEEP.h}` (WCH, with the CONFIG.h edits); `firmware/node/hal/include/KEY.h` and `firmware/node/hal/KEY.c` (WeAct); `firmware/node/src/app_mesh_config.c` and `firmware/node/src/app_mesh_config.h` (WCH, with the header edits)
- Create: `firmware/node/src/version.h`, `board.h`, `board.c`, `mesh_node.h`, `mesh_node.c`, `main.c`
- Create, generated: `firmware/node/.project`, `firmware/node/.cproject`
- Test: `firmware/test_node.py`

**Interfaces:**
- **Consumes:** `projects.Project`, `projects.ws`, `projects.MESH`, `projects.PROJECTS`, `projects.generate` (Task 2); `mrs_build` (Task 1); `check_image.check`, `check_image.symbol_value(elf, name) -> int | None`; `merge_hex.read_hex(path) -> dict[int, int]`.
- **Produces:**
  - `firmware/node` builds to `meshhub_node.hex` and `.elf`;
  - C functions `void board_init(void)`, `void board_led_set(bool on)`, `void board_boot_blink(void)` and `void mesh_node_init(void)`;
  - the constant `const uint8_t MESH_NODE_TEST_UUID[16]`, the ASCII bytes of `MeshHub-M1-test!`;
  - `version.h` with `FW_VERSION_MAJOR 1` and `FW_VERSION_MINOR 0`.

- [ ] **Step 1: Write the failing test.** Create `firmware/test_node.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails.**

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub && python -m unittest discover -s firmware -p "test_node.py" 2>&1 | tail -3`

Expected: FAILED. The errors are `FileNotFoundError`, because `firmware/node/.project` does not exist yet.

- [ ] **Step 3: Copy and edit the WCH and WeAct files**

```bash
cd /c/Embedded/WCH/projects/CH584F_MeshHub
SDK=/c/Embedded/WCH/SDK/CH585EVT/EVT/EXAM
EX=$SDK/BLE/MESH/adv_vendor_self_provision_with_peripheral
WEACT="/c/Embedded/WCH/WeActStudio.WCH-BLE-Core/Examples/CH584/ble/broadcaster/ble/HAL"
mkdir -p firmware/node/Ld firmware/node/hal/include firmware/node/src
cp "$EX/Ld/Link.ld" firmware/node/Ld/Link.ld
sed -i 's|RAM (xrw) : ORIGIN = 0x20005000, LENGTH = 108K|RAM (xrw) : ORIGIN = 0x20005000, LENGTH = 76K /* CH584: 96 KB RAM; 0x20000000-0x20004FFF stays reserved for the ROM library */|' firmware/node/Ld/Link.ld
for h in CONFIG.h HAL.h LED.h RTC.h SLEEP.h; do cp "$SDK/BLE/HAL/include/$h" firmware/node/hal/include/$h; done
cp "$WEACT/include/KEY.h" firmware/node/hal/include/KEY.h
cp "$WEACT/KEY.c" firmware/node/hal/KEY.c
sed -i 's/#define CHIP_ID\(\s*\)ID_CH585/#define CHIP_ID\1ID_CH584/' firmware/node/hal/include/CONFIG.h
sed -i 's/\(#define BLE_SNV\s\+\)TRUE/\1FALSE/' firmware/node/hal/include/CONFIG.h
cp "$EX/APP/app_mesh_config.c" firmware/node/src/app_mesh_config.c
cp "$EX/APP/include/app_mesh_config.h" firmware/node/src/app_mesh_config.h
sed -i -e 's/\(#define CONFIG_BLE_MESH_PROXY\s\+\)0\b/\11/' \
       -e 's/\(#define CONFIG_BLE_MESH_PB_GATT\s\+\)0\b/\11/' \
       -e 's/\(#define CONFIG_BLE_MESH_CFG_CLI\s\+\)1\b/\10/' \
       -e 's/\(#define CONFIG_MESH_UNSEG_LENGTH_DEF\s\+\)(221)/\1(7)/' \
       -e 's/\(#define CONFIG_MESH_RX_SDU_DEF\s\+\)(192)/\1(256)/' firmware/node/src/app_mesh_config.h
grep -c -E "#define CHIP_ID\s+ID_CH584|#define BLE_SNV\s+FALSE" firmware/node/hal/include/CONFIG.h
grep -c -E "#define CONFIG_BLE_MESH_PROXY\s+1|#define CONFIG_BLE_MESH_PB_GATT\s+1|#define CONFIG_BLE_MESH_CFG_CLI\s+0|#define CONFIG_MESH_UNSEG_LENGTH_DEF\s+\(7\)|#define CONFIG_MESH_RX_SDU_DEF\s+\(256\)" firmware/node/src/app_mesh_config.h
grep -c "LENGTH = 76K" firmware/node/Ld/Link.ld
```

Expected: `2`, `5` and `1`.

- [ ] **Step 4: Write the C sources.**

`firmware/node/src/version.h`:

```c
#ifndef VERSION_H
#define VERSION_H

#define FW_VERSION_MAJOR 1
#define FW_VERSION_MINOR 0

#endif
```

`firmware/node/src/board.h`:

```c
#ifndef BOARD_H
#define BOARD_H

#include <stdbool.h>

void board_init(void);
void board_led_set(bool on);
void board_boot_blink(void);

#endif
```

`firmware/node/src/board.c`:

```c
/* WeAct CH584F core board: LED on PB6, active low. */
#include "CONFIG.h"
#include "board.h"

#define BOARD_LED_PIN GPIO_Pin_6

void board_init(void)
{
    GPIOB_SetBits(BOARD_LED_PIN);
    GPIOB_ModeCfg(BOARD_LED_PIN, GPIO_ModeOut_PP_5mA);
}

void board_led_set(bool on)
{
    if(on)
    {
        GPIOB_ResetBits(BOARD_LED_PIN);
    }
    else
    {
        GPIOB_SetBits(BOARD_LED_PIN);
    }
}

void board_boot_blink(void)
{
    board_led_set(true);
    mDelaymS(100);
    board_led_set(false);
}
```

`firmware/node/src/mesh_node.h`:

```c
#ifndef MESH_NODE_H
#define MESH_NODE_H

#include <stdint.h>

extern const uint8_t MESH_NODE_TEST_UUID[16];

void mesh_node_init(void);

#endif
```

`firmware/node/src/mesh_node.c`:

```c
/* Bluetooth mesh set-up, M1 skeleton (spec step 1, sections 4 and 7.6).
 * Composition: Config Server and Health Server. The WCH vendor server is added in M4.
 * Unprovisioned: unprovisioned beacon and PB-GATT advertising with a fixed test UUID.
 * M2 replaces the test UUID with the factory page's UUID and adds static OOB and the provisioning window.
 * Init sequence as in WCH's adv_proxy and adv_vendor_self_provision_with_peripheral examples. */
#include "CONFIG.h"
#include "MESH_LIB.h"
#include "HAL.h"
#include "app_mesh_config.h"
#include "mesh_node.h"

/* ASCII "MeshHub-M1-test!" */
const uint8_t MESH_NODE_TEST_UUID[16] = {0x4D, 0x65, 0x73, 0x68, 0x48, 0x75, 0x62, 0x2D,
                                         0x4D, 0x31, 0x2D, 0x74, 0x65, 0x73, 0x74, 0x21};

static uint8_t MESH_MEM[1024 * 3] = {0};
extern const ble_mesh_cfg_t app_mesh_cfg;
extern const struct device  app_dev;

static uint8_t dev_uuid[16];
static uint8_t mac_addr[6];

static void cfg_srv_rsp_handler(const cfg_srv_status_t *val);
static void link_open(bt_mesh_prov_bearer_t bearer);
static void link_close(bt_mesh_prov_bearer_t bearer, uint8_t reason);
static void prov_complete(uint16_t net_idx, uint16_t addr, uint8_t flags, uint32_t iv_index);
static void prov_reset(void);

static struct bt_mesh_cfg_srv cfg_srv = {
    .relay = BLE_MESH_RELAY_ENABLED,
    .beacon = BLE_MESH_BEACON_ENABLED,
#if(CONFIG_BLE_MESH_PROXY)
    .gatt_proxy = BLE_MESH_GATT_PROXY_ENABLED,
#endif
    .default_ttl = 5,
    .net_transmit = BLE_MESH_TRANSMIT(7, 10),
    .relay_retransmit = BLE_MESH_TRANSMIT(7, 10),
    .handler = cfg_srv_rsp_handler,
};

static struct bt_mesh_health_srv health_srv;
BLE_MESH_HEALTH_PUB_DEFINE(health_pub, 8);

uint16_t cfg_srv_keys[CONFIG_MESH_MOD_KEY_COUNT_DEF] = {BLE_MESH_KEY_UNUSED};
uint16_t cfg_srv_groups[CONFIG_MESH_MOD_GROUP_COUNT_DEF] = {BLE_MESH_ADDR_UNASSIGNED};
uint16_t health_srv_keys[CONFIG_MESH_MOD_KEY_COUNT_DEF] = {BLE_MESH_KEY_UNUSED};
uint16_t health_srv_groups[CONFIG_MESH_MOD_GROUP_COUNT_DEF] = {BLE_MESH_ADDR_UNASSIGNED};

static struct bt_mesh_model root_models[] = {
    BLE_MESH_MODEL_CFG_SRV(cfg_srv_keys, cfg_srv_groups, &cfg_srv),
    BLE_MESH_MODEL_HEALTH_SRV(health_srv_keys, health_srv_groups, &health_srv, &health_pub),
};

static struct bt_mesh_elem elements[] = {
    {
        .loc = (0),
        .model_count = ARRAY_SIZE(root_models),
        .models = (root_models),
    }
};

const struct bt_mesh_comp app_comp = {
    .cid = 0x07D7, /* WCH */
    .elem = elements,
    .elem_count = ARRAY_SIZE(elements),
};

static const struct bt_mesh_prov app_prov = {
    .uuid = dev_uuid,
    .link_open = link_open,
    .link_close = link_close,
    .complete = prov_complete,
    .reset = prov_reset,
};

static void prov_enable(void)
{
    if(bt_mesh_is_provisioned())
    {
        return;
    }
    bt_mesh_scan_enable();
    bt_mesh_beacon_enable();
    if(CONFIG_BLE_MESH_PB_GATT)
    {
        bt_mesh_proxy_prov_enable();
    }
}

static void cfg_srv_rsp_handler(const cfg_srv_status_t *val)
{
    APP_DBG("config status %d", val->cfgHdr.status);
}

static void link_open(bt_mesh_prov_bearer_t bearer)
{
    APP_DBG("bearer %d", bearer);
}

static void link_close(bt_mesh_prov_bearer_t bearer, uint8_t reason)
{
    APP_DBG("reason %x", reason);
    if(!bt_mesh_is_provisioned())
    {
        prov_enable();
    }
}

static void prov_complete(uint16_t net_idx, uint16_t addr, uint8_t flags, uint32_t iv_index)
{
    APP_DBG("provisioned, address 0x%04x", addr);
}

static void prov_reset(void)
{
    prov_enable();
}

void mesh_node_init(void)
{
    int        err;
    mem_info_t info;

    info.base_addr = MESH_MEM;
    info.mem_len = ARRAY_SIZE(MESH_MEM);
    GetMACAddress(mac_addr);
    tmos_memcpy(dev_uuid, MESH_NODE_TEST_UUID, sizeof(dev_uuid));

    err = bt_mesh_cfg_set(&app_mesh_cfg, &app_dev, mac_addr, &info);
    if(err)
    {
        APP_DBG("Unable set configuration (err:%d)", err);
        return;
    }
    hal_rf_init();
    err = bt_mesh_comp_register(&app_comp);
    bt_mesh_relay_init();
    bt_mesh_proxy_beacon_init_register((void *)bt_mesh_proxy_beacon_init);
    gatts_notify_register(bt_mesh_gatts_notify);
    proxy_gatt_enable_register(bt_mesh_proxy_gatt_enable);
    proxy_prov_enable_register(bt_mesh_proxy_prov_enable);
    bt_mesh_proxy_init();
    bt_mesh_prov_retransmit_init();
    err = bt_mesh_prov_init(&app_prov);
    bt_mesh_mod_init();
    bt_mesh_net_init();
    bt_mesh_trans_init();
    bt_mesh_beacon_init();
    bt_mesh_adv_init();
    bt_mesh_conn_adv_init();
    bt_mesh_settings_init();
    bt_mesh_adapt_init();
    if(err)
    {
        APP_DBG("Initializing mesh failed (err %d)", err);
        return;
    }
    settings_load();
    if(!bt_mesh_is_provisioned())
    {
        prov_enable();
    }
}
```

`firmware/node/src/main.c`:

```c
/* MeshHub node start-up (spec step 1, section 4). Based on WCH's adv_vendor_self_provision_with_peripheral
 * app_main.c, with the board settings from the Step 0 spike (DC-DC call, 10 pF crystal capacitors). */
#include "CONFIG.h"
#include "MESH_LIB.h"
#include "HAL.h"
#include "app_mesh_config.h"
#include "board.h"
#include "mesh_node.h"

_Static_assert(CHIP_ID == ID_CH584, "hal/include/CONFIG.h must target the CH584");
_Static_assert(BLE_SNV == FALSE, "BLE SNV must be off: DataFlash 0x7000 is the OTA ImageFlag");
_Static_assert(DCDC_ENABLE == TRUE, "the project must define DCDC_ENABLE=1");

__attribute__((aligned(4))) uint32_t MEM_BUF[BLE_MEMHEAP_SIZE / 4];

__HIGH_CODE
__attribute__((noinline))
void Main_Circulation(void)
{
    while(1)
    {
        TMOS_SystemProcess();
    }
}

static uint8_t mesh_lib_init(void)
{
    uint8_t ret;

    if(tmos_memcmp(VER_MESH_LIB, VER_MESH_FILE, strlen(VER_MESH_FILE)) == FALSE)
    {
        PRINT("mesh head file error...\n");
        while(1);
    }
    ret = RF_RoleInit();
    hal_rf_tx_wait_enable(ENABLE);
    ret = GAPRole_PeripheralInit(); /* the proxy and PB-GATT need the peripheral role */
    MeshTimer_Init();
    MeshDeamon_Init();
    ble_sm_alg_ecc_init();
    return ret;
}

int main(void)
{
    PWR_DCDCCfg(ENABLE);            /* DCDC_ENABLE alone does nothing (Step 0 spike) */
    HSECFG_Capacitance(HSECap_10p); /* WeAct CH584F core board crystal */
    SetSysClock(SYSCLK_FREQ);
#ifdef DEBUG
    GPIOA_SetBits(GPIO_Pin_14);
    GPIOPinRemap(ENABLE, RB_PIN_UART0);
    GPIOA_ModeCfg(GPIO_Pin_15, GPIO_ModeIN_PU);
    GPIOA_ModeCfg(GPIO_Pin_14, GPIO_ModeOut_PP_5mA);
    UART0_DefInit();
#endif
    board_init();
    board_boot_blink();
    PRINT("%s\n", VER_LIB);
    PRINT("%s\n", VER_MESH_LIB);
    CH58x_BLEInit();
    HAL_Init();
    mesh_lib_init();
    mesh_node_init();
    Main_Circulation();
}
```

- [ ] **Step 5: Describe the node project and generate its files.** In `firmware/projects.py`, insert before `PROJECTS = [JUMPIAP, IAP]`:

```python
NODE_SDK = f"{MESH}/adv_vendor_self_provision_with_peripheral"

NODE = Project(
    folder="node", name="meshhub_node", template="adv_vendor_self_provision_with_peripheral",
    links=[("Startup", f"{NODE_SDK}/Startup"),
           ("sdk_hal", "BLE/HAL"),
           ("LIB", "BLE/LIB"),
           ("MESH_LIB", f"{MESH}/MESH_LIB"),
           ("RVMSIS", "SRC/RVMSIS"),
           ("StdPeriphDriver", "SRC/StdPeriphDriver")],
    lists={
        "c.compiler.defs": ["DEBUG=0", "BLE_BUFF_MAX_LEN=251", "LIB_FLASH_BASE_ADDRESSS=0x0004E000", "CH58xBLE_ROM",
                            "BLE_MEMHEAP_SIZE=5632", "HAL_KEY=1", "CLK_OSC32K=0", "DCDC_ENABLE=1"],
        "assembler.defs": ["LIB_FLASH_BASE_ADDRESSS=0x0004E000"],
        "c.compiler.include.paths": [ws("hal/include"), ws("src"), ws("StdPeriphDriver/inc"), ws("RVMSIS"),
                                     ws("LIB"), ws("MESH_LIB")],
        "c.linker.libs": ["ISP585", "CH58xMESHROM"],
        "c.linker.paths": ['"../"', ws("MESH_LIB"), ws("LIB"), ws("StdPeriphDriver")],
    },
    sources=[("src", None), ("hal", None), ("sdk_hal", "KEY.c"), ("Startup", None), ("StdPeriphDriver", None),
             ("RVMSIS", None), ("LIB", None)])
```

Change `PROJECTS = [JUMPIAP, IAP]` to `PROJECTS = [JUMPIAP, NODE, IAP]`. Then run:

```bash
cd /c/Embedded/WCH/projects/CH584F_MeshHub && python firmware/projects.py
```

Expected: three `generated ...` lines.

- [ ] **Step 6: Run the node and project tests to verify they pass.**

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub && python -m unittest discover -s firmware -p "test_*.py" > /tmp/t3.log 2>&1; echo "exit $?"; grep -E "^(Ran|OK|FAILED|FAIL:|ERROR:)|error:" /tmp/t3.log`

Expected: `exit 0`, `Ran 14 tests`, `OK`. If a compile error appears, it is printed with its file and line. Fix the source; do not change the tests.

- [ ] **Step 7: Commit**

```bash
git add firmware/projects.py firmware/test_node.py firmware/node
git commit -m "feat(firmware): node skeleton: own sources, SDK linked, CH584 board settings, unprovisioned advertising

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Build, check and package (`firmware/build.py`)

**Files:**
- Create: `firmware/build.py`
- Test: `firmware/test_build.py`

**Interfaces:**
- **Consumes:**
  - `mrs_build.parse_cproject`, `mrs_build.build`, `mrs_build.DEFAULT_TOOLCHAIN`, `mrs_build.BuildError`;
  - `check_image.check`;
  - `merge_hex.merge(parts) -> dict` (raises `ValueError("overlap at 0x.....")`), `read_hex`, `write_hex(mem, path)`;
  - the projects from Tasks 2 and 3.
- **Produces:**
  - `build.IMAGES: dict[str, tuple[folder, start, end, check_stack]]`;
  - `build.read_version(path=...) -> tuple[int, int]`;
  - `build.build_all(out_dir, images=IMAGES, toolchain=...) -> dict[name, {"elf","hex","map"}]`;
  - `build.package(hexes: dict[name, hex path], rom_hex, out_hex) -> str`;
  - `build.check_rom_file(path)`;
  - `build.FirmwareError`;
  - CLI `python firmware/build.py`, which writes `firmware/out/meshhub-1.0.hex`.

- [ ] **Step 1: Write the failing test.** Create `firmware/test_build.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails.**

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub && python -m unittest discover -s firmware -p "test_build.py" 2>&1 | tail -3`

Expected: FAILED with `ModuleNotFoundError: No module named 'build'`.

- [ ] **Step 3: Create `firmware/build.py`**

```python
"""Build, check and package the MeshHub firmware.

    python firmware/build.py      -> firmware/out/meshhub-<major>.<minor>.hex

Layout (system spec 6.2): JumpIAP 0x00000 | node (application) 0x01000 | IAP 0x4D000 | CH584 ROM library 0x4E000
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import check_image  # noqa: E402
import mrs_build  # noqa: E402
from merge_hex import merge, read_hex, write_hex  # noqa: E402

ROM_HEX = r"C:\Embedded\WCH\SDK\CH585EVT\EVT\EXAM\BLE\MESH\MESH_LIB\CH584BLE_ROM_MESH.hex"
ROM_REGION = (0x4E000, 0x70000)
STACK_TOP = 0x20018000
# name: (folder under firmware/, flash start, flash end (exclusive), check the stack top)
IMAGES = {"jumpiap": ("jumpiap", 0x00000, 0x01000, False),
          "node": ("node", 0x01000, 0x27000, True),
          "iap": ("iap", 0x4D000, 0x4E000, True)}


class FirmwareError(Exception):
    pass


def read_version(path=os.path.join(HERE, "node", "src", "version.h")):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    major = re.search(r"#define FW_VERSION_MAJOR\s+(\d+)", text)
    minor = re.search(r"#define FW_VERSION_MINOR\s+(\d+)", text)
    if not (major and minor):
        raise FirmwareError(f"FW_VERSION_MAJOR/FW_VERSION_MINOR not found in {path}")
    return int(major.group(1)), int(minor.group(1))


def build_all(out_dir, images=IMAGES, toolchain=mrs_build.DEFAULT_TOOLCHAIN):
    """Build every image into a fresh out_dir and check it. Returns {name: {"elf", "hex", "map"}}."""
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    paths = {}
    for name, (folder, start, end, stack) in images.items():
        cfg = mrs_build.parse_cproject(os.path.join(HERE, folder))
        p = mrs_build.build(cfg, os.path.join(out_dir, name), toolchain, [])
        errors = check_image.check(p["hex"], start, end, elf=p["elf"] if stack else None,
                                   stack_top=STACK_TOP if stack else None)
        if errors:
            raise FirmwareError(f"{name}: " + "; ".join(errors))
        paths[name] = p
    return paths


def check_rom_file(path):
    if "CH584" not in os.path.basename(path):
        raise FirmwareError(f"ROM library must be the CH584 build, got {os.path.basename(path)}")


def _in_region(name, mem, start, end):
    if min(mem) < start or max(mem) >= end:
        raise FirmwareError(f"{name}: 0x{min(mem):05X}-0x{max(mem):05X} outside 0x{start:05X}-0x{end - 1:05X}")
    return mem


def package(hexes, rom_hex, out_hex):
    """Merge {image name: hex path} and the ROM library into one WCHISPTool object file."""
    check_rom_file(rom_hex)
    parts = [_in_region(name, read_hex(path), IMAGES[name][1], IMAGES[name][2]) for name, path in hexes.items()]
    parts.append(_in_region("rom", read_hex(rom_hex), *ROM_REGION))
    try:
        merged = merge(parts)
    except ValueError as e:
        raise FirmwareError(str(e))
    os.makedirs(os.path.dirname(os.path.abspath(out_hex)), exist_ok=True)
    write_hex(merged, out_hex)
    return out_hex


def main():
    out = os.path.join(HERE, "out")
    try:
        paths = build_all(os.path.join(out, "build"))
        major, minor = read_version()
        pkg = package({n: p["hex"] for n, p in paths.items()}, ROM_HEX,
                      os.path.join(out, f"meshhub-{major}.{minor}.hex"))
    except (FirmwareError, mrs_build.BuildError) as e:
        print(f"FIRMWARE BUILD FAILED: {e}")
        return 1
    for name, p in paths.items():
        mem = read_hex(p["hex"])
        print(f"  {name}: {len(mem):,} bytes at 0x{min(mem):05X}-0x{max(mem):05X}")
    mem = read_hex(pkg)
    print(f"{pkg}: {len(mem):,} bytes at 0x{min(mem):05X}-0x{max(mem):05X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass, then build the package.**

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub && python -m unittest discover -s firmware -p "test_build.py" > /tmp/t4.log 2>&1; echo "exit $?"; grep -E "^(Ran|OK|FAILED|FAIL:|ERROR:)" /tmp/t4.log; python firmware/build.py | tail -4`

Expected:
- `exit 0`, `Ran 6 tests`, `OK`;
- then three image lines: jumpiap at `0x00000`, node at `0x01000`, iap at `0x4D000`;
- then `...firmware\out\meshhub-1.0.hex: N bytes at 0x00000-0x6D6C3`. The highest address is the end of the ROM library.

- [ ] **Step 5: Commit**

```bash
git add firmware/build.py firmware/test_build.py
git commit -m "feat(firmware): build, check and package script (meshhub-1.0.hex)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Laptop scan tool, README and the M1 hardware check

**Files:**
- Create: `tools/mesh_scan.py`, `firmware/README.md`, `firmware/RESULTS.md`
- Test: `tools/test_mesh_scan.py`

**Interfaces:**
- **Consumes:** `firmware/out/meshhub-1.0.hex` (Task 4); bleak.
- **Produces:**
  - `mesh_scan.describe(service_data: dict) -> list[str]`, where `service_data` maps a UUID string to bytes;
  - `mesh_scan.PROV` and `mesh_scan.PROXY`;
  - CLI `python tools/mesh_scan.py [seconds]`.

- [ ] **Step 1: Write the failing test.** Create `tools/test_mesh_scan.py`:

```python
import unittest

import mesh_scan


class DescribeTests(unittest.TestCase):
    def test_unprovisioned_device(self):
        data = {mesh_scan.PROV.upper(): bytes.fromhex("4d6573684875622d4d312d7465737421" "0000")}
        self.assertEqual(mesh_scan.describe(data),
                         ["UNPROVISIONED 0x1827: device UUID 4d6573684875622d4d312d7465737421 OOB info 0000"])

    def test_provisioned_proxy(self):
        data = {mesh_scan.PROXY: bytes.fromhex("00" "5a9a06c58f8949d3")}
        self.assertEqual(mesh_scan.describe(data), ["PROXY 0x1828: Network ID 5a9a06c58f8949d3"])

    def test_other_devices_give_nothing(self):
        self.assertEqual(mesh_scan.describe({"0000180f-0000-1000-8000-00805f9b34fb": b"\x64"}), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails.**

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub/tools && python -m unittest test_mesh_scan 2>&1 | tail -3`

Expected: FAILED with `ModuleNotFoundError: No module named 'mesh_scan'`.

- [ ] **Step 3: Create `tools/mesh_scan.py`**

```python
"""Scan for Bluetooth mesh devices with the laptop's adapter (bleak).

    python tools/mesh_scan.py [seconds]

Prints unprovisioned devices (Mesh Provisioning 0x1827: device UUID and OOB info) and provisioned proxies
(Mesh Proxy 0x1828: Network ID or Node Identity).
"""
import asyncio
import sys

PROV = "00001827-0000-1000-8000-00805f9b34fb"
PROXY = "00001828-0000-1000-8000-00805f9b34fb"


def describe(service_data):
    """Readable lines for one advertisement's service data {UUID string: bytes}."""
    sd = {k.lower(): bytes(v) for k, v in service_data.items()}
    lines = []
    if PROV in sd:
        d = sd[PROV]
        lines.append(f"UNPROVISIONED 0x1827: device UUID {d[:16].hex()} OOB info {d[16:18].hex()}")
    if PROXY in sd:
        d = sd[PROXY]
        kind = {0: "Network ID", 1: "Node Identity"}.get(d[0], f"type {d[0]}") if d else "empty"
        lines.append(f"PROXY 0x1828: {kind} {d[1:].hex()}")
    return lines


async def scan(seconds):
    from bleak import BleakScanner
    found = {}

    def on_advertisement(device, adv):
        lines = describe(adv.service_data or {})
        if lines:
            found[device.address] = (adv.rssi, lines)

    scanner = BleakScanner(detection_callback=on_advertisement)
    await scanner.start()
    await asyncio.sleep(seconds)
    await scanner.stop()
    return found


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    seconds = float(argv[0]) if argv else 10.0
    found = asyncio.run(scan(seconds))
    print(f"{len(found)} mesh device(s) in {seconds:g} s")
    for address, (rssi, lines) in sorted(found.items()):
        print(f"- {address}  RSSI {rssi} dBm")
        for line in lines:
            print("    " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run it to verify it passes.**

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub/tools && python -m unittest test_mesh_scan 2>&1 | tail -3`

Expected: `Ran 3 tests`, `OK`.

- [ ] **Step 5: Write `firmware/README.md`**

```markdown
# MeshHub firmware

Board firmware for the CH584F Mesh Hub (spec: `docs/specs/2026-10-04-step1-firmware-design.md`).

## Layout

| Folder | Content |
|---|---|
| `node/` | The product application. `src/` and `hal/` are ours; WCH SDK parts are linked from `C:\Embedded\WCH\SDK\CH585EVT`. |
| `iap/`, `jumpiap/` | WCH's installer and jump stub, linked from the SDK, with CH584 RAM in `Ld/Link.ld` |
| `projects.py` | The single description of the three projects. It generates their `.project` and `.cproject`. |
| `build.py` | Builds and checks all three images, then packages them with the CH584 ROM library |

## Build

    python firmware/build.py

Output: `firmware/out/meshhub-1.0.hex`. After changing `projects.py`, run `python firmware/projects.py`. The test
`test_projects.py` fails if the committed project files differ from the generator.

## Flash (WCHISPTool v4.0)

**The user flashes, and only with explicit approval.**

1. CH58x → CH584 → USB. Untick **Automatic Download**. Tick **Clear DataFlash**.
2. Object File 1: `firmware/out/meshhub-1.0.hex`. From M2 onwards, also load the board's DataFlash file.
3. Hold BOOT while plugging in USB, then **Download**.

Clear DataFlash removes any provisioning, so delete the old node in nRF Mesh before provisioning it again.

## Check

    python tools/mesh_scan.py 10

M1 boards advertise `UNPROVISIONED 0x1827: device UUID 4d6573684875622d4d312d7465737421` (ASCII `MeshHub-M1-test!`).
```

- [ ] **Step 6: Commit the tool and README**

```bash
git add tools/mesh_scan.py tools/test_mesh_scan.py firmware/README.md
git commit -m "feat(tools): mesh_scan laptop scanner; firmware README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Hardware check (the user flashes one board).**
  1. **Ask the user for approval** to flash one board with `firmware/out/meshhub-1.0.hex`, with Clear DataFlash ticked and no DataFlash file. Explain that the board's current spike firmware and its nRF Mesh provisioning will be replaced. Wait for a clear yes.
  2. The user flashes, then power-cycles the board. **Expected:** the LED gives one short (100 ms) blink at power-up, then stays off.
  3. Run `cd /c/Embedded/WCH/projects/CH584F_MeshHub && python tools/mesh_scan.py 10`. **Expected:** the board's address with `UNPROVISIONED 0x1827: device UUID 4d6573684875622d4d312d7465737421 OOB info 0000`.
  4. Do **not** provision the board. M1 has no static OOB; M2 adds it.

- [ ] **Step 8: Record the results.** Create `firmware/RESULTS.md`, filling the Observation column with the exact values seen:

```markdown
# Step 1 firmware results

| ID | Milestone | Check | Result | Observation |
|---|---|---|---|---|
| M1-1 | M1 | Build checks: node within 0x01000-0x26FFF with stack top 0x20018000; IAP within 0x4D000-0x4DFFF; JumpIAP within 0x00000-0x00FFF; package without overlaps | | |
| M1-2 | M1 | Boot: one 100 ms LED blink, then off | | |
| M1-3 | M1 | Laptop scan: 0x1827 with device UUID 4d6573684875622d4d312d7465737421 | | |
```

Then commit:

```bash
git add firmware/RESULTS.md
git commit -m "docs(firmware): record M1 hardware check

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 9: Run every suite.**

Run: `cd /c/Embedded/WCH/projects/CH584F_MeshHub && for s in tools firmware spike; do python -m unittest discover -s $s -p "test_*.py" > /tmp/all_$s.log 2>&1; echo "$s exit $? $(grep -E '^(Ran|OK|FAILED)' /tmp/all_$s.log | tr '\n' ' ')"; done`

Expected:
- `tools exit 0 Ran 27 tests OK` (17 existing + 7 from Task 1 + 3 from Task 5);
- `firmware exit 0 Ran 20 tests OK`;
- `spike exit 0 Ran 12 tests OK`.
