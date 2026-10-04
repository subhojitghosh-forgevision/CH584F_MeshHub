"""Throwaway diagnostic: minimal Bluetooth Mesh Profile 1.0.1 crypto (network, proxy config, upper transport).

AES-128 comes from Windows CNG (bcrypt.dll) via ctypes, so nothing has to be installed.
Implements: AES-ECB, AES-CMAC (RFC 4493), AES-CCM (RFC 3610, no AAD), s1, k2, k4, network/proxy PDU
encrypt/decrypt with obfuscation, application-key upper transport, access opcode parsing.
"""
import ctypes
from collections import namedtuple
from ctypes import wintypes

_bcrypt = ctypes.WinDLL("bcrypt.dll")
_alg = ctypes.c_void_p()
if _bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(_alg), ctypes.c_wchar_p("AES"), None, 0) != 0:
    raise OSError("BCryptOpenAlgorithmProvider(AES) failed")
_mode = ctypes.create_unicode_buffer("ChainingModeECB")
if _bcrypt.BCryptSetProperty(_alg, ctypes.c_wchar_p("ChainingMode"), _mode, ctypes.sizeof(_mode), 0) != 0:
    raise OSError("BCryptSetProperty(ChainingModeECB) failed")


def aes(key, block):
    """AES-128 encrypt one 16-byte block."""
    hkey = ctypes.c_void_p()
    kbuf = ctypes.create_string_buffer(bytes(key), 16)
    if _bcrypt.BCryptGenerateSymmetricKey(_alg, ctypes.byref(hkey), None, 0, kbuf, 16, 0) != 0:
        raise OSError("BCryptGenerateSymmetricKey failed")
    try:
        inp = ctypes.create_string_buffer(bytes(block), 16)
        out = ctypes.create_string_buffer(16)
        done = wintypes.ULONG()
        if _bcrypt.BCryptEncrypt(hkey, inp, 16, None, None, 0, out, 16, ctypes.byref(done), 0) != 0:
            raise OSError("BCryptEncrypt failed")
        return out.raw
    finally:
        _bcrypt.BCryptDestroyKey(hkey)


def xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def _dbl(b):
    n = int.from_bytes(b, "big") << 1
    if b[0] & 0x80:
        n ^= 0x87
    return (n & ((1 << 128) - 1)).to_bytes(16, "big")


def cmac(key, msg):
    k1 = _dbl(aes(key, bytes(16)))
    k2_ = _dbl(k1)
    blocks = max(1, (len(msg) + 15) // 16)
    tail = msg[16 * (blocks - 1):]
    if len(msg) and len(tail) == 16:
        last = xor(tail, k1)
    else:
        last = xor(tail + b"\x80" + bytes(15 - len(tail)), k2_)
    x = bytes(16)
    for i in range(blocks - 1):
        x = aes(key, xor(x, msg[16 * i:16 * i + 16]))
    return aes(key, xor(x, last))


def _ctr_block(key, nonce, i):
    return aes(key, b"\x01" + nonce + i.to_bytes(2, "big"))


def _ccm_tag(key, nonce, msg, mic_len):
    b0 = bytes([((mic_len - 2) // 2) << 3 | 0x01]) + nonce + len(msg).to_bytes(2, "big")
    x = aes(key, b0)
    for i in range(0, len(msg), 16):
        x = aes(key, xor(x, msg[i:i + 16].ljust(16, b"\x00")))
    return xor(x[:mic_len], _ctr_block(key, nonce, 0)[:mic_len])


def _ctr(key, nonce, data):
    out = bytearray()
    for j, i in enumerate(range(0, len(data), 16)):
        chunk = data[i:i + 16]
        out += xor(chunk, _ctr_block(key, nonce, j + 1)[:len(chunk)])
    return bytes(out)


def ccm_encrypt(key, nonce, msg, mic_len):
    return _ctr(key, nonce, msg) + _ccm_tag(key, nonce, msg, mic_len)


def ccm_decrypt(key, nonce, data, mic_len):
    if len(data) < mic_len:
        return None
    pt = _ctr(key, nonce, data[:-mic_len])
    return pt if _ccm_tag(key, nonce, pt, mic_len) == data[-mic_len:] else None


def s1(m):
    return cmac(bytes(16), m)


def k2(n, p):
    t = cmac(s1(b"smk2"), n)
    t1 = cmac(t, p + b"\x01")
    t2 = cmac(t, t1 + p + b"\x02")
    t3 = cmac(t, t2 + p + b"\x03")
    return t1[15] & 0x7F, t2, t3


def k4(n):
    t = cmac(s1(b"smk4"), n)
    return cmac(t, b"id6" + b"\x01")[15] & 0x3F


class NetKeys:
    def __init__(self, netkey):
        self.nid, self.enc, self.priv = k2(bytes(netkey), b"\x00")


NetMsg = namedtuple("NetMsg", "ivi nid ctl ttl seq src dst transport")


def _nonce(kind, ctl_ttl, seq, src, iv, proxy):
    if proxy:
        return b"\x03\x00" + seq.to_bytes(3, "big") + src.to_bytes(2, "big") + b"\x00\x00" + iv.to_bytes(4, "big")
    return bytes([kind, ctl_ttl]) + seq.to_bytes(3, "big") + src.to_bytes(2, "big") + b"\x00\x00" + iv.to_bytes(4, "big")


def _pecb(keys, iv, enc_part):
    return aes(keys.priv, bytes(5) + iv.to_bytes(4, "big") + enc_part[:7])


def net_encrypt(keys, iv, ctl, ttl, seq, src, dst, transport, proxy=False):
    ctl_ttl = (ctl << 7) | ttl
    mic_len = 8 if ctl else 4
    enc = ccm_encrypt(keys.enc, _nonce(0x00, ctl_ttl, seq, src, iv, proxy),
                      dst.to_bytes(2, "big") + transport, mic_len)
    header = bytes([ctl_ttl]) + seq.to_bytes(3, "big") + src.to_bytes(2, "big")
    return bytes([((iv & 1) << 7) | keys.nid]) + xor(header, _pecb(keys, iv, enc)[:6]) + enc


def net_decrypt(pdu, keys, iv_index, proxy=False):
    if len(pdu) < 14 or (pdu[0] & 0x7F) != keys.nid:
        return None
    ivi = pdu[0] >> 7
    iv = iv_index if ivi == (iv_index & 1) else iv_index - 1
    header = xor(pdu[1:7], _pecb(keys, iv, pdu[7:])[:6])
    ctl, ttl = header[0] >> 7, header[0] & 0x7F
    seq = int.from_bytes(header[1:4], "big")
    src = int.from_bytes(header[4:6], "big")
    pt = ccm_decrypt(keys.enc, _nonce(0x00, header[0], seq, src, iv, proxy), pdu[7:], 8 if ctl else 4)
    if pt is None:
        return None
    return NetMsg(ivi, keys.nid, ctl, ttl, seq, src, int.from_bytes(pt[:2], "big"), pt[2:])


def _app_nonce(seq, src, dst, iv, szmic=0):
    return (bytes([0x01, szmic << 7]) + seq.to_bytes(3, "big") + src.to_bytes(2, "big") + dst.to_bytes(2, "big")
            + iv.to_bytes(4, "big"))


def app_encrypt(appkey, access, seq, src, dst, iv, szmic=0):
    return ccm_encrypt(appkey, _app_nonce(seq, src, dst, iv, szmic), access, 8 if szmic else 4)


def app_decrypt(appkey, upper, seq, src, dst, iv, szmic=0):
    return ccm_decrypt(appkey, _app_nonce(seq, src, dst, iv, szmic), upper, 8 if szmic else 4)


def seq_auth(seq, seq_zero):
    return seq - ((seq - seq_zero) & 0x1FFF)


def parse_access(access):
    """Return (opcode, params). Vendor opcodes are returned as (byte, company_id)."""
    b0 = access[0]
    if b0 >> 6 == 3:
        return (b0, int.from_bytes(access[1:3], "little")), access[3:]
    if b0 >> 7 == 1:
        return int.from_bytes(access[:2], "big"), access[2:]
    return b0, access[1:]
