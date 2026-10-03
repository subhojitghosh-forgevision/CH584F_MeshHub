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
