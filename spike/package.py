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
