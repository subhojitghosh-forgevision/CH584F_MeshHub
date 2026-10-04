"""Throwaway diagnostic: act as a Mesh Proxy client on the laptop (S4 check).

Waits until the board advertises the Mesh Proxy service (0x1828, i.e. the phone has disconnected), connects,
reads the IV index from the Secure Network Beacon, sets the proxy filter to an empty EXCLUSION list (forward
everything), then decodes every forwarded Network PDU for SECONDS and prints vendor READINGs.

Usage: python proxy_client.py ADDRESS NETKEY_HEX [--appkey HEX] [--src 0x7F00] [--seconds 40] [--iv 0] [--wait 300]
The NetKey is taken from the command line only and never written to disk.
"""
import argparse
import asyncio
import time

from bleak import BleakClient, BleakScanner

import mesh_crypto as mc

PROXY_SVC = "00001828-0000-1000-8000-00805f9b34fb"
DATA_IN = "00002add-0000-1000-8000-00805f9b34fb"
DATA_OUT = "00002ade-0000-1000-8000-00805f9b34fb"
SDK_APPKEY = "0023456789abcdef0023456789abcdef"  # finding F2: the key the SDK example self-binds


def now():
    return time.strftime("%H:%M:%S")


async def wait_for_proxy_adverts(address, wait_s):
    print(f"[{now()}] waiting up to {wait_s:.0f} s for {address} to advertise Mesh Proxy 0x1828 "
          f"(tap DISCONNECT in nRF Mesh)", flush=True)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        found = await BleakScanner.discover(timeout=3.0, return_adv=True)
        for addr, (dev, adv) in found.items():
            if addr.upper() == address.upper():
                sd = {k.lower(): bytes(v) for k, v in (adv.service_data or {}).items()}
                if PROXY_SVC in sd:
                    d = sd[PROXY_SVC]
                    kind = {0: "Network ID", 1: "Node Identity"}.get(d[0], f"type {d[0]}")
                    print(f"[{now()}] board advertises 0x1828 ({kind} {d[1:].hex()}), RSSI {adv.rssi} dBm", flush=True)
                    return dev
    return None


class Reassembler:
    def __init__(self):
        self.parts = {}

    def add(self, src, seq, transport):
        h = transport[1:4]
        szmic = h[0] >> 7
        seq_zero = ((h[0] & 0x7F) << 6) | (h[1] >> 2)
        seg_o = ((h[1] & 0x03) << 3) | (h[2] >> 5)
        seg_n = h[2] & 0x1F
        key = (src, seq_zero)
        entry = self.parts.setdefault(key, {"segs": {}, "seq_auth": mc.seq_auth(seq, seq_zero), "szmic": szmic})
        entry["segs"][seg_o] = transport[4:]
        if len(entry["segs"]) == seg_n + 1:
            del self.parts[key]
            upper = b"".join(entry["segs"][i] for i in range(seg_n + 1))
            return upper, entry["seq_auth"] & 0xFFFFFF, entry["szmic"], seg_n + 1
        return None


async def main(a):
    netkey = bytes.fromhex(a.netkey)
    appkey = bytes.fromhex(a.appkey)
    keys = mc.NetKeys(netkey)
    app_aid = mc.k4(appkey)
    print(f"NID 0x{keys.nid:02X}, app key AID 0x{app_aid:02X} (key not printed)", flush=True)

    dev = await wait_for_proxy_adverts(a.address, a.wait)
    if dev is None:
        print(f"[{now()}] TIMEOUT: board never advertised 0x1828 (phone still connected?)", flush=True)
        return

    queue = asyncio.Queue()
    sar = {"buf": bytearray(), "type": None}

    def on_notify(_, data):
        data = bytes(data)
        if a.raw:
            print(f"[{now()}] RAW notify {data.hex()}", flush=True)
        s, typ = data[0] >> 6, data[0] & 0x3F
        if s == 0:
            queue.put_nowait((typ, data[1:]))
        elif s == 1:
            sar["buf"], sar["type"] = bytearray(data[1:]), typ
        else:
            sar["buf"] += data[1:]
            if s == 3:
                queue.put_nowait((sar["type"], bytes(sar["buf"])))

    stats = {"net": 0, "bad": 0, "readings": 0}
    reasm = Reassembler()
    async with BleakClient(dev, timeout=20.0) as client:
        print(f"[{now()}] connected; MTU {client.mtu_size}", flush=True)
        if client.services.get_service(PROXY_SVC) is None:
            print("Mesh Proxy service 0x1828 NOT present", flush=True)
            return
        for ch in client.services.get_service(PROXY_SVC).characteristics:
            print(f"    char {ch.uuid}  {','.join(ch.properties)}", flush=True)
        await client.start_notify(DATA_OUT, on_notify)

        iv = a.iv
        try:
            while True:
                typ, payload = await asyncio.wait_for(queue.get(), 4.0)
                if typ == 1 and payload and payload[0] == 0x01 and len(payload) >= 14:
                    iv = int.from_bytes(payload[10:14], "big")
                    print(f"[{now()}] Secure Network Beacon: flags 0x{payload[1]:02X}, network ID {payload[2:10].hex()}, "
                          f"IV index {iv}", flush=True)
                    break
                print(f"[{now()}] (pre-filter PDU type {typ}, {len(payload)} B)", flush=True)
        except asyncio.TimeoutError:
            print(f"[{now()}] no beacon within 4 s; using IV index {iv}", flush=True)

        seq = int(time.time()) & 0x0FFFFF
        for attempt in range(a.filter_tries):
            pdu = mc.net_encrypt(keys, iv, ctl=1, ttl=0, seq=seq, src=a.src, dst=0x0000, transport=b"\x00\x01",
                                 proxy=(a.cfg_nonce == "proxy"))
            await client.write_gatt_char(DATA_IN, b"\x02" + pdu, response=a.with_response)
            print(f"[{now()}] sent Proxy Set Filter Type = EXCLUSION (empty list) from 0x{a.src:04X}, seq {seq}: "
                  f"02{pdu.hex()}", flush=True)
            seq += 1
            await asyncio.sleep(1.0)
        if a.ask is not None:
            access = bytes([0xCC, 0xD7, 0x07, a.ask, 0xA4]) + a.node.to_bytes(2, "little")
            upper = mc.app_encrypt(appkey, access, seq, a.src, a.node, iv)
            pdu = mc.net_encrypt(keys, iv, ctl=0, ttl=4, seq=seq, src=a.src, dst=a.node,
                                 transport=bytes([0x40 | app_aid]) + upper)
            await client.write_gatt_char(DATA_IN, b"\x00" + pdu, response=a.with_response)
            print(f"[{now()}] sent vendor WRT ask-status TID 0x{a.ask:02X} to 0x{a.node:04X}, seq {seq}: 00{pdu.hex()}",
                  flush=True)
            seq += 1

        end = time.time() + a.seconds
        while time.time() < end:
            try:
                typ, payload = await asyncio.wait_for(queue.get(), max(0.1, end - time.time()))
            except asyncio.TimeoutError:
                break
            if typ == 2:
                m = mc.net_decrypt(payload, keys, iv, proxy=True)
                used = "proxy"
                if m is None:
                    m, used = mc.net_decrypt(payload, keys, iv, proxy=False), "network"
                print(f"[{now()}] proxy config PDU decrypted with the {used} nonce: {m is not None}", flush=True)
                if m and m.transport[:1] == b"\x03":
                    ftype = {0: "INCLUSION", 1: "EXCLUSION"}.get(m.transport[1], m.transport[1])
                    print(f"[{now()}] Proxy Filter Status from 0x{m.src:04X}: type {ftype}, list size "
                          f"{int.from_bytes(m.transport[2:4], 'big')}", flush=True)
                else:
                    print(f"[{now()}] proxy config PDU not decoded ({payload.hex()})", flush=True)
                continue
            if typ == 1:
                continue
            if typ != 0:
                print(f"[{now()}] PDU type {typ} ignored", flush=True)
                continue
            stats["net"] += 1
            m = mc.net_decrypt(payload, keys, iv)
            if m is None:
                stats["bad"] += 1
                print(f"[{now()}] network PDU not decrypted (other network/key?) {payload.hex()}", flush=True)
                continue
            head = f"[{now()}] src 0x{m.src:04X} -> dst 0x{m.dst:04X} ttl {m.ttl} seq {m.seq}"
            if m.ctl:
                print(f"{head} CONTROL opcode 0x{m.transport[0] & 0x7F:02X} {m.transport[1:].hex()}", flush=True)
                continue
            b0 = m.transport[0]
            seg, akf, aid = b0 >> 7, (b0 >> 6) & 1, b0 & 0x3F
            if seg:
                done = reasm.add(m.src, m.seq, m.transport)
                if done is None:
                    continue
                upper, seq_a, szmic, nseg = done
                head += f" (segmented x{nseg}, SeqAuth {seq_a})"
            else:
                upper, seq_a, szmic = m.transport[1:], m.seq, 0
            if not akf:
                print(f"{head} device-key access ({upper.hex()})", flush=True)
                continue
            if aid != app_aid:
                print(f"{head} app key AID 0x{aid:02X} is not the SDK key", flush=True)
                continue
            access = mc.app_decrypt(appkey, upper, seq_a, m.src, m.dst, iv, szmic)
            if access is None:
                print(f"{head} access TransMIC FAILED", flush=True)
                continue
            op, params = mc.parse_access(access)
            if op == (0xCF, 0x07D7) and len(params) >= 7 and params[1] == 0x01:
                stats["readings"] += 1
                temp = int.from_bytes(params[2:4], "little", signed=True) / 100
                rh = int.from_bytes(params[4:6], "little") / 100
                print(f"{head} READING tid 0x{params[0]:02X} temp {temp:.2f} C rh {rh:.2f} % seq {params[6]}  "
                      f"[access {access.hex()}]", flush=True)
            else:
                ops = f"0x{op[0]:02X}/CID 0x{op[1]:04X}" if isinstance(op, tuple) else f"0x{op:X}"
                print(f"{head} access opcode {ops} params {params.hex()}", flush=True)
    print(f"[{now()}] done: {stats['net']} network PDUs, {stats['bad']} not decrypted, {stats['readings']} READINGs",
          flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("address")
    p.add_argument("netkey")
    p.add_argument("--appkey", default=SDK_APPKEY)
    p.add_argument("--src", type=lambda s: int(s, 0), default=0x7F00)
    p.add_argument("--seconds", type=float, default=40)
    p.add_argument("--iv", type=int, default=0)
    p.add_argument("--wait", type=float, default=300)
    p.add_argument("--filter-tries", type=int, default=1)
    p.add_argument("--ask", type=lambda s: int(s, 0), default=None, help="also send WRT ask-status with this TID")
    p.add_argument("--node", type=lambda s: int(s, 0), default=0x0004)
    p.add_argument("--raw", action="store_true", help="print every notification")
    p.add_argument("--cfg-nonce", choices=["proxy", "network"], default="proxy",
                   help="nonce for proxy configuration messages (spec: proxy)")
    p.add_argument("--with-response", action="store_true", help="use GATT write with response")
    asyncio.run(main(p.parse_args()))
