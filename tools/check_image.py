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
    if stack_top is not None and elf is None:
        raise ValueError("stack_top needs an ELF to check against")
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
    if a.stack_top is not None and a.elf is None:
        ap.error("--stack-top needs --elf")
    start, end = (int(x, 16) for x in a.flash.split(":"))
    errors = check(a.hex, start, end, a.elf, a.stack_top)
    name = os.path.basename(a.hex)
    if errors:
        for e in errors:
            print(f"FAIL {name}: {e}")
        return 1
    mem = read_hex(a.hex)
    print(f"OK {name}: {len(mem):,} bytes at 0x{min(mem):05X}-0x{max(mem):05X}"
          + (f", stack top 0x{a.stack_top:08X}" if a.elf and a.stack_top is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
