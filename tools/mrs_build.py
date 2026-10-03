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
