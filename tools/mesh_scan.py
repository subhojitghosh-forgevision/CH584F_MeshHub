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
