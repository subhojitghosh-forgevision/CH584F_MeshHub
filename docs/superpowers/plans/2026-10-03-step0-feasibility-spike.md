# Step 0 — Feasibility Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer the spec's six feasibility questions (S1–S6) on one WeAct CH584F board. The output is a go/no-go report and proposed spec amendments. All spike firmware is throwaway.

**Architecture:** The plan builds a small, reusable build tool that reads a `.cproject` file, plus two helpers that check and merge hex files. A script assembles WCH's three update-capable mesh projects (node, IAP, JumpIAP) from the SDK and applies the CH584 and WeAct board changes. On top of those it adds the spike features: GATT provisioning (PB-GATT), mesh proxy, static OOB, a test publisher, and a version blink. The user flashes one merged image, then tests with the off-the-shelf **nRF Mesh** app. A version-2 image preloaded in the update buffer tests the CH584 install path without needing an OTA app.

**Tech Stack:** Python 3.12 (standard library only, `unittest`); the GCC 12 toolchain bundled with MounRiver Studio 2 V2.5.0 (`riscv-wch-elf-*`); the WCH CH585 EVT SDK (BLE lib V1.4, MESH lib V1.79); WCHISPTool v4.0; nRF Mesh for Android.

**Spec:** `docs/specs/2026-10-03-ch584f-mesh-hub-design.md` (sections 4, 5.2, 6, 7 and 11 are the ones this plan exercises)

## Global Constraints

- Repository root: `C:\Embedded\WCH\projects\CH584F_MeshHub` (Git Bash: `/c/Embedded/WCH/projects/CH584F_MeshHub`). All commands run from there unless stated otherwise.
- SDK: `C:\Embedded\WCH\SDK\CH585EVT\EVT\EXAM`. **Never modify the SDK.** Copy from it.
- Toolchain bin: `C:\MounRiver\MounRiver_Studio2\resources\app\resources\win32\components\WCH\Toolchain\RISC-V Embedded GCC12\bin` (`riscv-wch-elf-gcc` 12.2.0).
- MRS2 flag translation (copied verbatim from MRS2 V2.5.0):
  - `-march=rv32imc_zba_zbb_zbc_zbs_xw`, `-mabi=ilp32`
  - `-Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common`
  - `--param=highcode-gen-section-name=1`, `-g`
- CH584 RAM is **96 KB**: `0x20000000`–`0x20017FFF`. The stack top must be `0x20018000`.
- WCH OTA layout:
  - JumpIAP `0x00000` (4 KB)
  - application `0x01000` (152 KB)
  - update buffer `0x27000` (152 KB)
  - IAP `0x4D000` (4 KB)
  - BLE+mesh ROM library `0x4E000` (136 KB, file `CH584BLE_ROM_MESH.hex`)
- Vendor model: CID `0x07D7`, server model `0x0000`. Opcodes `WRT 0xCC`, `ACK 0xCD`, `MSG 0xCF`. TIDs: client 0–127, server 128–191.
- Mesh settings: `CONFIG_MESH_UNSEG_LENGTH_DEF` **7**; `CONFIG_MESH_RX_SDU_DEF` **256**. Groups: `0xC000` (all boards), `0xC001` (readings).
- Board:
  - LED **PB6, active low** (ON = `GPIOB_ResetBits`)
  - BOOT key PB22
  - `HSECFG_Capacitance(HSECap_10p)`
  - defines `CLK_OSC32K=0`, `DCDC_ENABLE=1`, **plus a real `PWR_DCDCCfg(ENABLE)` call in `main()`**
- **Flashing needs the user's explicit approval in chat.** Only the user flashes, with WCHISPTool (CH58x → CH584 → USB, tick *Clear DataFlash*, untick *Automatic Download When Device Connect*).
- File creation: the Write/Edit tools are blocked outside the workspace.
  - Create files under `C:\Embedded` with the Bash tool and a quoted heredoc (`cat > path <<'EOF' … EOF`). **Heredoc bodies must not contain apostrophes**, because the harness misparses them.
  - Alternatively, write the file to the session scratchpad with the Write tool, then `cp` it into place.
  - Keep Windows line endings out of Python files: write them as LF.
- Commit after each task. Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Spike code lives under `spike/`. Generated project copies and build output are git-ignored; scripts, docs and results are committed.

## Review Focus

1. **A reused TID is silently ignored.** The WCH server drops a message whose (TID, source) matches the previous one, so a hand-typed test that repeats a TID looks like a failure. Pinned by Task 6 step 6 (duplicate-TID negative test) and by the TID column in the test script.
2. **A wrong static OOB must fail provisioning.** If the board accepted any OOB, "secure commissioning" would be fake. Pinned by Task 6 step 2 (wrong-OOB negative test, which must fail before the correct-OOB test).
3. **Stale DataFlash after reflashing** (old mesh data, or a stray OTA image flag at DataFlash `0x7000`) makes the board boot provisioned or jump wrongly. Pinned by Task 5 (Clear DataFlash is mandatory in FLASHING.md) and Task 6 step 1 (the board must show as *unprovisioned* before anything else).
4. **The wrong-chip ROM library** (`CH585BLE_ROM_MESH.hex` on a CH584) or overlapping images break boot. Pinned by Task 5's packaging test (file name must contain `CH584`; ranges must not overlap) and by Task 2's overlap test.
5. **CH585 RAM sizes left in any of the three projects** (108 KB/128 KB) put the stack in non-existent RAM. Pinned by Task 3's assembler test (RAM lines) and by the `check_image.py --stack-top 0x20018000` runs.

---

### Task 1: Repository scaffolding and the `.cproject`-driven build tool

**Files:**
- Create: `.gitignore`
- Create: `tools/mrs_build.py`
- Test: `tools/test_mrs_build.py`

**Interfaces:**
- Consumes: nothing from earlier tasks. The regression oracles are the already-verified hex files:
  - `C:\Embedded\WCH\projects\CH584F_Mesh_Relay_LED`: SHA-256 `2a942bdf4dbc5ba64934b1884aa9a401dc47f078e098aa1919e6ef29dca20491`
  - `C:\Embedded\WCH\projects\CH584F_BLE_LED`: SHA-256 `a1d5e197fa85a45bf372492e11e80262adaf811abdea1b50e866fd693d421ca7`
- Produces:
  - `mrs_build.parse_cproject(project_dir: str) -> BuildConfig`
  - `mrs_build.build(cfg: BuildConfig, out_dir: str, toolchain: str, extra_defines: list[str]) -> dict` with keys `"elf"`, `"hex"`, `"map"` (absolute paths). Output files are named `<cfg.name>.elf/.hex/.map`, where `cfg.name` is the `<name>` in `.project`.
  - `mrs_build.DEFAULT_TOOLCHAIN: str`
  - CLI: `python tools/mrs_build.py <project_dir> [--out DIR] [--define NAME=VALUE]... [--toolchain DIR]`

- [ ] **Step 1: Create `.gitignore`**

```bash
cd /c/Embedded/WCH/projects/CH584F_MeshHub
cat > .gitignore <<'EOF'
__pycache__/
spike/node/
spike/iap/
spike/jumpiap/
spike/build/
spike/out/
EOF
```

- [ ] **Step 2: Write the failing test** at `tools/test_mrs_build.py`

```python
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m unittest discover -s tools -p "test_*.py" -v`
Expected: ERROR `ModuleNotFoundError: No module named 'mrs_build'`

- [ ] **Step 4: Write the implementation** at `tools/mrs_build.py`

```python
"""Command-line build for WCH MounRiver projects (.cproject), using the toolchain
bundled with MounRiver Studio 2 V2.5.0.

.cproject options are translated the way MRS2 V2.5.0 does it
(resources/app/extensions/mrs-team.mrs-vscode/out/extension.js):
  -march = <isa.base> + m (isa.multiply) + a (isa.atomic) + f/fd/fdq (isa.fp) + c (isa.compressed)
           + _zba_zbb_zbc_zbs (isa.b) + _xw (isa.xw)   [WCH GCC12/GCC15]
  optimization.mrs.highcode -> --param=highcode-gen-section-name=1

Usage:
  python tools/mrs_build.py <project_dir> [--out DIR] [--define NAME=VALUE]... [--toolchain BIN_DIR]
"""
import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

DEFAULT_TOOLCHAIN = (r"C:\MounRiver\MounRiver_Studio2\resources\app\resources\win32\components"
                     r"\WCH\Toolchain\RISC-V Embedded GCC12\bin")
OPT = "ilg.gnumcueclipse.managedbuild.cross.riscv.option."
SOURCE_EXTS = (".c", ".S")
SKIP_DIRS = {"obj", ".mrs", ".settings", "__pycache__"}
OPT_LEVELS = {"none": "-O0", "optimize": "-O1", "more": "-O2", "most": "-O3",
              "size": "-Os", "fast": "-Ofast", "debug": "-Og", "z": "-Oz"}


class BuildError(Exception):
    pass


@dataclass
class BuildConfig:
    name: str
    project_dir: str
    defines: list = field(default_factory=list)
    includes: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    libs: list = field(default_factory=list)
    lib_dirs: list = field(default_factory=list)
    linker_script: str = ""
    compile_flags: list = field(default_factory=list)
    link_flags: list = field(default_factory=list)
    c_std: str = ""
    gcc_major: str = ""


def _resolve(project_dir, value):
    v = value.strip().strip('"')
    prefix = "${workspace_loc:/${ProjName}/"
    if v.startswith(prefix):
        return os.path.normpath(os.path.join(project_dir, v[len(prefix):].rstrip("}")))
    if v.startswith("${workspace_loc:/${ProjName}}"):
        return os.path.normpath(project_dir)
    # Plain relative paths are relative to the build folder (obj/), one level below the project
    return os.path.normpath(os.path.join(project_dir, "obj", v))


def _options(cfg_elem):
    out = {}
    for opt in cfg_elem.iter("option"):
        sc = opt.get("superClass", "")
        key = sc[len(OPT):] if sc.startswith(OPT) else sc
        val = opt.get("value") or ""
        if val.startswith(OPT):
            val = val[len(OPT):]
        out[key] = (val, [lv.get("value") for lv in opt.findall("listOptionValue")])
    return out


def _val(o, key, default=""):
    return o.get(key, (default, []))[0] or default


def _list(o, key):
    return o.get(key, ("", []))[1]


def _true(o, key):
    return _val(o, key) == "true"


def _march(o):
    base = _val(o, "target.isa.base", "target.arch.rv32i").rsplit(".", 1)[-1]
    s = base
    if base not in ("rv32g", "rv64g"):
        if _true(o, "target.isa.multiply"):
            s += "m"
        if _true(o, "target.isa.atomic"):
            s += "a"
        fp = _val(o, "target.isa.fp", "isa.fp.none").rsplit(".", 1)[-1]
        s += {"single": "f", "double": "fd", "quad": "fdq"}.get(fp, "")
        if _true(o, "target.isa.compressed"):
            s += "c"
        if _true(o, "target.isa.b"):
            s += "_zba_zbb_zbc_zbs"
        if _true(o, "target.isa.xw"):
            s += "_xw"
    return "-march=" + s


def _mabi(o):
    abi = _val(o, "target.abi.integer", "abi.integer.ilp32").rsplit(".", 1)[-1]
    fp = _val(o, "target.abi.fp", "abi.fp.none").rsplit(".", 1)[-1]
    return "-mabi=" + abi + {"single": "f", "double": "d"}.get(fp, "")


def _sources(project_dir, cfg_elem):
    files = set()
    for e in cfg_elem.iter("entry"):
        if e.get("kind") != "sourcePath":
            continue
        root = os.path.join(project_dir, e.get("name") or "")
        if not os.path.isdir(root):
            continue
        excluded = {x for x in (e.get("excluding") or "").split("|") if x}
        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
            rel_dir = "" if rel_dir == "." else rel_dir + "/"
            dirnames[:] = [d for d in dirnames if (rel_dir + d) not in excluded and d not in SKIP_DIRS]
            for f in filenames:
                if os.path.splitext(f)[1] in SOURCE_EXTS and (rel_dir + f) not in excluded:
                    files.add(os.path.normpath(os.path.join(dirpath, f)))
    return sorted(files, key=lambda p: os.path.relpath(p, project_dir).replace("\\", "/"))


def parse_cproject(project_dir):
    project_dir = os.path.abspath(project_dir)
    name = ET.parse(os.path.join(project_dir, ".project")).getroot().findtext("name")
    cfg_elem = ET.parse(os.path.join(project_dir, ".cproject")).getroot().findall(".//configuration")[0]
    o = _options(cfg_elem)
    cfg = BuildConfig(name=name, project_dir=project_dir)
    cfg.defines = list(_list(o, "c.compiler.defs"))
    cfg.includes = [_resolve(project_dir, v) for v in _list(o, "c.compiler.include.paths")]
    cfg.sources = _sources(project_dir, cfg_elem)
    cfg.libs = list(_list(o, "c.linker.libs"))
    cfg.lib_dirs = [_resolve(project_dir, v) for v in _list(o, "c.linker.paths")]
    scripts = _list(o, "c.linker.scriptfile")
    if not scripts:
        raise BuildError("no linker script in .cproject")
    cfg.linker_script = _resolve(project_dir, scripts[0])
    std = _val(o, "c.compiler.std").rsplit(".", 1)[-1]
    cfg.c_std = "-std=" + std if std and std != "default" else ""
    cfg.gcc_major = _val(o, "target.rvGcc").rsplit(".", 1)[-1]
    flags = [_march(o), _mabi(o), OPT_LEVELS.get(_val(o, "optimization.level", "size").rsplit(".", 1)[-1], "-Os")]
    for key, flag in [("optimization.messagelength", "-fmessage-length=0"),
                      ("optimization.signedchar", "-fsigned-char"),
                      ("optimization.functionsections", "-ffunction-sections"),
                      ("optimization.datasections", "-fdata-sections"),
                      ("optimization.nocommon", "-fno-common"),
                      ("optimization.mrs.highcode", "--param=highcode-gen-section-name=1")]:
        if _true(o, key):
            flags.append(flag)
    flags.append("-g")
    cfg.compile_flags = flags
    link = []
    if _true(o, "c.linker.nostart"):
        link.append("-nostartfiles")
    if _true(o, "c.linker.gcsections"):
        link += ["-Xlinker", "--gc-sections"]
    for f in _list(o, "c.linker.flags"):
        link += ["-Xlinker", f] if f.startswith("--") else [f]
    if _true(o, "c.linker.usenewlibnano"):
        link.append("--specs=nano.specs")
    if _true(o, "c.linker.usenewlibnosys"):
        link.append("--specs=nosys.specs")
    cfg.link_flags = link
    return cfg


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout + r.stderr).strip()
    if out:
        print(out)
    if r.returncode != 0:
        raise BuildError(f"command failed ({r.returncode}): {cmd[0]} ... {cmd[-1]}")


def build(cfg, out_dir, toolchain, extra_defines):
    tool = lambda n: os.path.join(toolchain, f"riscv-wch-elf-{n}.exe")
    for n in ("gcc", "objcopy"):
        if not os.path.isfile(tool(n)):
            raise BuildError(f"toolchain program not found: {tool(n)}")
    version = subprocess.run([tool("gcc"), "-dumpversion"], capture_output=True, text=True).stdout.strip()
    if cfg.gcc_major and not version.startswith(cfg.gcc_major + "."):
        raise BuildError(f"project wants GCC{cfg.gcc_major}, toolchain is GCC {version}")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    inc = [f"-I{i}" for i in cfg.includes]
    defs = [f"-D{d}" for d in cfg.defines + list(extra_defines)]
    objects = []
    for src in cfg.sources:
        rel = os.path.relpath(src, cfg.project_dir)
        obj = os.path.join(out_dir, os.path.splitext(rel)[0] + ".o")
        os.makedirs(os.path.dirname(obj), exist_ok=True)
        if src.endswith(".S"):
            extra = ["-x", "assembler-with-cpp"] + inc
        else:
            extra = defs + inc + ([cfg.c_std] if cfg.c_std else [])
        _run([tool("gcc")] + cfg.compile_flags + extra + ["-c", src, "-o", obj])
        objects.append(obj)
    elf = os.path.join(out_dir, cfg.name + ".elf")
    hexfile = os.path.join(out_dir, cfg.name + ".hex")
    mapfile = os.path.join(out_dir, cfg.name + ".map")
    _run([tool("gcc")] + cfg.compile_flags + ["-T", cfg.linker_script] + cfg.link_flags
         + [f"-L{d}" for d in cfg.lib_dirs] + [f"-Wl,-Map,{mapfile}", "-o", elf]
         + objects + [f"-l{l}" for l in cfg.libs])
    _run([tool("objcopy"), "-O", "ihex", elf, hexfile])
    return {"elf": elf, "hex": hexfile, "map": mapfile}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a WCH MounRiver .cproject with the MRS2 GCC12 toolchain")
    ap.add_argument("project_dir")
    ap.add_argument("--out", help="output folder (default: <project>/obj)")
    ap.add_argument("--define", action="append", default=[], help="extra define, e.g. SPIKE_VERSION=2")
    ap.add_argument("--toolchain", default=DEFAULT_TOOLCHAIN)
    a = ap.parse_args(argv)
    cfg = parse_cproject(a.project_dir)
    try:
        paths = build(cfg, a.out or os.path.join(cfg.project_dir, "obj"), a.toolchain, a.define)
    except BuildError as e:
        print(f"BUILD FAILED: {e}")
        return 1
    for k, v in paths.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest discover -s tools -p "test_*.py" -v`
Expected: all 4 tests PASS. The regression tests take about a minute each.

If a regression hash differs, compare the link order first. Run `riscv-wch-elf-objdump -h` on both ELFs: the objects must be in sorted relative-path order, and the libraries in `.cproject` order. Do not edit the expected hashes.

- [ ] **Step 6: Commit**

```bash
git add .gitignore tools/mrs_build.py tools/test_mrs_build.py
git commit -m "feat(tools): add .cproject-driven MRS2 GCC12 build tool

Reproduces the verified CH584F_Mesh_Relay_LED and CH584F_BLE_LED hex files byte for byte.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Image checker and hex merger

**Files:**
- Create: `tools/check_image.py`
- Create: `tools/merge_hex.py`
- Test: `tools/test_check_image.py`
- Test: `tools/test_merge_hex.py`

**Interfaces:**
- Consumes: the verified build `C:\Embedded\WCH\projects\CH584F_BLE_LED\obj\CH584F_BLE_LED.elf` / `.hex` (stack top `0x20018000`, image at `0x00000`–`0x24887`).
- Produces:
  - `merge_hex.read_hex(path: str, offset: int = 0) -> dict[int, int]`. Handles record types 00/01/02/04; raises `ValueError` on a checksum error.
  - `merge_hex.merge(parts: list[dict[int, int]]) -> dict[int, int]`. Raises `ValueError("overlap at 0x...")`.
  - `merge_hex.write_hex(mem: dict[int, int], path: str) -> None`. Writes 16-byte data records, type-04 records at every 64 KB boundary, and a final EOF record.
  - CLI: `python tools/merge_hex.py --out OUT.hex IN.hex[@0xOFFSET] ...`
  - `check_image.check(hexfile: str, flash_start: int, flash_end: int, elf: str | None = None, stack_top: int | None = None, nm: str = DEFAULT_NM) -> list[str]`. Returns error messages; empty means OK.
  - CLI: `python tools/check_image.py --hex H [--elf E --stack-top 0x...] --flash 0xSTART:0xEND`. Prints `OK ...` or the errors and exits 1.

- [ ] **Step 1: Write the failing tests**

`tools/test_merge_hex.py`:

```python
import os
import tempfile
import unittest

import merge_hex


class MergeHexTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="merge_hex_test_")

    def path(self, name):
        return os.path.join(self.dir, name)

    def test_round_trip_above_64k(self):
        mem = {0x0FFFE: 1, 0x0FFFF: 2, 0x10000: 3, 0x4E000: 0xAA}
        merge_hex.write_hex(mem, self.path("a.hex"))
        self.assertEqual(merge_hex.read_hex(self.path("a.hex")), mem)
        text = open(self.path("a.hex")).read()
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
```

`tools/test_check_image.py`:

```python
import unittest

import check_image

ELF = r"C:\Embedded\WCH\projects\CH584F_BLE_LED\obj\CH584F_BLE_LED.elf"
HEX = r"C:\Embedded\WCH\projects\CH584F_BLE_LED\obj\CH584F_BLE_LED.hex"


class CheckImageTests(unittest.TestCase):
    def test_good_image_passes(self):
        self.assertEqual(check_image.check(HEX, 0x0, 0x70000, elf=ELF, stack_top=0x20018000), [])

    def test_wrong_stack_top_is_reported(self):
        errors = check_image.check(HEX, 0x0, 0x70000, elf=ELF, stack_top=0x20020000)
        self.assertEqual(len(errors), 1)
        self.assertIn("0x20018000", errors[0])

    def test_image_outside_flash_range_is_reported(self):
        errors = check_image.check(HEX, 0x1000, 0x27000)
        self.assertTrue(any("outside" in e for e in errors))

    def test_hex_only_check_works_without_elf(self):
        self.assertEqual(check_image.check(HEX, 0x0, 0x70000), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest discover -s tools -p "test_*image*.py" -v`, then `python -m unittest discover -s tools -p "test_merge*.py" -v`
Expected: ERROR `No module named 'check_image'` and `No module named 'merge_hex'`.

- [ ] **Step 3: Write `tools/merge_hex.py`**

```python
"""Read, merge and write Intel HEX files.

CLI: python tools/merge_hex.py --out OUT.hex IN1.hex IN2.hex@0x26000 ...
     (an @offset is added to every address of that input)
"""
import argparse
import sys


def read_hex(path, offset=0):
    mem, base = {}, 0
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line.startswith(":"):
                continue
            raw = bytes.fromhex(line[1:])
            if sum(raw) & 0xFF:
                raise ValueError(f"{path}:{lineno}: checksum error")
            n, addr, typ, data = raw[0], (raw[1] << 8) | raw[2], raw[3], raw[4:4 + raw[0]]
            if typ == 0x00:
                for i, b in enumerate(data):
                    mem[base + addr + i + offset] = b
            elif typ == 0x01:
                break
            elif typ == 0x02:
                base = ((data[0] << 8) | data[1]) << 4
            elif typ == 0x04:
                base = ((data[0] << 8) | data[1]) << 16
    return mem


def merge(parts):
    out = {}
    for part in parts:
        for addr, b in part.items():
            if addr in out:
                raise ValueError(f"overlap at 0x{addr:05X}")
            out[addr] = b
    return out


def _record(addr, typ, data):
    body = bytes([len(data), (addr >> 8) & 0xFF, addr & 0xFF, typ]) + bytes(data)
    return ":" + body.hex().upper() + f"{(-sum(body)) & 0xFF:02X}"


def write_hex(mem, path):
    lines, upper = [], None
    addrs = sorted(mem)
    i = 0
    while i < len(addrs):
        start = addrs[i]
        if start >> 16 != upper:
            upper = start >> 16
            lines.append(_record(0, 0x04, [(upper >> 8) & 0xFF, upper & 0xFF]))
        chunk = [mem[start]]
        j = i + 1
        while (j < len(addrs) and addrs[j] == start + len(chunk) and len(chunk) < 16
               and addrs[j] >> 16 == upper):
            chunk.append(mem[addrs[j]])
            j += 1
        lines.append(_record(start & 0xFFFF, 0x00, chunk))
        i = j
    lines.append(":00000001FF")
    with open(path, "w", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge Intel HEX files (optionally shifted)")
    ap.add_argument("--out", required=True)
    ap.add_argument("inputs", nargs="+", help="file.hex or file.hex@0xOFFSET")
    a = ap.parse_args(argv)
    parts = []
    for spec in a.inputs:
        path, _, off = spec.partition("@")
        parts.append(read_hex(path, int(off, 16) if off else 0))
    try:
        mem = merge(parts)
    except ValueError as e:
        print(f"MERGE FAILED: {e}")
        return 1
    write_hex(mem, a.out)
    print(f"wrote {a.out}: {len(mem):,} bytes, 0x{min(mem):05X}-0x{max(mem):05X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write `tools/check_image.py`**

```python
"""Check a built image: every hex byte inside [flash_start, flash_end) and, optionally,
the ELF symbol _eusrstack equal to the expected stack top.

CLI: python tools/check_image.py --hex H [--elf E --stack-top 0x20018000] --flash 0x1000:0x27000
"""
import argparse
import os
import subprocess
import sys

from merge_hex import read_hex

DEFAULT_NM = (r"C:\MounRiver\MounRiver_Studio2\resources\app\resources\win32\components"
              r"\WCH\Toolchain\RISC-V Embedded GCC12\bin\riscv-wch-elf-nm.exe")


def symbol_value(elf, name, nm=DEFAULT_NM):
    out = subprocess.run([nm, elf], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == name:
            return int(parts[0], 16)
    return None


def check(hexfile, flash_start, flash_end, elf=None, stack_top=None, nm=DEFAULT_NM):
    errors = []
    mem = read_hex(hexfile)
    lo, hi = min(mem), max(mem)
    if lo < flash_start or hi >= flash_end:
        errors.append(f"image 0x{lo:05X}-0x{hi:05X} lies outside flash 0x{flash_start:05X}-0x{flash_end - 1:05X}")
    if elf is not None and stack_top is not None:
        top = symbol_value(elf, "_eusrstack", nm)
        if top is None:
            errors.append("_eusrstack not found in ELF")
        elif top != stack_top:
            errors.append(f"stack top 0x{top:08X}, expected 0x{stack_top:08X}")
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check flash range and stack top of a built image")
    ap.add_argument("--hex", required=True)
    ap.add_argument("--elf")
    ap.add_argument("--stack-top", type=lambda s: int(s, 16))
    ap.add_argument("--flash", required=True, help="0xSTART:0xEND (END exclusive)")
    a = ap.parse_args(argv)
    start, end = (int(x, 16) for x in a.flash.split(":"))
    errors = check(a.hex, start, end, a.elf, a.stack_top)
    name = os.path.basename(a.hex)
    if errors:
        for e in errors:
            print(f"FAIL {name}: {e}")
        return 1
    mem = read_hex(a.hex)
    print(f"OK {name}: {len(mem):,} bytes at 0x{min(mem):05X}-0x{max(mem):05X}"
          + (f", stack top 0x{a.stack_top:08X}" if a.stack_top else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run all tool tests**

Run: `python -m unittest discover -s tools -p "test_*.py" -v`
Expected: all tests PASS (5 merge, 4 check, 4 build).

- [ ] **Step 6: Commit**

```bash
git add tools/merge_hex.py tools/check_image.py tools/test_merge_hex.py tools/test_check_image.py
git commit -m "feat(tools): add Intel HEX merger and image range/stack checker

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Assemble the CH584 update-capable projects (spike check S1)

**Files:**
- Create: `spike/README.md`
- Create: `spike/assemble_spike.py`
- Test: `spike/test_assemble_spike.py`
- Generated (git-ignored): `spike/node/`, `spike/iap/`, `spike/jumpiap/`, `spike/build/`

**Interfaces:**
- Consumes: `tools/mrs_build.py`, `tools/check_image.py` (Tasks 1–2).
- Produces:
  - `assemble_spike.assemble(dest: str, force: bool = False) -> dict[str, str]`. Maps `"node"`, `"iap"`, `"jumpiap"` to project folders. Project names are `spike_node`, `spike_iap`, `spike_jumpiap`.
  - `assemble_spike.edit(path: str, pattern: str, repl: str, label: str, flags: int = 0, expand: bool = False) -> None`. Raises `SystemExit` unless the pattern matches exactly once. With `expand=True`, `repl` may use `\g<1>`.
  - `assemble_spike.apply_board_edits(dirs: dict) -> None`
  - CLI: `python spike/assemble_spike.py [--dest spike] [--force]`

- [ ] **Step 1: Write `spike/README.md`**

```bash
cat > spike/README.md <<'EOF'
# Step 0 spike (THROWAWAY)

Feasibility checks S1-S6 from docs/specs/2026-10-03-ch584f-mesh-hub-design.md section 11.
Nothing here is production code. The firmware sub-project starts from its own spec and plan.

- assemble_spike.py: copies WCH update-capable mesh projects from the SDK and applies CH584/board/spike edits
- FLASHING.md: how the user flashes the merged spike image
- TESTS.md: hardware test script (nRF Mesh) with result columns
- REPORT.md: go/no-go per check and proposed spec amendments
EOF
```

- [ ] **Step 2: Write the failing test** at `spike/test_assemble_spike.py`

```python
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m unittest discover -s spike -p "test_*.py" -v`
Expected: ERROR `No module named 'assemble_spike'`

- [ ] **Step 4: Write `spike/assemble_spike.py`**

```python
"""Assemble the THROWAWAY Step-0 spike projects from the official WCH CH585 EVT SDK.

  node/     <- EVT/EXAM/BLE/MESH/adv_vendor_self_provision_with_peripheral
  iap/      <- EVT/EXAM/BLE/MESH/adv_vendor_self_provision_IAP
  jumpiap/  <- EVT/EXAM/BLE/MESH/adv_vendor_self_provision_JumpIAP

Linked SDK folders are copied in, then CH584 and WeAct-board edits are applied.
Every edit must match exactly once, otherwise the script stops.
"""
import argparse
import os
import re
import shutil
import sys

SDK = r"C:\Embedded\WCH\SDK\CH585EVT\EVT\EXAM"
MESH = os.path.join(SDK, "BLE", "MESH")
WEACT_HAL = r"C:\Embedded\WCH\WeActStudio.WCH-BLE-Core\Examples\CH584\ble\broadcaster\ble\HAL"
PROJECTS = {
    "node": ("adv_vendor_self_provision_with_peripheral", "spike_node"),
    "iap": ("adv_vendor_self_provision_IAP", "spike_iap"),
    "jumpiap": ("adv_vendor_self_provision_JumpIAP", "spike_jumpiap"),
}


def load(path):
    raw = open(path, "rb").read()
    return raw.decode("latin-1").replace("\r\n", "\n"), b"\r\n" in raw


def save(path, text, crlf):
    open(path, "wb").write((text.replace("\n", "\r\n") if crlf else text).encode("latin-1"))


def edit(path, pattern, repl, label, flags=0, expand=False):
    text, crlf = load(path)
    new, n = re.subn(pattern, (lambda m: m.expand(repl)) if expand else (lambda m: repl), text, flags=flags)
    if n != 1:
        sys.exit(f"ABORT [{path}] '{label}' matched {n} times (expected 1)")
    save(path, new, crlf)
    print(f"  ok  {os.path.basename(os.path.dirname(path))}/{os.path.basename(path)}: {label}")


def copy_project(sdk_name, dst, new_name):
    src = os.path.join(MESH, sdk_name)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("obj"))
    project_text, _ = load(os.path.join(src, ".project"))
    for link_name, uri in re.findall(r"<link>\s*<name>([^<]+)</name>\s*<type>2</type>\s*<locationURI>([^<]+)</locationURI>",
                                     project_text):
        m = re.match(r"PARENT-(\d+)-PROJECT_LOC/(.+)", uri)
        base = src
        for _ in range(int(m.group(1))):
            base = os.path.dirname(base)
        shutil.copytree(os.path.join(base, m.group(2)), os.path.join(dst, link_name))
    project = os.path.join(dst, ".project")
    edit(project, r"(<projectDescription>\s*<name>)[^<]+(</name>)", r"\g<1>" + new_name + r"\g<2>", "project name",
         expand=True)
    edit(project, r"[ \t]*<linkedResources>.*?</linkedResources>\n", "", "linked folders copied in", flags=re.S)


def assemble(dest, force=False):
    dirs = {key: os.path.join(dest, key) for key in PROJECTS}
    for key, d in dirs.items():
        if os.path.exists(d):
            if not force:
                sys.exit(f"ABORT: {d} exists (use --force to rebuild generated spike projects)")
            shutil.rmtree(d)
    os.makedirs(dest, exist_ok=True)
    for key, (sdk_name, new_name) in PROJECTS.items():
        print(f"{new_name}: copying {sdk_name}")
        copy_project(sdk_name, dirs[key], new_name)
    apply_board_edits(dirs)
    return dirs


def apply_board_edits(dirs):
    node, iap, jumpiap = dirs["node"], dirs["iap"], dirs["jumpiap"]
    for d in (node, iap):
        edit(os.path.join(d, "Ld", "Link.ld"), r"RAM \(xrw\) : ORIGIN = 0x20005000, LENGTH = 108K",
             "RAM (xrw) : ORIGIN = 0x20005000, LENGTH = 76K /* CH584: 96K RAM; WCH layout keeps 0x20000000-0x20004FFF for the ROM library */",
             "RAM 76K (CH584)")
    edit(os.path.join(jumpiap, "Ld", "Link.ld"), r"RAM \(xrw\) : ORIGIN = 0x20000000, LENGTH = 128K",
         "RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 96K /* CH584 */", "RAM 96K (CH584)")
    edit(os.path.join(node, ".cproject"), r'(\t+)<listOptionValue builtIn="false" value="DEBUG=0"/>\n',
         r'\g<0>\g<1><listOptionValue builtIn="false" value="CLK_OSC32K=0"/>' + "\n"
         + r'\g<1><listOptionValue builtIn="false" value="DCDC_ENABLE=1"/>' + "\n",
         "defines CLK_OSC32K=0, DCDC_ENABLE=1", expand=True)
    edit(os.path.join(node, "APP", "app_main.c"), re.escape("    HSECFG_Capacitance(HSECap_18p);"),
         "#if(defined(DCDC_ENABLE)) && (DCDC_ENABLE == TRUE)\n    PWR_DCDCCfg(ENABLE);\n#endif\n"
         "    HSECFG_Capacitance(HSECap_10p); // WeAct CH584F core board value",
         "DC-DC call + HSE 10p")
    shutil.copyfile(os.path.join(WEACT_HAL, "KEY.c"), os.path.join(node, "HAL", "KEY.c"))
    shutil.copyfile(os.path.join(WEACT_HAL, "include", "KEY.h"), os.path.join(node, "HAL", "include", "KEY.h"))
    print("  ok  node/HAL: WeAct KEY.c/KEY.h (KEY2 removed)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Assemble the throwaway Step-0 spike projects")
    ap.add_argument("--dest", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    assemble(a.dest, a.force)
    print("ASSEMBLED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m unittest discover -s spike -p "test_*.py" -v`
Expected: 4 tests PASS.

If an `ABORT ... matched 0 times` appears, inspect the real text with `tr -d '\r' < FILE | grep -n -A2 PATTERN | cat -A` and fix the pattern. Never loosen the exact-once rule.

- [ ] **Step 6: Assemble into `spike/` and build all three projects (spike check S1)**

```bash
python spike/assemble_spike.py --force
for p in node iap jumpiap; do python tools/mrs_build.py spike/$p --out spike/build/$p || exit 1; done
```

Expected: each build ends with `elf: ... hex: ... map: ...`. Record the `Memory region` lines the linker prints.

- [ ] **Step 7: Check every image against the CH584 layout**

```bash
python tools/check_image.py --elf spike/build/node/spike_node.elf --hex spike/build/node/spike_node.hex --stack-top 0x20018000 --flash 0x1000:0x27000
python tools/check_image.py --elf spike/build/iap/spike_iap.elf --hex spike/build/iap/spike_iap.hex --stack-top 0x20018000 --flash 0x4D000:0x4E000
python tools/check_image.py --hex spike/build/jumpiap/spike_jumpiap.hex --flash 0x0:0x1000
python tools/check_image.py --hex spike/node/MESH_LIB/CH584BLE_ROM_MESH.hex --flash 0x4E000:0x70000
```

Expected: four `OK` lines. The ROM library is `128,704 bytes at 0x4E000-0x6D6C3`. **S1 passes when all four print `OK`.** Record the node's flash and RAM usage in `spike/RESULTS.md` (created in Task 6).

- [ ] **Step 8: Commit**

```bash
git add spike/README.md spike/assemble_spike.py spike/test_assemble_spike.py
git commit -m "feat(spike): assemble CH584 update-capable mesh projects (S1)

Node/IAP RAM 76K, JumpIAP RAM 96K, WeAct board settings, real PWR_DCDCCfg call.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Spike node behaviour (PB-GATT, proxy, static OOB, test publisher, version blink)

**Files:**
- Modify: `spike/assemble_spike.py` (add `apply_spike_features`; call it from `assemble`)
- Modify: `spike/test_assemble_spike.py` (add `SpikeFeatureTests`)

**Interfaces:**
- Consumes: `assemble_spike.edit`, `assemble_spike.assemble` (Task 3), `tools/mrs_build.py` (Task 1).
- Produces in the generated node firmware:
  - Static OOB `00112233445566778899AABBCCDDEEFF`
  - Boot blink count = `SPIKE_VERSION` (default 1; build v2 with `--define SPIKE_VERSION=2`)
  - READING test messages to `0xC001` every 5 s once provisioned and an AppKey is bound
  - Symbols `spike_publish`, `spike_boot_blink`, `spike_static_oob`
  - The custom WCH peripheral is **not started**: `Peripheral_Init` is no longer called and is removed by `--gc-sections`.
  - Acknowledged `WRT` (0xCC) messages are passed to `App_trans_model_reveived` as well as `MSG` (0xCF). The SDK passes only `MSG`.

- [ ] **Step 1: Write the failing test.** Append to `spike/test_assemble_spike.py`, above the `if __name__` line:

```python
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

    def test_peripheral_entry_points_are_guarded(self):
        per = read(os.path.join(self.node, "APP", "peripheral.c"))
        self.assertEqual(per.count("    return; // SPIKE: custom peripheral not started"), 3)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest discover -s spike -p "test_*.py" -v`
Expected: the 3 new tests FAIL (for example `AssertionError: Regex didn't match: '#define CONFIG_BLE_MESH_PROXY\\s+1\\b'`). The 4 Task 3 tests still pass.

- [ ] **Step 3: Implement `apply_spike_features`** in `spike/assemble_spike.py`.

First add these module-level constants after `PROJECTS`:

```python
SPIKE_BLOCK = """/* ===== SPIKE (throwaway, Step 0) ===================================== */
#ifndef SPIKE_VERSION
#define SPIKE_VERSION        1
#endif
#define SPIKE_PUB_EVT        (1 << 8)
#define SPIKE_PUB_PERIOD     (1600 * 5)            // 5 s (TMOS tick = 0.625 ms)
#define SPIKE_READINGS_GROUP 0xC001

// Fixed static OOB for the spike only: 00112233445566778899AABBCCDDEEFF
static const uint8_t spike_static_oob[16] = {
    0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
    0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF,
};

static void spike_led(BOOL on)
{
    GPIOB_ModeCfg(GPIO_Pin_6, GPIO_ModeOut_PP_5mA);
    on ? GPIOB_ResetBits(GPIO_Pin_6) : GPIOB_SetBits(GPIO_Pin_6);
}

static void spike_boot_blink(uint8_t count)
{
    uint8_t i;
    for(i = 0; i < count; i++)
    {
        spike_led(TRUE);
        DelayMs(200);
        spike_led(FALSE);
        DelayMs(300);
    }
}

// READING payload (spec 4.3): 0x01, temperature int16 0.01 C, humidity uint16 0.01 %RH, sequence
static void spike_publish(void)
{
    static uint8_t seq = 0;
    static int16_t temp = 2500;
    const uint16_t rh = 5000;
    uint8_t p[6];

    if(!bt_mesh_is_provisioned() || (vnd_models[0].keys[0] == BLE_MESH_KEY_UNUSED))
    {
        return;
    }
    temp = (temp >= 3000) ? 2000 : (int16_t)(temp + 10);
    p[0] = 0x01;
    p[1] = (uint8_t)(temp & 0xFF);
    p[2] = (uint8_t)((temp >> 8) & 0xFF);
    p[3] = (uint8_t)(rh & 0xFF);
    p[4] = (uint8_t)((rh >> 8) & 0xFF);
    p[5] = seq++;
    vendor_model_srv_send(SPIKE_READINGS_GROUP, p, sizeof(p));
}
/* ===================================================================== */

"""

SPIKE_EVENT = """    if(events & SPIKE_PUB_EVT)
    {
        spike_publish();
        tmos_start_task(App_TaskID, SPIKE_PUB_EVT, SPIKE_PUB_PERIOD);
        return (events ^ SPIKE_PUB_EVT);
    }

"""
```

Then add the function after `apply_board_edits`:

```python
def apply_spike_features(node):
    cfg = os.path.join(node, "APP", "include", "app_mesh_config.h")
    edit(cfg, r"(#define CONFIG_BLE_MESH_PROXY\s+)0\b", r"\g<1>1", "PROXY 1", expand=True)
    edit(cfg, r"(#define CONFIG_BLE_MESH_PB_GATT\s+)0\b", r"\g<1>1", "PB_GATT 1", expand=True)
    edit(cfg, r"(#define CONFIG_MESH_UNSEG_LENGTH_DEF\s+)\(221\)", r"\g<1>(7)", "UNSEG_LENGTH 7", expand=True)
    edit(cfg, r"(#define CONFIG_MESH_RX_SDU_DEF\s+)\(192\)", r"\g<1>(256)", "RX_SDU 256", expand=True)

    app = os.path.join(node, "APP", "app.c")
    edit(app, re.escape("static const struct bt_mesh_prov app_prov = {"),
         SPIKE_BLOCK + "static const struct bt_mesh_prov app_prov = {", "spike block")
    edit(app, re.escape("    .uuid = dev_uuid,\n    .link_open = link_open,"),
         "    .uuid = dev_uuid,\n"
         "    .static_val = spike_static_oob, // SPIKE: fixed test value; production reads the factory page\n"
         "    .static_val_len = sizeof(spike_static_oob),\n"
         "    .link_open = link_open,", "static OOB in prov struct")
    edit(app, re.escape("    GAPRole_PeripheralInit();\n    Peripheral_Init();\n"),
         "    spike_boot_blink(SPIKE_VERSION); // SPIKE: custom WCH peripheral not started; the phone uses the mesh proxy\n",
         "no custom peripheral, boot blink")
    edit(app, re.escape("    HAL_KeyInit();\n    HalKeyConfig(keyPress);\n}"),
         "    HAL_KeyInit();\n    HalKeyConfig(keyPress);\n"
         "    tmos_start_task(App_TaskID, SPIKE_PUB_EVT, SPIKE_PUB_PERIOD);\n}", "start publish timer")
    edit(app, re.escape("    // Discard unknown events\n    return 0;\n}"),
         SPIKE_EVENT + "    // Discard unknown events\n    return 0;\n}", "publish event handler")
    # WCH's handler only passes MSG (0xCF) to App_trans_model_reveived; spec 4.2 sends unicast commands as WRT (0xCC)
    edit(app, r"(OP_VENDOR_MESSAGE_TRANSPARENT_WRT\)\n    \{\n(?:[ \t]*//[^\n]*\n)*[ \t]*APP_DBG\(\"len %d, data 0x%02x from 0x%04x\", "
              r"val->vendor_model_srv_Event\.write\.len,\n[ \t]*val->vendor_model_srv_Event\.write\.pdata\[0\],\n"
              r"[ \t]*val->vendor_model_srv_Event\.write\.addr\);\n)",
         r"\g<1>        App_trans_model_reveived(val->vendor_model_srv_Event.write.pdata, val->vendor_model_srv_Event.write.len," + "\n"
         + r"            val->vendor_model_srv_Event.write.addr); // SPIKE: unicast commands arrive as acknowledged WRT (spec 4.2)" + "\n",
         "route WRT to command handler", expand=True)

    per = os.path.join(node, "APP", "peripheral.c")
    for header in ("void peripheralChar4Notify(uint8_t *pValue, uint16_t len)\n{\n",
                   "void Peripheral_AdvertData_Privisioned(uint8_t privisioned)\n{\n",
                   "void Peripheral_TerminateLink(void)\n{\n"):
        edit(per, re.escape(header), header + "    return; // SPIKE: custom peripheral not started\n",
             "guard " + header.split("(")[0].split()[-1])
```

Finally, in `assemble`, change `apply_board_edits(dirs)` to:

```python
    apply_board_edits(dirs)
    apply_spike_features(dirs["node"])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s spike -p "test_*.py" -v`
Expected: 7 tests PASS.

- [ ] **Step 5: Build v1 and v2 of the node, and check them**

```bash
python spike/assemble_spike.py --force
python tools/mrs_build.py spike/node --out spike/build/node_v1 || exit 1
python tools/mrs_build.py spike/node --out spike/build/node_v2 --define SPIKE_VERSION=2 || exit 1
for v in v1 v2; do python tools/check_image.py --elf spike/build/node_$v/spike_node.elf --hex spike/build/node_$v/spike_node.hex --stack-top 0x20018000 --flash 0x1000:0x27000; done
NM="/c/MounRiver/MounRiver_Studio2/resources/app/resources/win32/components/WCH/Toolchain/RISC-V Embedded GCC12/bin/riscv-wch-elf-nm.exe"
"$NM" spike/build/node_v1/spike_node.elf | grep -E " (spike_publish|spike_boot_blink|spike_static_oob|Peripheral_Init)$"
```

Expected:
- two `OK` lines;
- `nm` lists `spike_publish`, `spike_boot_blink` and `spike_static_oob`, and does **not** list `Peripheral_Init`.

If the build fails, fix the edit that caused it. Do not change mesh library files.

- [ ] **Step 6: Commit**

```bash
git add spike/assemble_spike.py spike/test_assemble_spike.py
git commit -m "feat(spike): PB-GATT + proxy + static OOB node with test publisher and version blink

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Flash package and flashing instructions (approval gate)

**Files:**
- Create: `spike/package.py`
- Test: `spike/test_package.py`
- Create: `spike/FLASHING.md`
- Generated (git-ignored): `spike/out/spike_full_v1_plus_v2B.hex`, `spike/out/spike_full_v1.hex`

**Interfaces:**
- Consumes: `merge_hex.read_hex`, `merge_hex.merge`, `merge_hex.write_hex` (Task 2); the builds from Tasks 3–4 (`spike/build/{jumpiap,iap,node_v1,node_v2}`); `spike/node/MESH_LIB/CH584BLE_ROM_MESH.hex`.
- Produces:
  - `package.make_package(spike_dir: str, include_v2_in_b: bool) -> str`. Returns the output path and raises `ValueError` on overlap, a range violation, or a non-CH584 ROM file.
  - CLI: `python spike/package.py`. Writes both packages and prints their ranges.

- [ ] **Step 1: Write the failing test** at `spike/test_package.py`

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest discover -s spike -p "test_package.py" -v`
Expected: ERROR `No module named 'package'`

- [ ] **Step 3: Write `spike/package.py`**

```python
"""Merge the spike images into one WCHISPTool object file.

Layout (spec 6.2): JumpIAP 0x00000 | node v1 0x01000 | [node v2 shifted +0x26000 -> 0x27000] | IAP 0x4D000 | ROM lib 0x4E000
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from merge_hex import merge, read_hex, write_hex  # noqa: E402

REGIONS = {"jumpiap": (0x00000, 0x01000), "node_v1": (0x01000, 0x27000), "node_v2_in_b": (0x27000, 0x4D000),
           "iap": (0x4D000, 0x4E000), "rom": (0x4E000, 0x70000)}


def check_rom_file(path):
    if "CH584" not in os.path.basename(path):
        raise ValueError(f"ROM library must be the CH584 build, got {os.path.basename(path)}")


def _part(name, mem):
    lo, hi = REGIONS[name]
    if min(mem) < lo or max(mem) >= hi:
        raise ValueError(f"{name}: 0x{min(mem):05X}-0x{max(mem):05X} outside 0x{lo:05X}-0x{hi - 1:05X}")
    return mem


def make_package(spike_dir, include_v2_in_b):
    b = os.path.join(spike_dir, "build")
    rom = os.path.join(spike_dir, "node", "MESH_LIB", "CH584BLE_ROM_MESH.hex")
    check_rom_file(rom)
    parts = [_part("jumpiap", read_hex(os.path.join(b, "jumpiap", "spike_jumpiap.hex"))),
             _part("node_v1", read_hex(os.path.join(b, "node_v1", "spike_node.hex"))),
             _part("iap", read_hex(os.path.join(b, "iap", "spike_iap.hex"))),
             _part("rom", read_hex(rom))]
    if include_v2_in_b:
        parts.append(_part("node_v2_in_b", read_hex(os.path.join(b, "node_v2", "spike_node.hex"), 0x26000)))
    os.makedirs(os.path.join(spike_dir, "out"), exist_ok=True)
    out = os.path.join(spike_dir, "out", "spike_full_v1_plus_v2B.hex" if include_v2_in_b else "spike_full_v1.hex")
    write_hex(merge(parts), out)
    return out


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    for v2 in (True, False):
        path = make_package(here, v2)
        mem = read_hex(path)
        print(f"{os.path.basename(path)}: {len(mem):,} bytes, 0x{min(mem):05X}-0x{max(mem):05X}")
```

- [ ] **Step 4: Run the tests and build the packages**

Run:

```bash
python -m unittest discover -s spike -p "test_package.py" -v
python spike/package.py
```

Expected: 2 tests PASS. Then two lines, `spike_full_v1_plus_v2B.hex: ... 0x00000-0x6D6C3` and `spike_full_v1.hex: ...`.

- [ ] **Step 5: Write `spike/FLASHING.md`**

```bash
cat > spike/FLASHING.md <<'EOF'
# Flashing the spike image (user action, needs explicit approval)

Board: ONE WeAct CH584F (label it "spike"). Its current firmware is replaced.

1. WCHISPTool v4.0: Chip Series CH58x, Chip Model CH584, Dnld Port USB.
2. Untick "Automatic Download When Device Connect".
3. Object File1 = spike/out/spike_full_v1_plus_v2B.hex (ticked). Object File2-4 and DataFlash File empty/unticked.
4. Tick "Clear DataFlash" (mandatory: wipes old mesh data and the OTA image flag at DataFlash 0x7000).
5. Hold BOOT, plug USB, release BOOT, click Search, then Download. Expect "Succeed!" and Succ:1.
6. After the restart the LED blinks ONCE (version 1 is running). Note the result in RESULTS.md.

Version 2 sits in the update buffer (0x27000) and is only installed by the S5 test in TESTS.md.
To return to plain version 1 later, flash spike/out/spike_full_v1.hex the same way.
EOF
```

- [ ] **Step 6: Commit, then STOP for approval**

```bash
git add spike/package.py spike/test_package.py spike/FLASHING.md
git commit -m "feat(spike): merged flash package (v1 + v2 in update buffer) and flashing steps

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Ask the user in chat: *"Approve flashing `spike/out/spike_full_v1_plus_v2B.hex` to one board per `spike/FLASHING.md`?"* **Do not continue to Task 6 until the user says yes and reports the result.**

---

### Task 6: Hardware tests S2–S5 with nRF Mesh (user and agent)

**Files:**
- Create: `spike/TESTS.md` (the script the user follows)
- Create: `spike/RESULTS.md` (filled in while testing)

**Interfaces:**
- Consumes: the flashed board (Task 5), the nRF Mesh app (Nordic Semiconductor, Google Play), and the S1 numbers (Task 3).
- Produces: `RESULTS.md`, one row per test ID, each PASS / FAIL / PARTIAL with the exact observation. Task 7 reads it.

- [ ] **Step 1: Write `spike/TESTS.md`**

```bash
cat > spike/TESTS.md <<'EOF'
# Spike hardware tests (nRF Mesh for Android)

Static OOB (correct): 00112233445566778899AABBCCDDEEFF
Static OOB (WRONG, for the negative test): FFEEDDCCBBAA99887766554433221100
Node address: whatever nRF Mesh assigns (usually 0x0002). Below, AAAA = that address little-endian (0x0002 -> 0200).
Vendor model: company 0x07D7, model 0x0000. WRT opcode byte = 0xCC, MSG = 0xCF, ACK = 0xCD.
If the app asks for a 6-bit opcode instead of the full byte, use 0x0C for WRT. Record which form the app wanted.
Parameters = TID byte + payload. Use a NEW TID (01, 02, 03 ...) for every message unless a step says otherwise.

| ID | Step | Expected |
|---|---|---|
| T1 | Power the board. Open nRF Mesh, add node, scan. | Board listed as unprovisioned; LED blinked once at power-up |
| T2 | Provision it choosing Static OOB, enter the WRONG value | Provisioning FAILS (confirmation error); board stays unprovisioned |
| T3 (S2) | Provision again with the CORRECT static OOB | Provisioning succeeds; node shows Config Server, Health Server, Vendor model 0x07D7/0x0000 |
| T4 | Add the network App Key to the node; bind it to the vendor model 0x0000 | Both succeed |
| T5 (S3) | Vendor model: send WRT (0xCC), params 01 A4 AAAA (ask status) | App shows ACK (0xCD) with param 01; then a MSG (0xCF) whose params are: server TID (0x80-0xBF), 84, AAAA, 00 |
| T6 | Send the SAME message again with TID 01 | ACK arrives again but NO new 84 reply (duplicate dropped) |
| T7 (S4) | Add group 0xC001 to the proxy filter (Network or Proxy settings) and wait 15 s | MSG (0xCF) every 5 s: TID, 01, temp lo, temp hi, 88, 13, seq (temperature 20.00-30.00 C, humidity 0x1388 = 50.00 %) |
| T8 (S5 install) | Send WRT, params 02 A9 AAAA (OTA end) | NO ACK is expected (the board resets inside the handler before acknowledging; the app may show a timeout); the LED then blinks THREE times (version 2 installed by the IAP) |
| T9 | Reconnect if needed; send WRT, params 03 A4 AAAA | 84 reply again: still provisioned after the install |
| T10 (S5 path) | Send WRT, params 04 A6 AAAA (image info) | MSG with params: TID, 86, AAAA, 00 60 02 00 (image size 0x26000), block size (2 bytes), chip id (2 bytes), 00 |
| T11 | Unplug and replug the board | LED blinks three times; node still answers T9-style ask status (use TID 05) |
EOF
```

- [ ] **Step 2: Create `spike/RESULTS.md`**

```bash
cat > spike/RESULTS.md <<'EOF'
# Spike results

| ID | Result (PASS/FAIL/PARTIAL) | Observation (exact text/bytes shown by the app) |
|---|---|---|
| S1 build | | node flash/RAM: |
| T1 | | |
| T2 | | |
| T3 | | |
| T4 | | |
| T5 | | |
| T6 | | |
| T7 | | |
| T8 | | |
| T9 | | |
| T10 | | |
| T11 | | |
EOF
```

Fill in the S1 row from Task 3 step 7 straight away.

- [ ] **Step 3: Commit the script**

```bash
git add spike/TESTS.md spike/RESULTS.md
git commit -m "docs(spike): hardware test script and results sheet

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Run T1–T4 with the user.** Give the user one test at a time, collect what the app shows (a screenshot or exact text), and record it in `RESULTS.md`. **T2 must fail before T3 is attempted.** If T2 succeeds, stop: static OOB is not enforced, and that is a blocking finding.

- [ ] **Step 5: Run T5 (S3).** Record the exact opcode form the app accepted and every byte it displays.

- [ ] **Step 6: Run T6 (duplicate TID).** Expected: an ACK but no `84` reply. Record the result.

- [ ] **Step 7: Run T7 (S4).** If the app has no way to show unsolicited group messages, record PARTIAL. Note which app screens were tried; the reception path is then re-tested in app sub-project 2.

- [ ] **Step 8: Run T8–T11 (S5).** Record the blink counts and replies.

- [ ] **Step 9: Commit the results**

```bash
git add spike/RESULTS.md
git commit -m "docs(spike): record hardware test results T1-T11

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: S6 desk check, spike report and proposed spec amendments

**Files:**
- Create: `spike/REPORT.md`
- Modify (only after user approval): `docs/specs/2026-10-03-ch584f-mesh-hub-design.md`, sections 6.3, 6.4, 7, 11 and 13

**Interfaces:**
- Consumes: `spike/RESULTS.md` (Task 6) and the SDK header `spike/node/MESH_LIB/MESH_LIB.h`.
- Produces: `REPORT.md` with go/no-go for spec step 1 (needs S1–S4) and step 3 (needs S5), plus amendment text.

- [ ] **Step 1: S6 desk check.** Look for any way to put a name into the proxy advertising.

```bash
tr -d '\r' < spike/node/MESH_LIB/MESH_LIB.h | iconv -f GB18030 -t UTF-8 -c | grep -n -i -E "name|scan_rsp|scanrsp|adv_data|set_adv|gap_adv" | head -40
```

Expected: no public API for proxy scan-response or name. Record S6 as **not available: the name is shown via INFO only**, unless a matching API is listed. In that case record the API and mark S6 for a later test.

- [ ] **Step 2: Write `spike/REPORT.md`**

The report covers the fixed findings below plus the measured results. Copy each row from `RESULTS.md`.

```bash
cat > spike/REPORT.md <<'EOF'
# Step 0 spike report

## Results
(copy the table from RESULTS.md here, one line per ID, with PASS/FAIL/PARTIAL)

## Go / no-go
- Firmware sub-project (needs S1-S4): GO if S1, T2 (fails), T3, T5, T6 pass and T7 is PASS or PARTIAL.
- OTA sub-project (needs S5): GO if T8-T11 pass.

## Findings to carry into the spec (proposed amendments)
1. OTA over the mesh IS supported by WCH's update-capable example (commands 0xA6/0xA7/0xA8/0xA9 handled in
   App_trans_model_reveived from any mesh source). Spec section 7 "OTA over the mesh is not supported" is wrong:
   replace it with "the phone sends WCH OTA commands as vendor messages through the proxy to any board;
   throughput to be measured in the OTA sub-project".
2. DataFlash 0x7000 is the OTA ImageFlag page (OTA_DATAFLASH_ADD = 0x77000 - FLASH_ROM_MAX_SIZE), the same
   address as the BLE SNV default. Spec 6.3: reserve 0x7000 for the ImageFlag and disable BLE SNV (no bonding is used).
3. DCDC_ENABLE only takes effect with an explicit PWR_DCDCCfg(ENABLE) call in main(); the mesh examples lack it.
   Spec 6.1: state the call explicitly.
4. CONFIG.h hard-codes CHIP_ID ID_CH585; WCH OTA image info reports it. Firmware spec: report ID_CH584 (0x92).
5. The custom WCH peripheral (0xFFE0 service) is not needed; the phone link is the mesh proxy.
6. S6 result (from the desk check).
7. nRF Mesh behaviour notes (opcode entry form, how unsolicited messages are shown).
8. WCH's vendor handler only passes MSG (0xCF) to its command handler; WRT (0xCC) was only logged. The spike
   routes WRT to the handler. The firmware must handle WRT for unicast commands (spec 4.2), and commands that
   reset the board (OTA end, factory reset) are never acknowledged, so the app must treat a missing ACK there as expected.
EOF
```

Replace the two placeholder lines (`(copy the table ...)` and items 6–7) with the real content before committing.

- [ ] **Step 3: Commit the report**

```bash
git add spike/REPORT.md
git commit -m "docs(spike): Step 0 report with go/no-go and proposed spec amendments

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Present the report and ask for amendment approval.** In chat, show the go/no-go and findings 1–7, and ask: *"Approve these spec amendments?"*

- [ ] **Step 5: Apply the approved amendments only.** Edit the spec sections named in the findings, adding a line `Amended <today's date, YYYY-MM-DD> after Step 0 spike (spike/REPORT.md)` under the Status header, then commit:

```bash
git add docs/specs/2026-10-03-ch584f-mesh-hub-design.md
git commit -m "docs(spec): amend after Step 0 spike findings

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
