"""Build, check and package the MeshHub firmware.

    python firmware/build.py      -> firmware/out/meshhub-<major>.<minor>.hex

Layout (system spec 6.2): JumpIAP 0x00000 | node (application) 0x01000 | IAP 0x4D000 | CH584 ROM library 0x4E000
"""
import glob
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
        project = os.path.join(HERE, folder)
        if not os.path.isdir(project):
            raise FirmwareError(f"{name}: project folder not found: {project}")
        cfg = mrs_build.parse_cproject(project)
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


def run(out, images=IMAGES, rom_hex=ROM_HEX):
    """Build, check and package into out. Old packages are deleted first, so a failed run leaves none behind."""
    for old in glob.glob(os.path.join(out, "meshhub-*.hex")):
        os.remove(old)
    try:
        paths = build_all(os.path.join(out, "build"), images)
        major, minor = read_version()
        pkg = package({n: p["hex"] for n, p in paths.items()}, rom_hex,
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


def main():
    return run(os.path.join(HERE, "out"))


if __name__ == "__main__":
    sys.exit(main())
